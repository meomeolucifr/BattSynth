"""
compute_golden_metrics.py
=========================
Computes publication-ready metrics from the 30-paper Golden Dataset v2
human reviews. Produces:

  1. Extraction accuracy: precision / recall / F1 by entity type and tier
  2. LLM verifier vs. human agreement: confusion matrix, Cohen's kappa
  3. Error taxonomy breakdown
  4. Per-paper quality summary
  5. LaTeX-ready tables + matplotlib figures

Output:
    dataset/analysis/  (tables, figures, summary JSON)

Usage:
    python scripts/compute_golden_metrics.py
"""

import json
import os
import sys
import math
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime

import numpy as np

# Try to import matplotlib — generate figures if available
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.ticker as mticker
    HAS_MPL = True
except ImportError:
    HAS_MPL = False
    print("[WARN] matplotlib not available — skipping figure generation")

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ── Paths ────────────────────────────────────────────────────────────────────

REPO_ROOT  = Path(__file__).resolve().parents[1]
BASE       = Path(os.environ.get(
    "BATTSYNTH_GOLDEN_DIR",
    REPO_ROOT / "dataset",
))
REV_DIR    = BASE / "human_reviews"
OUT_DIR    = BASE / "analysis"

TIERS      = ["simple", "moderate", "complex"]

# ── Entity type classifier ───────────────────────────────────────────────────

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

ENTITY_TYPES = ["target", "chemical", "operation", "step_description",
                "characterization", "final_outcome"]

# ── Load all entities ────────────────────────────────────────────────────────

def load_all_entities():
    """Load all entity reviews from all 30 papers, tagging tier + paper."""
    entities = []
    papers = []
    for tier in TIERS:
        tier_dir = REV_DIR / tier
        if not tier_dir.exists():
            continue
        for rf in sorted(tier_dir.glob("Human_Review_*.json")):
            with open(rf, "r", encoding="utf-8") as f:
                review = json.load(f)
            paper_id = review.get("paper_id", rf.stem)
            paper_info = {
                "paper_id": paper_id,
                "tier": tier,
                "filename": rf.name,
                "total_entities": len(review.get("entity_reviews", [])),
                "summary": review.get("summary", {}),
            }
            for e in review.get("entity_reviews", []):
                e["_tier"] = tier
                e["_paper_id"] = paper_id
                e["_entity_type"] = entity_type(e.get("entity_path", ""))
                entities.append(e)
            papers.append(paper_info)
    return entities, papers


# ── 1. Extraction Accuracy (Precision / Recall / F1) ─────────────────────────
#
# In this context:
#   - Each extracted entity that was reviewed is a "prediction"
#   - human_verdict == "correct" means the extraction is a TRUE POSITIVE
#   - human_verdict == "incorrect" means the extraction is a FALSE POSITIVE
#   - human_verdict == "partially_correct" counts as 0.5 TP + 0.5 FP
#   - human_verdict == "missing_data" means the field should have had data
#     but was empty — this is a FALSE NEGATIVE (extractor missed real data)
#
# Precision = TP / (TP + FP)     — of what was extracted, how much is correct?
# Recall    = TP / (TP + FN)     — of what should exist, how much was found?
# F1        = 2 * P * R / (P + R)

def compute_prf(entities: list) -> dict:
    """Compute precision, recall, F1 from a list of entity dicts."""
    tp = 0.0
    fp = 0.0
    fn = 0.0
    partial = 0.0

    for e in entities:
        v = e.get("human_verdict", "")
        if v == "correct":
            tp += 1
        elif v == "incorrect":
            fp += 1
        elif v == "partially_correct":
            tp += 0.5
            fp += 0.5
            partial += 1
        elif v == "missing_data":
            fn += 1

    total = tp + fp + fn
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall    = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1        = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    return {
        "n": len(entities),
        "tp": tp, "fp": fp, "fn": fn, "partial": partial,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "accuracy": round(tp / max(tp + fp, 1), 4),  # simple accuracy (excl. missing_data)
    }


# ── 2. LLM vs. Human Confusion Matrix ────────────────────────────────────────
#
# LLM verdicts:  supported, unsupported, not_verified_by_llm
# Human verdicts: correct, incorrect, partially_correct, missing_data
#
# Key metrics:
#   - Agreement rate: LLM supported & human correct  +  LLM unsupported & human incorrect/missing
#   - False positive rate: LLM says supported but human says incorrect
#   - False negative rate: LLM says unsupported but human says correct (over-flagging)

