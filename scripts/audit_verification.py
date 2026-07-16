"""
Verification Audit Script
Parses all Verified_*.json files from the Golden Dataset and analyzes _llm_flag annotations.
Detects contradictions, computes error rates, and generates a CSV report + figures.
"""

import json
import os
import re
import csv
from pathlib import Path
from collections import Counter, defaultdict

REPO_ROOT = Path(__file__).resolve().parents[1]
GOLDEN_HIGH = REPO_ROOT / "src" / "data" / "golden_dataset" / "high_results"
GOLDEN_LOW = REPO_ROOT / "src" / "data" / "golden_dataset" / "low_results"
OUTPUT_DIR = REPO_ROOT / "src" / "analysis"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Phrases in reasoning that indicate support despite is_supported=False
SUPPORT_PHRASES = [
    r"explicitly present in the paper",
    r"explicitly stated",
    r"explicitly mentioned",
    r"explicitly discusses",
    r"explicitly mentions",
    r"explicitly listed",
    r"is supported",
    r"it should be supported",
    r"the value is supported",
    r"identity is supported",
    r"identity is correct",
    r"chemical identity is correct",
    r"formula is supported",
    r"value itself is supported",
    r"appears in the text",
    r"found in text",
    r"matches? the extracted",
    r"match the extracted",
    r"these match",
    r"correctly identified",
    r"supported by the text",
    r"supported by the document",
    r"is explicitly present",
    r"marking unsupported would be wrong",
]

SUPPORT_PATTERN = re.compile("|".join(SUPPORT_PHRASES), re.IGNORECASE)

# Phrases that indicate actual non-support
NONSUPPORT_PHRASES = [
    r"does not appear",
    r"does not mention",
    r"not found in",
    r"not stated in",
    r"never mentioned",
    r"nowhere in the provided",
    r"is incorrect",
    r"has an incorrect",
    r"wrong stoichiometry",
    r"wrong lithium stoichiometry",
    r"hallucinated",
    r"fabricated",
    r"over-substituted",
]

NONSUPPORT_PATTERN = re.compile("|".join(NONSUPPORT_PHRASES), re.IGNORECASE)


def extract_llm_flags(obj, path="", results=None):
    """Recursively extract all _llm_flag annotations from a JSON object."""
    if results is None:
        results = []

    if isinstance(obj, dict):
        if "_llm_flag" in obj:
            flag = obj["_llm_flag"]
            # Build context: grab nearby identifiable fields
            context = {}
            for key in ["target_id", "compound_name", "molecular_formula",
                        "chemical_id", "name", "step_id", "description",
                        "method", "action", "metric", "issue"]:
                if key in obj:
                    context[key] = obj[key]

            results.append({
                "path": path,
                "is_supported": flag.get("is_supported"),
                "confidence": flag.get("confidence"),
                "reasoning": flag.get("reasoning", ""),
                "suggested_fix": flag.get("suggested_fix", ""),
                "context": context,
            })

        for key, val in obj.items():
            if key != "_llm_flag":
                extract_llm_flags(val, f"{path}.{key}" if path else key, results)

    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            extract_llm_flags(item, f"{path}[{i}]", results)

    return results


def detect_contradiction(flag_entry):
    """Detect if reasoning contradicts the is_supported verdict."""
    reasoning = flag_entry["reasoning"]
    is_supported = flag_entry["is_supported"]

    if is_supported is True:
        # Check if reasoning says NOT supported but verdict is True (rare)
        has_nonsupport = bool(NONSUPPORT_PATTERN.search(reasoning))
        if has_nonsupport:
            return "false_positive_suspect"
        return None

    if is_supported is False:
        # Check if reasoning says it IS supported but verdict is False
        has_support = bool(SUPPORT_PATTERN.search(reasoning))
        has_nonsupport = bool(NONSUPPORT_PATTERN.search(reasoning))

        if has_support and not has_nonsupport:
            return "contradiction_clear"  # Reasoning says supported, verdict says not
        elif has_support and has_nonsupport:
            return "contradiction_mixed"  # Reasoning has both signals
        return None

    return None


