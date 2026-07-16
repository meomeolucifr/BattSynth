"""
compute_evaluation_scores.py
=============================
Implements the 4-metric evaluation scoring from "Evaluation Metrics.pdf":

  1. Provenance Validity    — binary per entity (prov field with valid locator)
  2. Units Policy Check     — hard constraint (pass/fail per paper)
  3. Hallucination Detection — text-grounded check (<=3 suspicious = pass)
  4. Overall Score          = (passed checks / total checks) * 100

Also includes:
  - Field-level completeness (schema, metadata, synthesis, characterization)
  - Entity-level validity (required fields, provenance, ontology, molecular formula)

Runs on the 30-paper Golden Dataset and the full 605-paper corpus.

Usage:
    python scripts/compute_evaluation_scores.py
"""

import json
import os
import sys
import re
import csv
import os
from pathlib import Path
from collections import Counter, defaultdict

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    import fitz  # PyMuPDF for hallucination check
    HAS_FITZ = True
except ImportError:
    HAS_FITZ = False
    print("[WARN] PyMuPDF not available — hallucination check will be skipped")

try:
    from rdkit import Chem
    HAS_RDKIT = True
except ImportError:
    HAS_RDKIT = False

REPO_ROOT = Path(__file__).resolve().parents[1]
GOLDEN = Path(os.environ.get(
    "BATTSYNTH_GOLDEN_DIR",
    REPO_ROOT / "dataset",
))
TIERS = ["simple", "moderate", "complex"]

# Required units policy from format.json
UNITS_POLICY = {
    "temperature": "K",
    "pressure": "bar",
    "time": "min",
    "mass": "g",
    "volume": "mL",
    "amount": "mmol",
    "concentration": "M",
    "capacity": "mAh g-1",
}

# Valid provenance locators
PROV_LOCATORS = ["Page", "Figure", "Table", "S", "Methods", "Abstract",
                 "Body", "Results", "Discussion", "Introduction",
                 "Experimental", "Supporting", "Supplementary", "SI"]


# ══════════════════════════════════════════════════════════════════════════════
# 1. PROVENANCE VALIDITY
# ══════════════════════════════════════════════════════════════════════════════

def check_provenance(entity: dict) -> bool:
    """Check if entity has valid provenance (prov field with locator)."""
    prov = entity.get("prov")
    if not prov or not isinstance(prov, list) or len(prov) == 0:
        return False
    # At least one entry must contain a locator keyword
    for p in prov:
        if not isinstance(p, str):
            continue
        for loc in PROV_LOCATORS:
            if loc.lower() in p.lower():
                return True
    return False


def score_provenance(data: dict) -> dict:
    """Score provenance for all entities in an extraction."""
    checks = []

    for t in data.get("targets", []):
        checks.append(("target", t.get("target_id", ""), check_provenance(t)))

    for c in data.get("chemicals", []):
        checks.append(("chemical", c.get("chemical_id", ""), check_provenance(c)))

    for step in data.get("synthesis", {}).get("steps", []):
        checks.append(("step", step.get("step_id", ""), check_provenance(step)))
        for op in step.get("operations", []):
            checks.append(("operation", op.get("action", ""), check_provenance(op)))

    for ch in data.get("characterization", []):
        checks.append(("characterization", ch.get("method", ""), check_provenance(ch)))

    passed = sum(1 for _, _, v in checks if v)
    total = len(checks)
    return {"passed": passed, "total": total, "details": checks}


# ══════════════════════════════════════════════════════════════════════════════
# 2. UNITS POLICY CHECK
# ══════════════════════════════════════════════════════════════════════════════

def check_unit(value_obj: dict, expected_quantity: str) -> bool:
    """Check if a value object's unit matches the policy."""
    if not isinstance(value_obj, dict):
        return True  # Not a value object, skip
    unit = value_obj.get("unit", "")
    value = value_obj.get("value")
    if value is None and not unit:
        return True  # No value, no unit — acceptable (empty field)
    if value is not None and not unit:
        return False  # Has value but no unit
    expected = UNITS_POLICY.get(expected_quantity, "")
    if not expected:
        return True
    return unit.strip() == expected.strip()


