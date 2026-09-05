#!/usr/bin/env python
"""Build the separately labelled v2 + Silent-extension fixture release."""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import hashlib
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.controlled_horizon_funnel import (  # noqa: E402
    _base_report,
    _file_sha256,
    _read_report,
)
from scripts.controlled_horizon_pilot import (  # noqa: E402
    _atomic_write_json,
    generate_frozen_candidates,
    load_frozen_protocol,
    select_frozen_release,
)
from scripts.controlled_horizon_silent_extension import (  # noqa: E402
    load_extension_protocol,
)
from slay_bench.controlled_horizon import CONTROLLED_HORIZON_VERSION  # noqa: E402


COMBINED_PROTOCOL_PATH = (
    ROOT / "configs" / "controlled_h_v2_combined_release.json")


def load_combined_protocol(path: Path = COMBINED_PROTOCOL_PATH) -> tuple[dict, str]:
    protocol = json.loads(path.read_text(encoding="utf-8"))
    if protocol.get("instrument_version") != CONTROLLED_HORIZON_VERSION:
        raise ValueError("combined release instrument version does not match code")
    rendered = json.dumps(protocol, sort_keys=True, separators=(",", ":"))
    return protocol, hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def _extension_flow(extension_rows: list[dict]) -> dict:
    counts = collections.Counter()
    for row in extension_rows:
        if row.get("error"):
            counts["budget_failure"] += 1
        elif row.get("horizon_sensitive_h1_h8"):
            counts["sensitive"] += 1
        else:
            counts["insensitive"] += 1
    return dict(counts)


def select_combined_release(base_rows: list[dict], extension_rows: list[dict],
                            base_protocol: dict, combined: dict) -> dict:
    """Apply the original release rule after adding eligible extension controls."""
    spec = combined["selection"]
    release_spec = base_protocol["release"]
    expected = {
        "fixtures_per_character": release_spec["fixtures_per_character"],
        "h1_h8_sensitive_per_character":
            release_spec["h1_h8_sensitive_per_character"],
        "h1_h8_insensitive_per_character":
            release_spec["h1_h8_insensitive_per_character"],
    }
    if any(spec[key] != value for key, value in expected.items()):
        raise ValueError("combined quotas differ from the original release contract")
    if spec["characters"] != base_protocol["candidate_generation"]["characters"]:
        raise ValueError("combined character order differs from the base protocol")
    if spec["rank_namespace_protocol_id"] != base_protocol["protocol_id"]:
        raise ValueError("combined rank namespace differs from the base protocol")
    if spec["extension_may_supply_h1_h8_sensitive"]:
        raise ValueError("the Silent extension may supply controls only")

    base_ids = {row["fixture"]["fixture_id"] for row in base_rows}
    extension_ids = [row["fixture"]["fixture_id"] for row in extension_rows]
    if len(extension_ids) != len(set(extension_ids)):
        raise ValueError("duplicate fixture IDs within the extension")
    if base_ids.intersection(extension_ids):
        raise ValueError("base and extension full-audit rows overlap")
    if any(row["fixture"]["character"]
           != spec["extension_may_supply_character"] for row in extension_rows):
        raise ValueError("extension contains a non-Silent fixture")

    extension_eval = select_frozen_release(extension_rows, base_protocol)
    allowed_extension_ids = {
        item["fixture_id"] for item in extension_eval["dispositions"]
        if item["eligible"] and not item["h1_h8_sensitive"]
    }
    allowed_extension_rows = [
        row for row in extension_rows
        if row["fixture"]["fixture_id"] in allowed_extension_ids
    ]
    selection = select_frozen_release(
        [*base_rows, *allowed_extension_rows], base_protocol)
    selected = set(selection["selected_fixture_ids"])
    selection["allowed_extension_control_fixture_ids"] = sorted(
        allowed_extension_ids)
    selection["extension_flow"] = _extension_flow(extension_rows)
    selection["selected_source_counts"] = {
        "base": len(selected.intersection(base_ids)),
        "silent_control_extension": len(
            selected.intersection(allowed_extension_ids)),
    }
    return selection