def compute_confusion(entities: list) -> dict:
    """Build confusion matrix: LLM verdict x Human verdict."""
    matrix = defaultdict(lambda: defaultdict(int))
    for e in entities:
        lv = e.get("llm_verdict", "unknown")
        hv = e.get("human_verdict", "unknown")
        matrix[lv][hv] += 1

    # Flatten for JSON serialization
    flat = {}
    for lv in sorted(matrix):
        flat[lv] = dict(matrix[lv])

    # Compute agreement metrics
    total = len(entities)
    # Entities where LLM verdict is meaningful (not step descriptions)
    verified_entities = [e for e in entities if e.get("llm_verdict") in ("supported", "unsupported")]
    n_verified = len(verified_entities)

    # LLM supported + human correct = true agreement
    agree_supported = sum(1 for e in verified_entities
                         if e["llm_verdict"] == "supported" and e["human_verdict"] == "correct")
    # LLM unsupported + human incorrect/missing_data = true agreement
    agree_unsupported = sum(1 for e in verified_entities
                           if e["llm_verdict"] == "unsupported"
                           and e["human_verdict"] in ("incorrect", "missing_data"))

    # LLM supported but human says incorrect (LLM missed an error)
    false_neg_llm = sum(1 for e in verified_entities
                        if e["llm_verdict"] == "supported"
                        and e["human_verdict"] in ("incorrect", "missing_data"))

    # LLM unsupported but human says correct (LLM over-flagged)
    false_pos_llm = sum(1 for e in verified_entities
                        if e["llm_verdict"] == "unsupported"
                        and e["human_verdict"] == "correct")

    agreement_rate = (agree_supported + agree_unsupported) / n_verified if n_verified > 0 else 0

    return {
        "matrix": flat,
        "total_entities": total,
        "llm_verified_entities": n_verified,
        "agree_supported": agree_supported,
        "agree_unsupported": agree_unsupported,
        "total_agreement": agree_supported + agree_unsupported,
        "agreement_rate": round(agreement_rate, 4),
        "false_negative_llm": false_neg_llm,  # LLM said OK but human said wrong
        "false_positive_llm": false_pos_llm,  # LLM flagged but human said correct
        "false_neg_rate": round(false_neg_llm / max(sum(1 for e in verified_entities if e["llm_verdict"] == "supported"), 1), 4),
        "false_pos_rate": round(false_pos_llm / max(sum(1 for e in verified_entities if e["llm_verdict"] == "unsupported"), 1), 4),
    }


# ── 3. Cohen's Kappa ─────────────────────────────────────────────────────────

def compute_cohens_kappa(entities: list) -> float:
    """
    Compute Cohen's kappa for LLM vs. human binary agreement.
    Binary mapping:
      LLM: supported → positive,   unsupported → negative
      Human: correct/partially → positive,  incorrect/missing → negative
    """
    verified = [e for e in entities if e.get("llm_verdict") in ("supported", "unsupported")]
    if not verified:
        return 0.0

    n = len(verified)
    # Binary labels
    # LLM: 1=supported, 0=unsupported
    # Human: 1=correct/partially, 0=incorrect/missing
    a = 0  # both positive
    b = 0  # LLM pos, human neg
    c = 0  # LLM neg, human pos
    d = 0  # both negative

    for e in verified:
        llm_pos = e["llm_verdict"] == "supported"
        human_pos = e["human_verdict"] in ("correct", "partially_correct")
        if llm_pos and human_pos:
            a += 1
        elif llm_pos and not human_pos:
            b += 1
        elif not llm_pos and human_pos:
            c += 1
        else:
            d += 1

    po = (a + d) / n  # observed agreement
    pe = ((a + b) * (a + c) + (c + d) * (b + d)) / (n * n)  # expected agreement
    if pe == 1.0:
        return 1.0
    kappa = (po - pe) / (1 - pe)
    return round(kappa, 4)


# ── 4. Error Taxonomy ─────────────────────────────────────────────────────────

def compute_error_taxonomy(entities: list) -> dict:
    """Break down errors by type and category."""
    errors = [e for e in entities if e.get("human_verdict") in ("incorrect", "partially_correct", "missing_data")]

    by_category = Counter()
    by_type_and_verdict = defaultdict(lambda: Counter())
    by_tier = defaultdict(lambda: Counter())

    for e in errors:
        cat = e.get("error_category", "") or "unspecified"
        etype = e.get("_entity_type", "other")
        verdict = e.get("human_verdict", "")
        tier = e.get("_tier", "")

        by_category[cat] += 1
        by_type_and_verdict[etype][verdict] += 1
        by_tier[tier][verdict] += 1

    return {
        "total_errors": len(errors),
        "by_category": dict(by_category),
        "by_entity_type": {k: dict(v) for k, v in by_type_and_verdict.items()},
        "by_tier": {k: dict(v) for k, v in by_tier.items()},
    }


