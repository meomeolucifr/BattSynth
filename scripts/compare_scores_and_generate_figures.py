"""
compare_scores_and_generate_figures.py
======================================
1. Scores backup (pre-correction) JSONs using same metrics as compute_evaluation_scores.py
2. Compares before/after correction improvement
3. Correlates automated evaluation scores vs human-review P/R/F1
4. Generates publication-quality figures (PNG + PDF)

Output:
  dataset/analysis/
    evaluation_scores_before.json
    comparison_summary.json
    figures/fig8_before_after_scores.{png,pdf}
    figures/fig9_score_vs_f1_correlation.{png,pdf}
    figures/fig10_metric_breakdown_comparison.{png,pdf}
    figures/fig11_score_improvement_waterfall.{png,pdf}

Usage:
    python scripts/compare_scores_and_generate_figures.py
"""

import json
import os
import sys
import re
import csv
from pathlib import Path
from collections import Counter

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy import stats as sp_stats

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    import fitz
    HAS_FITZ = True
except ImportError:
    HAS_FITZ = False
    print("[WARN] PyMuPDF not available — hallucination check will use empty text")

REPO_ROOT = Path(__file__).resolve().parents[1]
GOLDEN = Path(os.environ.get("BATTSYNTH_GOLDEN_DIR", REPO_ROOT / "dataset"))
ANALYSIS = GOLDEN / "analysis"
FIG_DIR = ANALYSIS / "figures"
FIG_DIR.mkdir(parents=True, exist_ok=True)
TIERS = ["simple", "moderate", "complex"]

# ══════════════════════════════════════════════════════════════════════════════
# Import scoring functions from compute_evaluation_scores
# ══════════════════════════════════════════════════════════════════════════════
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from compute_evaluation_scores import (
    compute_overall_score, extract_pdf_text,
    score_provenance, score_units_policy, check_hallucination,
    score_field_completeness, check_molecular_formula
)


# ══════════════════════════════════════════════════════════════════════════════
# STEP 1: Score backup (pre-correction) JSONs
# ══════════════════════════════════════════════════════════════════════════════