def build_combined_release(combined: dict, combined_digest: str,
                           base_protocol_path: Path, extension_protocol_path: Path,
                           base_full_path: Path, extension_full_path: Path,
                           fixtures_output: Path, audit_output: Path) -> dict:
    base_protocol, base_digest = load_frozen_protocol(base_protocol_path)
    extension_protocol, extension_digest = load_extension_protocol(
        extension_protocol_path)
    base_source = combined["base_protocol"]
    extension_source = combined["silent_control_extension"]
    if (base_protocol["protocol_id"] != base_source["protocol_id"]
            or base_digest != base_source["protocol_digest"]):
        raise ValueError("base protocol differs from the combined release freeze")
    if (extension_protocol["protocol_id"] != extension_source["protocol_id"]
            or extension_digest != extension_source["protocol_digest"]):
        raise ValueError("extension protocol differs from combined release freeze")

    base_full = _read_report(base_full_path, base_digest, "full")
    extension_full = _read_report(
        extension_full_path, extension_digest, "extension-full")
    if not base_full.get("complete") or not extension_full.get("complete"):
        raise ValueError("both source full-audit artifacts must be complete")
    if _file_sha256(base_full_path) != base_source["full_artifact_sha256"]:
        raise ValueError("base full-audit hash differs from the combined freeze")
    if (_file_sha256(extension_full_path)
            != extension_source["full_artifact_sha256"]):
        raise ValueError("extension full-audit hash differs from the combined freeze")
    base_release = select_frozen_release(base_full["rows"], base_protocol)
    if base_release["release_gate_passed"] != base_source["release_gate_passed"]:
        raise ValueError("base release outcome differs from the combined freeze")
    flow = _extension_flow(extension_full["rows"])
    expected_flow = {
        "insensitive": extension_source["exact_h1_h8_insensitive_rows"],
        "sensitive": extension_source["exact_h1_h8_sensitive_rows"],
        "budget_failure": extension_source["budget_failure_rows"],
    }
    if (extension_full["completed_fixture_rows"]
            != extension_source["completed_fixture_rows"] or flow != expected_flow):
        raise ValueError("extension outcome differs from the combined release freeze")

    selection = select_combined_release(
        base_full["rows"], extension_full["rows"], base_protocol, combined)
    selected_ids = set(selection["selected_fixture_ids"])
    fixtures, _attempts = generate_frozen_candidates(base_protocol)
    release_fixtures = [fixture for fixture in fixtures
                        if fixture.fixture_id in selected_ids]
    created_at = dt.datetime.now(dt.timezone.utc).isoformat()
    report = {
        **_base_report(combined, combined_digest, "combined-release",
                       created_at),
        "release_gate_passed": selection["release_gate_passed"],
        "original_v2_release_gate_passed": base_release["release_gate_passed"],
        "base_full_artifact_sha256": _file_sha256(base_full_path),
        "extension_full_artifact_sha256": _file_sha256(extension_full_path),
        "selection": selection,
        "released_fixture_count": len(release_fixtures),
    }
    fixture_payload = {
        **_base_report(combined, combined_digest, "combined-release-fixtures",
                       report["created_at_utc"]),
        "release_gate_passed": selection["release_gate_passed"],
        "fixtures": [asdict(fixture) for fixture in release_fixtures]
                     if selection["release_gate_passed"] else [],
    }
    _atomic_write_json(audit_output, report)
    _atomic_write_json(fixtures_output, fixture_payload)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, default=COMBINED_PROTOCOL_PATH)
    parser.add_argument("--base-protocol", type=Path, required=True)
    parser.add_argument("--extension-protocol", type=Path, required=True)
    parser.add_argument("--base-full-audit", type=Path, required=True)
    parser.add_argument("--extension-full-audit", type=Path, required=True)
    parser.add_argument("--fixtures-out", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    combined, digest = load_combined_protocol(args.protocol)
    report = build_combined_release(
        combined, digest, args.base_protocol, args.extension_protocol,
        args.base_full_audit, args.extension_full_audit,
        args.fixtures_out, args.out)
    print(json.dumps({
        "stage": report["stage"],
        "protocol_id": report["protocol_id"],
        "protocol_digest": report["protocol_digest"],
        "original_v2_release_gate_passed":
            report["original_v2_release_gate_passed"],
        "release_gate_passed": report["release_gate_passed"],
        "released_fixture_count": report["released_fixture_count"],
        "selected_source_counts":
            report["selection"]["selected_source_counts"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
