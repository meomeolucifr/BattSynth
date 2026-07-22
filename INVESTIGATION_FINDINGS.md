# Investigation Findings from AUDIT_DATA_AVAILABILITY.md

## Question 1: What are the 93 `Verified_*.json` files?

1. **File locations and list:** There are exactly 93 `Verified_*.json` files, distributed across three distinct directories:
   - `dataset/verified_jsons/` (30 files, distributed equally in `complex/`, `moderate/`, and `simple/` subdirectories)
   - `src/data/golden_dataset/high_results/` (33 files)
   - `src/data/golden_dataset/low_results/` (30 files)

2. **File timestamps:** All 93 files share the exact same commit timestamp (`Fri Jul 17 09:47:20 2026 +1000`) and the same creation/modification times in the local filesystem. They were all added in a single batch (commit hash `45a809220291e8237f0a2cc6bc87e17d7ce26d6a`, with message `"new"`), rather than incrementally over time.

3. **Git history:** A check using `git log` confirms the directory was committed exactly once with all these files present. There is no earlier commit where the file count was exactly 60.

4. **Selection script:** There is **no script** anywhere in the repository that dynamically implements a "top 30 + bottom 30 by automated evaluation score" selection logic. Instead, the selection appears to have been hardcoded directly into the repository's directory structure (`high_results/` and `low_results/`). Scripts like `re_evaluate_scores.py` simply print messages assuming this structure, but do not perform the selection themselves.

5. **Cross-reference against `dataset/human_reviews/`:** Exactly **30** of the 93 `Verified_*.json` files overlap with the human-review corpus. Specifically, the 30 files located in `dataset/verified_jsons/` map 1:1 to the 30 papers in `dataset/human_reviews/`. The remaining 63 files (in `high_results/` and `low_results/`) have no overlap with the human reviews.

## Question 2: What are the 91 PDFs in `dataset/pdfs/`?

1. **Count Clarification:** There are **60** PDFs in `dataset/pdfs/` (the number 91 represents the total count of `.pdf` files across the *entire* repository, including 31 figure files located in other directories).
2. **Overlap with 93 `Verified_*.json`:** The 60 PDFs in `dataset/pdfs/` contain only **30 unique papers**, because the 30 files in the root `dataset/pdfs/` folder are exactly duplicated inside its three subdirectories (`complex/`, `moderate/`, `simple/`). The overlap count with the 93 `Verified_*.json` set is therefore **30 unique papers** (matching the 30 in `dataset/verified_jsons/`).
3. **Overlap with `dataset/human_reviews/`:** The overlap count with the human reviews is also exactly **30**.
4. **Clean match:** The 30 unique PDFs in `dataset/pdfs/` perfectly match the 30-paper complexity-stratified human review corpus. The other 30 PDFs in this directory are just structural copies of the exact same 30 files.

## Question 3: Does a v2.0 verification prompt exist anywhere, in any form?

1. **Yes, a genuine v2.0 verification prompt exists as a standalone file**, but it is **not** located in a root `schema/` directory (which does not exist).
2. The file is named `improved_verification_prompt.txt` and starts with the header `"IMPROVED VERIFICATION PROMPT v2.0"`. 
3. **Conclusion:** It is saved as a standalone file in two different locations: 
   - `scripts/improved_verification_prompt.txt`
   - `src/schema/improved_verification_prompt.txt`
   The paper's claim that it exists is fundamentally accurate, but the path cited in the text/audit (`schema/`) is missing the `src/` prefix in the current repository structure.

## Question 4: Figure/script scatter inventory

1. **Figure File Locations:**
   - `scripts/figures/`: Contains 14 files (7 PDFs, 7 PNGs) named `fig1_score_distribution` through `fig7_journal_distribution`.
   - `src/analysis/figures/`: Contains 14 files (7 PDFs, 7 PNGs) with the **exact same names** as those in `scripts/figures/`.
   - `dataset/analysis/figures/`: Contains 30 files (PDFs and PNGs) with different, mostly non-overlapping descriptive suffixes (e.g., `fig1_prf_by_entity_type`, `fig10_metric_breakdown_comparison`, `fig14_llzo_sintering_vs_conductivity`).

2. **Duplication Status:** 
   While the filenames in `scripts/figures/` and `src/analysis/figures/` are identical (e.g., `fig1_score_distribution.pdf`), a check of their file sizes reveals they are **genuinely distinct files** (e.g., 20,608 bytes vs. 18,572 bytes). This indicates they were generated independently at different times or with different parameters, rather than being exact copies. The figures in `dataset/analysis/figures/` have uniquely descriptive names that are mostly distinct from the first two folders, though they share the `figX_` prefix numbering format. Any future consolidation will require deduplication/review of the identically-named but structurally distinct files in `scripts/` and `src/`.
