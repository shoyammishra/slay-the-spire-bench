# Design

## Architecture Overview

```
run_benchmark.py          CLI entry point (--character --acts --temperature --seeds --llm-routing --only)
slay_bench/
  benchmark.py            4-dimension harness + LLM interface (character/temperature/n_acts aware)
  prompt_builder.py       GameState → prompt (structured JSON or raw English); system_prompt(kind, character)
  combat.py               Turn engine: draw, play, enemy attack, block; powers reset per combat
  run_loop.py             Full act simulation, floor-by-floor (15 floors + boss per act)
  map_gen.py              Map generation, node types, path traversal
  cards.py                All Ironclad cards; make_card_for(character, name) dispatcher
  cards_silent.py         All Silent cards (~73), SILENT_POOL, SILENT_SYNERGY_FIXTURES
  enemies.py              Act 1 enemies
  enemies_act2.py         Act 2/3 enemies
  powers.py               Power hooks incl. Silent powers (Noxious Fumes, Wraith Form, …)
  relics.py / relics_full.py  Relic effects via EventBus; on_pickup/register lifecycle split
  rewards.py              card_pool_for(state) — character-aware card pools and rewards
  nodes.py                Non-combat floor nodes (shop, rest, events, relic pickup)
  state.py                GameState (character field) + CombatState
  rng.py                  Java-compatible LCG, 9 independent seeded streams
  visualize.py            PNG charts + ASCII reports
```

## Key Invariants

- **Energy**: deducted only in `play_card()` (combat.py). Cards never deduct energy themselves.
- **Determinism**: same seed → identical map, enemies, draws, rewards every run.
- **EventBus**: cleared at the top of `start_combat` to prevent listener stacking across combats.
- **Relic lifecycle split**: `Relic.on_pickup(state)` = one-time effects at acquisition (max HP,
  energy/turn, deck mutations); `Relic.register(state)` = event subscriptions only, re-called at
  every combat start (bus is cleared first). Only idempotent subscriptions belong in `register`.
- **Powers reset per combat**: `start_combat()` sets `state.player.powers = {}`. Relic-granted
  powers (Vajra, Shuriken, …) re-apply via their COMBAT_START hooks.
- **Poison bypasses block**: poison tick is `enemy.hp -= amt` directly (matches real StS).
- **Player debuffs tick at end of ROUND** (after enemy turns), not end of player turn — so
  Intangible/Vulnerable cover the enemy attacks of the round they're active. Debuffs enemies
  apply during their phase are flagged `just_applied` and skip their first tick (StS rule).
- **Thorns retaliates against attack damage only** — `_apply_damage_to_enemy(from_attack=True)`
  is set solely by `_deal_damage`; Combust/Juggernaut/relic damage doesn't trigger thorns.
- **`Event.SHUFFLE`** fires when the discard pile is reshuffled into the draw pile
  (Sundial, The Abacus key on it).
- **Character-aware factory**: `new_game(seed, character)` builds the right starter deck + relic;
  `make_card_for` / `card_pool_for` / `system_prompt` all dispatch on character.
- **Illegal plays**: if any card in a sequence is illegal, `damage_ratio = 0`.
- **HP fraction**: averaged over survivors only; deaths excluded (contribute to survival_rate as 0).
- **avg_progress**: floors_reached / total_floors, clamped to 1.0. Gives partial credit on death.
- **Multi-act**: `RunEvaluator.evaluate(state, n_acts)` plays acts 1→n in sequence;
  `_act_transition()` does a full heal + boss relic pick (LLM or greedy) between acts.
- **Pile membership is by IDENTITY (2026-06-11)**: `Card` is a dataclass → field-based
  `__eq__`; `list.remove`/`in` on combat piles match identical twins. Use
  `cards._remove_identical()` / `any(c is card for …)` for any specific card object.
  `play_card` raises if the exact object isn't in hand; the turn-eval simulator
  additionally rejects repeated hand indices (anti-replay).
- **Player-damage modes (2026-06-11, 3rd audit)**: `_damage_player` — default = attack
  damage (block/Intangible/Vulnerable/Torii); `from_attack=False` = non-attack damage
  (Thorns, Burn/Decay: blockable, Intangible-capped, NO Vulnerable amp, no Torii);
  `is_hp_loss=True` = HP loss (Offering/Combust/player poison/curses: bypasses
  block/Intangible/Vulnerable). Tungsten Rod applies to all.
- **Block resets at its owner's turn start (2026-06-11, 3rd audit)**: player block in
  `_begin_player_turn`; enemy block at the start of the enemy phase in
  `end_player_turn` — enemy blocking moves protect through the player's next turn.
