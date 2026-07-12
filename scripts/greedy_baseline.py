#!/usr/bin/env python
"""Measure the scripted greedy run-level baseline (the run-level "floor" anchor).

WHY THIS EXISTS
---------------
The horizon-collapse curve in ``slay_bench/visualize.py`` normalizes the run-level
dimension against a greedy Act-1 survival floor. That floor used to be a single
hard-coded ``GREEDY_PROGRESS = 0.78`` derived from an *unreproduced* session note
("greedy bot survives Act 1 ~1/100, avg ~12.5 floors") — no artifact, no seeds,
no n, and the same Ironclad-derived value was applied to BOTH characters even
though Silent's greedy Act 1 is documented as harsher. This script measures the
anchor empirically, per character, on the SAME seeds the LLM matrix used. It is
FREE: the greedy policy is deterministic engine code, zero API calls.

PROTOCOL PARITY (the whole point)
---------------------------------
The greedy baseline MUST replicate the LLM run-level protocol EXACTLY, replacing
only the LLM *decisions* with the scripted greedy policy. We therefore reuse
``RunEvaluator.evaluate`` / ``_play_act`` UNCHANGED (identical map traversal,
reward/offer counts, elite drops, potion drops, event auto-pick-0, greedy shop,
rest handling, act-transition bookkeeping) and only override the four decision
hooks in a subclass:

    _llm_combat        -> greedy card play (mirrors run_loop._resolve_combat's AI)
    _llm_card_choice   -> first non-curse offer (the documented greedy pick)
    _llm_boss_relic_choice -> index 0 (greedy default; single-act runs never hit it)
    _llm_rest_choice / _llm_path_choice -> never called (matrix ran llm_routing=False;
                                            REST + path pick=0 are the non-LLM defaults)

The combat loop is capped at ``self.max_combat_turns`` (50) exactly as the LLM
run's ``_llm_combat`` is — NOT run_loop's standalone 100 — because we are cloning
the *LLM run protocol*, not run_loop's standalone act runner.

SEEDS
-----
The matrix ran run-level with ``--n-run 20 --seeds 42 1042 2042 3042 4042``.
Per ``BenchmarkHarness.run_all``, the run-dimension per-sample seeds for base B are
``range(B + 300, B + 300 + n_run)`` (derived from code, not memory). Aggregation
(``run_benchmark._aggregate_summaries``) is: average the 20 runs within each base
seed, then take mean +/- std of those 5 per-base averages. We reproduce that exactly.

USAGE
-----
    .venv\\Scripts\\python.exe scripts/greedy_baseline.py

Writes results/greedy_baseline_ironclad.json and results/greedy_baseline_silent.json.
"""
from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path
from typing import List, Optional

# Make the package importable when run as a bare script.
_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from slay_bench import new_game                       # noqa: E402
from slay_bench.benchmark import RunEvaluator, RunScore  # noqa: E402

# Matches the matrix run-level config exactly.
BASE_SEEDS = [42, 1042, 2042, 3042, 4042]
N_RUN = 20
SEED_RUN_OFFSET = 300  # BenchmarkHarness.run_all: run_seeds = range(seed+300, seed+300+n_run)
N_ACTS = 1
CHARACTERS = ["ironclad", "silent"]


class GreedyRunEvaluator(RunEvaluator):
    """RunEvaluator with every LLM decision replaced by the scripted greedy policy.

    Reuses evaluate()/_play_act() from the base class untouched so the run protocol
    is byte-identical to the LLM matrix run; only the decision content changes.
    """

    # ----- combat: greedy card play (mirror of run_loop._resolve_combat's AI) -----
    def _llm_combat(self, state, counters: Optional[dict] = None):
        from slay_bench.combat import (
            play_card, end_player_turn, is_combat_over, end_combat,
        )
        counters = counters if counters is not None else {}
        turns = 0
        for _ in range(self.max_combat_turns):
            outcome = is_combat_over(state)
            if outcome:
                won = outcome == "win"
                if won:
                    end_combat(state)
                return won, turns
            turns += 1
            # Play every playable card, one at a time, until none can be played.
            played = True
            while played:
                played = False
                for card in list(state.combat.hand):
                    target = next((e for e in state.combat.enemies if e.hp > 0), None)
                    if target and card.can_play(state):
                        play_card(state, card, target)
                        played = True
                        if is_combat_over(state):
                            break
                        break
                if is_combat_over(state):
                    break
            if is_combat_over(state):
                continue  # loop top handles the win/lose bookkeeping
            end_player_turn(state)
        # timeout — clean up stale combat like the LLM path does
        if state.combat is not None:
            end_combat(state)
        return False, turns

    # ----- card reward: first non-curse offer (documented greedy pick) -----
    def _llm_card_choice(self, state, offers: List):
        from slay_bench.enums import CardType
        if not offers:
            return None
        for c in offers:
            if getattr(c, "type", None) != CardType.CURSE:
                return c
        return None

    # ----- boss relic: greedy default index 0 (unused for single-act runs) -----
    def _llm_boss_relic_choice(self, state, relic_ids: List[str]) -> int:
        return 0


