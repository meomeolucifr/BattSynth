import os
import json
import pandas as pd
from sklearn.metrics import cohen_kappa_score

def score_testretest(export_csv, map_csv, original_jsons_dir):
    df_export = pd.read_csv(export_csv)
    df_map = pd.read_csv(map_csv)
    
    if len(df_export) != len(df_map):
        raise ValueError("Row count mismatch between export and map CSVs!")
        
    if "re_review_verdict" not in df_export.columns:
        # Create a dummy column if the human hasn't labeled it yet for the sake of the script
        print("WARNING: 're_review_verdict' column missing. The reviewer needs to add this column with their verdicts.")
        return
        
    # Join map to export to get original IDs
    df = df_export.merge(df_map, left_on="entity_id", right_on="opaque_id", how="left")
    
    # Load original labels
    original_labels = {}
    from pathlib import Path
    base = Path(original_jsons_dir)
    for tier in ["simple", "moderate", "complex"]:
        tier_dir = base / tier
        if not tier_dir.exists(): continue
        for rf in tier_dir.glob("Human_Review_*.json"):
            with open(rf, "r", encoding="utf-8") as f:
                review = json.load(f)
            for e in review.get("entity_reviews", []):
                original_labels[e.get("entity_id")] = e.get("human_verdict")
                
    # Compare
    y_true = []
    y_pred = []
    
    for _, row in df.iterrows():
        orig_id = row["original_id"]
        old_verdict = original_labels.get(orig_id, "unknown")
        new_verdict = row["re_review_verdict"]
        
        y_true.append(old_verdict)
        y_pred.append(new_verdict)
        
    y_true = pd.Series(y_true)
    y_pred = pd.Series(y_pred)
    
    valid_classes = ["correct", "incorrect", "partially_correct", "missing_data"]
    
    # Raw agreement
    agreement = (y_true == y_pred).mean()
    
    # Cohen's Kappa
    kappa = cohen_kappa_score(y_true, y_pred, labels=valid_classes)
    
    stats = {
        "n_samples": len(df),
        "raw_agreement": agreement,
        "cohens_kappa": kappa
    }
    
    os.makedirs("dataset/analysis", exist_ok=True)
    with open("dataset/analysis/testretest_reliability.json", "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2)
        
    # Write markdown summary
    with open("dataset/analysis/testretest_summary.md", "w", encoding="utf-8") as f:
        f.write(f"## Test-Retest Reliability\n\n")
        f.write(f"- **N samples**: {len(df)}\n")
        f.write(f"- **Raw Agreement**: {agreement*100:.1f}%\n")
        f.write(f"- **Cohen's Kappa**: {kappa:.3f}\n")
        
    print("Scoring complete!")
    print(f"Raw Agreement: {agreement*100:.1f}%")
    print(f"Cohen's Kappa: {kappa:.3f}")

if __name__ == "__main__":
    try:
        score_testretest(
            "dataset/analysis/testretest_export.csv",
            "dataset/analysis/testretest_id_map.csv",
            "dataset/human_reviews"
        )
    except Exception as e:
        print(f"Error: {e}")
