import os
import json
import numpy as np
import pandas as pd
from pathlib import Path

def entity_type(path: str) -> str:
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

def load_entities_df():
    base = Path("dataset/human_reviews")
    records = []
    
    tiers = ["simple", "moderate", "complex"]
    for tier in tiers:
        tier_dir = base / tier
        if not tier_dir.exists():
            continue
        
        for rf in sorted(tier_dir.glob("Human_Review_*.json")):
            with open(rf, "r", encoding="utf-8") as f:
                review = json.load(f)
                
            paper_id = review.get("paper_id", rf.stem)
            
            for e in review.get("entity_reviews", []):
                v = e.get("human_verdict", "")
                
                tp, fp, fn = 0.0, 0.0, 0.0
                if v == "correct":
                    tp = 1.0
                elif v == "incorrect":
                    fp = 1.0
                elif v == "partially_correct":
                    tp = 0.5
                    fp = 0.5
                elif v == "missing_data":
                    fn = 1.0
                    
                records.append({
                    "paper_id": paper_id,
                    "tier": tier,
                    "entity_type": entity_type(e.get("entity_path", "")),
                    "tp": tp,
                    "fp": fp,
                    "fn": fn
                })
                
    return pd.DataFrame(records)

def paper_cluster_bootstrap(df, n_boot=10000, seed=42, group_col="paper_id",
                             entity_type_col="entity_type", entity_type_filter=None):
    if entity_type_filter is not None:
        df = df[df[entity_type_col] == entity_type_filter]

    papers = df[group_col].unique()
    rng = np.random.default_rng(seed)

    # Pre-aggregate tp, fp, fn per paper
    paper_sums = df.groupby(group_col)[["tp", "fp", "fn"]].sum()
    
    # Keep track of original point estimate
    tp_tot = paper_sums["tp"].sum()
    fp_tot = paper_sums["fp"].sum()
    fn_tot = paper_sums["fn"].sum()
    
    point_p = tp_tot / (tp_tot + fp_tot) if (tp_tot + fp_tot) > 0 else np.nan
    point_r = tp_tot / (tp_tot + fn_tot) if (tp_tot + fn_tot) > 0 else np.nan
    point_f1 = 2 * point_p * point_r / (point_p + point_r) if (point_p + point_r) > 0 else np.nan

    # Convert to numpy array for fast sampling
    # Rows correspond to papers, columns to tp, fp, fn
    paper_sums_arr = paper_sums.values
    n_papers = len(paper_sums_arr)
    
    boot_p, boot_r, boot_f1 = [], [], []
    for _ in range(n_boot):
        # Sample paper indices with replacement
        idx = rng.choice(n_papers, size=n_papers, replace=True)
        sample = paper_sums_arr[idx]
        
        tp = sample[:, 0].sum()
        fp = sample[:, 1].sum()
        fn = sample[:, 2].sum()
        
        p = tp / (tp + fp) if (tp + fp) > 0 else np.nan
        r = tp / (tp + fn) if (tp + fn) > 0 else np.nan
        f1 = 2 * p * r / (p + r) if (p + r) > 0 else np.nan
        
        boot_p.append(p)
        boot_r.append(r)
        boot_f1.append(f1)

    def ci(arr):
        arr = np.array(arr)
        arr = arr[~np.isnan(arr)]
        if len(arr) == 0:
            return (np.nan, np.nan)
        return np.percentile(arr, [2.5, 97.5])

    return {
        "precision": (point_p, *ci(boot_p)),
        "recall": (point_r, *ci(boot_r)),
        "f1": (point_f1, *ci(boot_f1)),
        "n_papers": len(papers),
        "n_boot": n_boot,
    }

def main():
    df = load_entities_df()
    
    # Validation (Smoke test)
    total_tp = df["tp"].sum()
    total_fp = df["fp"].sum()
    total_fn = df["fn"].sum()
    
    overall_p = total_tp / (total_tp + total_fp)
    overall_r = total_tp / (total_tp + total_fn)
    overall_f1 = 2 * overall_p * overall_r / (overall_p + overall_r)
    
    overall_p_pct = round(overall_p * 100, 1)
    overall_r_pct = round(overall_r * 100, 1)
    overall_f1_pct = round(overall_f1 * 100, 1)
    
    print(f"Smoke Test Validation:")
    print(f"Computed  -> Precision: {overall_p_pct}%, Recall: {overall_r_pct}%, F1: {overall_f1_pct}%")
    print(f"Expected  -> Precision: 93.6%, Recall: 94.6%, F1: 94.1%")
    
    if overall_p_pct != 93.6 or overall_r_pct != 94.6 or overall_f1_pct != 94.1:
        print("\n[ERROR] Smoke test failed! Point estimates do not match expected values.")
        return
    else:
        print("\n[SUCCESS] Smoke test passed! Running bootstrap...")

    results = []
    
    # Overall
    res = paper_cluster_bootstrap(df)
    results.append(["Overall", "All", res])
    
    # Entity Types
    entity_types = ["target", "chemical", "operation", "step_description", "characterization", "final_outcome"]
    for et in entity_types:
        res = paper_cluster_bootstrap(df, entity_type_filter=et)
        results.append(["Entity Type", et, res])
        
    # Tiers
    tiers = ["simple", "moderate", "complex"]
    for tier in tiers:
        res = paper_cluster_bootstrap(df, entity_type_col="tier", entity_type_filter=tier)
        results.append(["Tier", tier, res])
        
    # Write CSV
    os.makedirs("dataset/analysis", exist_ok=True)
    out_csv = "dataset/analysis/bootstrap_ci_results.csv"
    with open(out_csv, "w", encoding="utf-8") as f:
        f.write("level,subgroup,precision,precision_ci_lo,precision_ci_hi,recall,recall_ci_lo,recall_ci_hi,f1,f1_ci_lo,f1_ci_hi,n_papers,n_boot\n")
        for level, subgroup, res in results:
            p, plo, phi = res["precision"]
            r, rlo, rhi = res["recall"]
            f1, f1lo, f1hi = res["f1"]
            n_papers = res["n_papers"]
            n_boot = res["n_boot"]
            f.write(f"{level},{subgroup},{p},{plo},{phi},{r},{rlo},{rhi},{f1},{f1lo},{f1hi},{n_papers},{n_boot}\n")
            
    # Write Markdown
    out_md = "dataset/analysis/bootstrap_ci_table.md"
    with open(out_md, "w", encoding="utf-8") as f:
        f.write("| Level | Subgroup | Precision | Recall | F1 |\n")
        f.write("|---|---|---|---|---|\n")
        for level, subgroup, res in results:
            p, plo, phi = res["precision"]
            r, rlo, rhi = res["recall"]
            f1, f1lo, f1hi = res["f1"]
            
            def fmt(v, v_lo, v_hi):
                if pd.isna(v): return "N/A"
                return f"{v*100:.1f}% [{v_lo*100:.1f}, {v_hi*100:.1f}]"
            
            f.write(f"| {level} | {subgroup} | {fmt(p, plo, phi)} | {fmt(r, rlo, rhi)} | {fmt(f1, f1lo, f1hi)} |\n")
            
    print(f"\nSaved results to {out_csv} and {out_md}")

if __name__ == "__main__":
    main()
