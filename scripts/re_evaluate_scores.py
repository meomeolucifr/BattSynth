"""
re_evaluate_scores.py
=====================
Re-evaluates the automatic scores from the Golden Dataset v2 (30 papers)
and the original Golden Dataset (60 papers: top 30 + bottom 30) using the
same methodology as automatic_score.py and compute_evaluation_scores.py.

Compares computed scores against manuscript claims.
"""

import json
import os
import re
import csv
import sys
from pathlib import Path
from collections import Counter

BASE = Path(r"C:\Users\12124\Downloads\Results_final\Results_final")

# ──────────────────────────────────────────────────────────────────────────────
# SCORING FUNCTIONS (from automatic_score.py, adapted for local use)
# ──────────────────────────────────────────────────────────────────────────────

UNITS_POLICY = {
    "temperature": "K", "pressure": "bar", "time": "min", "mass": "g",
    "volume": "mL", "amount": "mmol", "concentration": "M", "capacity": "mAh g-1",
}

PROV_LOCATORS = ["Page", "Figure", "Table", "S", "Methods", "Abstract",
                 "Body", "Results", "Discussion", "Introduction",
                 "Experimental", "Supporting", "Supplementary", "SI"]

try:
    from rdkit import Chem
    pt = Chem.GetPeriodicTable()
    symbols = [pt.GetElementSymbol(i) for i in range(1, 119)]
    HAS_RDKIT = True
except ImportError:
    symbols = ["H","He","Li","Be","B","C","N","O","F","Ne","Na","Mg","Al","Si","P",
               "S","Cl","Ar","K","Ca","Sc","Ti","V","Cr","Mn","Fe","Co","Ni","Cu",
               "Zn","Ga","Ge","As","Se","Br","Kr","Rb","Sr","Y","Zr","Nb","Mo","Tc",
               "Ru","Rh","Pd","Ag","Cd","In","Sn","Sb","Te","I","Xe","Cs","Ba","La",
               "Ce","Pr","Nd","Pm","Sm","Eu","Gd","Tb","Dy","Ho","Er","Tm","Yb","Lu",
               "Hf","Ta","W","Re","Os","Ir","Pt","Au","Hg","Tl","Pb","Bi","Po","At","Rn"]
    HAS_RDKIT = False

try:
    import fitz
    HAS_FITZ = True
except ImportError:
    HAS_FITZ = False


def parse_formula(formula):
    return re.findall(r'[A-Z][a-z]?', re.sub(r'[0-9.()]+', '', formula))

def is_valid_formula(formula):
    if not formula or formula == "":
        return True
    elems = parse_formula(formula)
    invalid = [e for e in elems if e not in symbols]
    return len(invalid) == 0

def check_provenance(entity):
    prov = entity.get("prov")
    if not prov or not isinstance(prov, list) or len(prov) == 0:
        return False
    for p in prov:
        if not isinstance(p, str):
            continue
        for loc in PROV_LOCATORS:
            if loc.lower() in p.lower():
                return True
    return False

def score_provenance_all(data):
    checks = []
    for t in data.get("targets", []):
        checks.append(check_provenance(t))
    for c in data.get("chemicals", []):
        checks.append(check_provenance(c))
    for step in data.get("synthesis", {}).get("steps", []):
        checks.append(check_provenance(step))
        for op in step.get("operations", []):
            checks.append(check_provenance(op))
    for ch in data.get("characterization", []):
        checks.append(check_provenance(ch))
    passed = sum(checks)
    total = len(checks)
    return passed, total

