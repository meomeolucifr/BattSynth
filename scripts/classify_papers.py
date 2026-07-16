"""
Paper Type Classification & Characterization Normalization
Phase 0 of the revised publication roadmap.

1. Consolidates ~80 LLM-generated paper_type labels into 8 canonical categories
2. Adds has_experimental_section flag based on synthesis step count
3. Normalizes characterization method names to canonical forms
4. Updates master index and recomputes statistics for experimental-only subset
"""

import json
import csv
import re
from pathlib import Path
from collections import Counter, defaultdict

BASE_DIR = Path(r"C:\Users\12124\Downloads\Results_final\Results_final")
DATASET_DIR = BASE_DIR / "Output_JSON" / "All_dataset" / "output_dataset"
OUTPUT_DIR = BASE_DIR / "scripts" / "audit_output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================
# PART 1: Paper Type Classification
# ============================================================

# Mapping from raw LLM-generated types to canonical categories
TYPE_MAPPING = {
    # Experimental synthesis
    "materials_synthesis": "experimental_synthesis",
    "materials synthesis": "experimental_synthesis",
    "materials_synthesis_and_electrochemistry": "experimental_synthesis",
    "materials synthesis and electrochemistry": "experimental_synthesis",
    "materials synthesis and characterization": "experimental_synthesis",
    "materials_synthesis_and_evaluation": "experimental_synthesis",
    "materials synthesis and electrochemical study": "experimental_synthesis",
    "materials synthesis and electrochemistry study": "experimental_synthesis",
    "materials synthesis & electrochemistry": "experimental_synthesis",
    "materials synthesis and diffusion study": "experimental_synthesis",
    "materials synthesis and battery assembly": "experimental_synthesis",
    "materials_synthesis_and_battery_assembly": "experimental_synthesis",
    "materials_synthesis_and_battery_performance": "experimental_synthesis",
    "materials synthesis and device fabrication": "experimental_synthesis",
    "materials_synthesis_and_mechanical_testing": "experimental_synthesis",
    "materials_synthesis_study": "experimental_synthesis",
    "materials synthesis study": "experimental_synthesis",
    "inorganic_synthesis": "experimental_synthesis",
    "inorganic_solid_state_synthesis": "experimental_synthesis",
    "inorganic solid-state synthesis and characterization": "experimental_synthesis",
    "inorganic synthesis and characterization": "experimental_synthesis",
    "inorganic_synthesis_and_characterization": "experimental_synthesis",
    "solid_state_synthesis": "experimental_synthesis",
    "solid electrolyte study": "experimental_synthesis",
    "synthetic study": "experimental_synthesis",
    "polymer_synthesis_and_battery_application": "experimental_synthesis",
    "battery electrode fabrication": "experimental_synthesis",
    "electrochemical cell assembly and testing": "experimental_synthesis",
    "experimental study": "experimental_synthesis",

    # Research articles (need further classification by content)
    "research article": "research_article",
    "research-article": "research_article",
    "research_article": "research_article",
    "journal article": "research_article",
    "journal_article": "research_article",
    "battery research paper": "research_article",
    "battery research": "research_article",

    # Characterization / electrochemistry (no synthesis, just testing)
    "materials_characterization": "characterization_study",
    "materials characterization study": "characterization_study",
    "electrochemistry study": "characterization_study",
    "electrochemistry": "characterization_study",
    "battery aging study": "characterization_study",
    "battery characterization/performance study": "characterization_study",

    # Computational
    "computational study": "computational",
    "computational_study": "computational",
    "computational screening": "computational",
    "computational materials study": "computational",
    "computational materials screening": "computational",
    "computational chemistry / force-field development": "computational",
    "computational methodology": "computational",
    "computational modelling study": "computational",
    "computational_theoretical_study": "computational",
    "theoretical study": "computational",
    "theoretical modeling": "computational",
    "theoretical_modeling": "computational",
    "simulation study": "computational",

    # Review
    "review": "review",
    "review article": "review",
    "review_article": "review",
    "review_article_extraction": "review",
    "mini-review": "review",
    "mini review": "review",
    "minireview": "review",

    # Perspective / commentary
    "perspective": "perspective",
    "perspective_review": "perspective",
    "perspective_article": "perspective",
    "viewpoint": "perspective",
    "frontier article / perspective": "perspective",
    "commentary": "perspective",
    "news & views commentary": "perspective",
    "research briefing": "perspective",

    # Editorial
    "editorial": "editorial",
    "white paper": "editorial",
    "short communication": "editorial",
    "brief communication": "editorial",
    "communication": "editorial",

    # Supporting info
    "supporting_information": "supporting_info",
    "supplementary_information": "supporting_info",
    "supplementary information": "supporting_info",

    # Data
    "data descriptor": "data_descriptor",
    "technical_report": "data_descriptor",
    "PhD dissertation": "other",
    "PhD Dissertation": "other",

    # Recycling
    "battery_recycling_study": "experimental_synthesis",
    "battery recycling study": "experimental_synthesis",
    "materials_recycling": "experimental_synthesis",

    # Other
    "materials science": "other",
    "data-driven assessment": "computational",
}

