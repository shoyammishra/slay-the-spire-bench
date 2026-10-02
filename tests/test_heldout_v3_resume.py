"""The resume wrapper accepts only named, infrastructure-caused lost-in-flight failures."""
from pathlib import Path
import os
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import heldout_v3_resume as r


def _entry(failure=None, error_type=None):
    ev = {} if error_type is None else {'error_type': error_type}
    return dict(row=dict(diagnostics=dict(execution_failure=failure, truncated=False)), evidence=ev)


def _raises(fn):
    try:
        fn()
    except ValueError:
        return True
    return False


def test_accepted_lost_in_flight_is_masked_but_kept():
    rows = {1: _entry(), 2: _entry('ambiguous_query', 'lost_in_flight')}
    out = r.masked_rows(rows, frozenset({2}))
    assert set(out) == {1, 2}                      # kept -> never re-asked
    assert out[2]['row']['diagnostics']['execution_failure'] is None
    assert rows[2]['row']['diagnostics']['execution_failure'] == 'ambiguous_query'  # input untouched


def test_unnamed_or_other_failures_still_stop():
    assert _raises(lambda: r.masked_rows({3: _entry('ambiguous_query', 'lost_in_flight')}, frozenset()))
    assert _raises(lambda: r.masked_rows({3: _entry('transport_failure', 'URLError')}, frozenset({3})))


def test_accepting_a_non_failure_is_rejected():
    assert _raises(lambda: r.masked_rows({4: _entry()}, frozenset({4})))


def test_indices_parsed_from_env():
    os.environ['V3_ACCEPT_LOST'] = '5879:5881:'
    assert r.accepted_indices() == {5879, 5881}
    os.environ['V3_ACCEPT_LOST'] = '5879, 5881'
    assert r.accepted_indices() == {5879, 5881}
    del os.environ['V3_ACCEPT_LOST']


def test_resume_launcher_reuses_frozen_server_and_wraps_run_only():
    t = (ROOT / 'cluster/sharanga_v3_resume.sbatch').read_text(encoding='utf-8')
    assert 'scripts/heldout_v3_inference.py server' in t
    assert 'scripts/heldout_v3_resume.py run' in t
    assert 'V3_ACCEPT_LOST:?' in t


if __name__ == '__main__':
    for name, fn in list(globals().items()):
        if name.startswith('test_') and callable(fn):
            fn()
            print('ok', name)