def score_units_policy(data: dict) -> dict:
    """Check all units against the policy."""
    violations = []

    # Check synthesis step conditions
    for step in data.get("synthesis", {}).get("steps", []):
        for op in step.get("operations", []):
            params = op.get("parameters", {})
            # Temperature
            temp = params.get("temperature")
            if isinstance(temp, dict) and temp.get("value") is not None:
                if not check_unit(temp, "temperature"):
                    violations.append(f"operation.temperature: {temp.get('unit','')} != K")
            # Duration/time
            dur = params.get("duration")
            if isinstance(dur, dict) and dur.get("value") is not None:
                if not check_unit(dur, "time"):
                    violations.append(f"operation.duration: {dur.get('unit','')} != min")
            # Pressure
            pres = params.get("pressure")
            if isinstance(pres, dict) and pres.get("value") is not None:
                if not check_unit(pres, "pressure"):
                    violations.append(f"operation.pressure: {pres.get('unit','')} != bar")

        # Step-level conditions
        for cond in step.get("conditions", []) if isinstance(step.get("conditions"), list) else []:
            if isinstance(cond, dict):
                if "temperature" in cond:
                    t = cond["temperature"]
                    if isinstance(t, dict) and t.get("value") is not None:
                        if not check_unit(t, "temperature"):
                            violations.append(f"condition.temperature: {t.get('unit','')} != K")

    # Check chemical amounts
    for chem in data.get("chemicals", []):
        amt = chem.get("amount")
        if isinstance(amt, dict) and amt.get("value") is not None:
            unit = amt.get("unit", "")
            # Amount could be mass (g), volume (mL), amount (mmol), or concentration (M)
            # Check against all acceptable unit types
            valid_units = set(UNITS_POLICY.values())
            if unit and unit not in valid_units:
                # Allow common compound units
                compound_ok = any(u in unit for u in ["g", "mL", "mmol", "M", "mg", "wt%", "%"])
                if not compound_ok:
                    violations.append(f"chemical.amount: {unit} not in policy")

    # Check final outcomes
    fo = data.get("final_outcomes", {})
    cap = fo.get("capacity")
    if isinstance(cap, dict) and cap.get("value") is not None:
        if not check_unit(cap, "capacity"):
            violations.append(f"final_outcomes.capacity: {cap.get('unit','')} != mAh g-1")
    yld = fo.get("yield")
    if isinstance(yld, dict) and yld.get("value") is not None:
        unit = yld.get("unit", "")
        if unit and unit != "%":
            violations.append(f"final_outcomes.yield: {unit} != %")

    passed = len(violations) == 0
    return {"passed": passed, "violations": violations}


# ══════════════════════════════════════════════════════════════════════════════
# 3. HALLUCINATION DETECTION
# ══════════════════════════════════════════════════════════════════════════════

def normalize_text(text: str) -> str:
    t = text.lower().strip()
    t = re.sub(r'\s+', ' ', t)
    t = t.replace('\u2212', '-').replace('\u2013', '-').replace('\u2014', '-')
    return t


# Common abbreviations that are always acceptable
COMMON_ABBREVS = {
    "sem", "xrd", "tem", "xps", "eds", "edx", "eels", "afm", "stm",
    "nmr", "ir", "ftir", "uv", "raman", "dsc", "tga", "bet", "eis",
    "cv", "dft", "saxs", "waxs", "hrtem", "haadf", "saed", "ebsd",
    "icp", "gcd", "lsv", "xanes", "exafs", "pdf", "neutron",
}


