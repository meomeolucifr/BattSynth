# Validation & Robustness Work Summary Report

## 1. Overview
BattSynth's golden dataset relies on a single domain expert annotator. This effort adds independent lines of evidence for data quality and reliability without requiring a second annotator, plus an exploratory downstream-usability check that surfaced a concrete extraction error.

## 2. Task-by-task summary

- **Bootstrap CI (paper-clustered)**
  - **Script**: `scripts/bootstrap_ci.py`
  - **Output**: `dataset/analysis/bootstrap_ci_results.csv`, `dataset/analysis/bootstrap_ci_table.md`
  - **Results**: 
    - **Overall**: Precision 93.6% [91.5, 95.6], Recall 94.6% [92.8, 96.2], F1 94.1% [92.7, 95.4]
    - **Entity Type - target**: Precision 82.0% [60.9, 96.9], Recall 62.1% [43.5, 77.2], F1 70.7% [53.6, 82.9]
    - **Entity Type - chemical**: Precision 94.3% [90.1, 97.9], Recall 98.6% [97.1, 100.0], F1 96.4% [93.9, 98.4]
    - **Entity Type - operation**: Precision 90.1% [84.2, 95.4], Recall 98.2% [95.2, 100.0], F1 93.9% [90.5, 97.0]
    - **Entity Type - step_description**: Precision 99.1% [97.2, 100.0], Recall 100.0% [100.0, 100.0], F1 99.6% [98.6, 100.0]
    - **Entity Type - characterization**: Precision 94.8% [90.9, 98.1], Recall 92.5% [84.4, 98.2], F1 93.7% [89.0, 96.9]
    - **Entity Type - final_outcome**: Precision 97.5% [92.1, 100.0], Recall 100.0% [100.0, 100.0], F1 98.7% [95.9, 100.0]
    - **Tier - simple**: Precision 95.9% [92.2, 98.8], Recall 93.4% [88.4, 97.5], F1 94.6% [91.7, 96.9]
    - **Tier - moderate**: Precision 92.5% [88.0, 96.5], Recall 94.7% [92.7, 96.8], F1 93.6% [91.7, 95.4]
    - **Tier - complex**: Precision 93.7% [91.4, 96.0], Recall 95.0% [92.0, 97.8], F1 94.3% [92.0, 96.4]
  - **Status**: CI values have *not* been merged into `main.tex` Table 2 / Table 3 yet (the actual `.tex` files do not contain CI brackets).

- **Downstream validation — LLZO/garnet case study**
  - **Script**: `scripts/downstream_sintering_conductivity.py`
  - **Output**: `dataset/analysis/downstream_validation_stats.json`
  - **Methodology**: Compound family match → sintering-step match → paired conductivity match.
  - **Results**:
    - Funnel counts: total_papers: 605 → matched_compound: 36 → has_sintering: 16 → has_conductivity: 7 → final_joined: 7
    - Note: Quantitative correlation claims have been dropped (see scope cut decision).
  - **Status**: Complete, but deprecated for manuscript reporting.

- **Downstream validation — Cathode case study**
  - **Script**: `scripts/downstream_calcination_capacity.py`
  - **Output**: `dataset/analysis/downstream_cathode_validation_stats.json`
  - **Methodology**: Matched cathode role → has calcination temp → has paired capacity.
  - **Results**:
    - Funnel counts: total_papers: 605 → matched_cathode: 158 → has_calcination: 78 → has_capacity: 67 → final_joined: 67
    - Note: Quantitative correlation claims and stratified-by-family analysis have been dropped (see scope cut decision).
  - **Status**: Complete, but deprecated for manuscript reporting.

- **Test-retest tooling**
  - **Scripts**: `scripts/testretest_export.py`, `scripts/testretest_score.py`
  - **Output**: `dataset/analysis/testretest_export.csv`
  - **Results**: 
    - Tier counts in export: complex: 44, moderate: 37, simple: 19 (total 100 sampled rows, mapped via `testretest_id_map.csv`).
  - **Status**: Human re-review step not yet completed (the file `dataset/analysis/testretest_reliability.json` does not exist yet).

- **Codebook extraction**
  - **Output**: `dataset/analysis/codebook_worked_examples.json`
  - **Results**: 
    - Correct: 2 examples
    - Hallucination: 3 examples
    - Wrong amount: 1 example
    - Semantic mismatch: 1 example
    - Other: 3 examples
    - Partially correct: 3 examples
    - Missing data: 3 examples
    - Note: The `wrong amount` and `semantic mismatch` buckets did *not* come back empty.
  - **Status**: Complete.

- **Paper integration (Task E: CI merge, Task F: repo-structure audit)**
  - **Output**: `AUDIT_DATA_AVAILABILITY.md`
  - **Results**: The audit file exists and identifies 7 discrepancies between the paper's claims and the actual repo structure.
  - **Status**: Audit executed, but fixes and CI merge are pending.

## 3. Decision Log: Downstream Scope Cut (Hu et al. false alarm)

1. **Original Claim**: During drafting, it was claimed that a capacity of 10,823 mAh/g (from Hu et al.) was physically impossible for Li-MnO2 and represented a clear extraction error.
2. **Verification**: Checked against the actual source (Hu et al., *Angew. Chem. Int. Ed.* 2015, DOI 10.1002/anie.201411626).
3. **Actual Result**: The extracted value is **genuine and correctly reported**. It is a Li-air (Li-O2) capacity normalized per gram of carbon electrode (mAh/g_carbon), a standard convention in that subfield.
4. **Final Decision**: Because the outlier detection and family stratification relied on unverified domain judgments, all quantitative and outlier-specific claims related to downstream validation were cut from the paper. The paper now only claims the schema's capability to support cross-field joins. (See `DECISION_LOG_DOWNSTREAM_SCOPE_CUT.md` for full details).

## 4. Full artifact inventory

| Description | File Path |
|---|---|
| Bootstrap CI calculation script | `scripts/bootstrap_ci.py` |
| Bootstrap CI results (CSV) | `dataset/analysis/bootstrap_ci_results.csv` |
| Bootstrap CI results (Markdown Table) | `dataset/analysis/bootstrap_ci_table.md` |
| Downstream LLZO validation script | `scripts/downstream_sintering_conductivity.py` |
| Downstream LLZO stats (JSON) | `dataset/analysis/downstream_validation_stats.json` |
| Downstream Cathode validation script | `scripts/downstream_calcination_capacity.py` |
| Downstream Cathode stats (JSON) | `dataset/analysis/downstream_cathode_validation_stats.json` |
| Cathode match log | `dataset/analysis/cathode_match_log.csv` |
| Test-retest export script | `scripts/testretest_export.py` |
| Test-retest score script | `scripts/testretest_score.py` |
| Test-retest data export (CSV) | `dataset/analysis/testretest_export.csv` |
| Test-retest ID mapping (CSV) | `dataset/analysis/testretest_id_map.csv` |
| Codebook worked examples (JSON) | `dataset/analysis/codebook_worked_examples.json` |
| Repository structure audit report | `AUDIT_DATA_AVAILABILITY.md` |

## 5. Outstanding / pending work

- [ ] Merge Bootstrap CI brackets into `main.tex` (Table 2 and Table 3).
- [ ] Complete the human re-review step for test-retest (generate `testretest_reliability.json`).
- [ ] Write the actual codebook using the worked examples.
- [ ] Execute the repo-structure audit fixes to resolve discrepancies identified in `AUDIT_DATA_AVAILABILITY.md`.
- [ ] Fill remaining manuscript placeholders.
