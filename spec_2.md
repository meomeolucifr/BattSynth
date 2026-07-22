# BattSynth — Paper Integration & Repo-Structure Audit Spec

## Context

Two remaining items before the manuscript is submission-ready:

1. The paper-clustered bootstrap CI results (Task A from
   `ROBUSTNESS_VALIDATION_SPEC.md`) were computed successfully but never
   merged into the manuscript tables — `main.tex` Table 2 and Table 3 still
   show point estimates only.
2. During the earlier audit, the agent found that the actual repo layout
   (`Output_JSON/All_dataset/output_dataset/`, `dataset/human_reviews/`,
   `scripts/`, `dataset/analysis/`) differs from what Section 5.1 of the
   manuscript ("Dataset Description and Access") claims
   (`data/extractions/`, `dataset/`, `schema/`, `evaluation/`, `analysis/`).
   This needs a full, systematic verification pass — but the fix (rename
   repo paths vs. rewrite the paper text) is a judgment call for Vinh, not
   something the agent should decide unilaterally.

## No-touch zones

- Do not modify point-estimate numbers already in Table 2 / Table 3 — only
  append CI values alongside them. If a recomputed point estimate does not
  match the existing number exactly, stop and report the mismatch; do not
  silently overwrite the table with a new point estimate.
- Do not modify Table 4 (confusion matrix), Table 5 (score distribution),
  Table 6 (metric breakdown), or Table 7 (eval by tier) — out of scope.
- For Task F (repo audit): do not rename any files or directories, and do
  not edit Section 5.1 of `main.tex`. This task produces a report only.
  Vinh decides and applies the actual fix by hand.

---

## Task E: Merge bootstrap CI into Table 2 / Table 3

### Priority: High

### Inputs

- `dataset/analysis/bootstrap_ci_results.csv` (produced by
  `scripts/bootstrap_ci.py`)
- `dataset/analysis/bootstrap_ci_table.md`

### Location

`main.tex`:
- Table 2 (`\label{tab:prf_entity_type}`, currently ~line 484–499)
- Table 3 (`\label{tab:prf_tier}`, currently ~line 501–517)
- Prose paragraph in Section 4.1 (`\label{sec:accuracy}`, currently ~line
  158) — add one methodology sentence describing the bootstrap procedure.

### Current state (Table 2, problem)

```latex
\begin{tabular}{lrrrr}
\toprule
Entity Type & $n$ & Precision & Recall & F1 \\
\midrule
  Target & 75 & 82.0\% & 62.1\% & 70.7\% \\
  Chemical & 222 & 94.3\% & 98.6\% & 96.4\% \\
  Operation & 184 & 90.1\% & 98.2\% & 94.0\% \\
  Step Description & 113 & 99.1\% & 100.0\% & 99.6\% \\
  Characterization & 155 & 94.8\% & 92.5\% & 93.7\% \\
  Final Outcome & 79 & 97.5\% & 100.0\% & 98.7\% \\
\midrule
  \textbf{Overall} & \textbf{828} & \textbf{93.6\%} & \textbf{94.6\%} & \textbf{94.1\%} \\
\bottomrule
\end{tabular}
```

No uncertainty is shown — a single-paper resample could plausibly shift
these numbers, and Table 2 currently gives no sense of that.

### Exact fix

Append the 95% CI in brackets under each point estimate, using
`\footnotesize` for the CI line to keep the table from overflowing the
page width. Use a `\shortstack{}` or a manual two-line cell via
`\makecell` (load `\usepackage{makecell}` in the preamble if not already
present — check first, do not duplicate the package load) so each cell
reads:

```
94.1\%
\footnotesize{[91.8, 96.0]}
```

Full replacement for Table 2:

```latex
\begin{tabular}{lrccc}
\toprule
Entity Type & $n$ & Precision & Recall & F1 \\
\midrule
  Target & 75 & \makecell{82.0\%\\\footnotesize{[CI_LO, CI_HI]}} & \makecell{62.1\%\\\footnotesize{[CI_LO, CI_HI]}} & \makecell{70.7\%\\\footnotesize{[CI_LO, CI_HI]}} \\
  Chemical & 222 & \makecell{94.3\%\\\footnotesize{[CI_LO, CI_HI]}} & \makecell{98.6\%\\\footnotesize{[CI_LO, CI_HI]}} & \makecell{96.4\%\\\footnotesize{[CI_LO, CI_HI]}} \\
  Operation & 184 & \makecell{90.1\%\\\footnotesize{[CI_LO, CI_HI]}} & \makecell{98.2\%\\\footnotesize{[CI_LO, CI_HI]}} & \makecell{94.0\%\\\footnotesize{[CI_LO, CI_HI]}} \\
  Step Description & 113 & \makecell{99.1\%\\\footnotesize{[CI_LO, CI_HI]}} & \makecell{100.0\%\\\footnotesize{[CI_LO, CI_HI]}} & \makecell{99.6\%\\\footnotesize{[CI_LO, CI_HI]}} \\
  Characterization & 155 & \makecell{94.8\%\\\footnotesize{[CI_LO, CI_HI]}} & \makecell{92.5\%\\\footnotesize{[CI_LO, CI_HI]}} & \makecell{93.7\%\\\footnotesize{[CI_LO, CI_HI]}} \\
  Final Outcome & 79 & \makecell{97.5\%\\\footnotesize{[CI_LO, CI_HI]}} & \makecell{100.0\%\\\footnotesize{[CI_LO, CI_HI]}} & \makecell{98.7\%\\\footnotesize{[CI_LO, CI_HI]}} \\
\midrule
  \textbf{Overall} & \textbf{828} & \makecell{\textbf{93.6\%}\\\footnotesize{[CI_LO, CI_HI]}} & \makecell{\textbf{94.6\%}\\\footnotesize{[CI_LO, CI_HI]}} & \makecell{\textbf{94.1\%}\\\footnotesize{[CI_LO, CI_HI]}} \\
\bottomrule
\end{tabular}
```

Replace every `[CI_LO, CI_HI]` with the actual 2.5th/97.5th percentile
values from `bootstrap_ci_results.csv`, rounded to 1 decimal place,
formatted as e.g. `[65.2, 76.1]`. Apply the same pattern to Table 3
(`tab:prf_tier`), pulling the tier-level and overall CI rows from the same
CSV.

**Important:** the `Overall` row CI must be identical across Table 2 and
Table 3 (both are the same 828-entity, 30-paper overall metric) — if the
CSV gives different overall CIs in the entity-type breakdown run vs. the
tier breakdown run, that's a bug in `bootstrap_ci.py`'s aggregation, not
something to paper over by picking one; report it instead of resolving it
silently.

### Prose addition (Section 4.1, `sec:accuracy`)