def classify_flag_section(path):
    """Classify which section of the schema a flag belongs to."""
    path_lower = path.lower()
    if "target" in path_lower:
        return "targets"
    elif "chemical" in path_lower:
        return "chemicals"
    elif "synthesis" in path_lower or "operation" in path_lower:
        return "synthesis"
    elif "characterization" in path_lower:
        return "characterization"
    elif "workflow" in path_lower:
        return "workflow"
    elif "analysis" in path_lower:
        return "analysis"
    elif "final_outcome" in path_lower:
        return "final_outcomes"
    else:
        return "other"


def process_file(filepath, group):
    """Process a single Verified_*.json file and return all flag entries."""
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    filename = os.path.basename(filepath)
    paper_name = filename.replace("Verified_", "").replace("_reactions.json", "")

    flags = extract_llm_flags(data)

    entries = []
    for flag in flags:
        contradiction = detect_contradiction(flag)
        section = classify_flag_section(flag["path"])

        # Get a human-readable identifier for the flagged item
        ctx = flag["context"]
        item_id = (ctx.get("target_id") or ctx.get("chemical_id") or
                   ctx.get("step_id") or ctx.get("method") or
                   ctx.get("action") or ctx.get("metric") or
                   ctx.get("issue") or "unknown")
        item_name = (ctx.get("compound_name") or ctx.get("name") or
                     ctx.get("description") or ctx.get("method") or "")

        entries.append({
            "file": filename,
            "paper": paper_name,
            "group": group,
            "section": section,
            "path": flag["path"],
            "item_id": item_id,
            "item_name": item_name,
            "is_supported": flag["is_supported"],
            "confidence": flag["confidence"],
            "contradiction": contradiction,
            "reasoning_excerpt": flag["reasoning"][:200],
            "suggested_fix": flag["suggested_fix"][:200] if flag["suggested_fix"] else "",
        })

    return entries


