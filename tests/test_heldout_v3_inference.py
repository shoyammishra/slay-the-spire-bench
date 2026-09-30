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


def _oracle(opt):
    return {'oracles': {str(h): {'optimal_actions': [dict(action='play', card_index=i, target_index=0)
                                                      for i in ids]} for h, ids in opt.items()}}


def _row(card, q):
    return {'score': {'scored_action': dict(action='play', card_index=card, target_index=0)},
            'effective_quality': q}


def test_lookahead_curve_counts_use_myopia_and_baseline():
    # f1: H1-opt {0}, H8-opt {1}; model plays 0 at H1 and 1 at H8 -> uses lookahead.
    # f2: same optima; model plays 0 at both -> myopic.  f3: control at every H.
    oracles = {'f1': _oracle({1: [0], 2: [0], 4: [1], 8: [1]}),
               'f2': _oracle({1: [0], 2: [0], 4: [1], 8: [1]}),
               'f3': _oracle({1: [2], 2: [2], 4: [2], 8: [2]})}
    sets = {'f1': {1: _row(0, .2), 2: _row(0, .2), 4: _row(1, 1.), 8: _row(1, 1.)},
            'f2': {1: _row(0, .2), 2: _row(0, .2), 4: _row(0, .1), 8: _row(0, .1)},
            'f3': {1: _row(2, 1.), 2: _row(2, 1.), 4: _row(2, 1.), 8: _row(2, 1.)}}
    curve = inf.lookahead_curve(sets, oracles, [1, 2, 4, 8])
    assert curve['2']['sensitive_n'] == 0 and curve['2']['lookahead_use_rate'] is None
    c8 = curve['8']
    assert c8['sensitive_n'] == 2 and c8['control_n'] == 1
    assert c8['lookahead_use_rate'] == .5 and c8['myopic_rate'] == .5 and c8['ignore_baseline_rate'] == 0
    assert abs(c8['did'] - ((0.8 + -0.1) / 2 - 0.0)) < 1e-12


def test_v3_inference_runner_is_outside_the_frozen_code_receipt():
    from scripts.controlled_horizon_confirmatory import code_receipt
    assert not any('heldout_v3' in p for p in code_receipt())


if __name__ == '__main__':
    for name, fn in list(globals().items()):
        if name.startswith('test_'):
            fn()
            print('PASS', name)
