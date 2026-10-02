#!/usr/bin/env python
"""Encounter robustness for controlled-H v3 (post hoc, NOT pre-registered).

The v3 primary resamples fixtures, which is the right unit (one fixture per seed), but
the 1,760 fixtures come from only five encounters. This checks that no single encounter
drives a result: per-encounter H8 DiD and lookahead use, leave-one-encounter-out DiD,
and an encounter-stratified bootstrap (resample fixtures within encounter x sensitivity).
Reads rows exactly as `heldout_v3_inference.py analyze` does; changes nothing.

Usage: python scripts/heldout_v3_robustness.py [--model NAME ...] [--out FILE]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import random
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts import heldout_v3_inference as inf
from slay_bench.controlled_horizon import load_fixture

# Targeted Skills the controlled-H interface plays untargeted, so the oracle scores them as
# enemy no-ops (decision_log 2026-10-02, instrument finding 1).
UNTARGETED_SKILLS = frozenset({'Deadly Poison', 'Terror', 'Catalyst', 'Corpse Explosion',
                               'Malaise', 'Spot Weakness', 'Leg Sweep'})


def untargeted_exposed(fixture):
    """True if any combat pile holds a targeted Skill that the oracle plays as a no-op."""
    c = load_fixture(fixture).combat
    return any(card.name in UNTARGETED_SKILLS
               for pile in (c.hand, c.draw_pile, c.discard_pile) for card in pile)


def _encounter(fixture):
    return '+'.join(fixture.enemy_ids)


def model_sets(cfg, digest, model, ctx):
    """Fixture -> {H: row} for complete, execution-clean fixtures; None if the run is incomplete."""
    queries = inf.schedule(cfg, ctx[0], ctx[2])
    rows = inf.load_rows(cfg, digest, model, False, queries, ctx, strict=False)
    if len(rows) != len(queries):
        return None
    sets = {}
    for q in queries:
        sets.setdefault(q['fixture_id'], {})[q['horizon']] = rows[q['index']]['row']
    return {fid: hs for fid, hs in sets.items()
            if not any(r['diagnostics']['execution_failure'] for r in hs.values())}


def _did(cells):
    sens = [g for e in cells for g in cells[e][True]]
    ctrl = [g for e in cells for g in cells[e][False]]
    if not sens or not ctrl:
        return None
    return statistics.fmean(sens) - statistics.fmean(ctrl)


def stratified_bootstrap(cells, reps, seed, alpha=0.05):
    """Resample fixtures within each encounter x sensitivity stratum (keeps composition fixed)."""
    rng = random.Random(seed)
    obs = _did(cells)
    boots = []
    for _ in range(reps):
        res = {e: {t: rng.choices(v, k=len(v)) if v else [] for t, v in cells[e].items()} for e in cells}
        boots.append(_did(res))
    boots.sort()
    lo, hi = boots[int(alpha / 2 * reps)], boots[int((1 - alpha / 2) * reps) - 1]
    p = sum(abs(b - obs) >= abs(obs) for b in boots) / reps
    return dict(estimate=obs, ci_low=lo, ci_high=hi, p_two_sided=p,
                p_floor=1 / reps, p_reported=f'< {1 / reps:g}' if p == 0 else f'{p:.4g}')


def analyze_model(cfg, digest, model, ctx, reps=10000, exclude=frozenset()):
    sets = model_sets(cfg, digest, model, ctx)
    if sets is None:
        return dict(status='incomplete')
    sets = {fid: hs for fid, hs in sets.items() if fid not in exclude}
    fixtures, oracles, sens = ctx[0], ctx[1], ctx[2]
    seeds = cfg['analysis']['bootstrap_seed_by_character']
    out = {}
    for char in cfg['release']['characters']:
        cells, use = {}, {}
        for fid, hs in sets.items():
            f = fixtures[fid]
            if f.character != char:
                continue
            e = _encounter(f)
            cells.setdefault(e, {True: [], False: []})[sens[fid]].append(
                inf.cf_gain(oracles[fid], 8, hs[8], hs[1]))
            o1, o8 = inf._optimal(oracles[fid], 1), inf._optimal(oracles[fid], 8)
            if o1.isdisjoint(o8):
                u = use.setdefault(e, dict(n=0, use=0, baseline=0, myopic=0))
                k8, k1 = inf._key(hs[8]['score']), inf._key(hs[1]['score'])
                u['n'] += 1
                u['use'] += k8 in o8
                u['baseline'] += k1 in o8
                u['myopic'] += k8 in o1
        per = {}
        for e in sorted(cells):
            s, c = cells[e][True], cells[e][False]
            u = use.get(e, dict(n=0))
            per[e] = dict(sensitive_n=len(s), control_n=len(c),
                          sensitive_mean_g=statistics.fmean(s) if s else None,
                          control_mean_g=statistics.fmean(c) if c else None,
                          did=_did({e: cells[e]}),
                          h8_use=u['use'] / u['n'] if u['n'] else None,
                          h8_baseline=u['baseline'] / u['n'] if u['n'] else None,
                          h8_myopic=u['myopic'] / u['n'] if u['n'] else None)
        loeo = {e: _did({k: v for k, v in cells.items() if k != e}) for e in sorted(cells)}
        dids = [v for v in loeo.values() if v is not None]
        out[char] = dict(
            pooled_did=_did(cells),
            stratified_bootstrap=stratified_bootstrap(cells, reps, seeds[char] + 200),
            per_encounter=per,
            leave_one_encounter_out=loeo,
            loeo_range=[min(dids), max(dids)] if dids else None,
            encounters_with_positive_did=sum((p['did'] or 0) > 0 for p in per.values()),
            encounters=len(per))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--model', nargs='*')
    ap.add_argument('--reps', type=int, default=10000)
    ap.add_argument('--exclude-untargeted', action='store_true',
                    help='drop fixtures holding a targeted Skill the oracle plays as a no-op')
    ap.add_argument('--out', type=Path, default=ROOT / 'results/controlled_h_v3_robustness.json')
    args = ap.parse_args()
    cfg, digest = inf.load_config()
    ctx = inf.load_context(cfg)
    models = args.model or cfg['inference']['authorized_models']
    exclude = frozenset(fid for fid, f in ctx[0].items() if untargeted_exposed(f))         if args.exclude_untargeted else frozenset()
    report = dict(note='post hoc encounter robustness; not pre-registered', protocol_digest=digest,
                  excluded_untargeted_fixtures=len(exclude),
                  models={m: analyze_model(cfg, digest, m, ctx, args.reps, exclude) for m in models})
    if exclude:
        print(f'excluding {len(exclude)} fixtures exposed to untargeted Skills')
    args.out.write_text(json.dumps(report, indent=2), encoding='utf-8')
    for m, r in report['models'].items():
        if 'status' in r:
            print(f'{m}: {r["status"]}')
            continue
        for char, x in r.items():
            sb = x['stratified_bootstrap']
            print(f'{m:16s} {char:8s} DiD {x["pooled_did"]:+.3f} strat-CI [{sb["ci_low"]:+.3f},{sb["ci_high"]:+.3f}] '
                  f'p {sb["p_reported"]}  LOEO [{x["loeo_range"][0]:+.3f},{x["loeo_range"][1]:+.3f}]  '
                  f'+enc {x["encounters_with_positive_did"]}/{x["encounters"]}')
            for e, p in x['per_encounter'].items():
                fmt = lambda v: '  -  ' if v is None else f'{v:+.3f}'
                print(f'      {e:22s} n={p["sensitive_n"]:3d}/{p["control_n"]:3d} sens {fmt(p["sensitive_mean_g"])} '
                      f'ctrl {fmt(p["control_mean_g"])} DiD {fmt(p["did"])} '
                      f'use {fmt(p["h8_use"])} base {fmt(p["h8_baseline"])}')


if __name__ == '__main__':
    main()