def score_backup_jsons():
    """Score the backup (pre-correction) extraction JSONs."""
    print("=" * 70)
    print("  Scoring BACKUP (pre-correction) JSONs")
    print("=" * 70)

    backup_dir = GOLDEN / "extraction_jsons" / "backup"
    results = []

    # Build paper→tier mapping from current scores
    with open(ANALYSIS / "evaluation_scores.json", "r", encoding="utf-8") as f:
        current_scores = json.load(f)
    tier_map = {r["filename"]: r["tier"] for r in current_scores}

    for json_file in sorted(backup_dir.glob("*_reactions.json")):
        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            data = data[0] if data else {}

        tier = tier_map.get(json_file.name, "unknown")
        paper_stem = json_file.stem.replace("_reactions", "")

        # Find PDF
        pdf_path = GOLDEN / "pdfs" / tier / f"{paper_stem}.pdf"
        if not pdf_path.exists():
            pdf_path = GOLDEN / "pdfs" / f"{paper_stem}.pdf"
        pdf_text = extract_pdf_text(pdf_path) if pdf_path.exists() else ""

        score = compute_overall_score(data, pdf_text)
        score["paper_id"] = paper_stem
        score["tier"] = tier
        score["filename"] = json_file.name
        results.append(score)

        print(f"  [{tier[:3]}] {paper_stem[:55]:<55s} {score['score_percent']:>5.1f}% {score['verdict']}")

    # Save
    with open(ANALYSIS / "evaluation_scores_before.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    scores = np.array([r["score_percent"] for r in results])
    print(f"\n  Pre-correction: Mean={scores.mean():.1f}%, Median={np.median(scores):.1f}%, "
          f"Std={scores.std():.1f}%")
    print(f"  Saved: {ANALYSIS / 'evaluation_scores_before.json'}")

    return results


# ══════════════════════════════════════════════════════════════════════════════
# STEP 2: Load all data and build comparison
# ══════════════════════════════════════════════════════════════════════════════

def load_all_data():
    """Load current scores, backup scores, and human review metrics."""
    with open(ANALYSIS / "evaluation_scores.json", "r", encoding="utf-8") as f:
        after_scores = json.load(f)

    with open(ANALYSIS / "evaluation_scores_before.json", "r", encoding="utf-8") as f:
        before_scores = json.load(f)

    with open(ANALYSIS / "golden_dataset_metrics.json", "r", encoding="utf-8") as f:
        metrics = json.load(f)

    return after_scores, before_scores, metrics


def build_comparison(after_scores, before_scores, metrics):
    """Build per-paper comparison table."""
    # Index by filename
    before_map = {r["filename"]: r for r in before_scores}
    per_paper = {p["paper_id"]: p for p in metrics["per_paper"]}

    comparison = []
    for r in after_scores:
        fn = r["filename"]
        pid = r["paper_id"]

        before = before_map.get(fn, {})
        human = per_paper.get(pid, {})

        # Match paper_id by truncation (human review truncates at 50 chars)
        if not human:
            for hp in metrics["per_paper"]:
                if pid.startswith(hp["paper_id"][:40]):
                    human = hp
                    break

        entry = {
            "paper_id": pid,
            "tier": r["tier"],
            "filename": fn,
            "score_before": before.get("score_percent", 0),
            "score_after": r["score_percent"],
            "score_delta": r["score_percent"] - before.get("score_percent", 0),
            "verdict_before": before.get("verdict", ""),
            "verdict_after": r["verdict"],
            "human_precision": human.get("precision", 0),
            "human_recall": human.get("recall", 0),
            "human_f1": human.get("f1", 0),
            "n_entities": human.get("n_entities", 0),
            "n_correct": human.get("correct", 0),
            "n_incorrect": human.get("incorrect", 0),
            "n_missing": human.get("missing_data", 0),
            "llm_agreement": human.get("llm_agreement_rate", 0),
            # Metric breakdowns
            "prov_before": before.get("breakdown", {}).get("provenance", {}).get("passed", 0),
            "prov_total_before": before.get("breakdown", {}).get("provenance", {}).get("total", 1),
            "prov_after": r["breakdown"]["provenance"]["passed"],
            "prov_total_after": r["breakdown"]["provenance"]["total"],
            "comp_before": before.get("breakdown", {}).get("field_completeness", {}).get("passed", 0),
            "comp_total_before": before.get("breakdown", {}).get("field_completeness", {}).get("total", 1),
            "comp_after": r["breakdown"]["field_completeness"]["passed"],
            "comp_total_after": r["breakdown"]["field_completeness"]["total"],
            "formula_before": before.get("breakdown", {}).get("formula_validity", {}).get("passed", 0),
            "formula_total_before": before.get("breakdown", {}).get("formula_validity", {}).get("total", 1),
            "formula_after": r["breakdown"]["formula_validity"]["passed"],
            "formula_total_after": r["breakdown"]["formula_validity"]["total"],
            "units_before": before.get("breakdown", {}).get("units_policy", {}).get("passed", False),
            "units_after": r["breakdown"]["units_policy"]["passed"],
            "halluc_before": before.get("breakdown", {}).get("hallucination", {}).get("passed", True),
            "halluc_after": r["breakdown"]["hallucination"]["passed"],
        }
        comparison.append(entry)

    return comparison


# ══════════════════════════════════════════════════════════════════════════════
# STEP 3: Generate figures
# ══════════════════════════════════════════════════════════════════════════════

# Style config
COLORS = {
    "before": "#E74C3C",   # red
    "after": "#2ECC71",    # green
    "tier_simple": "#3498DB",
    "tier_moderate": "#F39C12",
    "tier_complex": "#9B59B6",
    "correlation": "#2C3E50",
}
plt.rcParams.update({
    "font.size": 11,
    "axes.titlesize": 13,
    "axes.labelsize": 12,
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
    "figure.dpi": 150,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
})


def fig8_before_after(comparison):
    """Before vs After correction scores — paired bar chart."""
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    # Sort by score improvement
    comp_sorted = sorted(comparison, key=lambda x: x["score_delta"], reverse=True)

    # Panel A: Paired bar chart
    ax = axes[0]
    n = len(comp_sorted)
    x = np.arange(n)
    width = 0.35

    before = [c["score_before"] for c in comp_sorted]
    after = [c["score_after"] for c in comp_sorted]
    labels = [c["paper_id"][:20] for c in comp_sorted]

    ax.barh(x + width/2, before, width, label="Before correction", color=COLORS["before"], alpha=0.7)
    ax.barh(x - width/2, after, width, label="After correction", color=COLORS["after"], alpha=0.7)

    ax.set_yticks(x)
    ax.set_yticklabels(labels, fontsize=7)
    ax.set_xlabel("Evaluation Score (%)")
    ax.set_title("(a) Per-Paper Evaluation Scores")
    ax.legend(loc="lower right", fontsize=9)
    ax.set_xlim(60, 102)
    ax.invert_yaxis()

    # Panel B: Score delta waterfall
    ax = axes[1]
    deltas = [c["score_delta"] for c in comp_sorted]
    colors = [COLORS["after"] if d > 0 else ("#95A5A6" if d == 0 else COLORS["before"]) for d in deltas]
    ax.barh(x, deltas, color=colors, alpha=0.8)
    ax.set_yticks(x)
    ax.set_yticklabels(labels, fontsize=7)
    ax.set_xlabel("Score Change (pp)")
    ax.set_title("(b) Score Improvement After Correction")
    ax.axvline(0, color="black", linewidth=0.5)
    ax.invert_yaxis()

    # Annotate mean improvement
    mean_delta = np.mean(deltas)
    ax.axvline(mean_delta, color=COLORS["after"], linestyle="--", linewidth=1, alpha=0.7)
    ax.text(mean_delta + 0.2, n - 1, f"Mean: +{mean_delta:.1f}pp", fontsize=9,
            color=COLORS["after"], va="center")

    plt.tight_layout()
    for ext in ["png", "pdf"]:
        fig.savefig(FIG_DIR / f"fig8_before_after_scores.{ext}")
    plt.close(fig)
    print(f"  [FIG8] Before/after scores saved")


def fig9_score_vs_f1(comparison):
    """Scatter plot: automated evaluation score vs human F1."""
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.5))

    scores_after = np.array([c["score_after"] for c in comparison])
    scores_before = np.array([c["score_before"] for c in comparison])
    f1s = np.array([c["human_f1"] * 100 for c in comparison])
    tiers = [c["tier"] for c in comparison]

    tier_colors = {"simple": COLORS["tier_simple"],
                   "moderate": COLORS["tier_moderate"],
                   "complex": COLORS["tier_complex"]}

    # Panel A: After correction score vs F1
    ax = axes[0]
    for tier in TIERS:
        mask = [t == tier for t in tiers]
        ax.scatter(scores_after[mask], f1s[mask], c=tier_colors[tier],
                   label=tier.capitalize(), s=70, alpha=0.8, edgecolors="white", linewidth=0.5)

    # Regression line
    slope, intercept, r_val, p_val, std_err = sp_stats.linregress(scores_after, f1s)
    x_line = np.linspace(scores_after.min() - 2, scores_after.max() + 2, 100)
    ax.plot(x_line, slope * x_line + intercept, '--', color=COLORS["correlation"], linewidth=1.5, alpha=0.7)
    ax.text(0.05, 0.95, f"r = {r_val:.3f}\np = {p_val:.3f}",
            transform=ax.transAxes, fontsize=10, va="top",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.8))

    ax.set_xlabel("Automated Evaluation Score (%)")
    ax.set_ylabel("Human-Verified F1 (%)")
    ax.set_title("(a) Automated Score vs. Human F1 (After Correction)")
    ax.legend(title="Tier", fontsize=9)

    # Diagonal reference
    lims = [min(ax.get_xlim()[0], ax.get_ylim()[0]), max(ax.get_xlim()[1], ax.get_ylim()[1])]
    ax.plot(lims, lims, ':', color='gray', alpha=0.4, linewidth=1)

    # Panel B: Before correction score vs F1
    ax = axes[1]
    for tier in TIERS:
        mask = [t == tier for t in tiers]
        ax.scatter(scores_before[mask], f1s[mask], c=tier_colors[tier],
                   label=tier.capitalize(), s=70, alpha=0.8, edgecolors="white", linewidth=0.5)

    slope_b, intercept_b, r_b, p_b, _ = sp_stats.linregress(scores_before, f1s)
    x_line_b = np.linspace(scores_before.min() - 2, scores_before.max() + 2, 100)
    ax.plot(x_line_b, slope_b * x_line_b + intercept_b, '--', color=COLORS["correlation"],
            linewidth=1.5, alpha=0.7)
    ax.text(0.05, 0.95, f"r = {r_b:.3f}\np = {p_b:.3f}",
            transform=ax.transAxes, fontsize=10, va="top",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.8))

    ax.set_xlabel("Automated Evaluation Score (%)")
    ax.set_ylabel("Human-Verified F1 (%)")
    ax.set_title("(b) Automated Score vs. Human F1 (Before Correction)")
    ax.legend(title="Tier", fontsize=9)
    lims = [min(ax.get_xlim()[0], ax.get_ylim()[0]), max(ax.get_xlim()[1], ax.get_ylim()[1])]
    ax.plot(lims, lims, ':', color='gray', alpha=0.4, linewidth=1)

    plt.tight_layout()
    for ext in ["png", "pdf"]:
        fig.savefig(FIG_DIR / f"fig9_score_vs_f1_correlation.{ext}")
    plt.close(fig)
    print(f"  [FIG9] Score vs F1 correlation saved (r_after={r_val:.3f}, r_before={r_b:.3f})")

    return r_val, p_val, r_b, p_b


