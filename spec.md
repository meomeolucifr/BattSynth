# BattSynth — Robustness & Validation Additions Spec

## Context

Reviewers will ask: "Ground truth comes from a single annotator — how do we
trust it, and does the dataset actually work for downstream materials
science use?" This spec adds three independent lines of evidence without
requiring a second human annotator (which is currently hard to source):

1. Paper-clustered bootstrap confidence intervals for the existing F1/precision/recall
   numbers (Table 2, Table 3).
2. A downstream extrinsic-validation task: reconstruct a known
   sintering-temperature vs. ionic-conductivity trend for garnet-type
   (LLZO-family) solid-state electrolytes directly from the extracted JSONs.
3. Tooling to support test–retest (intra-annotator) reliability: a blinded
   re-review export + scoring script. (The actual re-review is done by the
   human; the agent only builds the tooling.)

## Assumed repo layout (confirm before starting)

```
data/extractions/          # 605 per-paper extraction JSONs
data/golden_dataset/       # 60 papers (top/bottom 30 by auto score) w/ Verified_*.json
dataset/                   # 30-paper complexity-stratified golden corpus + human review labels
evaluation/                # per-paper scores, golden-dataset scores, analysis scripts
analysis/                  # master index, figures, aggregate stats
```

If actual paths differ, the agent must first run a `find`/`ls` pass and
report the real structure before writing any code — do not guess paths
silently.

## No-touch zones

- Do not modify `data/extractions/*.json` or `data/golden_dataset/*.json` —
  these are the released dataset artifacts. All new scripts read-only from
  these.
- Do not modify existing `evaluation/` scoring scripts (automated quality
  metrics, F1 computation) — new work adds *new* scripts alongside them,
  it does not alter existing metric definitions or their outputs.
- Do not alter the 30-paper human review labels in `dataset/` — test-retest
  tooling only *exports* a blinded copy for re-review; it never overwrites
  the original labels file.

---

## Priority table

| # | Task | Priority | Effort | Depends on human step? |
|---|------|----------|--------|--------------------------|
| A | Paper-clustered bootstrap CI for F1/P/R | High | Low | No |
| B | Downstream validation: sintering T vs. ionic conductivity | High | Medium | No |
| C | Test–retest blinded re-review export + agreement scorer | Medium | Low (tooling only) | Yes, for the actual re-review |
| D | Codebook → Supporting Information doc | Low | Low | No (text only, not agent work) |

---

## A. Paper-clustered bootstrap CI

### Problem

Table 2 and Table 3 report point estimates only (e.g. Overall F1 = 94.1%,
n = 828 entities). Entities within the same paper are correlated (shared
extraction quality, shared paper-level difficulty), so a naive entity-level
bootstrap or normal-approximation CI would understate uncertainty. Need
a **cluster bootstrap at the paper level** (resample the 30 papers with
replacement, not the 828 entities directly).

### Location

New script: `evaluation/bootstrap_ci.py`

Input: the same per-entity human-review labels used to produce Table 2/3
(TP/FP/FN classification with partial-correct = 0.5/0.5 split, as described
in Section 4.1 of the manuscript). Locate wherever this per-entity table
currently lives (likely `dataset/human_review/*.csv` or similar — confirm
actual file during repo scan).

### Exact implementation

