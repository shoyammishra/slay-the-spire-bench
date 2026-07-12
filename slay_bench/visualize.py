"""Save benchmark results as PNG charts and a human-readable text report."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple


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
    seed_val = summary.get("seeds") or summary.get("seed", "?")
    a(f"  Seed    : {seed_val}")
    elapsed = summary.get("elapsed_seconds")
    a(f"  Elapsed : {elapsed}s" if elapsed is not None else "  Elapsed : —")
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
        # hp_ratio can exceed 1.0 — raise the top so bars aren't clipped
        top = max(vals + [1.0])
        if top > 0.93:  # leave headroom for the % labels
            ax.set_ylim(0, max(1.05, top + 0.12))
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
    # Radar axes are fixed 0–1; hp_ratio >1 would spill outside the chart
    values = [min(1.0, v) for v in values]

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
        f"{summary['model']}\n{summary['prompt_format']} · seed {summary.get('seeds') or summary.get('seed', '?')}\n"
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


# ── Horizon-collapse curve + cross-horizon normalization ──────────────────────
#
# The four benchmark dimensions live in different units (turn = damage_ratio vs an
# exhaustive optimum; combat = win_rate / hp_ratio vs a greedy bot; synergy = three
# accuracies vs chance; run = progress vs greedy survival). To draw one line per model
# over the planning-horizon x-axis (turn → combat → synergy → run) they must first be
# rescaled onto a common "vs-baseline" 0–1 axis where 0 = the non-planning floor for
# that dimension and 1 = perfect play. The exact formulas + rationale + limitations are
# documented in docs/decision_log.md (2026-07-12 entry). Summary:
#
#   turn    = avg_damage_ratio                       (already 0–1 vs exhaustive oracle)
#   combat  = win_rate * min(1, hp_ratio)            (greedy bot ≈ 1.0; losers → 0)
#   synergy = mean over {archetype, pick, removal} of
#             clamp01((acc - chance) / (1 - chance)) (chance floor per metric → 0)
#   run     = clamp01((progress - GREEDY_PROGRESS) / (1 - GREEDY_PROGRESS))
#                                                    (greedy Act-1 survival → 0)
#
# Missing dimensions (qwen3-32b non-synergy; deepseek run) stay None and BREAK the line
# — never interpolated, never invented.

HORIZONS: List[str] = ["turn", "combat", "synergy", "run"]
HORIZON_LABELS = ["Turn\n(1 turn)", "Combat\n(1 fight)",
                  "Synergy\n(deck)", "Run\n(full act)"]

# Chance / baseline floors used by the normalization (documented in decision_log).
SYNERGY_CHANCE = {
    "archetype_acc": 0.25,   # 4 archetypes, uniform
    "card_pick_acc": 1.0 / 3.0,  # 3 offers, correct index rotated uniformly
    "removal_acc": 0.10,     # removal target = 1 basic among ~10-card fixture deck
}
# Greedy bot survives ~12.5 / 16 nodes of Act 1 → progress ≈ 0.78 is the run floor.
GREEDY_PROGRESS = 0.78


def _clamp01(v: float) -> float:
    return max(0.0, min(1.0, v))


def _norm_turn(turn: Optional[dict]) -> Optional[float]:
    if not turn or turn.get("avg_damage_ratio_mean") is None:
        return None
    # Already 0–1 vs the exhaustive optimum. Floor 0 = illegal/no damage, 1 = oracle.
    return _clamp01(turn["avg_damage_ratio_mean"])


def _norm_combat(combat: Optional[dict]) -> Optional[float]:
    if not combat or combat.get("win_rate_mean") is None:
        return None
    win = combat["win_rate_mean"]
    hp = combat.get("avg_hp_ratio_mean")
    # Center on the greedy bot: hp_ratio ≥ 1 (match or beat the bot's HP) counts full;
    # taking more damage than the bot scales the win down. A model that loses fights
    # drops toward 0. The greedy bot itself → win 1 · hp_ratio 1 ≈ 1.0 (Act 1 is
    # winnable by greedy play, so this dimension's baseline sits near the ceiling —
    # the collapse signal is dropping BELOW it, which only the reasoning models do).
    hp_factor = 1.0 if hp is None else _clamp01(hp)
    return _clamp01(win * hp_factor)


def _norm_synergy(syn: Optional[dict]) -> Optional[float]:
    if not syn:
        return None
    parts = []
    for key, chance in SYNERGY_CHANCE.items():
        acc = syn.get(f"{key}_mean")
        if acc is None:
            continue
        # Rescale so chance → 0, perfect (1.0) → 1. Below chance clamps to 0.
        parts.append(_clamp01((acc - chance) / (1.0 - chance)))
    if not parts:
        return None
    return sum(parts) / len(parts)


def _norm_run(run: Optional[dict]) -> Optional[float]:
    if not run or run.get("avg_progress_mean") is None:
        return None
    prog = run["avg_progress_mean"]
    # Greedy Act-1 survival floor → 0, full act (progress 1.0) → 1.
    return _clamp01((prog - GREEDY_PROGRESS) / (1.0 - GREEDY_PROGRESS))


_NORMALIZERS = {
    "turn": lambda a: _norm_turn(a.get("turn")),
    "combat": lambda a: _norm_combat(a.get("combat")),
    "synergy": lambda a: _norm_synergy(a.get("synergy")),
    "run": lambda a: _norm_run(a.get("run")),
}


def normalized_horizon_vector(agg: Dict[str, Any]) -> List[Optional[float]]:
    """Return [turn, combat, synergy, run] normalized to the common 0–1 axis.

    Each entry is None where the dimension was not evaluated (missing cell) — callers
    must break the line there, never interpolate.
    """
    return [_NORMALIZERS[h](agg) for h in HORIZONS]


def _discover_aggregates(results_dir: Path, fmt: str) -> List[Tuple[str, str, dict]]:
    """Find multi-seed aggregate JSONs for one prompt format.

    Returns a list of (model, character, agg_dict), sorted for stable colouring.
    Only files whose prompt_format matches `fmt` are returned.
    """
    out = []
    for path in sorted(results_dir.glob("*_seeds42_1042_2042_3042_4042.json")):
        try:
            agg = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if agg.get("prompt_format") != fmt:
            continue
        model = agg.get("model", path.stem)
        character = agg.get("character", "ironclad")
        out.append((model, character, agg))
    # stable, readable order: by model name then character
    out.sort(key=lambda t: (t[0], t[1]))
    return out


# distinct, colour-blind-ish palette for up to 6 model lines on the dark theme
_MODEL_COLORS = [
    "#4ade80",  # green   — qwen2.5-7b
    "#60a5fa",  # blue    — llama-3.1-8b
    "#f472b6",  # pink    — mistral-7b
    "#facc15",  # yellow  — qwen3-32b (reasoning, the line that bends away)
    "#fb923c",  # orange  — deepseek-14b
    "#a78bfa",  # purple  — deepseek-7b
]


def horizon_collapse_curve(results_dir: Path,
                           out_path: Path,
                           fmt: str = "structured") -> None:
    """Render the horizon-collapse curve for one prompt format.

    Two panels (Ironclad / Silent). x-axis = planning horizon (turn→combat→synergy→run),
    y-axis = normalized "vs-baseline" score (0 = non-planning floor, 1 = perfect). One
    line per model; gaps (unevaluated dimensions) break the line rather than interpolate.
    Reads only the on-disk multi-seed aggregates — no engine/harness state touched.
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        print("  [warn] matplotlib not installed — skipping horizon curve.")
        return

    aggs = _discover_aggregates(results_dir, fmt)
    if not aggs:
        print(f"  [warn] no {fmt} aggregates found in {results_dir}")
        return

    # group by character
    by_char: Dict[str, List[Tuple[str, dict]]] = {"ironclad": [], "silent": []}
    for model, char, agg in aggs:
        by_char.setdefault(char, []).append((model, agg))

    # deterministic colour per model across both panels
    all_models = sorted({m for m, _, _ in aggs})
    color_of = {m: _MODEL_COLORS[i % len(_MODEL_COLORS)]
                for i, m in enumerate(all_models)}

    COLOR_BG = "#16213e"
    COLOR_AXIS = "#e2e8f0"

    chars = [c for c in ("ironclad", "silent") if by_char.get(c)]
    fig, axes = plt.subplots(1, len(chars), figsize=(6.4 * len(chars), 5.4),
                             squeeze=False)
    axes = axes[0]
    fig.patch.set_facecolor("#1a1a2e")
    fig.suptitle(
        f"Horizon-Collapse Curve  —  {fmt} prompts\n"
        "normalized planning score (0 = non-planning floor, 1 = perfect) "
        "vs planning horizon",
        color="white", fontsize=12, fontweight="bold", y=0.99)

    x = list(range(len(HORIZONS)))
    printed = {}  # for the caller's sanity-check log
    for ax, char in zip(axes, chars):
        ax.set_facecolor(COLOR_BG)
        ax.set_title(char.capitalize(), color=COLOR_AXIS, fontsize=11,
                     fontweight="bold", pad=8)
        # baseline floor line at y=0
        ax.axhline(0.0, color="#64748b", linewidth=1.0, linestyle="--", zorder=1)
        ax.text(len(HORIZONS) - 1, 0.012, "non-planning floor",
                color="#94a3b8", fontsize=7, ha="right", va="bottom")

        for model, agg in sorted(by_char[char], key=lambda t: t[0]):
            vec = normalized_horizon_vector(agg)
            printed[(char, model)] = vec
            col = color_of[model]
            # plot as one line, but break across None gaps using NaN
            ys = [np.nan if v is None else v for v in vec]
            ax.plot(x, ys, color=col, linewidth=2.0, marker="o", markersize=6,
                    label=model, zorder=3)
            # mark evaluated-but-isolated points (e.g. qwen3-32b: synergy only)
            for xi, v in zip(x, vec):
                if v is not None:
                    ax.plot(xi, v, marker="o", markersize=6, color=col, zorder=4)

        ax.set_xticks(x)
        ax.set_xticklabels(HORIZON_LABELS, color=COLOR_AXIS, fontsize=8)
        ax.set_ylim(-0.03, 1.05)
        ax.set_ylabel("normalized score (vs baseline)", color=COLOR_AXIS, fontsize=8)
        ax.tick_params(colors=COLOR_AXIS, labelsize=8)
        ax.yaxis.grid(True, color="#334155", zorder=0)
        for spine in ax.spines.values():
            spine.set_edgecolor("#334155")

    # single shared legend
    handles, labels = axes[0].get_legend_handles_labels()
    # dedupe while preserving order
    seen = set()
    hl = [(h, l) for h, l in zip(handles, labels) if not (l in seen or seen.add(l))]
    if hl:
        fig.legend([h for h, _ in hl], [l for _, l in hl],
                   loc="lower center", ncol=min(6, len(hl)),
                   facecolor=COLOR_BG, edgecolor="#334155",
                   labelcolor=COLOR_AXIS, fontsize=8, bbox_to_anchor=(0.5, -0.02))

    plt.tight_layout(rect=[0, 0.06, 1, 0.93])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"  Horizon curve ({fmt}) : {out_path}")

    # emit the normalized matrix for sanity-checking against the CLAUDE.md tables
    for (char, model), vec in sorted(printed.items()):
        cells = " ".join(f"{h}={'--' if v is None else f'{v:.3f}'}"
                         for h, v in zip(HORIZONS, vec))
        print(f"    [{fmt}/{char:8s}] {model:24s} {cells}")


def render_horizon_curves(results_dir: Path) -> None:
    """Render both the structured (primary) and raw (companion) horizon curves."""
    horizon_collapse_curve(results_dir, results_dir / "horizon_collapse_structured.png",
                           fmt="structured")
    horizon_collapse_curve(results_dir, results_dir / "horizon_collapse_raw.png",
                           fmt="raw")


# ── CLI entry ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="slay-bench visualization utilities")
    parser.add_argument("--horizon-curve", action="store_true",
                        help="render the horizon-collapse curve(s) from the on-disk "
                             "multi-seed aggregates in results/")
    parser.add_argument("--results-dir", default="results",
                        help="directory holding the *_seeds…json aggregates")
    args = parser.parse_args()

    if args.horizon_curve:
        render_horizon_curves(Path(args.results_dir))
    else:
        parser.print_help()