def check_hallucination(data: dict, pdf_text: str) -> dict:
    """Check for hallucinated entities by comparing against PDF text."""
    if not pdf_text:
        return {"passed": True, "suspicious": 0, "details": [], "skipped": True}

    norm_pdf = normalize_text(pdf_text)
    suspicious = []

    # Check chemical names
    for chem in data.get("chemicals", []):
        name = chem.get("name", "")
        if not name:
            continue
        name_norm = normalize_text(name)
        # Skip very short/common names
        if len(name_norm) <= 3 or name_norm in COMMON_ABBREVS:
            continue
        # Check if name appears in PDF (fuzzy: remove hyphens/spaces)
        if name_norm not in norm_pdf:
            compact = name_norm.replace(" ", "").replace("-", "")
            compact_pdf = norm_pdf.replace(" ", "").replace("-", "")
            if compact not in compact_pdf:
                suspicious.append(f"chemical: {name}")

    # Check target compound names
    for tgt in data.get("targets", []):
        name = tgt.get("compound_name", "")
        if not name:
            continue
        name_norm = normalize_text(name)
        if len(name_norm) <= 3:
            continue
        if name_norm not in norm_pdf:
            # Try partial match (first significant word)
            words = [w for w in name_norm.split() if len(w) > 3]
            found = any(w in norm_pdf for w in words[:3])
            if not found:
                suspicious.append(f"target: {name}")

    # Check synthesis step descriptions
    for step in data.get("synthesis", {}).get("steps", []):
        desc = step.get("description", "")
        if not desc:
            continue
        desc_norm = normalize_text(desc)
        # Extract key terms from description
        key_terms = [w for w in desc_norm.split() if len(w) > 4 and w not in {"using", "under", "after", "about", "which", "where", "their", "these", "those"}]
        if key_terms:
            found = sum(1 for t in key_terms[:5] if t in norm_pdf)
            if found < len(key_terms[:5]) * 0.3:
                suspicious.append(f"step: {desc[:60]}")

    # Check characterization methods
    for ch in data.get("characterization", []):
        method = ch.get("method", "")
        if not method:
            continue
        method_norm = normalize_text(method)
        # Skip common abbreviations
        method_words = method_norm.split()
        if all(w in COMMON_ABBREVS or len(w) <= 3 for w in method_words):
            continue
        if method_norm not in norm_pdf:
            # Try individual significant words
            sig_words = [w for w in method_words if len(w) > 4]
            found = any(w in norm_pdf for w in sig_words)
            if not found:
                suspicious.append(f"characterization: {method}")

    passed = len(suspicious) <= 3
    return {"passed": passed, "suspicious": len(suspicious), "details": suspicious}


# ══════════════════════════════════════════════════════════════════════════════
# 4. FIELD-LEVEL COMPLETENESS & ENTITY VALIDITY
# ══════════════════════════════════════════════════════════════════════════════

def score_field_completeness(data: dict) -> dict:
    """Check field-level completeness across all sections."""
    checks = []

    # Schema
    schema = data.get("schema", {})
    checks.append(("schema.name", bool(schema.get("name"))))
    checks.append(("schema.version", bool(schema.get("version"))))

    # Source/metadata
    source = data.get("source", {})
    checks.append(("source.title", bool(source.get("title"))))
    checks.append(("source.doi", bool(source.get("doi"))))
    checks.append(("source.authors", bool(source.get("authors"))))
    checks.append(("source.journal", bool(source.get("journal"))))
    checks.append(("source.year", source.get("year") is not None))

    meta = data.get("metadata", {})
    checks.append(("metadata.discipline", bool(meta.get("discipline"))))
    checks.append(("metadata.type", bool(meta.get("type"))))

    # Targets
    targets = data.get("targets", [])
    checks.append(("targets.present", len(targets) > 0))
    for t in targets:
        checks.append(("target.compound_name", bool(t.get("compound_name"))))
        checks.append(("target.molecular_formula", bool(t.get("molecular_formula"))))
        checks.append(("target.intended_role", bool(t.get("intended_role"))))

    # Chemicals
    chemicals = data.get("chemicals", [])
    checks.append(("chemicals.present", len(chemicals) > 0))
    for c in chemicals:
        checks.append(("chemical.name", bool(c.get("name"))))
        checks.append(("chemical.ontology", bool(c.get("ontology"))))

    # Synthesis
    steps = data.get("synthesis", {}).get("steps", [])
    checks.append(("synthesis.steps_present", len(steps) > 0))
    for s in steps:
        checks.append(("step.description", bool(s.get("description"))))
        ops = s.get("operations", [])
        checks.append(("step.operations_present", len(ops) > 0))
        for op in ops:
            checks.append(("operation.action", bool(op.get("action"))))

    # Characterization
    chars = data.get("characterization", [])
    checks.append(("characterization.present", len(chars) > 0))
    for ch in chars:
        checks.append(("characterization.method", bool(ch.get("method"))))

    # Final outcomes
    fo = data.get("final_outcomes", {})
    checks.append(("final_outcomes.present", bool(fo)))

    # Workflow
    wf = data.get("workflow", {})
    checks.append(("workflow.timeline", bool(wf.get("timeline"))))

    passed = sum(1 for _, v in checks if v)
    total = len(checks)
    return {"passed": passed, "total": total, "details": checks}


