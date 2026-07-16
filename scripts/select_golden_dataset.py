"""
Select 30 Experimental Papers for the New Golden Dataset
Stratified by synthesis complexity (simple/moderate/complex) and score range.
"""

import csv
import random
from pathlib import Path
from collections import defaultdict

BASE_DIR = Path(r"C:\Users\12124\Downloads\Results_final\Results_final")
INDEX_PATH = BASE_DIR / "scripts" / "audit_output" / "master_index_v2.csv"
PDF_DIR = BASE_DIR / "Pdf_files" / "All_dataset" / "dataset"
OUTPUT_DIR = BASE_DIR / "scripts" / "audit_output"

random.seed(42)  # Reproducible selection


def load_papers():
    """Load all papers from master index v2."""
    papers = []
    with open(INDEX_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            row["num_synthesis_steps"] = int(row["num_synthesis_steps"])
            row["num_chemicals"] = int(row["num_chemicals"])
            row["num_targets"] = int(row["num_targets"])
            row["num_operations"] = int(row["num_operations"])
            row["num_characterization"] = int(row["num_characterization"])
            row["num_char_results"] = int(row["num_char_results"])
            try:
                row["score"] = float(row["score"]) if row["score"] else None
            except ValueError:
                row["score"] = None
            row["has_experimental_section"] = row["has_experimental_section"] == "True"
            papers.append(row)
    return papers


def classify_complexity(p):
    """Classify paper into simple/moderate/complex based on extraction richness."""
    steps = p["num_synthesis_steps"]
    chemicals = p["num_chemicals"]
    char = p["num_characterization"]
    ops = p["num_operations"]

    # Complexity score (weighted combination)
    complexity_score = steps * 3 + chemicals * 1 + char * 1.5 + ops * 2

    if steps <= 2 and chemicals <= 5:
        return "simple", complexity_score
    elif steps <= 5 and chemicals <= 10:
        return "moderate", complexity_score
    else:
        return "complex", complexity_score


def check_pdf_exists(filename):
    """Check if corresponding PDF exists in the dataset folder."""
    # Derive PDF name from JSON filename
    pdf_name = filename.replace("_reactions.json", ".pdf")
    return (PDF_DIR / pdf_name).exists()


def main():
    papers = load_papers()

    # Filter to experimental papers with synthesis steps
    experimental = [p for p in papers
                    if p["has_experimental_section"]
                    and p["paper_category"] == "experimental_synthesis"
                    and p["num_synthesis_steps"] > 0]

    print(f"Total experimental synthesis papers with steps: {len(experimental)}")

    # Classify complexity
    for p in experimental:
        tier, score = classify_complexity(p)
        p["complexity_tier"] = tier
        p["complexity_score"] = score

    # Group by tier
    tiers = defaultdict(list)
    for p in experimental:
        tiers[p["complexity_tier"]].append(p)

    print(f"\nComplexity distribution:")
    for tier in ["simple", "moderate", "complex"]:
        papers_in_tier = tiers[tier]
        scores = [p["score"] for p in papers_in_tier if p["score"] is not None]
        avg_score = sum(scores) / len(scores) if scores else 0
        print(f"  {tier:10s}: {len(papers_in_tier):4d} papers | avg score: {avg_score:.1f}% | "
              f"avg steps: {sum(p['num_synthesis_steps'] for p in papers_in_tier)/len(papers_in_tier):.1f} | "
              f"avg chemicals: {sum(p['num_chemicals'] for p in papers_in_tier)/len(papers_in_tier):.1f}")

    # Selection strategy:
    # For each tier, select 10 papers with score diversity:
    #   - 3-4 papers with score >= 95% (high quality extraction)
    #   - 3-4 papers with score 85-95% (medium quality)
    #   - 2-3 papers with score < 85% (challenging extractions)
    # Also ensure journal and subfield diversity

    selected = []

    for tier in ["simple", "moderate", "complex"]:
        pool = tiers[tier]

        # Sort by score for stratification
        scored = [p for p in pool if p["score"] is not None]

        high_score = [p for p in scored if p["score"] >= 95]
        mid_score = [p for p in scored if 85 <= p["score"] < 95]
        low_score = [p for p in scored if p["score"] < 85]

        print(f"\n{tier.upper()} tier selection pool:")
        print(f"  High (>=95%): {len(high_score)} papers")
        print(f"  Mid (85-95%): {len(mid_score)} papers")
        print(f"  Low (<85%): {len(low_score)} papers")

        tier_selected = []

        # Select from each score range
        if tier == "simple":
            # Simple: mostly high score expected, but include some lower
            n_high, n_mid, n_low = 4, 3, 3
        elif tier == "moderate":
            n_high, n_mid, n_low = 3, 4, 3
        else:  # complex
            n_high, n_mid, n_low = 3, 3, 4

        # Shuffle for randomness, then pick
        random.shuffle(high_score)
        random.shuffle(mid_score)
        random.shuffle(low_score)

        tier_selected.extend(high_score[:n_high])
        tier_selected.extend(mid_score[:n_mid])
        tier_selected.extend(low_score[:n_low])

        # If not enough in a range, fill from others
        remaining_needed = 10 - len(tier_selected)
        if remaining_needed > 0:
            all_remaining = [p for p in scored if p not in tier_selected]
            random.shuffle(all_remaining)
            tier_selected.extend(all_remaining[:remaining_needed])

        # Trim to exactly 10
        tier_selected = tier_selected[:10]

        for p in tier_selected:
            p["selection_tier"] = tier
        selected.extend(tier_selected)

    # === Write selection CSV ===
    sel_path = OUTPUT_DIR / "golden_dataset_selection.csv"
    with open(sel_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "tier", "filename", "title", "journal", "year", "score", "verdict",
            "battery_subfield", "num_synthesis_steps", "num_chemicals",
            "num_operations", "num_characterization", "num_char_results",
            "complexity_score", "doi"
        ])

        for tier in ["simple", "moderate", "complex"]:
            tier_papers = sorted(
                [p for p in selected if p["selection_tier"] == tier],
                key=lambda x: -(x["score"] or 0)
            )
            for p in tier_papers:
                writer.writerow([
                    tier,
                    p["filename"],
                    p["title"][:80],
                    p["journal"],
                    p["year"],
                    f"{p['score']:.1f}" if p["score"] else "",
                    p["verdict"],
                    p.get("battery_subfield", ""),
                    p["num_synthesis_steps"],
                    p["num_chemicals"],
                    p["num_operations"],
                    p["num_characterization"],
                    p["num_char_results"],
                    f"{p['complexity_score']:.0f}",
                    p["doi"],
                ])

    # === Print selection summary ===
    print(f"\n{'='*80}")
    print(f"GOLDEN DATASET SELECTION: {len(selected)} papers")
    print(f"{'='*80}")

    for tier in ["simple", "moderate", "complex"]:
        tier_papers = sorted(
            [p for p in selected if p["selection_tier"] == tier],
            key=lambda x: -(x["score"] or 0)
        )
        print(f"\n--- {tier.upper()} ({len(tier_papers)} papers) ---")
        print(f"{'Score':>6} {'Steps':>5} {'Chem':>5} {'Char':>5} {'Journal':<30} {'Title':<50}")
        print("-" * 130)
        for p in tier_papers:
            print(f"{p['score']:>5.1f}% {p['num_synthesis_steps']:>5} "
                  f"{p['num_chemicals']:>5} {p['num_characterization']:>5} "
                  f"{p['journal'][:30]:<30} {p['title'][:50]}")

    # Score distribution of selected papers
    sel_scores = [p["score"] for p in selected if p["score"]]
    print(f"\n--- SELECTION STATISTICS ---")
    print(f"Score range: {min(sel_scores):.1f}% - {max(sel_scores):.1f}%")
    print(f"Average score: {sum(sel_scores)/len(sel_scores):.1f}%")
    print(f"Median score: {sorted(sel_scores)[len(sel_scores)//2]:.1f}%")

    # Journal diversity
    journals = set(p["journal"] for p in selected)
    print(f"Unique journals: {len(journals)}")

    # Subfield diversity
    subfields = set(p.get("battery_subfield", "") for p in selected)
    print(f"Unique battery subfields: {len(subfields)}: {', '.join(sorted(subfields))}")

    print(f"\nOutput: {sel_path}")


if __name__ == "__main__":
    main()
