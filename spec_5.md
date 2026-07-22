# Spec: Investigate Open Questions from AUDIT_DATA_AVAILABILITY.md

## Purpose

The repo-structure audit found several claims in `main.tex` Section 5.1
that don't match the actual repository, most notably a count mismatch:
the paper claims 60 papers in the "golden dataset" (top 30 + bottom 30
by automated evaluation score), but 93 `Verified_*.json` files actually
exist. This spec investigates the open questions **before** any decision
is made about fixing the repo or the paper — do not rename, delete, or
move any files as part of this task. This is read-only investigation.

## No-touch zones

Do not modify, rename, move, or delete any file in the repository as
part of this investigation. Do not "fix" the count mismatch by deleting
files to reach 60, and do not edit `main.tex`. This task produces a
findings report only; decisions based on it come afterward.

## Output

New file: `INVESTIGATION_FINDINGS.md` (repo root)

Structure the report as one section per question below, each with a
clear, direct answer plus the evidence used to reach it. If a question
cannot be answered from available data, say so explicitly rather than
guessing — a confident-sounding wrong answer here is worse than an
honest "couldn't determine this."

---

## Question 1 (highest priority): What are the 93 `Verified_*.json` files?

1. List all 93 filenames in `dataset/verified_jsons/` (or wherever this
   directory is actually located — re-confirm the path first).
2. Check file timestamps (creation and last-modified, if the filesystem
   / git history preserves this). Report the distribution: are all 93
   from a single batch (same day/hour), or spread across multiple
   distinct time periods? A single tight cluster suggests one generation
   run; multiple clusters suggest incremental additions over time.
3. If this is a git repository, run `git log --follow` (or equivalent)
   on a sample of these files, and specifically check whether the full
   set of 93 was ever exactly 60 at some earlier commit, with 33 added
   later. Report what you find, including specific commit hashes/dates
   if available.
4. Search the repo for any script that implements "top 30 + bottom 30 by
   automated evaluation score" selection logic (this is the paper's
   stated definition of the golden dataset in Section 5.1). If such a
   script exists:
   - Run it (read-only, don't let it overwrite anything) against the
     current `combined_evaluation_summary.csv` (or wherever per-paper
     automated scores now live) to compute the specific 60 paper IDs it
     would currently select.
   - Compare that computed list of 60 against the actual 93 filenames.
     Report: how many of the 93 match the computed 60? Are all 60
     computed papers present among the 93? What are the 33 (or however
     many) extra files, specifically — list their paper IDs/titles.
   - If no such script exists in the repo, say so explicitly — this
     itself is an important finding (it would mean the "top 30 + bottom
     30" selection was done manually or by a since-lost process, which
     has implications for reproducibility).
5. Cross-reference against `dataset/human_reviews/` (the 30-paper
   complexity-stratified human-review corpus): how many of the 93
   `Verified_*.json` papers are also among those 30? Report the exact
   overlap count and, ideally, the list.

## Question 2: What are the 91 PDFs in `dataset/pdfs/`?

1. List all 91 filenames/paper IDs.
2. Cross-reference against the 93 `Verified_*.json` set from Question 1:
   report exact overlap count.
3. Cross-reference against the 30-paper `dataset/human_reviews/` set:
   report exact overlap count.
4. If there's a clean near-match (e.g., 91 of 93, or 91 of some other
   meaningful set), report that explicitly, since it may indicate which
   real-world set of papers `dataset/pdfs/` was actually built to serve
   (e.g., "PDFs for all verified_jsons papers except 2 that couldn't be
   sourced" vs. some other explanation).

## Question 3: Does a v2.0 verification prompt exist anywhere, in any form?

1. Search the entire repo (not just `schema/`, since that directory
   doesn't exist per the audit) for anything resembling a "v2" or
   "improved" verification prompt:
   ```bash
   grep -rl "verification prompt" --include="*.py" --include="*.md" --include="*.json" --include="*.txt" .
   grep -rl "v2\.0\|v2_0\|version 2" --include="*.py" --include="*.md" .
   ```
2. Check whether the verification prompt is embedded as a string
   constant inside a Python script (e.g., `scripts/verify.py` or
   similar) rather than saved as a standalone file — if so, report
   which script and whether that embedded prompt differs from whatever
   v1 prompt file does exist (`extraction_prompt.md` per the audit).
3. Report a clear conclusion: (a) a genuine v2.0 prompt exists but isn't
   isolated as a standalone file, (b) no v2.0 prompt exists anywhere and
   the paper's claim is simply inaccurate, or (c) something else — state
   which, with evidence.

## Question 4 (lower priority): Figure/script scatter inventory

1. List all figure files (by filename) in `scripts/figures/`,
   `src/analysis/figures/`, and `dataset/analysis/` (or wherever figures
   actually live per the audit).
2. Report whether any filenames are duplicated across these locations
   (same figure saved in multiple places) versus genuinely distinct
   figures split across locations. This determines whether a future
   consolidation is a simple move or needs deduplication first.

---

## Acceptance check

- Every question above must have an explicit answer in the report, even
  if the answer is "could not be determined from available data" — do
  not silently skip a sub-question.
- All counts (overlaps, totals) must be exact numbers derived from
  actually listing/counting files or running a script, not estimates.
- Do not propose a fix or recommendation in this report — that's a
  follow-up decision. This report's job is only to establish the facts
  needed to make that decision correctly.