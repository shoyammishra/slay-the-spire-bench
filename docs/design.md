# Design

## Architecture Overview

```
run_benchmark.py          CLI entry point
slay_bench/
  benchmark.py            4-dimension harness + LLM interface
  prompt_builder.py       GameState → prompt (structured JSON or raw English)
  combat.py               Turn engine: draw, play, enemy attack, block
  run_loop.py             Full Act 1 simulation (15 floors)
  map_gen.py              Map generation + path traversal
  cards.py                All Ironclad cards
  enemies.py              Act 1 enemies
  relics.py / relics_full.py  Relic effects via EventBus
  rng.py                  Java-compatible LCG, 9 independent seeded streams
  visualize.py            PNG charts + ASCII reports
```

## Key Invariants

- **Energy**: deducted only in `play_card()` (combat.py). Cards never deduct energy themselves.
- **Determinism**: same seed → identical map, enemies, draws, rewards every run.
- **EventBus**: cleared at the top of `start_combat` to prevent listener stacking across combats.
- **Illegal plays**: if any card in a sequence is illegal, `damage_ratio = 0`.
- **HP fraction**: averaged over survivors only; deaths excluded (contribute to survival_rate as 0).
- **avg_progress**: floors_reached / 15, clamped to 1.0. Gives partial credit on death.

## Prompt Formats
- `structured`: compact JSON with card names, costs, HP numbers
- `raw`: verbose natural English description
- Both use identical RNG seeds for fair comparison

## Scoring Ground Truth
| Dimension | Ground truth method |
|---|---|
| Turn-level | Exhaustive search over ≤720 permutations |
| Combat-level | Greedy bot baseline |
| Synergy | Expert heuristic labels |
| Run-level | Absolute (survival + progress) |

## RNG Streams (9 total)
hp_rng, card_rng, enemy_rng, event_rng, map_rng, reward_rng, shop_rng, boss_rng, misc_rng
Each is an independent Java-compatible LCG seeded from the run seed.
