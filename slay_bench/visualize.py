"""Save benchmark results as PNG charts and a human-readable text report."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Dict, Any


# ── Text report ───────────────────────────────────────────────────────────────

def _pct(v) -> str:
    return f"{v*100:.1f}%" if v is not None else "N/A"

def _bar(v, width=20) -> str:
    if v is None:
        return "[" + "?" * width + "]"
    filled = round(v * width)
    return "[" + "#" * filled + "-" * (width - filled) + "]"

def _rating(v) -> str:
    if v is None: return ""
    if v >= 0.8:  return "EXCELLENT"
    if v >= 0.6:  return "GOOD"
    if v >= 0.4:  return "FAIR"
    if v >= 0.2:  return "POOR"
    return "VERY POOR"


def write_text_report(summary: Dict[str, Any], out_path: Path) -> None:
    """Write a human-readable .txt report from a benchmark summary dict."""
    lines = []
    a = lines.append

    a("=" * 60)
    a("  SLAY THE SPIRE  —  LLM BENCHMARK REPORT")
    a("=" * 60)
    a(f"  Model   : {summary['model']}")
    a(f"  Format  : {summary['prompt_format']}")
    a(f"  Seed    : {summary['seed']}")
    a(f"  Elapsed : {summary['elapsed_seconds']}s")
    a("")

    # Turn
    t = summary.get("turn")
    a("─" * 60)
    a("  1. TURN-LEVEL  (can the model find the best card sequence?)")
    a("─" * 60)
    if t:
        a(f"  Samples          : {t['n']}")
        a(f"  Damage ratio     : {_bar(t['avg_damage_ratio'])}  {_pct(t['avg_damage_ratio'])}  {_rating(t['avg_damage_ratio'])}")
        a(f"  Parse success    : {_bar(t['parse_ok_rate'])}  {_pct(t['parse_ok_rate'])}")
        a(f"  Legal plays      : {_bar(t['legal_rate'])}  {_pct(t['legal_rate'])}")
        a("")
        a("  Damage ratio = LLM damage / greedy-optimal damage.")
        a("  1.0 means the model found the best possible sequence.")
    else:
        a("  (not evaluated)")
    a("")

    # Combat
    c = summary.get("combat")
    a("─" * 60)
    a("  2. COMBAT-LEVEL  (can the model win a full fight?)")
    a("─" * 60)
    if c:
        a(f"  Samples          : {c['n']}")
        a(f"  Win rate         : {_bar(c['win_rate'])}  {_pct(c['win_rate'])}  {_rating(c['win_rate'])}")
        a(f"  HP ratio vs bot  : {_bar(c['avg_hp_ratio'])}  {_pct(c['avg_hp_ratio'])}  {_rating(c['avg_hp_ratio'])}")
        a(f"  Avg parse errors : {c['avg_parse_errors']:.2f}")
        a("")
        a("  HP ratio = LLM hp remaining / greedy-bot hp remaining.")
        a("  >1.0 means the LLM took less damage than the baseline bot.")
    else:
        a("  (not evaluated)")
    a("")

    # Synergy
    s = summary.get("synergy")
    a("─" * 60)
    a("  3. SYNERGY  (does the model understand the deck's strategy?)")
    a("─" * 60)
    if s:
        a(f"  Samples          : {s['n']}")
        a(f"  Archetype acc    : {_bar(s['archetype_acc'])}  {_pct(s['archetype_acc'])}  {_rating(s['archetype_acc'])}")
        a(f"  Best card acc    : {_bar(s['card_pick_acc'])}  {_pct(s['card_pick_acc'])}  {_rating(s['card_pick_acc'])}")
        a(f"  Removal acc      : {_bar(s.get('removal_acc'))}  {_pct(s.get('removal_acc'))}  {_rating(s.get('removal_acc'))}")
        a(f"  Parse success    : {_bar(s['parse_ok_rate'])}  {_pct(s['parse_ok_rate'])}")
    else:
        a("  (not evaluated)")
    a("")

    # Run
    r = summary.get("run")
    a("─" * 60)
    a("  4. RUN-LEVEL  (can the model survive a full act?)")
    a("─" * 60)
    if r:
        a(f"  Samples          : {r['n']}")
        a(f"  Survival rate    : {_bar(r['survival_rate'])}  {_pct(r['survival_rate'])}  {_rating(r['survival_rate'])}")
        a(f"  Progress         : {_bar(r['avg_progress'])}  {_pct(r['avg_progress'])}  {_rating(r['avg_progress'])}")
        a(f"  HP fraction      : {_bar(r['avg_hp_fraction'])}  {_pct(r['avg_hp_fraction'])}  (survivors only)")
        a(f"  Draft coherence  : {_bar(r['avg_draft_coherence'])}  {_pct(r['avg_draft_coherence'])}  {_rating(r['avg_draft_coherence'])}")
        a(f"  Avg floors       : {r['avg_floors_reached']:.1f}")
    else:
        a("  (not evaluated)")
    a("")

    # Overall score
    scores = []
    if t:   scores.append(t["avg_damage_ratio"] or 0)
    if c:   scores.append(c["win_rate"] or 0)
    if s:
        sub = [v for v in [s.get("archetype_acc"), s.get("card_pick_acc"),
                            s.get("removal_acc")] if v is not None]
        if sub: scores.append(sum(sub) / len(sub))
    if r:   scores.append(r["survival_rate"] or 0)

    if scores:
        overall = sum(scores) / len(scores)
        a("=" * 60)
        a(f"  OVERALL SCORE  : {_bar(overall, 30)}  {_pct(overall)}  {_rating(overall)}")
        a("=" * 60)

    out_path.write_text("\n".join(lines), encoding="utf-8")


# ── PNG charts ────────────────────────────────────────────────────────────────

def write_charts(summary: Dict[str, Any], out_path: Path) -> None:
    """Write a 2×2 PNG chart grid from a benchmark summary dict."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches
        import numpy as np
    except ImportError:
        print("  [warn] matplotlib not installed — skipping charts. pip install matplotlib")
        return

    fig, axes = plt.subplots(2, 2, figsize=(12, 9))
    fig.patch.set_facecolor("#1a1a2e")
    model_label = f"{summary['model']} ({summary['prompt_format']})"
    fig.suptitle(f"Slay the Spire LLM Benchmark\n{model_label}",
                 color="white", fontsize=13, fontweight="bold", y=0.98)

    COLOR_GOOD  = "#4ade80"
    COLOR_MID   = "#facc15"
    COLOR_BAD   = "#f87171"
    COLOR_BG    = "#16213e"
    COLOR_AXIS  = "#e2e8f0"

    def bar_color(v):
        if v is None: return COLOR_BAD
        if v >= 0.6: return COLOR_GOOD
        if v >= 0.3: return COLOR_MID
        return COLOR_BAD

    def style_ax(ax, title):
        ax.set_facecolor(COLOR_BG)
        ax.set_title(title, color=COLOR_AXIS, fontsize=10, fontweight="bold", pad=8)
        ax.tick_params(colors=COLOR_AXIS, labelsize=8)
        for spine in ax.spines.values():
            spine.set_edgecolor("#334155")
        ax.set_ylim(0, 1.05)
        ax.axhline(1.0, color="#334155", linewidth=0.8, linestyle="--")

    def draw_bars(ax, labels, values, title):
        style_ax(ax, title)
        colors = [bar_color(v) for v in values]
        vals   = [v if v is not None else 0 for v in values]
        bars   = ax.bar(labels, vals, color=colors, width=0.55, zorder=3)
        ax.yaxis.grid(True, color="#334155", zorder=0)
        for bar, v in zip(bars, values):
            if v is not None:
                ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.02,
                        f"{v*100:.0f}%", ha="center", va="bottom",
                        color=COLOR_AXIS, fontsize=8, fontweight="bold")
        ax.set_ylabel("Score (0–1)", color=COLOR_AXIS, fontsize=8)
        ax.tick_params(axis="x", labelsize=8)

    # ── 1. Turn ───────────────────────────────────────────────────────────────
    t = summary.get("turn")
    if t:
        draw_bars(axes[0, 0],
                  ["Dmg\nRatio", "Parse\nOK", "Legal\nPlays"],
                  [t["avg_damage_ratio"], t["parse_ok_rate"], t["legal_rate"]],
                  "1. Turn-Level  (optimal card sequence?)")
    else:
        axes[0, 0].text(0.5, 0.5, "Not evaluated", ha="center", va="center",
                        transform=axes[0, 0].transAxes, color=COLOR_AXIS)
        style_ax(axes[0, 0], "1. Turn-Level")

    # ── 2. Combat ─────────────────────────────────────────────────────────────
    c = summary.get("combat")
    if c:
        draw_bars(axes[0, 1],
                  ["Win\nRate", "HP Ratio\nvs Bot"],
                  [c["win_rate"], c["avg_hp_ratio"]],
                  "2. Combat-Level  (survive the fight?)")
    else:
        axes[0, 1].text(0.5, 0.5, "Not evaluated", ha="center", va="center",
                        transform=axes[0, 1].transAxes, color=COLOR_AXIS)
        style_ax(axes[0, 1], "2. Combat-Level")

    # ── 3. Synergy ────────────────────────────────────────────────────────────
    s = summary.get("synergy")
    if s:
        draw_bars(axes[1, 0],
                  ["Archetype\nAcc", "Best Card\nAcc", "Removal\nAcc", "Parse\nOK"],
                  [s.get("archetype_acc"), s.get("card_pick_acc"),
                   s.get("removal_acc"), s.get("parse_ok_rate")],
                  "3. Synergy  (deck strategy recognition?)")
    else:
        axes[1, 0].text(0.5, 0.5, "Not evaluated", ha="center", va="center",
                        transform=axes[1, 0].transAxes, color=COLOR_AXIS)
        style_ax(axes[1, 0], "3. Synergy")

    # ── 4. Run ────────────────────────────────────────────────────────────────
    r = summary.get("run")
    if r:
        draw_bars(axes[1, 1],
                  ["Survival\nRate", "Progress\n(floors)", "Draft\nCoherence"],
                  [r["survival_rate"], r.get("avg_progress", 0), r["avg_draft_coherence"]],
                  "4. Run-Level  (full act survival?)")
    else:
        axes[1, 1].text(0.5, 0.5, "Not evaluated", ha="center", va="center",
                        transform=axes[1, 1].transAxes, color=COLOR_AXIS)
        style_ax(axes[1, 1], "4. Run-Level")

    # ── Legend ────────────────────────────────────────────────────────────────
    legend = [
        mpatches.Patch(color=COLOR_GOOD, label="Good (>=60%)"),
        mpatches.Patch(color=COLOR_MID,  label="Fair (30-60%)"),
        mpatches.Patch(color=COLOR_BAD,  label="Poor (<30%)"),
    ]
    fig.legend(handles=legend, loc="lower center", ncol=3,
               facecolor=COLOR_BG, edgecolor="#334155",
               labelcolor=COLOR_AXIS, fontsize=8, bbox_to_anchor=(0.5, 0.01))

    plt.tight_layout(rect=[0, 0.05, 1, 0.95])
    fig.savefig(out_path, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)


