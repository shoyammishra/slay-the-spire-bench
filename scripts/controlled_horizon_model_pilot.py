#!/usr/bin/env python
"""Run the frozen controlled-H model pilot or its no-inference mock smoke."""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import hashlib
import importlib.metadata
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.controlled_horizon_combined_release import (  # noqa: E402
    COMBINED_PROTOCOL_PATH,
    load_combined_protocol,
)
from scripts.controlled_horizon_funnel import _file_sha256, _read_report  # noqa: E402
from scripts.controlled_horizon_pilot import (  # noqa: E402
    FROZEN_PROTOCOL_PATH,
    _atomic_write_json,
    _git_value,
    load_frozen_protocol,
)
from scripts.controlled_horizon_silent_extension import (  # noqa: E402
    EXTENSION_PROTOCOL_PATH,
    load_extension_protocol,
)
from slay_bench.benchmark import MockLLM  # noqa: E402
from slay_bench.controlled_horizon import (  # noqa: E402
    CONTROLLED_HORIZON_VERSION,
    ControlledAction,
    ControlledFixture,
    build_prompt,
    load_fixture,
)


PILOT_PROTOCOL_PATH = ROOT / "configs" / "controlled_h_v2_model_pilot.json"


def _package_version(package: str) -> str | None:
    try:
        return importlib.metadata.version(package)
    except importlib.metadata.PackageNotFoundError:
        return None


def validate_serving_stack(protocol: dict,
                           versions: dict[str, str | None] | None = None) -> None:
    versions = versions or {
        package: _package_version(package)
        for package in ("vllm", "transformers")
    }
    expected = protocol["inference"]["serving_stack"]
    for package, key in (("vllm", "vllm_version"),
                         ("transformers", "transformers_version")):
        if versions.get(package) != expected[key]:
            raise ValueError(
                f"{package} runtime {versions.get(package)!r} differs from "
                f"frozen version {expected[key]!r}")


def load_pilot_protocol(path: Path = PILOT_PROTOCOL_PATH) -> tuple[dict, str]:
    protocol = json.loads(path.read_text(encoding="utf-8"))
    if protocol.get("instrument_version") != CONTROLLED_HORIZON_VERSION:
        raise ValueError("pilot instrument version does not match code")
    rendered = json.dumps(protocol, sort_keys=True, separators=(",", ":"))
    return protocol, hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def _rank(protocol_id: str, fixture_id: str) -> str:
    return hashlib.sha256(f"{protocol_id}:{fixture_id}".encode("utf-8")).hexdigest()


def select_pilot_fixtures(release_audit: dict, protocol: dict) -> dict:
    """Select the preregistered character/sensitivity pilot strata."""
    if not release_audit.get("release_gate_passed"):
        raise ValueError("pilot source release did not pass")
    spec = protocol["pilot_sample"]
    buckets = collections.defaultdict(list)
    for disposition in release_audit["selection"]["dispositions"]:
        if not disposition.get("released"):
            continue
        key = (disposition["character"], disposition["h1_h8_sensitive"])
        buckets[key].append({
            "fixture_id": disposition["fixture_id"],
            "character": disposition["character"],
            "h1_h8_sensitive": disposition["h1_h8_sensitive"],
            "rank": _rank(protocol["protocol_id"], disposition["fixture_id"]),
        })
    selected = []
    for character in spec["characters"]:
        for sensitive, quota_key in (
                (True, "h1_h8_sensitive_per_character"),
                (False, "h1_h8_insensitive_per_character")):
            pool = sorted(buckets[(character, sensitive)], key=lambda item: item["rank"])
            quota = spec[quota_key]
            if len(pool) < quota:
                raise ValueError(
                    f"pilot stratum {character}/{sensitive} has {len(pool)} < {quota}")
            selected.extend(pool[:quota])
    expected = spec["fixtures_per_character"] * len(spec["characters"])
    if len(selected) != expected:
        raise ValueError("pilot fixture count differs from the frozen design")
    latin_orders = (
        [1, 2, 8, 4],
        [2, 4, 1, 8],
        [4, 8, 2, 1],
        [8, 1, 4, 2],
    )
    for character in spec["characters"]:
        character_rows = sorted(
            (item for item in selected if item["character"] == character),
            key=lambda item: hashlib.sha256(
                f"{protocol['protocol_id']}:query-order:{item['fixture_id']}".encode(
                    "utf-8")).hexdigest())
        for index, item in enumerate(character_rows):
            item["horizon_query_order"] = latin_orders[index % len(latin_orders)]
    selected_ids = sorted(item["fixture_id"] for item in selected)
    rendered = "\n".join(selected_ids) + "\n"
    digest = hashlib.sha256(rendered.encode("utf-8")).hexdigest()
    if digest != spec["selected_fixture_ids_sha256"]:
        raise ValueError("pilot selected-fixture digest differs from the freeze")
    return {
        "selected_fixture_ids": selected_ids,
        "selected_fixture_ids_sha256": digest,
        "decisions": sorted(selected, key=lambda item: item["fixture_id"]),
    }


