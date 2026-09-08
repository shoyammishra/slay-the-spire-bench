"""Focused known-answer tests for the controlled-H batch amendment."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from tempfile import TemporaryDirectory
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import scripts.confirmatory_batch as batch
from scripts.controlled_horizon_confirmatory import (
    code_receipt, load_protocol, make_row, query_schedule, row_path,
)
from scripts.controlled_horizon_pilot import _atomic_write_json


def synthetic_chain():
    protocol, _ = load_protocol()
    protocol = copy.deepcopy(protocol)
    protocol["inference"]["expected_query_count"] = 8
    fixtures = {
        "ironclad": SimpleNamespace(character="ironclad", fixture_id="ironclad"),
        "silent": SimpleNamespace(character="silent", fixture_id="silent"),
    }
    oracle = {
        "oracles": {
            str(h): {
                "action_values": {"end_turn:-1:-1": 0.0, "play:0:0": 1.0},
                "best_value": 1.0, "worst_value": 0.0, "exact": True,
            } for h in (1, 2, 4, 8)
        }
    }
    oracles = {fixture_id: copy.deepcopy(oracle) for fixture_id in fixtures}
    prompts = {
        fixture_id: {h: ("system", f"fixture={fixture_id}; H={h}")
                     for h in (1, 2, 4, 8)}
        for fixture_id in fixtures
    }
    context = (fixtures, oracles, {fixture_id: False for fixture_id in fixtures}, prompts)
    schedule = query_schedule(protocol, fixtures, context[2])
    first_query = schedule[0]
    first_id = first_query["fixture_id"]
    first = make_row(first_query, prompts[first_id], oracles[first_id],
                     {"action": "end_turn", "card_index": -1, "target_index": -1},
                     '{"action":"end_turn","card_index":-1,"target_index":-1}',
                     "stop")
    parent = {"contract": {}, "pending": None, "complete": False}
    return protocol, "original-test-digest", context, schedule, Path("parent"), parent, [first]


def synthetic_amendment(expected=8):
    amendment, _ = batch.load_amendment()
    amendment = copy.deepcopy(amendment)
    amendment["status"] = "test"
    amendment["original_protocol"]["expected_queries"] = expected
    amendment["original_protocol"]["completed_parent_queries"] = 1
    amendment["journal"]["coverage_start_index"] = 1
    amendment["batch"]["first_continuation_global_index"] = 1
    amendment["batch"]["first_continuation_batch_queries"] = 1
    return amendment


def args_for(directory: Path, journal: Path, out: Path, count=2):
    return SimpleNamespace(
        source_dir=directory, journal=journal, provider="mock", out=out,
        base_url="http://localhost:8000/v1", server_receipt=None,
        authorize_model_inference=False, max_new_queries=count,
        stop_at_unix=None,
    )


def test_mock_batches_are_contiguous_and_exact_once():
    amendment = synthetic_amendment()
    chain = synthetic_chain()
    with TemporaryDirectory() as directory_name, patch.object(
            batch, "_validate_parent", return_value=chain) as validate_parent:
        directory = Path(directory_name)
        journal = directory / "mock-journal.json"
        first_path = directory / "arbitrary-first.json"
        first = batch.run_batch(args_for(directory, journal, first_path), amendment, "test")
        assert first["next_global_index"] == 3 and first["finalized_sessions"] == 1
        first_report = json.loads(first_path.read_text(encoding="utf-8"))
        first_rows = [json.loads(row_path(first_path, i).read_text(encoding="utf-8"))
                      for i in range(2)]
        assert [row["index"] for row in first_rows] == [1, 2]
        assert first_report["finalized"] and first_report["stop_reason"] == "batch_cap"

        second_path = directory / "arbitrary-second.json"
        second = batch.run_batch(args_for(directory, journal, second_path), amendment, "test")
        assert second["next_global_index"] == 5 and second["finalized_sessions"] == 2
        try:
            batch.run_batch(args_for(directory, journal, second_path), amendment, "test")
            assert False, "an existing session artifact was reused"
        except ValueError:
            pass
        assert validate_parent.call_count == 3  # one per run, including the rejected reuse
    print("[PASS] batch sessions cover each global query exactly once")


def test_zero_row_finalized_session_preserves_the_next_query():
    amendment = synthetic_amendment()
    chain = synthetic_chain()
    protocol, protocol_digest, context, schedule, *_ = chain
    with TemporaryDirectory() as directory_name, patch.object(
            batch, "_validate_parent", return_value=chain):
        directory = Path(directory_name)
        journal_path = directory / "journal.json"
        session_path = directory / "deadline-session.json"
        journal = batch._new_journal(amendment, "test", protocol_digest, schedule)
        journal["active_session_id"] = 1
        journal["active_session_filename"] = session_path.name
        report = active_report(amendment, chain)
        report["pending"] = None
        _atomic_write_json(session_path, report)
        batch._finalize_session(report, session_path, "deadline_headroom")
        rows = batch._validate_session(
            report, session_path, amendment, "test", protocol, protocol_digest,
            context, schedule, True)
        batch._append_finalized(journal, journal_path, amendment, report,
                                session_path, rows)
        status = batch.inspect_chain(amendment, "test", directory, journal_path)
        assert status["next_global_index"] == 1
        assert status["runnable"]
        next_path = directory / "next-session.json"
        result = batch.run_batch(args_for(directory, journal_path, next_path, 1),
                                 amendment, "test")
        assert result["next_global_index"] == 2
        next_row = json.loads(row_path(next_path, 0).read_text(encoding="utf-8"))
        assert next_row["index"] == 1
    print("[PASS] a zero-row deadline stop leaves the next query unconsumed")


def active_report(amendment, chain, start=1, planned_end=2):
    protocol, protocol_digest, _context, schedule, *_ = chain
    return {
        "result_schema_version": "2.1-batch-session",
        "run_kind": "controlled-h-confirmatory-batch-session",
        "amendment_id": amendment["amendment_id"],
        "amendment_digest": "test",
        "original_protocol_digest": protocol_digest,
        "parent_report_sha256": amendment["parent"]["report_sha256"],
        "schedule_sha256": batch.digest_json(schedule),
        "session_id": 1, "start_global_index": start,
        "requested_max_new_queries": planned_end - start,
        "initial_planned_end_global_index": planned_end,
        "planned_end_global_index": planned_end, "end_global_index": None,
        "provider": "mock", "model_inference": False,
        "model": protocol["inference"], "transport": protocol["transport"],
        "source_code_sha256": code_receipt(), "server_provenance": None,
        "stop_at_unix": None,
        "runtime_versions": {"vllm": None, "transformers": None, "numpy": None},
        "created_at_utc": "test", "completed_rows": [],
        "pending": schedule[start], "complete": False,
        "finalized": False, "stop_reason": None,
    }


def write_active(directory, amendment, chain, with_row=False):
    journal_path = directory / "journal.json"
    protocol_digest = chain[1]
    schedule = chain[3]
    journal = batch._new_journal(amendment, "test", protocol_digest, schedule)
    session_path = directory / "active.json"
    journal["active_session_id"] = 1
    journal["active_session_filename"] = session_path.name
    _atomic_write_json(journal_path, journal)
    report = active_report(amendment, chain)
    _atomic_write_json(session_path, report)
    if with_row:
        query = schedule[1]
        fixture_id = query["fixture_id"]
        context = chain[2]
        row = make_row(query, context[3][fixture_id], context[1][fixture_id],
                       {"action": "end_turn", "card_index": -1, "target_index": -1},
                       '{"action":"end_turn","card_index":-1,"target_index":-1}',
                       "stop")
        _atomic_write_json(row_path(session_path, 0), row)
    return journal_path, session_path


def test_pending_resolution_never_requeries_and_preserves_existing_row():
    amendment = synthetic_amendment()
    chain = synthetic_chain()
    for with_row, expected_failure in ((False, "ambiguous_query"), (True, None)):
        with TemporaryDirectory() as directory_name, patch.object(
                batch, "_validate_parent", return_value=chain):
            directory = Path(directory_name)
            journal, session = write_active(directory, amendment, chain, with_row)
            status = batch.resolve_active(
                SimpleNamespace(source_dir=directory, journal=journal), amendment, "test")
            row = json.loads(row_path(session, 0).read_text(encoding="utf-8"))
            assert row["diagnostics"]["execution_failure"] == expected_failure
            assert status["next_global_index"] == 2
            assert status["claim_already_failed"] is (expected_failure is not None)
    print("[PASS] pending response is reconciled or explicitly failed without requery")


def test_finalized_orphan_is_reconciled_before_next_batch():
    amendment = synthetic_amendment()
    chain = synthetic_chain()
    with TemporaryDirectory() as directory_name, patch.object(
            batch, "_validate_parent", return_value=chain):
        directory = Path(directory_name)
        journal_path = directory / "journal.json"
        session_path = directory / "first.json"
        batch.run_batch(args_for(directory, journal_path, session_path, 1),
                        amendment, "test")
        journal = json.loads(journal_path.read_text(encoding="utf-8"))
        journal["sessions"] = []
        journal["next_global_index"] = 1
        journal["complete"] = False
        journal["active_session_id"] = 1
        journal["active_session_filename"] = session_path.name
        _atomic_write_json(journal_path, journal)
        status = batch.inspect_chain(amendment, "test", directory, journal_path)
        assert status["active_session_status"] == "finalized_orphan"
        second_path = directory / "second.json"
        result = batch.run_batch(args_for(directory, journal_path, second_path, 1),
                                 amendment, "test")
        assert result["next_global_index"] == 3
        journal = json.loads(journal_path.read_text(encoding="utf-8"))
        assert [entry["filename"] for entry in journal["sessions"]] == [
            session_path.name, second_path.name]
    print("[PASS] finalized orphan is journaled before new coverage")


def test_tamper_overlap_and_server_receipt_are_rejected():
    amendment = synthetic_amendment()
    chain = synthetic_chain()
    with TemporaryDirectory() as directory_name, patch.object(
            batch, "_validate_parent", return_value=chain):
        directory = Path(directory_name)
        journal_path = directory / "journal.json"
        session_path = directory / "session.json"
        batch.run_batch(args_for(directory, journal_path, session_path, 1),
                        amendment, "test")
        row_path(session_path, 0).write_text("{}", encoding="utf-8")
        try:
            batch.inspect_chain(amendment, "test", directory, journal_path)
            assert False, "row tamper was accepted"
        except (ValueError, KeyError):
            pass

    protocol, protocol_digest, context, schedule, *_ = chain
    report = active_report(amendment, chain)
    report.update(provider="local", model_inference=True, pending=None,
                  server_provenance={"endpoint_sha256": "bad", "launch_receipt": {}},
                  completed_rows=[], complete=True, finalized=True,
                  planned_end_global_index=1, end_global_index=1)
    with TemporaryDirectory() as directory_name:
        path = Path(directory_name) / "local.json"
        _atomic_write_json(path, report)
        try:
            batch._validate_session(report, path, amendment, "test", protocol,
                                    protocol_digest, context, schedule, True)
            assert False, "mismatched server receipt was accepted"
        except (ValueError, KeyError):
            pass
    print("[PASS] missing/tampered rows and mismatched server receipts fail closed")


def test_deadline_requires_full_timeout_and_headroom():
    amendment = synthetic_amendment()
    with patch.object(batch, "now_unix", return_value=1000.0):
        assert batch.deadline_allows(2080.0, amendment)
        assert not batch.deadline_allows(2079.999, amendment)
    print("[PASS] deadline guard reserves 900s request plus 180s persistence headroom")


def test_continuation_smoke_is_a_one_query_fail_closed_gate():
    assert batch._continuation_smoke_ok({
        "index": 1,
        "score": {"parse_ok": True, "schema_ok": True, "legal": True},
        "diagnostics": {"truncated": False, "execution_failure": None},
    })
    assert not batch._continuation_smoke_ok({
        "index": 1,
        "score": {"parse_ok": True, "schema_ok": True, "legal": False},
        "diagnostics": {"truncated": False, "execution_failure": None},
    })
    print("[PASS] first continuation is a one-query fail-closed stack smoke")


def test_diagnostic_outputs_and_journal_metadata_are_protected():
    from types import SimpleNamespace
    amendment = synthetic_amendment()
    chain = synthetic_chain()
    with TemporaryDirectory() as directory_name, patch.object(batch, '_validate_parent', return_value=chain):
        directory = Path(directory_name)
        journal = directory / 'journal.json'
        session = directory / 'session.json'
        batch.run_batch(args_for(directory, journal, session, 1), amendment, 'test')
        for target in (journal, session, row_path(session, 0)):
            args = SimpleNamespace(out=target, journal=journal, source_dir=directory)
            try:
                batch.protect_diagnostic_output(args, chain[0], amendment)
                assert False, 'diagnostic allowed to overwrite evidence'
            except ValueError:
                pass
        saved = json.loads(journal.read_text(encoding='utf-8'))
        saved['sessions'][0]['end_global_index'] += 1
        _atomic_write_json(journal, saved)
        try:
            batch.inspect_chain(amendment, 'test', directory, journal)
            assert False, 'changed journal reference metadata accepted'
        except ValueError:
            pass
    print('[PASS] diagnostics cannot overwrite evidence; journal metadata is bound')


def test_persisted_real_chain_cannot_bypass_smoke_cap():
    amendment = synthetic_amendment()
    chain = synthetic_chain()
    with TemporaryDirectory() as directory_name, patch.object(batch, '_validate_parent', return_value=chain):
        directory = Path(directory_name)
        journal = directory / 'journal.json'
        session = directory / 'session.json'
        batch.run_batch(args_for(directory, journal, session, 2), amendment, 'test')
        report = json.loads(session.read_text(encoding='utf-8'))
        report.update(provider='local', model_inference=True)
        _atomic_write_json(session, report)
        manifest = json.loads(journal.read_text(encoding='utf-8'))
        manifest['sessions'][0]['report_sha256'] = batch._sha256(session)
        _atomic_write_json(journal, manifest)
        try:
            batch.inspect_chain(amendment, 'test', directory, journal)
            assert False, 'persisted real session bypassed first-query cap'
        except ValueError as exc:
            assert 'one-query smoke cap' in str(exc)
    with TemporaryDirectory() as directory_name, patch.object(batch, '_validate_parent', return_value=chain):
        directory = Path(directory_name)
        journal = directory / 'journal.json'
        first, second = directory / 'first.json', directory / 'second.json'
        invalid_llm = batch.MockLLM(['not-json'])
        with patch.object(batch, 'MockLLM', return_value=invalid_llm):
            batch.run_batch(args_for(directory, journal, first, 1), amendment, 'test')
        batch.run_batch(args_for(directory, journal, second, 1), amendment, 'test')
        report = json.loads(second.read_text(encoding='utf-8'))
        report.update(provider='local', model_inference=True)
        _atomic_write_json(second, report)
        manifest = json.loads(journal.read_text(encoding='utf-8'))
        manifest['sessions'][1]['report_sha256'] = batch._sha256(second)
        _atomic_write_json(journal, manifest)
        try:
            batch.inspect_chain(amendment, 'test', directory, journal)
            assert False, 'persisted continuation accepted a failed smoke'
        except ValueError as exc:
            assert 'failed or missing smoke' in str(exc)
    print('[PASS] persisted real sessions independently enforce the smoke cap')


if __name__ == "__main__":
    tests = [
        test_mock_batches_are_contiguous_and_exact_once,
        test_zero_row_finalized_session_preserves_the_next_query,
        test_pending_resolution_never_requeries_and_preserves_existing_row,
        test_finalized_orphan_is_reconciled_before_next_batch,
        test_tamper_overlap_and_server_receipt_are_rejected,
        test_deadline_requires_full_timeout_and_headroom,
        test_continuation_smoke_is_a_one_query_fail_closed_gate,
        test_diagnostic_outputs_and_journal_metadata_are_protected,
        test_persisted_real_chain_cannot_bypass_smoke_cap,
    ]
    passed = failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except Exception:
            import traceback
            traceback.print_exc()
            failed += 1
    print(f"Results: {passed} passed, {failed} failed")
    if failed:
        raise SystemExit(1)