```python
import numpy as np
import pandas as pd

def paper_cluster_bootstrap(df, n_boot=10000, seed=42, group_col="paper_id",
                             entity_type_col=None, entity_type_filter=None):
    """
    df: one row per entity, columns must include:
        - paper_id
        - tp, fp, fn  (floats; partially-correct entities already
          contribute 0.5 to tp and 0.5 to fp per the paper's convention)
    Returns dict with point estimate + 95% CI for precision, recall, F1.
    """
    if entity_type_filter is not None:
        df = df[df[entity_type_col] == entity_type_filter]

    papers = df[group_col].unique()
    rng = np.random.default_rng(seed)

    def compute_prf(sub):
        tp, fp, fn = sub["tp"].sum(), sub["fp"].sum(), sub["fn"].sum()
        precision = tp / (tp + fp) if (tp + fp) > 0 else np.nan
        recall = tp / (tp + fn) if (tp + fn) > 0 else np.nan
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else np.nan
        return precision, recall, f1

    point_p, point_r, point_f1 = compute_prf(df)

    boot_p, boot_r, boot_f1 = [], [], []
    for _ in range(n_boot):
        sampled_papers = rng.choice(papers, size=len(papers), replace=True)
        sub = pd.concat([df[df[group_col] == p] for p in sampled_papers])
        p, r, f1 = compute_prf(sub)
        boot_p.append(p); boot_r.append(r); boot_f1.append(f1)

    def ci(arr):
        arr = np.array(arr)
        arr = arr[~np.isnan(arr)]
        return np.percentile(arr, [2.5, 97.5])

    return {
        "precision": (point_p, *ci(boot_p)),
        "recall": (point_r, *ci(boot_r)),
        "f1": (point_f1, *ci(boot_f1)),
        "n_papers": len(papers),
        "n_boot": n_boot,
    }
```

Run for:
- Overall (Table 2 "Overall" row)
- Each entity type (Target, Chemical, Operation, Step Description,
  Characterization, Final Outcome) — Table 2 breakdown
- Each complexity tier (Simple, Moderate, Complex) — Table 3

### Output

`evaluation/bootstrap_ci_results.csv` with columns:
`level, subgroup, precision, precision_ci_lo, precision_ci_hi, recall, recall_ci_lo, recall_ci_hi, f1, f1_ci_lo, f1_ci_hi, n_papers, n_boot`

Also produce a markdown table formatted for direct paste into the paper
(`evaluation/bootstrap_ci_table.md`), matching the style of Table 2/3 with
CI in brackets, e.g. `94.1% [91.8, 96.0]`.

### Acceptance check

- `n_boot=10000` minimum.
- Point estimates from the bootstrap function must exactly reproduce the
  numbers already in Table 2/3 (93.6% / 94.6% / 94.1% overall) — if they
  don't match, the input dataframe construction is wrong; stop and report
  the discrepancy rather than adjusting the CI code to compensate.

---

## B. Downstream validation task: sintering temperature vs. ionic conductivity

### Goal

Independently reconstruct a chemistry trend that's already established in
the literature (higher sintering/calcination temperature within a
reasonable window correlates with higher ionic conductivity in garnet-type
LLZO-family solid electrolytes, up to a point) using **only** fields pulled
from the BattSynth extraction JSONs. If the reconstructed trend matches
known literature direction, this is extrinsic evidence the extractions are
usable for real materials-informatics analysis, not just internally
consistent.

### Location

New script: `analysis/downstream_sintering_conductivity.py`

### Steps

1. **Filter target compounds.** Scan `data/extractions/*.json`, keep records
   where `target_compounds[].formula` or `.name` matches garnet-family
   LLZO patterns. Use a permissive regex/substring match, not exact string
   equality, since compositional notation varies:
   - Match on substring `"Li7La3Zr2O12"`, `"LLZO"`, or regex for
     Li-La-Zr-O stoichiometric variants (e.g. `Li7-xLa3Zr2-xTaxO12`-style
     doped variants — match on presence of Li, La, Zr, O elements plus
     "garnet" keyword in target compound name/role field if present).
   - Log every matched paper's `doi`/`title` + matched target string to
     `analysis/llzo_match_log.csv` for manual spot-check — do not silently
     trust the regex.

2. **Extract sintering temperature.** From `synthesis.steps[].operations[]`
   where `operation type` indicates sintering/calcination (match on
   operation name containing "sinter" or "calcin", case-insensitive). Pull
   `parameters.temperature` (already normalized to Kelvin per the schema's
   units policy — Section 2.2). If multiple sintering steps exist in one
   paper, take the maximum temperature (final densification step is
   typically the relevant one) and note ambiguity in the log.

3. **Extract ionic conductivity.** From `characterization[]` entries where
   `method` is EIS / "Electrochemical Impedance Spectroscopy" /
   "impedance spectroscopy" (these appear as separate un-normalized
   strings per the paper's own Limitation 6.4 — the agent must merge these
   method-name variants, not treat them as distinct methods). Pull the
   conductivity value from `results[]` — units may vary (S/cm, mS/cm);
   normalize to S/cm before comparison. If the schema/notes field doesn't
   preserve unit info clearly, flag the record as unusable rather than
   guessing.

