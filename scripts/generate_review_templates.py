"""
generate_review_templates.py
============================
Pre-populates human_review_template.json for all 30 golden dataset papers.
Creates one ready-to-fill review file per paper in dataset/human_reviews/

Each template is pre-filled with:
  - Paper metadata (title, journal, year, tier, score)
  - All targets, chemicals, synthesis steps, and characterization entries
    extracted from the JSON (so you only need to fill in human_verdict)
  - Summary counters auto-calculated

Usage:
    python scripts/generate_review_templates.py
"""

import json
import csv
import shutil
from pathlib import Path
from datetime import date

BASE_DIR = Path(r"C:\Users\12124\Downloads\Results_final\Results_final")
CSV_PATH  = BASE_DIR / "dataset" / "golden_dataset_selection.csv"
JSON_DIR  = BASE_DIR / "dataset" / "extraction_jsons"
OUT_DIR   = BASE_DIR / "dataset" / "human_reviews"

# ── helpers ─────────────────────────────────────────────────────────────────

BLANK_ENTITY = {
    "entity_path"    : "",
    "entity_id"      : "",
    "extracted_value": "",
    "llm_verdict"    : "N/A (no Verified_ file — review directly from PDF)",
    "llm_confidence" : None,
    # ← YOU FILL THESE IN:
    "human_verdict"  : "",          # correct | incorrect | partially_correct | missing_data
    "human_notes"    : "",          # brief explanation
    "correction"     : "",          # if incorrect, what should it be?
    "page_reference" : "",          # e.g. "Page 3, Table 1"
    "agrees_with_llm": None,
    "error_category" : ""           # null | hallucination | missing_formula | wrong_amount |
                                    # term_normalization | provenance_error | semantic_mismatch | other
}

def make_entity(path: str, eid: str, value) -> dict:
    e = dict(BLANK_ENTITY)
    e["entity_path"]     = path
    e["entity_id"]       = eid
    e["extracted_value"] = value
    return e


def val_summary(obj) -> str:
    """Return a human-readable short string for a value."""
    if obj is None:
        return "null"
    if isinstance(obj, (str, int, float, bool)):
        return str(obj)
    if isinstance(obj, list):
        return f"[{len(obj)} items]"
    if isinstance(obj, dict):
        # pick the most informative field
        for key in ("compound_name", "name", "value", "action", "description", "formula"):
            if key in obj and obj[key]:
                return str(obj[key])
        return "{...}"
    return str(obj)


def extract_entities(data: dict) -> list:
    """Walk the extraction JSON and collect the key reviewable entities."""
    entities = []

    # --- targets ---
    for i, t in enumerate(data.get("targets", [])):
        entities.append(make_entity(
            f"targets[{i}]",
            t.get("target_id", f"target_{i}"),
            f"compound={t.get('compound_name','')}  formula={t.get('molecular_formula','')}  role={t.get('intended_role','')}"
        ))

    # --- chemicals ---
    for i, c in enumerate(data.get("chemicals", [])):
        entities.append(make_entity(
            f"chemicals[{i}]",
            c.get("chem_id", f"chem_{i}"),
            f"name={c.get('name','')}  formula={c.get('formula','')}  role={c.get('role','')}  amount={val_summary(c.get('amount'))}"
        ))

    # --- synthesis steps & operations ---
    synthesis = data.get("synthesis", {})
    steps = synthesis.get("steps", []) if isinstance(synthesis, dict) else []
    for si, step in enumerate(steps):
        # step-level description
        entities.append(make_entity(
            f"synthesis.steps[{si}]",
            step.get("step_id", f"step_{si}"),
            f"description={step.get('description','')}"
        ))
        # individual operations
        for oi, op in enumerate(step.get("operations", [])):
            entities.append(make_entity(
                f"synthesis.steps[{si}].operations[{oi}]",
                f"{step.get('step_id','step')}_op{oi}",
                f"action={op.get('action','')}  T={val_summary(op.get('temperature'))}  t={val_summary(op.get('duration'))}"
            ))

    # --- characterization ---
    for i, ch in enumerate(data.get("characterization", [])):
        entities.append(make_entity(
            f"characterization[{i}]",
            ch.get("char_id", f"char_{i}"),
            f"method={ch.get('method','')}  purpose={ch.get('purpose','')}"
        ))

    # --- final_outcomes (spot-check) ---
    outcomes = data.get("final_outcomes", {})
    if isinstance(outcomes, dict):
        for k, v in outcomes.items():
            if v:
                entities.append(make_entity(
                    f"final_outcomes.{k}",
                    k,
                    val_summary(v)
                ))

    return entities


# ── main ────────────────────────────────────────────────────────────────────

