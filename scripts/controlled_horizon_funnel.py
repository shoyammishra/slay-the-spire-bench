#!/usr/bin/env python
"""Execute the frozen controlled-H fixture funnel without model inference.

Stages are deliberately separate so the inexpensive H={1,4} screen is preserved
before any H=8 work. Every stage validates the preregistration digest and atomically
checkpoints each completed row. Budget failures are completed dispositions, not
retries or silently dropped candidates.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.controlled_horizon_pilot import (  # noqa: E402
    FROZEN_PROTOCOL_PATH,
    _atomic_write_json,
    _git_value,
    audit_fixture,
    generate_frozen_candidates,
    load_frozen_protocol,
    select_frozen_advancements,
    select_frozen_release,
)


def _read_report(path: Path, protocol_digest: str, expected_stage: str) -> dict:
    report = json.loads(path.read_text(encoding="utf-8"))
    if report.get("protocol_digest") != protocol_digest:
        raise ValueError(f"{path} does not match the frozen protocol digest")
    if report.get("stage") != expected_stage:
        raise ValueError(f"{path} is not a {expected_stage!r} stage artifact")
    return report


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _base_report(protocol: dict, digest: str, stage: str,
                 created_at_utc: str) -> dict:
    return {
        "result_schema_version": "2.0",
        "run_kind": "compute-free-controlled-h-fixture-funnel",
        "instrument_version": protocol["instrument_version"],
        "protocol_id": protocol["protocol_id"],
        "protocol_digest": digest,
        "stage": stage,
        "created_at_utc": created_at_utc,
        "provenance": {
            "git_commit": _git_value("rev-parse", "HEAD"),
            "git_dirty": bool(_git_value("status", "--porcelain")),
            "model_inference": False,
            "paid_api": False,
            "cluster_compute": False,
        },
    }


def write_manifest(protocol: dict, digest: str, output: Path) -> dict:
    fixtures, attempts = generate_frozen_candidates(protocol)
    report = {
        **_base_report(
            protocol, digest, "manifest", dt.datetime.now(dt.timezone.utc).isoformat()),
        "candidate_attempt_count": len(attempts),
        "generated_fixture_count": len(fixtures),
        "generation_failure_count": sum(not row["generated"] for row in attempts),
        "attempts": attempts,
        "fixtures": [asdict(fixture) for fixture in fixtures],
    }
    _atomic_write_json(output, report)
    return report


def _audit_stage(protocol: dict, digest: str, stage: str, fixtures: list,
                 horizons: tuple[int, ...], node_budget: int,
                 wall_seconds: float, output: Path, extra: dict | None = None) -> dict:
    prior = None
    if output.exists():
        prior = _read_report(output, digest, stage)
        for key, value in (extra or {}).items():
            if key in prior and prior[key] != value:
                raise ValueError(
                    f"{output} was checkpointed with different {key!r} metadata")
    created_at = (prior or {}).get(
        "created_at_utc", dt.datetime.now(dt.timezone.utc).isoformat())
    rows = list((prior or {}).get("rows", []))
    completed = {row["fixture"]["fixture_id"] for row in rows}
    fixture_ids = {fixture.fixture_id for fixture in fixtures}
    if not completed.issubset(fixture_ids):
        raise ValueError(f"{output} contains rows outside the selected fixture set")

    def report() -> dict:
        return {
            **_base_report(protocol, digest, stage, created_at),
            **(extra or {}),
            "horizons": list(horizons),
            "node_budget_per_fixture_h": node_budget,
            "wall_seconds_per_fixture_h": wall_seconds,
            "requested_fixture_rows": len(fixtures),
            "completed_fixture_rows": len(rows),
            "complete": len(rows) == len(fixtures),
            "rows": rows,
        }

    remaining = [fixture for fixture in fixtures if fixture.fixture_id not in completed]
    for index, fixture in enumerate(remaining, 1):
        print(
            f"[{index}/{len(remaining)} remaining] {stage} {fixture.fixture_id}",
            file=sys.stderr, flush=True)
        rows.append(audit_fixture(fixture, horizons, node_budget, wall_seconds))
        _atomic_write_json(output, report())
    final = report()
    _atomic_write_json(output, final)
    return final


def run_screen(protocol: dict, digest: str, output: Path) -> dict:
    fixtures, attempts = generate_frozen_candidates(protocol)
    screen = protocol["screen"]
    return _audit_stage(
        protocol, digest, "screen", fixtures, tuple(screen["horizons"]),
        screen["node_budget_per_fixture_h"],
        screen["wall_seconds_per_fixture_h"], output,
        extra={
            "candidate_attempt_count": len(attempts),
            "generation_failure_count": sum(not row["generated"] for row in attempts),
            "generation_attempts": attempts,
        })


def run_full(protocol: dict, digest: str, screen_path: Path,
             output: Path) -> dict:
    screen_report = _read_report(screen_path, digest, "screen")
    if not screen_report.get("complete"):
        raise ValueError("screen stage is incomplete")
    advancement = select_frozen_advancements(screen_report["rows"], protocol)
    advancement["screen_artifact_sha256"] = _file_sha256(screen_path)
    fixtures, _attempts = generate_frozen_candidates(protocol)
    selected = set(advancement["selected_fixture_ids"])
    fixtures = [fixture for fixture in fixtures if fixture.fixture_id in selected]
    full = protocol["full_oracle"]
    return _audit_stage(
        protocol, digest, "full", fixtures, tuple(full["horizons"]),
        full["node_budget_per_fixture_h"],
        full["wall_seconds_per_fixture_h"], output,
        extra={"advancement": advancement})


def finalize_release(protocol: dict, digest: str, full_path: Path,
                     fixtures_output: Path, audit_output: Path) -> dict:
    full_report = _read_report(full_path, digest, "full")
    if not full_report.get("complete"):
        raise ValueError("full-oracle stage is incomplete")
    selection = select_frozen_release(full_report["rows"], protocol)
    fixtures, _attempts = generate_frozen_candidates(protocol)
    selected = set(selection["selected_fixture_ids"])
    release_fixtures = [fixture for fixture in fixtures
                        if fixture.fixture_id in selected]
    report = {
        **_base_report(
            protocol, digest, "release", dt.datetime.now(dt.timezone.utc).isoformat()),
        "release_gate_passed": selection["release_gate_passed"],
        "full_artifact_sha256": _file_sha256(full_path),
        "selection": selection,
        "released_fixture_count": len(release_fixtures),
    }
    fixture_payload = {
        **_base_report(protocol, digest, "release-fixtures",
                       report["created_at_utc"]),
        "release_gate_passed": selection["release_gate_passed"],
        "fixtures": [asdict(fixture) for fixture in release_fixtures],
    }
    _atomic_write_json(audit_output, report)
    _atomic_write_json(fixtures_output, fixture_payload)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=("manifest", "screen", "full", "release"))
    parser.add_argument("--protocol", type=Path, default=FROZEN_PROTOCOL_PATH)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--screen-audit", type=Path)
    parser.add_argument("--full-audit", type=Path)
    parser.add_argument("--fixtures-out", type=Path)
    args = parser.parse_args()
    protocol, digest = load_frozen_protocol(args.protocol)

    if args.stage == "manifest":
        report = write_manifest(protocol, digest, args.out)
    elif args.stage == "screen":
        report = run_screen(protocol, digest, args.out)
    elif args.stage == "full":
        if args.screen_audit is None:
            parser.error("full stage requires --screen-audit")
        report = run_full(protocol, digest, args.screen_audit, args.out)
    else:
        if args.full_audit is None or args.fixtures_out is None:
            parser.error("release stage requires --full-audit and --fixtures-out")
        report = finalize_release(
            protocol, digest, args.full_audit, args.fixtures_out, args.out)
    print(json.dumps({
        "stage": report["stage"],
        "protocol_id": report["protocol_id"],
        "protocol_digest": report["protocol_digest"],
        "complete": report.get("complete"),
        "release_gate_passed": report.get("release_gate_passed"),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
