#!/usr/bin/env python
"""Compute-free fixture and oracle gates for controlled-decision-horizon-v2.

This script never calls an LLM. It creates model-blind deterministic fixture
recipes, verifies their integrity digests, sizes the exact oracle, and scores the
registered degenerate and H-mismatched baselines before any inference is allowed.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import subprocess
import sys
import time
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from slay_bench.combat import is_combat_over  # noqa: E402
from slay_bench.controlled_horizon import (  # noqa: E402
    CONTROLLED_HORIZON_VERSION,
    DEFAULT_HORIZONS,
    ControlledAction,
    OracleBudgetExceeded,
    OracleTimeBudgetExceeded,
    build_prompt,
    create_fixture,
    exact_action_values,
    legal_actions,
    load_fixture,
    transition,
)
from slay_bench.enums import CardType  # noqa: E402
from slay_bench.rewards import card_pool_for  # noqa: E402


PILOT_ENCOUNTERS = (
    ("GremlinNob",),
    ("Lagavulin",),
    ("SlimeBoss",),
    ("Hexaghost",),
    ("Sentry", "Sentry"),
)

FROZEN_PROTOCOL_PATH = ROOT / "configs" / "controlled_h_v2_preregistration.json"


def _git_value(*args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args], cwd=ROOT, capture_output=True, text=True,
            check=True, timeout=5)
        return result.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def _deck_for_candidate(character: str, seed: int, ordinal: int) -> list[str]:
    """Build a varied ten-card deck from the shipped reward pool."""
    _fixture, state = create_fixture(character, seed, ("Cultist",))
    pool = sorted(name for names in card_pool_for(state).values() for name in names)
    basics = (["Strike_R", "Defend_R", "Bash"] if character == "ironclad"
              else ["Strike_G", "Defend_G", "Neutralize", "Survivor"])
    wanted = 10 - len(basics)
    chosen = []
    cursor = (seed + ordinal * 17) % len(pool)
    stride = 17
    while len(chosen) < wanted:
        name = pool[cursor]
        if name not in chosen:
            chosen.append(name)
        cursor = (cursor + stride) % len(pool)
    return basics + chosen


def _prefix_for_candidate(character: str, seed: int, enemy_ids: tuple[str, ...],
                          ordinal: int, deck_names: list[str],
                          player_hp: int, desired_turn: int | None = None,
                          current_turn_plays: int | None = None
                          ) -> list[ControlledAction]:
    """Produce state diversity with a fixed, non-model policy.

    The policy advances 0--2 complete turns and optionally plays one card on the
    fixture turn. Its choices depend only on candidate ordinal and seed, never on
    an evaluated model or model response.
    """
    _fixture, state = create_fixture(
        character, seed, enemy_ids, deck_names=deck_names, player_hp=player_hp)
    prefix: list[ControlledAction] = []
    desired_turn = desired_turn if desired_turn is not None else 1 + ordinal % 3
    current_turn_plays = (current_turn_plays if current_turn_plays is not None
                          else (ordinal // 3) % 2)
    step = 0

    def choose_play() -> ControlledAction | None:
        plays = [action for action in legal_actions(state) if action.action == "play"]
        if not plays:
            return None
        return plays[(seed + ordinal + step) % len(plays)]

    for _ in range(desired_turn - 1):
        action = choose_play()
        if action is not None:
            state = transition(state, action)
            prefix.append(action)
            step += 1
        if is_combat_over(state):
            raise ValueError("candidate prefix ended combat")
        end = ControlledAction("end_turn")
        state = transition(state, end)
        prefix.append(end)
        step += 1
        if is_combat_over(state):
            raise ValueError("candidate prefix ended combat")

    for _ in range(current_turn_plays):
        action = choose_play()
        if action is None:
            break
        state = transition(state, action)
        prefix.append(action)
        step += 1
        if is_combat_over(state):
            raise ValueError("candidate prefix ended combat")
    return prefix


def generate_fixtures(per_character: int, seed_base: int = 62000,
                      hp_mode: str = "stratified") -> list:
    """Create a deterministic, model-blind pilot fixture set."""
    if hp_mode not in ("stratified", "full"):
        raise ValueError("hp_mode must be stratified or full")
    fixtures = []
    for character_index, character in enumerate(("ironclad", "silent")):
        ordinal = attempts = 0
        while ordinal < per_character:
            seed = seed_base + character_index * 10000 + attempts * 1009
            enemy_ids = PILOT_ENCOUNTERS[attempts % len(PILOT_ENCOUNTERS)]
            attempts += 1
            try:
                deck_names = _deck_for_candidate(character, seed, ordinal)
                max_hp = 80 if character == "ironclad" else 70
                player_hp = (max_hp if hp_mode == "full" else
                             (max_hp, round(max_hp * 0.75), round(max_hp * 0.50))[
                                 ordinal % 3])
                prefix = _prefix_for_candidate(
                    character, seed, enemy_ids, ordinal, deck_names, player_hp)
                family = "pilot-full" if hp_mode == "full" else "pilot"
                fixture_id = f"{family}-{character}-{ordinal:03d}"
                fixture, _state = create_fixture(
                    character, seed, enemy_ids, prefix, fixture_id,
                    deck_names, player_hp)
            except ValueError:
                continue
            fixtures.append(fixture)
            ordinal += 1
    return fixtures


def load_frozen_protocol(path: Path = FROZEN_PROTOCOL_PATH) -> tuple[dict, str]:
    """Load and hash the immutable preregistration payload."""
    protocol = json.loads(path.read_text(encoding="utf-8"))
    if protocol.get("instrument_version") != CONTROLLED_HORIZON_VERSION:
        raise ValueError("frozen protocol instrument version does not match code")
    rendered = json.dumps(protocol, sort_keys=True, separators=(",", ":"))
    return protocol, hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def _protocol_rank(protocol_id: str, fixture_id: str) -> str:
    return hashlib.sha256(f"{protocol_id}:{fixture_id}".encode("utf-8")).hexdigest()


def generate_frozen_candidates(protocol: dict) -> tuple[list, list[dict]]:
    """Generate every predeclared candidate once, without outcome-driven replacement."""
    spec = protocol["candidate_generation"]
    fixtures = []
    attempts = []
    encounters = [tuple(ids) for ids in spec["encounters"]]
    hp_fractions = spec["hp_fractions"]
    turns = spec["combat_turns"]
    fixture_plays = spec["fixture_turn_plays"]
    per_character = spec["candidates_per_character"]
    for character_index, character in enumerate(spec["characters"]):
        max_hp = 80 if character == "ironclad" else 70
        for ordinal in range(per_character):
            fixture_id = (
                f"{protocol['protocol_id']}-{character}-{ordinal:04d}")
            seed = (spec["seed_base"]
                    + character_index * spec["character_seed_offset"]
                    + ordinal * spec["seed_stride"])
            encounter = encounters[ordinal % len(encounters)]
            hp_index = (ordinal // len(encounters)) % len(hp_fractions)
            turn_index = (
                ordinal // (len(encounters) * len(hp_fractions))) % len(turns)
            play_index = (
                ordinal // (len(encounters) * len(hp_fractions) * len(turns))
            ) % len(fixture_plays)
            player_hp = round(max_hp * hp_fractions[hp_index])
            attempt = {
                "fixture_id": fixture_id,
                "character": character,
                "ordinal": ordinal,
                "seed": seed,
                "enemy_ids": list(encounter),
                "hp_fraction": hp_fractions[hp_index],
                "target_combat_turn": turns[turn_index],
                "fixture_turn_plays": fixture_plays[play_index],
                "generated": False,
                "error": None,
            }
            try:
                deck_names = _deck_for_candidate(character, seed, ordinal)
                prefix = _prefix_for_candidate(
                    character, seed, encounter, ordinal, deck_names, player_hp,
                    desired_turn=turns[turn_index],
                    current_turn_plays=fixture_plays[play_index])
                fixture, _state = create_fixture(
                    character, seed, encounter, prefix, fixture_id,
                    deck_names, player_hp)
                fixtures.append(fixture)
                attempt["generated"] = True
                attempt["state_digest"] = fixture.state_digest
            except ValueError as exc:
                attempt["error"] = {"type": type(exc).__name__, "message": str(exc)}
            attempts.append(attempt)
    return fixtures, attempts


def _optimal_keys(row: dict, horizon: int) -> set[str]:
    oracle = row.get("oracles", {}).get(str(horizon))
    if not oracle:
        return set()
    return {
        _action_key(ControlledAction(**action))
        for action in oracle["optimal_actions"]
    }


def select_frozen_advancements(screen_rows: list[dict], protocol: dict) -> dict:
    """Apply the preregistered H=1/H=4 advancement rule deterministically."""
    spec = protocol["screen"]
    protocol_id = protocol["protocol_id"]
    decisions = []
    selected_ids = set()
    negative_by_character = {
        character: [] for character in protocol["candidate_generation"]["characters"]}
    for row in screen_rows:
        fixture = row["fixture"]
        fixture_id = fixture["fixture_id"]
        character = fixture["character"]
        eligible = (
            row.get("error") is None
            and row.get("prompt_only_h_changes") is True
            and bool(_optimal_keys(row, 1))
            and bool(_optimal_keys(row, 4))
            and not row["oracles"]["4"]["zero_span"]
        )
        disjoint = eligible and _optimal_keys(row, 1).isdisjoint(
            _optimal_keys(row, 4))
        decision = {
            "fixture_id": fixture_id,
            "character": character,
            "eligible": eligible,
            "disjoint_h1_h4": bool(disjoint),
            "rank": _protocol_rank(protocol_id, fixture_id),
            "advanced": False,
            "reason": "screen_ineligible",
        }
        if disjoint and spec["advance_all_disjoint_h1_h4"]:
            decision["advanced"] = True
            decision["reason"] = "all_screen_sensitive"
            selected_ids.add(fixture_id)
        elif eligible:
            decision["reason"] = "screen_insensitive_rank_pool"
            negative_by_character[character].append(decision)
        decisions.append(decision)
    limit = spec["screen_insensitive_advances_per_character"]
    for character, pool in negative_by_character.items():
        for decision in sorted(pool, key=lambda item: item["rank"])[:limit]:
            decision["advanced"] = True
            decision["reason"] = "ranked_screen_insensitive_control"
            selected_ids.add(decision["fixture_id"])
    return {
        "selected_fixture_ids": sorted(selected_ids),
        "decisions": decisions,
    }


def select_frozen_release(full_rows: list[dict], protocol: dict) -> dict:
    """Select the fixed character/sensitivity quotas or fail closed."""
    spec = protocol["release"]
    protocol_id = protocol["protocol_id"]
    buckets = {}
    dispositions = []
    for row in full_rows:
        fixture = row["fixture"]
        fixture_id = fixture["fixture_id"]
        character = fixture["character"]
        h1 = _optimal_keys(row, 1)
        h8 = _optimal_keys(row, 8)
        eligible = (
            row.get("error") is None
            and (not spec["require_prompt_invariance"]
                 or row.get("prompt_only_h_changes") is True)
            and bool(h1) and bool(h8)
            and (not spec["require_nonzero_h8_oracle_span"]
                 or not row["oracles"]["8"]["zero_span"])
            and (not spec["require_exact_oracles_at_all_horizons"]
                 or all(str(h) in row["oracles"] and row["oracles"][str(h)]["exact"]
                        for h in protocol["full_oracle"]["horizons"]))
        )
        sensitive = eligible and h1.isdisjoint(h8)
        if (sensitive
                and spec["require_h1_mismatch_loss_on_sensitive_fixtures"]
                and row["oracles"]["8"]["baselines"][
                    "h1_mismatched_oracle"]["regret"] <= 0):
            eligible = False
            sensitive = False
        disposition = {
            "fixture_id": fixture_id,
            "character": character,
            "eligible": eligible,
            "h1_h8_sensitive": bool(sensitive),
            "rank": _protocol_rank(protocol_id, fixture_id),
            "released": False,
            "reason": "full_oracle_ineligible",
        }
        if eligible:
            key = (character, bool(sensitive))
            buckets.setdefault(key, []).append(disposition)
            disposition["reason"] = "eligible_rank_pool"
        dispositions.append(disposition)

    shortfalls = []
    selected_ids = set()
    for character in protocol["candidate_generation"]["characters"]:
        for sensitive, quota_key in (
                (True, "h1_h8_sensitive_per_character"),
                (False, "h1_h8_insensitive_per_character")):
            quota = spec[quota_key]
            pool = sorted(buckets.get((character, sensitive), []),
                          key=lambda item: item["rank"])
            if len(pool) < quota:
                shortfalls.append({
                    "character": character,
                    "h1_h8_sensitive": sensitive,
                    "required": quota,
                    "available": len(pool),
                })
            for disposition in pool[:quota]:
                disposition["released"] = True
                disposition["reason"] = "selected_by_preregistered_rank"
                selected_ids.add(disposition["fixture_id"])
    expected = (spec["fixtures_per_character"]
                * len(protocol["candidate_generation"]["characters"]))
    sensitive_n = sum(item["released"] and item["h1_h8_sensitive"]
                      for item in dispositions)
    fraction = sensitive_n / len(selected_ids) if selected_ids else 0.0
    gate = (not shortfalls and len(selected_ids) == expected
            and fraction >= spec["minimum_sensitive_fraction"])
    return {
        "release_gate_passed": gate,
        "selected_fixture_ids": sorted(selected_ids) if gate else [],
        "candidate_selected_fixture_ids": sorted(selected_ids),
        "shortfalls": shortfalls,
        "sensitive_fraction": fraction,
        "dispositions": dispositions,
    }


def _action_key(action: ControlledAction) -> str:
    return f"{action.action}:{action.card_index}:{action.target_index}"


def _action_list(actions) -> list[dict]:
    return [asdict(action) for action in actions]


def _quality(value: float, best: float, worst: float) -> float:
    return 1.0 if best == worst else (value - worst) / (best - worst)


def _baseline_rows(state, oracle, h1_actions: list[ControlledAction]) -> dict:
    actions = legal_actions(state)
    plays = [action for action in actions if action.action == "play"]
    end_turn = ControlledAction("end_turn")

    def value(action: ControlledAction) -> float:
        return oracle.action_values[_action_key(action)]

    def row(action: ControlledAction) -> dict:
        action_value = value(action)
        return {
            "action": asdict(action),
            "value": action_value,
            "regret": oracle.best_value - action_value,
            "quality": _quality(action_value, oracle.best_value, oracle.worst_value),
        }

    # Immediate damage is measured on a clone after one transition. Ties break
    # by the stable legal-action ordering.
    initial_enemy_hp = sum(max(0, enemy.hp) for enemy in state.combat.enemies)
    immediate = []
    for action in actions:
        nxt = transition(state, action)
        remaining = sum(max(0, enemy.hp) for enemy in nxt.combat.enemies)
        immediate.append((initial_enemy_hp - remaining, action))
    immediate_best = max(immediate, key=lambda pair: (pair[0], -actions.index(pair[1])))[1]
    one_step = min(h1_actions)
    mismatch = max(h1_actions, key=value)  # conservative: best H=1 optimum at target H

    uniform_value = sum(value(action) for action in actions) / len(actions)
    return {
        "always_end_turn": row(end_turn),
        "first_legal_card": row(plays[0] if plays else end_turn),
        "immediate_damage_greedy": row(immediate_best),
        "one_step_utility_greedy": row(one_step),
        "h1_mismatched_oracle": row(mismatch),
        "uniform_legal_expected": {
            "action": None,
            "value": uniform_value,
            "regret": oracle.best_value - uniform_value,
            "quality": _quality(
                uniform_value, oracle.best_value, oracle.worst_value),
        },
        "h_aware_exact_oracle": {
            "action": None,
            "value": oracle.best_value,
            "regret": 0.0,
            "quality": 1.0,
        },
    }


def _prompt_only_h_changes(state, horizons: tuple[int, ...]) -> bool:
    for prompt_format in ("structured", "raw"):
        normalized = []
        systems = []
        for horizon in horizons:
            system, prompt = build_prompt(state, horizon, prompt_format)
            systems.append(system)
            normalized.append(prompt.replace(
                f"after exactly {horizon} decision transitions",
                "after exactly <H> decision transitions"))
        if len(set(systems)) != 1 or len(set(normalized)) != 1:
            return False
    return True


def audit_fixture(fixture, horizons: tuple[int, ...], node_budget: int,
                  wall_time_budget_s: float | None = None) -> dict:
    state = load_fixture(fixture)
    actions = legal_actions(state)
    action_contract = _action_list(actions)
    row = {
        "fixture": asdict(fixture),
        "strata": {
            "character": fixture.character,
            "combat_turn": state.combat.turn,
            "player_hp": state.player.hp,
            "enemy_count": sum(enemy.hp > 0 for enemy in state.combat.enemies),
            "hand_size": len(state.combat.hand),
            "legal_action_count": len(actions),
            "energy": state.player.energy,
            "has_attack": any(card.type == CardType.ATTACK for card in state.combat.hand),
            "has_defense_or_setup": any(
                card.type in (CardType.SKILL, CardType.POWER)
                for card in state.combat.hand),
        },
        "prompt_only_h_changes": _prompt_only_h_changes(state, horizons),
        "action_contract": action_contract,
        "oracles": {},
        "error": None,
    }
    h1_actions: list[ControlledAction] | None = None
    try:
        for horizon in horizons:
            started = time.perf_counter()
            oracle = exact_action_values(
                state, horizon, node_budget=node_budget,
                wall_time_budget_s=wall_time_budget_s)
            elapsed = time.perf_counter() - started
            if horizon == 1:
                h1_actions = list(oracle.optimal_actions)
            assert h1_actions is not None
            row["oracles"][str(horizon)] = {
                **asdict(oracle),
                "wall_seconds": elapsed,
                "zero_span": oracle.best_value == oracle.worst_value,
                "baselines": _baseline_rows(state, oracle, h1_actions),
            }
    except (OracleBudgetExceeded, OracleTimeBudgetExceeded) as exc:
        row["error"] = {"type": type(exc).__name__, "message": str(exc)}

    if row["error"] is None and "1" in row["oracles"] and "8" in row["oracles"]:
        h1 = {_action_key(ControlledAction(**action))
              for action in row["oracles"]["1"]["optimal_actions"]}
        h8 = {_action_key(ControlledAction(**action))
              for action in row["oracles"]["8"]["optimal_actions"]}
        row["optimal_sets_differ_h1_h8"] = h1 != h8
        row["horizon_sensitive_h1_h8"] = h1.isdisjoint(h8)
    else:
        row["optimal_sets_differ_h1_h8"] = None
        row["horizon_sensitive_h1_h8"] = None
    return row


def summarize(rows: list[dict], node_budget: int,
              wall_time_budget_s: float | None = None,
              horizons: tuple[int, ...] = DEFAULT_HORIZONS) -> dict:
    exact_rows = [row for row in rows if row["error"] is None]
    sensitive = [row for row in exact_rows if row["horizon_sensitive_h1_h8"]]
    mismatched = [
        row["oracles"]["8"]["baselines"]["h1_mismatched_oracle"]
        for row in sensitive
    ]
    treatment_rate = len(sensitive) / len(exact_rows) if exact_rows else 0.0
    mismatch_mean_quality = (
        sum(item["quality"] for item in mismatched) / len(mismatched)
        if mismatched else None)
    gate = {
        "all_oracles_exact_within_budget": len(exact_rows) == len(rows),
        "prompt_only_h_changes": all(
            row["prompt_only_h_changes"] for row in rows),
        "treatment_strength_at_least_20pct": treatment_rate >= 0.20,
        "h1_mismatch_loses_on_sensitive_subset": bool(mismatched) and all(
            item["regret"] > 0 for item in mismatched),
        "exact_oracle_quality_is_one": all(
            oracle["baselines"]["h_aware_exact_oracle"]["quality"] == 1.0
            for row in exact_rows for oracle in row["oracles"].values()),
    }
    return {
        "fixture_count": len(rows),
        "exact_fixture_count": len(exact_rows),
        "oracle_budget_failures": len(rows) - len(exact_rows),
        "oracle_node_budget_failures": sum(
            (row.get("error") or {}).get("type") == "OracleBudgetExceeded"
            for row in rows),
        "oracle_time_budget_failures": sum(
            (row.get("error") or {}).get("type") == "OracleTimeBudgetExceeded"
            for row in rows),
        "node_budget_per_fixture_h": node_budget,
        "wall_time_budget_seconds_per_fixture_h": wall_time_budget_s,
        "horizons": list(horizons),
        "h1_h8_disjoint_optimal_set_count": len(sensitive),
        "treatment_strength_rate": treatment_rate,
        "h1_mismatch_mean_quality_sensitive": mismatch_mean_quality,
        "max_h8_nodes": max((
            row["oracles"]["8"]["nodes_expanded"]
            for row in exact_rows if "8" in row["oracles"]), default=None),
        "total_oracle_wall_seconds": sum(
            oracle["wall_seconds"] for row in exact_rows
            for oracle in row["oracles"].values()),
        "gate": gate,
        "go_for_model_pilot": all(gate.values()),
    }


def _atomic_write_json(path: Path, payload: dict, compact: bool = False) -> None:
    """Replace a checkpoint only after its complete JSON has been written."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    rendered = json.dumps(payload, indent=None if compact else 2, sort_keys=True) + "\n"
    temporary.write_text(rendered, encoding="utf-8")
    temporary.replace(path)


