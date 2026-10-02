#!/usr/bin/env python
"""Controlled-H v3 Amendment 6: game-knowledge conditions (PTA review response).

Two prompt conditions on the 1,169 v3 fixtures that hold no targeted Skill (the
controlled-H interface plays those untargeted, so the frozen oracle scores them as enemy
no-ops; decision_log 2026-10-02):
  described : the frozen prompt plus an engine-verified effect reference for every visible
              card, enemy, relic and power (`slay_bench.ablation.effect_text`).
  renamed   : `described`, then every proper name (cards, enemies, relics, distinctive moves,
              Slay the Spire / Ironclad / Silent) replaced by a neutral token, the system
              prompt's game sentence neutralized, and private engine-flag keys anonymized.
The model's answer is index-based, so the frozen oracles and scorer apply unchanged.

This is a WRAPPER around the frozen runner `heldout_v3_inference.py`, which is not edited
(its hash is in the contract of rows still being written). It swaps in the subset/prompt
loader and reuses the runner's serving contract, evidence store, schedule and analysis.

Stages: server | run | status | analyze | contrasts  (+ --condition described|renamed)
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts import heldout_v3_inference as inf
from scripts.controlled_horizon_model_pilot import _package_version
from scripts.controlled_horizon_pilot import _atomic_write_json
from slay_bench.ablation import effect_text as et
from slay_bench.controlled_horizon import load_fixture, legal_actions

AMENDMENT = ROOT / 'configs/controlled_h_v3_inference_amendment6.json'
FROZEN_DIGEST = 'b7f44796ac1937ac4161c954d529a21a6e206432cd1172082ff37137a1f88884'
CONDITIONS = ('described', 'renamed')
_ANCHOR = '\n\nChoose the next action'
_FLAG_RE = re.compile(r'"(_[a-z][a-z0-9_]*)"(?=\s*:)')


def _text_sha(rel):
    return hashlib.sha256((ROOT / rel).read_text(encoding='utf-8').encode()).hexdigest()


def load_amendment(require_frozen=True):
    am = json.loads(AMENDMENT.read_text(encoding='utf-8'))
    digest = inf.c.digest_json(am)
    if require_frozen and digest != FROZEN_DIGEST:
        raise ValueError('amendment 6 differs from its freeze')
    if _text_sha(am['effect_text']['module']) != am['effect_text']['sha256']:
        raise ValueError('effect-text module differs from the amendment')
    return am, digest


def untargeted_exposed(fixture, cards):
    c = load_fixture(fixture).combat
    return any(card.name in cards for pile in (c.hand, c.draw_pile, c.discard_pile) for card in pile)


def kept_ids(fixtures, am):
    rule = am['fixture_subset']
    cards = frozenset(rule['excluded_if_any_pile_holds'])
    return sorted(fid for fid, f in fixtures.items() if not untargeted_exposed(f, cards))


def ids_sha(ids):
    return hashlib.sha256('\n'.join(sorted(ids)).encode()).hexdigest()


def condition_prompt(fixture, horizon, system, user, condition, am, names, flags):
    """Frozen (system, user) -> condition prompt. Raises if any splice point is missing."""
    state = load_fixture(fixture)
    legal_actions(state)  # same cost refresh as the frozen prompt builder
    if user.count(_ANCHOR) != 1:
        raise ValueError('effect-reference anchor not found exactly once')
    appendix = et.effects_appendix(state, am['effect_text']['mode'])
    user = user.replace(_ANCHOR, '\n\n' + appendix + _ANCHOR)
    if condition == 'described':
        return system, user
    rw = am['conditions']['renamed']['system_prompt_rewrite']
    old = rw['from'].replace('{character}', fixture.character.capitalize())
    if system.count(old) != 1:
        raise ValueError('system-prompt game sentence not found exactly once')
    system = et.rename(system.replace(old, rw['to']), names)
    user = _FLAG_RE.sub(lambda m: '"' + flags.get(m.group(1), m.group(1)) + '"', et.rename(user, names))
    for text in (system, user):
        leaked = [n for n in names if re.search(r'(?<![A-Za-z0-9_])' + re.escape(n) + r'(?![A-Za-z0-9_])', text)]
        if leaked:
            raise ValueError(f'original names survive renaming: {leaked[:5]}')
    return system, user


def condition_config(cfg, digest, condition, am, am_digest):
    if condition not in CONDITIONS:
        raise ValueError('unknown knowledge condition')
    out = copy.deepcopy(cfg)
    out['protocol_id'] = f"{am['amendment_id']}:{condition}"
    out['inference']['horizons'] = list(am['horizons'])
    out['inference']['authorized_models'] = [m for m in am['models'] if m in cfg['inference']['models']]
    # Bind what defines the evidence (amendment + effect text). Not the wrapper/launcher code:
    # every saved row's prompt is re-derived and compared on load (validate_row), so a prompt
    # change is caught anyway, while an analysis fix must not orphan finished rows.
    bound = inf.c.digest_json(dict(amendment=am_digest, effect_text=am['effect_text']['sha256']))
    out['_condition'] = dict(name=condition, amendment_id=am['amendment_id'], digest=bound)
    out['_knowledge'] = dict(condition=condition, amendment=am)
    return out


_ORIGINAL_LOAD_CONTEXT = inf.load_context


def load_context(cfg, source_dir=ROOT / 'results'):
    """Frozen loader for base configs; subset + condition prompts for knowledge configs."""
    k = cfg.get('_knowledge')
    if not k:
        return _ORIGINAL_LOAD_CONTEXT(cfg, source_dir)
    am = k['amendment']
    plain = {key: v for key, v in cfg.items() if key not in ('_condition', '_knowledge')}
    fixtures, oracles, sensitivity, prompts = _ORIGINAL_LOAD_CONTEXT(plain, source_dir)
    keep = kept_ids(fixtures, am)
    rule = am['fixture_subset']
    if len(keep) != rule['kept_count'] or ids_sha(keep) != rule['kept_ids_sha256']:
        raise ValueError('fixture subset differs from the amendment')
    fixtures = {fid: fixtures[fid] for fid in keep}
    names = et.release_name_map(am['conditions']['renamed']['name_seed'], include_context=True)
    flags = am['conditions']['renamed']['flag_key_map']
    out = {fid: {h: condition_prompt(fixtures[fid], h, *prompts[fid][h], k['condition'], am, names, flags)
                 for h in prompts[fid]} for fid in keep}
    return fixtures, {fid: oracles[fid] for fid in keep}, {fid: sensitivity[fid] for fid in keep}, out


inf.load_context = load_context  # the runner resolves this global at call time


def private_flag_keys(fixtures):
    """Private engine-flag keys (`_asleep`, `_inferno_count`, `_combust_plays`...) name game
    entities; the amendment maps each to a neutral key in sorted order."""
    from slay_bench.controlled_horizon import oracle_visible_continuation_state
    keys = set()
    for f in fixtures.values():
        keys.update(_FLAG_RE.findall(json.dumps(oracle_visible_continuation_state(load_fixture(f)))))
    return sorted(keys)


# ---------------------------------------------------------------- pre-registered contrasts
def contrasts(base_cfg, digest, am, am_digest):
    """Per model x character, paired by fixture on the subset, at H8 (Holm over the family):
    knowledge = DiD(g_described - g_base); familiarity = DiD(g_renamed - g_described),
    g = EQ8(a8) - EQ8(a1) under the frozen oracle. Secondary: H8 use on sensitive fixtures
    (McNemar between conditions) and mean H8 effective quality."""
    a = base_cfg['analysis']
    ctx_b = _ORIGINAL_LOAD_CONTEXT(base_cfg)
    cfgs = {cond: condition_config(base_cfg, digest, cond, am, am_digest) for cond in CONDITIONS}
    ctxs = {cond: load_context(cfgs[cond]) for cond in CONDITIONS}
    fixtures, oracles, sens = ctxs['described'][0], ctxs['described'][1], ctxs['described'][2]
    tests, out = [], {}
    for model in am['models']:
        sets = {'base': inf._paired_sets(base_cfg, digest, model, ctx_b)}
        for cond in CONDITIONS:
            sets[cond] = inf._paired_sets(cfgs[cond], digest, model, ctxs[cond])
        if any(v is None for v in sets.values()):
            out[model] = dict(status='incomplete: needs base and both conditions complete')
            continue
        valid = {'base': inf.analyze(base_cfg, digest, model, ctx=ctx_b)['valid_for_primary_inference']}
        for cond in CONDITIONS:
            valid[cond] = inf.analyze(cfgs[cond], digest, model, ctx=ctxs[cond])['valid_for_primary_inference']
        out[model] = dict(validity=valid, by_character={})
        for char in base_cfg['release']['characters']:
            ids = [fid for fid in fixtures if fixtures[fid].character == char]
            g = {k: {fid: inf.cf_gain(oracles[fid], 8, s[fid][8], s[fid][1]) for fid in ids}
                 for k, s in sets.items()}
            res = dict(n_sensitive=sum(sens[f] for f in ids), n_control=sum(not sens[f] for f in ids))
            for name, (hi, lo), off in (('knowledge', ('described', 'base'), 300),
                                        ('familiarity', ('renamed', 'described'), 400)):
                diff = {True: [], False: []}
                for fid in ids:
                    diff[sens[fid]].append(g[hi][fid] - g[lo][fid])
                r = inf.did_bootstrap(diff[True], diff[False], a['bootstrap_replicates'],
                                      a['bootstrap_seed_by_character'][char] + off, am['analysis']['alpha'])
                r['valid'] = bool(valid[hi] and valid[lo])
                res[name] = r
                tests.append((r['p_two_sided'], model, char, name))
            use, quality = {}, {}
            for k, s in sets.items():
                o8 = {fid: inf._optimal(oracles[fid], 8) for fid in ids}
                hits = {fid: inf._key(s[fid][8]['score']) in o8[fid] for fid in ids if sens[fid]}
                use[k] = hits
                quality[k] = sum(s[fid][8]['effective_quality'] for fid in ids) / len(ids)
            res['h8_use_rate'] = {k: sum(v.values()) / len(v) for k, v in use.items()}
            res['h8_mean_effective_quality'] = quality
            for name, (hi, lo) in (('knowledge', ('described', 'base')), ('familiarity', ('renamed', 'described'))):
                b = sum(use[hi][f] and not use[lo][f] for f in use[hi])
                m = sum(use[lo][f] and not use[hi][f] for f in use[hi])
                res[name]['h8_use_mcnemar_exact_p'] = inf._binom_two_sided(b, b + m) if b + m else None
            out[model]['by_character'][char] = res
    ordered, running = sorted(tests), 0.0
    for i, (p, model, char, name) in enumerate(ordered):
        running = max(running, min(1.0, (len(ordered) - i) * p))
        r = out[model]['by_character'][char][name]
        r['holm_p'] = running
        r['reject_holm_05'] = bool(r['valid'] and running < am['analysis']['alpha'])
    return dict(amendment_digest=am_digest, holm_family_size=len(ordered),
                family_complete=len(ordered) == am['analysis']['holm_family_size'], models=out)


# ---------------------------------------------------------------- CLI
def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('action', choices=('server', 'run', 'status', 'analyze', 'contrasts'))
    ap.add_argument('--model')
    ap.add_argument('--condition', choices=CONDITIONS)
    ap.add_argument('--mock', action='store_true')
    ap.add_argument('--port', type=int, default=18900)
    ap.add_argument('--receipt', type=Path)
    ap.add_argument('--stop-at-unix', type=float)
    ap.add_argument('--max-new', type=int)
    ap.add_argument('--authorize-model-inference', action='store_true')
    args = ap.parse_args()
    base_cfg, digest = inf.load_config()
    am, am_digest = load_amendment()
    if am['amends_protocol_digest'] != digest:
        raise ValueError('amendment 6 amends another protocol')
    if args.action == 'contrasts':
        result = contrasts(base_cfg, digest, am, am_digest)
        _atomic_write_json(inf.OUT / 'real' / 'knowledge_contrasts.json', result)
        print(json.dumps(result, indent=1))
        return
    if not (args.model and args.condition):
        ap.error('--model and --condition are required')
    cfg = condition_config(base_cfg, digest, args.condition, am, am_digest)
    if args.model not in cfg['inference']['authorized_models']:
        ap.error('model is not authorized by amendment 6')
    if args.action == 'server':
        if args.mock or not args.authorize_model_inference or sys.platform == 'win32':
            ap.error('server requires authorized Linux execution')
        if args.receipt is None or args.receipt.exists():
            ap.error('supply a new receipt path')
        for pkg in ('vllm', 'transformers'):
            if _package_version(pkg) != inf.stack_versions(cfg, args.model)[pkg]:
                raise ValueError(f'{pkg} differs from the protocol')
        cmd = inf.server_command(cfg, args.model, args.port)
        _atomic_write_json(args.receipt, dict(contract=inf.contract(cfg, digest, args.model, False),
                                              command=cmd, port=args.port, pid=os.getpid(),
                                              runtime_versions={k: _package_version(k)
                                                                for k in ('vllm', 'transformers')}))
        os.execv(sys.executable, [sys.executable] + cmd)
    if args.action == 'run':
        while inf.run(args, cfg, digest) == 'continue':
            pass
        return
    if args.action == 'analyze':
        result = inf.analyze(cfg, digest, args.model, args.mock)
        _atomic_write_json(inf.model_dir(args.model, args.mock, cfg) / 'analysis.json', result)
        print(json.dumps(result, indent=1))
        return
    ctx = load_context(cfg)
    queries = inf.schedule(cfg, ctx[0], ctx[2])
    rows = inf.load_rows(cfg, digest, args.model, args.mock, queries, ctx, strict=False)
    print(json.dumps(dict(completed=len(rows), total=len(queries), smoke_gate=inf.smoke_gate(cfg, rows),
                          clean=sum(inf.clean(r['row']) for r in rows.values()),
                          truncated=sum(r['row']['diagnostics']['truncated'] for r in rows.values()))))


if __name__ == '__main__':
    main()
