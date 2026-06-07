# Experiment Log

## 2026-06-07 — Synergy re-run (post synergy-fix): all models, seed=42

**Config:** `--only synergy`, n_synergy=3, both formats, both models
**Status:** Valid. First synergy results with real deck (greedy card_choice_fn fix applied).

| Model | Format | Archetype | Card Pick | Removal | Parse OK |
|---|---|---|---|---|---|
| llama-3.1-8b-instant | structured | 67% | 33% | 0% | 100% |
| llama-3.1-8b-instant | raw | 100% | 33% | 0% | 100% |
| llama-4-scout-17b | structured | 67% | 67% | 0% | 100% |
| llama-4-scout-17b | raw | 100% | 33% | 0% | 100% |

**Key findings:**
- Removal 0% confirmed genuine model failure (not a bug). Expert says remove Strike; models say Disarm/Battle Trance/Bash — reasoning about card quality, not deck cycling.
- Raw format = 100% archetype acc for both models. Structured = 67%.
- Scout-17b better at structured card pick (67% vs 33%).

---

## 2026-06-07 — Post-fix run: llama-3.1-8b-instant, seed=42

**Config:** n_turn=5, n_combat=3, n_synergy=3, n_run=5, both formats
**Status:** Turn/combat/run valid. Synergy invalid (pre-synergy-fix) — needs re-run with `--only synergy`.

| Metric | Structured | Raw |
|---|---|---|
| Turn damage ratio | 36.7% | 69.6% |
| Turn legal rate | 60% | 100% |
| Combat win rate | 100% | 100% |
| Combat HP ratio | 112.3% | 113.8% |
| Synergy archetype | 0% ⚠ | 66.7% ⚠ |
| Synergy best card | 33.3% ⚠ | 33.3% ⚠ |
| Synergy removal | 0% ⚠ | 0% ⚠ |
| Run survival | 20% | 40% |
| Run avg floors | 13.4/15 | 13.4/15 |
| Run HP fraction | 93.8% survivors | 60.6% survivors |
| Run draft coherence | 36.4% | 40.9% |
| **Overall** | **41.9%** | **60.7%** |

**Notes:** Run-level now real (map+EventBus bugs fixed). Raw significantly outperforms structured overall. Synergy marked ⚠ — synergy eval used starter deck throughout; fix landed after this run.

---

## 2026-06-07 — Pilot: llama-3.1-8b-instant, seed=42

**Config:** n_turn=5, n_combat=3, n_synergy=3, n_run=1, both formats

| Metric | Structured | Raw |
|---|---|---|
| Turn damage ratio | 36.7% | 69.6% |
| Turn legal rate | 60% | 100% |
| Combat win rate | 100% | 100% |
| Combat HP ratio | 112.3% | 108.5% |
| Synergy archetype | 66.7% | 100% |
| Synergy best card | 100% | 33.3% |
| Synergy removal | 0% | 0% |
| Run survival | 0% | 0% |
| Run floors | 5/15 | 5/15 |
| **Overall** | **48.1%** | **53.5%** |

**Notes:** Run floors were artificially stuck at 5/15 due to map dead-end bug (now fixed). Run results invalid — need re-run.

---

## 2026-06-07 — Pilot: meta-llama/llama-4-scout-17b-16e-instruct, seed=42

**Config:** n_turn=5, n_combat=3, n_synergy=3, n_run=1, both formats

Results saved in `results/meta-llama-llama-4-scout-17b-16e-instruct_*.txt`. Need to review.

---

## Bugs that invalidated earlier results

1. **Map dead-end** — all pre-fix run results show floors=5/15, invalid.
2. **EventBus stacking** — survival=1.0, hp_fraction=1.0 for weak models, invalid.
Both fixed as of 2026-06-07. Any runs before these fixes need to be discarded and re-run.
