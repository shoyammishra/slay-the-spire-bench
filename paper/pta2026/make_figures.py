"""Build the paper's operation-profile figure from canonical aggregates.

This script never modifies benchmark results. It reads the five-seed aggregate
JSON files and the matched-greedy statistical report, then writes a vector PDF.
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "results"
OUT = Path(__file__).resolve().parent / "figures"

MODELS = [
    "qwen2.5-7b",
    "llama-3.1-8b",
    "mistral-7b",
    "deepseek-r1-distill-7b",
    "deepseek-r1-distill-14b",
    "qwen3-32b",
    "qwen3-235b-a22b-fp8",
]

LABELS = [
    "Qwen2.5-7B",
    "Llama-3.1-8B",
    "Mistral-7B",
    "DS-R1-7B",
    "DS-R1-14B",
    "Qwen3-32B",
    "Qwen3-235B-A22B",
]


def mean_or_nan(values: list[float]) -> float:
    return float(np.mean(values)) if values else float("nan")


def load_profiles() -> dict[str, list[float]]:
    aggs: dict[str, list[dict]] = {m: [] for m in MODELS}
    pattern = "*_seeds42_1042_2042_3042_4042.json"
    for path in RESULTS.glob(pattern):
        with path.open("r", encoding="utf-8") as stream:
            item = json.load(stream)
        model = item.get("model")
        if model in aggs:
            aggs[model].append(item)

    with (RESULTS / "stats" / "stats_rigor.json").open("r", encoding="utf-8") as stream:
        stats = json.load(stream)

    profiles = {"turn": [], "combat": [], "pick": [], "run": []}
    for model in MODELS:
        cells = aggs[model]
        profiles["turn"].append(mean_or_nan([
            float(c["turn"]["avg_damage_ratio_mean"])
            for c in cells if c.get("turn", {}).get("avg_damage_ratio_mean") is not None
        ]))
        profiles["combat"].append(mean_or_nan([
            float(c["combat"]["avg_hp_ratio_mean"])
            for c in cells if c.get("combat", {}).get("avg_hp_ratio_mean") is not None
        ]))
        profiles["pick"].append(mean_or_nan([
            float(c["synergy"]["card_pick_acc_mean"])
            for c in cells if c.get("synergy", {}).get("card_pick_acc_mean") is not None
        ]))
        profiles["run"].append(mean_or_nan([
            float(row["mean_diff"])
            for row in stats["run_vs_greedy"]
            if row["model"] == model and row["metric"] == "floors"
        ]))
    return profiles


def draw() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    profiles = load_profiles()

    mpl.rcParams.update({
        "font.family": "DejaVu Sans",
        "font.size": 7.0,
        "axes.titlesize": 7.2,
        "axes.labelsize": 6.8,
        "xtick.labelsize": 6.2,
        "ytick.labelsize": 6.5,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
    })

    fig = plt.figure(figsize=(5.5, 2.35), constrained_layout=False)
    grid = fig.add_gridspec(
        1, 5, width_ratios=[0.92, 0.92, 0.92, 0.92, 1.8],
        left=0.19, right=0.99, top=0.86, bottom=0.18, wspace=0.13,
    )

    specs = [
        ("turn", "Immediate\nsequence", "damage / best", 0.0, 1.0, mpl.cm.Blues),
        ("combat", "Combat\nexecution", "HP / greedy", 0.0, 1.1, mpl.cm.Blues),
        ("pick", "Fixed-deck\ncard choice", "accuracy", 0.0, 0.8, mpl.cm.Blues),
        ("run", "Hybrid\nrollout", "$\\Delta$ floors", -3.0, 1.5, mpl.cm.RdBu),
    ]

    for col, (key, title, unit, lo, hi, cmap) in enumerate(specs):
        ax = fig.add_subplot(grid[0, col])
        vals = np.asarray(profiles[key], dtype=float).reshape(-1, 1)
        masked = np.ma.masked_invalid(vals)
        ax.imshow(masked, cmap=cmap, vmin=lo, vmax=hi, aspect="auto", origin="upper")
        ax.set_title(title, fontweight="bold", pad=5)
        ax.set_xlabel(unit, labelpad=5)
        ax.set_xticks([])
        ax.set_yticks(np.arange(len(MODELS)))
        if col == 0:
            ax.set_yticklabels(LABELS)
        else:
            ax.set_yticklabels([])
        ax.set_xticks(np.arange(-0.5, 1, 1), minor=True)
        ax.set_yticks(np.arange(-0.5, len(MODELS), 1), minor=True)
        ax.grid(which="minor", color="white", linewidth=0.8)
        ax.tick_params(which="minor", bottom=False, left=False)
        ax.tick_params(axis="y", length=0, pad=3)
        for spine in ax.spines.values():
            spine.set_visible(False)
        for row, val in enumerate(vals[:, 0]):
            label = "--" if np.isnan(val) else (f"{val:+.2f}" if key == "run" else f"{val:.2f}")
            if np.isnan(val):
                color = "#555555"
            else:
                norm = (val - lo) / (hi - lo)
                color = "white" if (key != "run" and norm > 0.57) or (key == "run" and abs(norm - 0.5) > 0.35) else "#111111"
            ax.text(0, row, label, ha="center", va="center", color=color, fontsize=6.4,
                    fontweight="bold" if row >= 5 else "normal")

    ax = fig.add_subplot(grid[0, 4])
    deltas = np.asarray([0.2558, 0.1100, 0.2800, 0.2100])
    cells = ["Ironclad / S", "Ironclad / R", "Silent / S", "Silent / R"]
    colors = ["#2d6a9f", "#79a8cf", "#c15a3a", "#e6a07f"]
    y = np.arange(4)
    ax.barh(y, deltas, color=colors, height=0.62)
    ax.axvline(0, color="#333333", linewidth=0.7)
    ax.set_yticks(y)
    ax.set_yticklabels([])
    ax.invert_yaxis()
    ax.set_xlim(0, 0.31)
    ax.set_xticks([0.0, 0.1, 0.2, 0.3])
    ax.set_xlabel("accuracy gain")
    ax.set_title("(b) Qwen3 card-choice gain\n235B-A22B minus 32B", fontweight="bold", pad=5)
    ax.grid(axis="x", color="#dddddd", linewidth=0.6, zorder=0)
    ax.set_axisbelow(True)
    for spine in ["top", "right", "left"]:
        ax.spines[spine].set_visible(False)
    ax.spines["bottom"].set_color("#777777")
    ax.tick_params(axis="y", length=0)
    for yi, val in zip(y, deltas):
        ax.text(0.006, yi, cells[yi], ha="left", va="center", color="#222222",
                fontsize=5.2, fontweight="bold")
        if val < 0.15:
            ax.text(0.17, yi, f"+{val:.2f}", ha="left", va="center",
                    color="#222222", fontsize=6.2, fontweight="bold")
        else:
            ax.text(val - 0.008, yi, f"+{val:.2f}", ha="right", va="center",
                    color="white", fontsize=6.4, fontweight="bold")

    fig.text(0.012, 0.95, "(a)", fontsize=8, fontweight="bold", va="top")
    fig.savefig(OUT / "operation_profile.pdf", bbox_inches="tight", pad_inches=0.01)
    fig.savefig(OUT / "operation_profile.png", dpi=300, bbox_inches="tight", pad_inches=0.01)
    plt.close(fig)
    draw_controlled_h()


def draw_controlled_h() -> None:
    from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

    fig, ax = plt.subplots(figsize=(5.5, 1.18))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    boxes = [
        (0.01, 0.22, 0.25, 0.58, "Frozen fixture", "state $s$, legal actions $A$\nobjective $U$\nresponse contract"),
        (0.34, 0.22, 0.25, 0.58, "Single intervention", "$H \\in \\{1,2,4,8\\}$\nonly prompt byte changed"),
        (0.67, 0.22, 0.32, 0.58, "Paired estimand", "exact $q_H(a)$ for each first action\npaired $H=1$ vs. $H=8$ change"),
    ]
    colors = ["#e9f2f8", "#fff0e8", "#eaf4ea"]
    edges = ["#4d7ea8", "#c76a3d", "#4d8a57"]
    for (x, y, w, h, title, body), face, edge in zip(boxes, colors, edges):
        patch = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.012,rounding_size=0.02",
                               linewidth=1.0, edgecolor=edge, facecolor=face)
        ax.add_patch(patch)
        ax.text(x + w / 2, y + h * 0.70, title, ha="center", va="center",
                fontsize=7.1, fontweight="bold", color="#222222")
        ax.text(x + w / 2, y + h * 0.37, body, ha="center", va="center",
                fontsize=6.0, color="#333333", linespacing=1.18)
    for start, end in [((0.272, 0.51), (0.328, 0.51)), ((0.602, 0.51), (0.658, 0.51))]:
        ax.add_patch(FancyArrowPatch(start, end, arrowstyle="-|>", mutation_scale=9,
                                     linewidth=1.0, color="#555555"))
    ax.text(0.5, 0.04, "MODEL RESULTS: PENDING EXPERIMENT", ha="center", va="bottom",
            fontsize=6.5, fontweight="bold", color="#a33d2a")
    fig.savefig(OUT / "controlled_h_protocol.pdf", bbox_inches="tight", pad_inches=0.01)
    fig.savefig(OUT / "controlled_h_protocol.png", dpi=300, bbox_inches="tight", pad_inches=0.01)
    plt.close(fig)


if __name__ == "__main__":
    draw()