CANONICAL_CATEGORIES = [
    "experimental_synthesis",
    "research_article",       # Ambiguous — needs content-based classification
    "characterization_study",
    "computational",
    "review",
    "perspective",
    "editorial",
    "supporting_info",
    "data_descriptor",
    "other",
]


def classify_paper_type(raw_type, num_synthesis_steps, num_targets, num_characterization, tags):
    """Classify paper into canonical category."""
    raw_lower = raw_type.strip().lower()

    # Direct mapping
    canonical = TYPE_MAPPING.get(raw_type) or TYPE_MAPPING.get(raw_lower)

    if canonical and canonical != "research_article":
        return canonical

    # For "research_article" or unmapped types: use content-based classification
    has_synthesis = num_synthesis_steps > 0
    has_targets = num_targets > 0
    has_characterization = num_characterization > 0
    tags_lower = " ".join(tags).lower() if tags else ""

    # Check tags for computational indicators
    comp_keywords = ["dft", "molecular dynamics", "simulation", "first-principles",
                     "machine learning", "computational", "ab initio", "density functional",
                     "monte carlo", "deep learning"]
    is_computational = any(kw in tags_lower for kw in comp_keywords)

    review_keywords = ["review", "overview", "perspective", "advances", "progress",
                       "state of the art", "state-of-the-art"]
    is_review = any(kw in tags_lower for kw in review_keywords)

    if is_computational and not has_synthesis:
        return "computational"
    elif is_review and not has_synthesis:
        return "review"
    elif has_synthesis:
        return "experimental_synthesis"
    elif has_characterization and has_targets:
        return "characterization_study"
    elif has_targets and not has_synthesis:
        return "characterization_study"
    elif not has_synthesis and not has_targets and not has_characterization:
        # Empty extraction — likely review, computational, or editorial
        if is_computational:
            return "computational"
        elif is_review:
            return "review"
        else:
            return "other"
    else:
        return "research_article"


# ============================================================
# PART 2: Characterization Method Normalization
# ============================================================

