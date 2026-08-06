#!/usr/bin/env python
"""Degenerate-strategy baseline for the TURN-LEVEL dimension (instrument audit).

WHY THIS EXISTS
---------------
On 2026-08-07 the Sharanga qwen3-32b matrix returned ``avg_damage_ratio =
1.000 +/- 0.000`` for Silent/structured -- 100/100 samples exactly at the
exhaustive oracle, with zero variance across five seeds. Per the standing
project rule (decision_log; "the instrument lies before the subject does"), a
measurement sitting on a boundary with std ~ 0 is a HARNESS BUG until a
per-sample audit clears it. The specific worry: if most legal play sequences
happen to tie at the optimum, then ``damage_ratio = 1.0`` means only "played
legally", the dimension cannot discriminate, and the number is an instrument
ceiling rather than a planning result.

WHAT IT MEASURES
----------------
Rebuilds every turn-eval state the matrix used (``new_game(seed, character)`` +
``start_combat`` vs a Cultist, exactly as ``BenchmarkHarness.run_turn_eval``
does) and, for each state, enumerates the FULL space of maximal legal play
sequences. Zero API calls -- the oracle and the engine are local.

    frac_opt     fraction of ALL legal sequences that reach the oracle optimum.
                 ~1.0 => saturated metric (any legal play scores 1.0).
    saturated    count of states where EVERY legal sequence is optimal.
    rand_mean    mean damage_ratio of a uniformly random legal sequence.
    naive_lr     damage_ratio of "walk the hand left-to-right, play whatever is
                 legal" -- a zero-planning policy.

READING THE OUTPUT
------------------
If ``saturated`` is ~all states, the turn metric cannot discriminate for that
character and any 1.000 must be reported as a ceiling artifact. If the naive and
random baselines sit well below 1.0, the dimension discriminates and a 1.000 is
a real result -- which is what the 2026-08-07 run found (Silent: 0/100 saturated,
random 0.145, naive 0.510; Ironclad: 0/100, random 0.231, naive 0.614).

USAGE
-----
    .venv/Scripts/python.exe scripts/turn_saturation_check.py

Deterministic: same seeds -> same numbers, no API, no GPU.
"""
import copy
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from slay_bench import new_game, start_combat                       # noqa: E402
from slay_bench.enemies import Cultist                              # noqa: E402
from slay_bench.benchmark import _exhaustive_best_sequence          # noqa: E402
from slay_bench.combat import play_card, is_combat_over             # noqa: E402

# The matrix's turn seeds: run_all uses range(base, base + n_turn) per base seed.
BASES = [42, 1042, 2042, 3042, 4042]
N_TURN = 20
# Node budget per state. Turn-1 hands are energy-bounded, so the real search is
# far smaller than this; the cap only guards a pathological all-zero-cost hand.
DFS_BUDGET = 4000


def all_legal_sequences(snapshot, cap=DFS_BUDGET):
    """Every maximal legal play sequence -> list of (damage, sequence).

    Mirrors _exhaustive_best_sequence's pruning contract: identical cards (same
    name/upgrade/cost) are expanded once per node, and membership is by identity
    (never __eq__ -- Card is a dataclass whose twins compare equal).
    """
    base = copy.deepcopy(snapshot)
    initial_hp = sum(e.hp for e in base.combat.enemies if e.hp > 0)
    hand0 = list(base.combat.hand)
    out = []
    budget = [cap]

    def dfs(s, seq, used):
        if budget[0] <= 0:
            return
        budget[0] -= 1
        dmg = initial_hp - sum(e.hp for e in s.combat.enemies if e.hp > 0)
        extended = False
        if not is_combat_over(s):
            seen = set()
            for i, card in enumerate(hand0):
                if i in used:
                    continue
                key = (card.name, getattr(card, "upgraded", False), card.cost)
                if key in seen:
                    continue
                if not any(h is card for h in s.combat.hand):
                    continue
                if not card.can_play(s):
                    continue
                seen.add(key)
                extended = True
                s2 = copy.deepcopy(s)
                c2 = next(h for h in s2.combat.hand
                          if h.name == card.name
                          and getattr(h, "upgraded", False) == getattr(card, "upgraded", False))
                tgt = next((e for e in s2.combat.enemies if e.hp > 0), None)
                play_card(s2, c2, tgt)
                dfs(s2, seq + [i], used | {i})
        if not extended:
            out.append((dmg, list(seq)))

    dfs(base, [], set())
    return out


def naive_left_to_right(snapshot):
    """Zero-planning policy: walk the hand in order, play whatever is legal."""
    s = copy.deepcopy(snapshot)
    initial_hp = sum(e.hp for e in s.combat.enemies if e.hp > 0)
    for card in list(s.combat.hand):
        if not any(h is card for h in s.combat.hand):
            continue
        if not card.can_play(s):
            continue
        tgt = next((e for e in s.combat.enemies if e.hp > 0), None)
        play_card(s, card, tgt)
        if is_combat_over(s):
            break
    return initial_hp - sum(e.hp for e in s.combat.enemies if e.hp > 0)


def main():
    for character in ("ironclad", "silent"):
        fracs, naives, rands, opts = [], [], [], []
        saturated = 0
        seeds = [b + k for b in BASES for k in range(N_TURN)]
        for seed in seeds:
            state = new_game(seed, character)
            start_combat(state, [Cultist(state.rng.hp_rng)])
            opt, _ = _exhaustive_best_sequence(state)
            opts.append(opt)
            if opt <= 0:
                continue
            dmgs = [d for d, _ in all_legal_sequences(state)]
            frac = sum(1 for d in dmgs if d >= opt) / len(dmgs)
            fracs.append(frac)
            if frac >= 0.999:
                saturated += 1
            rands.append(statistics.mean(dmgs) / opt)
            naives.append(naive_left_to_right(state) / opt)

        print("=== {} (n={} states) ===".format(character, len(fracs)))
        print("  oracle optimal damage        mean={:.2f}  min={}  max={}".format(
            statistics.mean(opts), min(opts), max(opts)))
        print("  frac of legal seqs optimal   mean={:.3f}".format(statistics.mean(fracs)))
        print("  states where EVERY legal seq is optimal: {}/{}".format(
            saturated, len(fracs)))
        print("  random-legal-sequence score  mean={:.3f}".format(statistics.mean(rands)))
        print("  naive left-to-right score    mean={:.3f}".format(statistics.mean(naives)))
        print()

    print("If 'states where EVERY legal seq is optimal' is ~all states, the turn")
    print("metric is saturated for that character and a 1.000 is an instrument")
    print("ceiling, not a planning result. If the naive/random baselines sit well")
    print("below 1.0, the dimension discriminates and the score stands.")


if __name__ == "__main__":
    main()