def _load_sources(protocol: dict, combined_protocol_path: Path,
                  release_audit_path: Path, release_fixtures_path: Path,
                  base_full_path: Path, extension_full_path: Path,
                  base_protocol_path: Path,
                  extension_protocol_path: Path) -> tuple[dict, dict, dict]:
    combined, combined_digest = load_combined_protocol(combined_protocol_path)
    source = protocol["source_release"]
    if (combined["protocol_id"] != source["protocol_id"]
            or combined_digest != source["protocol_digest"]):
        raise ValueError("combined protocol differs from the pilot freeze")
    if _file_sha256(release_audit_path) != source["audit_artifact_sha256"]:
        raise ValueError("combined release audit hash differs from the pilot freeze")
    if _file_sha256(release_fixtures_path) != source["fixture_artifact_sha256"]:
        raise ValueError("combined release fixture hash differs from the pilot freeze")
    release_audit = json.loads(release_audit_path.read_text(encoding="utf-8"))
    release_fixtures = json.loads(release_fixtures_path.read_text(encoding="utf-8"))
    if (not release_audit.get("release_gate_passed")
            or not release_fixtures.get("release_gate_passed")
            or len(release_fixtures["fixtures"]) != source["release_fixture_count"]):
        raise ValueError("combined release artifacts are incomplete")

    base_protocol, base_digest = load_frozen_protocol(base_protocol_path)
    extension_protocol, extension_digest = load_extension_protocol(
        extension_protocol_path)
    base_source = combined["base_protocol"]
    extension_source = combined["silent_control_extension"]
    if (base_protocol["protocol_id"] != base_source["protocol_id"]
            or base_digest != base_source["protocol_digest"]):
        raise ValueError("base protocol differs from combined release metadata")
    if (extension_protocol["protocol_id"] != extension_source["protocol_id"]
            or extension_digest != extension_source["protocol_digest"]):
        raise ValueError("extension protocol differs from combined release metadata")
    if _file_sha256(base_full_path) != base_source["full_artifact_sha256"]:
        raise ValueError("base oracle artifact differs from combined release metadata")
    if _file_sha256(extension_full_path) != extension_source["full_artifact_sha256"]:
        raise ValueError("extension oracle artifact differs from combined metadata")
    base_full = _read_report(base_full_path, base_digest, "full")
    extension_full = _read_report(
        extension_full_path, extension_digest, "extension-full")
    oracle_rows = {
        row["fixture"]["fixture_id"]: row
        for row in [*base_full["rows"], *extension_full["rows"]]
    }
    fixtures = {
        item["fixture_id"]: ControlledFixture.from_dict(item)
        for item in release_fixtures["fixtures"]
    }
    return release_audit, fixtures, oracle_rows


