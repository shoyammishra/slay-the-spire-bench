"""v3 inference: DiD bootstrap, exact McNemar, counterbalanced H1/H8 schedule (no model)."""
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import heldout_v3_inference as inf


def test_did_bootstrap_recovers_known_difference():
    sens = [0.5, 0.4, 0.6, 0.5, 0.5] * 20
    ctrl = [0.1, 0.0, 0.2, 0.1, 0.1] * 20
    r = inf.did_bootstrap(sens, ctrl, 2000, 1, 0.025)
    assert abs(r['estimate'] - 0.4) < 1e-12
    assert r['ci_low'] < 0.4 < r['ci_high'] and r['ci_low'] > 0.3
    assert r['p_two_sided'] < 0.001


def test_did_bootstrap_null_is_not_rejected():
    xs = [0.0, 1.0, 0.5, 0.25, 0.75] * 20
    r = inf.did_bootstrap(xs, list(xs), 2000, 2, 0.025)
    assert abs(r['estimate']) < 1e-12 and r['p_two_sided'] > 0.5


def test_exact_mcnemar():
    assert abs(inf._binom_two_sided(0, 5) - 0.0625) < 1e-12
    assert abs(inf._binom_two_sided(5, 10) - 1.0) < 1e-12
    assert abs(inf._binom_two_sided(1, 8) - 0.0703125) < 1e-12


def test_schedule_latin_square_balances_positions_within_strata():
    cfg = {'protocol_id': 'test', 'release': {'characters': ['ironclad', 'silent']},
           'inference': {'horizons': [1, 2, 4, 8]}}
    fixtures = {f'{c}-{i}': SimpleNamespace(character=c) for c in ('ironclad', 'silent') for i in range(40)}
    sens = {fid: int(fid.split('-')[1]) % 2 == 0 for fid in fixtures}
    q = inf.schedule(cfg, fixtures, sens)
    assert len(q) == 320 and [x['index'] for x in q] == list(range(320))
    for c in ('ironclad', 'silent'):
        for tag in (True, False):
            for pos in range(4):
                hs = [x['horizon'] for x in q if x['character'] == c and x['h1_h8_sensitive'] is tag
                      and x['query_order_within_fixture'] == pos]
                assert all(hs.count(h) == 5 for h in (1, 2, 4, 8)), (c, tag, pos, hs)
    per = {}
    for x in q:
        per.setdefault(x['fixture_id'], []).append(x['horizon'])
    assert all(sorted(v) == [1, 2, 4, 8] for v in per.values())


def _oracle(values_by_h):
    """values_by_h: {H: {card: value}} -> oracle row in the frozen format."""
    out = {}
    for h, vals in values_by_h.items():
        best, worst = max(vals.values()), min(vals.values())
        out[str(h)] = dict(action_values={f'play:{k}:0': v for k, v in vals.items()},
                           best_value=best, worst_value=worst, exact=True,
                           optimal_actions=[dict(action='play', card_index=k, target_index=0)
                                            for k, v in vals.items() if v == best])
    return {'oracles': out}


def _row(oracle, h, card):
    from scripts.controlled_horizon_confirmatory import effective_quality
    from scripts.controlled_horizon_model_pilot import score_precomputed_oracle
    parsed = dict(action='play', card_index=card, target_index=0)
    score = score_precomputed_oracle(oracle, h, parsed)
    return dict(score=score, response_parsed=parsed, diagnostics={'truncated': False},
                effective_quality=effective_quality(score))


