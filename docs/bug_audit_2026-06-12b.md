# Bug Audit — 2026-06-12 (5th audit, "one last pass" before the GPU phase)

Scope: (1) line-by-line review of the two most recent code commits — `0de519a`
(4th-audit fix batch) and `a36b42d` (`--provider local` / `LocalLLM`); (2) a fresh
full read of the engine core (combat.py, powers.py, cards.py, state.py), the
harness (benchmark.py, run_benchmark.py, prompt_builder.py, visualize.py keys),
the run layer (run_loop.py, nodes.py, events_pool.py, map_gen.py, rewards.py),
and relics/enemies/potions (relics.py, relics_full.py, enemies.py,
enemies_act2.py spot-checks, potions.py).

Verified CLEAN from the recent batches (no action): Sentinel exhaust-energy hook
(fires for Corruption/Sever Soul/Fiend Fire, identity-safe), Pride
`end_of_turn_effect` IS wired (powers.py TURN_END loop over hand), Brutality
per-combat reset both ends, Berserk unconditional energy, Awakened One
`_intangible_fresh` ordering (execute → tick → select_move), `--run-tag` flows
to JSON + `save_all` charts, LocalLLM request shape / 429-vs-error split,
`_safe_int` float-strings, negative-target fallback, parse-fail ⇒ legal=False,
synergy fixture #16 (Twin Strike offer is consistent), relic rarity pools dedup,
visualize.py metric keys match `summary()` keys. Baseline: 118/118 tests green.

Found: **2 high, 5 medium, ~9 low** — none invalidate the synergy n=20 data
(no synergy-path bug; prompts unchanged). Turn/combat/run had no valid data to
lose (re-baseline already pending).

---

## HIGH

### H1 — A single non-429 server error mid-run loses ALL completed work (GPU-phase killer)
`LocalLLM.complete` deliberately raises `RuntimeError` on any non-429 HTTP error
(good: surfaces misconfiguration). `OpenRouterLLM` likewise re-raises non-429/402.
But the partial-save machinery only catches `RateLimitExhausted`
(`run_run_eval` loop, `run_all`). On the GPU box, vLLM returns **HTTP 400 when a
prompt exceeds the model context window** — run-level prompts grow with deck/
floor state, so one oversized prompt hundreds of calls into a run-level pass
raises RuntimeError → the whole process dies → every completed run/dimension of
that invocation is discarded. Exactly the failure mode partial-save was built for.
**Fix:** in `run_run_eval`, catch `Exception` (not just `RateLimitExhausted`) per
run-seed: print the error, `break`, keep completed scores. In `run_all`, widen the
existing `except RateLimitExhausted` to also catch other exceptions from an
evaluator dimension: print + keep partial results (the JSON merge in
run_benchmark.py then preserves prior dimensions as today). Do NOT retry; do NOT
swallow silently — the error text must be printed loudly. Regression test: an LLM
stub whose `complete` raises RuntimeError on call N → run_run_eval returns N-1
scores instead of propagating.