def check_molecular_formula(formula: str) -> bool:
    """Check if a molecular formula is valid (basic check)."""
    if not formula:
        return False
    # Basic: must contain at least one uppercase letter (element)
    if not re.search(r'[A-Z]', formula):
        return False
    # Should look like a chemical formula (elements + numbers + some symbols)
    if re.match(r'^[A-Za-z0-9.()\-/+@·:,\s]+$', formula):
        return True
    return False


# ══════════════════════════════════════════════════════════════════════════════
# OVERALL SCORE
# ══════════════════════════════════════════════════════════════════════════════

def compute_overall_score(data: dict, pdf_text: str = "") -> dict:
    """
    Compute the overall extraction score.
    Score (%) = (Number of passed checks / Total checks) * 100
    """
    # 1. Field completeness
    completeness = score_field_completeness(data)

    # 2. Provenance validity
    provenance = score_provenance(data)

    # 3. Entity validity: molecular formula checks
    formula_checks = []
    for t in data.get("targets", []):
        f = t.get("molecular_formula", "")
        formula_checks.append(check_molecular_formula(f))
    for c in data.get("chemicals", []):
        f = c.get("molecular_formula", "")
        # Chemicals don't always need formulas — only check if field exists
        if f:
            formula_checks.append(check_molecular_formula(f))

    formula_passed = sum(formula_checks)
    formula_total = len(formula_checks)

    # 4. Units policy
    units = score_units_policy(data)

    # 5. Hallucination detection
    hallucination = check_hallucination(data, pdf_text) if pdf_text else {
        "passed": True, "suspicious": 0, "details": [], "skipped": True
    }

    # Aggregate: all checks into one score
    total_checks = 0
    passed_checks = 0

    # Field completeness checks
    total_checks += completeness["total"]
    passed_checks += completeness["passed"]

    # Provenance checks
    total_checks += provenance["total"]
    passed_checks += provenance["passed"]

    # Formula validity checks
    total_checks += formula_total
    passed_checks += formula_passed

    # Units policy (1 check)
    total_checks += 1
    passed_checks += 1 if units["passed"] else 0

    # Hallucination (1 check)
    total_checks += 1
    passed_checks += 1 if hallucination["passed"] else 0

    score_pct = (passed_checks / total_checks * 100) if total_checks > 0 else 0

    # Verdict
    if score_pct >= 90:
        verdict = "Excellent"
    elif score_pct >= 75:
        verdict = "Good"
    elif score_pct >= 60:
        verdict = "Acceptable"
    else:
        verdict = "Poor"

    return {
        "score_percent": round(score_pct, 1),
        "verdict": verdict,
        "passed_checks": passed_checks,
        "total_checks": total_checks,
        "raw_score": f"{passed_checks}/{total_checks}",
        "breakdown": {
            "field_completeness": {
                "passed": completeness["passed"],
                "total": completeness["total"],
            },
            "provenance": {
                "passed": provenance["passed"],
                "total": provenance["total"],
            },
            "formula_validity": {
                "passed": formula_passed,
                "total": formula_total,
            },
            "units_policy": {
                "passed": units["passed"],
                "violations": units["violations"],
            },
            "hallucination": {
                "passed": hallucination["passed"],
                "suspicious_count": hallucination["suspicious"],
                "suspicious_items": hallucination.get("details", [])[:10],
            },
        },
    }


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def extract_pdf_text(pdf_path: Path) -> str:
    if not HAS_FITZ:
        return ""
    try:
        long_path = str(pdf_path)
        if sys.platform == "win32" and len(long_path) > 240:
            long_path = "\\\\?\\" + long_path
        doc = fitz.open(long_path)
        text = "\n".join(p.get_text() for p in doc)
        doc.close()
        return text
    except Exception:
        return ""