# Canonical mapping: normalized_name → list of variants
CHAR_METHOD_MAPPING = {
    "XRD": [
        "XRD", "X-ray diffraction", "X-ray Diffraction", "Powder XRD", "PXRD",
        "powder X-ray diffraction", "Powder X-ray diffraction", "X-ray powder diffraction",
        "XRPD", "X-ray diffraction (XRD)", "X-ray Diffraction (XRD)",
        "Synchrotron XRD", "synchrotron XRD", "In situ XRD", "in situ XRD",
        "ex situ XRD", "High-resolution XRD", "HR-XRD",
        "Variable-temperature XRD", "VT-XRD",
    ],
    "SEM": [
        "SEM", "Scanning electron microscopy", "scanning electron microscopy",
        "Scanning Electron Microscopy", "FE-SEM", "FESEM",
        "field-emission SEM", "Field-emission scanning electron microscopy",
        "SEM-EDS", "SEM/EDS", "SEM-EDX", "SEM/EDX",
    ],
    "TEM": [
        "TEM", "Transmission electron microscopy", "transmission electron microscopy",
        "Transmission Electron Microscopy", "HR-TEM", "HRTEM",
        "High-resolution TEM", "STEM", "STEM-HAADF", "STEM-EDS",
        "Scanning transmission electron microscopy",
        "cryo-TEM", "Cryo-TEM",
    ],
    "XPS": [
        "XPS", "X-ray photoelectron spectroscopy", "X-ray Photoelectron Spectroscopy",
    ],
    "EIS": [
        "EIS", "Electrochemical Impedance Spectroscopy",
        "Electrochemical impedance spectroscopy",
        "electrochemical impedance spectroscopy",
        "Impedance spectroscopy", "impedance spectroscopy",
        "AC impedance spectroscopy", "AC impedance",
        "Complex impedance spectroscopy",
        "Electrochemical Impedance Spectroscopy (EIS)",
        "AC Impedance Spectroscopy",
    ],
    "Cyclic voltammetry": [
        "CV", "Cyclic Voltammetry", "Cyclic voltammetry", "cyclic voltammetry",
        "Cyclic Voltammetry (CV)", "cyclic voltammogram",
        "Linear sweep voltammetry", "LSV",
    ],
    "Galvanostatic cycling": [
        "Galvanostatic cycling", "galvanostatic cycling",
        "Galvanostatic charge/discharge", "galvanostatic charge/discharge",
        "Galvanostatic charge-discharge", "GCD",
        "Charge-discharge cycling", "charge/discharge",
        "Electrochemical cycling", "electrochemical cycling",
        "Battery testing", "battery testing",
        "Rate capability", "rate capability",
        "Long-term cycling", "Cycle performance",
    ],
    "Raman spectroscopy": [
        "Raman spectroscopy", "Raman Spectroscopy", "raman spectroscopy",
        "Raman", "Micro-Raman", "In situ Raman",
    ],
    "TGA": [
        "TGA", "Thermogravimetric analysis", "thermogravimetric analysis",
        "Thermogravimetric Analysis", "TG", "TG-DSC", "TGA-DSC",
    ],
    "DSC": [
        "DSC", "Differential scanning calorimetry",
        "Differential Scanning Calorimetry",
    ],
    "BET": [
        "BET", "BET surface area", "N2 adsorption-desorption",
        "BET analysis", "Brunauer-Emmett-Teller",
        "Nitrogen adsorption", "N2 physisorption",
    ],
    "FTIR": [
        "FTIR", "Fourier-transform infrared spectroscopy",
        "Fourier Transform Infrared Spectroscopy",
        "IR spectroscopy", "Infrared spectroscopy",
        "ATR-FTIR",
    ],
    "ICP": [
        "ICP", "ICP-OES", "ICP-MS", "ICP-AES",
        "Inductively coupled plasma", "inductively coupled plasma",
    ],
    "NMR": [
        "NMR", "Solid-state NMR", "solid-state NMR", "SS-NMR",
        "7Li NMR", "6Li NMR", "23Na NMR", "31P NMR", "19F NMR",
        "Nuclear magnetic resonance",
    ],
    "Ionic conductivity measurement": [
        "Ionic conductivity measurement", "ionic conductivity measurement",
        "Ionic conductivity", "ionic conductivity",
        "Conductivity measurement", "DC polarization",
        "Hebb-Wagner polarization", "Electronic conductivity",
    ],
    "DFT calculation": [
        "DFT", "Density functional theory", "density functional theory",
        "DFT calculation", "DFT calculations",
        "First-principles calculation", "first-principles calculations",
        "Ab initio", "ab initio", "VASP", "AIMD",
        "DFT (PBE)", "DFT (PBE+vdW)", "DFT (HSE06)",
        "Molecular dynamics", "molecular dynamics", "MD simulation",
    ],
    "Neutron diffraction": [
        "Neutron diffraction", "neutron diffraction",
        "Neutron powder diffraction", "NPD",
    ],
    "EDX/EDS": [
        "EDX", "EDS", "Energy-dispersive X-ray spectroscopy",
        "Energy dispersive spectroscopy",
    ],
    "AFM": [
        "AFM", "Atomic force microscopy", "atomic force microscopy",
    ],
    "UV-Vis": [
        "UV-Vis", "UV-Vis spectroscopy", "UV-visible spectroscopy",
        "Ultraviolet-visible spectroscopy",
    ],
    "Mossbauer spectroscopy": [
        "Mossbauer spectroscopy", "Mössbauer spectroscopy",
        "57Fe Mössbauer",
    ],
    "EELS": [
        "EELS", "Electron energy loss spectroscopy",
    ],
    "XANES/EXAFS": [
        "XANES", "EXAFS", "X-ray absorption spectroscopy", "XAS",
        "X-ray absorption near edge structure",
        "Extended X-ray absorption fine structure",
    ],
}

