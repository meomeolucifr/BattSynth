"""
Generate Paper Figures for BattSynth Dataset Paper
Produces publication-quality figures for JCIM submission.
"""

import csv
import os
from pathlib import Path
from collections import Counter, defaultdict

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import seaborn as sns
import numpy as np

BASE_DIR = Path(r"C:\Users\12124\Downloads\Results_final\Results_final")
DATA_DIR = BASE_DIR / "scripts" / "audit_output"
FIG_DIR = BASE_DIR / "scripts" / "figures"
FIG_DIR.mkdir(parents=True, exist_ok=True)

# Style setup for JCIM
plt.rcParams.update({
    'font.family': 'sans-serif',
    'font.sans-serif': ['Arial', 'DejaVu Sans'],
    'font.size': 10,
    'axes.titlesize': 12,
    'axes.labelsize': 11,
    'xtick.labelsize': 9,
    'ytick.labelsize': 9,
    'legend.fontsize': 9,
    'figure.dpi': 300,
    'savefig.dpi': 300,
    'savefig.bbox': 'tight',
})

COLORS = {
    'Excellent': '#2ecc71',
    'Good': '#3498db',
    'Acceptable': '#f39c12',
    'Poor': '#e74c3c',
}


def load_csv(filename):
    """Load CSV file from data directory."""
    with open(DATA_DIR / filename, 'r', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def fig1_score_distribution():
    """Figure 1: Score distribution histogram."""
    data = load_csv("score_distribution.csv")

    verdicts = [d['verdict'] for d in data if d['verdict'] != 'Unknown']
    counts = [int(d['count']) for d in data if d['verdict'] != 'Unknown']
    colors = [COLORS.get(v, '#95a5a6') for v in verdicts]

    fig, ax = plt.subplots(figsize=(6, 4))
    bars = ax.bar(verdicts, counts, color=colors, edgecolor='white', linewidth=0.5)

    for bar, count in zip(bars, counts):
        ax.text(bar.get_x() + bar.get_width() / 2., bar.get_height() + 5,
                f'{count}', ha='center', va='bottom', fontweight='bold', fontsize=10)

    ax.set_ylabel('Number of Papers')
    ax.set_title('Extraction Quality Score Distribution (N=605)')
    ax.set_ylim(0, max(counts) * 1.15)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    fig.savefig(FIG_DIR / "fig1_score_distribution.png")
    fig.savefig(FIG_DIR / "fig1_score_distribution.pdf")
    plt.close(fig)
    print("  Fig 1: Score distribution")


def fig2_subfield_distribution():
    """Figure 2: Battery subfield distribution (horizontal bar chart)."""
    data = load_csv("subfield_distribution.csv")

    # Sort by count descending
    data = sorted(data, key=lambda x: int(x['count']))
    labels = [d['subfield'] for d in data]
    counts = [int(d['count']) for d in data]

    fig, ax = plt.subplots(figsize=(7, 5))
    colors = sns.color_palette("viridis", len(labels))
    bars = ax.barh(labels, counts, color=colors, edgecolor='white', linewidth=0.5)

    for bar, count in zip(bars, counts):
        ax.text(bar.get_width() + 2, bar.get_y() + bar.get_height() / 2.,
                f'{count}', ha='left', va='center', fontsize=8)

    ax.set_xlabel('Number of Papers')
    ax.set_title('Battery Subfield Distribution')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    fig.savefig(FIG_DIR / "fig2_subfield_distribution.png")
    fig.savefig(FIG_DIR / "fig2_subfield_distribution.pdf")
    plt.close(fig)
    print("  Fig 2: Subfield distribution")


def fig3_year_distribution():
    """Figure 3: Publication year distribution."""
    data = load_csv("year_distribution.csv")

    years = [int(d['year']) for d in data]
    counts = [int(d['count']) for d in data]

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(years, counts, color='#3498db', edgecolor='white', linewidth=0.5, width=0.8)

    ax.set_xlabel('Publication Year')
    ax.set_ylabel('Number of Papers')
    ax.set_title('Publication Year Distribution (N=605)')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    # Only show labels for every 5 years
    ax.set_xticks([y for y in years if y % 5 == 0])

    fig.savefig(FIG_DIR / "fig3_year_distribution.png")
    fig.savefig(FIG_DIR / "fig3_year_distribution.pdf")
    plt.close(fig)
    print("  Fig 3: Year distribution")


def fig4_verification_analysis():
    """Figure 4: Verification audit analysis (multi-panel)."""
    # Load per-section breakdown from detailed audit
    detailed = load_csv("verification_audit_detailed.csv")

    # Panel A: Support rate by section
    sections = defaultdict(lambda: {"supported": 0, "unsupported": 0, "contradictions": 0})
    for row in detailed:
        sec = row['section']
        if row['is_supported'] == 'True':
            sections[sec]["supported"] += 1
        elif row['is_supported'] == 'False':
            sections[sec]["unsupported"] += 1
        if row['contradiction'] in ('contradiction_clear', 'contradiction_mixed'):
            sections[sec]["contradictions"] += 1

    # Panel B: Confidence calibration
    calib = load_csv("confidence_calibration.csv")

    fig, axes = plt.subplots(1, 3, figsize=(15, 5))

    # Panel A: Stacked bar - supported vs unsupported by section
    ax = axes[0]
    sec_names = sorted(sections.keys())
    supported = [sections[s]["supported"] for s in sec_names]
    unsupported = [sections[s]["unsupported"] for s in sec_names]

    x = np.arange(len(sec_names))
    width = 0.6
    ax.bar(x, supported, width, label='Supported', color='#2ecc71', edgecolor='white')
    ax.bar(x, unsupported, width, bottom=supported, label='Unsupported', color='#e74c3c',
           edgecolor='white')

    ax.set_xticks(x)
    ax.set_xticklabels(sec_names, rotation=45, ha='right', fontsize=8)
    ax.set_ylabel('Number of Flags')
    ax.set_title('(a) Verification Flags by Section')
    ax.legend(loc='upper right', fontsize=8)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    # Panel B: Confidence calibration
    ax = axes[1]
    conf_bins = [float(d['confidence_bin']) for d in calib]
    actual_rates = [float(d['actual_support_rate']) for d in calib]
    counts = [int(d['total_count']) for d in calib]

    # Scatter with size proportional to count
    sizes = [max(c / 5, 10) for c in counts]
    scatter = ax.scatter(conf_bins, actual_rates, s=sizes, c='#3498db', alpha=0.7,
                         edgecolors='white', linewidth=0.5)

    # Perfect calibration line
    ax.plot([0, 1], [0, 100], 'k--', alpha=0.3, label='Perfect calibration')
    ax.set_xlabel('LLM Confidence Score')
    ax.set_ylabel('Actual Support Rate (%)')
    ax.set_title('(b) Confidence Calibration')
    ax.set_xlim(0.1, 1.05)
    ax.set_ylim(-5, 105)
    ax.legend(fontsize=8)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    # Panel C: Contradiction rate by section
    ax = axes[2]
    contra_rates = []
    for s in sec_names:
        total = sections[s]["supported"] + sections[s]["unsupported"]
        rate = sections[s]["contradictions"] / total * 100 if total else 0
        contra_rates.append(rate)

    bars = ax.bar(x, contra_rates, width, color='#e67e22', edgecolor='white')
    ax.set_xticks(x)
    ax.set_xticklabels(sec_names, rotation=45, ha='right', fontsize=8)
    ax.set_ylabel('Contradiction Rate (%)')
    ax.set_title('(c) Verifier Contradiction Rate')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    # Add percentage labels
    for bar, rate in zip(bars, contra_rates):
        if rate > 0:
            ax.text(bar.get_x() + bar.get_width() / 2., bar.get_height() + 0.3,
                    f'{rate:.1f}%', ha='center', va='bottom', fontsize=7)

    plt.tight_layout()
    fig.savefig(FIG_DIR / "fig4_verification_analysis.png")
    fig.savefig(FIG_DIR / "fig4_verification_analysis.pdf")
    plt.close(fig)
    print("  Fig 4: Verification analysis (3 panels)")


def fig5_characterization_methods():
    """Figure 5: Top characterization methods."""
    data = load_csv("characterization_methods.csv")

    # Take top 15
    data = data[:15]
    methods = [d['method'] for d in data]
    counts = [int(d['count']) for d in data]

    fig, ax = plt.subplots(figsize=(7, 5))
    colors = sns.color_palette("Blues_r", len(methods))
    y_pos = np.arange(len(methods))
    ax.barh(y_pos, counts, color=colors, edgecolor='white', linewidth=0.5)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(methods, fontsize=8)
    ax.invert_yaxis()
    ax.set_xlabel('Frequency')
    ax.set_title('Top 15 Characterization Methods')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    for i, count in enumerate(counts):
        ax.text(count + 1, i, str(count), va='center', fontsize=8)

    fig.savefig(FIG_DIR / "fig5_characterization_methods.png")
    fig.savefig(FIG_DIR / "fig5_characterization_methods.pdf")
    plt.close(fig)
    print("  Fig 5: Characterization methods")


def fig6_high_vs_low_comparison():
    """Figure 6: High vs Low group comparison from verification audit."""
    detailed = load_csv("verification_audit_detailed.csv")

    # Compare high vs low group
    groups = {"high": defaultdict(int), "low": defaultdict(int)}
    for row in detailed:
        g = row['group']
        groups[g]["total"] += 1
        if row['is_supported'] == 'True':
            groups[g]["supported"] += 1
        if row['contradiction'] in ('contradiction_clear', 'contradiction_mixed'):
            groups[g]["contradictions"] += 1

    fig, axes = plt.subplots(1, 2, figsize=(10, 4))

    # Panel A: Support rates
    ax = axes[0]
    labels = ['High (100%)', 'Low (74-79%)']
    support_rates = [
        groups['high']['supported'] / groups['high']['total'] * 100,
        groups['low']['supported'] / groups['low']['total'] * 100,
    ]
    bars = ax.bar(labels, support_rates, color=['#2ecc71', '#e74c3c'],
                  edgecolor='white', width=0.5)
    ax.set_ylabel('Verification Support Rate (%)')
    ax.set_title('(a) LLM Verification Support Rate')
    ax.set_ylim(0, 100)
    for bar, rate in zip(bars, support_rates):
        ax.text(bar.get_x() + bar.get_width() / 2., bar.get_height() + 1,
                f'{rate:.1f}%', ha='center', va='bottom', fontweight='bold')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    # Panel B: Contradiction rates
    ax = axes[1]
    contra_rates = [
        groups['high']['contradictions'] / groups['high']['total'] * 100,
        groups['low']['contradictions'] / groups['low']['total'] * 100,
    ]
    bars = ax.bar(labels, contra_rates, color=['#f39c12', '#e67e22'],
                  edgecolor='white', width=0.5)
    ax.set_ylabel('Contradiction Rate (%)')
    ax.set_title('(b) Verifier Contradiction Rate')
    ax.set_ylim(0, max(contra_rates) * 1.4)
    for bar, rate in zip(bars, contra_rates):
        ax.text(bar.get_x() + bar.get_width() / 2., bar.get_height() + 0.2,
                f'{rate:.1f}%', ha='center', va='bottom', fontweight='bold')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    plt.tight_layout()
    fig.savefig(FIG_DIR / "fig6_high_vs_low.png")
    fig.savefig(FIG_DIR / "fig6_high_vs_low.pdf")
    plt.close(fig)
    print("  Fig 6: High vs Low comparison")


def fig7_journal_distribution():
    """Figure 7: Top journals pie chart."""
    data = load_csv("journal_distribution.csv")

    # Top 10 + Others
    top_n = 10
    top_data = data[:top_n]
    other_count = sum(int(d['count']) for d in data[top_n:])

    labels = [d['journal'] for d in top_data] + ['Others']
    sizes = [int(d['count']) for d in top_data] + [other_count]

    fig, ax = plt.subplots(figsize=(8, 6))
    colors = sns.color_palette("Set3", len(labels))
    wedges, texts, autotexts = ax.pie(sizes, labels=None, autopct='%1.1f%%',
                                       colors=colors, pctdistance=0.85,
                                       textprops={'fontsize': 8})

    ax.legend(labels, loc='center left', bbox_to_anchor=(1, 0.5), fontsize=8)
    ax.set_title('Journal Distribution (Top 10)')

    fig.savefig(FIG_DIR / "fig7_journal_distribution.png")
    fig.savefig(FIG_DIR / "fig7_journal_distribution.pdf")
    plt.close(fig)
    print("  Fig 7: Journal distribution")


def main():
    print("Generating figures...")
    fig1_score_distribution()
    fig2_subfield_distribution()
    fig3_year_distribution()
    fig4_verification_analysis()
    fig5_characterization_methods()
    fig6_high_vs_low_comparison()
    fig7_journal_distribution()
    print(f"\nAll figures saved to: {FIG_DIR}")


if __name__ == "__main__":
    main()
