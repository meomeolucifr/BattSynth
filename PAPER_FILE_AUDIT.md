# BattSynth paper file audit

This manifest marks repository content by its relationship to the BattSynth
manuscript. It does not delete or move files.

## Status labels

- **PAPER-CORE**: directly supports a manuscript claim, table, figure, or released dataset.
- **PAPER-WORKFLOW**: records how paper artifacts were selected, verified, reviewed, or corrected.
- **GENERATED**: reproducible output; useful to publish, but not source code or source data.
- **ARCHIVE**: preserves a before/after state or historical provenance.
- **REDUNDANT-COPY**: duplicate/staging copy whose canonical version is elsewhere.
- **UNRELATED**: belongs to the newer crystal-structure synthesis application, not this paper.
- **LEGACY**: superseded or nonportable script; retain only for provenance unless modernized.

## Canonical paper release

| Path | Mark | Purpose |
|---|---|---|
| `src/data/extractions/` | **PAPER-CORE** | Canonical released set of 605 extraction JSONs. |
| `src/schema/format.json` | **PAPER-CORE** | Universal Chemistry Extraction Schema v2.1. |
| `src/schema/extraction_prompt.txt` | **PAPER-CORE** | Released extraction prompt. |
| `src/schema/improved_verification_prompt.txt` | **PAPER-CORE** | Released verifier prompt. |
| `src/evaluation/combined_evaluation_summary.csv` | **PAPER-CORE** | Scores for all 605 records. |
| `src/evaluation/golden_high_scores.csv` | **PAPER-CORE** | Top-30 automated-score selection. |
| `src/evaluation/golden_low_scores.csv` | **PAPER-CORE** | Bottom-30 automated-score selection. |
| `src/data/golden_dataset/` | **PAPER-CORE** | Original high/low score audit set and available LLM flags. |
| `src/analysis/master_index.csv` | **PAPER-CORE** | Corpus metadata used for journal, year, and subfield statistics. |
| `src/analysis/dataset_statistics_summary.txt` | **PAPER-CORE** | Aggregate counts reported in the manuscript. |
| `src/analysis/figures/` | **GENERATED** | Corpus-level manuscript figures. |
| Other files in `src/analysis/` | **GENERATED** | Verification audit and aggregate intermediate outputs. |
| `src/README.md` | **PAPER-CORE** | Public release documentation. |

## Complexity-stratified human benchmark

| Path | Mark | Purpose |
|---|---|---|
| `dataset/human_reviews/{simple,moderate,complex}/` | **PAPER-CORE** | Human ground-truth annotations for 30 papers and 828 entities. |
| `dataset/pdfs/{simple,moderate,complex}/` | **PAPER-CORE** | Source documents used for human and automated verification. |
| `dataset/extraction_jsons/{simple,moderate,complex}/` | **PAPER-CORE** | Evaluated extraction records. |
| `dataset/verified_jsons/{simple,moderate,complex}/` | **PAPER-CORE** | Entity-level LLM verifier annotations. |
| `dataset/extraction_jsons_corrected/` | **PAPER-CORE** | Corrected records and correction logs used for the after-correction analysis. |
| `dataset/golden_dataset_selection.csv` | **PAPER-WORKFLOW** | Complexity tier and paper selection record. |
| `dataset/analysis/golden_dataset_metrics.json` | **GENERATED** | Source for F1, agreement, kappa, calibration, and error-taxonomy results. |
| `dataset/analysis/evaluation_scores*.{json,csv}` | **GENERATED** | Automated golden-dataset scores. |
| `dataset/analysis/comparison_summary.{json,csv}` | **GENERATED** | Before/after correction results. |
| `dataset/analysis/table*.tex` | **GENERATED** | Manuscript-ready tables. |
| `dataset/analysis/figures/` | **GENERATED** | Manuscript-ready benchmark figures. |
| `dataset/**/backup/` and `**/_backups/` | **ARCHIVE** | Pre-correction or pre-update state. Keep where used for before/after results. |
| Flat duplicates directly in `dataset/pdfs/` | **REDUNDANT-COPY** | Tiered PDF directories are canonical. |
| Flat duplicates directly in `dataset/extraction_jsons/` | **REDUNDANT-COPY** | Tiered extraction directories are canonical; verify before deletion because older scripts read the flat layout. |

## Scripts used by the paper

### Active reproducibility entry points

| Script | Mark | Paper output |
|---|---|---|
| `scripts/compute_golden_metrics.py` | **PAPER-CORE** | 828-entity P/R/F1, tier/type breakdown, verifier agreement, kappa, calibration, errors, tables, figures. |
| `scripts/compute_evaluation_scores.py` | **PAPER-CORE** | Golden-dataset completeness, provenance, formula, units, hallucination, and composite scores. |
| `scripts/compare_scores_and_generate_figures.py` | **PAPER-CORE** | Before/after correction comparison and related figures. |
| `scripts/compute_stats.py` | **PAPER-CORE** | Corpus counts, coverage, journal/year/subfield summaries. |
| `scripts/generate_figures.py` | **PAPER-CORE** | Corpus-level paper figures from audit outputs. |

### Workflow/provenance scripts