def check_units_policy(data):
    violations = []
    for step in data.get("synthesis", {}).get("steps", []):
        for op in step.get("operations", []):
            params = op.get("parameters", {})
            temp = params.get("temperature")
            if isinstance(temp, dict) and temp.get("value") is not None:
                if temp.get("unit", "") != "K":
                    violations.append(f"temperature: {temp.get('unit','')}")
            dur = params.get("duration")
            if isinstance(dur, dict) and dur.get("value") is not None:
                if dur.get("unit", "") != "min":
                    violations.append(f"duration: {dur.get('unit','')}")
            pres = params.get("pressure")
            if isinstance(pres, dict) and pres.get("value") is not None:
                if pres.get("unit", "") != "bar":
                    violations.append(f"pressure: {pres.get('unit','')}")
        # step-level temperature
        temp2 = step.get("temperature", {})
        if isinstance(temp2, dict) and temp2.get("value") is not None:
            if temp2.get("unit", "") != "K":
                violations.append(f"step.temperature: {temp2.get('unit','')}")
        conds = step.get("conditions", {})
        if isinstance(conds, dict):
            ct = conds.get("temperature", {})
            if isinstance(ct, dict) and ct.get("value") is not None:
                if ct.get("unit", "") != "K":
                    violations.append(f"condition.temperature: {ct.get('unit','')}")
    # Final outcomes
    fo = data.get("final_outcomes", {})
    cap = fo.get("capacity")
    if isinstance(cap, dict) and cap.get("value") is not None:
        if cap.get("unit", "") != "mAh g-1":
            violations.append(f"capacity: {cap.get('unit','')}")
    yld = fo.get("yield")
    if isinstance(yld, dict) and yld.get("value") is not None:
        if yld.get("unit", "") and yld.get("unit", "") != "%":
            violations.append(f"yield: {yld.get('unit','')}")
    return len(violations) == 0, violations

COMMON_ABBREVS = {
    "sem", "xrd", "tem", "xps", "eds", "edx", "eels", "afm", "stm",
    "nmr", "ir", "ftir", "uv", "raman", "dsc", "tga", "bet", "eis",
    "cv", "dft", "saxs", "waxs", "hrtem", "haadf", "saed", "ebsd",
    "icp", "gcd", "lsv", "xanes", "exafs", "pdf", "neutron",
}

def normalize_text(text):
    t = text.lower().strip()
    t = re.sub(r'\s+', ' ', t)
    t = t.replace('\u2212', '-').replace('\u2013', '-').replace('\u2014', '-')
    return t

def check_hallucination(data, pdf_text):
    if not pdf_text:
        return True, 0, []
    norm_pdf = normalize_text(pdf_text)
    suspicious = []
    for chem in data.get("chemicals", []):
        name = chem.get("name", "")
        if not name:
            continue
        name_norm = normalize_text(name)
        if len(name_norm) <= 3 or name_norm in COMMON_ABBREVS:
            continue
        if name_norm not in norm_pdf:
            compact = name_norm.replace(" ", "").replace("-", "")
            compact_pdf = norm_pdf.replace(" ", "").replace("-", "")
            if compact not in compact_pdf:
                suspicious.append(f"chemical: {name}")
    for tgt in data.get("targets", []):
        name = tgt.get("compound_name", "")
        if not name:
            continue
        name_norm = normalize_text(name)
        if len(name_norm) <= 3:
            continue
        if name_norm not in norm_pdf:
            words = [w for w in name_norm.split() if len(w) > 3]
            found = any(w in norm_pdf for w in words[:3])
            if not found:
                suspicious.append(f"target: {name}")
    for step in data.get("synthesis", {}).get("steps", []):
        desc = step.get("description", "")
        if not desc:
            continue
        desc_norm = normalize_text(desc)
        key_terms = [w for w in desc_norm.split() if len(w) > 4 and w not in
                     {"using", "under", "after", "about", "which", "where", "their", "these", "those"}]
        if key_terms:
            found = sum(1 for t in key_terms[:5] if t in norm_pdf)
            if found < len(key_terms[:5]) * 0.3:
                suspicious.append(f"step: {desc[:60]}")
    for ch in data.get("characterization", []):
        method = ch.get("method", "")
        if not method:
            continue
        method_norm = normalize_text(method)
        method_words = method_norm.split()
        if all(w in COMMON_ABBREVS or len(w) <= 3 for w in method_words):
            continue
        if method_norm not in norm_pdf:
            sig_words = [w for w in method_words if len(w) > 4]
            found = any(w in norm_pdf for w in sig_words)
            if not found:
                suspicious.append(f"characterization: {method}")
    passed = len(suspicious) <= 3
    return passed, len(suspicious), suspicious

