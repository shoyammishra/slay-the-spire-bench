#!/usr/bin/env python
"""Prospective and pilot-informed power analysis for controlled-H."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import statistics
import sys
from pathlib import Path
from statistics import NormalDist

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.controlled_horizon_model_pilot import (
    PILOT_PROTOCOL_PATH,
    load_pilot_protocol,
)
from scripts.controlled_horizon_pilot import _atomic_write_json


def normal_approx_power(effect_abs: float, sd: float, n: int,
                        alpha: float) -> float:
    if effect_abs <= 0 or sd <= 0 or n < 2 or not 0 < alpha < 1:
        raise ValueError("power inputs must be positive and 0 < alpha < 1")
    normal = NormalDist()
    critical = normal.inv_cdf(1 - alpha / 2)
    noncentrality = effect_abs * math.sqrt(n) / sd
    return (normal.cdf(-critical - noncentrality)
            + 1 - normal.cdf(critical - noncentrality))


def required_n(effect_abs: float, sd: float, alpha: float,
               target_power: float) -> int:
    if not 0 < target_power < 1:
        raise ValueError("target power must be between zero and one")
    normal = NormalDist()
    z_alpha = normal.inv_cdf(1 - alpha / 2)
    z_power = normal.inv_cdf(target_power)
    return max(2, math.ceil(((z_alpha + z_power) * sd / effect_abs) ** 2))


def prospective_table(protocol: dict) -> dict:
    spec = protocol["power"]
    effect = spec["minimum_mean_quality_difference_abs"]
    alpha = spec["two_sided_alpha"]
    target = spec["target_power"]
    rows = []
    for sd in spec["prospective_sd_grid"]:
        row = {
            "sd": sd,
            "required_n_per_character": required_n(effect, sd, alpha, target),
            "power_by_n_per_character": {
                str(n): normal_approx_power(effect, sd, n, alpha)
                for n in spec["prospective_n_grid_per_character"]
            },
        }
        rows.append(row)
    return {
        "method": "two-sided normal approximation for paired fixture differences",
        "effect_abs": effect,
        "alpha": alpha,
        "target_power": target,
        "rows": rows,
    }


def _percentile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, math.ceil(probability * len(ordered)) - 1)
    return ordered[index]


def bootstrap_sd_upper(differences: list[float], replicates: int,
                       seed: int) -> float:
    if len(differences) < 2:
        raise ValueError("at least two paired fixture differences are required")
    rng = random.Random(seed)
    boot = []
    for _ in range(replicates):
        sample = [differences[rng.randrange(len(differences))]
                  for _ in differences]
        boot.append(statistics.stdev(sample))
    return _percentile(boot, 0.95)


def analyze_pilot(report: dict, protocol: dict) -> dict:
    if report.get("protocol_id") != protocol["protocol_id"]:
        raise ValueError("pilot report protocol ID differs from power protocol")
    rendered = json.dumps(protocol, sort_keys=True, separators=(",", ":"))
    expected_digest = hashlib.sha256(rendered.encode("utf-8")).hexdigest()
    if report.get("protocol_digest") != expected_digest:
        raise ValueError("pilot report protocol digest differs from power protocol")
    if report.get("provider") == "mock":
        raise ValueError("mock responses cannot supply model-variance power estimates")
    power = protocol["power"]
    gate_spec = protocol["pilot_gate"]
    by_character = {}
    power_gate = True
    for char_index, character in enumerate(protocol["pilot_sample"]["characters"]):
        values = collections_by_fixture(report["rows"], character)
        differences = []
        for fixture_id, horizons in values.items():
            if 1 in horizons and 8 in horizons:
                one = horizons[1]
                eight = horizons[8]
                if one is not None and eight is not None:
                    differences.append(eight - one)
        if len(differences) != protocol["pilot_sample"]["fixtures_per_character"]:
            power_gate = False
        sd_observed = statistics.stdev(differences) if len(differences) >= 2 else None
        sd_upper = (bootstrap_sd_upper(
            differences, power["bootstrap_replicates"],
            power["bootstrap_seed"] + char_index)
            if len(differences) >= 2 else None)
        needed = (required_n(
            power["minimum_mean_quality_difference_abs"], sd_upper,
            power["two_sided_alpha"], power["target_power"])
            if sd_upper and sd_upper > 0 else (2 if sd_upper == 0 else None))
        powered = (needed is not None and needed
                   <= gate_spec["maximum_powered_full_fixtures_per_character"])
        power_gate = power_gate and powered
        by_character[character] = {
            "paired_fixture_count": len(differences),
            "observed_mean_h8_minus_h1": statistics.fmean(differences)
                                           if differences else None,
            "observed_sd": sd_observed,
            "bootstrap_95pct_upper_sd": sd_upper,
            "required_n_per_character": needed,
            "powered_within_release": powered,
        }

    summary = report["summary"]
    operational = {
        "all_queries_complete": report.get("complete") is True
            and report.get("completed_queries") == gate_spec[
                "completed_queries_required"],
        "parse_rate_per_character": all(
            summary["by_character"][character]["parse_rate"] is not None
            and summary["by_character"][character]["parse_rate"]
            >= gate_spec["minimum_parse_rate_per_character"]
            for character in protocol["pilot_sample"]["characters"]),
        "legal_rate_per_character": all(
            summary["by_character"][character]["legal_rate"] is not None
            and summary["by_character"][character]["legal_rate"]
            >= gate_spec["minimum_legal_rate_per_character"]
            for character in protocol["pilot_sample"]["characters"]),
        "parse_rate_per_character_horizon": all(
            cell["parse_rate"] is not None and cell["parse_rate"]
            >= gate_spec["minimum_parse_rate_per_character_horizon"]
            for character in protocol["pilot_sample"]["characters"]
            for cell in summary["by_character"][character]["by_horizon"].values()),
        "truncation_rate": summary["truncation_rate"] is not None
            and summary["truncation_rate"]
            <= gate_spec["maximum_truncation_rate"],
        "variance_powered_within_release": power_gate,
    }
    return {
        "by_character": by_character,
        "operational_gate": operational,
        "go_for_registered_matrix": all(operational.values()),
        "observed_effect_sign_used_for_gate": False,
    }


def collections_by_fixture(rows: list[dict], character: str) -> dict:
    values = {}
    for row in rows:
        if row["character"] != character:
            continue
        values.setdefault(row["fixture_id"], {})[row["horizon"]] = (
            row["score"]["normalized_quality"])
    return values


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, default=PILOT_PROTOCOL_PATH)
    parser.add_argument("--pilot-report", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    protocol, digest = load_pilot_protocol(args.protocol)
    report = {
        "result_schema_version": "2.0",
        "run_kind": "controlled-h-power-analysis",
        "protocol_id": protocol["protocol_id"],
        "protocol_digest": digest,
        "prospective": prospective_table(protocol),
        "pilot_informed": None,
        "model_inference": False,
    }
    if args.pilot_report:
        pilot = json.loads(args.pilot_report.read_text(encoding="utf-8"))
        report["pilot_informed"] = analyze_pilot(pilot, protocol)
    _atomic_write_json(args.out, report)
    print(json.dumps({
        "protocol_id": report["protocol_id"],
        "protocol_digest": report["protocol_digest"],
        "pilot_informed": report["pilot_informed"] is not None,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
