# Spec: Synthesize Validation & Robustness Work Summary Report

## Purpose

Produce one accurate, self-contained report documenting: (1) everything
done so far under the robustness/validation effort (bootstrap CI,
downstream case studies, test-retest tooling), (2) the specific
extraction error that was discovered, and (3) the exact methodological
chain by which it was found. This report should be usable as: an internal
audit trail, source material for a Methods/SI appendix, and an update
Vinh can share with Prof. Tho or collaborators without them needing to
reconstruct the whole process from chat history.

## Critical constraint: ground everything in actual files, not narrative memory

Do not write this report from a paraphrased summary of "what happened."
Re-derive every number and every claim by actually opening the relevant
output files listed below. If a number in this spec's background section
conflicts with what you find in the actual file, trust the file and flag
the discrepancy — do not silently reconcile it.

## No-touch zones

This is a read-only synthesis task. Do not modify any script, any data
file, any JSON, or `main.tex`. Output is a single new report file only.

## Output

New file: `dataset/analysis/VALIDATION_SUMMARY_REPORT.md`

---

## Required structure and content

### 1. Overview (short, 3-5 sentences)

State the purpose: BattSynth's golden dataset relies on a single domain
expert annotator; this effort adds independent lines of evidence for
data quality and reliability without requiring a second annotator, plus
an exploratory downstream-usability check that surfaced a concrete
extraction error.

### 2. Task-by-task summary

For each task below, report: what was done, the exact method, the files
involved, the actual results (numbers pulled fresh from the real output
files, not restated from memory), and current status (`complete`,
`tooling built / human step pending`, `spec written / not yet executed`).

- **Bootstrap CI (paper-clustered)**
  - Script: `scripts/bootstrap_ci.py`
  - Output: `dataset/analysis/bootstrap_ci_results.csv`,
    `dataset/analysis/bootstrap_ci_table.md`
  - Re-open these files and report the actual overall/entity-type/tier
    point estimates and CI bounds found inside them.
  - Report whether these values have been merged into `main.tex` Table 2
    / Table 3 yet (check the actual `.tex` source for CI brackets in
    those tables — do not assume based on this spec).

- **Downstream validation — LLZO/garnet case study**
  - Script: `scripts/downstream_sintering_conductivity.py`
  - Output: relevant stats file(s) under `dataset/analysis/` (locate the
    actual filename — likely `downstream_validation_stats.json` or
    similar; if multiple versions exist from iterative reruns, use the
    most recent one and note the file's last-modified time)
  - Report: matching methodology (compound family match → sintering-step
    match → paired conductivity match), the funnel counts at each stage,
    and the final correlation statistics with exact values.

- **Downstream validation — Cathode case study**
  - Same script family (cathode variant)
  - Report: funnel counts (matched cathode role → has calcination temp →
    has paired capacity), pooled correlation statistics, and the
    stratified-by-family results (list every family group that reached
    n≥10, with its n and correlation statistics).

- **Test-retest tooling**
  - Scripts: `scripts/testretest_export.py`, `scripts/testretest_score.py`
  - Report: sampling method and actual tier counts in
    `testretest_export.csv` (re-count the actual rows per tier from the
    file, don't assume the originally planned numbers), and explicitly
    state whether `testretest_reliability.json` exists yet (i.e. whether
    the human re-review has been completed and scored). If it does not
    exist, state plainly: "human re-review step not yet completed."

- **Codebook extraction**
  - Check whether `dataset/analysis/codebook_worked_examples.json`
    exists. If not, state plainly: "not yet generated." If it exists,
    summarize how many real examples were found per bucket, and
    explicitly flag if the `wrong amount` or `semantic mismatch` buckets
    came back empty.

- **Paper integration (Task E: CI merge, Task F: repo-structure audit)**
  - State whether `AUDIT_DATA_AVAILABILITY.md` exists yet. If not:
    "not yet executed."

### 3. Key finding: the Hu et al. extraction error

This section needs to narrate the discovery chain precisely, in the order
it actually happened — not a cleaned-up "we hypothesized X and confirmed
it" narrative. Reconstruct it as:

1. **Starting point**: the cathode downstream validation task (calcination
   temperature vs. discharge capacity) was run on the full pooled sample
   (report actual n).
2. **What was observed**: the pooled linear correlation was weak/near-zero
   (report actual r, p).
3. **Follow-up diagnostic**: residuals from the linear fit were inspected;
   report the actual top-5 (or however many were inspected) largest-
   residual points, with their paper, temperature, and capacity values.
4. **Manual physical-plausibility check**: for each of those points,
   state what was checked against (theoretical capacity limits for the
   relevant chemistry) and the conclusion for each — which were flagged
   as genuine chemistry (conversion-type cathodes) vs. which was flagged
   as an error (Hu et al., Li-MnO2, reported value vs. theoretical
   maximum, with the actual ratio).
5. **Cross-check against golden dataset membership**: report whether Hu
   et al. was found in `dataset/human_reviews/` (i.e., whether it was
   part of the 30-paper human-reviewed golden set) — re-verify this by
   actually searching the directory, don't restate a prior claim without
   re-checking.
6. **Cross-check against automated evaluation score**: report the exact
   automated score and verdict for this paper, pulled fresh from
   whatever the actual scoring file is (previously located in
   `src/evaluation/combined_evaluation_summary.csv` — confirm this path
   is still correct, repo structure may have been reorganized since).
7. **Interpretation**: state plainly what this demonstrates — that the
   automated hallucination-detection heuristic (text-verbatim matching)
   did not catch a physically-impossible value, because the value was
   genuinely present in the source PDF text, and that this specific error
   would not have been caught by any existing QA layer had this
   downstream exercise not been run, since the paper fell outside the
   5% golden human-review sample.

### 4. Full artifact inventory

A flat table: every script and every output file produced during this
effort, with a one-line description and its actual current path
(re-verify each path exists — do not copy paths from this spec without
checking, since prior reorganizations have already caused path drift at
least once).

### 5. Outstanding / pending work

An explicit checklist of everything not yet done, derived from what
section 2 actually found to be missing/pending (not a static copy of a
prior plan) — e.g. human re-review for test-retest, codebook writing,
CI merge into paper tables, repo-structure audit execution, figure
generation for the three new downstream-validation figures, remaining
manuscript placeholders.

---

## Acceptance check

- Every numeric claim in the report must be traceable to a specific file
  path the agent actually opened — if a number cannot be re-verified
  from an existing file, mark it `[UNVERIFIED — could not locate source
  file]` rather than including it silently.
- Section 3 (the Hu et al. narrative) must reflect the actual
  chronological discovery process, not a retrospectively cleaned-up
  version. If reconstructing the exact original order is genuinely
  impossible from available files/logs, say so and present the best
  reconstruction available with that caveat stated.
- Do not editorialize or add recommendations beyond what's explicitly
  requested in sections 1-5 above — this is a factual synthesis report,
  not a new round of analysis.