def fig10_metric_breakdown(comparison):
    """Grouped bar chart comparing metric breakdowns before/after."""
    fig, ax = plt.subplots(figsize=(10, 5))

    metrics_names = ["Field\nCompleteness", "Provenance\nValidity", "Formula\nValidity",
                     "Units Policy\n(pass rate)", "Hallucination\n(pass rate)"]

    # Compute aggregate metrics
    comp_before = sum(c["comp_before"] for c in comparison) / max(sum(c["comp_total_before"] for c in comparison), 1) * 100
    comp_after = sum(c["comp_after"] for c in comparison) / max(sum(c["comp_total_after"] for c in comparison), 1) * 100

    prov_before = sum(c["prov_before"] for c in comparison) / max(sum(c["prov_total_before"] for c in comparison), 1) * 100
    prov_after = sum(c["prov_after"] for c in comparison) / max(sum(c["prov_total_after"] for c in comparison), 1) * 100

    form_before = sum(c["formula_before"] for c in comparison) / max(sum(c["formula_total_before"] for c in comparison), 1) * 100
    form_after = sum(c["formula_after"] for c in comparison) / max(sum(c["formula_total_after"] for c in comparison), 1) * 100

    units_before = sum(1 for c in comparison if c["units_before"]) / len(comparison) * 100
    units_after = sum(1 for c in comparison if c["units_after"]) / len(comparison) * 100

    halluc_before = sum(1 for c in comparison if c["halluc_before"]) / len(comparison) * 100
    halluc_after = sum(1 for c in comparison if c["halluc_after"]) / len(comparison) * 100

    before_vals = [comp_before, prov_before, form_before, units_before, halluc_before]
    after_vals = [comp_after, prov_after, form_after, units_after, halluc_after]

    x = np.arange(len(metrics_names))
    width = 0.35

    bars1 = ax.bar(x - width/2, before_vals, width, label="Before correction",
                   color=COLORS["before"], alpha=0.7)
    bars2 = ax.bar(x + width/2, after_vals, width, label="After correction",
                   color=COLORS["after"], alpha=0.7)

    # Value labels
    for bar in bars1:
        h = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2, h + 0.5, f"{h:.1f}",
                ha="center", va="bottom", fontsize=8)
    for bar in bars2:
        h = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2, h + 0.5, f"{h:.1f}",
                ha="center", va="bottom", fontsize=8)

    ax.set_xticks(x)
    ax.set_xticklabels(metrics_names)
    ax.set_ylabel("Score / Pass Rate (%)")
    ax.set_title("Evaluation Metric Breakdown: Before vs. After Correction")
    ax.legend(fontsize=10)
    ax.set_ylim(0, 110)
    ax.axhline(90, color="green", linestyle=":", alpha=0.3, label="Excellent threshold")

    plt.tight_layout()
    for ext in ["png", "pdf"]:
        fig.savefig(FIG_DIR / f"fig10_metric_breakdown_comparison.{ext}")
    plt.close(fig)
    print(f"  [FIG10] Metric breakdown comparison saved")

    return {
        "before": dict(zip(["completeness", "provenance", "formula", "units", "hallucination"], before_vals)),
        "after": dict(zip(["completeness", "provenance", "formula", "units", "hallucination"], after_vals)),
    }


