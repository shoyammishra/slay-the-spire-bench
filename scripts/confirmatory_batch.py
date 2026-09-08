#!/usr/bin/env python
"""Versioned, exact-once batch continuation for controlled-H confirmation."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
from pathlib import Path
import re
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.controlled_horizon_confirmatory import (  # noqa: E402
    code_receipt, digest_json, effective_quality, exclusive_writer, load_context,
    load_protocol, load_rows, make_row, query_schedule, row_directory, row_path,
    serving_receipt, validate_row, verify_live_server,
)
from scripts.controlled_horizon_confirmatory_analysis import analyze_rows, planning_power  # noqa: E402
from scripts.controlled_horizon_model_pilot import _package_version, validate_serving_stack  # noqa: E402
from scripts.controlled_horizon_pilot import _atomic_write_json  # noqa: E402
from slay_bench.benchmark import LocalLLM, MockLLM, RateLimitExhausted  # noqa: E402


AMENDMENT_PATH = ROOT / "configs" / "controlled_h_v2_batch_amendment.json"
AMENDMENT_DIGEST = 'ba73b91d23336923b8ea96f693df5cc836c0f13e51b4f2bd1b44bf311863caad'


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source_sha256(path: Path, normalize_digest: bool = False) -> str:
    source = path.read_text(encoding="utf-8")
    if normalize_digest:
        source = re.sub(
            r"(?m)^AMENDMENT_DIGEST = '(?:[0-9a-f]{64}|<amendment-digest>)'$",
            "AMENDMENT_DIGEST = '<amendment-digest>'", source)
    return hashlib.sha256(source.encode()).hexdigest()


def load_amendment(path: Path = AMENDMENT_PATH) -> tuple[dict, str]:
    amendment = json.loads(path.read_text(encoding="utf-8"))
    digest = digest_json(amendment)
    if AMENDMENT_DIGEST != '<amendment-digest>' and digest != AMENDMENT_DIGEST:
        raise ValueError("batch amendment differs from freeze")
    locks = amendment["source_lock"]
    for key, spec in locks.items():
        source = ROOT / spec["filename"]
        actual = _source_sha256(source, normalize_digest=(key == "script"))
        if spec["sha256"] != "PENDING" and actual != spec["sha256"]:
            raise ValueError(f"batch amendment {key} differs from freeze")
    if amendment.get("status") == "frozen-before-batch-continuation":
        if AMENDMENT_DIGEST == '<amendment-digest>' or any(
                spec["sha256"] == "PENDING" for spec in locks.values()):
            raise ValueError("batch amendment claims frozen status without hashes")
    return amendment, digest


def _validate_parent(amendment: dict, source_dir: Path):
    protocol, protocol_digest = load_protocol()
    original = amendment["original_protocol"]
    if (protocol["protocol_id"] != original["protocol_id"]
            or protocol_digest != original["protocol_digest"]
            or protocol["inference"]["expected_query_count"] != original["expected_queries"]):
        raise ValueError("original confirmatory protocol differs from amendment")
    context = load_context(protocol, source_dir)
    schedule = query_schedule(protocol, context[0], context[2])
    parent_spec = amendment["parent"]
    parent_path = source_dir / parent_spec["report_filename"]
    receipt_path = source_dir / parent_spec["server_receipt_filename"]
    if _sha256(parent_path) != parent_spec["report_sha256"]:
        raise ValueError("original smoke report differs from amendment")
    if _sha256(row_path(parent_path, 0)) != parent_spec["first_row_sha256"]:
        raise ValueError("original smoke response differs from amendment")
    if _sha256(receipt_path) != parent_spec["server_receipt_sha256"]:
        raise ValueError("original server receipt differs from amendment")
    report = json.loads(parent_path.read_text(encoding="utf-8"))
    rows = load_rows(report, parent_path, schedule, context)
    if (len(rows) != original["completed_parent_queries"] or report.get("pending") is not None
            or report.get("complete") is not False):
        raise ValueError("original smoke checkpoint state differs from amendment")
    first = rows[0]
    if (not first["score"]["legal"] or first["diagnostics"]["truncated"]
            or first["diagnostics"]["execution_failure"] is not None):
        raise ValueError("original smoke response is not legal and nontruncated")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if report["contract"].get("server_provenance", {}).get("launch_receipt") != receipt:
        raise ValueError("original smoke report and receipt differ")
    if (report["contract"].get("protocol_digest") != protocol_digest
            or report["contract"].get("schedule_sha256") != digest_json(schedule)
            or report["contract"].get("source_code_sha256") != code_receipt()
            or report.get("model") != protocol["inference"]
            or report.get("model_inference") is not True):
        raise ValueError("original smoke execution contract differs")
    return protocol, protocol_digest, context, schedule, parent_path, report, rows


def canonical_journal(amendment: dict) -> Path:
    return ROOT / "results" / amendment["journal"]["real_filename"]


def _session_path(journal_path: Path, amendment: dict, session_id: int) -> Path:
    spec = amendment["journal"]
    name = f"{spec['real_session_prefix']}{session_id:0{spec['session_digits']}d}.json"
    return journal_path.with_name(name)


def _new_journal(amendment: dict, amendment_digest: str, protocol_digest: str,
                 schedule: list[dict]) -> dict:
    return {
        "result_schema_version": "2.1-batch-amendment",
        "run_kind": "controlled-h-confirmatory-batch-journal",
        "amendment_id": amendment["amendment_id"],
        "amendment_digest": amendment_digest,
        "original_protocol_digest": protocol_digest,
        "parent_report_sha256": amendment["parent"]["report_sha256"],
        "schedule_sha256": digest_json(schedule),
        "expected_queries": len(schedule),
        "parent_completed_queries": amendment["original_protocol"]["completed_parent_queries"],
        "created_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "sessions": [],
        "active_session_id": None,
        "active_session_filename": None,
        "next_global_index": amendment["journal"]["coverage_start_index"],
        "complete": False,
    }


def _load_journal(path: Path, amendment: dict, amendment_digest: str,
                  protocol_digest: str, schedule: list[dict]) -> dict:
    journal = (json.loads(path.read_text(encoding="utf-8")) if path.exists()
               else _new_journal(amendment, amendment_digest, protocol_digest, schedule))
    expected = {
        "result_schema_version": "2.1-batch-amendment",
        "run_kind": "controlled-h-confirmatory-batch-journal",
        "amendment_id": amendment["amendment_id"],
        "amendment_digest": amendment_digest,
        "original_protocol_digest": protocol_digest,
        "parent_report_sha256": amendment["parent"]["report_sha256"],
        "schedule_sha256": digest_json(schedule),
        "expected_queries": len(schedule),
        "parent_completed_queries": amendment["original_protocol"]["completed_parent_queries"],
    }
    if any(journal.get(key) != value for key, value in expected.items()):
        raise ValueError("batch journal contract differs from amendment")
    return journal


def _session_schedule(report: dict, schedule: list[dict]) -> list[dict]:
    start = report["start_global_index"]
    end = report["planned_end_global_index"]
    if (not isinstance(start, int) or not isinstance(end, int)
            or not 0 <= start <= end <= len(schedule)):
        raise ValueError("invalid session schedule bounds")
    return schedule[start:end]


def _validate_session(report: dict, path: Path, amendment: dict,
                      amendment_digest: str, protocol: dict, protocol_digest: str,
                      context, schedule: list[dict], require_finalized: bool) -> list[dict]:
    provider = report.get("provider")
    if (report.get("run_kind") != "controlled-h-confirmatory-batch-session"
            or report.get("result_schema_version") != "2.1-batch-session"
            or report.get("amendment_id") != amendment["amendment_id"]
            or report.get("amendment_digest") != amendment_digest
            or report.get("original_protocol_digest") != protocol_digest
            or report.get("parent_report_sha256") != amendment["parent"]["report_sha256"]
            or report.get("schedule_sha256") != digest_json(schedule)
            or report.get("model") != protocol["inference"]
            or report.get("transport") != protocol["transport"]
            or report.get("source_code_sha256") != code_receipt()
            or provider not in ("mock", "local")
            or report.get("model_inference") != (provider == "local")):
        raise ValueError("batch session contract differs from amendment")
    if provider == "local":
        from scripts.controlled_horizon_confirmatory_server import server_command
        provenance = report.get("server_provenance")
        receipt = provenance.get("launch_receipt") if isinstance(provenance, dict) else None
        expected_runtime = {
            key: protocol["inference"]["serving_stack"][key + "_version"]
            for key in ("vllm", "transformers")}
        if (not isinstance(receipt, dict)
                or receipt.get("protocol_digest") != protocol_digest
                or receipt.get("endpoint_sha256") != provenance.get("endpoint_sha256")
                or receipt.get("command") != server_command(protocol, receipt.get("port"))
                or receipt.get("runtime_versions") != expected_runtime
                or any(report.get("runtime_versions", {}).get(key) != value
                       for key, value in expected_runtime.items())):
            raise ValueError("batch session server provenance differs from freeze")
    elif report.get("server_provenance") is not None:
        raise ValueError("mock batch session carries server provenance")
    requested = report.get("requested_max_new_queries")
    initial_end = report.get("initial_planned_end_global_index")
    start = report.get("start_global_index")
    if (not isinstance(requested, int) or isinstance(requested, bool)
            or not 1 <= requested <= amendment["batch"]["maximum_new_queries"]
            or initial_end != min(len(schedule), start + requested)
            or report.get("planned_end_global_index") > initial_end):
        raise ValueError("batch session declared bounds differ from amendment")
    if provider == "local" and (not isinstance(report.get("stop_at_unix"), (int, float))
                                or isinstance(report.get("stop_at_unix"), bool)
                                or not math.isfinite(report["stop_at_unix"])):
        raise ValueError("real batch session lacks a finite deadline")
    if provider == "mock" and report.get("stop_at_unix") is not None:
        raise ValueError("mock batch session carries a real deadline")
    if require_finalized and (report.get("finalized") is not True
                              or report.get("pending") is not None):
        raise ValueError("batch session is not finalized")
    subset = _session_schedule(report, schedule)
    rows = load_rows(report, path, subset, context)
    if rows and rows[0]["index"] != report["start_global_index"]:
        raise ValueError("session starts at the wrong global query")
    if any(row["index"] != report["start_global_index"] + i
           for i, row in enumerate(rows)):
        raise ValueError("session response coverage is not contiguous")
    if report.get("finalized"):
        if (not report.get("complete") or report.get("end_global_index")
                != report["start_global_index"] + len(rows)):
            raise ValueError("finalized session coverage metadata differs")
        # A finalized session's planned bound is narrowed to its exact coverage.
        if report["planned_end_global_index"] != report["end_global_index"]:
            raise ValueError("finalized session retains unaccounted planned queries")
    return rows


def _validate_journal_sessions(journal: dict, journal_path: Path, amendment: dict,
                               amendment_digest: str, protocol: dict,
                               protocol_digest: str, context, schedule: list[dict]):
    rows = []
    next_index = amendment["journal"]["coverage_start_index"]
    real_journal = journal_path.resolve() == canonical_journal(amendment).resolve()
    for number, entry in enumerate(journal["sessions"], 1):
        path = journal_path.with_name(entry["filename"])
        canonical_name_ok = (not real_journal or path == _session_path(
            journal_path, amendment, number))
        if (entry.get("session_id") != number or not canonical_name_ok
                or Path(entry["filename"]).name != entry["filename"]
                or _sha256(path) != entry.get("report_sha256")):
            raise ValueError("journal session reference differs from canonical artifact")
        report = json.loads(path.read_text(encoding="utf-8"))
        if (report.get("session_id") != number
                or entry.get("start_global_index") != report.get("start_global_index")
                or entry.get("end_global_index") != report.get("end_global_index")):
            raise ValueError("journal reference metadata differs from session")
        if real_journal and report.get("provider") != "local":
            raise ValueError("canonical real journal contains a mock session")
        if report.get('provider') == 'local':
            first_index = amendment['batch']['first_continuation_global_index']
            if report.get('start_global_index') == first_index:
                if report.get('requested_max_new_queries') != amendment['batch']['first_continuation_batch_queries']:
                    raise ValueError('persisted first continuation violates one-query smoke cap')
            elif not _continuation_smoke_ok(next((r for r in rows if r['index'] == first_index), {})):
                raise ValueError('persisted continuation follows a failed or missing smoke')
        session_rows = _validate_session(
            report, path, amendment, amendment_digest, protocol, protocol_digest,
            context, schedule, True)
        if (report["start_global_index"] != next_index
                or report["end_global_index"] != next_index + len(session_rows)):
            raise ValueError("journal session coverage overlaps or has a gap")
        next_index = report["end_global_index"]
        rows.extend(session_rows)
    if (journal.get("next_global_index") != next_index
            or journal.get("complete") != (next_index == len(schedule))):
        raise ValueError("journal completion metadata differs from session coverage")
    if real_journal:
        prefix = amendment["journal"]["real_session_prefix"]
        allowed_reports = {entry["filename"] for entry in journal["sessions"]}
        allowed_reports.add(_session_path(
            journal_path, amendment, len(journal["sessions"]) + 1).name)
        if any(path.name not in allowed_reports
               for path in journal_path.parent.glob(prefix + "*.json")):
            raise ValueError("foreign real session report outside journal chain")
        allowed_row_dirs = {name + ".rows" for name in allowed_reports}
        if any(path.name not in allowed_row_dirs
               for path in journal_path.parent.glob(prefix + "*.json.rows")):
            raise ValueError("foreign real session row directory outside journal chain")
    return rows, next_index


def _continuation_smoke_ok(row: dict) -> bool:
    return (row.get("index") == 1
            and row.get("score", {}).get("parse_ok") is True
            and row.get("score", {}).get("schema_ok") is True
            and row.get("score", {}).get("legal") is True
            and row.get("diagnostics", {}).get("truncated") is False
            and row.get("diagnostics", {}).get("execution_failure") is None)


def _orphan_status(journal: dict, journal_path: Path, amendment: dict,
                   amendment_digest: str, protocol: dict, protocol_digest: str,
                   context, schedule: list[dict]):
    session_id = len(journal["sessions"]) + 1
    active_id = journal.get("active_session_id")
    active_name = journal.get("active_session_filename")
    if (active_id is None) != (active_name is None):
        raise ValueError("journal active-session reservation is incomplete")
    if active_id is not None:
        if (active_id != session_id or Path(active_name).name != active_name):
            raise ValueError("journal active-session reservation is invalid")
        path = journal_path.with_name(active_name)
        if not path.exists():
            return "reserved", path, None, []
    else:
        path = _session_path(journal_path, amendment, session_id)
    if not path.exists():
        return None, path, None, []
    report = json.loads(path.read_text(encoding="utf-8"))
    rows = _validate_session(report, path, amendment, amendment_digest, protocol,
                             protocol_digest, context, schedule, False)
    if report.get("session_id") != session_id:
        raise ValueError("orphan session number differs from canonical position")
    return ("finalized_orphan" if report.get("finalized") else
            "pending" if report.get("pending") is not None else "interrupted"), path, report, rows


def _append_finalized(journal: dict, journal_path: Path, amendment: dict,
                      report: dict, path: Path, rows: list[dict]) -> None:
    expected_start = journal["next_global_index"]
    if report["start_global_index"] != expected_start:
        raise ValueError("orphan session does not continue journal")
    entry = {
        "session_id": report["session_id"], "filename": path.name,
        "start_global_index": expected_start,
        "end_global_index": expected_start + len(rows),
        "report_sha256": _sha256(path),
    }
    journal["sessions"].append(entry)
    journal["active_session_id"] = None
    journal["active_session_filename"] = None
    journal["next_global_index"] = entry["end_global_index"]
    journal["complete"] = journal["next_global_index"] == journal["expected_queries"]
    _atomic_write_json(journal_path, journal)


def inspect_chain(amendment: dict, amendment_digest: str, source_dir: Path,
                  journal_path: Path, validated_parent=None) -> dict:
    # A caller that just validated the immutable parent may reuse that result for
    # this in-process status pass. Separate CLI invocations always reload it.
    parent_state = (validated_parent if validated_parent is not None
                    else _validate_parent(amendment, source_dir))
    protocol, protocol_digest, context, schedule, _parent_path, _parent, parent_rows = (
        parent_state)
    journal = _load_journal(journal_path, amendment, amendment_digest,
                            protocol_digest, schedule)
    session_rows, next_index = _validate_journal_sessions(
        journal, journal_path, amendment, amendment_digest, protocol,
        protocol_digest, context, schedule)
    status, orphan_path, orphan, orphan_rows = _orphan_status(
        journal, journal_path, amendment, amendment_digest, protocol,
        protocol_digest, context, schedule)
    virtual_next = next_index
    if status == "finalized_orphan":
        if orphan["start_global_index"] != next_index:
            raise ValueError("finalized orphan does not continue journal")
        virtual_next += len(orphan_rows)
    all_rows = parent_rows + session_rows + orphan_rows
    failures = sum(row["diagnostics"]["execution_failure"] is not None for row in all_rows)
    unresolved = status in ("reserved", "pending", "interrupted")
    complete = virtual_next == len(schedule) and not unresolved
    real_chain = journal_path.resolve() == canonical_journal(amendment).resolve()
    continuation_smoke_passed = (None if virtual_next <= 1 else
                                 _continuation_smoke_ok(next(
                                     row for row in all_rows if row["index"] == 1)))
    failed_smoke = real_chain and continuation_smoke_passed is False
    return {
        "runnable": not complete and not unresolved and not failed_smoke,
        "complete": complete,
        "next_global_index": virtual_next,
        "expected_queries": len(schedule),
        "finalized_sessions": len(journal["sessions"]) + (status == "finalized_orphan"),
        "active_session_status": status,
        "active_session_path": str(orphan_path) if status else None,
        "claim_already_failed": failures > 0,
        "execution_failures": failures,
        "continuation_smoke_passed": continuation_smoke_passed,
        "reason": ("complete" if complete else "unresolved active session" if unresolved
                   else "continuation smoke failed" if failed_smoke else "ready"),
    }


# Kept as a named boundary so tests can patch only wall-clock time.
def now_unix() -> float:
    return time.time()


def deadline_allows(stop_at_unix: float, amendment: dict) -> bool:
    batch = amendment["batch"]
    return (stop_at_unix - now_unix()
            >= batch["request_timeout_seconds"] + batch["deadline_headroom_seconds"])


def _protected_paths(protocol: dict, amendment: dict, source_dir: Path) -> set[Path]:
    paths = {AMENDMENT_PATH.resolve(),
             (ROOT / 'configs/controlled_h_v2_confirmatory.json').resolve(),
             (source_dir / amendment["parent"]["report_filename"]).resolve(),
             (source_dir / amendment["parent"]["server_receipt_filename"]).resolve()}
    paths.update((ROOT / name).resolve() for name in code_receipt())
    paths.update((ROOT / spec['filename']).resolve() for spec in amendment.get('source_lock', {}).values())
    for spec in protocol["sources"].values():
        path = source_dir / spec["filename"] if spec["kind"] == "result" else ROOT / spec["filename"]
        paths.add(path.resolve())
    return paths


def protect_diagnostic_output(args, protocol, amendment):
    target = args.out.resolve()
    protected = _protected_paths(protocol, amendment, args.source_dir)
    protected.update((args.journal.resolve(), canonical_journal(amendment).resolve()))
    if args.journal.exists():
        journal = json.loads(args.journal.read_text(encoding='utf-8'))
        protected.update(args.journal.with_name(ref['filename']).resolve()
                         for ref in journal['sessions'])
        if journal.get('active_session_filename'):
            protected.add(args.journal.with_name(journal['active_session_filename']).resolve())
    if (target in protected or any(part.endswith('.rows') for part in target.parts)
            or target.name.startswith(amendment['journal']['real_session_prefix'])):
        raise ValueError('diagnostic output would overwrite frozen source or session evidence')


def _write_row(report: dict, path: Path, row: dict) -> None:
    local_index = len(report["completed_rows"])
    target = row_path(path, local_index)
    if target.exists():
        if json.loads(target.read_text(encoding="utf-8")) != row:
            raise ValueError("refusing to overwrite an existing batch response")
    else:
        _atomic_write_json(target, row)
    report["completed_rows"].append({"index": local_index, "sha256": _sha256(target)})
    report["pending"] = None
    report["complete"] = len(report["completed_rows"]) == (
        report["planned_end_global_index"] - report["start_global_index"])
    _atomic_write_json(path, report)


def _reconcile_pending(report: dict, path: Path, subset: list[dict], context,
                       as_failure: bool) -> None:
    local_index = len(report["completed_rows"])
    if report.get("pending") is None:
        return
    if local_index >= len(subset) or report["pending"] != subset[local_index]:
        raise ValueError("active session pending query differs from schedule")
    query = subset[local_index]
    target = row_path(path, local_index)
    fid = query["fixture_id"]
    if target.exists():
        row = json.loads(target.read_text(encoding="utf-8"))
        validate_row(row, query, context[3][fid], context[1][fid])
        _write_row(report, path, row)
    elif as_failure:
        row = make_row(query, context[3][fid], context[1][fid],
                       {"error": "ambiguous_query"}, None, None, "ambiguous_query")
        _write_row(report, path, row)
    else:
        raise ValueError("ambiguous active query requires explicit no-inference resolution")


def _finalize_session(report: dict, path: Path, stop_reason: str) -> None:
    if report.get("pending") is not None:
        raise ValueError("cannot finalize a pending session")
    report["end_global_index"] = report["start_global_index"] + len(report["completed_rows"])
    report["planned_end_global_index"] = report["end_global_index"]
    report["complete"] = True
    report["finalized"] = True
    report["stop_reason"] = stop_reason
    report["finalized_at_utc"] = dt.datetime.now(dt.timezone.utc).isoformat()
    _atomic_write_json(path, report)


def run_batch(args, amendment: dict, amendment_digest: str) -> dict:
    parent_state = _validate_parent(amendment, args.source_dir)
    protocol, protocol_digest, context, schedule, _parent_path, _parent, _parent_rows = (
        parent_state)
    real = args.provider == "local"
    if real and amendment.get("status") != "frozen-before-batch-continuation":
        raise ValueError("real inference is forbidden under an unfrozen amendment")
    journal_path = canonical_journal(amendment) if real else args.journal
    if real and args.journal.resolve() != journal_path.resolve():
        raise ValueError("real batch continuation requires the canonical journal")
    if real and args.out is not None:
        raise ValueError("real session path is canonical; --out is mock-only")
    if not real and args.out is None:
        raise ValueError("mock batch requires an explicit --out session path")
    if not real and journal_path.resolve() == canonical_journal(amendment).resolve():
        raise ValueError("mock batch must not use the canonical real journal")
    if not 1 <= args.max_new_queries <= amendment["batch"]["maximum_new_queries"]:
        raise ValueError("batch query count is outside the frozen bound")
    if real and (not args.authorize_model_inference or args.stop_at_unix is None
                 or not math.isfinite(args.stop_at_unix)):
        raise ValueError("real batch requires authorization and an absolute stop time")
    protected = _protected_paths(protocol, amendment, args.source_dir)
    if journal_path.resolve() in protected or (args.out is not None and args.out.resolve() in protected):
        raise ValueError("batch output would overwrite a frozen source")
    if args.out is not None and args.out.resolve() == journal_path.resolve():
        raise ValueError("session report and journal must be different files")
    if (not real and args.out.parent.resolve() == canonical_journal(amendment).parent.resolve()
            and args.out.name.startswith(amendment["journal"]["real_session_prefix"])):
        raise ValueError("mock output would occupy a canonical real-session name")
    provenance = None
    if real:
        if args.server_receipt is None:
            raise ValueError("real batch requires a server receipt")
        validate_serving_stack(protocol)
        provenance = serving_receipt(protocol, args.server_receipt, args.base_url)
        verify_live_server(provenance)
        llm = LocalLLM(protocol["inference"]["served_model_name"], args.base_url,
                       timeout=protocol["transport"]["timeout_seconds"], max_attempts=1)
    else:
        llm = MockLLM(['{"action":"end_turn","card_index":-1,"target_index":-1,"reasoning":"batch mock"}'])

    with exclusive_writer(journal_path):
        journal = _load_journal(journal_path, amendment, amendment_digest,
                                protocol_digest, schedule)
        session_rows, _ = _validate_journal_sessions(
            journal, journal_path, amendment, amendment_digest,
            protocol, protocol_digest, context, schedule)
        status, canonical_path, active, active_rows = _orphan_status(
            journal, journal_path, amendment, amendment_digest, protocol,
            protocol_digest, context, schedule)
        if status == "finalized_orphan":
            _append_finalized(journal, journal_path, amendment, active,
                              canonical_path, active_rows)
            canonical_path = _session_path(
                journal_path, amendment, len(journal["sessions"]) + 1)
            session_rows.extend(active_rows)
            status = None
        elif status is not None:
            raise ValueError("unresolved active session; use resolve before another batch")
        if journal["complete"]:
            return inspect_chain(amendment, amendment_digest, args.source_dir, journal_path,
                                 validated_parent=parent_state)
        if real and journal["next_global_index"] == amendment["batch"][
                "first_continuation_global_index"]:
            if args.max_new_queries != amendment["batch"]["first_continuation_batch_queries"]:
                raise ValueError("first continuation session is the frozen one-query stack smoke")
        elif real:
            smoke_row = next((row for row in session_rows if row["index"] == amendment[
                "batch"]["first_continuation_global_index"]), None)
            if smoke_row is None or not _continuation_smoke_ok(smoke_row):
                raise ValueError("continuation stack smoke did not pass; no replacement is allowed")
        if real and not deadline_allows(args.stop_at_unix, amendment):
            raise ValueError("insufficient deadline headroom to start a query")

        session_id = len(journal["sessions"]) + 1
        path = canonical_path if real else args.out
        if path.parent.resolve() != journal_path.parent.resolve():
            raise ValueError("session report must share the journal directory")
        if path.exists() or any(row_directory(path).glob("*.json")):
            raise ValueError("session artifact already exists outside the journal")
        start = journal["next_global_index"]
        planned_end = min(len(schedule), start + args.max_new_queries)
        journal["active_session_id"] = session_id
        journal["active_session_filename"] = path.name
        _atomic_write_json(journal_path, journal)
        report = {
            "result_schema_version": "2.1-batch-session",
            "run_kind": "controlled-h-confirmatory-batch-session",
            "amendment_id": amendment["amendment_id"],
            "amendment_digest": amendment_digest,
            "original_protocol_digest": protocol_digest,
            "parent_report_sha256": amendment["parent"]["report_sha256"],
            "schedule_sha256": digest_json(schedule),
            "session_id": session_id,
            "start_global_index": start,
            "requested_max_new_queries": args.max_new_queries,
            "initial_planned_end_global_index": planned_end,
            "planned_end_global_index": planned_end,
            "end_global_index": None,
            "provider": args.provider,
            "model_inference": real,
            "model": protocol["inference"],
            "transport": protocol["transport"],
            "source_code_sha256": code_receipt(),
            "server_provenance": provenance,
            "stop_at_unix": args.stop_at_unix if real else None,
            "runtime_versions": {p: _package_version(p) for p in ("vllm", "transformers", "numpy")},
            "created_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
            "completed_rows": [], "pending": None, "complete": False,
            "finalized": False, "stop_reason": None,
        }
        _atomic_write_json(path, report)
        subset = schedule[start:planned_end]
        stop_reason = "batch_cap"
        for query in subset:
            if real and not deadline_allows(args.stop_at_unix, amendment):
                stop_reason = "deadline_headroom"
                break
            local_index = len(report["completed_rows"])
            report["pending"] = query
            _atomic_write_json(path, report)
            llm.last_raw_response = None
            llm.last_finish_reason = None
            failure = None
            fid = query["fixture_id"]
            try:
                parsed = llm.complete_json(
                    *context[3][fid][query["horizon"]],
                    temperature=protocol["inference"]["temperature"],
                    max_tokens=protocol["inference"]["max_tokens"])
                raw, finish = llm.last_raw_response, llm.last_finish_reason
            except (RateLimitExhausted, TimeoutError, ConnectionError, OSError):
                parsed, raw, finish, failure = ({"error": "transport_failure"},
                                                None, None, "transport_failure")
            except RuntimeError as exc:
                if not isinstance(llm, LocalLLM) or not str(exc).startswith(
                        "Local server returned HTTP "):
                    raise
                parsed, raw, finish, failure = ({"error": "transport_failure"},
                                                None, None, "transport_failure")
            row = make_row(query, context[3][fid], context[1][fid], parsed,
                           raw, finish, failure)
            validate_row(row, query, context[3][fid], context[1][fid])
            _write_row(report, path, row)
            if failure:
                stop_reason = "transport_failure"
                break
        if start + len(report["completed_rows"]) == len(schedule):
            stop_reason = "complete"
        _finalize_session(report, path, stop_reason)
        rows = _validate_session(report, path, amendment, amendment_digest,
                                 protocol, protocol_digest, context, schedule, True)
        _append_finalized(journal, journal_path, amendment, report, path, rows)
        return inspect_chain(amendment, amendment_digest, args.source_dir, journal_path,
                             validated_parent=parent_state)


def resolve_active(args, amendment: dict, amendment_digest: str) -> dict:
    parent_state = _validate_parent(amendment, args.source_dir)
    protocol, protocol_digest, context, schedule, _parent_path, _parent, _parent_rows = (
        parent_state)
    journal_path = args.journal
    with exclusive_writer(journal_path):
        journal = _load_journal(journal_path, amendment, amendment_digest,
                                protocol_digest, schedule)
        _validate_journal_sessions(journal, journal_path, amendment, amendment_digest,
                                   protocol, protocol_digest, context, schedule)
        status, path, report, rows = _orphan_status(
            journal, journal_path, amendment, amendment_digest, protocol,
            protocol_digest, context, schedule)
        if status is None:
            raise ValueError("no active session to resolve")
        if status == "reserved":
            journal["active_session_id"] = None
            journal["active_session_filename"] = None
            _atomic_write_json(journal_path, journal)
        elif status == "finalized_orphan":
            _append_finalized(journal, journal_path, amendment, report, path, rows)
        else:
            subset = _session_schedule(report, schedule)
            _reconcile_pending(report, path, subset, context, as_failure=True)
            _finalize_session(report, path, "explicit_no_inference_resolution")
            rows = _validate_session(report, path, amendment, amendment_digest,
                                     protocol, protocol_digest, context, schedule, True)
            _append_finalized(journal, journal_path, amendment, report, path, rows)
    return inspect_chain(amendment, amendment_digest, args.source_dir, journal_path,
                         validated_parent=parent_state)


def analyze_chain(args, amendment: dict, amendment_digest: str) -> dict:
    protocol, protocol_digest, context, schedule, _parent_path, _parent, parent_rows = (
        _validate_parent(amendment, args.source_dir))
    journal = _load_journal(args.journal, amendment, amendment_digest,
                            protocol_digest, schedule)
    session_rows, next_index = _validate_journal_sessions(
        journal, args.journal, amendment, amendment_digest, protocol,
        protocol_digest, context, schedule)
    status, _path, _report, _rows = _orphan_status(
        journal, args.journal, amendment, amendment_digest, protocol,
        protocol_digest, context, schedule)
    if status is not None:
        raise ValueError("analysis refuses an unjournaled session artifact")
    rows = parent_rows + session_rows
    if any(row["index"] != index for index, row in enumerate(rows)):
        raise ValueError("combined confirmation coverage is missing or overlapping")
    all_local = all(entry.get("provider") == "local" for entry in (
        json.loads(args.journal.with_name(ref["filename"]).read_text(encoding="utf-8"))
        for ref in journal["sessions"]))
    smoke_ok = _continuation_smoke_ok(next((row for row in rows if row['index'] == 1), {}))
    real_evidence = next_index == len(schedule) and all_local and smoke_ok
    analysis = analyze_rows(rows, protocol, real_evidence)
    output = {
        "run_kind": "controlled-h-confirmatory-batch-analysis",
        "amendment_id": amendment["amendment_id"],
        "amendment_digest": amendment_digest,
        "original_protocol_digest": protocol_digest,
        "journal_sha256": _sha256(args.journal),
        "planning": planning_power(protocol, args.source_dir),
        "coverage": {"completed": len(rows), "expected": len(schedule)},
        "analysis": analysis,
        "post_smoke_execution_amendment": True,
        "model_inference": False,
    }
    output["analysis"]["quality_by_character_horizon_stratum"] = {
        f"{character}/{horizon}/{label}": {
            "n": len(values),
            "mean": sum(values) / len(values) if values else None,
        }
        for character in protocol["release"]["characters"]
        for horizon in protocol["inference"]["horizons"]
        for sensitive, label in ((True, "sensitive"), (False, "control"))
        for values in [[row["effective_quality"] for row in rows
                        if row["character"] == character and row["horizon"] == horizon
                        and row["h1_h8_sensitive"] == sensitive]]
    }
    output["analysis"]["raw_regret_by_character_horizon"] = {
        f"{character}/{horizon}": {
            "valid_n": len(values),
            "mean": sum(values) / len(values) if values else None,
            "interpretation": "conditional on legal action; invalid raw regrets remain absent",
        }
        for character in protocol["release"]["characters"]
        for horizon in protocol["inference"]["horizons"]
        for values in [[row["score"]["regret"] for row in rows
                        if row["character"] == character and row["horizon"] == horizon
                        and row["score"]["regret"] is not None]]
    }
    output["analysis"]["oracle_diagnostics"] = {
        f"{character}/{horizon}": {
            "fixture_n": len(oracles),
            "zero_spans": sum(o["best_value"] == o["worst_value"] for o in oracles),
            "mean_span": sum(o["best_value"] - o["worst_value"] for o in oracles) / len(oracles),
            "mean_baseline_quality": {
                name: sum(o["baselines"][name]["quality"] for o in oracles) / len(oracles)
                for name in ("always_end_turn", "uniform_legal_expected",
                             "h1_mismatched_oracle", "h_aware_exact_oracle")},
        }
        for character in protocol["release"]["characters"]
        for horizon in protocol["inference"]["horizons"]
        for oracles in [[context[1][fixture_id]["oracles"][str(horizon)]
                         for fixture_id, fixture in context[0].items()
                         if fixture.character == character]]
    }
    protected = list(_protected_paths(protocol, amendment, args.source_dir))
    protected.extend([args.journal, args.source_dir / amendment["parent"]["report_filename"]])
    protected.extend(args.journal.with_name(ref["filename"]) for ref in journal["sessions"])
    if args.out.resolve() in {path.resolve() for path in protected}:
        raise ValueError("analysis output would overwrite evidence")
    protect_diagnostic_output(args, protocol, amendment)
    _atomic_write_json(args.out, output)
    return output


def _print_status(status: dict) -> None:
    print(json.dumps(status, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, default=ROOT / "results")
    parser.add_argument("--journal", type=Path,
                        default=ROOT / "results" / "controlled_h_v2_confirmatory_batch.json")
    sub = parser.add_subparsers(dest="command", required=True)
    preflight = sub.add_parser("preflight")
    preflight.add_argument("--out", type=Path)
    run = sub.add_parser("run")
    run.add_argument("--provider", choices=("mock", "local"), required=True)
    run.add_argument("--out", type=Path, help="required for mock; forbidden for local")
    run.add_argument("--base-url", default="http://localhost:8000/v1")
    run.add_argument("--server-receipt", type=Path)
    run.add_argument("--authorize-model-inference", action="store_true")
    run.add_argument("--max-new-queries", type=int, required=True)
    run.add_argument("--stop-at-unix", type=float)
    sub.add_parser("resolve")
    analyze = sub.add_parser("analyze")
    analyze.add_argument("--out", type=Path, required=True)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    amendment, amendment_digest = load_amendment()
    if args.command == "preflight":
        status = inspect_chain(amendment, amendment_digest, args.source_dir, args.journal)
        if args.out:
            protect_diagnostic_output(args, load_protocol()[0], amendment)
            _atomic_write_json(args.out, status)
        _print_status(status)
        if not status["runnable"] and not status["complete"]:
            raise SystemExit(2)
    elif args.command == "run":
        _print_status(run_batch(args, amendment, amendment_digest))
    elif args.command == "resolve":
        _print_status(resolve_active(args, amendment, amendment_digest))
    else:
        output = analyze_chain(args, amendment, amendment_digest)
        _print_status({"completed": output["coverage"]["completed"],
                       "expected": output["coverage"]["expected"],
                       "valid_for_primary_inference": output["analysis"][
                           "valid_for_primary_inference"]})


if __name__ == "__main__":
    main()
