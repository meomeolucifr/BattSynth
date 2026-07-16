"""
apply_review_corrections.py
============================
Applies human review corrections back to the extraction JSONs.

For each entity reviewed in the Human_Review_*.json files:
  - correct:            no change needed
  - missing_data:       fill in empty fields using llm_suggested_fix or correction
  - incorrect:          apply correction/llm_suggested_fix, or flag the entity
  - partially_correct:  apply correction/llm_suggested_fix if available

The corrected JSONs are written to:
    dataset/extraction_jsons_corrected/{tier}/

The original JSONs remain untouched. A summary report is printed.

Usage:
    python scripts/apply_review_corrections.py
"""

import json
import os
import sys
import re
import shutil
from pathlib import Path
from collections import Counter, defaultdict
from copy import deepcopy

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = Path(r"C:\Users\12124\Downloads\Results_final\Results_final\dataset")
REV_DIR = BASE / "human_reviews"
EXT_DIR = BASE / "extraction_jsons"
OUT_DIR = BASE / "extraction_jsons_corrected"
TIERS = ["simple", "moderate", "complex"]

# ── Path navigation ──────────────────────────────────────────────────────────

def navigate_to(data, path):
    """
    Navigate a dotted+indexed path like 'synthesis.steps[0].operations[1]'
    Returns (parent_obj, key) so caller can read or write the value.
    """
    parts = re.split(r'\.(?![^\[]*\])', path)
    obj = data
    for i, part in enumerate(parts):
        # Check for array index
        m = re.match(r'(\w+)\[(\d+)\]', part)
        if m:
            key, idx = m.group(1), int(m.group(2))
            if key not in obj or not isinstance(obj[key], list):
                return None, None
            if idx >= len(obj[key]):
                return None, None
            if i == len(parts) - 1:
                return obj[key], idx
            obj = obj[key][idx]
        else:
            if not isinstance(obj, dict) or part not in obj:
                return None, None
            if i == len(parts) - 1:
                return obj, part
            obj = obj[part]
    return None, None


def get_entity(data, path):
    """Get the entity object at the given path."""
    parent, key = navigate_to(data, path)
    if parent is None:
        return None
    return parent[key]


def set_entity(data, path, value):
    """Set the entity at the given path."""
    parent, key = navigate_to(data, path)
    if parent is None:
        return False
    parent[key] = value
    return True


# ── Correction parsers ────────────────────────────────────────────────────────

def parse_target_fix(entity, fix_text):
    """
    Parse a target fix like:
      'LiAlxMn2−xO4 (Al-doped spinel lithium manganese oxide; x varied ~0–0.12)'
    into molecular_formula update.
    """
    if not fix_text:
        return entity

    modified = deepcopy(entity)

    # If the fix text is instructional (starts with "If", "Specify", "Use", etc.)
    # then it doesn't contain a clean formula — try to extract one
    is_instructional = fix_text.strip().startswith(("If ", "Specify ", "Use ", "Include "))

    if is_instructional:
        # Try to extract a formula from the instructional text
        # Look for chemical formula patterns: Li2SO4, LiAlxMn2-xO4, Na3V2(PO4)3, etc.
        formula_patterns = re.findall(
            r'[A-Z][a-z]?\d*(?:[A-Z][a-z]?\d*)*(?:\([A-Z][a-z]?\d*(?:[A-Z][a-z]?\d*)*\)\d*)*',
            fix_text
        )
        # Filter for actual formulas (at least 2 elements)
        formulas = [f for f in formula_patterns if len(f) > 3 and re.search(r'[A-Z].*[a-z]', f)]
        if formulas:
            formula = formulas[0]
        else:
            # For organic compounds, the compound_name IS effectively the formula
            # Use compound_name as the formula if available
            compound_name = modified.get("compound_name", "")
            if compound_name:
                modified["molecular_formula"] = compound_name
                return modified
            return entity  # Can't parse, skip
    else:
        formula = fix_text.strip()
        # If there's a parenthetical note, extract just the formula part
        if '(' in formula:
            # But check if parens are part of the formula (e.g., Na3V2(PO4)3)
            # Chemical formulas have parens followed by a digit
            parts = re.split(r'\s*\((?![A-Z])', formula, maxsplit=1)
            formula_part = parts[0].strip()
            if formula_part:
                formula = formula_part

        # Clean common artifacts
        formula = formula.rstrip(' |,;.')

    if modified.get("molecular_formula", "") == "" or modified.get("molecular_formula") is None:
        modified["molecular_formula"] = formula
    return modified


