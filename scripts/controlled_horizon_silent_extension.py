#!/usr/bin/env python
"""Run the frozen Silent-control extension without model inference.

The base v2 release remains failed. This extension deterministically audits the
next-ranked, previously unadvanced Silent screen-insensitive candidates and may
only supplement the control stratum in a separately labelled combined release.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.controlled_horizon_funnel import (  # noqa: E402
    _audit_stage,
    _file_sha256,
    _read_report,
)
from scripts.controlled_horizon_pilot import (  # noqa: E402
    FROZEN_PROTOCOL_PATH,
    generate_frozen_candidates,
    load_frozen_protocol,
    select_frozen_advancements,
    select_frozen_release,
)
from slay_bench.controlled_horizon import CONTROLLED_HORIZON_VERSION  # noqa: E402


EXTENSION_PROTOCOL_PATH = (
    ROOT / "configs" / "controlled_h_v2_silent_control_extension.json")


def load_extension_protocol(path: Path = EXTENSION_PROTOCOL_PATH) -> tuple[dict, str]:
    """Load and digest-lock the extension payload."""
    protocol = json.loads(path.read_text(encoding="utf-8"))
    if protocol.get("instrument_version") != CONTROLLED_HORIZON_VERSION:
        raise ValueError("extension instrument version does not match code")
    rendered = json.dumps(protocol, sort_keys=True, separators=(",", ":"))
    return protocol, hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def select_extension_candidates(screen_rows: list[dict], base_protocol: dict,
                                extension: dict) -> dict:
    """Select the declared next-rank slice from the unadvanced control pool."""
    spec = extension["selection"]
    if spec["rank_namespace_protocol_id"] != base_protocol["protocol_id"]:
        raise ValueError("extension rank namespace must be the base protocol ID")
    if not spec["exclude_base_advanced_fixtures"]:
        raise ValueError("extension must exclude every base-advanced fixture")
    if (spec["offset_after_base_advanced"]
            != base_protocol["screen"][
                "screen_insensitive_advances_per_character"]):
        raise ValueError("extension rank offset differs from the base advancement count")
    advancement = select_frozen_advancements(screen_rows, base_protocol)
    pool = [
        decision for decision in advancement["decisions"]
        if decision["character"] == spec["character"]
        and decision["reason"] == "screen_insensitive_rank_pool"
        and not decision["advanced"]
    ]
    pool.sort(key=lambda decision: decision["rank"])
    count = spec["fixture_count"]
    if len(pool) < count:
        raise ValueError(
            f"extension requests {count} fixtures but only {len(pool)} remain")
    selected = pool[:count]
    return {
        "selected_fixture_ids": sorted(
            decision["fixture_id"] for decision in selected),
        "rank_ordered_fixture_ids": [
            decision["fixture_id"] for decision in selected],
        "available_unadvanced_pool_size": len(pool),
        "selection_count": len(selected),
        "decisions": [
            {**decision, "extension_selected": decision in selected}
            for decision in pool
        ],
    }


def _validate_base_outcome(extension: dict, full_report: dict,
                           base_protocol: dict) -> dict:
    observed = extension["observed_base_outcome"]
    release = select_frozen_release(full_report["rows"], base_protocol)
    matching = [
        item for item in release["shortfalls"]
        if item["character"] == observed["character"]
        and item["h1_h8_sensitive"] is False
    ]
    if release["release_gate_passed"] or len(matching) != 1:
        raise ValueError("base result does not have the declared Silent-control failure")
    shortfall = matching[0]
    expected = {
        "required": observed["h1_h8_insensitive_required"],
        "available": observed["h1_h8_insensitive_available"],
    }
    if any(shortfall[key] != value for key, value in expected.items()):
        raise ValueError("base Silent-control shortfall differs from extension freeze")
    if shortfall["required"] - shortfall["available"] != observed["shortfall"]:
        raise ValueError("declared extension shortfall is inconsistent")
    return release


def run_extension(extension: dict, extension_digest: str, base_protocol_path: Path,
                  screen_path: Path, full_path: Path, output: Path) -> dict:
    base_protocol, base_digest = load_frozen_protocol(base_protocol_path)
    source = extension["base_protocol"]
    if (base_protocol["protocol_id"] != source["protocol_id"]
            or base_digest != source["protocol_digest"]):
        raise ValueError("base protocol does not match the extension freeze")
    screen = _read_report(screen_path, base_digest, "screen")
    full = _read_report(full_path, base_digest, "full")
    if not screen.get("complete") or not full.get("complete"):
        raise ValueError("base screen and full artifacts must both be complete")
    if _file_sha256(screen_path) != source["screen_artifact_sha256"]:
        raise ValueError("base screen artifact hash differs from extension freeze")
    if _file_sha256(full_path) != source["full_artifact_sha256"]:
        raise ValueError("base full artifact hash differs from extension freeze")
    base_release = _validate_base_outcome(extension, full, base_protocol)
    selection = select_extension_candidates(screen["rows"], base_protocol, extension)
    fixtures, _attempts = generate_frozen_candidates(base_protocol)
    selected_ids = set(selection["selected_fixture_ids"])
    fixtures = [fixture for fixture in fixtures
                if fixture.fixture_id in selected_ids]
    oracle = extension["full_oracle"]
    return _audit_stage(
        extension, extension_digest, "extension-full", fixtures,
        tuple(oracle["horizons"]), oracle["node_budget_per_fixture_h"],
        oracle["wall_seconds_per_fixture_h"], output,
        extra={
            "base_protocol_digest": base_digest,
            "base_screen_artifact_sha256": _file_sha256(screen_path),
            "base_full_artifact_sha256": _file_sha256(full_path),
            "base_release_shortfalls": base_release["shortfalls"],
            "extension_selection": selection,
        })


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, default=EXTENSION_PROTOCOL_PATH)
    parser.add_argument("--base-protocol", type=Path, default=FROZEN_PROTOCOL_PATH)
    parser.add_argument("--screen-audit", type=Path, required=True)
    parser.add_argument("--full-audit", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    extension, digest = load_extension_protocol(args.protocol)
    report = run_extension(
        extension, digest, args.base_protocol, args.screen_audit,
        args.full_audit, args.out)
    print(json.dumps({
        "stage": report["stage"],
        "protocol_id": report["protocol_id"],
        "protocol_digest": report["protocol_digest"],
        "completed_fixture_rows": report["completed_fixture_rows"],
        "requested_fixture_rows": report["requested_fixture_rows"],
        "complete": report["complete"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