def score_field_completeness(data):
    checks = []
    schema = data.get("schema", {})
    checks.append(bool(schema.get("name")))
    checks.append(bool(schema.get("version")))
    source = data.get("source", {})
    checks.append(bool(source.get("title")))
    checks.append(bool(source.get("doi")))
    checks.append(bool(source.get("authors")))
    checks.append(bool(source.get("journal")))
    checks.append(source.get("year") is not None)
    meta = data.get("metadata", {})
    checks.append(bool(meta.get("discipline")))
    checks.append(bool(meta.get("type")))
    targets = data.get("targets", [])
    checks.append(len(targets) > 0)
    for t in targets:
        checks.append(bool(t.get("compound_name")))
        checks.append(bool(t.get("molecular_formula")))
        checks.append(bool(t.get("intended_role")))
    chemicals = data.get("chemicals", [])
    checks.append(len(chemicals) > 0)
    for c in chemicals:
        checks.append(bool(c.get("name")))
        checks.append(bool(c.get("ontology")))
    steps = data.get("synthesis", {}).get("steps", [])
    checks.append(len(steps) > 0)
    for s in steps:
        checks.append(bool(s.get("description")))
        ops = s.get("operations", [])
        checks.append(len(ops) > 0)
        for op in ops:
            checks.append(bool(op.get("action")))
    chars = data.get("characterization", [])
    checks.append(len(chars) > 0)
    for ch in chars:
        checks.append(bool(ch.get("method")))
    fo = data.get("final_outcomes", {})
    checks.append(bool(fo))
    wf = data.get("workflow", {})
    checks.append(bool(wf.get("timeline")))
    passed = sum(checks)
    total = len(checks)
    return passed, total

def check_molecular_formula(formula):
    if not formula:
        return False
    if not re.search(r'[A-Z]', formula):
        return False
    if re.match(r'^[A-Za-z0-9.()\-/+@·:,\s]+$', formula):
        return True
    return False

def extract_pdf_text(pdf_path):
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


def compute_overall_score(data, pdf_text=""):
    # 1. Field completeness
    comp_passed, comp_total = score_field_completeness(data)
    # 2. Provenance
    prov_passed, prov_total = score_provenance_all(data)
    # 3. Formula validity
    formula_checks = []
    for t in data.get("targets", []):
        f = t.get("molecular_formula", "")
        formula_checks.append(check_molecular_formula(f))
    for c in data.get("chemicals", []):
        f = c.get("molecular_formula", "")
        if f:
            formula_checks.append(check_molecular_formula(f))
    formula_passed = sum(formula_checks)
    formula_total = len(formula_checks)
    # 4. Units policy
    units_ok, units_violations = check_units_policy(data)
    # 5. Hallucination
    hallu_ok, hallu_count, hallu_details = check_hallucination(data, pdf_text)

    total = comp_total + prov_total + formula_total + 1 + 1  # +1 units, +1 hallucination
    passed = comp_passed + prov_passed + formula_passed + (1 if units_ok else 0) + (1 if hallu_ok else 0)
    score_pct = (passed / total * 100) if total > 0 else 0

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
        "raw_score": f"{passed}/{total}",
        "passed": passed,
        "total": total,
        "breakdown": {
            "completeness": {"passed": comp_passed, "total": comp_total},
            "provenance": {"passed": prov_passed, "total": prov_total},
            "formula": {"passed": formula_passed, "total": formula_total},
            "units": {"passed": units_ok, "violations": units_violations},
            "hallucination": {"passed": hallu_ok, "count": hallu_count, "items": hallu_details[:5]},
        }
    }


# ──────────────────────────────────────────────────────────────────────────────
# EVALUATION RUNNER
# ──────────────────────────────────────────────────────────────────────────────