def fig11_score_distribution(comparison):
    """Histogram of score distributions before/after."""
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    before = [c["score_before"] for c in comparison]
    after = [c["score_after"] for c in comparison]

    bins = np.arange(70, 102, 2)

    # Panel A: Overlapping histograms
    ax = axes[0]
    ax.hist(before, bins=bins, alpha=0.5, color=COLORS["before"], label="Before correction", edgecolor="white")
    ax.hist(after, bins=bins, alpha=0.5, color=COLORS["after"], label="After correction", edgecolor="white")
    ax.axvline(90, color="black", linestyle="--", linewidth=1, alpha=0.5, label="Excellent threshold")
    ax.set_xlabel("Evaluation Score (%)")
    ax.set_ylabel("Number of Papers")
    ax.set_title("(a) Score Distribution")
    ax.legend(fontsize=9)

    # Panel B: Verdict distribution before/after
    ax = axes[1]
    verdicts = ["Excellent", "Good", "Acceptable", "Poor"]
    before_counts = [sum(1 for c in comparison if c["verdict_before"] == v) for v in verdicts]
    after_counts = [sum(1 for c in comparison if c["verdict_after"] == v) for v in verdicts]

    x = np.arange(len(verdicts))
    width = 0.35
    ax.bar(x - width/2, before_counts, width, label="Before", color=COLORS["before"], alpha=0.7)
    ax.bar(x + width/2, after_counts, width, label="After", color=COLORS["after"], alpha=0.7)

    # Value labels
    for i, (b, a) in enumerate(zip(before_counts, after_counts)):
        ax.text(i - width/2, b + 0.3, str(b), ha="center", fontsize=9)
        ax.text(i + width/2, a + 0.3, str(a), ha="center", fontsize=9)

    ax.set_xticks(x)
    ax.set_xticklabels(verdicts)
    ax.set_ylabel("Number of Papers")
    ax.set_title("(b) Verdict Distribution")
    ax.legend(fontsize=9)

    plt.tight_layout()
    for ext in ["png", "pdf"]:
        fig.savefig(FIG_DIR / f"fig11_score_distribution.{ext}")
    plt.close(fig)
    print(f"  [FIG11] Score distribution saved")