def run_character(character: str) -> dict:
    """Run the greedy baseline for one character across all base seeds.

    Returns a fully aggregated dict (per-sample + per-base + overall mean/std).
    """
    evaluator = GreedyRunEvaluator(
        llm=None,                       # no LLM is ever called on the greedy path
        prompt_format="structured",     # irrelevant: all decision hooks overridden
        temperature=0.0,
        llm_routing=False,              # matches the matrix (path pick=0, rest=REST)
        character=character,
    )

    per_base = []          # one entry per base seed
    all_samples = []       # flat list of every run (for reference)
    for base in BASE_SEEDS:
        run_seeds = list(range(base + SEED_RUN_OFFSET,
                               base + SEED_RUN_OFFSET + N_RUN))
        base_samples = []
        for seed in run_seeds:
            state = new_game(seed, character)
            score: RunScore = evaluator.evaluate(state, n_acts=N_ACTS)
            sample = {
                "seed": seed,
                "floors_reached": score.floors_reached,
                "total_floors": score.total_floors,
                "progress": score.progress,
                "survived": score.survived,
                "final_hp": score.final_hp,
                "max_hp": score.max_hp,
            }
            base_samples.append(sample)
            all_samples.append(sample)

        # Per-base averages == what run_all's per-seed summary would report.
        floors = [s["floors_reached"] for s in base_samples]
        progress = [s["progress"] for s in base_samples]
        survived = [1.0 if s["survived"] else 0.0 for s in base_samples]
        per_base.append({
            "base_seed": base,
            "run_seeds": [run_seeds[0], run_seeds[-1]],
            "n_run": N_RUN,
            "avg_floors_reached": round(statistics.mean(floors), 4),
            "avg_progress": round(statistics.mean(progress), 4),
            "survival_rate": round(statistics.mean(survived), 4),
            "samples": base_samples,
        })

    def _mean_std(values):
        return (round(statistics.mean(values), 4),
                round(statistics.stdev(values), 4) if len(values) > 1 else 0.0)

    floors_m, floors_s = _mean_std([b["avg_floors_reached"] for b in per_base])
    prog_m, prog_s = _mean_std([b["avg_progress"] for b in per_base])
    surv_m, surv_s = _mean_std([b["survival_rate"] for b in per_base])

    return {
        "character": character,
        "n_acts": N_ACTS,
        "base_seeds": BASE_SEEDS,
        "n_run_per_base": N_RUN,
        "seed_scheme": "range(base+300, base+300+20)  (matches BenchmarkHarness.run_all)",
        "policy": "scripted greedy: play-all-playable combat, first-non-curse card pick, "
                  "path pick=0, rest=REST, boss relic=0 (llm_routing=False)",
        # Overall = mean +/- std across the 5 per-base averages (matches
        # run_benchmark._aggregate_summaries).
        "avg_floors_reached_mean": floors_m,
        "avg_floors_reached_std": floors_s,
        "avg_progress_mean": prog_m,
        "avg_progress_std": prog_s,
        "survival_rate_mean": surv_m,
        "survival_rate_std": surv_s,
        "per_base": per_base,
        "all_samples": all_samples,
    }


def main() -> None:
    results_dir = _REPO / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    for character in CHARACTERS:
        print(f"── greedy baseline: {character} "
              f"(bases {BASE_SEEDS}, n_run={N_RUN}) ──", flush=True)
        agg = run_character(character)
        out = results_dir / f"greedy_baseline_{character}.json"
        out.write_text(json.dumps(agg, indent=2), encoding="utf-8")
        print(f"  floors  = {agg['avg_floors_reached_mean']} "
              f"± {agg['avg_floors_reached_std']}")
        print(f"  progress= {agg['avg_progress_mean']} "
              f"± {agg['avg_progress_std']}")
        print(f"  survival= {agg['survival_rate_mean']} "
              f"± {agg['survival_rate_std']}")
        print(f"  wrote {out}", flush=True)


if __name__ == "__main__":
    main()
