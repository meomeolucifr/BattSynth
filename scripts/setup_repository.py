"""
Setup GitHub Repository Structure for BattSynth Dataset
Creates the directory structure and README for the public release.
"""

import os
import shutil
from pathlib import Path

BASE_DIR = Path(r"C:\Users\12124\Downloads\Results_final\Results_final")
REPO_DIR = BASE_DIR / "src"


def create_structure():
    """Create the repository directory structure."""
    dirs = [
        REPO_DIR / "data" / "extractions",          # All 605 extraction JSONs
        REPO_DIR / "data" / "golden_dataset" / "high_results",  # Top 30 verified
        REPO_DIR / "data" / "golden_dataset" / "low_results",   # Bottom 30 verified
        REPO_DIR / "schema",                          # Schema + prompt
        REPO_DIR / "evaluation",                      # Scoring scripts + metrics
        REPO_DIR / "analysis",                        # Audit scripts + figures
        REPO_DIR / "analysis" / "figures",
        REPO_DIR / "notebooks",                       # Usage examples
        REPO_DIR / "templates",                       # Human review template
    ]

    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)

    print("Directory structure created.")
    return dirs


def copy_files():
    """Copy key files to repository structure."""
    copies = [
        # Schema
        (BASE_DIR / "format.json", REPO_DIR / "schema" / "format.json"),
        (BASE_DIR / "prompt.txt", REPO_DIR / "schema" / "extraction_prompt.txt"),

        # Evaluation
        (BASE_DIR / "results" / "combined_evaluation_summary.csv",
         REPO_DIR / "evaluation" / "combined_evaluation_summary.csv"),
        (BASE_DIR / "results" / "30_high.csv",
         REPO_DIR / "evaluation" / "golden_high_scores.csv"),
        (BASE_DIR / "results" / "30_low.csv",
         REPO_DIR / "evaluation" / "golden_low_scores.csv"),

        # Analysis outputs
        (BASE_DIR / "scripts" / "audit_output" / "verification_audit_summary.txt",
         REPO_DIR / "analysis" / "verification_audit_summary.txt"),
        (BASE_DIR / "scripts" / "audit_output" / "dataset_statistics_summary.txt",
         REPO_DIR / "analysis" / "dataset_statistics_summary.txt"),
        (BASE_DIR / "scripts" / "audit_output" / "master_index.csv",
         REPO_DIR / "analysis" / "master_index.csv"),
        (BASE_DIR / "scripts" / "audit_output" / "contradictions_for_review.csv",
         REPO_DIR / "analysis" / "contradictions_for_review.csv"),
        (BASE_DIR / "scripts" / "audit_output" / "per_file_summary.csv",
         REPO_DIR / "analysis" / "per_file_summary.csv"),
        (BASE_DIR / "scripts" / "audit_output" / "confidence_calibration.csv",
         REPO_DIR / "analysis" / "confidence_calibration.csv"),

        # Scripts
        (BASE_DIR / "scripts" / "audit_verification.py",
         REPO_DIR / "evaluation" / "audit_verification.py"),
        (BASE_DIR / "scripts" / "compute_stats.py",
         REPO_DIR / "evaluation" / "compute_stats.py"),
        (BASE_DIR / "scripts" / "generate_figures.py",
         REPO_DIR / "analysis" / "generate_figures.py"),
        (BASE_DIR / "scripts" / "improved_verification_prompt.txt",
         REPO_DIR / "schema" / "improved_verification_prompt.txt"),

        # Templates
        (BASE_DIR / "scripts" / "human_review_template.json",
         REPO_DIR / "templates" / "human_review_template.json"),
    ]

    for src, dst in copies:
        if src.exists():
            shutil.copy2(src, dst)
            print(f"  Copied: {src.name} -> {dst.relative_to(REPO_DIR)}")
        else:
            print(f"  MISSING: {src}")

    # Copy figures
    fig_src = BASE_DIR / "scripts" / "figures"
    if fig_src.exists():
        for f in fig_src.glob("*.png"):
            shutil.copy2(f, REPO_DIR / "analysis" / "figures" / f.name)
        for f in fig_src.glob("*.pdf"):
            shutil.copy2(f, REPO_DIR / "analysis" / "figures" / f.name)
        print(f"  Copied {len(list(fig_src.glob('*')))} figure files")

    # Copy all extraction JSONs
    src_dir = BASE_DIR / "Output_JSON" / "All_dataset" / "output_dataset"
    dst_dir = REPO_DIR / "data" / "extractions"
    count = 0
    for f in src_dir.glob("*.json"):
        shutil.copy2(f, dst_dir / f.name)
        count += 1
    print(f"  Copied {count} extraction JSONs to data/extractions/")

    # Copy golden dataset verified JSONs
    for group in ["high_results", "low_results"]:
        src = BASE_DIR / "Golden Dataset" / group
        dst = REPO_DIR / "data" / "golden_dataset" / group
        count = 0
        for f in src.glob("Verified_*.json"):
            shutil.copy2(f, dst / f.name)
            count += 1
        # Also copy the original (non-verified) JSONs
        for f in src.glob("*_reactions.json"):
            if not f.name.startswith("Verified_"):
                shutil.copy2(f, dst / f.name)
                count += 1
        print(f"  Copied {count} files to golden_dataset/{group}/")