def fig12_f1_vs_agreement(comparison):
    """Scatter: Human F1 vs LLM Agreement Rate, sized by n_entities."""
    fig, ax = plt.subplots(figsize=(8, 6))

    f1s = np.array([c["human_f1"] * 100 for c in comparison])
    agreements = np.array([c["llm_agreement"] * 100 for c in comparison])
    sizes = np.array([c["n_entities"] for c in comparison])
    tiers = [c["tier"] for c in comparison]

    tier_colors = {"simple": COLORS["tier_simple"],
                   "moderate": COLORS["tier_moderate"],
                   "complex": COLORS["tier_complex"]}

    for tier in TIERS:
        mask = np.array([t == tier for t in tiers])
        ax.scatter(f1s[mask], agreements[mask],
                   s=sizes[mask] * 3, c=tier_colors[tier],
                   label=f"{tier.capitalize()} (n={mask.sum()})",
                   alpha=0.7, edgecolors="white", linewidth=0.5)

    # Regression
    slope, intercept, r_val, p_val, _ = sp_stats.linregress(f1s, agreements)
    x_line = np.linspace(f1s.min() - 2, f1s.max() + 2, 100)
    ax.plot(x_line, slope * x_line + intercept, '--', color=COLORS["correlation"],
            linewidth=1.5, alpha=0.7)
    ax.text(0.05, 0.05, f"r = {r_val:.3f}, p = {p_val:.3f}",
            transform=ax.transAxes, fontsize=10,
            bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.8))

    ax.set_xlabel("Human-Verified F1 (%)")
    ax.set_ylabel("LLM Verifier Agreement Rate (%)")
    ax.set_title("Human F1 vs. LLM Verifier Agreement (bubble size = entity count)")
    ax.legend(title="Tier", fontsize=9)

    plt.tight_layout()
    for ext in ["png", "pdf"]:
        fig.savefig(FIG_DIR / f"fig12_f1_vs_llm_agreement.{ext}")
    plt.close(fig)
    print(f"  [FIG12] F1 vs LLM agreement saved (r={r_val:.3f})")


