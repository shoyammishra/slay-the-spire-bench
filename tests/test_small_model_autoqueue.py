"""Fake-Slurm tests of the 48-query development supervisor."""
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import small_model_autoqueue as q


def result(text='', code=0):
    return SimpleNamespace(stdout=text, returncode=code)


class QueueTests(unittest.TestCase):
    def test_accounting_exact_root_and_job_name(self):
        self.assertEqual(q.accounting(1, lambda _: result('1|slay_small_pilot|COMPLETED|0:0|\n1.batch|other|FAILED|1:0|')),
                         ('COMPLETED', '0:0'))
        for text in ('1|other|COMPLETED|0:0|', '1|slay_small_pilot|COMPLETED|0:0|\n1|slay_small_pilot|COMPLETED|0:0|'):
            with self.assertRaises(ValueError):
                q.accounting(1, lambda _: result(text))

    def test_progress_limits(self):
        self.assertEqual(q.decide(1, 0, 0, 5), 'submit')
        self.assertEqual(q.decide(48, 33, 3, 5), 'complete')
        self.assertEqual(q.decide(33, 17, 5, 5), 'budget_exhausted')
        for index, before in ((1, 1), (49, 33), (18, 1), (0, 0)):
            with self.assertRaises(ValueError):
                q.decide(index, before, 0, 5)

    def test_full_automatic_chain(self):
        states = iter([1, 17, 33, 48])
        submissions = []
        def execute(argv):
            if argv[0] == 'sacct':
                return result(f'{argv[4]}|slay_small_pilot|COMPLETED|0:0|')
            if argv[0] == 'squeue':
                return result()
            submissions.append(argv)
            return result(str(100+len(submissions)))
        with tempfile.TemporaryDirectory() as td:
            state = q.run(1, 5, 0, path=Path(td)/'state.json', stop_path=Path(td)/'stop',
                          execute=execute, preflight=lambda _: next(states))
        self.assertEqual(state['phase'], 'complete')
        self.assertEqual(len(submissions), 3)
        self.assertIn('PILOT_MAX_NEW=15', ' '.join(submissions[-1]))

    def test_failed_job_and_stop_file_submit_nothing(self):
        for stop in (False, True):
            calls = []
            with tempfile.TemporaryDirectory() as td:
                sp = Path(td)/'stop'
                if stop:
                    sp.touch()
                def execute(argv):
                    calls.append(argv[0])
                    return result('1|slay_small_pilot|FAILED|0:9|')
                state = q.run(1, 5, 0, path=Path(td)/'state.json', stop_path=sp, execute=execute)
            self.assertEqual(state['phase'], 'stopped')
            self.assertNotIn('sbatch', calls)

    def test_other_queued_job_blocks_duplicate(self):
        with self.assertRaises(ValueError):
            q.no_other_jobs(lambda _: result('123\n'))
        with self.assertRaises(ValueError):
            q.no_other_jobs(lambda _: result('', 1))

    def test_ambiguous_submission_never_retried(self):
        calls = []
        def execute(argv):
            if argv[0] == 'sacct':
                return result('1|slay_small_pilot|COMPLETED|0:0|')
            if argv[0] == 'squeue':
                return result()
            calls.append(argv)
            raise TimeoutError()
        with tempfile.TemporaryDirectory() as td:
            path, stop = Path(td)/'state.json', Path(td)/'stop'
            for error in (TimeoutError, ValueError):
                with self.assertRaises(error):
                    q.run(1, 5, 0, path=path, stop_path=stop, execute=execute, preflight=lambda _: 1)
            self.assertEqual(json.loads(path.read_text())['phase'], 'submit_pending')
        self.assertEqual(len(calls), 1)

    def test_bad_checkpoint_blocks_submission(self):
        def bad(_):
            raise ValueError('pending or tampered evidence')
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ValueError):
                q.run(1, 5, 0, path=Path(td)/'state.json', stop_path=Path(td)/'stop',
                      execute=lambda _: result('1|slay_small_pilot|COMPLETED|0:0|'), preflight=bad)


if __name__ == '__main__':
    unittest.main()