def _build_report(fixtures, rows, args, created_at_utc: str) -> dict:
    return {
        "result_schema_version": "2.0",
        "instrument_version": CONTROLLED_HORIZON_VERSION,
        "run_kind": "compute-free-fixture-oracle-pilot",
        "created_at_utc": created_at_utc,
        "provenance": {
            "git_commit": _git_value("rev-parse", "HEAD"),
            "git_dirty": bool(_git_value("status", "--porcelain")),
            "model_inference": False,
            "paid_api": False,
            "cluster_compute": False,
        },
        "selection": {
            "model_blind": True,
            "generator": "fixed seed/enemy schedule with deterministic prefix policy",
            "per_character": args.per_character,
            "horizons": list(args.horizons),
            "node_budget_per_fixture_h": args.node_budget,
            "wall_time_budget_seconds_per_fixture_h": args.wall_seconds_per_h,
            "seed_base": args.seed_base,
            "hp_mode": args.hp_mode,
        },
        "checkpoint": {
            "completed_fixture_rows": len(rows),
            "requested_fixture_rows": len(fixtures),
            "complete": len(rows) == len(fixtures),
        },
        "summary": summarize(
            rows, args.node_budget, args.wall_seconds_per_h,
            tuple(args.horizons)),
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--per-character", type=int, default=10)
    parser.add_argument("--node-budget", type=int, default=2_000_000)
    parser.add_argument("--wall-seconds-per-h", type=float, default=120.0)
    parser.add_argument("--horizons", type=int, nargs="+",
                        default=list(DEFAULT_HORIZONS),
                        choices=list(DEFAULT_HORIZONS))
    parser.add_argument("--seed-base", type=int, default=62000)
    parser.add_argument("--hp-mode", choices=["stratified", "full"],
                        default="stratified")
    parser.add_argument(
        "--fixture-id", action="append", default=[],
        help="Audit only the named generated fixture; repeat for multiple IDs.")
    parser.add_argument("--fixtures-out", type=Path)
    parser.add_argument("--audit-out", type=Path)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    if args.per_character < 1:
        parser.error("--per-character must be positive")
    if args.node_budget < 1:
        parser.error("--node-budget must be positive")
    if args.wall_seconds_per_h <= 0:
        parser.error("--wall-seconds-per-h must be positive")
    args.horizons = list(dict.fromkeys(args.horizons))
    if 1 not in args.horizons:
        parser.error("--horizons must include 1 for registered baseline scoring")

    fixtures = generate_fixtures(
        args.per_character, seed_base=args.seed_base, hp_mode=args.hp_mode)
    if args.fixture_id:
        requested = set(args.fixture_id)
        fixtures = [fixture for fixture in fixtures
                    if fixture.fixture_id in requested]
        missing = requested - {fixture.fixture_id for fixture in fixtures}
        if missing:
            parser.error("unknown --fixture-id(s) for generated pool: "
                         + ", ".join(sorted(missing)))
    if args.fixtures_out:
        _atomic_write_json(args.fixtures_out,
            {"version": CONTROLLED_HORIZON_VERSION,
             "fixtures": [asdict(fixture) for fixture in fixtures]})

    created_at_utc = dt.datetime.now(dt.timezone.utc).isoformat()
    rows = []
    for index, fixture in enumerate(fixtures, 1):
        print(f"[{index}/{len(fixtures)}] auditing {fixture.fixture_id}",
              file=sys.stderr, flush=True)
        rows.append(audit_fixture(
            fixture, tuple(args.horizons), args.node_budget,
            args.wall_seconds_per_h))
        if args.audit_out:
            _atomic_write_json(
                args.audit_out,
                _build_report(fixtures, rows, args, created_at_utc),
                compact=args.compact)
    report = _build_report(fixtures, rows, args, created_at_utc)
    rendered = json.dumps(report, indent=None if args.compact else 2, sort_keys=True)
    print(rendered)


if __name__ == "__main__":
    main()