- **Time Warp (2026-06-11, 3rd audit)**: `play_card` sets `combat.time_warp_lock`
  every Nth play vs an enemy with `PowerId.TIME_WARP` (+2 Str to it); `can_play`
  returns False under the lock; cleared at next turn start.
- **Potions (2026-06-11, 3rd audit)**: inventory-only by design (nothing drinks them);
  `start_combat` registers potion hooks so passive ones (Fairy in a Bottle) fire.
- **CARD_DISCARD = manual discards only (2026-06-11)**: playing a card and the end-of-turn
  hand discard emit nothing; only `_discard_from_hand` emits (Tingsha-class triggers).
- **Relic counter lifecycles (2026-06-11)**: per-RUN counters = class attributes, never
  reset in `register()`; per-TURN counters = TURN_START-subscription reset; per-COMBAT
  counters = reset in `register()` (which runs at every combat start).
- **Out-of-window energy goes through ENERGIZED (2026-06-11)**: COMBAT_START / TURN_END
  energy grants queue `PowerId.ENERGIZED` (consumed at TURN_START after the energy reset);
  direct `player.energy +=` is wiped there.
- **Healing**: combat heals go through `cards._heal_player()` (Magic Flower ×1.5 hook).
  X-cost values go through `cards._x_value()` (Chemical X +2 hook).
- **Room tags (2026-06-11)**: `spawn_enemies(..., elite=, boss=)` stamps `_elite`/`_boss`
  on enemies; Preserved Insect / Slaver's Collar / elite relic drops key on them. Elites
  drop 1 relic (2 with Black Star) in BOTH run loops.
- **Relic pools are character-gated**: `relics_full.relic_allowed(id, character)` +
  owned-relic dedup in `random_relic` and `generate_boss_relic_choices`; boss relics are
  not in the chest "rare" pool.
- **MERCHANT nodes** run `nodes.greedy_shop_visit` (deterministic: Meal Ticket heal +
  worst-card removal) identically in both run loops.
- **justApplied covers the end-of-turn window too (2026-06-12, 5th audit)**:
  `CombatState.turn_end_window` is True during the TURN_END emit; player debuffs applied
  then (Doubt/Shame `end_of_turn_effect`) are flagged `just_applied` like enemy-phase
  debuffs, so they survive the same-round tick and cover the player's next turn.
- **Partial-save on ANY error (2026-06-12, 5th audit)**: `run_run_eval` (per run-seed)
  and `run_all` (per dimension) catch all exceptions except KeyboardInterrupt — print
  loudly, stop the affected scope, return everything completed. A vLLM HTTP 400
  (context overflow) surfaced as RuntimeError must never discard finished runs.
- **`complete_json` fallback is raw_decode-based (2026-06-12, 5th audit)**: one
  `JSONDecoder.raw_decode` attempt per `{` (first success wins) — never re-scan end
  positions; garbage/truncated reasoning dumps must fail in milliseconds, not minutes.
