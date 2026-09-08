"""No-Slurm tests of the bounded confirmation submission supervisor."""
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import confirmatory_autoqueue as queue


def status(index=34, sessions=2):
    return dict(next_global_index=index, finalized_sessions=sessions,
                expected_queries=2016, active_session_status=None,
                claim_already_failed=False, execution_failures=0,
                continuation_smoke_passed=True, complete=index == 2016,
                runnable=index < 2016)


def result(stdout='', code=0):
    return SimpleNamespace(stdout=stdout, returncode=code)


class AutoqueueTests(unittest.TestCase):
    def test_accounting_uses_exact_root_and_name(self):
        self.assertEqual(queue.accounting(10613, lambda _: result(
            '10613|slay_h_confirm|COMPLETED|0:0|\n10613.batch|batch|FAILED|1:0|')),
            ('COMPLETED', '0:0'))
        for text in ('10613|other|COMPLETED|0:0|',
                     '10613|slay_h_confirm|COMPLETED|0:0|\n10613|slay_h_confirm|RUNNING|0:0|'):
            with self.assertRaises(ValueError):
                queue.accounting(10613, lambda _: result(text))

    def test_progress_and_integrity_gates(self):
        self.assertEqual(queue.decide(status(), 2, 1, 0, 2), 'submit')
        self.assertEqual(queue.decide(status(), 2, 1, 2, 2), 'budget_exhausted')
        changes = [dict(next_global_index=2), dict(next_global_index=35),
                   dict(finalized_sessions=3), dict(active_session_status='pending'),
                   dict(continuation_smoke_passed=False), dict(execution_failures=1),
                   dict(claim_already_failed=True), dict(runnable=False)]
        for fields in changes:
            value = status(); value.update(fields)
            with self.assertRaises(ValueError):
                queue.decide(value, 2, 1, 0, 64)

    def test_one_successor_then_budget_stop(self):
        with TemporaryDirectory() as folder:
            path, stop = Path(folder)/'state.json', Path(folder)/'stop'
            calls = []
            accounting = iter(['RUNNING', 'COMPLETED', 'COMPLETED'])
            progress = iter([status(), status(66, 3)])
            def execute(argv):
                calls.append(argv)
                if argv[0] == 'sbatch':
                    self.assertEqual(json.loads(path.read_text())['phase'], 'submit_pending')
                    self.assertIn('--no-requeue', argv)
                    self.assertNotIn('--export=ALL', argv)
                    return result('200;test-cluster\n')
                return result(f'{argv[4]}|slay_h_confirm|{next(accounting)}|0:0|')
            final = queue.run(10613, 1, 2, 1, path=path, stop_path=stop, execute=execute,
                              sleep=lambda _: None, preflight=lambda *_: next(progress))
            self.assertEqual(final['phase'], 'budget_exhausted')
            self.assertEqual(final['submitted_jobs'], [200])
            self.assertEqual(sum(call[0] == 'sbatch' for call in calls), 1)

    def test_failed_job_and_stopfile_never_submit(self):
        for stop_first in (False, True):
            with TemporaryDirectory() as folder:
                path, stop = Path(folder)/'state.json', Path(folder)/'stop'
                if stop_first: stop.touch()
                calls = []
                def execute(argv):
                    calls.append(argv)
                    self.assertEqual(argv[0], 'sacct')
                    return result('10613|slay_h_confirm|FAILED|0:9|')
                final = queue.run(10613, 64, 2, 1, path=path, stop_path=stop, execute=execute)
                self.assertEqual(final['phase'], 'stopped')
                self.assertEqual(final['current_job'], 10613)
                self.assertEqual(final['submitted_jobs'], [])

    def test_ambiguous_submission_is_not_repeated_on_restart(self):
        with TemporaryDirectory() as folder:
            path, stop = Path(folder)/'state.json', Path(folder)/'stop'
            calls = []
            def execute(argv):
                calls.append(argv)
                if argv[0] == 'sbatch':
                    raise TimeoutError('scheduler receipt lost')
                return result('10613|slay_h_confirm|COMPLETED|0:0|')
            with self.assertRaises(TimeoutError):
                queue.run(10613, 2, 2, 1, path=path, stop_path=stop, execute=execute,
                          preflight=lambda *_: status())
            self.assertEqual(json.loads(path.read_text())['phase'], 'submit_pending')
            with self.assertRaisesRegex(ValueError, 'ambiguous'):
                queue.run(10613, 2, 2, 1, path=path, stop_path=stop, execute=execute)
            self.assertEqual(sum(call[0] == 'sbatch' for call in calls), 1)

    def test_completion_stops_without_submission(self):
        with TemporaryDirectory() as folder:
            def execute(argv):
                self.assertEqual(argv[0], 'sacct')
                return result('10613|slay_h_confirm|COMPLETED|0:0|')
            final = queue.run(10613, 64, 1984, 63, path=Path(folder)/'state.json',
                              stop_path=Path(folder)/'stop', execute=execute,
                              preflight=lambda *_: status(2016, 64))
            self.assertEqual(final['phase'], 'complete')

    def test_contract_drift_cannot_expand_budget(self):
        with TemporaryDirectory() as folder:
            path, stop = Path(folder)/'state.json', Path(folder)/'stop'
            stop.touch()
            queue.run(10613, 1, 2, 1, path=path, stop_path=stop)
            with self.assertRaisesRegex(ValueError, 'contract changed'):
                queue.run(10613, 64, 2, 1, path=path, stop_path=stop)


if __name__ == '__main__':
    unittest.main(verbosity=2)
