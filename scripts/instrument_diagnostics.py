#!/usr/bin/env python
"""Compute-free adversarial diagnostics for the benchmark instrument.

This script does not call a model or mutate saved results.  It tests whether a
degenerate lookup policy can solve the fixed synergy fixtures and inventories the
auditability of persisted result artifacts.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from slay_bench.benchmark import (  # noqa: E402
    _SYNERGY_FIXTURES_BY_CHAR,
    _classify_archetype_confident,
    _get_archetype_tables,
)
from slay_bench.cards import make_card_for  # noqa: E402

PAPER_BASE_SEEDS = (42, 1042, 2042, 3042, 4042)


def synergy_lookup_audit() -> dict:
    """Score a non-planning dictionary lookup on every fixture and position.

    The policy labels the deck from card-name membership and selects the sole offer
    in that label's shipped card-name bucket.  It does no rollout, utility estimate,
    opponent modeling, or resource planning.
    """
    by_character = {}
    for character in ("ironclad", "silent"):
        fixtures = list(_SYNERGY_FIXTURES_BY_CHAR[character])
        archetypes, _payoffs, _default = _get_archetype_tables(character)
        archetype_correct = pick_correct = total = unique_offer_cases = 0
        target_positions = {0: 0, 1: 0, 2: 0}
        for _declared_arch, deck_names, offer_names, original_pick in fixtures:
            deck = [make_card_for(character, name) for name in deck_names]
            inferred_arch, confident = _classify_archetype_confident(deck, [], character)
            for target_position in range(3):
                rotation = (original_pick - target_position) % len(offer_names)
                rotated = list(offer_names[rotation:]) + list(offer_names[:rotation])
                offers = [make_card_for(character, name) for name in rotated]
                candidates = [i for i, card in enumerate(offers)
                              if card.name in set(archetypes[inferred_arch])]
                total += 1
                target_positions[target_position] += 1
                archetype_correct += int(confident and inferred_arch == _declared_arch)
                unique_offer_cases += int(len(candidates) == 1)
                pick_correct += int(len(candidates) == 1 and candidates[0] == target_position)
        by_character[character] = {
            "fixture_position_cases": total,
            "archetype_lookup_accuracy": archetype_correct / total,
            "unique_on_label_offer_rate": unique_offer_cases / total,
            "card_pick_lookup_accuracy": pick_correct / total,
            "expert_position_counts": target_positions,
        }
    return {
        "policy": "card-name dictionary lookup; no simulator or lookahead",
        "by_character": by_character,
        "interpretation": (
            "Perfect lookup performance demonstrates label leakage/recognition, not "
            "planning. It does not prove that evaluated LLMs used this shortcut."),
    }


def artifact_audit(results_dir: Path, include_files: bool = False) -> dict:
    files = []
    for path in sorted(results_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict) or "model" not in data:
            continue
        dims = {}
        for dim in ("turn", "combat", "synergy", "run"):
            payload = data.get(dim)
            dims[dim] = {
                "present": payload is not None,
                "samples_persisted": bool(isinstance(payload, dict) and "samples" in payload),
            }
        files.append({
            "file": path.name,
            "aggregate": "seeds" in path.stem,
            "has_provenance": isinstance(data.get("provenance"), dict),
            "has_instrument_version": bool(data.get("instrument_version")),
            "dimensions": dims,
        })
    report = {
        "artifact_count": len(files),
        "with_provenance": sum(f["has_provenance"] for f in files),
        "with_instrument_version": sum(f["has_instrument_version"] for f in files),
        "per_dimension_sample_artifacts": {
            dim: sum(f["dimensions"][dim]["samples_persisted"] for f in files)
            for dim in ("turn", "combat", "synergy", "run")
        },
    }
    if include_files:
        report["files"] = files
    return report


def instrument_inventory() -> dict:
    return {
        "legacy_four_task_controlled_horizon": False,
        "controlled_horizon_v1_status": "superseded pre-inference: hidden-state collision",
        "controlled_horizon_v2_status": "implemented; no model results",
        "turn": {
            "enemy_classes": ["Cultist"],
            "state_family": "starter-deck opening state",
            "objective": "immediate enemy HP loss only",
            "oracle": "depth-first sequence search with a 20,000-node budget",
        },
        "combat": {
            "enemy_classes": ["Cultist", "JawWorm"],
            "baseline": "play every playable card in current hand order",
            "optimal_oracle": False,
        },
        "synergy": {
            "state_family": "fixed single-archetype decks",
            "candidate_design": "exactly one on-label offer plus two distractors",
            "forward_utility_oracle": False,
        },
        "run_default": {
            "llm_controls": ["combat card actions", "card reward choice"],
            "scripted_controls": [
                "leftmost map path", "rest unless mechanically overridden",
                "merchant policy", "event option 0"],
            "description": "hybrid scripted-policy rollout, not full-run agent control",
        },
    }


def turn_oracle_audit(base_seeds=PAPER_BASE_SEEDS, n_per_base: int = 20) -> dict:
    """Replay the current turn fixture generator and audit the bounded oracle."""
    from slay_bench import new_game, start_combat
    from slay_bench.benchmark import _exhaustive_best_sequence
    from slay_bench.enemies import Cultist

    rows = {}
    for character in ("ironclad", "silent"):
        audits = []
        for base in base_seeds:
            for sample_seed in range(base, base + n_per_base):
                state = new_game(sample_seed, character)
                start_combat(state, [Cultist(state.rng.hp_rng)])
                _damage, _sequence, audit = _exhaustive_best_sequence(
                    state, return_audit=True)
                audits.append(audit)
        rows[character] = {
            "states": len(audits),
            "exact_states": sum(a["exact"] for a in audits),
            "bound_hits": sum(not a["exact"] for a in audits),
            "max_nodes_expanded": max(a["nodes_expanded"] for a in audits),
            "mean_nodes_expanded": round(
                sum(a["nodes_expanded"] for a in audits) / len(audits), 3),
            "node_budget": audits[0]["node_budget"],
        }
    return {
        "scope": "current-code replay of paper seed schedule; not historical-commit proof",
        "by_character": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-dir", type=Path, default=ROOT / "results")
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--include-files", action="store_true",
                        help="Include the per-artifact inventory, not just counts.")
    args = parser.parse_args()
    report = {
        "synergy_lookup": synergy_lookup_audit(),
        "artifacts": artifact_audit(args.results_dir, include_files=args.include_files),
        "instrument": instrument_inventory(),
        "turn_oracle": turn_oracle_audit(),
    }
    print(json.dumps(report, indent=None if args.compact else 2, sort_keys=True))


if __name__ == "__main__":
    main()