### H2 — `complete_json` fallback is O(n²)-ish: minutes of CPU per parse failure on long reasoning outputs
The brace-scan fallback tries `json.loads(text[m.start():end])` for **every end
position from len(text) downward, for every `{` in the text**. A truncated 32k-char
`<think>` response (no closing tag → nothing stripped → no valid JSON anywhere)
runs ~(#braces × len) parse attempts, each O(len). This is precisely the qwen3
truncation cascade expected in the GPU phase — every parse failure would burn
minutes of CPU on top of the lost call.
**Fix:** replace the inner reverse scan with a single
`json.JSONDecoder().raw_decode(text[m.start():])` per `{` (raw_decode parses a
prefix and ignores trailing junk). Identical accepted-input semantics for valid
embedded objects, linear-ish cost. Keep behavior: first decodable object wins;
on total failure return the same `{"error": "parse_failure", "raw": raw}`.
Regression: multi-object string still returns the FIRST valid object
(existing tests cover this — must stay green), plus a perf-shaped sanity test
(e.g. 50k chars of `{` noise parses/fails in well under a few seconds).

## MEDIUM

### M1 — Doubt and Shame curses are complete no-ops
`Doubt.end_of_turn_effect` / `Shame.end_of_turn_effect` apply WEAK/FRAIL 1 during
the TURN_END emit — that's the player phase, so `_apply_power` does not mark
`just_applied` (condition requires `combat.enemy_phase`). `_tick_player_debuffs`
then runs at end of the SAME round and deletes the single stack before it covers
anything. In real StS, Doubt's Weak is justApplied and affects your next turn.
**Fix:** make debuffs applied during the end-of-turn window skip their first tick.
Cleanest: a `combat` flag (e.g. `_turn_end_window`) set around the TURN_END emit
in `end_player_turn`, and `_apply_power` marks `just_applied` when EITHER
`enemy_phase` or that flag is set. (Do not blanket-mark player-turn applications —
Berserk's self-Vulnerable correctly ticks at end of the round it was played.)
Regression: end a turn with Doubt in hand → WEAK present and active during the
player's NEXT turn, gone the round after.

### M2 — Blue Candle + Pride: double exhaust-pile entry + double CARD_EXHAUST
`BlueCandle.register`'s CARD_PLAY hook (fires BEFORE `card.play()`) exhausts any
played curse. Pride is the one curse that is naturally playable and ALSO
self-exhausts in `Pride.play` → the same object lands in `exhaust_pile` twice and
CARD_EXHAUST is emitted twice (Feel No Pain / Dark Embrace / Sentinel hooks double-
fire). This is the same double-exhaust class fixed in audit 3.
**Fix:** gate the hook on `card.unplayable` (Blue Candle's mechanic exists to make
*unplayable* curses playable; Pride manages itself), or identity-check
`exhaust_pile` before appending. Prefer the `unplayable` gate (also stops the 1-HP
loss double-dipping on Pride). Regression: play Pride with Blue Candle owned →
exactly one exhaust entry, one CARD_EXHAUST.

### M3 — Dead Branch adds curses and statuses to hand
The CARD_EXHAUST hook picks uniformly from the FULL card-class registry
(IRONCLAD_CARD_CLASSES / SILENT_CARD_CLASSES), which includes Burn, Dazed, Wound,
Void, Pride, Pain, every curse. Real Dead Branch adds a random *character* card —
never curses/statuses. As written it actively poisons the deck it's supposed to
reward, and exhaust-heavy decks (its synergy partner) trigger it constantly.
**Fix:** filter candidates to `CardType.ATTACK/SKILL/POWER` (exclude
CURSE/STATUS; also exclude the basic Strike/Defend ids for fidelity). Keep the
misc_rng draw pattern (index into the filtered, deterministic list).
Regression: 50 triggers → no curse/status ever added.

### M4 — Tiny House grants a permanent +1 energy per turn it should not have
Real Tiny House (shop relic): potion, 50 gold, +5 max HP, a card, upgrade a card —
**no energy**. Ours adds `energy_per_turn += 1`, i.e. a second Busted-Crown-grade
effect on a shop relic; any run that buys it plays the rest of the run at 4 energy.
**Fix:** delete the energy line; optionally add the missing "upgrade 1 random
card" (misc_rng over un-upgraded, non-curse/status deck cards) to complete the
real effect. Update/extend the relic test if one asserts current behavior.

### M5 — Nemesis intangible off-by-one vs its own spec
Docstring/comment says "stay Intangible through the first 3 turns", but the
re-apply runs only while `_phase < 3` AFTER increment → phases 1,2. Sequence:
intangible covers player turns 1–2; on turn 3 the player already attacks a
non-intangible Nemesis. **Fix:** make code match the documented simplification
(intangible during turns 1–3, droppable from turn 4): re-apply for
`self._phase <= 3` and pop at phase 4 (adjust the pattern indexing accordingly),
or simply change the condition to `< 4` with the pop in the else. Regression:
turn-3 attack against Nemesis is capped at 1; turn-4 is not.

## LOW

### L1 — The Abacus / Tough Bandages / Anchor add block without BLOCK_GAINED
Inconsistent with 4th-audit fix E9 (Orichalcum/Captain's Wheel/Cloak Clasp now
emit so Juggernaut fires). Same one-line pattern: `block += n` + emit with
`amount=n` (flat relic block, no Dex/Frail — matches E9 comment style).

### L2 — Frozen Egg / Molten Egg / Toxic Egg are dead relics (write-only flags)
`_frozen_egg`/`_molten_egg`/`_toxic_egg` are set in register() and never read.
**Fix:** in `generate_card_reward`, after `make_card_for`, upgrade the offer when
its type matches an owned egg (POWER↔Frozen, ATTACK↔Molten, SKILL↔Toxic — real
StS effect is "whenever you ADD a card", apply at reward-generation time like the
existing rare-upgrade roll; keep the RNG call order unchanged ahead of it).

### L3 — Juzu Bracelet is a dead relic (write-only `_juzu`)
Real effect: "? rooms can no longer be combats". Our EVENT nodes never spawn
combats (fight branches are text stubs), so the effect is structurally moot.
**Action:** remove the dead flag write and DOCUMENT in the class docstring that
Juzu is a no-op by design in this sim (event combats unimplemented) — same
documented-design treatment as Mummified Hand. Do not implement speculative logic.

### L4 — Mark of Pain puts both Wounds on TOP of the draw pile
`draw_pile.append(Wound()) ×2` after the shuffle = the top 2 draws of EVERY
combat are Wounds (real StS shuffles them in). **Fix:** insert each at a
`shuffle_rng`-rolled index into the draw pile.

### L5 — Exhume can retrieve another Exhume
Real Exhume cannot return Exhume. **Fix:** pop the most recent non-Exhume entry
(identity-safe scan from the end); no-op if only Exhumes are exhausted.

### L6 — Limit Break writes a `STRENGTH: 0` powers entry at 0 Strength
`powers[STRENGTH] = strength * 2` materializes a zero entry when the player had
none (prompts filter zero values now, but the key lingers in state and in any
`PowerId.STRENGTH in powers` checks). **Fix:** skip the write when result is 0
(or delete the key when 0), matching how Flex cleans up.

### L7 — `_act_transition` counts an llm_call even when no LLM call happens
The counter increments before `_llm_boss_relic_choice`, which short-circuits
(returns 0, no API call) when ≤1 relic is offered. Move the increment inside the
`len(relic_ids) > 1` condition (mirror the helper's own guard) or increment in
the helper itself next to the actual `complete_json` call.

### L8 — Player REGENERATE never ticks (latent)
`RegenPotion` grants `PowerId.REGENERATE` on the player; only the ENEMY tick path
reads it. Unreachable today (potions are undrinkable by design) but a landmine if
potion-drinking is ever added. **Action:** add a player-side heal in the TURN_END
hook (`_heal_player(gs, stacks)`) OR a one-line "dead by design until potions are
drinkable" comment on RegenPotion. Prefer the comment (no behavior change, no new
RNG/heal interactions to re-baseline).

### L9 — Power Potion / Skill Potion hardcode `_IRONCLAD_POOL`
A Silent player drinking them would get Ironclad cards. Unreachable today
(undrinkable by design). **Fix:** switch to `card_pool_for(state)` — one line each,
keeps the latent path correct.

### L10 — Watcher relics still present in boss pool definitions (defense-in-depth)
`Holy Water` sits in `BOSS_RELIC_POOL` (strings) and `_RARITY_POOLS["boss"]`;
`VioletLotus` in `_RARITY_POOLS["boss"]`; both are blocked at draw time by
`relic_allowed` (_WATCHER_ONLY), so unreachable — but Violet Lotus's stand-in
implementation ("+1 energy per 0-cost card played") would be an infinite-energy
fountain for Shiv decks if the gate ever regressed, and Holy Water's stand-in
(3 potions) is not its real effect. **Fix:** remove both from `BOSS_RELIC_POOL`
and `_RARITY_POOLS["boss"]` (Nuclear Battery precedent: removed outright), keep
the classes + `relic_allowed` entries as belt-and-suspenders.

---

## NOT bugs / documented design (checked, leave alone)
- Master-deck `list.remove()` equality removals (nodes.py, events_pool.py,
  relics_full.py): removing an identical twin from the out-of-combat deck is
  behaviorally identical (no per-object combat state outside combat).
- `_llm_combat` leaves `state.combat` set on a LOSS — the run ends immediately;
  end_combat-on-loss would wrongly fire COMBAT_END heals.
- Wild Strike / Reckless Charge `insert(0, …)` = BOTTOM of draw pile (pop() is
  top) — acceptable stand-in for "shuffle in"; do not change (seed stability).
- Headbutt takes top of discard (real: player's choice) — greedy stand-in.
- Transient flees by `hp = 0` → counts as a kill with rewards (minor fidelity,
  matches "win" semantics used everywhere; leave).
- `effective_move_damage` ignores player Vulnerable in the intent display —
  matches real StS intent display; Vulnerable applies at damage time.
- DreamCatcher offer not cleared on smith/toke path in run_loop — overwritten on
  the next REST_SITE_ENTER before any read; harmless.
- `_choose_active_cols(rng, floor, num_floors)` ignores its floor args —
  cosmetic only.
- Membership Card doesn't discount potions; `_relic_price` flat 143 — known
  placeholder economy.
- Cultist never appends move_history — nothing reads it.
- Catalyst/Malaise mutate enemy powers directly (no Artifact interaction) —
  consistent with Disarm; Strength-down isn't in the Artifact debuff set by
  project convention.

## Fix-batch requirements (for the implementing agent)
1. Implement H1–H2, M1–M5, L1–L10 (L3/L8 may be comment/doc-only as specced).
2. Add regression tests per item where behavior changes (target: every
   HIGH/MEDIUM gets at least one test; L-items where cheap).
3. All existing 118 tests must stay green (PYTHONIOENCODING=utf-8 on Windows).
4. Mock pipeline must stay green: both characters × both formats
   (`python run_benchmark.py --provider mock --model mock --format structured|raw
   [--character silent] --seed 42`).
5. Record per-item implementation notes in this file (append an
   "Implementation notes" section).
6. Data impact: NONE of these touch the synergy prompt bytes or scoring path —
   synergy n=20 stays valid. Turn/combat/run were already pending re-baseline.

---

## Implementation notes (2026-06-12)

All 17 items implemented. Tests: 118 → 133 green (combat 48→56, benchmark 40→44,
run 30→33). Mock pipeline green ×4 (both characters × both formats). No existing
test needed updating — no item changed behavior an existing test asserted.

- **H1** (`benchmark.py` `run_run_eval` / `run_all`): per-run `except` now also
  catches generic `Exception` (after `RateLimitExhausted`, re-raising
  `KeyboardInterrupt`): prints `[error] run-level aborted ... keeping partial
  results`, breaks, keeps completed scores. `run_all` gained the matching
  `except Exception` block (loud `[error]` print, stops remaining dimensions,
  keeps partial). Tests: `test_run_eval_keeps_partial_on_server_error`,
  `test_run_all_keeps_partial_on_dimension_error` (test_benchmark.py).
- **H2** (`benchmark.py` `LLMInterface.complete_json`): reverse end-scan replaced
  with `json.JSONDecoder().raw_decode(text[m.start():])` per `{`. Same first-
  object-wins semantics; linear-ish. Test:
  `test_complete_json_first_object_and_fast_on_garbage` (50k `{` fails in <0.2s).
- **M1** (`state.py`, `combat.py`, `cards.py`): added `CombatState.turn_end_window`,
  set around the TURN_END emit in `end_player_turn` (try/finally). `_apply_power`
  marks `just_applied` when player-targeted AND (`enemy_phase` OR
  `turn_end_window`). Doubt/Shame's Weak/Frail now survive the round it was
  applied. Test: `test_doubt_curse_weak_covers_next_turn` (test_combat.py).
- **M2** (`relics_full.py` `BlueCandle`): CARD_PLAY hook gated on
  `getattr(card, 'unplayable', False)` — Pride (playable, self-exhausting) no
  longer double-exhausts / double-loses 1 HP. Test:
  `test_blue_candle_pride_single_exhaust`.
- **M3** (`relics.py` `DeadBranch`): candidates filtered to ATTACK/SKILL/POWER
  and rarity != BASIC (no curses/statuses/basics). Test:
  `test_dead_branch_adds_no_curse_or_status`.
- **M4** (`relics_full.py` `TinyHouse`): deleted the `energy_per_turn += 1` line;
  added "upgrade 1 random un-upgraded non-curse/status deck card" via misc_rng.
  Test: `test_tiny_house_no_energy_upgrades_card` (test_run.py).
- **M5** (`enemies_act2.py` `Nemesis.select_move`): re-applies Intangible on
  phases 1,2,3 (always in the `if _phase<3` branch) and pops it in the else
  (phase 4 selection). Turn-3 attack now capped at 1, turn-4 full. Test:
  `test_nemesis_intangible_through_turn_three`.
- **L1** (`relics.py` `Anchor`; `relics_full.py` `TheAbacus`, `ToughBandages`):
  each flat-block grant now emits `BLOCK_GAINED` (amount=n) like E9. Test:
  `test_anchor_block_emits_block_gained`.
- **L2** (`rewards.py` `generate_card_reward`): after `make_card_for`, an owned
  egg upgrades a matching-type offer IN PLACE via `card.upgrade()` (no RNG → call
  order preserved). Tests: `test_eggs_upgrade_matching_reward_cards`,
  `test_eggs_preserve_reward_rng_order` (test_run.py).
- **L3** (`relics_full.py` `JuzuBracelet`): dead `_juzu` write removed; docstring
  documents the by-design no-op (event combats unimplemented). Comment-only.
- **L4** (`relics.py` `MarkOfPain`): each Wound now inserted at a
  `shuffle_rng`-rolled index instead of appended (top). Test:
  `test_mark_of_pain_shuffles_wounds`.
- **L5** (`cards.py` `Exhume.play`): pops the most recent non-Exhume exhaust
  entry (identity scan from the end); no-op if only Exhumes. Test:
  `test_exhume_cannot_return_exhume`.
- **L6** (`cards.py` `LimitBreak.play`): skips/deletes the STRENGTH key when the
  doubled result is 0 (Flex-style cleanup). Test:
  `test_limit_break_no_zero_strength_key`.
- **L7** (`benchmark.py` `_act_transition`): the `llm_calls` increment is now
  gated on `len(relic_ids) > 1`, matching the helper's short-circuit. Test:
  `test_act_transition_counts_llm_call_only_when_made`.
- **L8** (`potions.py` `RegenPotion`): added the "dead by design until potions
  are drinkable" comment per spec preference (no behavior change). Comment-only.
- **L9** (`potions.py` `PowerPotion`, `SkillPotion`): hardcoded `_IRONCLAD_POOL`
  replaced with `card_pool_for(state)` + `make_card_for(character, …)`.
- **L10** (`relics_full.py`): Holy Water removed from `BOSS_RELIC_POOL` and the
  `"boss"` rarity pool; Violet Lotus removed from the `"boss"` pool. Classes +
  `_WATCHER_ONLY` entries kept (belt-and-suspenders). Covered by the existing
  `test_no_duplicate_relics_in_pools` / pool-gating tests.

No spec deviations.
