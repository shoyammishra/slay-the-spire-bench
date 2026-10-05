"""Figures for the ARR paper.

Inputs: results/v3_paper/summary.json (per-model analysis) and results/v3_paper/review/
(churn_*.json transitions, churn_BASELINES.json oracle baselines). One colour code runs
through every figure: orange = the greedy move (best at H=1), blue = the move that is best
eight decisions ahead (H=8), grey = everything else. Palette = validated dataviz slots."""
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / 'figures'
BLUE, ORANGE, GREY, LIGHT = '#2a78d6', '#eb6834', '#b9b8b2', '#e4e3de'
INK, MUTED, GRID = '#1a1a1a', '#5c5b57', '#ecebe7'
plt.rcParams.update({'font.family': 'sans-serif', 'font.sans-serif': ['Arial', 'Helvetica', 'DejaVu Sans'],
                     'font.size': 7.5, 'axes.edgecolor': GREY, 'axes.labelcolor': INK,
                     'xtick.color': MUTED, 'ytick.color': INK, 'axes.spines.top': False,
                     'axes.spines.right': False, 'axes.spines.left': False, 'axes.linewidth': 0.6,
                     'xtick.major.width': 0.6, 'xtick.major.size': 2.5, 'ytick.major.size': 0,
                     'savefig.bbox': 'tight', 'savefig.pad_inches': 0.02, 'pdf.fonttype': 42})

NAMES = {'llama-3.1-8b': 'Llama-3.1-8B', 'mistral-7b': 'Mistral-7B', 'qwen2.5-7b': 'Qwen2.5-7B',
         'llama-3.3-70b-r2': 'Llama-3.3-70B', 'qwen3-8b': 'Qwen3-8B$^\\dagger$', 'qwen3-14b': 'Qwen3-14B',
         'qwen3-32b': 'Qwen3-32B', 'qwen3-32b-nothink': 'Qwen3-32B (no think)', 'gpt-oss-120b': 'gpt-oss-120b'}
ORDER = ['mistral-7b', 'qwen2.5-7b', 'llama-3.1-8b', 'qwen3-8b',
         'llama-3.3-70b-r2', 'qwen3-14b', 'qwen3-32b-nothink', 'qwen3-32b', 'gpt-oss-120b']


def load(name):
    return json.loads((ROOT / 'results/v3_paper' / name).read_text(encoding='utf-8'))


def fig_example():
    """Figure 1: one real state (ironclad-0052); exact action values at H=1 and H=8."""
    acts = ['End turn', 'Feel No Pain', 'Limit Break', 'Pommel Strike', 'Bash']
    panels = [([0, 0, 0, 13, 12], ORANGE, 'Goal 1 decision ahead'),
              ([31, 40, 40, 40, 48], BLUE, 'Goal 8 decisions ahead')]
    fig, axes = plt.subplots(1, 2, figsize=(3.15, 1.5), sharey=True)
    for ax, (vals, col, title) in zip(axes, panels):
        best = max(vals)
        ax.barh(range(len(acts)), vals, color=[col if v == best else LIGHT for v in vals],
                height=0.66, edgecolor='white', linewidth=0.8)
        for i, v in enumerate(vals):
            win = v == best
            ax.text(v + best * 0.04, i, f'{v:g}' + (' best' if win else ''), va='center',
                    fontsize=6.8, color=col if win else MUTED, fontweight='bold' if win else 'normal')
        ax.set_title(title, fontsize=7.2, color=INK, pad=4, fontweight='bold')
        ax.set_xlim(0, best * 1.8)
        ax.set_xticks([])
        ax.spines['bottom'].set_visible(False)
    axes[0].set_yticks(range(len(acts)))
    axes[0].set_yticklabels(acts, fontsize=7)
    fig.savefig(OUT / 'example.pdf')
    plt.close(fig)