# ── 5. Per-Paper Quality Summary ─────────────────────────────────────────────

def per_paper_summary(entities: list) -> list:
    """Compute per-paper metrics."""
    by_paper = defaultdict(list)
    for e in entities:
        by_paper[(e["_paper_id"], e["_tier"])].append(e)

    results = []
    for (paper_id, tier), ents in sorted(by_paper.items()):
        prf = compute_prf(ents)
        confusion = compute_confusion(ents)
        hv = Counter(e["human_verdict"] for e in ents)
        results.append({
            "paper_id": paper_id[:60],
            "tier": tier,
            "n_entities": len(ents),
            "correct": hv.get("correct", 0),
            "incorrect": hv.get("incorrect", 0),
            "partially_correct": hv.get("partially_correct", 0),
            "missing_data": hv.get("missing_data", 0),
            "precision": prf["precision"],
            "recall": prf["recall"],
            "f1": prf["f1"],
            "llm_agreement_rate": confusion["agreement_rate"],
        })

    return results


# ── 6. Confidence Calibration ─────────────────────────────────────────────────

def confidence_calibration(entities: list) -> list:
    """Bin LLM confidence and compute human agreement rate per bin."""
    verified = [e for e in entities
                if e.get("llm_verdict") in ("supported", "unsupported")
                and e.get("llm_confidence") is not None]

    bins = [(0.5, 0.6), (0.6, 0.7), (0.7, 0.8), (0.8, 0.9), (0.9, 1.01)]
    results = []

    for lo, hi in bins:
        in_bin = [e for e in verified if lo <= (e.get("llm_confidence") or 0) < hi]
        if not in_bin:
            results.append({"bin": f"{lo:.1f}-{hi:.1f}", "n": 0, "agreement_rate": 0})
            continue

        agree = sum(1 for e in in_bin if (
            (e["llm_verdict"] == "supported" and e["human_verdict"] in ("correct", "partially_correct"))
            or
            (e["llm_verdict"] == "unsupported" and e["human_verdict"] in ("incorrect", "missing_data"))
        ))
        results.append({
            "bin": f"{lo:.1f}-{hi:.2f}",
            "n": len(in_bin),
            "agreement_rate": round(agree / len(in_bin), 4),
        })

    return results


# ── 7. Generate Figures ───────────────────────────────────────────────────────

