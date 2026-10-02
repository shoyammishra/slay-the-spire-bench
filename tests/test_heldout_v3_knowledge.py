"""Amendment 6 (knowledge conditions) wrapper: freeze, subset, prompt splicing, leak check,
contract binding, and H-blind invariance on a mock run. Needs the v3 result files on disk."""
from pathlib import Path
import json
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import heldout_v3_inference as inf
from scripts import heldout_v3_knowledge as k
from slay_bench.ablation import effect_text as et

HAVE_DATA = (ROOT / 'results/controlled_h_v3_full.json').exists()
_CACHE = {}


def _setup():
    if 'cfg' not in _CACHE:
        cfg, digest = inf.load_config()
        am, am_digest = k.load_amendment()
        _CACHE.update(cfg=cfg, digest=digest, am=am, am_digest=am_digest,
                      base=k._ORIGINAL_LOAD_CONTEXT(cfg))
        for cond in k.CONDITIONS:
            ccfg = k.condition_config(cfg, digest, cond, am, am_digest)
            _CACHE[cond] = (ccfg, k.load_context(ccfg))
    return _CACHE


def test_amendment_frozen_and_bound_to_effect_text_and_base():
    am, digest = k.load_amendment()
    assert digest == k.FROZEN_DIGEST
    assert am['amends_protocol_digest'] == inf.FROZEN_DIGEST
    assert k._text_sha(am['effect_text']['module']) == am['effect_text']['sha256']
    assert am['analysis']['holm_family_size'] == 2 * 2 * len(am['models'])


def test_frozen_runner_is_not_patched_on_disk():
    # The wrapper swaps load_context at import; the frozen file itself must be untouched.
    assert 'heldout_v3_knowledge' not in (ROOT / 'scripts/heldout_v3_inference.py').read_text(encoding='utf-8')
    assert inf.load_context is k.load_context


def test_subset_matches_amendment():
    if not HAVE_DATA:
        return print('skip: no v3 data')
    s = _setup()
    fixtures, _, sens, _ = s['described'][1]
    assert len(fixtures) == 1169
    assert k.ids_sha(fixtures) == s['am']['fixture_subset']['kept_ids_sha256']
    banned = set(s['am']['fixture_subset']['excluded_if_any_pile_holds'])
    assert banned == set(et.TARGETED_SKILLS)
    assert not any(k.untargeted_exposed(f, banned) for f in fixtures.values())


def test_base_config_still_loads_full_release():
    if not HAVE_DATA:
        return print('skip: no v3 data')
    assert len(_setup()['base'][0]) == 1760


def test_described_only_inserts_reference_before_instruction():
    if not HAVE_DATA:
        return print('skip: no v3 data')
    s = _setup()
    base_prompts, prompts = s['base'][3], s['described'][1][3]
    for fid in list(prompts)[:50]:
        for h in (1, 8):
            bs, bu = base_prompts[fid][h]
            ds, du = prompts[fid][h]
            assert ds == bs
            head, tail = bu.split(k._ANCHOR)
            assert du.startswith(head + '\n\n=== EFFECT REFERENCE') and du.endswith(k._ANCHOR + tail)


def test_renamed_prompts_leak_no_names_or_flag_keys():
    if not HAVE_DATA:
        return print('skip: no v3 data')
    s = _setup()
    names = et.release_name_map(s['am']['conditions']['renamed']['name_seed'], include_context=True)
    flags = s['am']['conditions']['renamed']['flag_key_map']
    assert sorted(flags) == k.private_flag_keys(s['described'][1][0])
    pat = re.compile(r'(?<![A-Za-z0-9_])(?:' + '|'.join(re.escape(n) for n in names) + r')(?![A-Za-z0-9_])')
    for fid, hp in s['renamed'][1][3].items():
        for h, (system, user) in hp.items():
            assert not pat.search(system) and not pat.search(user), fid
            assert not any(f'"{key}"' in user for key in flags), fid
            assert 'deck-building card game' in system


def test_condition_prompts_differ_only_in_horizon_across_h():
    if not HAVE_DATA:
        return print('skip: no v3 data')
    for cond in k.CONDITIONS:
        for fid, hp in list(_setup()[cond][1][3].items())[:100]:
            norm = {u.replace(f'after exactly {h} decision transitions', '<H>') for h, (_, u) in hp.items()}
            assert len(norm) == 1 and len({sy for sy, _ in hp.values()}) == 1


def test_contract_binds_amendment_and_effect_text():
    s = _setup() if HAVE_DATA else None
    cfg, digest = inf.load_config()
    am, am_digest = k.load_amendment()
    a = k.condition_config(cfg, digest, 'described', am, am_digest)
    b = k.condition_config(cfg, digest, 'renamed', am, am_digest)
    assert a['_condition']['digest'] == b['_condition']['digest']
    assert a['_condition']['name'] != b['_condition']['name']
    assert inf.model_dir('llama-3.1-8b', False, a) != inf.model_dir('llama-3.1-8b', False, b)
    assert inf.contract(a, digest, 'llama-3.1-8b', False)['condition']['digest'] == a['_condition']['digest']
    assert a['inference']['horizons'] == [1, 8]
    assert a['_condition']['digest'] == inf.c.digest_json(dict(amendment=am_digest,
                                                                effect_text=am['effect_text']['sha256']))


def test_launcher_only_runs_amendment_models_and_conditions():
    text = (ROOT / 'cluster/sharanga_v3_knowledge.sbatch').read_text(encoding='utf-8')
    assert 'scripts/heldout_v3_inference.py' not in text
    assert 'case "$MODEL" in llama-3.1-8b|gpt-oss-120b)' in text
    assert 'case "$COND" in described|renamed)' in text
    assert 'V3_CONDITION:?set V3_CONDITION' in text


def test_mock_run_is_h_blind_invariant():
    """The constant-answer mock gives identical H1/H8 answers, so every DiD must be exactly 0."""
    if not HAVE_DATA:
        return print('skip: no v3 data')
    s = _setup()
    ccfg, ctx = s['renamed']
    queries = inf.schedule(ccfg, ctx[0], ctx[2])
    rows = {}
    for q in queries:
        row, _ = inf.ask(ccfg, 'llama-3.1-8b', q, ctx, None, None, True, None)
        rows[q['index']] = dict(row=row)
    out = inf.analyze(ccfg, s['digest'], 'llama-3.1-8b', mock=True, rows=rows, ctx=ctx)
    assert out['valid_for_primary_inference']
    for char, x in out['by_character'].items():
        assert x['primary']['estimate'] == 0.0, char
        assert x['lookahead_curve']['8']['lookahead_use_rate'] == x['lookahead_curve']['8']['ignore_baseline_rate']


if __name__ == '__main__':
    for name, fn in list(globals().items()):
        if name.startswith('test_') and callable(fn):
            fn()
            print('ok', name)