def main():
    all_entries = []

    # Process high results
    for filepath in sorted(GOLDEN_HIGH.glob("Verified_*.json")):
        try:
            entries = process_file(filepath, "high")
            all_entries.extend(entries)
        except Exception as e:
            print(f"ERROR processing {filepath.name}: {e}")

    # Process low results
    for filepath in sorted(GOLDEN_LOW.glob("Verified_*.json")):
        try:
            entries = process_file(filepath, "low")
            all_entries.extend(entries)
        except Exception as e:
            print(f"ERROR processing {filepath.name}: {e}")

    # === Write detailed CSV ===
    csv_path = OUTPUT_DIR / "verification_audit_detailed.csv"
    fieldnames = ["file", "paper", "group", "section", "path", "item_id",
                  "item_name", "is_supported", "confidence", "contradiction",
                  "reasoning_excerpt", "suggested_fix"]

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_entries)

    # === Compute summary statistics ===
    total_flags = len(all_entries)
    supported = sum(1 for e in all_entries if e["is_supported"] is True)
    unsupported = sum(1 for e in all_entries if e["is_supported"] is False)
    contradictions_clear = sum(1 for e in all_entries if e["contradiction"] == "contradiction_clear")
    contradictions_mixed = sum(1 for e in all_entries if e["contradiction"] == "contradiction_mixed")
    false_positive_suspects = sum(1 for e in all_entries if e["contradiction"] == "false_positive_suspect")

    # Per-group breakdown
    stats = {}
    for group in ["high", "low"]:
        group_entries = [e for e in all_entries if e["group"] == group]
        g_total = len(group_entries)
        g_supported = sum(1 for e in group_entries if e["is_supported"] is True)
        g_unsupported = sum(1 for e in group_entries if e["is_supported"] is False)
        g_contra_clear = sum(1 for e in group_entries if e["contradiction"] == "contradiction_clear")
        g_contra_mixed = sum(1 for e in group_entries if e["contradiction"] == "contradiction_mixed")

        stats[group] = {
            "total_flags": g_total,
            "supported": g_supported,
            "unsupported": g_unsupported,
            "support_rate": g_supported / g_total * 100 if g_total else 0,
            "contradictions_clear": g_contra_clear,
            "contradictions_mixed": g_contra_mixed,
            "contradiction_rate": (g_contra_clear + g_contra_mixed) / g_total * 100 if g_total else 0,
        }

    # Per-section breakdown
    section_stats = defaultdict(lambda: {"total": 0, "supported": 0, "unsupported": 0,
                                          "contradictions": 0})
    for e in all_entries:
        sec = e["section"]
        section_stats[sec]["total"] += 1
        if e["is_supported"] is True:
            section_stats[sec]["supported"] += 1
        elif e["is_supported"] is False:
            section_stats[sec]["unsupported"] += 1
        if e["contradiction"] in ("contradiction_clear", "contradiction_mixed"):
            section_stats[sec]["contradictions"] += 1

    # Confidence calibration: bin by confidence, compute actual support rate
    confidence_bins = defaultdict(lambda: {"count": 0, "supported": 0})
    for e in all_entries:
        if e["confidence"] is not None:
            bin_val = round(e["confidence"], 1)
            confidence_bins[bin_val]["count"] += 1
            if e["is_supported"] is True:
                confidence_bins[bin_val]["supported"] += 1

    # Per-file summary
    file_stats = defaultdict(lambda: {"total": 0, "supported": 0, "unsupported": 0,
                                       "contradictions": 0, "group": ""})
    for e in all_entries:
        fs = file_stats[e["paper"]]
        fs["total"] += 1
        fs["group"] = e["group"]
        if e["is_supported"] is True:
            fs["supported"] += 1
        elif e["is_supported"] is False:
            fs["unsupported"] += 1
        if e["contradiction"] in ("contradiction_clear", "contradiction_mixed"):
            fs["contradictions"] += 1

    # === Write summary report ===
    summary_path = OUTPUT_DIR / "verification_audit_summary.txt"
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write("=" * 70 + "\n")
        f.write("VERIFICATION AUDIT SUMMARY REPORT\n")
        f.write("=" * 70 + "\n\n")

        f.write(f"Total files analyzed: {len(set(e['file'] for e in all_entries))}\n")
        f.write(f"Total _llm_flag annotations: {total_flags}\n")
        f.write(f"  Supported (is_supported=True): {supported} ({supported/total_flags*100:.1f}%)\n")
        f.write(f"  Unsupported (is_supported=False): {unsupported} ({unsupported/total_flags*100:.1f}%)\n\n")

        f.write("CONTRADICTION DETECTION:\n")
        f.write(f"  Clear contradictions (reasoning says supported, verdict says false): {contradictions_clear}\n")
        f.write(f"  Mixed contradictions (reasoning has both support + non-support): {contradictions_mixed}\n")
        f.write(f"  False positive suspects (reasoning says unsupported, verdict says true): {false_positive_suspects}\n")
        f.write(f"  Total contradictions: {contradictions_clear + contradictions_mixed}\n")
        f.write(f"  Contradiction rate: {(contradictions_clear + contradictions_mixed)/total_flags*100:.1f}%\n\n")

        f.write("PER-GROUP BREAKDOWN:\n")
        for group in ["high", "low"]:
            s = stats[group]
            f.write(f"\n  {group.upper()} group ({s['total_flags']} flags):\n")
            f.write(f"    Supported: {s['supported']} ({s['support_rate']:.1f}%)\n")
            f.write(f"    Unsupported: {s['unsupported']} ({100-s['support_rate']:.1f}%)\n")
            f.write(f"    Contradictions: {s['contradictions_clear']} clear + {s['contradictions_mixed']} mixed = {s['contradictions_clear']+s['contradictions_mixed']}\n")
            f.write(f"    Contradiction rate: {s['contradiction_rate']:.1f}%\n")

        f.write("\nPER-SECTION BREAKDOWN:\n")
        for sec in sorted(section_stats.keys()):
            ss = section_stats[sec]
            rate = ss["supported"] / ss["total"] * 100 if ss["total"] else 0
            contra_rate = ss["contradictions"] / ss["total"] * 100 if ss["total"] else 0
            f.write(f"  {sec:20s}: {ss['total']:4d} flags, "
                    f"{ss['supported']:4d} supported ({rate:5.1f}%), "
                    f"{ss['contradictions']:3d} contradictions ({contra_rate:5.1f}%)\n")

        f.write("\nCONFIDENCE CALIBRATION (confidence bin -> actual support rate):\n")
        for bin_val in sorted(confidence_bins.keys()):
            cb = confidence_bins[bin_val]
            actual_rate = cb["supported"] / cb["count"] * 100 if cb["count"] else 0
            f.write(f"  Confidence {bin_val:.1f}: {cb['count']:4d} flags, "
                    f"{cb['supported']:4d} supported ({actual_rate:5.1f}% actual support rate)\n")

        f.write("\nPER-FILE CONTRADICTION SUMMARY (sorted by contradiction count):\n")
        for paper, fs in sorted(file_stats.items(), key=lambda x: -x[1]["contradictions"]):
            if fs["contradictions"] > 0:
                f.write(f"  [{fs['group'].upper()}] {paper[:60]:60s}: "
                        f"{fs['contradictions']}/{fs['total']} contradictions "
                        f"({fs['contradictions']/fs['total']*100:.0f}%)\n")

    # === Write contradictions-only CSV for human review ===
    contra_path = OUTPUT_DIR / "contradictions_for_review.csv"
    contra_entries = [e for e in all_entries
                      if e["contradiction"] in ("contradiction_clear", "contradiction_mixed")]

    with open(contra_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(contra_entries)

    # === Write confidence calibration CSV ===
    calib_path = OUTPUT_DIR / "confidence_calibration.csv"
    with open(calib_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["confidence_bin", "total_count",
                                                "supported_count", "actual_support_rate"])
        writer.writeheader()
        for bin_val in sorted(confidence_bins.keys()):
            cb = confidence_bins[bin_val]
            actual_rate = cb["supported"] / cb["count"] * 100 if cb["count"] else 0
            writer.writerow({
                "confidence_bin": f"{bin_val:.1f}",
                "total_count": cb["count"],
                "supported_count": cb["supported"],
                "actual_support_rate": f"{actual_rate:.1f}",
            })

    # === Write per-file summary CSV ===
    file_summary_path = OUTPUT_DIR / "per_file_summary.csv"
    with open(file_summary_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["paper", "group", "total_flags",
                                                "supported", "unsupported",
                                                "support_rate", "contradictions",
                                                "contradiction_rate"])
        writer.writeheader()
        for paper, fs in sorted(file_stats.items(), key=lambda x: x[0]):
            rate = fs["supported"] / fs["total"] * 100 if fs["total"] else 0
            contra_rate = fs["contradictions"] / fs["total"] * 100 if fs["total"] else 0
            writer.writerow({
                "paper": paper,
                "group": fs["group"],
                "total_flags": fs["total"],
                "supported": fs["supported"],
                "unsupported": fs["unsupported"],
                "support_rate": f"{rate:.1f}",
                "contradictions": fs["contradictions"],
                "contradiction_rate": f"{contra_rate:.1f}",
            })

    # Print summary
    print(f"\nAudit complete!")
    print(f"  Files processed: {len(set(e['file'] for e in all_entries))}")
    print(f"  Total flags: {total_flags}")
    print(f"  Supported: {supported} ({supported/total_flags*100:.1f}%)")
    print(f"  Unsupported: {unsupported} ({unsupported/total_flags*100:.1f}%)")
    print(f"  Contradictions: {contradictions_clear} clear + {contradictions_mixed} mixed")
    print(f"  Contradiction rate: {(contradictions_clear + contradictions_mixed)/total_flags*100:.1f}%")
    print(f"\nOutputs written to: {OUTPUT_DIR}")
    print(f"  - verification_audit_detailed.csv (all {total_flags} flags)")
    print(f"  - verification_audit_summary.txt (summary report)")
    print(f"  - contradictions_for_review.csv ({len(contra_entries)} contradictions)")
    print(f"  - confidence_calibration.csv")
    print(f"  - per_file_summary.csv")


if __name__ == "__main__":
    main()
