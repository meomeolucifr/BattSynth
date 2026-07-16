"""
Compute Aggregate Dataset Statistics
Parses all 605 extraction JSONs and computes:
- Total unique compounds, chemicals, synthesis steps, characterization entries
- Material system distribution
- Journal and year distribution
- Paper type distribution
- Score distribution (from evaluation CSVs)
"""

import json
import csv
import os
from pathlib import Path
from collections import Counter, defaultdict

REPO_ROOT = Path(__file__).resolve().parents[1]
DATASET_DIR = REPO_ROOT / "src" / "data" / "extractions"
SCORES_FILE = REPO_ROOT / "src" / "evaluation" / "combined_evaluation_summary.csv"
OUTPUT_DIR = REPO_ROOT / "src" / "analysis"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def safe_get(obj, *keys, default=None):
    """Safely get nested dict values."""
    for key in keys:
        if isinstance(obj, dict):
            obj = obj.get(key, default)
        else:
            return default
    return obj


def parse_json(filepath):
    """Parse a single extraction JSON and return stats."""
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    stats = {
        "filename": os.path.basename(filepath),
        "title": safe_get(data, "source", "title", default=""),
        "doi": safe_get(data, "source", "doi", default=""),
        "journal": safe_get(data, "source", "journal", default=""),
        "year": safe_get(data, "source", "year", default=None),
        "paper_type": safe_get(data, "metadata", "type", default=""),
        "tags": safe_get(data, "metadata", "tags", default=[]),
        "num_targets": len(safe_get(data, "targets", default=[])),
        "num_chemicals": len(safe_get(data, "chemicals", default=[])),
        "num_synthesis_steps": len(safe_get(data, "synthesis", "steps", default=[])),
        "num_characterization": len(safe_get(data, "characterization", default=[])),
        "num_analysis_methods": len(safe_get(data, "analysis", "methods", default=[])),
        "num_ambiguities": len(safe_get(data, "workflow", "ambiguities", default=[])),
        "has_yield": safe_get(data, "final_outcomes", "yield", "value") is not None,
        "has_capacity": safe_get(data, "final_outcomes", "capacity", "value") is not None,
        "has_cycle_life": safe_get(data, "final_outcomes", "cycle_life") is not None,
    }

    # Count total operations across all steps
    total_ops = 0
    for step in safe_get(data, "synthesis", "steps", default=[]):
        ops = step.get("operations", [])
        if isinstance(ops, list):
            total_ops += len(ops)
    stats["num_operations"] = total_ops

    # Collect target names and chemical names
    target_names = []
    for t in safe_get(data, "targets", default=[]):
        name = t.get("compound_name", "")
        formula = t.get("molecular_formula", "")
        if name:
            target_names.append(name)
        if formula and formula != name:
            target_names.append(formula)
    stats["target_names"] = target_names

    chemical_names = []
    chemical_roles = []
    for c in safe_get(data, "chemicals", default=[]):
        name = c.get("name", "")
        if name:
            chemical_names.append(name)
        role = safe_get(c, "ontology", "role", default="")
        if role:
            chemical_roles.append(role)
    stats["chemical_names"] = chemical_names
    stats["chemical_roles"] = chemical_roles

    # Collect characterization methods
    char_methods = []
    for ch in safe_get(data, "characterization", default=[]):
        m = ch.get("method", "")
        if m:
            char_methods.append(m)
    stats["char_methods"] = char_methods

    # Count characterization results
    total_char_results = 0
    for ch in safe_get(data, "characterization", default=[]):
        results = ch.get("results", [])
        if isinstance(results, list):
            total_char_results += len(results)
    stats["num_char_results"] = total_char_results

    return stats


