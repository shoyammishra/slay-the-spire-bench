"""Development pilot tests: no API, downloads or cluster submission."""
import copy
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import small_model_pilot as m


class PilotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ctx, cls.queries = m.prepare()

    def test_exposed_balanced_selection(self):
        qs = self.queries
        self.assertEqual(len(qs), 48)
        self.assertEqual(len({q['fixture_id'] for q in qs}), 12)
        self.assertEqual(qs[0]['horizon'], 2)
        self.assertTrue(all(q['original_index'] < 432 for q in qs))
        for char in ('ironclad', 'silent'):
            for tag in (True, False):
                self.assertEqual(sum(q['character'] == char and q['h1_h8_sensitive'] == tag for q in qs), 12)

    def test_context_boundary(self):
        s = m.spec()
        m.check_context(16768, s)
        for count in (16769, 0, -1, True, None):
            with self.assertRaises(ValueError):
                m.check_context(count, s)

    def test_smoke_gate(self):
        for cap in (0, 2, 17):
            with self.assertRaises(ValueError):
                m.check_ready({'rows': []}, cap, 48)
        m.check_ready({'rows': []}, 1, 48)
        with self.assertRaises(ValueError):
            m.check_ready({'rows': []}, 1, 0)

    def test_paths_and_commands(self):
        self.assertNotEqual(m.output_path('qwen3-8b'), m.output_path('qwen3-8b', True))
        self.assertNotEqual(m.output_path('qwen3-8b'), m.output_path('qwen3-14b'))
        for model in m.spec()['models']:
            cmd = m.command(model, 18808)
            self.assertIn(m.spec()['models'][model]['revision'], cmd)
            self.assertEqual(cmd[cmd.index('--tokenizer-revision')+1],
                             m.spec()['models'][model]['revision'])
            self.assertIn('32768', cmd)
            self.assertIn('bfloat16', cmd)
        with self.assertRaises(ValueError):
            m.command('qwen3-8b', 0)

    def args(self, model='qwen3-8b', mock=True):
        return SimpleNamespace(model=model, mock=mock, max_new=1, port=18808,
                               receipt=Path('unused'), stop_at_unix=10**12,
                               authorize_model_inference=True)

    def receipt(self):
        return dict(contract=m.contract('qwen3-8b', False), command=m.command('qwen3-8b', 18808),
                    port=18808, endpoint_sha256=m.c.digest_json('http://localhost:18808'),
                    runtime_versions={k: m.spec()[k+'_version'] for k in ('vllm', 'transformers')})

    def test_receipt_tampering(self):
        receipt = self.receipt()
        m.validate_receipt(receipt, 'qwen3-8b', 18808)
        for key, value in [('command', []), ('port', 99), ('runtime_versions', {}), ('endpoint_sha256', '')]:
            bad = dict(receipt, **{key: value})
            with self.assertRaises(ValueError):
                m.validate_receipt(bad, 'qwen3-8b', 18808)
        self.assertFalse(m.receipt_path_ok(ROOT/'private.json'))

    def test_truncated_smoke_is_not_clean(self):
        q = self.queries[0]
        for raw, finish in [('{"action":"end_turn"}', 'length'), ('<think>unfinished', 'stop')]:
            replay = m.c.Replay(); replay.raw = raw; replay.last_finish_reason = finish
            row = m.c.make_row(q, self.ctx[3][q['fixture_id']], self.ctx[1][q['fixture_id']],
                               replay.complete_json('', ''), raw, finish)
            self.assertFalse(m.clean(row))
            with self.assertRaises(ValueError):
                m.check_ready({'rows': [{'row': row}]}, 1, 48)

    def test_full_mock_both_models_resume_and_replay(self):
        for model in m.spec()['models']:
            with tempfile.TemporaryDirectory() as td, patch.object(m, 'prepare', return_value=(self.ctx, self.queries)):
                path = Path(td)/'pilot.json'
                with patch.object(m, 'output_path', return_value=path), patch('builtins.print'):
                    args = self.args(model)
                    m.run(args)
                    args.max_new = 16
                    for _ in range(3):
                        m.run(args)
                report = json.loads(path.read_text())
                self.assertEqual(len(report['rows']), 48)
                m.check_report(report, model, True, self.queries, self.ctx)
                self.assertFalse(report['confirmatory'])

    def test_pending_blocks_without_retry(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td)/'pilot.json'
            r = m.get_report(path, 'qwen3-8b', True, self.queries, self.ctx)
            r['pending'] = {'index': 0}
            with self.assertRaisesRegex(ValueError, 'pending'):
                m.check_report(r, 'qwen3-8b', True, self.queries, self.ctx)
            with self.assertRaises(ValueError):
                m.check_report(r, 'qwen3-14b', True, self.queries, self.ctx)

    def test_raw_evidence_tampering_rejected(self):
        with tempfile.TemporaryDirectory() as td, patch.object(m, 'prepare', return_value=(self.ctx, self.queries)):
            path = Path(td)/'pilot.json'
            with patch.object(m, 'output_path', return_value=path), patch('builtins.print'):
                m.run(self.args())
            r = json.loads(path.read_text())
            r['rows'][0]['evidence']['response']['choices'][0]['message']['content'] = '{}'
            r['rows'][0]['evidence_sha256'] = m.c.digest_json(r['rows'][0]['evidence'])
            with self.assertRaisesRegex(ValueError, 'raw response'):
                m.check_report(r, 'qwen3-8b', True, self.queries, self.ctx)

    def test_timeout_saved_once_and_blocks_resume(self):
        calls = []
        def http(url, payload=None, timeout=30):
            if url.endswith('/models'):
                return {'data': [{'id': 'qwen3-8b', 'max_model_len': 32768}]}
            if url.endswith('/tokenize'):
                return {'count': 1000}
            calls.append(url)
            raise TimeoutError()
        with tempfile.TemporaryDirectory() as td, patch.object(m, 'prepare', return_value=(self.ctx, self.queries)):
            path = Path(td)/'pilot.json'
            with patch.object(m, 'output_path', return_value=path), patch.object(m, 'http_json', side_effect=http), patch.object(m, 'live_receipt', return_value=self.receipt()), patch('builtins.print'):
                for _ in range(2):
                    with self.assertRaises(ValueError):
                        m.run(self.args(mock=False))
            self.assertEqual(len(calls), 1)
            r = json.loads(path.read_text())
            self.assertEqual(r['rows'][0]['row']['effective_quality'], 0)
            self.assertIsNone(r['pending'])
            r['rows'][0]['evidence']['request']['max_tokens'] = 8000
            r['rows'][0]['evidence_sha256'] = m.c.digest_json(r['rows'][0]['evidence'])
            with self.assertRaisesRegex(ValueError, 'saved request'):
                m.check_report(r, 'qwen3-8b', False, self.queries, self.ctx)

    def test_crash_after_request_preserves_pending(self):
        def http(url, payload=None, timeout=30):
            if url.endswith('/models'):
                return {'data': [{'id': 'qwen3-8b', 'max_model_len': 32768}]}
            if url.endswith('/tokenize'):
                return {'count': 1000}
            raise KeyboardInterrupt()
        with tempfile.TemporaryDirectory() as td, patch.object(m, 'prepare', return_value=(self.ctx, self.queries)):
            path = Path(td)/'pilot.json'
            with patch.object(m, 'output_path', return_value=path), patch.object(m, 'http_json', side_effect=http), patch.object(m, 'live_receipt', return_value={}):
                with self.assertRaises(KeyboardInterrupt):
                    m.run(self.args(mock=False))
            r = json.loads(path.read_text())
            self.assertEqual(r['pending']['query']['index'], 0)
            self.assertEqual(r['rows'], [])

    def test_saved_real_receipt_replayed_and_no_time_stops(self):
        calls = []
        def http(url, payload=None, timeout=30):
            if url.endswith('/models'):
                return {'data': [{'id': 'qwen3-8b', 'max_model_len': 32768}]}
            if url.endswith('/tokenize'):
                return {'count': 1000}
            calls.append(url)
            return {'choices': [{'message': {'content': '{"action":"end_turn"}'},
                                 'finish_reason': 'stop'}], 'usage': {'completion_tokens': 8}}
        with tempfile.TemporaryDirectory() as td, patch.object(m, 'prepare', return_value=(self.ctx, self.queries)):
            path = Path(td)/'pilot.json'
            args = self.args(mock=False)
            with patch.object(m, 'output_path', return_value=path), patch.object(m, 'http_json', side_effect=http), patch.object(m, 'live_receipt', return_value=self.receipt()), patch('builtins.print'):
                args.stop_at_unix = 0
                with self.assertRaisesRegex(ValueError, 'no progress'):
                    m.run(args)
                self.assertEqual(calls, [])
                args.stop_at_unix = 10**12
                m.run(args)
            r = json.loads(path.read_text())
            m.check_report(r, 'qwen3-8b', False, self.queries, self.ctx)
            r['rows'][0]['evidence']['server_receipt']['runtime_versions'] = {}
            r['rows'][0]['evidence_sha256'] = m.c.digest_json(r['rows'][0]['evidence'])
            with self.assertRaisesRegex(ValueError, 'runtime'):
                m.check_report(r, 'qwen3-8b', False, self.queries, self.ctx)


if __name__ == '__main__':
    unittest.main()