def _strict_int(value, default: int) -> int:
    if value is None:
        return default
    if isinstance(value, bool):
        raise ValueError("boolean is not an integer index")
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().lstrip("-").isdigit():
        return int(value)
    raise ValueError("index is not an integer")


def score_precomputed_oracle(oracle_row: dict, horizon: int,
                             response: dict) -> dict:
    """Score one parsed action against the frozen exact-oracle values."""
    oracle = oracle_row["oracles"][str(horizon)]
    parse_ok = isinstance(response, dict) and "error" not in response
    schema_ok = False
    try:
        action_name = response.get("action") if parse_ok else None
        if action_name not in ("play", "end_turn"):
            raise ValueError("invalid action name")
        chosen = ControlledAction(
            action_name,
            _strict_int(response.get("card_index"), -1),
            _strict_int(response.get("target_index"), -1),
        )
        schema_ok = True
    except (AttributeError, TypeError, ValueError):
        chosen = ControlledAction("invalid")
    key = f"{chosen.action}:{chosen.card_index}:{chosen.target_index}"
    chosen_value = oracle["action_values"].get(key)
    legal = schema_ok and chosen_value is not None
    regret = oracle["best_value"] - chosen_value if legal else None
    span = oracle["best_value"] - oracle["worst_value"]
    quality = None
    if legal:
        quality = 1.0 if span == 0 else (
            chosen_value - oracle["worst_value"]) / span
    return {
        "chosen_action": {
            "action": chosen.action,
            "card_index": chosen.card_index,
            "target_index": chosen.target_index,
        },
        "parse_ok": parse_ok,
        "schema_ok": schema_ok,
        "legal": legal,
        "chosen_value": chosen_value,
        "optimal_value": oracle["best_value"],
        "worst_value": oracle["worst_value"],
        "regret": regret,
        "normalized_quality": quality,
        "oracle_exact": oracle["exact"],
    }


def _prompt_contract(fixture: ControlledFixture, protocol: dict) -> dict[int, tuple[str, str]]:
    state = load_fixture(fixture)
    prompt_format = protocol["inference"]["prompt_format"]
    prompts = {
        horizon: build_prompt(state, horizon, prompt_format)
        for horizon in protocol["inference"]["horizons"]
    }
    systems = {system for system, _user in prompts.values()}
    normalized = {
        user.replace(
            f"after exactly {horizon} decision transitions",
            "after exactly <H> decision transitions")
        for horizon, (_system, user) in prompts.items()
    }
    if len(systems) != 1 or len(normalized) != 1:
        raise ValueError(f"fixture {fixture.fixture_id} changes more than H")
    return prompts


def _summarize(rows: list[dict], protocol: dict) -> dict:
    by_character = {}
    for character in protocol["pilot_sample"]["characters"]:
        subset = [row for row in rows if row["character"] == character]
        qualities = [row["score"]["normalized_quality"] for row in subset
                     if row["score"]["normalized_quality"] is not None]
        by_horizon = {}
        for horizon in protocol["inference"]["horizons"]:
            cells = [row for row in subset if row["horizon"] == horizon]
            by_horizon[str(horizon)] = {
                "n": len(cells),
                "parse_rate": sum(row["score"]["parse_ok"] for row in cells)
                              / len(cells) if cells else None,
                "legal_rate": sum(row["score"]["legal"] for row in cells)
                              / len(cells) if cells else None,
            }
        by_character[character] = {
            "n_queries": len(subset),
            "parse_rate": sum(row["score"]["parse_ok"] for row in subset)
                          / len(subset) if subset else None,
            "legal_rate": sum(row["score"]["legal"] for row in subset)
                          / len(subset) if subset else None,
            "mean_normalized_quality": statistics.fmean(qualities)
                                       if qualities else None,
            "by_horizon": by_horizon,
        }
    truncations = sum(row["diagnostics"]["truncated"] for row in rows)
    return {
        "completed_queries": len(rows),
        "expected_queries": protocol["inference"]["expected_query_count"],
        "truncation_count": truncations,
        "truncation_rate": truncations / len(rows) if rows else None,
        "by_character": by_character,
    }