- **BLOCK_GAINED on every relic block grant**: flat relic block bypasses `_gain_block`
  (no Dex/Frail) but must still emit `Event.BLOCK_GAINED` so Juggernaut fires
  (Orichalcum, Captain's Wheel, Cloak Clasp, The Abacus, Tough Bandages, Anchor).

## Prompt Formats
- `structured`: compact JSON with card names, costs, HP numbers
- `raw`: verbose natural English description
- Both use identical RNG seeds for fair comparison

## Scoring Ground Truth
| Dimension | Ground truth method |
|---|---|
| Turn-level | Exhaustive search over ≤720 permutations |
| Combat-level | Greedy bot baseline |
| Synergy | Hand-crafted archetype fixtures (20/character × 2 characters), expert-labeled archetype + best pick; removal-v1 is quarantined |
| Run-level | Absolute (survival + progress per act) |

## Sampling & Seeds
- `--temperature` is passed through every evaluator to `LLMInterface.complete` (default 0;
  temp>0 enables repeated-sampling error bars, esp. for the deterministic synergy fixtures).
- `--seeds 42 43 …` runs the full benchmark per seed, saves per-seed JSON+charts, then writes a
  combined JSON with mean ± std per metric.

## LLM Providers (`LLMInterface` implementations in benchmark.py)
- `GroqLLM` — Groq SDK; typed 429 detection + 6-attempt backoff → `RateLimitExhausted` for graceful partial-save.
- `OpenRouterLLM` — OpenAI-shaped HTTP over urllib; 402 = hard "add credits" error, 429 retried.
- `LocalLLM` (2026-06-12, GPU phase) — OpenAI-compatible `/v1/chat/completions` over urllib for a
  self-hosted server (vLLM `:8000/v1`, Ollama `:11434/v1`, TGI). `--provider local --base-url URL`
  (falls back to `$LOCAL_BASE_URL` then `http://localhost:8000/v1`). Differs from `OpenRouterLLM`: no
  402 wall (a local server never bills → any non-429 HTTP error is surfaced with the response body so a
  misconfigured endpoint is obvious); 300s timeout (slow single-GPU 32B serving); 8000 max_tokens
  (reasoning `<think>` blocks). Optional `$LOCAL_API_KEY` for vLLM `--api-key` servers (default `EMPTY`).
- `MockLLM` — scripted responses for tests/mock pipeline, no network.
- `complete_json` (shared) strips `<think>…</think>` + markdown fences, then scans for the first valid
  JSON object; unparseable → `{"error": "parse_failure", "raw": …}`.

## RNG Streams (9 total)
hp_rng, card_rng, enemy_rng, event_rng, map_rng, reward_rng, shop_rng, boss_rng, misc_rng
Each is an independent Java-compatible LCG seeded from the run seed.

## Parse-failure scoring policy
Dimensions handle an unparseable LLM answer differently, by design:
- **Turn-level**: a parse failure scores `damage_ratio = 0` AND `legal = False` (an
  empty/garbage answer is not a legal play — counting it as legal would inflate
  `legal_rate` by exactly the parse-failure rate). `parse_ok_rate` is reported separately.
- **Synergy**: a parse failure is **excluded** (`None`) from the serialized accuracies
  (`archetype_acc`, `card_pick_acc`, `removal_acc`) — these values are conditional on a
  parseable answer, not parse-success metrics. To keep the denominator visible,
  `summary()` reports the three `*_n_scored` fields alongside `parse_ok_rate`.
  **Only archetype and card pick are valid capability metrics.** `removal_acc` remains
  serialized for provenance but is quarantined as described below.

## Removal-v1 quarantine (2026-08-30)

All 40 fixed synergy fixtures currently set `expert_remove_name="Strike"`. A constant
`Strike` answer therefore scores 100%, so removal-v1 cannot distinguish strategic
pruning from a degenerate response. It is intentionally excluded from statistical
analysis, headline tables, and the synergy horizon composite. Existing raw fields are
preserved so the failure remains auditable.

A future removal-v2 is a new instrument version, not an in-place correction. It must:

- vary the expert target across strategically justified cards;
- balance target names and candidate positions so every constant answer is at chance;
- persist fixture ID, candidate set, expert target, and model selection per sample;
- pass explicit constant-answer and position-only regression tests; and
- re-baseline the full synergy matrix, because archetype, pick, and removal share one
  model prompt and old/new synergy answers are not byte-comparable.

## Documented simplifications (intentional, not bugs)
These are deliberate fidelity gaps recorded so future audits don't re-flag them
(full provenance in `docs/bug_audit_2026-06-12.md` D-items + earlier audits):
- **Potions are undrinkable** (only Fairy in a Bottle's auto-revive is live). So the
  Regen Potion's REGENERATE grant is dormant (players don't tick Regenerate) and the
  Colorless Potion is a no-op (colorless cards unimplemented).
- **Event-only mode**: combat-promising events (Colosseum, Trial of Fire, Mysterious
  Sphere, Dead Adventurer 40%, Masked Bandits "fight", Mind Bloom "war") resolve as
  flavor text — no spawned fight, no reward.
- **Deterministic event outcomes**: Scrap Ooze always yields its relic by the 4th
  attempt; Wild Strike / Reckless Charge insert their status at the draw-pile bottom;
  Sentry Bolt puts Dazed in the draw pile (real: discard).
- **Relic pool design choices**: Captain's Wheel is gated Defect-only here;
  `random_relic`'s exhausted-pool fallback can grant a duplicate; N'loth's Gift /
  Golden Wing pop a relic without reverting its `on_pickup` effect (max HP / energy
  persist). Prayer Wheel rare-upgrade doubling and Golden Idol +25% gold are comments
  only in `rewards.py`.
- **Timing approximations**: Unceasing Top draws on CARD_PLAY (before the played card
  resolves); Mummified Hand discounts the *next* card "until played".
- **String power keys**: a few enemy/buff keys are plain strings (`"Calm"`, `"enrage"`)
  rather than `PowerId` members — intentional, do not "fix".
- **Archetype substring matching** (H8): archetype mention detection is substring-based,
  so a hypothetical answer like `"blockade"` could read as a "Block" mention. No observed
  impact in saved samples; word-boundary hardening is optional future work.
- **Dead class**: `CenturionAndMystic` is defined but never registered/used.