| Script | Mark | Role |
|---|---|---|
| `scripts/classify_papers.py` | **PAPER-WORKFLOW, LEGACY-PATH** | Canonical paper-type classification and characterization normalization. |
| `scripts/select_golden_dataset.py` | **PAPER-WORKFLOW, LEGACY-PATH** | Reproducible complexity-stratified selection (`random.seed(42)`). |
| `scripts/generate_review_templates.py` | **PAPER-WORKFLOW, LEGACY-PATH** | Created human-review templates. |
| `scripts/run_verifier_golden.py` | **PAPER-WORKFLOW, LEGACY/INCOMPLETE** | Generated verifier files, but depends on an external `test_app` and API key. |
| `scripts/update_review_templates.py` | **PAPER-WORKFLOW, LEGACY-PATH** | Merged verifier flags into review templates. |
| `scripts/corrections_simple.py` | **PAPER-WORKFLOW** | Evidence-backed simple-tier corrections. |
| `scripts/corrections_moderate.py` | **PAPER-WORKFLOW, LEGACY-PATH** | Evidence-backed moderate-tier corrections; hard-coded path. |
| `scripts/corrections_complex.py` | **PAPER-WORKFLOW** | Evidence-backed complex-tier corrections. |
| `scripts/apply_review_corrections_v2.py` | **PAPER-WORKFLOW, LEGACY-PATH** | PDF-cross-checked correction pipeline; preferred over v1 but still hard-coded. |
| `scripts/audit_verification.py` | **PAPER-WORKFLOW, LEGACY-PATH** | Original 60-paper verifier contradiction audit. |
| `scripts/human_review_template.json` | **PAPER-WORKFLOW** | Review schema/template. |
| `scripts/improved_verification_prompt.txt` | **REDUNDANT-COPY** | Canonical copy is `src/schema/improved_verification_prompt.txt`. |

### Superseded or unsafe for paper ground truth

| Script | Mark | Reason |
|---|---|---|
| `scripts/apply_review_corrections.py` | **LEGACY** | V1 can trust LLM-suggested fixes; superseded by PDF-cross-checked v2 and explicit tier correction scripts. |
| `scripts/auto_complete_reviews.py` | **LEGACY / DO-NOT-USE-AS-GROUND-TRUTH** | Produces heuristic draft labels. It cannot replace entity-by-entity expert review. |
| `scripts/automatic_score.py` | **LEGACY** | Notebook-style original scorer; scoring logic is duplicated and better captured by `compute_evaluation_scores.py`. |
| `scripts/re_evaluate_scores.py` | **LEGACY** | Transitional cross-check with duplicated scoring logic and hard-coded paths. |
| `scripts/setup_repository.py` | **LEGACY** | One-off release assembly script; the assembled release now exists. |

## Duplicate/staging trees

| Path | Mark | Canonical replacement |
|---|---|---|
| `Output_JSON/All_dataset/output_dataset/` | **REDUNDANT-COPY / STAGING** | `src/data/extractions/` for publication. Keep only if it is the original extraction working tree. |
| `results/combined_evaluation_summary.csv` | **REDUNDANT-COPY / WORKING** | `src/evaluation/combined_evaluation_summary.csv`. |
| `results/30_high.csv` | **REDUNDANT-COPY / WORKING** | `src/evaluation/golden_high_scores.csv`. |
| `results/30_low.csv` | **REDUNDANT-COPY / WORKING** | `src/evaluation/golden_low_scores.csv`. |
| `format.json` | **REDUNDANT-COPY** | `src/schema/format.json`. |
| `prompt.txt` | **REDUNDANT-COPY** | `src/schema/extraction_prompt.txt`. |
| `scripts/audit_output/` | **REDUNDANT-COPY / GENERATED** | Published equivalents are under `src/analysis/`; some development-only normalized outputs remain here. |
| `scripts/figures/` | **REDUNDANT-COPY / GENERATED** | `src/analysis/figures/`. |
| `scripts/analysis_output/` | **GENERATED / HISTORICAL** | Superseded by `dataset/analysis/` for the final human benchmark. |

Before deleting any duplicate tree, compare file counts and hashes. Several
historical scripts still point to working-tree paths rather than canonical
release paths.

## Unrelated application code

The following files implement a separate crystal-structure retrieval and
synthesis-pathway application. They are not used to generate or evaluate the
BattSynth paper dataset:

- `run_graph.py`, `graph.py`, `state.py`, `models.py`
- `nodes/extraction.py`, `nodes/reasoning.py`
- `retriever.py`, `retrieve_mote2_arxiv.py`
- `prompts.py`, `example_data.py`
- `extraction_format.json`, `extraction_prompt.md`
- `mote2_arxiv_results_sample.json`
- `examples/`

Mark these **UNRELATED** and move them to a separate project or subdirectory if
the repository is intended to be the archival paper release.

## Recommended minimal archival package

For a clean paper repository, retain:

1. `src/`
2. `dataset/` (excluding unnecessary flat duplicates after hash verification)
3. The active and workflow scripts listed above after converting legacy paths
4. `Evaluation metrics.pdf`
5. `PAPER_FILE_AUDIT.md`

The external manuscript remains at `/home/abshe/MyCodes/a2i2_battsynth/main.tex`.
