# Extract Real Worked Examples for Annotation Codebook

## Goal

Pull 2–3 real worked examples per label/error-category from the existing
828-entity human review data, formatted for direct use in a codebook
document. Do not invent examples.

## No-touch

Do not modify the original human review JSON files. This is a read-only
extraction.

## Input

The per-entity review data used to produce Table 2/Figure 7 in the paper
— locate the file(s) under `dataset/human_reviews/*/*.json` (confirm
actual path first if it has moved).

## What to pull

For each of the following 7 buckets, find 2–3 real entities and extract:
`paper title/id, entity type, extracted value (as it appears in the JSON),
source context snippet (if available), assigned label, error category (if
incorrect)`.

1. `correct` — 2 examples (any entity type, to show the baseline case)
2. `incorrect` → `hallucination` subtype — 2–3 examples (21 logged
   instances total per the paper's Section 4.6 — pick clear ones)
3. `incorrect` → `wrong amount` subtype — only 1 logged instance exists
   in the whole dataset per Section 4.6. Pull it if present. If not
   found, report that clearly rather than substituting a different
   category's example.
4. `incorrect` → `semantic mismatch` subtype — same as above, only 1
   logged instance exists. Pull if present.
5. `incorrect` → `other` subtype — 2–3 examples (largest bucket, 65
   instances / 68.4% of errors — pick ones that are clearly
   representative, e.g. misattributed cross-reference, formatting
   mismatch)
6. `partially correct` — 2–3 examples, ideally including at least one
   rounded/truncated-value case
7. `missing data` — 2–3 examples

## Output

`dataset/analysis/codebook_worked_examples.json`, structured as a flat
list of objects with the fields above, grouped by bucket. Keep
`source_context_snippet` short (1–2 sentences) — this goes into a
supplementary document, not a full reproduction of paper text.

## Acceptance check

- Report the actual count found for buckets 3 and 4 (`wrong amount`,
  `semantic mismatch`) explicitly — if either bucket has zero matches,
  say so plainly instead of silently omitting the bucket from the output.
- Every example must trace back to a real entity in the review data —
  include enough identifying info (paper title, entity type) that it can
  be manually spot-checked against the source JSON.