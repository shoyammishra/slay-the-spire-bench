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

## Prompt Formats
- `structured`: compact JSON with card names, costs, HP numbers
- `raw`: verbose natural English description
- Both use identical RNG seeds for fair comparison

## Scoring Ground Truth
| Dimension | Ground truth method |
|---|---|
| Turn-level | Exhaustive search over ≤720 permutations |
| Combat-level | Greedy bot baseline |
| Synergy | Hand-crafted archetype fixtures (20/character × 2 characters), expert-labeled best pick + worst removal |
| Run-level | Absolute (survival + progress per act) |

## Sampling & Seeds
- `--temperature` is passed through every evaluator to `LLMInterface.complete` (default 0;
  temp>0 enables repeated-sampling error bars, esp. for the deterministic synergy fixtures).
- `--seeds 42 43 …` runs the full benchmark per seed, saves per-seed JSON+charts, then writes a
  combined JSON with mean ± std per metric.

## RNG Streams (9 total)
hp_rng, card_rng, enemy_rng, event_rng, map_rng, reward_rng, shop_rng, boss_rng, misc_rng
Each is an independent Java-compatible LCG seeded from the run seed.
