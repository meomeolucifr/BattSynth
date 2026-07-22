"""
DEPRECATED FOR PAPER REPORTING: This script generates downstream validation statistics
that are no longer reported in the manuscript. The correlation numbers and outlier interpretations
previously derived from this script have been cut from the scope of the paper.
See DECISION_LOG_DOWNSTREAM_SCOPE_CUT.md for details.
"""
import os
import json
import glob
import numpy as np
import pandas as pd
from scipy.stats import pearsonr, spearmanr
import matplotlib.pyplot as plt

def is_cathode_match(data):
    targets = data.get("targets", [])
    if not targets:
        targets = data.get("target_compounds", [])
        
    for t in targets:
        role = str(t.get("intended_role", t.get("role", ""))).lower()
        if "cathode" in role:
            return True
            
    meta = data.get("metadata", {})
    tags = [str(x).lower() for x in meta.get("tags", [])]
    if any("cathode" in t for t in tags):
        return True
        
    title = str(data.get("source", {}).get("title", "")).lower()
    if "cathode" in title:
        return True
        
    return False

def get_calcination_temp(data):
    max_temp = None
    synthesis = data.get("synthesis", {})
    steps = synthesis.get("steps", [])
    for step in steps:
        operations = step.get("operations", [])
        for op in operations:
            op_type = str(op.get("type", "")).lower()
            op_action = str(op.get("action", "")).lower()
            op_name = str(op.get("name", "")).lower()
            
            op_text = op_type + " " + op_action + " " + op_name
            sinter_keywords = ["sinter", "calcin", "anneal", "heat", "hot press", "hot_press", "sps", "densif"]
            if any(k in op_text for k in sinter_keywords):
                temp = None
                
                if "temperature" in op:
                    t_obj = op["temperature"]
                    if isinstance(t_obj, dict):
                        temp = t_obj.get("value")
                    else:
                        temp = t_obj
                elif "parameters" in op and "temperature" in op["parameters"]:
                    t_obj = op["parameters"]["temperature"]
                    if isinstance(t_obj, dict):
                        temp = t_obj.get("value")
                    else:
                        temp = t_obj
                        
                if temp is not None:
                    try:
                        temp_val = float(temp)
                        if max_temp is None or temp_val > max_temp:
                            max_temp = temp_val
                    except ValueError:
                        pass
    return max_temp

def get_capacity(data):
    final = data.get("final_outcomes", {})
    cap = final.get("capacity", {})
    if isinstance(cap, dict):
        val = cap.get("value")
        if val is not None:
            try:
                return float(val)
            except ValueError:
                pass
    
    chars = data.get("characterization", [])
    for char in chars:
        method = str(char.get("method", "")).lower()
        if "cycl" in method or "galvano" in method or "capacity" in method:
            results = char.get("results", [])
            for res in results:
                prop = str(res.get("property", res.get("metric", ""))).lower()
                val = res.get("value")
                
                if "capacit" in prop and val is not None:
                    try:
                        # Extract first number if it's a string like "202.5 / 219.8 / 236.8"
                        if isinstance(val, str):
                            val = val.split('/')[0].strip()
                        return float(val)
                    except ValueError:
                        pass
    return None

def main():
    json_dir = "Output_JSON/All_dataset/output_dataset/"
    files = glob.glob(os.path.join(json_dir, "*.json"))
    
    funnel = {
        "total_papers": len(files),
        "matched_cathode": 0,
        "has_calcination": 0,
        "has_capacity": 0,
        "final_joined": 0
    }
    
    matches = []
    plot_data = []
    
    for fpath in files:
        with open(fpath, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        paper_id = os.path.basename(fpath).replace(".json", "")
        meta = data.get("source", {})
        if not meta:
            meta = data.get("metadata", {})
        doi = meta.get("doi", "")
        title = meta.get("title", paper_id)
        
        if is_cathode_match(data):
            funnel["matched_cathode"] += 1
            matches.append({
                "paper_id": paper_id,
                "doi": doi,
                "title": title
            })
            
            temp = get_calcination_temp(data)
            if temp is not None:
                funnel["has_calcination"] += 1
                
                cap = get_capacity(data)
                if cap is not None:
                    funnel["has_capacity"] += 1
                    funnel["final_joined"] += 1
                    plot_data.append({
                        "paper_id": paper_id,
                        "doi": doi,
                        "title": title,
                        "calcination_temp_K": temp,
                        "capacity_mAh_g": cap
                    })
                    
    os.makedirs("dataset/analysis", exist_ok=True)
    pd.DataFrame(matches).to_csv("dataset/analysis/cathode_match_log.csv", index=False)
    
    print("Funnel Stats:")
    for k, v in funnel.items():
        print(f"  {k}: {v}")
        
    if not plot_data:
        print("No valid data to plot!")
        return
        
    df = pd.DataFrame(plot_data)
    
    mask = df["capacity_mAh_g"] > 0
    df = df[mask]
    if len(df) < 2:
        print("Not enough points to calculate correlation.")
        return
        
    x = df["calcination_temp_K"].values
    y = df["capacity_mAh_g"].values
    
    r_val, p_r = pearsonr(x, y)
    rho_val, p_rho = spearmanr(x, y)
    
    stats = {
        "_caveat": "Correlation values in this file were computed correctly but their chemistry-based interpretation (outlier classification, family stratification) was not independently verified and one such judgment (Hu et al.) was confirmed incorrect. Not used in the manuscript. See DECISION_LOG_DOWNSTREAM_SCOPE_CUT.md.",
        "n_papers": len(df),
        "pearson_r": r_val,
        "pearson_p": p_r,
        "spearman_rho": rho_val,
        "spearman_p": p_rho,
        "funnel": funnel,
        "paired_data": df[["paper_id", "calcination_temp_K", "capacity_mAh_g"]].to_dict(orient="records")
    }
    
    with open("dataset/analysis/downstream_cathode_validation_stats.json", "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2)
        
    os.makedirs("dataset/analysis/figures", exist_ok=True)
    plt.figure(figsize=(8, 6))
    plt.scatter(x, y, alpha=0.7)
    plt.xlabel("Calcination Temperature (K)")
    plt.ylabel("Capacity (mAh/g)")
    plt.title("Calcination Temperature vs. Capacity (Cathodes)")
    
    z = np.polyfit(x, y, 1)
    p = np.poly1d(z)
    plt.plot(x, p(x), "r--", alpha=0.5)
    
    plt.annotate(f"Pearson r: {r_val:.3f} (p={p_r:.3f})\nSpearman rho: {rho_val:.3f} (p={p_rho:.3f})\nn = {len(df)}", 
                 xy=(0.05, 0.95), xycoords='axes fraction', 
                 va='top', bbox=dict(boxstyle='round,pad=0.5', fc='white', alpha=0.8))
                 
    plt.tight_layout()
    plt.savefig("dataset/analysis/figures/cathode_calcination_vs_capacity.png", dpi=300)
    
if __name__ == "__main__":
    main()