Insert as a new sentence at the end of the existing paragraph (after "...
without any domain-specific fine-tuning."):

```latex
To quantify the uncertainty introduced by evaluating on a finite,
30-paper sample, we additionally computed 95\% confidence intervals via
paper-clustered bootstrap resampling ($N$ = 10,000 resamples, resampling
the 30 papers with replacement rather than the 828 entities directly, to
respect within-paper correlation); these intervals are reported alongside
the point estimates in Tables~\ref{tab:prf_entity_type}
and~\ref{tab:prf_tier}.
```

### Acceptance check

- Every point estimate in the rebuilt tables must exactly match the
  existing (pre-CI) point estimates. Diff the old and new table content
  ignoring the CI additions to confirm zero drift.
- Confirm `\usepackage{makecell}` (or whatever two-line-cell mechanism is
  used) is declared exactly once in the preamble.
- Render a local pdflatex/xelatex compile if the toolchain is available
  in Vinh's environment, and report whether Table 2 overflows the text
  width at 5 columns with two-line cells (12pt article class, 1in
  margins per the preamble). If it overflows, reduce to `\scriptsize` for
  the whole tabular rather than restructuring the table, and report that
  this was needed.

---

## Task F: Repo-structure vs. Section 5.1 audit (diagnostic only)

### Priority: High (blocks release, but decision belongs to Vinh — do not auto-fix)

### Goal

Systematically check every path/artifact claim made in Section 5.1
("Dataset Contents") of `main.tex` against what actually exists in the
repository, and produce a structured discrepancy report. Do not rename
anything, do not edit `main.tex`, do not move files.

### Location of output

New file: `AUDIT_DATA_AVAILABILITY.md` (repo root)

### Claims to verify, one row per claim

Go through this exact list — each is a specific, falsifiable claim from
Section 5.1 of `main.tex`. For each, report: the claim, the actual path
found (or "not found"), the actual count where a count is claimed, and a
`suggested_action` of one of: `rename repo to match paper`,
`update paper to match repo`, `paper claim appears correct, no action`,
or `ambiguous — needs manual decision`.

1. **"605 extraction JSONs (one per paper) stored in `data/extractions/`"**
   — verify the actual directory (likely
   `Output_JSON/All_dataset/output_dataset/`), and verify the file count
   is exactly 605, not approximately 605.
2. **"`data/golden_dataset/` contains 60 papers — the top 30 and bottom 30
   by automated evaluation score — with the available LLM verification
   annotations (`Verified_*.json`)"** — this is a *different* 60-paper set
   from the 30-paper complexity-stratified human-review corpus. Confirm
   this second, separate 60-paper directory actually exists, confirm the
   count is 60 (not 30, not some other number — this claim has been a
   likely source of confusion given `dataset/human_reviews/` was already
   found to hold a different 30-paper set), and confirm `Verified_*.json`
   files with the described structure are present.
3. **"The complexity-stratified 30-paper human-review corpus ... is
   provided in `dataset/` at the repository root"** — verify against the
   already-confirmed `dataset/human_reviews/<tier>/Human_Review_*.json`
   location; confirm tier subfolder names and file count per tier (10/10/10
   papers).
4. **"The schema itself, the GPT-o3 extraction prompt, and the improved
   verification prompt (v2.0) are provided in a separate `schema/`
   directory"** — verify existence of a schema directory, and specifically
   verify a v2.0-labeled verification prompt file exists (not just a v1
   or unlabeled prompt file).
5. **"per-paper scores, golden-dataset scores, and analysis scripts are
   collected in `evaluation/`"** — verify against the already-confirmed
   `scripts/` location, and specifically confirm whether per-paper score
   files (e.g. the `combined_evaluation_summary.csv` used earlier to look
   up the Hu et al. score) live under `scripts/` or somewhere else (e.g.
   `src/evaluation/`, which is where `combined_evaluation_summary.csv` was
   actually found according to the earlier session log — reconcile this
   third possible location explicitly).
6. **"an `analysis/` directory contains a master index, publication-quality
   figures, and aggregate statistics"** — verify against the
   already-confirmed `dataset/analysis/` location, and confirm the figures
   referenced in `main.tex` (`figures/fig_*.pdf` etc.) actually resolve to
   files somewhere in the repo (they may be in a separate top-level
   `figures/` folder rather than inside `analysis/` — check both).
7. **"The human reviews, source PDFs, original and corrected extraction
   JSONs, LLM-verification files, and generated analysis outputs required
   to reproduce the entity-level benchmark are included in that
   directory"** (referring to `analysis/`, per claim 6) — specifically
   verify that source PDFs are actually present somewhere in the repo (PDF
   files are large; confirm they are genuinely included and not, e.g.,
   referenced by path only with the files themselves absent or gitignored).

### Format of `AUDIT_DATA_AVAILABILITY.md`

```markdown
| # | Paper claim (Section 5.1) | Actual location found | Actual count (if applicable) | Suggested action | Notes |
|---|---|---|---|---|---|
| 1 | data/extractions/, 605 JSONs | ... | ... | ... | ... |
| 2 | data/golden_dataset/, 60 papers | ... | ... | ... | ... |
...
```

Add a final section `## Flagged for Vinh's manual review` listing every
row where `suggested_action` is `ambiguous` or where the actual count did
not match the paper's claimed count exactly — these are the items Vinh
needs to resolve by hand (either edit the repo structure before public
release, or edit Section 5.1's wording).

### Acceptance check

- Every one of the 7 claims above must have a row in the output table —
  do not skip a claim because it seems similar to one already checked.
- The agent must not conclude "probably fine" for any claim without
  actually listing the directory / counting files. If a path cannot be
  found at all, report `not found`, not a guess.
- This task produces a report file only. If the agent notices an
  opportunity to auto-fix something (e.g., renaming a folder), it should
  note the opportunity in the report's Notes column, not act on it.