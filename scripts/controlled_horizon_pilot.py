#!/usr/bin/env python
"""Compute-free fixture and oracle gates for controlled-decision-horizon-v1.

This script never calls an LLM. It creates model-blind deterministic fixture
recipes, verifies their integrity digests, sizes the exact oracle, and scores the
registered degenerate and H-mismatched baselines before any inference is allowed.
"""
from __future__ import annotations

import argparse
import datetime as dt
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
    ("Cultist",),
    ("JawWorm",),
    ("RedLouse",),
    ("GreenLouse",),
    ("AcidSlimeM",),
    ("FungalBeast",),
    ("RedLouse", "GreenLouse"),
)


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
                          player_hp: int) -> list[ControlledAction]:
    """Produce state diversity with a fixed, non-model policy.

    The policy advances 0--2 complete turns and optionally plays one card on the
    fixture turn. Its choices depend only on candidate ordinal and seed, never on
    an evaluated model or model response.
    """
    _fixture, state = create_fixture(
        character, seed, enemy_ids, deck_names=deck_names, player_hp=player_hp)
    prefix: list[ControlledAction] = []
    desired_turn = 1 + ordinal % 3
    current_turn_plays = (ordinal // 3) % 2
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


def generate_fixtures(per_character: int) -> list:
    """Create a deterministic, model-blind pilot fixture set."""
    fixtures = []
    for character_index, character in enumerate(("ironclad", "silent")):
        ordinal = attempts = 0
        while ordinal < per_character:
            seed = 42000 + character_index * 10000 + attempts * 1009
            enemy_ids = PILOT_ENCOUNTERS[attempts % len(PILOT_ENCOUNTERS)]
            attempts += 1
            try:
                deck_names = _deck_for_candidate(character, seed, ordinal)
                max_hp = 80 if character == "ironclad" else 70
                player_hp = (max_hp, round(max_hp * 0.75), round(max_hp * 0.50))[
                    ordinal % 3]
                prefix = _prefix_for_candidate(
                    character, seed, enemy_ids, ordinal, deck_names, player_hp)
                fixture_id = f"pilot-{character}-{ordinal:03d}"
                fixture, _state = create_fixture(
                    character, seed, enemy_ids, prefix, fixture_id,
                    deck_names, player_hp)
            except ValueError:
                continue
            fixtures.append(fixture)
            ordinal += 1
    return fixtures


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
    normalized = []
    systems = []
    for horizon in horizons:
        system, prompt = build_prompt(state, horizon, "structured")
        systems.append(system)
        normalized.append(prompt.replace(
            f"after exactly {horizon} decision transitions",
            "after exactly <H> decision transitions"))
    return len(set(systems)) == 1 and len(set(normalized)) == 1


def audit_fixture(fixture, horizons: tuple[int, ...], node_budget: int) -> dict:
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
            oracle = exact_action_values(state, horizon, node_budget=node_budget)
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
    except OracleBudgetExceeded as exc:
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


def summarize(rows: list[dict], node_budget: int) -> dict:
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
        "node_budget_per_fixture_h": node_budget,
        "h1_h8_disjoint_optimal_set_count": len(sensitive),
        "treatment_strength_rate": treatment_rate,
        "h1_mismatch_mean_quality_sensitive": mismatch_mean_quality,
        "max_h8_nodes": max(
            (row["oracles"]["8"]["nodes_expanded"] for row in exact_rows),
            default=None),
        "total_oracle_wall_seconds": sum(
            oracle["wall_seconds"] for row in exact_rows
            for oracle in row["oracles"].values()),
        "gate": gate,
        "go_for_model_pilot": all(gate.values()),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--per-character", type=int, default=10)
    parser.add_argument("--node-budget", type=int, default=2_000_000)
    parser.add_argument("--fixtures-out", type=Path)
    parser.add_argument("--audit-out", type=Path)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    if args.per_character < 1:
        parser.error("--per-character must be positive")
    if args.node_budget < 1:
        parser.error("--node-budget must be positive")

    fixtures = generate_fixtures(args.per_character)
    if args.fixtures_out:
        args.fixtures_out.parent.mkdir(parents=True, exist_ok=True)
        args.fixtures_out.write_text(json.dumps(
            {"version": CONTROLLED_HORIZON_VERSION,
             "fixtures": [asdict(fixture) for fixture in fixtures]},
            indent=2, sort_keys=True) + "\n", encoding="utf-8")

    rows = []
    for index, fixture in enumerate(fixtures, 1):
        print(f"[{index}/{len(fixtures)}] auditing {fixture.fixture_id}",
              file=sys.stderr, flush=True)
        rows.append(audit_fixture(fixture, DEFAULT_HORIZONS, args.node_budget))
    report = {
        "result_schema_version": "2.0",
        "instrument_version": CONTROLLED_HORIZON_VERSION,
        "run_kind": "compute-free-fixture-oracle-pilot",
        "created_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
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
            "horizons": list(DEFAULT_HORIZONS),
        },
        "summary": summarize(rows, args.node_budget),
        "rows": rows,
    }
    rendered = json.dumps(report, indent=None if args.compact else 2, sort_keys=True)
    if args.audit_out:
        args.audit_out.parent.mkdir(parents=True, exist_ok=True)
        args.audit_out.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