def run_pilot(protocol: dict, protocol_digest: str, llm, provider: str,
              release_audit: dict, fixtures: dict, oracle_rows: dict,
              output: Path, cluster_compute: bool = False,
              max_new_queries: int | None = None) -> dict:
    if max_new_queries is not None and max_new_queries < 1:
        raise ValueError("max_new_queries must be positive")
    selection = select_pilot_fixtures(release_audit, protocol)
    prior = json.loads(output.read_text(encoding="utf-8")) if output.exists() else None
    if prior and (prior.get("protocol_digest") != protocol_digest
                  or prior.get("provider") != provider
                  or prior.get("provenance", {}).get("cluster_compute")
                  != cluster_compute):
        raise ValueError("existing pilot checkpoint differs from this invocation")
    created_at = (prior or {}).get(
        "created_at_utc", dt.datetime.now(dt.timezone.utc).isoformat())
    rows = list((prior or {}).get("rows", []))
    completed = {(row["fixture_id"], row["horizon"]) for row in rows}
    new_queries = 0
    if len(completed) != len(rows):
        raise ValueError("pilot checkpoint contains duplicate queries")

    def report() -> dict:
        return {
            "result_schema_version": "2.0",
            "run_kind": "controlled-h-model-pilot" if provider != "mock"
                        else "controlled-h-no-inference-smoke",
            "instrument_version": protocol["instrument_version"],
            "protocol_id": protocol["protocol_id"],
            "protocol_digest": protocol_digest,
            "created_at_utc": created_at,
            "provider": provider,
            "model": protocol["inference"]["served_model_name"],
            "prompt_format": protocol["inference"]["prompt_format"],
            "provenance": {
                "git_commit": _git_value("rev-parse", "HEAD"),
                "git_dirty": bool(_git_value("status", "--porcelain")),
                "model_inference": provider != "mock",
                "paid_api": False,
                "cluster_compute": cluster_compute,
                "model_repository": protocol["inference"]["model_repository"],
                "model_revision": protocol["inference"]["model_revision"],
                "serving_stack": protocol["inference"]["serving_stack"],
                "runtime_versions": {
                    package: _package_version(package)
                    for package in ("vllm", "transformers", "torch")
                },
            },
            "selection": selection,
            "completed_queries": len(rows),
            "expected_queries": protocol["inference"]["expected_query_count"],
            "complete": len(rows) == protocol["inference"]["expected_query_count"],
            "summary": _summarize(rows, protocol),
            "rows": rows,
        }

    decision_by_id = {
        item["fixture_id"]: item for item in selection["decisions"]}
    for fixture_id in selection["selected_fixture_ids"]:
        if fixture_id not in fixtures or fixture_id not in oracle_rows:
            raise ValueError(f"missing fixture/oracle source for {fixture_id}")
        fixture = fixtures[fixture_id]
        oracle_row = oracle_rows[fixture_id]
        prompts = _prompt_contract(fixture, protocol)
        horizon_order = decision_by_id[fixture_id]["horizon_query_order"]
        if sorted(horizon_order) != sorted(protocol["inference"]["horizons"]):
            raise ValueError(f"invalid horizon order for {fixture_id}")
        for horizon in horizon_order:
            if (fixture_id, horizon) in completed:
                continue
            system, user = prompts[horizon]
            response = llm.complete_json(
                system, user,
                temperature=protocol["inference"]["temperature"],
                max_tokens=protocol["inference"]["max_tokens"],
            )
            raw = getattr(llm, "last_raw_response", None)
            finish_reason = getattr(llm, "last_finish_reason", None)
            score = score_precomputed_oracle(oracle_row, horizon, response)
            row = {
                "fixture_id": fixture_id,
                "character": fixture.character,
                "h1_h8_sensitive": decision_by_id[fixture_id][
                    "h1_h8_sensitive"],
                "horizon": horizon,
                "query_order_within_fixture": horizon_order.index(horizon),
                "system_prompt": system,
                "user_prompt": user,
                "system_prompt_sha256": hashlib.sha256(
                    system.encode("utf-8")).hexdigest(),
                "user_prompt_sha256": hashlib.sha256(
                    user.encode("utf-8")).hexdigest(),
                "response_raw": raw,
                "response_parsed": response,
                "diagnostics": {
                    "finish_reason": finish_reason,
                    "raw_length": len(raw) if raw is not None else None,
                    "truncated_think": bool(
                        isinstance(response, dict)
                        and response.get("truncated_think")),
                    "truncated": finish_reason == "length" or bool(
                        isinstance(response, dict)
                        and response.get("truncated_think")),
                },
                "score": score,
            }
            rows.append(row)
            completed.add((fixture_id, horizon))
            new_queries += 1
            _atomic_write_json(output, report())
            if (max_new_queries is not None
                    and new_queries >= max_new_queries):
                return report()
    final = report()
    _atomic_write_json(output, final)
    return final


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, default=PILOT_PROTOCOL_PATH)
    parser.add_argument("--combined-protocol", type=Path,
                        default=COMBINED_PROTOCOL_PATH)
    parser.add_argument("--base-protocol", type=Path,
                        default=FROZEN_PROTOCOL_PATH)
    parser.add_argument("--extension-protocol", type=Path,
                        default=EXTENSION_PROTOCOL_PATH)
    parser.add_argument("--release-audit", type=Path, required=True)
    parser.add_argument("--release-fixtures", type=Path, required=True)
    parser.add_argument("--base-full-audit", type=Path, required=True)
    parser.add_argument("--extension-full-audit", type=Path, required=True)
    parser.add_argument("--provider", choices=("mock", "local"), default="mock")
    parser.add_argument("--base-url")
    parser.add_argument("--authorize-model-inference", action="store_true")
    parser.add_argument("--cluster-compute", action="store_true",
                        help="Record that the local provider is served on a cluster")
    parser.add_argument(
        "--max-new-queries", type=int,
        help="Checkpoint after this many new calls; use 1 for the real-stack smoke")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    protocol, digest = load_pilot_protocol(args.protocol)
    if args.provider != "mock" and not args.authorize_model_inference:
        parser.error("non-mock pilot requires --authorize-model-inference")
    if args.provider != "mock" and args.provider != protocol["inference"]["provider"]:
        parser.error("provider differs from the frozen pilot protocol")
    if args.provider == "mock" and args.cluster_compute:
        parser.error("mock smoke cannot be labelled as cluster compute")
    if args.provider != "mock":
        validate_serving_stack(protocol)
    release_audit, fixtures, oracle_rows = _load_sources(
        protocol, args.combined_protocol, args.release_audit,
        args.release_fixtures, args.base_full_audit,
        args.extension_full_audit, args.base_protocol,
        args.extension_protocol)
    if args.provider == "mock":
        llm = MockLLM([
            '{"action":"end_turn","card_index":-1,"target_index":-1,'
            '"reasoning":"deterministic no-inference smoke"}'
        ])
    else:
        from run_benchmark import build_llm
        llm = build_llm(
            args.provider, protocol["inference"]["served_model_name"],
            base_url=args.base_url)
    report = run_pilot(
        protocol, digest, llm, args.provider, release_audit,
        fixtures, oracle_rows, args.out, cluster_compute=args.cluster_compute,
        max_new_queries=args.max_new_queries)
    print(json.dumps({
        "protocol_id": report["protocol_id"],
        "protocol_digest": report["protocol_digest"],
        "provider": report["provider"],
        "completed_queries": report["completed_queries"],
        "expected_queries": report["expected_queries"],
        "complete": report["complete"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
