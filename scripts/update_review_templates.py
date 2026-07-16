"""
update_review_templates.py
==========================
After run_verifier_golden.py has produced Verified_*.json files, this script
reads those files and merges the _llm_flag data back into the human review
templates, replacing the "N/A" placeholders with actual LLM verdicts.

Also updates the per-paper summary counters (total_llm_flags_reviewed,
agreements_with_llm counts are left for you to fill after your review).

Input:
    dataset/verified_jsons/{tier}/Verified_*_reactions.json
    dataset/human_reviews/{tier}/Human_Review_*.json

Output:
    dataset/human_reviews/{tier}/Human_Review_*.json  (updated in-place)
    Also backs up originals to human_reviews/backup/ before overwriting.

Usage:
    python scripts/update_review_templates.py
"""

import json
import re
import shutil
from pathlib import Path
from datetime import datetime

# ── Paths ─────────────────────────────────────────────────────────────────────

BASE_DIR      = Path(r"C:\Users\12124\Downloads\Results_final\Results_final")
GOLDEN_DIR    = BASE_DIR / "dataset"
VERIFIED_BASE = GOLDEN_DIR / "verified_jsons"
REVIEWS_BASE  = GOLDEN_DIR / "human_reviews"
BACKUP_DIR    = REVIEWS_BASE / "backup"

TIERS = ["simple", "moderate", "complex"]

# ── JSON path navigator ────────────────────────────────────────────────────────

def navigate(data: dict, path: str):
    """
    Navigate a dotted+indexed path like 'synthesis.steps[0].operations[1]'
    and return the object at that location (or None if not found).

    Examples:
        navigate(d, 'targets[0]')                       -> d['targets'][0]
        navigate(d, 'chemicals[2]')                     -> d['chemicals'][2]
        navigate(d, 'synthesis.steps[0]')               -> d['synthesis']['steps'][0]
        navigate(d, 'synthesis.steps[0].operations[1]') -> ...operations[1]
        navigate(d, 'characterization[0]')              -> d['characterization'][0]
        navigate(d, 'final_outcomes.yield')             -> d['final_outcomes']  (flag is on parent)
    """
    # Split on '.' but NOT inside brackets like steps[0]
    parts = re.split(r'\.(?![^\[]*\])', path)
    obj = data
    for part in parts:
        if obj is None:
            return None
        arr_match = re.match(r'^(\w+)\[(\d+)\]$', part)
        if arr_match:
            key = arr_match.group(1)
            idx = int(arr_match.group(2))
            if isinstance(obj, dict) and key in obj:
                lst = obj[key]
                if isinstance(lst, list) and idx < len(lst):
                    obj = lst[idx]
                else:
                    return None
            else:
                return None
        else:
            # Plain key
            if isinstance(obj, dict) and part in obj:
                obj = obj[part]
            else:
                return None
    return obj


def get_flag_for_path(verified_data: dict, entity_path: str):
    """
    Returns the _llm_flag dict for a given entity_path, or None.

    The verifier attaches _llm_flag to:
      targets[i]                          -> flag on targets[i]
      chemicals[i]                        -> flag on chemicals[i]
      synthesis.steps[i].operations[j]   -> flag on operations[j]
      synthesis.steps[i]                  -> NO direct flag (step descriptions
                                             not verified); return None
      characterization[i]                 -> flag on characterization[i]
      final_outcomes.*                    -> flag on final_outcomes (parent)
      workflow.*                          -> flag on the specific entry
    """
    obj = navigate(verified_data, entity_path)
    if obj and isinstance(obj, dict) and "_llm_flag" in obj:
        return obj["_llm_flag"]

    # Special case: final_outcomes sub-fields — flag is on the parent dict
    if entity_path.startswith("final_outcomes."):
        parent = navigate(verified_data, "final_outcomes")
        if parent and isinstance(parent, dict) and "_llm_flag" in parent:
            return parent["_llm_flag"]

    return None


# ── Template updater ───────────────────────────────────────────────────────────