def generate_figures(entities, paper_summaries, confusion_data, calibration_data, error_data):
    """Generate publication-quality matplotlib figures."""
    if not HAS_MPL:
        return

    fig_dir = OUT_DIR / "figures"
    fig_dir.mkdir(exist_ok=True)

    # Color palette
    COLORS = {
        "correct": "#2ecc71",
        "incorrect": "#e74c3c",
        "partially_correct": "#f39c12",
        "missing_data": "#9b59b6",
    }
    TIER_COLORS = {"simple": "#3498db", "moderate": "#e67e22", "complex": "#e74c3c"}

    # ── Figure 1: P/R/F1 by entity type ──────────────────────────────────────
    fig, ax = plt.subplots(figsize=(10, 5))
    by_type = defaultdict(list)
    for e in entities:
        by_type[e["_entity_type"]].append(e)

    types_ordered = [t for t in ENTITY_TYPES if t in by_type]
    prfs = [compute_prf(by_type[t]) for t in types_ordered]

    x = np.arange(len(types_ordered))
    w = 0.25
    ax.bar(x - w, [p["precision"] for p in prfs], w, label="Precision", color="#3498db", edgecolor="white")
    ax.bar(x,     [p["recall"] for p in prfs],    w, label="Recall",    color="#2ecc71", edgecolor="white")
    ax.bar(x + w, [p["f1"] for p in prfs],        w, label="F1",        color="#e74c3c", edgecolor="white")

    ax.set_xticks(x)
    ax.set_xticklabels([t.replace("_", " ").title() for t in types_ordered], rotation=20, ha="right")
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Score")
    ax.set_title("Extraction Quality by Entity Type (30-Paper Golden Dataset)")
    ax.legend(loc="lower left")
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(1.0))
    for i, prf in enumerate(prfs):
        ax.text(i + w, prf["f1"] + 0.02, f'{prf["f1"]:.0%}', ha="center", va="bottom", fontsize=8, fontweight="bold")

    plt.tight_layout()
    plt.savefig(fig_dir / "fig1_prf_by_entity_type.png", dpi=300, bbox_inches="tight")
    plt.savefig(fig_dir / "fig1_prf_by_entity_type.pdf", bbox_inches="tight")
    plt.close()
    print(f"  [FIG1] P/R/F1 by entity type saved")

    # ── Figure 2: P/R/F1 by complexity tier ──────────────────────────────────
    fig, ax = plt.subplots(figsize=(7, 5))
    by_tier = defaultdict(list)
    for e in entities:
        by_tier[e["_tier"]].append(e)

    tier_prfs = [compute_prf(by_tier[t]) for t in TIERS]

    x = np.arange(len(TIERS))
    ax.bar(x - w, [p["precision"] for p in tier_prfs], w, label="Precision", color="#3498db", edgecolor="white")
    ax.bar(x,     [p["recall"] for p in tier_prfs],    w, label="Recall",    color="#2ecc71", edgecolor="white")
    ax.bar(x + w, [p["f1"] for p in tier_prfs],        w, label="F1",        color="#e74c3c", edgecolor="white")

    ax.set_xticks(x)
    ax.set_xticklabels([t.title() for t in TIERS])
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Score")
    ax.set_title("Extraction Quality by Paper Complexity")
    ax.legend()
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(1.0))
    for i, prf in enumerate(tier_prfs):
        ax.text(i + w, prf["f1"] + 0.02, f'{prf["f1"]:.0%}', ha="center", va="bottom", fontsize=9, fontweight="bold")
        ax.text(i - w, prf["precision"] + 0.02, f'n={prf["n"]}', ha="center", va="bottom", fontsize=7, color="gray")

    plt.tight_layout()
    plt.savefig(fig_dir / "fig2_prf_by_tier.png", dpi=300, bbox_inches="tight")
    plt.savefig(fig_dir / "fig2_prf_by_tier.pdf", bbox_inches="tight")
    plt.close()
    print(f"  [FIG2] P/R/F1 by tier saved")

    # ── Figure 3: LLM vs Human Confusion Matrix Heatmap ─────────────────────
    llm_labels = ["supported", "unsupported", "not_verified_by_llm"]
    human_labels = ["correct", "incorrect", "partially_correct", "missing_data"]

    cm = np.zeros((len(llm_labels), len(human_labels)), dtype=int)
    for i, lv in enumerate(llm_labels):
        for j, hv in enumerate(human_labels):
            cm[i, j] = confusion_data["matrix"].get(lv, {}).get(hv, 0)

    fig, ax = plt.subplots(figsize=(8, 5))
    im = ax.imshow(cm, cmap="YlOrRd", aspect="auto")

    ax.set_xticks(np.arange(len(human_labels)))
    ax.set_yticks(np.arange(len(llm_labels)))
    ax.set_xticklabels([h.replace("_", " ").title() for h in human_labels], rotation=25, ha="right")
    ax.set_yticklabels([l.replace("_", " ").title() for l in llm_labels])
    ax.set_xlabel("Human Verdict")
    ax.set_ylabel("LLM Verdict")
    ax.set_title("LLM Verifier vs. Human Expert: Confusion Matrix")

    # Annotate cells
    for i in range(len(llm_labels)):
        for j in range(len(human_labels)):
            val = cm[i, j]
            color = "white" if val > cm.max() * 0.6 else "black"
            ax.text(j, i, str(val), ha="center", va="center", color=color, fontsize=12, fontweight="bold")

    plt.colorbar(im, ax=ax, label="Count")
    plt.tight_layout()
    plt.savefig(fig_dir / "fig3_confusion_matrix.png", dpi=300, bbox_inches="tight")
    plt.savefig(fig_dir / "fig3_confusion_matrix.pdf", bbox_inches="tight")
    plt.close()
    print(f"  [FIG3] Confusion matrix saved")

    # ── Figure 4: Confidence Calibration Curve ───────────────────────────────
    fig, ax = plt.subplots(figsize=(7, 5))
    cal_bins = [c for c in calibration_data if c["n"] > 0]
    if cal_bins:
        x_cal = range(len(cal_bins))
        bars = ax.bar(x_cal, [c["agreement_rate"] for c in cal_bins],
                       color="#3498db", edgecolor="white", alpha=0.8)
        ax.set_xticks(x_cal)
        ax.set_xticklabels([c["bin"] for c in cal_bins])
        ax.set_xlabel("LLM Confidence Bin")
        ax.set_ylabel("Agreement with Human Expert")
        ax.set_title("LLM Verifier Confidence Calibration")
        ax.set_ylim(0, 1.05)
        ax.yaxis.set_major_formatter(mticker.PercentFormatter(1.0))

        # Add count labels on bars
        for i, c in enumerate(cal_bins):
            ax.text(i, c["agreement_rate"] + 0.02,
                    f'n={c["n"]}\n{c["agreement_rate"]:.0%}',
                    ha="center", va="bottom", fontsize=8)

        # Perfect calibration line
        ax.axhline(y=1.0, color="gray", linestyle="--", alpha=0.3, label="Perfect")

    plt.tight_layout()
    plt.savefig(fig_dir / "fig4_confidence_calibration.png", dpi=300, bbox_inches="tight")
    plt.savefig(fig_dir / "fig4_confidence_calibration.pdf", bbox_inches="tight")
    plt.close()
    print(f"  [FIG4] Confidence calibration saved")

    # ── Figure 5: Verdict Distribution Stacked Bar by Tier ───────────────────
    fig, ax = plt.subplots(figsize=(8, 5))

    verdicts = ["correct", "incorrect", "missing_data", "partially_correct"]
    by_tier_counts = {}
    for tier in TIERS:
        tier_ents = by_tier.get(tier, [])
        vc = Counter(e["human_verdict"] for e in tier_ents)
        total = len(tier_ents)
        by_tier_counts[tier] = {v: vc.get(v, 0) / total if total > 0 else 0 for v in verdicts}

    x = np.arange(len(TIERS))
    bottom = np.zeros(len(TIERS))
    for v in verdicts:
        vals = [by_tier_counts[t].get(v, 0) for t in TIERS]
        ax.bar(x, vals, 0.5, bottom=bottom, label=v.replace("_", " ").title(),
               color=COLORS.get(v, "#95a5a6"), edgecolor="white")
        bottom += vals

    ax.set_xticks(x)
    ax.set_xticklabels([f"{t.title()}\n(n={len(by_tier[t])})" for t in TIERS])
    ax.set_ylabel("Fraction of Entities")
    ax.set_title("Human Verdict Distribution by Paper Complexity")
    ax.legend(bbox_to_anchor=(1.02, 1), loc="upper left")
    ax.set_ylim(0, 1.05)
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(1.0))

    plt.tight_layout()
    plt.savefig(fig_dir / "fig5_verdict_distribution.png", dpi=300, bbox_inches="tight")
    plt.savefig(fig_dir / "fig5_verdict_distribution.pdf", bbox_inches="tight")
    plt.close()
    print(f"  [FIG5] Verdict distribution saved")

    # ── Figure 6: Error Category Pie Chart ───────────────────────────────────
    fig, ax = plt.subplots(figsize=(7, 5))
    cats = error_data["by_category"]
    if cats:
        labels = []
        sizes = []
        for k, v in sorted(cats.items(), key=lambda x: -x[1]):
            labels.append(k.replace("_", " ").title())
            sizes.append(v)
        colors_pie = plt.cm.Set3(np.linspace(0, 1, len(labels)))
        wedges, texts, autotexts = ax.pie(sizes, labels=labels, autopct='%1.1f%%',
                                           colors=colors_pie, startangle=90)
        ax.set_title(f"Error Category Distribution (n={sum(sizes)})")

    plt.tight_layout()
    plt.savefig(fig_dir / "fig6_error_categories.png", dpi=300, bbox_inches="tight")
    plt.savefig(fig_dir / "fig6_error_categories.pdf", bbox_inches="tight")
    plt.close()
    print(f"  [FIG6] Error categories saved")

    # ── Figure 7: Per-paper F1 distribution ──────────────────────────────────
    fig, ax = plt.subplots(figsize=(12, 5))
    ps = sorted(paper_summaries, key=lambda p: (-{"simple": 0, "moderate": 1, "complex": 2}.get(p["tier"], 3), -p["f1"]))

    colors_bar = [TIER_COLORS.get(p["tier"], "gray") for p in ps]
    names = [p["paper_id"][:30] for p in ps]
    f1s = [p["f1"] for p in ps]

    bars = ax.barh(range(len(ps)), f1s, color=colors_bar, edgecolor="white", alpha=0.85)
    ax.set_yticks(range(len(ps)))
    ax.set_yticklabels(names, fontsize=7)
    ax.set_xlabel("F1 Score")
    ax.set_title("Per-Paper Extraction F1 Score (30-Paper Golden Dataset)")
    ax.set_xlim(0, 1.05)
    ax.invert_yaxis()

    # Add tier legend
    from matplotlib.patches import Patch
    legend_elements = [Patch(facecolor=TIER_COLORS[t], label=t.title()) for t in TIERS]
    ax.legend(handles=legend_elements, loc="lower right")

    # Add F1 value labels
    for i, (bar, f1_val) in enumerate(zip(bars, f1s)):
        ax.text(f1_val + 0.01, i, f'{f1_val:.0%}', va="center", fontsize=7)

    plt.tight_layout()
    plt.savefig(fig_dir / "fig7_per_paper_f1.png", dpi=300, bbox_inches="tight")
    plt.savefig(fig_dir / "fig7_per_paper_f1.pdf", bbox_inches="tight")
    plt.close()
    print(f"  [FIG7] Per-paper F1 saved")