def fig_use(summary, baselines):
    """Figure 2: how often the H=8-best move is chosen when told H=8 (arrow head), against the
    model's own H=1 answer (open circle) and a uniformly random legal move (dashed line)."""
    fig, axes = plt.subplots(1, 2, figsize=(3.15, 2.55), sharey=True)
    for ax, char in zip(axes, ('ironclad', 'silent')):
        rnd = baselines[f'{char}_sens']['random_legal_h8opt']
        ax.axvline(rnd, color=MUTED, lw=0.7, ls=(0, (2, 2)), zorder=0)
        ax.text(rnd + 0.007, -0.5, 'random\nmove', fontsize=5.6, color=MUTED,
                ha='left', va='bottom', linespacing=0.95)
        for i, m in enumerate(ORDER):
            c = summary[m][char]['curve']['8']
            sig = c['mc'] is not None and c['mc'] < 0.05 and c['use'] > c['base']
            col = BLUE if sig else GREY
            if abs(c['use'] - c['base']) > 0.012:
                ax.annotate('', xy=(c['use'], i), xytext=(c['base'], i),
                            arrowprops=dict(arrowstyle='-|>,head_length=0.35,head_width=0.2', color=col,
                                            lw=1.4 if sig else 0.9, shrinkA=2.5, shrinkB=0))
            else:
                ax.scatter(c['use'], i, s=14, color=col, zorder=4)
            ax.scatter(c['base'], i, s=17, facecolor='white', edgecolor=MUTED, lw=0.9, zorder=3)
        ax.axhspan(len(ORDER) - 2.5, len(ORDER) - 0.5, color=BLUE, alpha=0.07, lw=0, zorder=0)
        ax.set_title(char.capitalize(), fontsize=7.8, color=INK, pad=3, fontweight='bold')
        ax.set_xlim(0.04, 0.42)
        ax.set_xticks([0.1, 0.2, 0.3, 0.4])
        ax.set_xticklabels(['10%', '20%', '30%', '40%'])
        ax.grid(axis='x', color=GRID, lw=0.5)
        ax.set_axisbelow(True)
        ax.set_ylim(-0.6, len(ORDER) - 0.4)
    axes[0].set_yticks(range(len(ORDER)))
    axes[0].set_yticklabels([NAMES[m] for m in ORDER], fontsize=7)
    for t in axes[0].get_yticklabels()[-2:]:
        t.set_fontweight('bold')
    for t in axes[0].get_yticklabels():
        if 'no think' in t.get_text():
            t.set_color(MUTED)
            t.set_fontstyle('italic')
    handles = [Line2D([], [], ls='', marker='o', mfc='white', mec=MUTED, ms=4.5),
               Line2D([], [], color=BLUE, lw=1.4, marker='>', ms=4),
               Line2D([], [], color=GREY, lw=0.9, marker='>', ms=3.5)]
    fig.legend(handles, ['own $H{=}1$ answer', 'told $H{=}8$: higher ($p<.05$)', 'told $H{=}8$: no gain'],
               ncol=3, fontsize=6, frameon=False, loc='upper center', bbox_to_anchor=(0.52, 1.07),
               handletextpad=0.3, columnspacing=0.6, handlelength=1.3)
    fig.text(0.58, -0.035, 'states where the $H{=}8$-best move is chosen (horizon-sensitive states)',
             ha='center', fontsize=6.6, color=MUTED)
    fig.savefig(OUT / 'use_vs_baseline.pdf')
    plt.close(fig)


def fig_churn(churn):
    """Figure 3: answer changes from H=1 to H=8, both characters, as a share of states.
    Blue (right): answers that became an H=8-best move. Orange (left): H=8-best answers given up."""
    fig, axes = plt.subplots(1, 2, figsize=(3.15, 2.45), sharey=True)
    for ax, kind, title in zip(axes, ('sens', 'ctrl'), ('Sensitive states', 'Control states')):
        for i, m in enumerate(ORDER):
            d = [churn[m][f'{c}_{kind}'] for c in ('ironclad', 'silent')]
            n = sum(x['n'] for x in d)
            gain = 100 * sum(x['gained_best'] for x in d) / n
            loss = 100 * sum(x['lost_best'] for x in d) / n
            ax.barh(i, gain, color=BLUE, height=0.66, edgecolor='white', lw=0.6)
            ax.barh(i, -loss, color=ORANGE, height=0.66, edgecolor='white', lw=0.6)
            net = gain - loss
            if gain + loss > 4:
                ax.text(gain + 1.3, i, f'{net:+.0f}', va='center', fontsize=6.2,
                        color=BLUE if net > 0 else ORANGE, fontweight='bold')
        ax.axvline(0, color=MUTED, lw=0.6)
        ax.axhspan(len(ORDER) - 2.5, len(ORDER) - 0.5, color=BLUE, alpha=0.07, lw=0, zorder=0)
        ax.set_title(title, fontsize=7.8, color=INK, pad=3, fontweight='bold')
        ax.set_xlim(-36, 30)
        ax.set_xticks([-30, -15, 0, 15])
        ax.set_xticklabels(['30%', '15%', '0', '15%'])
        ax.grid(axis='x', color=GRID, lw=0.5)
        ax.set_axisbelow(True)
        ax.set_ylim(-0.6, len(ORDER) - 0.4)
    axes[0].set_yticks(range(len(ORDER)))
    axes[0].set_yticklabels([NAMES[m] for m in ORDER], fontsize=7)
    for t in axes[0].get_yticklabels()[-2:]:
        t.set_fontweight('bold')
    for t in axes[0].get_yticklabels():
        if 'no think' in t.get_text():
            t.set_color(MUTED)
            t.set_fontstyle('italic')
    handles = [plt.Rectangle((0, 0), 1, 1, color=ORANGE), plt.Rectangle((0, 0), 1, 1, color=BLUE)]
    fig.legend(handles, ['best move given up', 'best move found'], ncol=2, fontsize=6.4, frameon=False,
               loc='upper center', bbox_to_anchor=(0.56, 1.07), handlelength=1.2, columnspacing=1.2)
    fig.text(0.58, -0.035, 'share of states, $H{=}1$ answer to $H{=}8$ answer (number: net change)',
             ha='center', fontsize=6.6, color=MUTED)
    fig.savefig(OUT / 'churn.pdf')
    plt.close(fig)


if __name__ == '__main__':
    OUT.mkdir(exist_ok=True)
    summary = load('summary.json')
    churn = {m: load(f'review/churn_{m}.json') for m in ORDER}
    baselines = load('review/churn_BASELINES.json')
    fig_example()
    fig_use(summary, baselines)
    fig_churn(churn)
    print(sorted(p.name for p in OUT.iterdir()))
