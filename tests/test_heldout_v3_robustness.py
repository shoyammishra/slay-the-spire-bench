"""Known-answer tests for the post hoc encounter-robustness analysis."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.heldout_v3_robustness import _did, stratified_bootstrap


def test_did_pools_fixtures_not_encounter_means():
    cells = {'A': {True: [1.0, 1.0, 1.0], False: [0.0]},
             'B': {True: [0.0], False: [0.0, 0.0, 0.0]}}
    # Fixture-weighted: sensitive mean .75, control mean 0 (encounter-mean would give .5).
    assert abs(_did(cells) - 0.75) < 1e-12


def test_did_none_without_both_strata():
    assert _did({'A': {True: [1.0], False: []}}) is None


def test_stratified_bootstrap_constant_data_has_zero_width_ci():
    cells = {'A': {True: [0.2] * 5, False: [0.0] * 5}, 'B': {True: [0.2] * 3, False: [0.0] * 4}}
    r = stratified_bootstrap(cells, reps=200, seed=1)
    assert abs(r['estimate'] - 0.2) < 1e-12
    assert abs(r['ci_low'] - 0.2) < 1e-12 and abs(r['ci_high'] - 0.2) < 1e-12
    assert r['p_two_sided'] == 0 and r['p_reported'] == '< 0.005'


def test_stratified_bootstrap_null_effect_is_not_significant():
    cells = {'A': {True: [1.0, -1.0] * 10, False: [1.0, -1.0] * 10}}
    r = stratified_bootstrap(cells, reps=500, seed=3)
    assert r['ci_low'] < 0 < r['ci_high'] and r['p_two_sided'] > 0.5


def test_stratified_bootstrap_is_deterministic_per_seed():
    cells = {'A': {True: [0.1, 0.5, 0.9], False: [0.0, 0.3]}}
    assert stratified_bootstrap(cells, 300, 7) == stratified_bootstrap(cells, 300, 7)


def test_untargeted_exposure_count_on_release():
    import json
    from scripts.heldout_v3_robustness import untargeted_exposed
    from slay_bench.controlled_horizon import ControlledFixture, load_fixture
    path = Path(__file__).resolve().parents[1] / 'results/controlled_h_v3_release_fixtures.json'
    if not path.exists():
        print('skip: release fixtures not on disk')
        return
    fixtures = [ControlledFixture.from_dict(f) for f in json.loads(path.read_text(encoding='utf-8'))]
    flags = [untargeted_exposed(f) for f in fixtures]
    assert sum(flags) == 591
    clean = fixtures[flags.index(False)]
    c = load_fixture(clean).combat
    assert not any(card.name == 'Deadly Poison' for p in (c.hand, c.draw_pile, c.discard_pile) for card in p)


if __name__ == '__main__':
    for name, fn in sorted(globals().items()):
        if name.startswith('test_') and callable(fn):
            fn()
            print('ok', name)