# ══════════════════════════════════════════════════════════════════════════════
# LaTeX table: Comparison summary
# ══════════════════════════════════════════════════════════════════════════════

def generate_table4(comparison, r_after, p_after, metric_breakdown):
    """Generate LaTeX table4: evaluation metric summary before/after."""
    tex = r"""\begin{table}[htbp]
\centering
\caption{Evaluation metric summary before and after human-guided correction on the 30-paper Golden Dataset.}
\label{tab:eval_improvement}
\begin{tabular}{lrr}
\toprule
Metric & Before & After \\
\midrule
"""
    b = metric_breakdown["before"]
    a = metric_breakdown["after"]

    before_scores = [c["score_before"] for c in comparison]
    after_scores = [c["score_after"] for c in comparison]

    tex += f"  Overall Score (mean) & {np.mean(before_scores):.1f}\\% & {np.mean(after_scores):.1f}\\% \\\\\n"
    tex += f"  Field Completeness & {b['completeness']:.1f}\\% & {a['completeness']:.1f}\\% \\\\\n"
    tex += f"  Provenance Validity & {b['provenance']:.1f}\\% & {a['provenance']:.1f}\\% \\\\\n"
    tex += f"  Formula Validity & {b['formula']:.1f}\\% & {a['formula']:.1f}\\% \\\\\n"
    tex += f"  Units Policy (pass rate) & {b['units']:.0f}\\% & {a['units']:.0f}\\% \\\\\n"
    tex += f"  Hallucination (pass rate) & {b['hallucination']:.0f}\\% & {a['hallucination']:.0f}\\% \\\\\n"

    # Verdict counts
    excellent_b = sum(1 for c in comparison if c["verdict_before"] == "Excellent")
    excellent_a = sum(1 for c in comparison if c["verdict_after"] == "Excellent")
    tex += r"\midrule" + "\n"
    tex += f"  Excellent (\\geq 90\\%) & {excellent_b} & {excellent_a} \\\\\n"
    tex += f"  Good (\\geq 75\\%) & {sum(1 for c in comparison if c['verdict_before'] == 'Good')} & {sum(1 for c in comparison if c['verdict_after'] == 'Good')} \\\\\n"

    tex += r"""\bottomrule
\end{tabular}
\end{table}"""

    with open(ANALYSIS / "table4_eval_improvement.tex", "w", encoding="utf-8") as f:
        f.write(tex)
    print(f"  [TABLE4] Evaluation improvement table saved")