def parse_chemical_fix(entity, fix_text):
    """Parse a chemical fix — usually about formula or amount."""
    if not fix_text:
        return entity

    modified = deepcopy(entity)
    fix_lower = fix_text.lower()

    # If the fix mentions a formula and the entity has an empty formula
    if modified.get("molecular_formula", "") in ("", None):
        # Try to extract formula from fix text
        # Look for patterns like "formula: X" or just the first chemical-looking string
        formula_match = re.search(r'formula[:\s]+([A-Z][A-Za-z0-9()·\-]+)', fix_text)
        if formula_match:
            modified["molecular_formula"] = formula_match.group(1)

    # If the fix mentions amount info
    if "amount" in fix_lower or "stoichiometric" in fix_lower:
        # Update notes with amount info
        if not modified.get("notes"):
            modified["notes"] = fix_text[:200]
        elif len(modified["notes"]) < 10:
            modified["notes"] = fix_text[:200]

    return modified


def parse_operation_fix(entity, fix_text, correction_text=""):
    """Parse an operation fix — usually about the action name."""
    if not fix_text and not correction_text:
        return entity

    modified = deepcopy(entity)

    # If there's a direct correction for the action
    if correction_text:
        correction_clean = correction_text.strip().lower().replace(" ", "_")
        if len(correction_clean) < 30:  # reasonable action name
            modified["action"] = correction_clean
            return modified

    # Try to parse fix text for an action
    if fix_text:
        # Look for quoted action words
        action_match = re.search(r'"(\w+)"', fix_text)
        if action_match:
            modified["action"] = action_match.group(1).lower()
        elif '(' in fix_text:
            # e.g., "co-precipitation (method)"
            action = fix_text.split('(')[0].strip().lower().replace(" ", "_")
            if len(action) < 30:
                modified["action"] = action

    return modified


def parse_characterization_fix(entity, fix_text):
    """Parse a characterization fix — usually about filling purpose/results."""
    if not fix_text:
        return entity

    modified = deepcopy(entity)

    # Most characterization missing_data is about empty "purpose" or "results" fields
    # The fix text from LLM is often instructional — extract key info
    is_instructional = fix_text.strip().startswith(("Include ", "Indicate ", "Add ", "Specify "))

    if modified.get("results", None) in ([], None, [""]):
        # Try to extract key results from the fix text
        # Look for quoted findings or key phrases
        results_text = fix_text
        if is_instructional:
            # Extract the actual content after the instruction
            results_text = re.sub(r'^(Include|Indicate|Add|Specify)\s+\w+\s+', '', fix_text, flags=re.IGNORECASE)
        modified["results"] = [results_text[:250]]

    if modified.get("interpretation", "") in ("", None):
        if not is_instructional:
            modified["interpretation"] = fix_text[:250]

    return modified


def parse_final_outcome_fix(entity, path, fix_text):
    """Parse a final_outcome fix."""
    if not fix_text:
        return entity

    modified = deepcopy(entity)

    # For final_outcomes.capacity, .yield, .cycle_life
    # Try to extract numeric value
    num_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:mAh|%|cycles?)', fix_text)
    if num_match and isinstance(modified, dict) and "value" in modified:
        try:
            modified["value"] = float(num_match.group(1))
        except ValueError:
            pass

    return modified


# ── Main correction logic ─────────────────────────────────────────────────────