# ── Radar / spider chart (overall summary) ────────────────────────────────────

def write_radar(summary: Dict[str, Any], out_path: Path) -> None:
    """Write a radar chart summarising all 4 dimensions in a single PNG."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        return

    t = summary.get("turn") or {}
    c = summary.get("combat") or {}
    s = summary.get("synergy") or {}
    r = summary.get("run") or {}

    def _avg(*vals):
        v = [x for x in vals if x is not None]
        return sum(v) / len(v) if v else 0.0

    labels = ["Turn\nDamage", "Combat\nWin Rate", "Synergy\nAccuracy",
              "Run\nSurvival", "HP\nConservation"]
    values = [
        _avg(t.get("avg_damage_ratio")),
        _avg(c.get("win_rate")),
        _avg(s.get("archetype_acc"), s.get("card_pick_acc"), s.get("removal_acc")),
        _avg(r.get("survival_rate"), r.get("avg_progress")),
        _avg(c.get("avg_hp_ratio"), r.get("avg_hp_fraction")),
    ]

    N = len(labels)
    angles = [n / float(N) * 2 * np.pi for n in range(N)]
    angles += angles[:1]
    values_plot = values + values[:1]

    fig, ax = plt.subplots(figsize=(6, 6), subplot_kw=dict(polar=True))
    fig.patch.set_facecolor("#1a1a2e")
    ax.set_facecolor("#16213e")

    ax.plot(angles, values_plot, color="#4ade80", linewidth=2)
    ax.fill(angles, values_plot, color="#4ade80", alpha=0.25)

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labels, color="#e2e8f0", size=9)
    ax.set_ylim(0, 1)
    ax.set_yticks([0.2, 0.4, 0.6, 0.8, 1.0])
    ax.set_yticklabels(["20%","40%","60%","80%","100%"],
                       color="#94a3b8", size=7)
    ax.grid(color="#334155", linewidth=0.8)
    ax.spines["polar"].set_color("#334155")

    overall = sum(values) / len(values)
    ax.set_title(
        f"{summary['model']}\n{summary['prompt_format']} · seed {summary['seed']}\n"
        f"Overall: {overall*100:.1f}%",
        color="white", size=10, fontweight="bold", pad=18)

    fig.savefig(out_path, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)


# ── Entry point ───────────────────────────────────────────────────────────────

def save_all(summary: Dict[str, Any], stem: str, out_dir: Path) -> None:
    """
    Given a summary dict and a stem name (e.g. '20260607_llama_structured_seed42'),
    write three files into out_dir:
      <stem>.txt   — human-readable report
      <stem>.png   — 2×2 bar chart grid
      <stem>_radar.png — spider chart
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    txt_path   = out_dir / f"{stem}.txt"
    bars_path  = out_dir / f"{stem}.png"
    radar_path = out_dir / f"{stem}_radar.png"

    write_text_report(summary, txt_path)
    write_charts(summary, bars_path)
    write_radar(summary, radar_path)

    print(f"  Report : {txt_path}")
    print(f"  Chart  : {bars_path}")
    print(f"  Radar  : {radar_path}")