# ── 8. Generate LaTeX Tables ─────────────────────────────────────────────────

def generate_latex_tables(prf_by_type, prf_by_tier, prf_overall, confusion, kappa, calibration):
    """Generate LaTeX-formatted tables for the paper."""
    tables = {}

    # Table 1: PRF by entity type
    lines = [
        r"\begin{table}[htbp]",
        r"\centering",
        r"\caption{Extraction accuracy by entity type on the 30-paper Golden Dataset, evaluated against human expert annotations.}",
        r"\label{tab:prf_entity_type}",
        r"\begin{tabular}{lrrrr}",
        r"\toprule",
        r"Entity Type & $n$ & Precision & Recall & F1 \\",
        r"\midrule",
    ]
    for etype in ENTITY_TYPES:
        if etype in prf_by_type:
            p = prf_by_type[etype]
            name = etype.replace("_", " ").title()
            lines.append(f"  {name} & {p['n']} & {p['precision']:.1%} & {p['recall']:.1%} & {p['f1']:.1%} \\\\")
    lines.append(r"\midrule")
    lines.append(f"  \\textbf{{Overall}} & \\textbf{{{prf_overall['n']}}} & \\textbf{{{prf_overall['precision']:.1%}}} & \\textbf{{{prf_overall['recall']:.1%}}} & \\textbf{{{prf_overall['f1']:.1%}}} \\\\")
    lines.extend([
        r"\bottomrule",
        r"\end{tabular}",
        r"\end{table}",
    ])
    tables["table1_prf_entity_type"] = "\n".join(lines)

    # Table 2: PRF by tier
    lines = [
        r"\begin{table}[htbp]",
        r"\centering",
        r"\caption{Extraction accuracy by paper complexity tier.}",
        r"\label{tab:prf_tier}",
        r"\begin{tabular}{lrrrr}",
        r"\toprule",
        r"Tier & $n$ & Precision & Recall & F1 \\",
        r"\midrule",
    ]
    for tier in TIERS:
        p = prf_by_tier[tier]
        lines.append(f"  {tier.title()} & {p['n']} & {p['precision']:.1%} & {p['recall']:.1%} & {p['f1']:.1%} \\\\")
    lines.extend([
        r"\midrule",
        f"  \\textbf{{Overall}} & \\textbf{{{prf_overall['n']}}} & \\textbf{{{prf_overall['precision']:.1%}}} & \\textbf{{{prf_overall['recall']:.1%}}} & \\textbf{{{prf_overall['f1']:.1%}}} \\\\",
        r"\bottomrule",
        r"\end{tabular}",
        r"\end{table}",
    ])
    tables["table2_prf_tier"] = "\n".join(lines)

    # Table 3: Confusion matrix
    lines = [
        r"\begin{table}[htbp]",
        r"\centering",
        r"\caption{LLM verifier vs.\ human expert confusion matrix. Cohen's $\kappa$ = " + f"{kappa:.3f}" + r".}",
        r"\label{tab:confusion}",
        r"\begin{tabular}{lrrrr|r}",
        r"\toprule",
        r" & \multicolumn{4}{c|}{Human Verdict} & \\",
        r"LLM Verdict & Correct & Incorrect & Partial & Missing & Total \\",
        r"\midrule",
    ]
    llm_labels = ["supported", "unsupported", "not_verified_by_llm"]
    for lv in llm_labels:
        row_data = confusion["matrix"].get(lv, {})
        c = row_data.get("correct", 0)
        i = row_data.get("incorrect", 0)
        p = row_data.get("partially_correct", 0)
        m = row_data.get("missing_data", 0)
        t = c + i + p + m
        name = lv.replace("_", " ").title()
        lines.append(f"  {name} & {c} & {i} & {p} & {m} & {t} \\\\")
    lines.extend([
        r"\bottomrule",
        r"\end{tabular}",
        r"\end{table}",
    ])
    tables["table3_confusion"] = "\n".join(lines)

    return tables


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    if not REV_DIR.exists():
        raise SystemExit(
            f"Human-review directory not found: {REV_DIR}\n"
            "Set BATTSYNTH_GOLDEN_DIR to a dataset directory containing "
            "human_reviews/{simple,moderate,complex}."
        )
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print("=" * 66)
    print("  Golden Dataset v2 — Metrics & Analysis")
    print("=" * 66)

    # Load data
    entities, papers = load_all_entities()
    print(f"\n  Loaded {len(entities)} entities from {len(papers)} papers")

    # ── 1. Overall PRF ──
    prf_overall = compute_prf(entities)
    print(f"\n  OVERALL EXTRACTION QUALITY")
    print(f"    Precision : {prf_overall['precision']:.1%}")
    print(f"    Recall    : {prf_overall['recall']:.1%}")
    print(f"    F1        : {prf_overall['f1']:.1%}")
    print(f"    (n={prf_overall['n']}, TP={prf_overall['tp']}, FP={prf_overall['fp']}, FN={prf_overall['fn']})")

    # ── 2. PRF by entity type ──
    by_type = defaultdict(list)
    for e in entities:
        by_type[e["_entity_type"]].append(e)

    prf_by_type = {}
    print(f"\n  BY ENTITY TYPE:")
    print(f"    {'Type':<20s} {'n':>5s} {'P':>7s} {'R':>7s} {'F1':>7s}")
    print(f"    {'-'*42}")
    for etype in ENTITY_TYPES:
        if etype in by_type:
            prf = compute_prf(by_type[etype])
            prf_by_type[etype] = prf
            print(f"    {etype:<20s} {prf['n']:>5d} {prf['precision']:>7.1%} {prf['recall']:>7.1%} {prf['f1']:>7.1%}")

    # ── 3. PRF by tier ──
    by_tier = defaultdict(list)
    for e in entities:
        by_tier[e["_tier"]].append(e)

    prf_by_tier = {}
    print(f"\n  BY COMPLEXITY TIER:")
    print(f"    {'Tier':<12s} {'n':>5s} {'P':>7s} {'R':>7s} {'F1':>7s}")
    print(f"    {'-'*36}")
    for tier in TIERS:
        prf = compute_prf(by_tier.get(tier, []))
        prf_by_tier[tier] = prf
        print(f"    {tier:<12s} {prf['n']:>5d} {prf['precision']:>7.1%} {prf['recall']:>7.1%} {prf['f1']:>7.1%}")

    # ── 4. LLM vs. Human confusion ──
    confusion = compute_confusion(entities)
    print(f"\n  LLM vs. HUMAN AGREEMENT:")
    print(f"    LLM-verified entities : {confusion['llm_verified_entities']}")
    print(f"    Agreement rate        : {confusion['agreement_rate']:.1%}")
    print(f"    Agreements (supported): {confusion['agree_supported']}")
    print(f"    Agreements (unsupport): {confusion['agree_unsupported']}")
    print(f"    LLM false negatives   : {confusion['false_negative_llm']} (said OK, human said wrong)")
    print(f"    LLM false positives   : {confusion['false_positive_llm']} (flagged, human said correct)")
    print(f"    False negative rate   : {confusion['false_neg_rate']:.1%}")
    print(f"    False positive rate   : {confusion['false_pos_rate']:.1%}")

    # ── 5. Cohen's Kappa ──
    kappa = compute_cohens_kappa(entities)
    print(f"\n  COHEN'S KAPPA (binary): {kappa:.4f}")
    if kappa >= 0.81:
        kappa_interp = "almost perfect"
    elif kappa >= 0.61:
        kappa_interp = "substantial"
    elif kappa >= 0.41:
        kappa_interp = "moderate"
    elif kappa >= 0.21:
        kappa_interp = "fair"
    else:
        kappa_interp = "slight/poor"
    print(f"    Interpretation: {kappa_interp} agreement")

    # ── 6. Confidence calibration ──
    calibration = confidence_calibration(entities)
    print(f"\n  CONFIDENCE CALIBRATION:")
    print(f"    {'Bin':<15s} {'n':>5s} {'Agreement':>10s}")
    for c in calibration:
        print(f"    {c['bin']:<15s} {c['n']:>5d} {c['agreement_rate']:>10.1%}")

    # ── 7. Error taxonomy ──
    error_data = compute_error_taxonomy(entities)
    print(f"\n  ERROR TAXONOMY ({error_data['total_errors']} errors):")
    print(f"    By category:")
    for cat, count in sorted(error_data["by_category"].items(), key=lambda x: -x[1]):
        print(f"      {cat:<25s} {count:>4d}")
    print(f"    By entity type:")
    for etype, verdicts in sorted(error_data["by_entity_type"].items()):
        parts = ", ".join(f"{v}={c}" for v, c in sorted(verdicts.items()))
        print(f"      {etype:<20s} {parts}")

    # ── 8. Per-paper summaries ──
    paper_summaries = per_paper_summary(entities)
    print(f"\n  PER-PAPER F1 SCORES:")
    print(f"    {'Paper':<35s} {'Tier':<10s} {'n':>4s} {'P':>7s} {'R':>7s} {'F1':>7s} {'LLM Agr':>8s}")
    print(f"    {'-'*80}")
    for p in sorted(paper_summaries, key=lambda x: -x["f1"]):
        print(f"    {p['paper_id']:<35s} {p['tier']:<10s} {p['n_entities']:>4d} "
              f"{p['precision']:>7.1%} {p['recall']:>7.1%} {p['f1']:>7.1%} {p['llm_agreement_rate']:>8.1%}")

    # ── 9. Generate figures ──
    print(f"\n  Generating figures...")
    generate_figures(entities, paper_summaries, confusion, calibration, error_data)

    # ── 10. Generate LaTeX tables ──
    print(f"\n  Generating LaTeX tables...")
    latex_tables = generate_latex_tables(prf_by_type, prf_by_tier, prf_overall, confusion, kappa, calibration)
    for name, content in latex_tables.items():
        path = OUT_DIR / f"{name}.tex"
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"    {name}.tex saved")

    # ── 11. Save comprehensive JSON ──
    results = {
        "generated_at": datetime.now().isoformat(),
        "dataset": {
            "total_papers": len(papers),
            "total_entities": len(entities),
            "tiers": {t: len(by_tier.get(t, [])) for t in TIERS},
            "entity_types": {t: len(by_type.get(t, [])) for t in ENTITY_TYPES},
        },
        "extraction_quality": {
            "overall": prf_overall,
            "by_entity_type": prf_by_type,
            "by_tier": prf_by_tier,
        },
        "llm_vs_human": {
            "confusion": confusion,
            "cohens_kappa": kappa,
            "kappa_interpretation": kappa_interp,
            "confidence_calibration": calibration,
        },
        "error_taxonomy": error_data,
        "per_paper": paper_summaries,
    }

    json_path = OUT_DIR / "golden_dataset_metrics.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\n  Full metrics saved to: {json_path}")

    # ── Summary ──
    print(f"\n{'='*66}")
    print(f"  SUMMARY FOR JCIM PAPER")
    print(f"{'='*66}")
    print(f"  Dataset: 30 papers, {len(entities)} entities")
    print(f"    Simple: {len(by_tier.get('simple',[]))} entities from 10 papers")
    print(f"    Moderate: {len(by_tier.get('moderate',[]))} entities from 10 papers")
    print(f"    Complex: {len(by_tier.get('complex',[]))} entities from 10 papers")
    print(f"")
    print(f"  Extraction Quality (Human-Verified):")
    print(f"    Overall Precision: {prf_overall['precision']:.1%}")
    print(f"    Overall Recall:    {prf_overall['recall']:.1%}")
    print(f"    Overall F1:        {prf_overall['f1']:.1%}")
    print(f"")
    print(f"  LLM Verifier Performance:")
    print(f"    Agreement with human: {confusion['agreement_rate']:.1%}")
    print(f"    Cohen's kappa:        {kappa:.3f} ({kappa_interp})")
    print(f"    False negative rate:  {confusion['false_neg_rate']:.1%} (missed errors)")
    print(f"    False positive rate:  {confusion['false_pos_rate']:.1%} (over-flagged)")
    print(f"")
    print(f"  Output files:")
    print(f"    {OUT_DIR / 'golden_dataset_metrics.json'}")
    print(f"    {OUT_DIR / 'figures/'}")
    print(f"    {OUT_DIR / '*.tex'}")
    print(f"{'='*66}")


if __name__ == "__main__":
    main()
