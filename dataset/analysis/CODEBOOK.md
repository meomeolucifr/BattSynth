# BattSynth Annotation Codebook

## 1. Overview

This codebook documents the criteria applied when a domain-expert reviewer assigned one of four labels to each of the 828 entities in the BattSynth golden dataset (Section 3.2 of the main text). It was reconstructed from the review's own worked examples rather than written from a theoretical rulebook, so the boundary rules below describe how the labels were actually used in practice. This document also serves as the reference standard for the test–retest reliability check reported in the main text's Limitations section.

## 2. Label definitions

### `correct`

The entity matches the source paper in name, value, and context.

**Boundary rule:** a paraphrased or abbreviated entity name counts as `correct` if it unambiguously refers to the same real-world entity as the source text. For example, an entity extracted as "lithium hexafluorophosphate" was marked `correct` against a source paper that wrote only "1 M LiPF6" — the full chemical name and the standard abbreviation refer to the same compound, so the mismatch in surface form does not by itself make the entity incorrect.

### `incorrect`

The entity contains a factual error: a wrong value, a fabricated name, or a misattributed property. Every `incorrect` entity is further classified into one of five error subtypes (matching the taxonomy in Section 4.6 of the main text):

- **`hallucination`** — the extracted entity or value does not appear anywhere in the source text, in any form. Example: an electrolyte solvent was extracted as "ethylene carbonate" when the source paper's Methods section specifies a different solvent entirely ("1 M LiPF6 in ethyl carbonate (EC): diethyl carbonate (DEC)") — the extracted name does not match what the paper actually reports. Another example: a synthesis step was extracted with the operation `add`, when the paper's methods describe the relevant step only as reagents being "pumped into the reactor" and powders being "mixed" and "calcined" — the model introduced an operation verb that has no basis in the source text.
- **`wrong_amount`** — a numeric quantity is present in the source but the extracted value differs from it in a way that is not attributable to rounding or unit conversion. Example: a target compound was extracted as "2.5h-milled graphite," but the paper's actual starting-material composition is a graphite/h-BN mixture at a stated 1:8 weight ratio — the extracted description does not reflect the actual composition reported.
- **`semantic_mismatch`** — a value that is correct in isolation is attached to the wrong entity, step, or context. Example: a synthesis step was extracted with the action `contact` at a specific temperature and duration, but the paper's actual "contact with molten Li" step is a distinct triggering event in the procedure from the one the extracted temperature/duration values actually belong to — the values are real, but attached to the wrong step.
- **`other`** — miscellaneous extraction errors that don't fit the categories above: misattributed cross-references, formatting issues, or a field left incompletely populated despite the source supporting a fuller answer. This is the largest error category (68.4% of all logged errors) and covers cases such as a chemical amount being left as an unresolved placeholder despite the source giving an explicit molar ratio, or a characterization method being marked incorrect because an associated field (e.g., its stated purpose or the specific result it supports) does not match what the source describes, even though the method name itself is right.
- **`unspecified`** — an error was identified but did not clearly fit the four categories above.

### `partially correct`

The entity captures the correct underlying concept, but with an incompleteness or imprecision that falls short of `correct`.

**Boundary rule, based on observed practice:** in the reviewed cases, `partially correct` was applied predominantly to **incomplete parameter capture** rather than to numeric rounding. Common patterns include: a synthesis step correctly identifies that an addition-type operation occurred, but the specific reagent-addition detail described in the source (e.g., "slowly adding dilute hydrochloric acid") is reduced to a generic `add` action; or a step's action is correctly identified but its duration field is left `null` when the source at least implies a duration, even if it isn't stated as a precise number. In other words, this label is generally used when the extraction gets the *type* of information right but drops or approximates specific *parameters* attached to it, rather than for cases where a specific number was extracted and only rounded within some numeric tolerance. If a genuine numeric-rounding case is identified in the dataset later, it should also fall under this label, but the tolerance for "acceptable rounding" was not formalized as a fixed percentage during the original review, and this codebook does not assert one.

### `missing data`

An entity that the schema requests, and that is present in the source paper, is entirely absent from the extraction — as opposed to an entity the schema doesn't request at all (which is out of scope, not `missing data`).