4. **Join** on paper_id: one row per paper with
   `(sintering_temp_K, ionic_conductivity_S_cm, doi, title)`. Expect a
   small final n (likely 15–40 papers) — this is fine, it's a spot-check,
   not a full statistical study.

5. **Plot + correlate.**
   - Scatter plot, x = sintering temperature (K), y = log10(ionic
     conductivity), color/annotate by paper.
   - Report Pearson r and Spearman ρ (Spearman is more appropriate given
     likely non-linear/plateau behavior at high temperature — do not
     over-interpret a single linear r).
   - Save plot to `analysis/figures/llzo_sintering_vs_conductivity.png`
     and stats to `analysis/downstream_validation_stats.json`.

6. **Do not claim causality or overreach.** The write-up (done by Vinh, not
   the agent) should frame this as "extracted values reproduce the
   qualitative direction reported in prior literature for this system,"
   citing 1–2 known review sources for the expected trend — the agent
   should just produce the numbers/plot; interpretation stays with the
   authors.

### Acceptance check

- Report exact match count at each filtering stage (papers matched by
  compound name → papers with a sintering step → papers with valid EIS
  conductivity value → final joined n). This funnel must be logged, not
  just the final n, so the authors can sanity-check how much data was
  dropped and why.

---

## C. Test–retest blinded re-review tooling

### Goal

Support intra-annotator reliability check: same human reviewer re-labels a
subsample of entities weeks later, blind to their original labels. The
agent builds the export/import/scoring tooling only — it does not perform
the re-review itself.

### Location

New scripts: `evaluation/testretest_export.py`, `evaluation/testretest_score.py`

### `testretest_export.py`

1. From the 30-paper golden dataset, stratified-sample ~10–15% of entities
   across all three complexity tiers (proportional to tier size: roughly
   16 simple, 31 moderate, 36 complex → adjust to hit ~100 total entities).
2. Export a **blinded CSV** for re-review:
   `entity_id (opaque, not the original database id), paper_title, entity_type, extracted_value, source_context_snippet`
   — deliberately omit the original human label and the original
   entity database ID, replacing it with a random opaque ID. Keep a
   separate `evaluation/testretest_id_map.csv` (original_id ↔ opaque_id)
   that is NOT given to the reviewer.
3. Shuffle row order (do not preserve paper grouping) so the reviewer
   can't infer context from adjacency to their memory of the first pass.

### `testretest_score.py`

1. Takes the reviewer's completed re-review CSV (same opaque IDs, new
   label column added) plus the hidden id map plus the original labels.
2. Joins back via `testretest_id_map.csv`, computes:
   - Raw percent agreement (pass 1 vs. pass 2 label match)
   - Cohen's κ (4-class: correct/incorrect/partially correct/missing)
3. Outputs `evaluation/testretest_reliability.json` and a short markdown
   summary suitable for a Limitations-section citation.

### Acceptance check

- Verify the opaque ID mapping never leaks into the reviewer-facing CSV
  (grep the export file for any original entity ID string before
  finalizing).
- `testretest_score.py` must refuse to run (raise, not silently skip) if
  the re-review CSV has a different row count than the export, to catch
  accidental row drops during the reviewer's editing.

---

## D. Codebook → Supporting Information (not agent work)

Not a coding task — Vinh should write this directly as a markdown/Word doc:
formal decision tree for the 4 labels (correct / incorrect / partially
correct / missing data), with 2–3 concrete worked examples per label drawn
from the existing 95 logged errors (Section 4.6 / Figure 7 data already
has the error categories — pull real examples from there rather than
inventing new ones). Flag this as a follow-up doc task, not something to
hand to the coding agent.

---

## Suggested execution order for the agent

1. Confirm actual repo paths (read-only scan, report back before writing code).
2. Task A (bootstrap CI) — self-contained, fastest to validate correctness.
3. Task B (downstream validation) — log the filtering funnel explicitly.
4. Task C (test-retest tooling) — build and hand off export CSV to Vinh for
   the actual human re-review step.