def generate_table5(r_after, p_after, r_before, p_before):
    """Generate LaTeX table5: correlation between automated and human metrics."""
    tex = r"""\begin{table}[htbp]
\centering
\caption{Pearson correlation between automated evaluation score and human-verified F1 on the 30-paper Golden Dataset.}
\label{tab:score_correlation}
\begin{tabular}{lrr}
\toprule
Condition & Pearson $r$ & $p$-value \\
\midrule
"""
    tex += f"  Before correction & {r_before:.3f} & {p_before:.4f} \\\\\n"
    tex += f"  After correction & {r_after:.3f} & {p_after:.4f} \\\\\n"
    tex += r"""\bottomrule
\end{tabular}
\end{table}"""

    with open(ANALYSIS / "table5_score_correlation.tex", "w", encoding="utf-8") as f:
        f.write(tex)
    print(f"  [TABLE5] Score correlation table saved")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    # Step 1: Score backup JSONs
    before_scores = score_backup_jsons()

    # Step 2: Load all data
    after_scores, before_scores_loaded, metrics = load_all_data()
    comparison = build_comparison(after_scores, before_scores_loaded, metrics)

    # Summary stats
    before_arr = np.array([c["score_before"] for c in comparison])
    after_arr = np.array([c["score_after"] for c in comparison])
    delta_arr = after_arr - before_arr

    print(f"\n{'='*70}")
    print(f"  COMPARISON SUMMARY")
    print(f"{'='*70}")
    print(f"  Before correction:  Mean={before_arr.mean():.1f}%, Median={np.median(before_arr):.1f}%")
    print(f"  After correction:   Mean={after_arr.mean():.1f}%, Median={np.median(after_arr):.1f}%")
    print(f"  Improvement:        Mean=+{delta_arr.mean():.1f}pp, Max=+{delta_arr.max():.1f}pp")
    print(f"  Papers improved:    {sum(delta_arr > 0)}/{len(comparison)}")
    print(f"  Papers unchanged:   {sum(delta_arr == 0)}/{len(comparison)}")

    # Step 3: Generate figures
    print(f"\n  Generating figures...")
    fig8_before_after(comparison)
    r_after, p_after, r_before, p_before = fig9_score_vs_f1(comparison)
    metric_breakdown = fig10_metric_breakdown(comparison)
    fig11_score_distribution(comparison)
    fig12_f1_vs_agreement(comparison)

    # Step 4: Generate LaTeX tables
    print(f"\n  Generating LaTeX tables...")
    generate_table4(comparison, r_after, p_after, metric_breakdown)
    generate_table5(r_after, p_after, r_before, p_before)

    # Step 5: Save full comparison
    summary = {
        "n_papers": len(comparison),
        "before_mean": round(float(before_arr.mean()), 1),
        "before_median": round(float(np.median(before_arr)), 1),
        "after_mean": round(float(after_arr.mean()), 1),
        "after_median": round(float(np.median(after_arr)), 1),
        "improvement_mean": round(float(delta_arr.mean()), 1),
        "improvement_max": round(float(delta_arr.max()), 1),
        "papers_improved": int(sum(delta_arr > 0)),
        "papers_unchanged": int(sum(delta_arr == 0)),
        "correlation_after": {"r": round(r_after, 4), "p": round(p_after, 4)},
        "correlation_before": {"r": round(r_before, 4), "p": round(p_before, 4)},
        "metric_breakdown": metric_breakdown,
        "per_paper": comparison,
    }

    with open(ANALYSIS / "comparison_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    # CSV too
    with open(ANALYSIS / "comparison_summary.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["paper_id", "tier", "score_before", "score_after", "delta",
                         "verdict_before", "verdict_after", "human_f1",
                         "human_precision", "human_recall", "llm_agreement"])
        for c in sorted(comparison, key=lambda x: x["score_delta"], reverse=True):
            writer.writerow([
                c["paper_id"][:60], c["tier"],
                c["score_before"], c["score_after"], round(c["score_delta"], 1),
                c["verdict_before"], c["verdict_after"],
                round(c["human_f1"], 4), round(c["human_precision"], 4),
                round(c["human_recall"], 4), round(c["llm_agreement"], 4),
            ])

    print(f"\n  Output files:")
    print(f"    {ANALYSIS / 'evaluation_scores_before.json'}")
    print(f"    {ANALYSIS / 'comparison_summary.json'}")
    print(f"    {ANALYSIS / 'comparison_summary.csv'}")
    print(f"    {ANALYSIS / 'table4_eval_improvement.tex'}")
    print(f"    {ANALYSIS / 'table5_score_correlation.tex'}")
    print(f"    {FIG_DIR / 'fig8_before_after_scores.png'}")
    print(f"    {FIG_DIR / 'fig9_score_vs_f1_correlation.png'}")
    print(f"    {FIG_DIR / 'fig10_metric_breakdown_comparison.png'}")
    print(f"    {FIG_DIR / 'fig11_score_distribution.png'}")
    print(f"    {FIG_DIR / 'fig12_f1_vs_llm_agreement.png'}")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