def apply_corrections():
    print("=" * 66)
    print("  Applying Human Review Corrections to Extraction JSONs")
    print("=" * 66)

    stats = Counter()
    changes_log = []

    for tier in TIERS:
        tier_rev_dir = REV_DIR / tier
        tier_out_dir = OUT_DIR / tier
        tier_out_dir.mkdir(parents=True, exist_ok=True)

        if not tier_rev_dir.exists():
            continue

        for review_file in sorted(tier_rev_dir.glob("Human_Review_*.json")):
            with open(review_file, "r", encoding="utf-8") as f:
                review = json.load(f)

            paper_id = review.get("paper_id", "")
            ext_filename = review.get("extraction_json_filename", "")

            # Find the extraction JSON
            # Check in tier subfolder first, then root
            ext_path = EXT_DIR / tier / ext_filename
            if not ext_path.exists():
                ext_path = EXT_DIR / ext_filename
            if not ext_path.exists():
                print(f"  [SKIP] {ext_filename} — not found")
                stats["skipped"] += 1
                continue

            with open(ext_path, "r", encoding="utf-8") as f:
                ext_data = json.load(f)

            # Handle list-wrapped extractions
            is_list = isinstance(ext_data, list)
            if is_list:
                working = deepcopy(ext_data[0]) if ext_data else {}
            else:
                working = deepcopy(ext_data)

            paper_changes = 0

            for entity_review in review.get("entity_reviews", []):
                verdict = entity_review.get("human_verdict", "")
                path = entity_review.get("entity_path", "")
                correction = entity_review.get("correction", "").strip()
                llm_fix = entity_review.get("llm_suggested_fix", "").strip()
                error_cat = entity_review.get("error_category", "")

                # Skip correct entities
                if verdict == "correct":
                    stats["correct_skipped"] += 1
                    continue

                # Get the fix text (prefer human correction, fall back to llm)
                fix_text = correction if correction else llm_fix

                if not fix_text:
                    stats["no_fix_available"] += 1
                    continue

                # Navigate to entity
                entity = get_entity(working, path)
                if entity is None:
                    stats["path_not_found"] += 1
                    continue

                # Apply type-specific fixes
                new_entity = None
                if path.startswith("targets"):
                    new_entity = parse_target_fix(entity, fix_text)
                elif path.startswith("chemicals"):
                    new_entity = parse_chemical_fix(entity, fix_text)
                elif "operations[" in path:
                    new_entity = parse_operation_fix(entity, fix_text, correction)
                elif path.startswith("characterization"):
                    new_entity = parse_characterization_fix(entity, fix_text)
                elif path.startswith("final_outcomes"):
                    new_entity = parse_final_outcome_fix(entity, path, fix_text)
                elif path.startswith("synthesis.steps") and "operations" not in path:
                    # Step description — usually correct, skip
                    stats["step_desc_skipped"] += 1
                    continue

                if new_entity is not None and new_entity != entity:
                    if set_entity(working, path, new_entity):
                        paper_changes += 1
                        stats["applied"] += 1
                        changes_log.append({
                            "paper": paper_id[:50],
                            "tier": tier,
                            "path": path,
                            "verdict": verdict,
                            "change_type": "correction" if correction else "llm_fix",
                        })
                    else:
                        stats["set_failed"] += 1
                else:
                    stats["no_change_needed"] += 1

            # Write corrected JSON
            output = [working] if is_list else working
            out_path = tier_out_dir / ext_filename
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(output, f, indent=2, ensure_ascii=False)

            # Also write to the main extraction_jsons folder (overwrite original)
            original_path = EXT_DIR / ext_filename
            if original_path.exists():
                # Backup original
                backup_dir = EXT_DIR / "backup"
                backup_dir.mkdir(exist_ok=True)
                backup_path = backup_dir / ext_filename
                if not backup_path.exists():
                    shutil.copy2(original_path, backup_path)
                # Write corrected
                with open(original_path, "w", encoding="utf-8") as f:
                    json.dump(output, f, indent=2, ensure_ascii=False)

            # Also handle tier subfolder if it exists
            tier_original = EXT_DIR / tier / ext_filename
            if tier_original.exists():
                tier_backup = EXT_DIR / tier / "backup"
                tier_backup.mkdir(exist_ok=True)
                if not (tier_backup / ext_filename).exists():
                    shutil.copy2(tier_original, tier_backup / ext_filename)
                with open(tier_original, "w", encoding="utf-8") as f:
                    json.dump(output, f, indent=2, ensure_ascii=False)

            status = f"{paper_changes} corrections" if paper_changes > 0 else "no changes"
            print(f"  [{tier.upper()[:3]}] {paper_id[:50]:<50s} {status}")
            stats["papers_processed"] += 1

    # ── Summary ──
    print(f"\n{'='*66}")
    print(f"  CORRECTION SUMMARY")
    print(f"{'='*66}")
    print(f"  Papers processed:    {stats['papers_processed']}")
    print(f"  Corrections applied: {stats['applied']}")
    print(f"  Correct (no change): {stats['correct_skipped']}")
    print(f"  No fix available:    {stats['no_fix_available']}")
    print(f"  No change needed:    {stats['no_change_needed']}")
    print(f"  Path not found:      {stats['path_not_found']}")
    print(f"  Skipped (not found): {stats.get('skipped', 0)}")
    print(f"  Set failed:          {stats.get('set_failed', 0)}")
    print(f"  Step desc skipped:   {stats.get('step_desc_skipped', 0)}")
    print()

    # Show changes by type
    if changes_log:
        by_type = Counter()
        by_verdict = Counter()
        for c in changes_log:
            path = c["path"]
            if path.startswith("targets"):
                by_type["target"] += 1
            elif path.startswith("chemicals"):
                by_type["chemical"] += 1
            elif "operations" in path:
                by_type["operation"] += 1
            elif path.startswith("characterization"):
                by_type["characterization"] += 1
            elif path.startswith("final_outcomes"):
                by_type["final_outcome"] += 1
            else:
                by_type["other"] += 1
            by_verdict[c["verdict"]] += 1

        print(f"  Changes by entity type:")
        for t, c in by_type.most_common():
            print(f"    {t:<20s} {c:>4d}")
        print(f"\n  Changes by verdict:")
        for v, c in by_verdict.most_common():
            print(f"    {v:<20s} {c:>4d}")
        print(f"\n  Changes by source:")
        src_counts = Counter(c["change_type"] for c in changes_log)
        for s, c in src_counts.most_common():
            print(f"    {s:<20s} {c:>4d}")

    print(f"\n  Corrected JSONs saved to:")
    print(f"    {OUT_DIR}/")
    print(f"    {EXT_DIR}/ (originals backed up to backup/)")
    print(f"{'='*66}")

    # Save change log
    log_path = OUT_DIR / "correction_log.json"
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump({
            "stats": dict(stats),
            "changes": changes_log,
        }, f, indent=2, ensure_ascii=False)
    print(f"\n  Change log: {log_path}")


if __name__ == "__main__":
    apply_corrections()