def update_template(review_path: Path, verified_path: Path) -> dict:
    """
    Merge _llm_flag data from verified_path into the template at review_path.
    Returns a summary dict with counts.
    """
    with open(review_path, "r", encoding="utf-8") as f:
        review = json.load(f)

    with open(verified_path, "r", encoding="utf-8") as f:
        verified = json.load(f)

    stats = {
        "total_entities": len(review.get("entity_reviews", [])),
        "flags_found": 0,
        "flags_missing": 0,
        "supported": 0,
        "unsupported": 0,
    }

    for entity in review.get("entity_reviews", []):
        path = entity.get("entity_path", "")
        flag = get_flag_for_path(verified, path)

        if flag:
            stats["flags_found"] += 1
            verdict = "supported" if flag.get("is_supported", True) else "unsupported"
            entity["llm_verdict"]    = verdict
            entity["llm_confidence"] = round(float(flag.get("confidence", 0.0)), 2)
            entity["llm_reasoning"]  = flag.get("reasoning", "")
            entity["llm_suggested_fix"] = flag.get("suggested_fix", "")
            # Remove the N/A placeholder note
            if verdict == "supported":
                stats["supported"] += 1
            else:
                stats["unsupported"] += 1
        else:
            stats["flags_missing"] += 1
            # Entity path has no LLM flag — mark clearly
            entity["llm_verdict"] = "not_verified_by_llm"
            entity["llm_confidence"] = None

    # Update summary section
    summary = review.get("summary", {})
    summary["total_llm_flags_reviewed"] = stats["flags_found"]
    summary["llm_supported_count"]      = stats["supported"]
    summary["llm_unsupported_count"]    = stats["unsupported"]
    summary["llm_not_verified_count"]   = stats["flags_missing"]
    review["summary"] = summary
    review["verified_json_filename"] = verified_path.name
    review["_llm_update_timestamp"]  = datetime.now().isoformat(timespec="seconds")

    return review, stats


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    print("=" * 64)
    print("  Merging Verified_*.json flags -> human review templates")
    print("=" * 64)

    # Create backup directory
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    total_updated = 0
    total_skipped = 0
    grand_stats   = {"flags_found": 0, "supported": 0, "unsupported": 0, "flags_missing": 0}

    for tier in TIERS:
        verified_dir = VERIFIED_BASE / tier
        reviews_dir  = REVIEWS_BASE / tier

        if not verified_dir.exists():
            print(f"\n[SKIP] No verified_jsons for tier '{tier}' yet.")
            total_skipped += 1
            continue

        verified_files = {
            vf.name.replace("Verified_", "").replace("_reactions.json", ""): vf
            for vf in verified_dir.glob("Verified_*_reactions.json")
        }

        if not verified_files:
            print(f"\n[SKIP] No Verified_*.json in {verified_dir}")
            total_skipped += 1
            continue

        print(f"\n[{tier.upper()}] {len(verified_files)} verified files found")

        for review_file in sorted(reviews_dir.glob("Human_Review_*.json")):
            # Match by stripping Human_Review_ prefix (use .stem to drop .json extension)
            paper_key = review_file.stem.replace("Human_Review_", "")

            if paper_key not in verified_files:
                print(f"  [MISS ] No Verified_ match for {review_file.name}")
                total_skipped += 1
                continue

            verified_file = verified_files[paper_key]

            # Backup original
            backup_path = BACKUP_DIR / f"{tier}_{review_file.name}"
            shutil.copy2(review_file, backup_path)

            # Merge and save
            updated_review, stats = update_template(review_file, verified_file)

            with open(review_file, "w", encoding="utf-8") as f:
                json.dump(updated_review, f, indent=2, ensure_ascii=False)

            # Accumulate stats
            for k in grand_stats:
                grand_stats[k] += stats.get(k, 0)

            total_updated += 1
            flag_pct = stats['flags_found'] / max(stats['total_entities'], 1) * 100
            print(f"  [OK  ] {review_file.name[:58]}")
            print(f"         entities={stats['total_entities']}  "
                  f"llm_flags={stats['flags_found']} ({flag_pct:.0f}%)  "
                  f"unsupported={stats['unsupported']}")

    print(f"\n{'='*64}")
    print(f"  Updated  : {total_updated} templates")
    print(f"  Skipped  : {total_skipped}")
    print(f"\n  Across all updated papers:")
    print(f"    LLM flags merged    : {grand_stats['flags_found']}")
    print(f"    Supported           : {grand_stats['supported']}")
    print(f"    Unsupported (flagged): {grand_stats['unsupported']}")
    print(f"    No LLM flag         : {grand_stats['flags_missing']}")
    pct = grand_stats['unsupported'] / max(grand_stats['flags_found'], 1) * 100
    print(f"\n    LLM flag rate       : {pct:.1f}% of entities flagged as unsupported")
    print(f"\n  Backups saved to    : {BACKUP_DIR}")
    print(f"  Templates updated at: {REVIEWS_BASE}")
    print(f"{'='*64}")
    print("\nNext step: Open a template in VS Code and start your review!")
    print("  Start with simple/ papers — they have fewest entities (~15 avg)")


if __name__ == "__main__":
    main()