def write_readme():
    """Write the repository README."""
    readme = REPO_DIR / "README.md"
    readme.write_text("""# BattSynth: LLM-Extracted Chemical Synthesis Dataset for Battery Materials

A large-scale dataset of chemical synthesis procedures extracted from 605 battery material research papers using GPT-o3, with multi-metric quality assurance and human-in-the-loop verification.

## Dataset Overview

| Metric | Count |
|--------|-------|
| Total papers | 605 |
| Target compounds | 1,537 |
| Unique chemicals | 1,663 |
| Synthesis steps | 1,872 |
| Synthesis operations | 2,880 |
| Characterization entries | 2,048 |
| Characterization results | 4,086 |

### Quality Distribution
- **Excellent** (>=90%): 437 papers (72.2%)
- **Good** (>=75%): 166 papers (27.4%)
- **Acceptable** (>=60%): 2 papers (0.3%)

### Battery Subfield Coverage
- Solid-state electrolytes: 216 (35.7%)
- Cathode materials: 124 (20.5%)
- Anode materials: 47 (7.8%)
- Liquid/polymer electrolytes: 43 (7.1%)
- Computational/ML: 38 (6.3%)
- And more...

## Repository Structure

```
src/
|-- data/
|   |-- extractions/           # 605 extraction JSONs (full dataset release)
|   |-- golden_dataset/        # 60 papers for evaluating extraction methods
|       |-- high_results/      # Top 30 (100% score) + Verified JSONs
|       |-- low_results/       # Bottom 30 (74-79%) + Verified JSONs
|-- schema/
|   |-- format.json            # Universal Chemistry Extraction Schema v2.1
|   |-- extraction_prompt.txt  # GPT-o3 extraction prompt
|   |-- improved_verification_prompt.txt  # LLM verification prompt v2.0
|-- evaluation/
|   |-- combined_evaluation_summary.csv   # All 605 paper scores
|   |-- golden_high_scores.csv            # Top 30 scores
|   |-- golden_low_scores.csv             # Bottom 30 scores
|   |-- audit_verification.py             # Verification audit script
|   |-- compute_stats.py                  # Dataset statistics script
|-- analysis/
|   |-- figures/                          # Publication figures
|   |-- master_index.csv                  # Master index of all papers
|   |-- verification_audit_summary.txt    # Verification quality report
|   |-- dataset_statistics_summary.txt    # Aggregate statistics
|-- templates/
|   |-- human_review_template.json        # Template for expert review
|-- notebooks/                            # Usage examples (TODO)
```

## Schema

All extractions follow the **Universal Chemistry Extraction Schema v2.1** (`schema/format.json`) with:
- Source metadata (title, DOI, authors, journal, year)
- Target compounds with molecular formulas
- Chemicals with roles (reactant, solvent, catalyst, etc.) and amounts
- Synthesis steps with operations, conditions, and parameters
- Characterization methods with quantitative results
- Final outcomes (yield, capacity, cycle life)
- Provenance tracking (page, table, figure references)

### Units Policy (strict)
| Quantity | Unit |
|----------|------|
| Temperature | K |
| Pressure | bar |
| Time | min |
| Mass | g |
| Volume | mL |
| Amount | mmol |
| Concentration | M |
| Capacity | mAh g-1 |

## Evaluation Metrics

Four metrics assess extraction quality:
1. **Provenance Validity**: Is each entity traceable to a source location?
2. **Units Policy Check**: Do all values use standardized units?
3. **Hallucination Detection**: Are extracted entities actually in the paper?
4. **Overall Score**: Weighted combination of field completeness + entity validity

## Golden Dataset

60 papers (top 30 + bottom 30 by score) serve as a benchmark:
- LLM-verified (`Verified_*.json`) with `_llm_flag` annotations
- Human expert reviewed (`Human_Verified_*.json`) — ground truth

## Citation

[Paper citation will be added upon publication]

## License

[To be determined]
""", encoding="utf-8")
    print("  README.md written")


def main():
    print("Setting up BattSynth repository structure...")
    create_structure()
    print("\nCopying files...")
    copy_files()
    print("\nWriting README...")
    write_readme()
    print(f"\nRepository ready at: {REPO_DIR}")

    # Count total files
    total = sum(1 for _ in REPO_DIR.rglob("*") if _.is_file())
    print(f"Total files in repository: {total}")


if __name__ == "__main__":
    main()