def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    # tier subfolders
    for tier in ["simple", "moderate", "complex"]:
        (OUT_DIR / tier).mkdir(exist_ok=True)

    with open(CSV_PATH, "r", encoding="utf-8") as f:
        papers = list(csv.DictReader(f))

    print(f"Generating pre-populated review templates for {len(papers)} papers...\n")
    total_entities = 0

    for paper in papers:
        tier        = paper["tier"]
        json_fname  = paper["filename"]
        title       = paper["title"]
        journal     = paper["journal"]
        year        = paper["year"]
        score       = paper["score"]
        doi         = paper.get("doi", "")
        pdf_fname   = json_fname.replace("_reactions.json", ".pdf")

        json_path = JSON_DIR / tier / json_fname
        if not json_path.exists():
            print(f"  [WARN] JSON not found: {json_path}")
            continue

        with open(json_path, "r", encoding="utf-8") as f:
            extraction = json.load(f)

        entities = extract_entities(extraction)
        total_entities += len(entities)

        # build the review document
        review = {
            "_instructions": {
                "purpose": (
                    "Fill in human_verdict for each entity below. "
                    "Compare the extracted_value against the source PDF. "
                    "Focus on any values that look suspicious or surprising."
                ),
                "human_verdict_choices": [
                    "correct           — value matches the PDF exactly",
                    "incorrect         — value is wrong (fill in 'correction')",
                    "partially_correct — partially right but incomplete/imprecise",
                    "missing_data      — field should have a value but is null/empty"
                ],
                "error_category_choices": [
                    "null              — no error",
                    "hallucination     — value not in the paper at all",
                    "missing_formula   — formula missing or wrong",
                    "wrong_amount      — numerical value or unit is wrong",
                    "term_normalization— naming/synonym issue",
                    "provenance_error  — wrong page/table/figure citation",
                    "semantic_mismatch — meaning is off",
                    "other             — anything else"
                ],
                "workflow": [
                    "STEP 1: Open the PDF:  dataset/pdfs/" + tier + "/" + pdf_fname,
                    "STEP 2: Open this file in a text editor (VS Code recommended)",
                    "STEP 3: Work through entity_reviews top-to-bottom",
                    "STEP 4: For each entity: set human_verdict + page_reference at minimum",
                    "STEP 5: If incorrect: fill in correction + error_category",
                    "STEP 6: Add missed_errors entries for errors the extractor missed entirely",
                    "STEP 7: Add missing_extractions for important info not extracted at all",
                    "STEP 8: Fill in the summary section at the bottom",
                    "STEP 9: Save as-is (filename already set correctly)"
                ]
            },
            "paper_id"             : json_fname.replace("_reactions.json", ""),
            "reviewer_name"        : "",           # ← fill in your name
            "review_date"          : str(date.today()),
            "review_start_time"    : "",           # ← e.g. "14:00"
            "review_end_time"      : "",           # ← e.g. "14:45"
            "source_pdf_filename"  : pdf_fname,
            "extraction_json_filename": json_fname,
            "tier"                 : tier,
            "score_percent"        : float(score),
            "title"                : title,
            "journal"              : journal,
            "year"                 : year,
            "doi"                  : doi,

            "entity_reviews": entities,

            "missed_errors": [
                {
                    "_comment"     : "Errors NOT caught by the extractor (values that are simply wrong but look plausible)",
                    "entity_path"  : "",          # e.g. chemicals[2].amount
                    "entity_id"    : "",
                    "issue"        : "",          # what is wrong
                    "correct_value": "",          # what it should be
                    "page_reference": ""          # where you found the evidence
                }
            ],

            "missing_extractions": [
                {
                    "_comment"      : "Important information in the PDF that was NOT extracted at all",
                    "what_is_missing": "",        # e.g. 'sintering temperature 800C not captured'
                    "page_reference" : "",
                    "section"        : ""         # targets|chemicals|synthesis|characterization|final_outcomes
                }
            ],

            "summary": {
                "total_entities_reviewed"   : len(entities),
                "total_llm_flags_reviewed"  : 0,   # N/A — no Verified_ file for these papers
                "agreements_with_llm"       : 0,   # N/A
                "disagreements_with_llm"    : 0,   # N/A
                "false_negatives_by_llm"    : 0,   # N/A
                "false_positives_by_llm"    : 0,   # N/A
                "correct_count"             : 0,   # ← fill after review
                "incorrect_count"           : 0,   # ← fill after review
                "partially_correct_count"   : 0,   # ← fill after review
                "missing_data_count"        : 0,   # ← fill after review
                "missed_errors_count"       : 0,   # ← fill after review
                "missing_extractions_count" : 0,   # ← fill after review
                "overall_extraction_quality": "",  # excellent|good|acceptable|poor
                "reviewer_comments"         : ""   # free text
            }
        }

        out_path = OUT_DIR / tier / f"Human_Review_{json_fname.replace('_reactions.json', '')}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(review, f, indent=2, ensure_ascii=False)

        print(f"  [{tier:8s}] {json_fname[:55]:55s}  -> {len(entities)} entities")

    print(f"\n{'='*65}")
    print(f"Done. {len(papers)} templates generated in:")
    print(f"  {OUT_DIR}")
    print(f"Total entities pre-filled: {total_entities}")
    print(f"Average entities per paper: {total_entities/len(papers):.1f}")


if __name__ == "__main__":
    main()
