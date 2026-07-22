"""
DEPRECATED FOR PAPER REPORTING: This script generates downstream validation statistics
that are no longer reported in the manuscript. The correlation numbers and outlier interpretations
previously derived from this script have been cut from the scope of the paper.
See DECISION_LOG_DOWNSTREAM_SCOPE_CUT.md for details.
"""
import os
import json
import re
import glob
import math
import numpy as np
import pandas as pd
from scipy.stats import pearsonr, spearmanr
import matplotlib.pyplot as plt

def is_llzo_match(target):
    name = str(target.get("compound_name", "")).lower()
    formula = str(target.get("molecular_formula", "")).lower()
    text = name + " " + formula
    
    if "li7la3zr2o12" in text or "llzo" in text:
        return True
    
    has_elements = all(el in text for el in ["li", "la", "zr", "o"])
    if has_elements and "garnet" in text:
        return True
        
    return False

def get_sintering_temp(data):
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

def get_ionic_conductivity(data):
    chars = data.get("characterization", [])
    for char in chars:
        method = str(char.get("method", "")).lower()
        if "eis" in method or "impedance" in method:
            results = char.get("results", [])
            for res in results:
                prop = str(res.get("property", res.get("metric", ""))).lower()
                val = res.get("value")
                unit = str(res.get("unit", "")).lower()
                
                if "conductiv" in prop and val is not None:
                    try:
                        val_float = float(val)
                        if unit == "s/cm" or unit == "s cm-1":
                            return val_float
                        elif unit == "ms/cm" or unit == "ms cm-1":
                            return val_float * 1e-3
                        elif unit == "s m-1" or unit == "s/m":
                            return val_float * 1e-2
                    except ValueError:
                        pass
    return None

def main():
    json_dir = "Output_JSON/All_dataset/output_dataset/"
    files = glob.glob(os.path.join(json_dir, "*.json"))
    
    funnel = {
        "total_papers": len(files),
        "matched_compound": 0,
        "has_sintering": 0,
        "has_conductivity": 0,
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
        
        targets = data.get("targets", [])
        if not targets:
            targets = data.get("target_compounds", [])
            
        matched_target_str = None
        for t in targets:
            if is_llzo_match(t):
                matched_target_str = str(t.get("compound_name", t.get("name", ""))) + " | " + str(t.get("molecular_formula", t.get("formula", "")))
                break
                
        if matched_target_str:
            funnel["matched_compound"] += 1
            matches.append({
                "paper_id": paper_id,
                "doi": doi,
                "title": title,
                "target_match": matched_target_str
            })
            
            temp = get_sintering_temp(data)
            if temp is not None:
                funnel["has_sintering"] += 1
                
                cond = get_ionic_conductivity(data)
                if cond is not None:
                    funnel["has_conductivity"] += 1
                    funnel["final_joined"] += 1
                    plot_data.append({
                        "paper_id": paper_id,
                        "doi": doi,
                        "title": title,
                        "sintering_temp_K": temp,
                        "ionic_conductivity_S_cm": cond
                    })
                    
    os.makedirs("dataset/analysis", exist_ok=True)
    pd.DataFrame(matches).to_csv("dataset/analysis/llzo_match_log.csv", index=False)
    
    print("Funnel Stats:")
    for k, v in funnel.items():
        print(f"  {k}: {v}")
        
    if not plot_data:
        print("No valid data to plot!")
        return
        
    df = pd.DataFrame(plot_data)
    
    mask = df["ionic_conductivity_S_cm"] > 0
    df = df[mask]
    if len(df) < 2:
        print("Not enough points to calculate correlation after filtering out invalid conductivities.")
        return
        
    x = df["sintering_temp_K"].values
    y_raw = df["ionic_conductivity_S_cm"].values
    y = np.log10(y_raw)
    
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
        "paired_data": df[["paper_id", "sintering_temp_K", "ionic_conductivity_S_cm"]].to_dict(orient="records")
    }
    
    with open("dataset/analysis/downstream_validation_stats.json", "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2)
        
    os.makedirs("dataset/analysis/figures", exist_ok=True)
    plt.figure(figsize=(8, 6))
    plt.scatter(x, y, alpha=0.7)
    plt.xlabel("Sintering Temperature (K)")
    plt.ylabel("log10(Ionic Conductivity [S/cm])")
    plt.title("Sintering Temperature vs. Ionic Conductivity (Garnet LLZO)")
    
    z = np.polyfit(x, y, 1)
    p = np.poly1d(z)
    plt.plot(x, p(x), "r--", alpha=0.5)
    
    plt.annotate(f"Pearson r: {r_val:.3f}\nSpearman rho: {rho_val:.3f}\nn = {len(df)}", 
                 xy=(0.05, 0.95), xycoords='axes fraction', 
                 va='top', bbox=dict(boxstyle='round,pad=0.5', fc='white', alpha=0.8))
                 
    plt.tight_layout()
    plt.savefig("dataset/analysis/figures/llzo_sintering_vs_conductivity.png", dpi=300)
    
if __name__ == "__main__":
    main()