def test_lookahead_curve_counts_use_myopia_baseline_and_same_oracle_did():
    short, long_ = {0: 10, 1: 0, 2: 5}, {0: 0, 1: 10, 2: 5}
    sens_oracle = _oracle({1: short, 2: short, 4: long_, 8: long_})
    ctrl_oracle = _oracle({h: {0: 0, 1: 5, 2: 10} for h in (1, 2, 4, 8)})
    oracles = {'f1': sens_oracle, 'f2': sens_oracle, 'f3': ctrl_oracle}
    plays = {'f1': {1: 0, 2: 0, 4: 1, 8: 1},   # switches to the long-horizon move
             'f2': {1: 0, 2: 0, 4: 0, 8: 0},   # myopic
             'f3': {1: 2, 2: 2, 4: 2, 8: 2}}   # control, optimal throughout
    sets = {f: {h: _row(oracles[f], h, card) for h, card in p.items()} for f, p in plays.items()}
    curve = inf.lookahead_curve(sets, oracles, [1, 2, 4, 8])
    assert curve['2']['sensitive_n'] == 0 and curve['2']['lookahead_use_rate'] is None
    c8 = curve['8']
    assert c8['sensitive_n'] == 2 and c8['control_n'] == 1
    assert c8['lookahead_use_rate'] == .5 and c8['myopic_rate'] == .5 and c8['ignore_baseline_rate'] == 0
    assert inf.cf_gain(oracles['f1'], 8, sets['f1'][8], sets['f1'][1]) == 1.0
    assert inf.cf_gain(oracles['f2'], 8, sets['f2'][8], sets['f2'][1]) == 0.0
    assert c8['did'] == 0.5


def test_h_blind_constant_policy_scores_exactly_zero_on_the_real_release():
    # Instrument check (the degenerate strategy): an answer that ignores H must have zero gain
    # at every H and zero DiD, on the frozen release itself. Regression for 2026-09-30.
    from scripts.controlled_horizon_confirmatory import make_row
    cfg, _ = inf.load_config()
    fixtures, oracles, sens, prompts = inf.load_context(cfg)
    queries = inf.schedule(cfg, fixtures, sens)
    sets = {}
    for q in queries[:400]:
        row = make_row(q, prompts[q['fixture_id']], oracles[q['fixture_id']],
                       {'action': 'end_turn'}, '{"action":"end_turn"}', 'stop')
        sets.setdefault(q['fixture_id'], {})[q['horizon']] = row
    sets = {f: hs for f, hs in sets.items() if len(hs) == 4}
    assert len(sets) >= 50
    for f, hs in sets.items():
        for h in (2, 4, 8):
            assert inf.cf_gain(oracles[f], h, hs[h], hs[1]) == 0.0
    curve = inf.lookahead_curve(sets, oracles, [1, 2, 4, 8])
    for h, v in curve.items():
        assert v['did'] in (None, 0.0) and v['lookahead_use_rate'] == v['ignore_baseline_rate'], (h, v)


def test_amendment_only_adds_models_and_leaves_base_contracts_untouched():
    cfg, digest = inf.load_config()
    assert {'llama-3.1-8b', 'deepseek-r1-distill-14b'} <= set(cfg['inference']['authorized_models'])
    assert 'amendment' not in inf.contract(cfg, digest, 'qwen3-14b', False)
    assert inf.contract(cfg, digest, 'llama-3.1-8b', False)['amendment']['amendment_id'].endswith('amendment-1-2026-10-01')
    a = inf.contract(cfg, digest, 'qwen3-8b', False)
    b = dict(a, code={'scripts/heldout_v3_inference.py': 'old'})
    assert inf.contract_matches(b, a, strict=False) and not inf.contract_matches(b, a, strict=True)
    c2 = dict(a, protocol_digest='0' * 64)
    assert not inf.contract_matches(c2, a, strict=False)


def test_v3_inference_runner_is_outside_the_frozen_code_receipt():
    from scripts.controlled_horizon_confirmatory import code_receipt
    assert not any('heldout_v3' in p for p in code_receipt())


def test_launcher_readiness_budget_fits_large_checkpoints_and_walltime():
    """Regression (job 374631): a fixed 20-min readiness wait killed Qwen3-32B mid-load."""
    import re
    text = (ROOT / 'cluster/sharanga_v3_inference.sbatch').read_text(encoding='utf-8')
    budget = int(re.search(r'HEALTH_WAIT_MIN:-(\d+)', text).group(1))
    assert 'seq 1 $((HEALTH_WAIT_MIN * 12))' in text and 'sleep 5' in text
    h, m, _ = map(int, re.search(r'--time=(\d+):(\d+):(\d+)', text).groups())
    assert 60 <= budget < h * 60 + m
    assert 24 * 60 - budget >= 18 * 60  # still leaves the H200 1-day cap room for ~18 h of queries


if __name__ == '__main__':
    for name, fn in list(globals().items()):
        if name.startswith('test_'):
            fn()
            print('PASS', name)
