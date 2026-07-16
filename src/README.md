# BattSynth: LLM-Extracted Chemical Synthesis Dataset for Battery Materials

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

The checked-in golden-dataset subset contains the top 30 and bottom 30 papers by automated score, together with the available LLM-verification files:
- LLM-verified (`Verified_*.json`) with `_llm_flag` annotations

The complexity-stratified 30-paper human-review corpus is available at the repository root in `dataset/`. It contains the human reviews, original and corrected extraction JSONs, LLM-verification files, source PDFs, generated tables and figures, and aggregate analysis outputs. The entity-level precision, recall, F1, and LLM-versus-human agreement metrics can be regenerated with `python scripts/compute_golden_metrics.py`; automated evaluation scores can be regenerated with `python scripts/compute_evaluation_scores.py`. Set `BATTSYNTH_GOLDEN_DIR` only when the corpus is stored elsewhere.

The `auto_complete_reviews.py` utility creates heuristic draft labels and must not be treated as a substitute for domain-expert review. Any labels it produces require entity-by-entity expert approval before use as human ground truth.

## Citation

[Paper citation will be added upon publication]

## License

[To be determined]
