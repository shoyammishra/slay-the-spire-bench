"""Figures for the ARR paper. Inputs: results/v3_paper/summary.json (per-model analysis),
results/v3_paper/decomp.json (choice classes). Palette: validated categorical slots 1-3
(dataviz reference) + neutral grey; direct labels carry identity (aqua is < 3:1)."""
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / 'figures'
BLUE, ORANGE, AQUA, GREY, INK, MUTED = '#2a78d6', '#eb6834', '#1baf7a', '#b9b8b2', '#0b0b0b', '#52514e'
plt.rcParams.update({'font.family': 'serif', 'font.size': 8, 'axes.edgecolor': MUTED,
                     'axes.labelcolor': INK, 'xtick.color': MUTED, 'ytick.color': INK,
                     'axes.spines.top': False, 'axes.spines.right': False, 'axes.linewidth': 0.6,
                     'xtick.major.width': 0.6, 'ytick.major.width': 0, 'savefig.bbox': 'tight'})

NAMES = {'llama-3.1-8b': 'Llama-3.1-8B', 'mistral-7b': 'Mistral-7B', 'qwen2.5-7b': 'Qwen2.5-7B',
         'llama-3.3-70b-r2': 'Llama-3.3-70B', 'qwen3-8b': 'Qwen3-8B$^\\dagger$', 'qwen3-14b': 'Qwen3-14B',
         'qwen3-32b': 'Qwen3-32B', 'gpt-oss-120b': 'gpt-oss-120b'}
ORDER = ['mistral-7b', 'qwen2.5-7b', 'llama-3.1-8b', 'llama-3.3-70b-r2',
         'qwen3-8b', 'qwen3-14b', 'qwen3-32b', 'gpt-oss-120b']
REASONING = {'qwen3-8b', 'qwen3-14b', 'qwen3-32b', 'gpt-oss-120b'}


def fig_example():
    """Figure 1: one real state (ironclad-0052); exact action values at H=1 and H=8."""
    acts = ['End turn', 'Feel No Pain', 'Limit Break', 'Pommel Strike', 'Bash']
    h1 = [0, 0, 0, 13, 12]
    h8 = [31, 40, 40, 40, 48]
    fig, axes = plt.subplots(1, 2, figsize=(3.1, 1.45), sharey=True)
    for ax, vals, h in zip(axes, (h1, h8), (1, 8)):
        best = max(vals)
        colors = [BLUE if v == best else GREY for v in vals]
        ax.barh(range(len(acts)), vals, color=colors, height=0.62, edgecolor='white', linewidth=1)
        for i, v in enumerate(vals):
            ax.text(v + best * 0.03, i, f'{v:g}', va='center', fontsize=7,
                    color=INK if v == best else MUTED, fontweight='bold' if v == best else 'normal')
        ax.set_title(f'horizon $H={h}$', fontsize=7.5, color=INK, pad=3)
        ax.set_xlim(0, best * 1.3)
        ax.set_xticks([])
        ax.spines['bottom'].set_visible(False)
    axes[0].set_yticks(range(len(acts)))
    axes[0].set_yticklabels(acts, fontsize=7)
    fig.savefig(OUT / 'example.pdf')
    plt.close(fig)