**Boundary rule:** this label applies even when a *related* entity was captured but a specific sub-field of it was left empty despite the source clearly supporting a value. Example: a target compound's overall identity was captured (e.g., "rGO/LiI composite cathode"), but its molecular formula field was left empty even though the source explicitly and repeatedly identifies LiI as the active material — the compound-level entity exists in the extraction, but a specific required piece of information about it is missing. Another example: a characterization method's `purpose` field was left blank even though the surrounding text clearly describes what the measurement was used to show.

## 3. Decision tree

```
1. Does the source paper contain this entity/value, in any form, anywhere?
   NO  -> is this a field the schema requires for this record?
          YES -> MISSING DATA
          NO  -> out of scope, does not get a label
   YES -> continue to 2

2. Does the extracted entity correctly identify WHAT it refers to
   (the right compound / operation / method / step)?
   NO (wrong identity, or no basis at all in the source text) -> INCORRECT (hallucination)
   YES -> continue to 3

3. Are the specific value(s) attached to that entity (amount, temperature,
   duration, formula, purpose, etc.) accurate and attached to the right context?
   Fully accurate and correctly attached -> CORRECT
   Right entity, but with incomplete/approximated parameters
     (e.g., a generic action standing in for a more specific one,
     a duration left null when the source implies one) -> PARTIALLY CORRECT
   Wrong numeric value (not attributable to rounding) -> INCORRECT (wrong_amount)
   Correct value, but attached to the wrong entity/step/context -> INCORRECT (semantic_mismatch)
   Some other mismatch not covered above -> INCORRECT (other, or unspecified)
```

## 4. Worked examples

The examples below are drawn directly from the 828-entity review. Paper identities are given as first-author/year, consistent with how the main text cites examples.

**Correct**
- Kim et al. (2017): a chemical entity extracted as "lithium hexafluorophosphate," matching the source's "1 M LiPF6" in its electrolyte description.
- Li and Monroe (2019): the exemplary garnet-oxide compound extracted as Li7La3Zr2O12 (LLZO), matching the source's explicit statement of this compound.

**Incorrect — hallucination**
- Chen et al.: electrolyte solvent extracted as "ethylene carbonate," when the source specifies "ethyl carbonate (EC)" in a different solvent combination — the extracted name does not match the source.
- Liu et al. (2021): a synthesis step extracted with action `add`, when the source only describes reagents being "pumped" and powders being "mixed" and "calcined" — no basis for an `add` operation in the text.

**Incorrect — wrong_amount**
- Kim et al. (2017): a target extracted as "2.5h-milled graphite," when the source's actual starting-material ratio is graphite:h-BN at 1:8 by weight — the extracted description does not reflect the reported composition.

**Incorrect — semantic_mismatch**
- Lin et al. (2016): a synthesis step extracted with action `contact` at a specific temperature/duration, where the source's "contact with molten Li" step is a distinct triggering event from the one those specific parameter values actually belong to.

**Incorrect — other**
- Han et al. (2015): a chemical amount for phosphorus pentasulfide left as an unresolved placeholder, despite the source giving an explicit molar ratio for it.
- Trease et al. (2016): a characterization method (Synchrotron X-ray Powder Diffraction) marked incorrect because an associated field did not match the source's description of the joint refinement, despite the method name itself being correct.

**Partially correct**
- Wang et al. (2014): a synthesis step correctly identified as an addition-type operation, but reduced to the generic action `add` when the source describes a more specific procedure ("slowly adding dilute hydrochloric acid").
- Rana et al. (2020): a synthesis step's action and temperature (298 K) correctly captured, but its duration field left `null` when the source's description implies a duration was involved.

**Missing data**
- Kim et al. (2017): a target compound's overall identity captured (rGO/LiI composite cathode), but the molecular formula field left empty despite the source explicitly and repeatedly identifying LiI as the active material.
- Lamsayah et al. (2016): a target compound's formula field left empty despite the source giving explicit molecular formulas for the relevant ligands.
- Kim et al. (2017): an SEM characterization entry with its `purpose` field left blank despite the surrounding text describing what the imaging was used to show.

## 5. Note on scope

This codebook was reconstructed from the criteria actually applied during the original 828-entity review, based on real worked examples, for transparency and reproducibility. It also serves as the reference standard for the test–retest reliability analysis reported in the main text. It does not itself constitute independent inter-annotator validation, which remains a direction for future work. Where this document's boundary rules could not be anchored to a real example from the review (for instance, no genuine numeric-rounding case was identified for the `partially correct` label), that gap is stated explicitly above rather than filled with an invented rule.
