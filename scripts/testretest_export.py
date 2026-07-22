import os
import json
import uuid
import pandas as pd
from pathlib import Path
import random

def entity_type_fn(path: str) -> str:
    if path.startswith("targets"):
        return "target"
    if path.startswith("chemicals"):
        return "chemical"
    if "operations[" in path:
        return "operation"
    if path.startswith("synthesis.steps"):
        return "step_description"
    if path.startswith("characterization"):
        return "characterization"
    if path.startswith("final_outcomes"):
        return "final_outcome"
    return "other"

def main():
    base = Path("dataset/human_reviews")
    records_by_tier = {"simple": [], "moderate": [], "complex": []}
    
    tiers = ["simple", "moderate", "complex"]
    for tier in tiers:
        tier_dir = base / tier
        if not tier_dir.exists():
            continue
        
        for rf in sorted(tier_dir.glob("Human_Review_*.json")):
            with open(rf, "r", encoding="utf-8") as f:
                review = json.load(f)
                
            paper_title = review.get("title", rf.stem)
            
            for e in review.get("entity_reviews", []):
                if "extracted_value" not in e:
                    continue
                    
                records_by_tier[tier].append({
                    "original_id": e.get("entity_id", ""),
                    "paper_title": paper_title,
                    "entity_type": entity_type_fn(e.get("entity_path", "")),
                    "extracted_value": e.get("extracted_value", ""),
                    "source_context_snippet": e.get("source_context_snippet", ""),
                    "tier": tier
                })
                
    # Stratified sampling: ~12% to reach ~100 total
    samples = []
    
    random.seed(42) # For reproducibility
    for tier, target_n in [("simple", 19), ("moderate", 37), ("complex", 44)]:
        tier_recs = records_by_tier[tier]
        if len(tier_recs) <= target_n:
            sampled = tier_recs
        else:
            sampled = random.sample(tier_recs, target_n)
        samples.extend(sampled)
        
    random.shuffle(samples)
    
    export_rows = []
    map_rows = []
    
    for row in samples:
        opaque_id = f"REV_{uuid.uuid4().hex[:8].upper()}"
        original_id = row["original_id"]
        
        safe_snippet = row["source_context_snippet"]
        if original_id and original_id in safe_snippet:
            safe_snippet = safe_snippet.replace(original_id, "[ID_REDACTED]")
            
        export_rows.append({
            "entity_id": opaque_id,
            "paper_title": row["paper_title"],
            "entity_type": row["entity_type"],
            "extracted_value": row["extracted_value"],
            "source_context_snippet": safe_snippet
        })
        
        map_rows.append({
            "opaque_id": opaque_id,
            "original_id": original_id,
            "tier": row["tier"]
        })
        
    os.makedirs("dataset/analysis", exist_ok=True)
    export_path = "dataset/analysis/testretest_export.csv"
    map_path = "dataset/analysis/testretest_id_map.csv"
    
    df_export = pd.DataFrame(export_rows)
    df_map = pd.DataFrame(map_rows)
    
    # Pre-export check: Assert no original IDs in the export dataframe
    leak_detected = False
    for original_id in df_map["original_id"].unique():
        if not original_id: continue
        for col in df_export.select_dtypes(include=[object]).columns:
            if df_export[col].str.contains(original_id, regex=False).any():
                print(f"WARNING: ID {original_id} leaked in column {col}!")
                df_export[col] = df_export[col].str.replace(original_id, "[ID_REDACTED]", regex=False)
                leak_detected = True

    if not leak_detected:
        print("Leakage check passed: No original entity IDs found in the export file.")
        
    df_export.to_csv(export_path, index=False)
    df_map.to_csv(map_path, index=False)
    
    print(f"Exported {len(df_export)} entities for re-review to {export_path}")
    print(f"Saved hidden mapping to {map_path}")

if __name__ == "__main__":
    main()
