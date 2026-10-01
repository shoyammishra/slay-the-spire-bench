#!/usr/bin/env python
"""Amendment 3 link analysis: controlled-H lookahead use vs the existing benchmark matrix.

For every model that is gate-valid in the base controlled-H condition AND has structured-format
5-seed matrix aggregates, correlate H8 lookahead use (and use minus the H-blind baseline) with
combat and run metrics, per character. Spearman rho with an exact permutation p over all n!
orderings. Directional only: n is the number of models. Not named controlled_horizon*.py (that
glob is hashed by the frozen v2 code receipt).
"""
from __future__ import annotations

import itertools
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts import heldout_v3_inference as inf
from scripts.controlled_horizon_pilot import _atomic_write_json

MATRIX = {'ironclad': 'results/{m}_structured_seeds42_1042_2042_3042_4042.json',
          'silent': 'results/{m}_silent_structured_seeds42_1042_2042_3042_4042.json'}
Y = {'combat_score': lambda d: d['combat']['win_rate_mean'] * min(1.0, d['combat']['avg_hp_ratio_mean']),
     'combat_hp_ratio': lambda d: d['combat']['avg_hp_ratio_mean'],
     'run_progress': lambda d: d['run']['avg_progress_mean'],
     'turn_damage_ratio': lambda d: d['turn']['avg_damage_ratio_mean']}


def ranks(xs):
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    r = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        for k in range(i, j + 1):
            r[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return r


def pearson(a, b):
    n = len(a)
    ma, mb = sum(a) / n, sum(b) / n
    va = sum((x - ma) ** 2 for x in a)
    vb = sum((y - mb) ** 2 for y in b)
    if va == 0 or vb == 0:
        return None
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / (va * vb) ** 0.5


def spearman_exact(x, y):
    """Spearman rho and exact two-sided permutation p; None when either side is constant."""
    rx, ry = ranks(x), ranks(y)
    rho = pearson(rx, ry)
    if rho is None:
        return dict(rho=None, p_exact=None, note='undefined: a variable is constant (ties/ceiling)')
    perms = list(itertools.permutations(ry))
    hits = sum(abs(pearson(rx, list(p))) >= abs(rho) - 1e-12 for p in perms)
    return dict(rho=rho, p_exact=hits / len(perms), n=len(x),
                min_attainable_p=2 / len(perms) if len(set(rx)) == len(rx) else None)


def link(models=None):
    cfg, digest = inf.load_config()
    ctx = inf.load_context(cfg)
    candidates = models or cfg['inference']['authorized_models']
    rows, used, skipped = {}, [], {}
    for m in candidates:
        if not all((ROOT / MATRIX[c].format(m=m)).exists() for c in MATRIX):
            skipped[m] = 'no structured matrix aggregates'
            continue
        try:
            a = inf.analyze(cfg, digest, m, ctx=ctx)
        except Exception as exc:  # noqa: BLE001 - recorded, not hidden
            skipped[m] = f'no analyzable controlled-H run ({type(exc).__name__})'
            continue
        if not a['valid_for_primary_inference']:
            skipped[m] = 'controlled-H gate failed'
            continue
        used.append(m)
        rows[m] = a
    out = dict(models=used, skipped=skipped, by_character={})
    for char, pattern in MATRIX.items():
        mat = {m: json.loads((ROOT / pattern.format(m=m)).read_text(encoding='utf-8')) for m in used}
        cur = {m: rows[m]['by_character'][char]['lookahead_curve']['8'] for m in used}
        xs = {'h8_use': [cur[m]['lookahead_use_rate'] for m in used],
              'h8_use_minus_baseline': [cur[m]['lookahead_use_rate'] - cur[m]['ignore_baseline_rate'] for m in used]}
        res = dict(values={m: dict(h8_use=cur[m]['lookahead_use_rate'],
                                   h8_baseline=cur[m]['ignore_baseline_rate'],
                                   **{k: f(mat[m]) for k, f in Y.items()}) for m in used},
                   tests={})
        if len(used) >= 3:
            for xn, x in xs.items():
                for yn, f in Y.items():
                    res['tests'][f'{xn}~{yn}'] = spearman_exact(x, [f(mat[m]) for m in used])
        out['by_character'][char] = res
    return out


if __name__ == '__main__':
    result = link(sys.argv[1:] or None)
    _atomic_write_json(inf.OUT / 'real' / 'link.json', result)
    print(json.dumps(result, indent=1))