def evaluate_dataset():
    """Evaluate the 30-paper Golden Dataset v2 (stratified by tier)."""
    gd2 = BASE / "dataset"
    tiers = ["simple", "moderate", "complex"]
    results = []

    for tier in tiers:
        ext_dir = gd2 / "extraction_jsons" / tier
        pdf_dir = gd2 / "pdfs"
        # Also check tier-specific pdf subdirs
        pdf_tier_dir = gd2 / "pdfs" / tier

        if not ext_dir.exists():
            print(f"  [WARN] Missing tier dir: {ext_dir}")
            continue

        for ext_file in sorted(ext_dir.glob("*_reactions.json")):
            if "backup" in str(ext_file).lower() or "Verified" in ext_file.name:
                continue
            with open(ext_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                data = data[0] if data else {}

            paper_stem = ext_file.stem.replace("_reactions", "")
            # Try multiple locations for the PDF
            pdf_path = None
            for candidate in [
                pdf_dir / f"{paper_stem}.pdf",
                pdf_tier_dir / f"{paper_stem}.pdf",
            ]:
                if candidate.exists():
                    pdf_path = candidate
                    break

            pdf_text = extract_pdf_text(pdf_path) if pdf_path else ""
            score = compute_overall_score(data, pdf_text)
            score["paper_id"] = paper_stem
            score["tier"] = tier
            results.append(score)

    return results


def evaluate_golden_dataset_original():
    """Evaluate the 60-paper original Golden Dataset (high_results + low_results)."""
    gd = BASE / "Golden Dataset"
    results = []

    for group in ["high_results", "low_results"]:
        group_dir = gd / group
        if not group_dir.exists():
            continue

        for ext_file in sorted(group_dir.glob("*_reactions.json")):
            if "Verified" in ext_file.name or "backup" in ext_file.name.lower():
                continue
            with open(ext_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                data = data[0] if data else {}

            paper_stem = ext_file.stem.replace("_reactions", "")
            pdf_path = group_dir / f"{paper_stem}.pdf"
            pdf_text = extract_pdf_text(pdf_path) if pdf_path.exists() else ""

            score = compute_overall_score(data, pdf_text)
            score["paper_id"] = paper_stem
            score["group"] = group
            results.append(score)

    return results


def print_summary(results, label):
    scores = [r["score_percent"] for r in results]
    if not scores:
        print(f"\n  No results for {label}")
        return

    avg = sum(scores) / len(scores)
    median = sorted(scores)[len(scores) // 2]
    verdict_counts = Counter(r["verdict"] for r in results)

    print(f"\n{'='*70}")
    print(f"  {label} ({len(results)} papers)")
    print(f"{'='*70}")
    print(f"  Mean score:   {avg:.1f}%")
    print(f"  Median score: {median:.1f}%")
    print(f"  Min:          {min(scores):.1f}%")
    print(f"  Max:          {max(scores):.1f}%")
    print(f"\n  Verdict distribution:")
    for v in ["Excellent", "Good", "Acceptable", "Poor"]:
        n = verdict_counts.get(v, 0)
        pct = n / len(results) * 100
        print(f"    {v:<12s}: {n:>3d} ({pct:.1f}%)")

    # By-tier or by-group breakdown
    groups = set(r.get("tier", r.get("group", "unknown")) for r in results)
    if len(groups) > 1:
        print(f"\n  Breakdown by group/tier:")
        for g in sorted(groups):
            g_scores = [r["score_percent"] for r in results if r.get("tier", r.get("group")) == g]
            if g_scores:
                print(f"    {g:<15s}: mean={sum(g_scores)/len(g_scores):.1f}%  n={len(g_scores)}")

    # Metric breakdown averages
    print(f"\n  Average metric breakdown:")
    for metric in ["completeness", "provenance", "formula"]:
        p = sum(r["breakdown"][metric]["passed"] for r in results)
        t = sum(r["breakdown"][metric]["total"] for r in results)
        if t > 0:
            print(f"    {metric:<20s}: {p}/{t} ({p/t*100:.1f}%)")
    up = sum(1 for r in results if r["breakdown"]["units"]["passed"])
    print(f"    {'units_policy':<20s}: {up}/{len(results)} papers pass ({up/len(results)*100:.1f}%)")
    hp = sum(1 for r in results if r["breakdown"]["hallucination"]["passed"])
    print(f"    {'hallucination':<20s}: {hp}/{len(results)} papers pass ({hp/len(results)*100:.1f}%)")


def compare_with_manuscript(gd2_results, orig_results):
    """Compare computed scores with manuscript claims."""
    print(f"\n{'='*70}")
    print(f"  COMPARISON WITH MANUSCRIPT CLAIMS")
    print(f"{'='*70}")

    # Manuscript claims (from Section 2.4 and Table 5):
    # - Full 605 papers: mean 93.4%, 72.2% Excellent, 27.4% Good, 0.3% Acceptable, 0% Poor
    # - Golden Dataset (30 papers): mean before corrections = 89.0%, after = 90.6%

    if gd2_results:
        gd2_scores = [r["score_percent"] for r in gd2_results]
        gd2_avg = sum(gd2_scores) / len(gd2_scores)
        gd2_verdict = Counter(r["verdict"] for r in gd2_results)
        gd2_excellent_pct = gd2_verdict.get("Excellent", 0) / len(gd2_results) * 100

        print(f"\n  Golden Dataset v2 (30 papers, complexity-stratified):")
        print(f"    Computed mean:     {gd2_avg:.1f}%")
        print(f"    Manuscript claims: 89.0% (before corrections), 90.6% (after corrections)")
        print(f"    Excellent rate:    {gd2_excellent_pct:.1f}%")

    if orig_results:
        orig_scores = [r["score_percent"] for r in orig_results]
        orig_avg = sum(orig_scores) / len(orig_scores)
        orig_verdict = Counter(r["verdict"] for r in orig_results)

        high_results = [r for r in orig_results if r.get("group") == "high_results"]
        low_results = [r for r in orig_results if r.get("group") == "low_results"]

        print(f"\n  Original Golden Dataset (top 30 + bottom 30 by score):")
        print(f"    Overall mean:      {orig_avg:.1f}%")
        if high_results:
            h_avg = sum(r["score_percent"] for r in high_results) / len(high_results)
            print(f"    High group mean:   {h_avg:.1f}%  (n={len(high_results)})")
        if low_results:
            l_avg = sum(r["score_percent"] for r in low_results) / len(low_results)
            print(f"    Low group mean:    {l_avg:.1f}%  (n={len(low_results)})")

        orig_excellent_pct = orig_verdict.get("Excellent", 0) / len(orig_results) * 100
        print(f"\n    Manuscript claims for full 605 papers:")
        print(f"      Mean: 93.4% — Our {len(orig_results)}-paper subset: {orig_avg:.1f}%")
        print(f"      Excellent: 72.2% — Our subset: {orig_excellent_pct:.1f}%")
        for v in ["Excellent", "Good", "Acceptable", "Poor"]:
            n = orig_verdict.get(v, 0)
            print(f"      {v}: {n} ({n/len(orig_results)*100:.1f}%)")

    # Per-paper details for golden v2
    if gd2_results:
        print(f"\n{'='*70}")
        print(f"  PER-PAPER SCORES (Golden Dataset v2, 30 papers)")
        print(f"{'='*70}")
        print(f"  {'Paper':<55s} {'Tier':<10s} {'Score':>6s} {'Verdict':<10s}")
        print(f"  {'-'*55} {'-'*10} {'-'*6} {'-'*10}")
        for r in sorted(gd2_results, key=lambda x: x["score_percent"], reverse=True):
            name = r["paper_id"][:55]
            print(f"  {name:<55s} {r['tier']:<10s} {r['score_percent']:>5.1f}% {r['verdict']:<10s}")


def main():
    print("Re-evaluating scores using automatic_score.py methodology...")
    print(f"PyMuPDF available: {HAS_FITZ}")
    print(f"RDKit available: {HAS_RDKIT}")

    gd2_results = evaluate_dataset()
    print_summary(gd2_results, "Golden Dataset v2 (30 papers, complexity-stratified)")

    orig_results = evaluate_golden_dataset_original()
    print_summary(orig_results, "Original Golden Dataset (high + low)")

    compare_with_manuscript(gd2_results, orig_results)

    # Save results
    out_dir = BASE / "scripts" / "analysis_output"
    out_dir.mkdir(exist_ok=True)

    with open(out_dir / "re_evaluation_gd2.json", "w", encoding="utf-8") as f:
        json.dump(gd2_results, f, indent=2, ensure_ascii=False)
    with open(out_dir / "re_evaluation_original.json", "w", encoding="utf-8") as f:
        json.dump(orig_results, f, indent=2, ensure_ascii=False)

    # CSV
    with open(out_dir / "re_evaluation_gd2.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["paper_id", "tier", "score_percent", "verdict", "raw_score",
                         "completeness_pct", "provenance_pct", "formula_pct",
                         "units_pass", "hallucination_pass"])
        for r in gd2_results:
            b = r["breakdown"]
            comp_pct = b["completeness"]["passed"] / max(b["completeness"]["total"], 1) * 100
            prov_pct = b["provenance"]["passed"] / max(b["provenance"]["total"], 1) * 100
            form_pct = b["formula"]["passed"] / max(b["formula"]["total"], 1) * 100
            writer.writerow([
                r["paper_id"], r["tier"], r["score_percent"], r["verdict"], r["raw_score"],
                f"{comp_pct:.1f}", f"{prov_pct:.1f}", f"{form_pct:.1f}",
                "1" if b["units"]["passed"] else "0",
                "1" if b["hallucination"]["passed"] else "0",
            ])

    print(f"\n  Results saved to {out_dir}")


if __name__ == "__main__":
    main()