# Build reverse lookup: variant → canonical name
CHAR_REVERSE_MAP = {}
for canonical, variants in CHAR_METHOD_MAPPING.items():
    for variant in variants:
        CHAR_REVERSE_MAP[variant.lower()] = canonical


def normalize_char_method(raw_method):
    """Normalize a characterization method name to canonical form."""
    raw_lower = raw_method.strip().lower()

    # Direct match
    if raw_lower in CHAR_REVERSE_MAP:
        return CHAR_REVERSE_MAP[raw_lower]

    # Substring matching for common patterns
    for canonical, variants in CHAR_METHOD_MAPPING.items():
        for variant in variants:
            if variant.lower() in raw_lower or raw_lower in variant.lower():
                return canonical

    # If no match, return original (cleaned up)
    return raw_method.strip()


# ============================================================
# MAIN: Process all JSONs
# ============================================================

def safe_get(obj, *keys, default=None):
    for key in keys:
        if isinstance(obj, dict):
            obj = obj.get(key, default)
        else:
            return default
    return obj


def process_all():
    all_papers = []
    char_raw_to_norm = Counter()
    char_norm_counter = Counter()
    unmapped_methods = Counter()

    for filepath in sorted(DATASET_DIR.glob("*.json")):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"ERROR: {filepath.name}: {e}")
            continue

        filename = filepath.name
        raw_type = safe_get(data, "metadata", "type", default="")
        tags = safe_get(data, "metadata", "tags", default=[])
        num_targets = len(safe_get(data, "targets", default=[]))
        num_chemicals = len(safe_get(data, "chemicals", default=[]))
        num_steps = len(safe_get(data, "synthesis", "steps", default=[]))
        num_char = len(safe_get(data, "characterization", default=[]))

        # Count operations
        num_ops = 0
        for step in safe_get(data, "synthesis", "steps", default=[]):
            ops = step.get("operations", [])
            if isinstance(ops, list):
                num_ops += len(ops)

        # Count char results
        num_char_results = 0
        for ch in safe_get(data, "characterization", default=[]):
            results = ch.get("results", [])
            if isinstance(results, list):
                num_char_results += len(results)

        # Classify paper type
        canonical_type = classify_paper_type(raw_type, num_steps, num_targets, num_char, tags)
        has_experimental = num_steps > 0

        # Normalize characterization methods
        char_methods_raw = []
        char_methods_normalized = []
        for ch in safe_get(data, "characterization", default=[]):
            method = ch.get("method", "")
            if method:
                char_methods_raw.append(method)
                norm = normalize_char_method(method)
                char_methods_normalized.append(norm)
                char_raw_to_norm[f"{method} → {norm}"] += 1
                char_norm_counter[norm] += 1
                if norm == method.strip():
                    unmapped_methods[method.strip()] += 1

        all_papers.append({
            "filename": filename,
            "title": safe_get(data, "source", "title", default=""),
            "doi": safe_get(data, "source", "doi", default=""),
            "journal": safe_get(data, "source", "journal", default=""),
            "year": safe_get(data, "source", "year", default=None),
            "raw_paper_type": raw_type,
            "paper_category": canonical_type,
            "has_experimental_section": has_experimental,
            "num_targets": num_targets,
            "num_chemicals": num_chemicals,
            "num_synthesis_steps": num_steps,
            "num_operations": num_ops,
            "num_characterization": num_char,
            "num_char_results": num_char_results,
            "char_methods_raw": "|".join(char_methods_raw),
            "char_methods_normalized": "|".join(char_methods_normalized),
            "tags": "|".join(tags) if tags else "",
        })

    # Load scores
    scores = {}
    for csv_file in [BASE_DIR / "results" / "combined_evaluation_summary.csv",
                     BASE_DIR / "results" / "30_high.csv",
                     BASE_DIR / "results" / "30_low.csv"]:
        if csv_file.exists():
            with open(csv_file, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    fn = row.get("filename") or row.get("file") or ""
                    try:
                        score = float(row.get("score_percent") or row.get("score_pct") or 0)
                    except:
                        score = 0
                    verdict = row.get("verdict", "")
                    if fn and fn not in scores:
                        scores[fn] = {"score": score, "verdict": verdict}

    for p in all_papers:
        s = scores.get(p["filename"], {})
        p["score"] = s.get("score", None)
        p["verdict"] = s.get("verdict", "Unknown")

    # === Write updated master index ===
    index_path = OUTPUT_DIR / "master_index_v2.csv"
    fieldnames = ["filename", "title", "doi", "journal", "year",
                  "raw_paper_type", "paper_category", "has_experimental_section",
                  "score", "verdict",
                  "num_targets", "num_chemicals", "num_synthesis_steps",
                  "num_operations", "num_characterization", "num_char_results",
                  "char_methods_normalized", "tags"]

    with open(index_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for p in all_papers:
            row = {k: p[k] for k in fieldnames}
            writer.writerow(row)

    # === Paper category statistics ===
    cat_counter = Counter(p["paper_category"] for p in all_papers)
    exp_papers = [p for p in all_papers if p["has_experimental_section"]]
    non_exp = [p for p in all_papers if not p["has_experimental_section"]]

    # Score distribution by category
    cat_scores = defaultdict(list)
    for p in all_papers:
        if p["score"] is not None:
            cat_scores[p["paper_category"]].append(p["score"])

    # Experimental-only statistics
    exp_total_targets = sum(p["num_targets"] for p in exp_papers)
    exp_total_chemicals = sum(p["num_chemicals"] for p in exp_papers)
    exp_total_steps = sum(p["num_synthesis_steps"] for p in exp_papers)
    exp_total_ops = sum(p["num_operations"] for p in exp_papers)
    exp_total_char = sum(p["num_characterization"] for p in exp_papers)
    exp_total_char_results = sum(p["num_char_results"] for p in exp_papers)

    # Experimental-only score distribution
    exp_score_dist = Counter()
    for p in exp_papers:
        exp_score_dist[p["verdict"]] += 1

    full_score_dist = Counter(p["verdict"] for p in all_papers)

    # === Write comprehensive report ===
    report_path = OUTPUT_DIR / "classification_report.txt"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("=" * 70 + "\n")
        f.write("PAPER TYPE CLASSIFICATION & CHARACTERIZATION NORMALIZATION REPORT\n")
        f.write("=" * 70 + "\n\n")

        f.write(f"Total papers processed: {len(all_papers)}\n")
        f.write(f"Papers WITH experimental synthesis: {len(exp_papers)} ({len(exp_papers)/len(all_papers)*100:.1f}%)\n")
        f.write(f"Papers WITHOUT experimental synthesis: {len(non_exp)} ({len(non_exp)/len(all_papers)*100:.1f}%)\n\n")

        f.write("CANONICAL PAPER CATEGORIES:\n")
        for cat in sorted(cat_counter.keys()):
            count = cat_counter[cat]
            avg_score = sum(cat_scores[cat]) / len(cat_scores[cat]) if cat_scores[cat] else 0
            f.write(f"  {cat:30s}: {count:4d} ({count/len(all_papers)*100:5.1f}%) | avg score: {avg_score:5.1f}%\n")

        f.write("\n" + "=" * 70 + "\n")
        f.write("SCORE DISTRIBUTION COMPARISON\n")
        f.write("=" * 70 + "\n\n")

        f.write("Full dataset (N={}):\n".format(len(all_papers)))
        for v in ["Excellent", "Good", "Acceptable", "Poor", "Unknown"]:
            c = full_score_dist.get(v, 0)
            f.write(f"  {v:12s}: {c:4d} ({c/len(all_papers)*100:.1f}%)\n")

        f.write(f"\nExperimental-only (N={len(exp_papers)}):\n")
        for v in ["Excellent", "Good", "Acceptable", "Poor", "Unknown"]:
            c = exp_score_dist.get(v, 0)
            f.write(f"  {v:12s}: {c:4d} ({c/len(exp_papers)*100:.1f}%)\n")

        f.write(f"\n{'Metric':<35} {'Full (N={})'.format(len(all_papers)):>15} {'Exp-only (N={})'.format(len(exp_papers)):>15}\n")
        f.write("-" * 65 + "\n")
        all_targets = sum(p["num_targets"] for p in all_papers)
        all_chemicals = sum(p["num_chemicals"] for p in all_papers)
        all_steps = sum(p["num_synthesis_steps"] for p in all_papers)
        all_ops = sum(p["num_operations"] for p in all_papers)
        all_char = sum(p["num_characterization"] for p in all_papers)
        all_char_r = sum(p["num_char_results"] for p in all_papers)

        for label, full_val, exp_val in [
            ("Total target compounds", all_targets, exp_total_targets),
            ("Total chemicals", all_chemicals, exp_total_chemicals),
            ("Total synthesis steps", all_steps, exp_total_steps),
            ("Total synthesis operations", all_ops, exp_total_ops),
            ("Total characterization entries", all_char, exp_total_char),
            ("Total characterization results", all_char_r, exp_total_char_results),
        ]:
            f.write(f"  {label:<33} {full_val:>15,} {exp_val:>15,}\n")

        f.write("\n" + "=" * 70 + "\n")
        f.write("CHARACTERIZATION METHOD NORMALIZATION\n")
        f.write("=" * 70 + "\n\n")

        f.write("NORMALIZED METHOD FREQUENCIES:\n")
        for method, count in char_norm_counter.most_common():
            f.write(f"  {method:35s}: {count:4d}\n")

        f.write(f"\nTotal raw method entries: {sum(char_norm_counter.values())}\n")
        f.write(f"Unique normalized methods: {len(char_norm_counter)}\n")

        if unmapped_methods:
            f.write(f"\nUNMAPPED METHODS (not normalized, kept as-is):\n")
            for method, count in unmapped_methods.most_common(30):
                f.write(f"  {method:50s}: {count:4d}\n")

        # Papers with zero synthesis that score 100%
        f.write("\n" + "=" * 70 + "\n")
        f.write("PAPERS SCORING 100% WITH ZERO SYNTHESIS STEPS\n")
        f.write("=" * 70 + "\n\n")
        perfect_no_synth = [p for p in all_papers
                           if p["score"] == 100.0 and p["num_synthesis_steps"] == 0]
        f.write(f"Count: {len(perfect_no_synth)} papers\n\n")
        for p in perfect_no_synth[:20]:
            f.write(f"  [{p['paper_category']}] {p['filename'][:70]}\n")
            f.write(f"    Targets: {p['num_targets']}, Chemicals: {p['num_chemicals']}, "
                    f"Char: {p['num_characterization']}\n")
        if len(perfect_no_synth) > 20:
            f.write(f"  ... and {len(perfect_no_synth) - 20} more\n")

    # === Write paper category distribution CSV ===
    cat_csv_path = OUTPUT_DIR / "paper_category_distribution.csv"
    with open(cat_csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["category", "count", "percentage", "avg_score",
                         "has_experimental_count"])
        for cat in sorted(cat_counter.keys()):
            count = cat_counter[cat]
            avg_score = sum(cat_scores[cat]) / len(cat_scores[cat]) if cat_scores[cat] else 0
            exp_count = sum(1 for p in all_papers
                          if p["paper_category"] == cat and p["has_experimental_section"])
            writer.writerow([cat, count, f"{count/len(all_papers)*100:.1f}",
                           f"{avg_score:.1f}", exp_count])

    # === Write normalized characterization CSV ===
    norm_char_path = OUTPUT_DIR / "characterization_normalized.csv"
    with open(norm_char_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["normalized_method", "count"])
        for method, count in char_norm_counter.most_common():
            writer.writerow([method, count])

    # === Write experimental-only score distribution ===
    exp_score_path = OUTPUT_DIR / "score_distribution_experimental.csv"
    with open(exp_score_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["verdict", "count", "percentage"])
        for v in ["Excellent", "Good", "Acceptable", "Poor", "Unknown"]:
            c = exp_score_dist.get(v, 0)
            writer.writerow([v, c, f"{c/len(exp_papers)*100:.1f}" if exp_papers else "0"])

    print(f"\nClassification complete!")
    print(f"  Total: {len(all_papers)} papers")
    print(f"  Experimental: {len(exp_papers)} ({len(exp_papers)/len(all_papers)*100:.1f}%)")
    print(f"  Non-experimental: {len(non_exp)} ({len(non_exp)/len(all_papers)*100:.1f}%)")
    print(f"\nCategory breakdown:")
    for cat, count in cat_counter.most_common():
        print(f"  {cat:30s}: {count:4d}")
    print(f"\nCharacterization methods: {sum(char_norm_counter.values())} entries -> "
          f"{len(char_norm_counter)} unique normalized methods")
    print(f"\nOutputs: {OUTPUT_DIR}")
    print(f"  - master_index_v2.csv")
    print(f"  - classification_report.txt")
    print(f"  - paper_category_distribution.csv")
    print(f"  - characterization_normalized.csv")
    print(f"  - score_distribution_experimental.csv")


if __name__ == "__main__":
    process_all()