def fig_use(summary):
    """Figure 2: H8 lookahead use vs the H-blind baseline, per model and character."""
    fig, axes = plt.subplots(1, 2, figsize=(3.1, 2.3), sharey=True)
    for ax, char in zip(axes, ('ironclad', 'silent')):
        for i, m in enumerate(ORDER):
            c = summary[m][char]['curve']['8']
            ax.plot([c['base'], c['use']], [i, i], color=GREY, lw=1.6, zorder=1, solid_capstyle='round')
            ax.scatter(c['base'], i, s=22, facecolor='white', edgecolor=MUTED, lw=1, zorder=2)
            ax.scatter(c['use'], i, s=26, color=BLUE if m in REASONING else ORANGE,
                       edgecolor='white', lw=0.8, zorder=3)
            if c['mc'] is not None and c['mc'] < 0.05 and c['use'] > c['base']:
                ax.text(c['use'] + 0.012, i, '*', va='center', fontsize=9, color=INK)
        ax.axhline(3.5, color=GREY, lw=0.5, ls=(0, (2, 2)))
        ax.set_title(char.capitalize(), fontsize=8, color=INK, pad=3)
        ax.set_xlim(0.05, 0.42)
        ax.set_xticks([0.1, 0.2, 0.3, 0.4])
        ax.grid(axis='x', color='#e9e8e4', lw=0.5)
        ax.set_axisbelow(True)
    axes[0].set_yticks(range(len(ORDER)))
    axes[0].set_yticklabels([NAMES[m] for m in ORDER], fontsize=7.5)
    for ax in axes:
        ax.text(0.06, 3.6, 'reasoning', fontsize=6, color=MUTED, ha='left', va='bottom')
        ax.text(0.06, 3.4, 'no reasoning', fontsize=6, color=MUTED, ha='left', va='top')
    from matplotlib.lines import Line2D
    handles = [Line2D([], [], ls='', marker='o', mfc='white', mec=MUTED, ms=5),
               Line2D([], [], ls='', marker='o', mfc=BLUE, mec='white', ms=5.5),
               Line2D([], [], ls='', marker='o', mfc=ORANGE, mec='white', ms=5.5)]
    fig.legend(handles, ['H-blind baseline', 'told $H=8$ (reasoning)', 'told $H=8$ (no reasoning)'],
               ncol=3, fontsize=6.5, frameon=False, loc='upper center', bbox_to_anchor=(0.6, 1.07),
               handletextpad=0.2, columnspacing=0.8)
    fig.text(0.62, -0.02, 'share of horizon-sensitive states where the H=8-best move is chosen',
             ha='center', fontsize=7, color=MUTED)
    fig.savefig(OUT / 'use_vs_baseline.pdf')
    plt.close(fig)


def fig_decomp(decomp):
    """Figure 3: what the H=1 and H=8 answers are, on horizon-sensitive states (both characters)."""
    models = [m for m in ('llama-3.3-70b-r2', 'qwen3-14b', 'qwen3-32b', 'gpt-oss-120b') if m in decomp]
    classes = [('h8opt', 'H=8-best', BLUE), ('myopic', 'H=1-best (greedy)', ORANGE),
               ('other', 'other legal', GREY), ('illegal', 'illegal / cut off', '#e9e8e4')]
    fig, ax = plt.subplots(figsize=(3.1, 1.9))
    y, labels = 0, []
    for m in models:
        for h in ('1', '8'):
            left = 0
            tot = sum(decomp[m][h].values())
            for key, _, col in classes:
                w = decomp[m][h].get(key, 0) / tot
                ax.barh(y, w, left=left, color=col, height=0.72, edgecolor='white', linewidth=1)
                if w > 0.09:
                    ax.text(left + w / 2, y, f'{w:.0%}', ha='center', va='center', fontsize=6,
                            color='white' if col in (BLUE, ORANGE) else INK)
                left += w
            labels.append(f'{NAMES[m]}  $H={h}$')
            y += 1
        y += 0.5
    ys = [i + 0.5 * (i // 2) for i in range(len(labels))]
    ax.set_yticks(ys)
    ax.set_yticklabels(labels, fontsize=6.5)
    ax.invert_yaxis()
    ax.set_xlim(0, 1)
    ax.set_xticks([])
    ax.spines['bottom'].set_visible(False)
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for _, _, c in classes]
    ax.legend(handles, [l for _, l, _ in classes], ncol=2, fontsize=6, frameon=False,
              loc='upper center', bbox_to_anchor=(0.42, 1.2))
    fig.savefig(OUT / 'decomposition.pdf')
    plt.close(fig)


if __name__ == '__main__':
    OUT.mkdir(exist_ok=True)
    summary = json.loads((ROOT / 'results/v3_paper/summary.json').read_text())
    fig_example()
    fig_use(summary)
    dpath = ROOT / 'results/v3_paper/decomp.json'
    if dpath.exists():
        fig_decomp(json.loads(dpath.read_text()))
    print(sorted(p.name for p in OUT.iterdir()))