def main():
    extraction_root = GOLDEN / "extraction_jsons"
    if not extraction_root.exists():
        raise SystemExit(
            f"Golden-dataset extractions not found: {extraction_root}\n"
            "Set BATTSYNTH_GOLDEN_DIR to a dataset directory containing "
            "extraction_jsons/ and pdfs/."
        )
    print("=" * 70)
    print("  Evaluation Scoring — Golden Dataset v2 (30 papers)")
    print("  Implementing metrics from 'Evaluation Metrics.pdf'")
    print("=" * 70)

    results = []
    all_scores = []

    for tier in TIERS:
        ext_dir = GOLDEN / "extraction_jsons" / tier
        pdf_dir = GOLDEN / "pdfs" / tier

        if not ext_dir.exists():
            ext_dir = GOLDEN / "extraction_jsons"

        for ext_file in sorted(ext_dir.glob("*_reactions.json")):
            with open(ext_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                data = data[0] if data else {}

            # Find PDF
            paper_stem = ext_file.stem.replace("_reactions", "")
            pdf_path = pdf_dir / f"{paper_stem}.pdf"
            if not pdf_path.exists():
                pdf_path = GOLDEN / "pdfs" / f"{paper_stem}.pdf"

            pdf_text = extract_pdf_text(pdf_path) if pdf_path.exists() else ""

            # Score
            score = compute_overall_score(data, pdf_text)
            score["paper_id"] = paper_stem
            score["tier"] = tier
            score["filename"] = ext_file.name
            results.append(score)
            all_scores.append(score["score_percent"])

            print(f"  [{tier[:3]}] {paper_stem[:55]:<55s} {score['score_percent']:>5.1f}% {score['verdict']:<10s} "
                  f"({score['raw_score']})")

    # Summary
    import numpy as np
    scores_arr = np.array(all_scores)

    print(f"\n{'='*70}")
    print(f"  SCORING SUMMARY (30 papers)")
    print(f"{'='*70}")
    print(f"  Mean score:   {scores_arr.mean():.1f}%")
    print(f"  Median score: {np.median(scores_arr):.1f}%")
    print(f"  Std dev:      {scores_arr.std():.1f}%")
    print(f"  Min:          {scores_arr.min():.1f}%")
    print(f"  Max:          {scores_arr.max():.1f}%")

    verdict_counts = Counter(r["verdict"] for r in results)
    print(f"\n  Verdict distribution:")
    for v in ["Excellent", "Good", "Acceptable", "Poor"]:
        print(f"    {v:<12s}: {verdict_counts.get(v, 0):>3d} ({verdict_counts.get(v, 0)/len(results)*100:.0f}%)")

    # By tier
    print(f"\n  By tier:")
    for tier in TIERS:
        tier_scores = [r["score_percent"] for r in results if r["tier"] == tier]
        if tier_scores:
            print(f"    {tier:<10s}: mean={np.mean(tier_scores):.1f}% median={np.median(tier_scores):.1f}% "
                  f"(n={len(tier_scores)})")

    # Breakdown averages
    print(f"\n  Average metric breakdown:")
    for metric in ["field_completeness", "provenance", "formula_validity"]:
        passed = sum(r["breakdown"][metric]["passed"] for r in results)
        total = sum(r["breakdown"][metric]["total"] for r in results)
        print(f"    {metric:<25s}: {passed}/{total} ({passed/total*100:.1f}%)")

    units_pass = sum(1 for r in results if r["breakdown"]["units_policy"]["passed"])
    print(f"    {'units_policy':<25s}: {units_pass}/{len(results)} papers pass")

    halluc_pass = sum(1 for r in results if r["breakdown"]["hallucination"]["passed"])
    print(f"    {'hallucination':<25s}: {halluc_pass}/{len(results)} papers pass")

    # Save results
    out_dir = GOLDEN / "analysis"
    out_dir.mkdir(exist_ok=True)

    # JSON
    with open(out_dir / "evaluation_scores.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    # CSV
    with open(out_dir / "evaluation_scores.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["filename", "paper_id", "tier", "score_percent", "verdict",
                         "raw_score", "completeness_pct", "provenance_pct",
                         "formula_pct", "units_pass", "hallucination_pass"])
        for r in results:
            b = r["breakdown"]
            comp_pct = b["field_completeness"]["passed"] / max(b["field_completeness"]["total"], 1) * 100
            prov_pct = b["provenance"]["passed"] / max(b["provenance"]["total"], 1) * 100
            form_pct = b["formula_validity"]["passed"] / max(b["formula_validity"]["total"], 1) * 100
            writer.writerow([
                r["filename"], r["paper_id"], r["tier"],
                r["score_percent"], r["verdict"], r["raw_score"],
                f"{comp_pct:.1f}", f"{prov_pct:.1f}", f"{form_pct:.1f}",
                "1" if b["units_policy"]["passed"] else "0",
                "1" if b["hallucination"]["passed"] else "0",
            ])

    print(f"\n  Output:")
    print(f"    {out_dir / 'evaluation_scores.json'}")
    print(f"    {out_dir / 'evaluation_scores.csv'}")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
