"""Generate light-themed figures for docs/report.html and embed them as base64.

Reads the current results/*.json (seed 42) and produces two figures that match the
report's light aesthetic and its data-validity stance (turn/combat/synergy only — run-level
is excluded because its on-disk numbers are pre-fix). The PNGs are base64-embedded directly
into docs/report.html (placeholders FIG_SCORES and FIG_ARCHETYPE), keeping the report a
single self-contained, emailable file. Re-run after new results land.
"""
import base64
import io
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RESULTS = os.path.join(ROOT, "results")
REPORT = os.path.join(HERE, "report.html")

# Light palette matching report.html
INK = "#1d2330"
SOFT = "#5b6473"
LINE = "#e4e7ec"
GOOD = "#1f9d6b"
WARN = "#c8881d"
BAD = "#d24b3a"
SERIES = ["#3b6fd4", "#7aa2e3", "#e0a13a", "#e6c27a"]  # llama-s, llama-r, scout-s, scout-r

plt.rcParams.update({
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "savefig.facecolor": "white",
    "text.color": INK,
    "axes.labelcolor": INK,
    "axes.edgecolor": LINE,
    "xtick.color": SOFT,
    "ytick.color": SOFT,
    "font.size": 11,
    "axes.spines.top": False,
    "axes.spines.right": False,
})

FILES = {
    "llama-s": "llama-3.1-8b-instant_structured_seed42.json",
    "llama-r": "llama-3.1-8b-instant_raw_seed42.json",
    "scout-s": "meta-llama-llama-4-scout-17b-16e-instruct_structured_seed42.json",
    "scout-r": "meta-llama-llama-4-scout-17b-16e-instruct_raw_seed42.json",
}


def load(key):
    with open(os.path.join(RESULTS, FILES[key]), encoding="utf-8") as f:
        return json.load(f)


def fig_to_datauri(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return "data:image/png;base64," + b64


def make_scores():
    data = {k: load(k) for k in FILES}
    metrics = [
        ("Turn\ndamage ratio", lambda d: d["turn"]["avg_damage_ratio"]),
        ("Combat\nHP ratio", lambda d: d["combat"]["avg_hp_ratio"]),
        ("Synergy\narchetype", lambda d: d["synergy"]["archetype_acc"]),
        ("Synergy\ncard pick", lambda d: d["synergy"]["card_pick_acc"]),
        ("Removal-v1\ndiagnostic*", lambda d: d["synergy"]["removal_acc"]),
    ]
    labels = ["llama-8b · struct", "llama-8b · raw", "scout-17b · struct", "scout-17b · raw"]
    keys = list(FILES)
    n_groups = len(metrics)
    n_bars = len(keys)
    width = 0.78 / n_bars

    fig, ax = plt.subplots(figsize=(9, 4.6))
    for bi, k in enumerate(keys):
        d = data[k]
        vals = [m[1](d) for m in metrics]
        xs = [g + (bi - (n_bars - 1) / 2) * width for g in range(n_groups)]
        bars = ax.bar(xs, vals, width=width, color=SERIES[bi], label=labels[bi],
                      edgecolor="white", linewidth=.6)
        for x, v in zip(xs, vals):
            ax.text(x, v + 0.015, f"{v*100:.0f}", ha="center", va="bottom",
                    fontsize=7.5, color=SOFT)

    ax.axhline(1.0, color=LINE, lw=1, ls="--", zorder=0)
    ax.set_xticks(range(n_groups))
    ax.set_xticklabels([m[0] for m in metrics], fontsize=9.5)
    ax.set_ylabel("Score (0–1; combat HP ratio may exceed 1)")
    ax.set_ylim(0, 1.25)
    ax.set_yticks([0, .25, .5, .75, 1.0])
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, 1.16), ncol=4,
              frameon=False, fontsize=9, handlelength=1.1, columnspacing=1.4)
    ax.grid(axis="y", color=LINE, lw=.8)
    ax.set_axisbelow(True)
    return fig_to_datauri(fig)


def make_archetype():
    # 8 attempts each (2 decks x 2 models x 2 formats). Counted from the per-sample audits.
    arche = ["Aggro", "Block", "Strength", "Exhaust"]
    correct = [8, 7, 2, 0]
    colors = [GOOD, GOOD, WARN, BAD]

    fig, ax = plt.subplots(figsize=(7.6, 3.1))
    bars = ax.barh(arche[::-1], [c for c in correct[::-1]],
                   color=colors[::-1], edgecolor="white", linewidth=.8, height=.62)
    for y, c in enumerate(correct[::-1]):
        ax.text(c + 0.12, y, f"{c}/8", va="center", ha="left", fontsize=10,
                color=INK, fontweight="bold")
    ax.set_xlim(0, 8.8)
    ax.set_xticks(range(0, 9, 2))
    ax.set_xlabel("Decks identified correctly (out of 8 attempts)")
    ax.grid(axis="x", color=LINE, lw=.8)
    ax.set_axisbelow(True)
    ax.tick_params(axis="y", length=0)
    for s in ("left",):
        ax.spines[s].set_color(LINE)
    return fig_to_datauri(fig)


def main():
    scores = make_scores()
    archetype = make_archetype()
    with open(REPORT, encoding="utf-8") as f:
        html = f.read()
    html = html.replace("FIG_SCORES", scores, 1)
    html = html.replace("FIG_ARCHETYPE", archetype, 1)
    with open(REPORT, "w", encoding="utf-8") as f:
        f.write(html)
    print("Embedded 2 figures into", REPORT)
    print("  report size:", round(len(html) / 1024, 1), "KB")


if __name__ == "__main__":
    main()