def load_scores():
    """Load evaluation scores from CSV."""
    scores = {}
    # Also try loading from 30_high.csv and 30_low.csv
    for csv_file in [SCORES_FILE,
                     REPO_ROOT / "src" / "evaluation" / "golden_high_scores.csv",
                     REPO_ROOT / "src" / "evaluation" / "golden_low_scores.csv"]:
        if csv_file.exists():
            with open(csv_file, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Handle different column name conventions
                    filename = (row.get("filename") or row.get("file") or "")
                    try:
                        score = float(row.get("score_percent") or
                                      row.get("score_pct") or
                                      row.get("score") or 0)
                    except (ValueError, TypeError):
                        score = 0
                    verdict = row.get("verdict", "")
                    if filename and filename not in scores:
                        scores[filename] = {"score": score, "verdict": verdict}
    return scores


def classify_battery_subfield(tags, title, targets):
    """Attempt to classify paper into battery subfield based on tags and title."""
    text = " ".join(tags + [title] + targets).lower()

    if any(kw in text for kw in ["solid state electrolyte", "solid-state electrolyte",
                                   "solid electrolyte", "garnet", "nasicon", "argyrodite",
                                   "perovskite", "antiperovskite", "lipon", "sulfide electrolyte",
                                   "halide electrolyte", "all-solid-state"]):
        return "solid-state electrolyte"
    elif any(kw in text for kw in ["cathode", "ncm", "nmc", "lco", "lfp", "lmo",
                                     "layered oxide", "spinel", "olivine", "nickel-rich",
                                     "cobalt-free"]):
        return "cathode"
    elif any(kw in text for kw in ["anode", "graphite anode", "silicon anode",
                                     "lithium metal anode", "li metal"]):
        return "anode"
    elif any(kw in text for kw in ["li-s", "lithium sulfur", "lithium-sulfur",
                                     "sulfur cathode"]):
        return "Li-S"
    elif any(kw in text for kw in ["li-air", "lithium-air", "lithium air",
                                     "li-o2"]):
        return "Li-air"
    elif any(kw in text for kw in ["sodium", "na-ion", "na ion", "nasicon electrode"]):
        return "Na-ion"
    elif any(kw in text for kw in ["electrolyte", "liquid electrolyte", "gel electrolyte",
                                     "polymer electrolyte", "ionic liquid"]):
        return "electrolyte (liquid/polymer)"
    elif any(kw in text for kw in ["separator", "membrane"]):
        return "separator"
    elif any(kw in text for kw in ["recycl", "spent batter"]):
        return "recycling"
    elif any(kw in text for kw in ["mxene", "2d material"]):
        return "2D materials"
    elif any(kw in text for kw in ["interface", "interphase", "sei", "cei"]):
        return "interface/interphase"
    elif any(kw in text for kw in ["diffusion", "ionic conduction", "conductivity",
                                     "transport", "migration"]):
        return "ion transport"
    elif any(kw in text for kw in ["machine learning", "data-driven", "computational",
                                     "dft", "first-principles", "simulation"]):
        return "computational/ML"
    elif any(kw in text for kw in ["review", "overview", "perspective", "advances"]):
        return "review"
    else:
        return "other/general"


def main():
    # Parse all JSONs
    all_stats = []
    errors = []

    for filepath in sorted(DATASET_DIR.glob("*.json")):
        try:
            stats = parse_json(filepath)
            all_stats.append(stats)
        except Exception as e:
            errors.append(f"{filepath.name}: {e}")

    n = len(all_stats)
    print(f"Parsed {n} files ({len(errors)} errors)")

    # Load scores
    scores = load_scores()

    # === Aggregate counts ===
    total_targets = sum(s["num_targets"] for s in all_stats)
    total_chemicals = sum(s["num_chemicals"] for s in all_stats)
    total_steps = sum(s["num_synthesis_steps"] for s in all_stats)
    total_operations = sum(s["num_operations"] for s in all_stats)
    total_characterization = sum(s["num_characterization"] for s in all_stats)
    total_char_results = sum(s["num_char_results"] for s in all_stats)
    total_analysis = sum(s["num_analysis_methods"] for s in all_stats)
    total_ambiguities = sum(s["num_ambiguities"] for s in all_stats)

    # Unique items
    all_target_names = set()
    all_chemical_names = set()
    all_char_methods = set()
    for s in all_stats:
        all_target_names.update(s["target_names"])
        all_chemical_names.update(s["chemical_names"])
        all_char_methods.update(s["char_methods"])

    # Distributions
    journal_counter = Counter(s["journal"] for s in all_stats if s["journal"])
    year_counter = Counter(s["year"] for s in all_stats if s["year"])
    type_counter = Counter(s["paper_type"] for s in all_stats if s["paper_type"])
    role_counter = Counter()
    char_method_counter = Counter()
    for s in all_stats:
        role_counter.update(s["chemical_roles"])
        char_method_counter.update(s["char_methods"])

    # Battery subfield classification
    subfield_counter = Counter()
    for s in all_stats:
        subfield = classify_battery_subfield(
            s["tags"], s["title"], s["target_names"]
        )
        s["battery_subfield"] = subfield
        subfield_counter[subfield] += 1

    # Score distribution
    score_dist = {"Excellent": 0, "Good": 0, "Acceptable": 0, "Poor": 0, "Unknown": 0}
    for s in all_stats:
        score_info = scores.get(s["filename"], {})
        verdict = score_info.get("verdict", "Unknown")
        s["score"] = score_info.get("score", None)
        s["verdict"] = verdict
        score_dist[verdict] = score_dist.get(verdict, 0) + 1

    # Final outcomes
    papers_with_yield = sum(1 for s in all_stats if s["has_yield"])
    papers_with_capacity = sum(1 for s in all_stats if s["has_capacity"])
    papers_with_cycle_life = sum(1 for s in all_stats if s["has_cycle_life"])

    # === Write master index CSV ===
    index_path = OUTPUT_DIR / "master_index.csv"
    with open(index_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "filename", "title", "doi", "journal", "year", "paper_type",
            "battery_subfield", "score", "verdict",
            "num_targets", "num_chemicals", "num_synthesis_steps",
            "num_operations", "num_characterization", "num_char_results",
            "num_analysis_methods", "num_ambiguities",
            "has_yield", "has_capacity", "has_cycle_life"
        ])
        writer.writeheader()
        for s in all_stats:
            writer.writerow({
                "filename": s["filename"],
                "title": s["title"],
                "doi": s["doi"],
                "journal": s["journal"],
                "year": s["year"],
                "paper_type": s["paper_type"],
                "battery_subfield": s["battery_subfield"],
                "score": s["score"],
                "verdict": s["verdict"],
                "num_targets": s["num_targets"],
                "num_chemicals": s["num_chemicals"],
                "num_synthesis_steps": s["num_synthesis_steps"],
                "num_operations": s["num_operations"],
                "num_characterization": s["num_characterization"],
                "num_char_results": s["num_char_results"],
                "num_analysis_methods": s["num_analysis_methods"],
                "num_ambiguities": s["num_ambiguities"],
                "has_yield": s["has_yield"],
                "has_capacity": s["has_capacity"],
                "has_cycle_life": s["has_cycle_life"],
            })

    # === Write summary report ===
    report_path = OUTPUT_DIR / "dataset_statistics_summary.txt"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("=" * 70 + "\n")
        f.write("BATTSYNTH DATASET STATISTICS SUMMARY\n")
        f.write("=" * 70 + "\n\n")

        f.write(f"Total papers: {n}\n")
        f.write(f"Parse errors: {len(errors)}\n\n")

        f.write("AGGREGATE COUNTS:\n")
        f.write(f"  Total target compounds: {total_targets}\n")
        f.write(f"  Unique target names: {len(all_target_names)}\n")
        f.write(f"  Total chemicals: {total_chemicals}\n")
        f.write(f"  Unique chemical names: {len(all_chemical_names)}\n")
        f.write(f"  Total synthesis steps: {total_steps}\n")
        f.write(f"  Total synthesis operations: {total_operations}\n")
        f.write(f"  Total characterization entries: {total_characterization}\n")
        f.write(f"  Total characterization results: {total_char_results}\n")
        f.write(f"  Total analysis methods: {total_analysis}\n")
        f.write(f"  Total ambiguities flagged: {total_ambiguities}\n\n")

        f.write("FINAL OUTCOMES COVERAGE:\n")
        f.write(f"  Papers with yield: {papers_with_yield} ({papers_with_yield/n*100:.1f}%)\n")
        f.write(f"  Papers with capacity: {papers_with_capacity} ({papers_with_capacity/n*100:.1f}%)\n")
        f.write(f"  Papers with cycle life: {papers_with_cycle_life} ({papers_with_cycle_life/n*100:.1f}%)\n\n")

        f.write("SCORE DISTRIBUTION:\n")
        for verdict in ["Excellent", "Good", "Acceptable", "Poor", "Unknown"]:
            count = score_dist.get(verdict, 0)
            f.write(f"  {verdict:12s}: {count:4d} ({count/n*100:.1f}%)\n")
        f.write("\n")

        f.write("PAPER TYPE DISTRIBUTION:\n")
        for ptype, count in type_counter.most_common():
            f.write(f"  {ptype:30s}: {count:4d} ({count/n*100:.1f}%)\n")
        f.write("\n")

        f.write("BATTERY SUBFIELD DISTRIBUTION:\n")
        for sf, count in subfield_counter.most_common():
            f.write(f"  {sf:30s}: {count:4d} ({count/n*100:.1f}%)\n")
        f.write("\n")

        f.write("TOP 20 JOURNALS:\n")
        for journal, count in journal_counter.most_common(20):
            f.write(f"  {journal:50s}: {count:4d}\n")
        f.write("\n")

        f.write("YEAR DISTRIBUTION:\n")
        for year in sorted(year_counter.keys()):
            if year:
                f.write(f"  {year}: {year_counter[year]:4d}\n")
        f.write("\n")

        f.write("TOP 20 CHEMICAL ROLES:\n")
        for role, count in role_counter.most_common(20):
            f.write(f"  {role:30s}: {count:4d}\n")
        f.write("\n")

        f.write("TOP 20 CHARACTERIZATION METHODS:\n")
        for method, count in char_method_counter.most_common(20):
            f.write(f"  {method:30s}: {count:4d}\n")
        f.write("\n")

        if errors:
            f.write("PARSE ERRORS:\n")
            for err in errors:
                f.write(f"  {err}\n")

    # === Write distributions as CSVs for plotting ===
    # Score distribution
    with open(OUTPUT_DIR / "score_distribution.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["verdict", "count", "percentage"])
        for verdict in ["Excellent", "Good", "Acceptable", "Poor", "Unknown"]:
            count = score_dist.get(verdict, 0)
            writer.writerow([verdict, count, f"{count/n*100:.1f}"])

    # Battery subfield distribution
    with open(OUTPUT_DIR / "subfield_distribution.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["subfield", "count", "percentage"])
        for sf, count in subfield_counter.most_common():
            writer.writerow([sf, count, f"{count/n*100:.1f}"])

    # Year distribution
    with open(OUTPUT_DIR / "year_distribution.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["year", "count"])
        for year in sorted(year_counter.keys()):
            if year:
                writer.writerow([year, year_counter[year]])

    # Journal distribution
    with open(OUTPUT_DIR / "journal_distribution.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["journal", "count"])
        for journal, count in journal_counter.most_common():
            writer.writerow([journal, count])

    # Characterization methods
    with open(OUTPUT_DIR / "characterization_methods.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["method", "count"])
        for method, count in char_method_counter.most_common():
            writer.writerow([method, count])

    print(f"\nOutputs written to: {OUTPUT_DIR}")
    print(f"  - master_index.csv ({n} papers)")
    print(f"  - dataset_statistics_summary.txt")
    print(f"  - score_distribution.csv")
    print(f"  - subfield_distribution.csv")
    print(f"  - year_distribution.csv")
    print(f"  - journal_distribution.csv")
    print(f"  - characterization_methods.csv")


if __name__ == "__main__":
    main()
