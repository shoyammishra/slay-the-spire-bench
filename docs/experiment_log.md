# Experiment Log

## 2026-06-10 — Synergy n=20, both characters, DE-BIASED instrument (CURRENT valid synergy data)

**Config:** `--only synergy --n-synergy 20`, seed=42, free Groq, post-bug-sweep code.
8 runs = 2 models × 2 formats × {Ironclad, Silent}. Silent is **first-ever synergy data**.
Ran via `.venv\Scripts\python.exe` (system Python lacks `groq` — gotcha logged below).

⚠️ **These numbers REPLACE an earlier biased run from the same day.** The first n=20 pass
ran on a synergy instrument with a positional confound (expert pick was at offer index 0 in
35/40 fixtures) + one mislabeled fixture; those card-pick numbers were not interpretable.
Fixed in commit `5db7063` (offer rotation cycles the correct index 0→1→2; fixture #18 pick
corrected; strict single-name archetype match) and re-run. Rotation verified: expert-pick
position is now uniform {0:7,1:7,2:6} and the model spreads its answers {0:5,1:9,2:6} rather
than parroting 0. See "Bugs Fixed" #synergy-instrument in CLAUDE.md.

| Character | Model | Format | n | Archetype | Card Pick | Removal | Parse |
|---|---|---|---|---|---|---|---|
| Ironclad | llama-3.1-8b | structured | 20 | 0.55 | 0.65 | 0.15 | 1.0 |
| Ironclad | llama-3.1-8b | raw | 20 | 0.40 | 0.65 | 0.05 | 1.0 |
| Ironclad | scout-17b | structured | 20 | 0.70 | 0.75 | 0.25 | 1.0 |
| Ironclad | scout-17b | raw | 20 | 0.45 | 0.70 | 0.15 | 1.0 |
| Silent | llama-3.1-8b | structured | 20 | 0.75 | 0.35 | 0.15 | 1.0 |
| Silent | llama-3.1-8b | raw | 20 | 0.60 | 0.65 | 0.15 | 1.0 |
| Silent | scout-17b | structured | 20 | 0.75 | 0.70 | **0.60** | 1.0 |
| Silent | scout-17b | raw | 20 | **0.80** | **0.75** | 0.20 | 1.0 |

**Per-archetype archetype-ID, all 8 combos pooled (20 attempts each, 40 for Block):**

| Archetype | Correct | Character |
|---|---|---|
| Aggro | 19/20 = 95% | Ironclad |
| Poison | 19/20 = 95% | Silent |
| Shiv | 18/20 = 90% | Silent |
| Block | 34/40 = 85% | both |
| Strength | 8/20 = 40% | Ironclad |
| **Exhaust** | **1/20 = 5%** | Ironclad |
| **Discard** | **1/20 = 5%** | Silent |

**Key results (n=20, both characters, de-biased):**
- **Mechanic-defined archetypes are the universal blind spot — now airtight.** Pooled over
  all 8 combos, **Exhaust 5% and Discard 5%** sit far below every surface-readable archetype
  (Aggro/Poison/Shiv/Block 85–95%). Both characters' miss is exactly the archetype defined by
  a *payoff mechanic* (exhaust / discard), not a card-name keyword. Strength (40%) is the
  intermediate case — frequently "Aggro" because Strength decks are Strike-heavy.
- **Card-pick survived de-biasing** (0.65–0.75 for both models on most combos, vs ~0.33
  chance) — so the **name-vs-play dissociation is real, not a positional artifact**: models
  judge local card quality well even on decks they cannot label. (The lone exception, Silent
  llama structured at 0.35, is a genuine weak spot, not the old bias.)
- **Silent archetype-ID ≥ Ironclad** (0.60–0.80 vs 0.40–0.70). Plausibly Silent labels
  (Poison/Shiv/Block/Discard) read more literally off the cards than Ironclad's abstractions.
- **scout-17b Silent structured removal 0.60** is still the standout — the removal blind spot
  is much weaker on Silent for the bigger model. Removal stays near-floor (0.05–0.25)
  everywhere else.
- parse_ok = 1.0 everywhere.

**Caveat:** all 8 are seed=42 only (one fixture pass; deterministic). For paper-grade error
bars still need `--temperature 0.7` k-sampling or a seed sweep — the harness supports both.

---

## 2026-06-10 — No new runs; harness extended for A* acceptance (code-only)

**Status:** No experiments — run-level remains blocked on free Groq TPM (paid tier pending).
Harness changes that affect FUTURE runs (commit d35771e):
- Silent character (full card set + 20 synergy fixtures; Ironclad fixtures expanded 8 → 20)
- Multi-act runs (`--acts 3`), `--temperature`, `--seeds` (mean±std), `--llm-routing`
- Relic lifecycle split (on_pickup/register) — relics no longer stack across a run

**Comparability note:** the relic-stacking fix changes run-level dynamics, so any future
run-level numbers are NOT comparable to pre-2026-06-10 ones — which is moot, since all
existing run-level data was already invalid (map dead-end + EventBus bugs).

**Bug sweep (same day, later):** a full logic+code audit fixed 21 bugs (see CLAUDE.md
"Bugs Fixed"). The player-debuff timing fix (tick at end of round, not before enemy
attacks) **changes combat-level dynamics too**: enemy-applied Weak/Vulnerable now actually
affect the player, so the greedy baseline and LLM combats both take more damage (the Act-1
determinism fixture flipped from survived=True/hp=74 to survived=False/hp=0). ⇒ **Pilot
turn/combat numbers in the tables below were collected on the pre-sweep engine and are not
comparable to future runs.** Synergy is unaffected (static deck snapshot, no combat).
Also fixed before any paid run could be burned: the multi-seed aggregator was emitting
`null` for most means (wrong metric key names). 47 tests pass (24 benchmark + 10 combat +
13 run; needs `PYTHONIOENCODING=utf-8` on Windows consoles).

---

## 2026-06-07 — Synergy re-run on HAND-CRAFTED fixtures, n=8 (CURRENT valid synergy data)

**Config:** `--only synergy --n-synergy 8`, both formats, both models, seed=42.
**Status:** Valid + current. Supersedes ALL earlier synergy numbers (which used RNG-drafted
decks). 8 fixtures = one pass over the fixed set (2 per archetype × 4 archetypes); all 8
classify confident, 0 ambiguous.

| Model | Format | Archetype | Card Pick | Removal | Parse OK |
|---|---|---|---|---|---|
| llama-3.1-8b-instant | structured | 50.0% | 100% | 25.0% | 100% |
| llama-3.1-8b-instant | raw | 37.5% | 62.5% | 12.5% | 100% |
| llama-4-scout-17b | structured | 75.0% | 75.0% | 25.0% | 100% |
| llama-4-scout-17b | raw | 50.0% | 100% | 12.5% | 100% |

**Per-archetype identification (8 attempts each = 2 decks × 2 models × 2 formats):**

| True archetype | Correct | Models said instead |
|---|---|---|
| Block | 7/8 | one "Strength" |
| Aggro | 8/8 | — |
| Strength | 2/8 | almost always "Aggro" |
| Exhaust | 0/8 | ALWAYS "Aggro" |

**Key findings (NEW, from clean fixtures):**
- **Exhaust archetype is never recognised** (0/8) — every model/format calls it "Aggro".
  Strength also weak (2/8). Models name an archetype only when its signature is a simple
  surface pattern (Block, generic Aggro); they miss mechanic-defined strategies (Exhaust
  payoff) even with signature cards present. Systematic, not noise.
- **Name-vs-play dissociation:** card-pick is high (62.5–100%) even on decks the model can't
  label — local card-quality judgement is strong, abstract strategic label is weak.
- **Removal still near-zero** (12.5–25%) — the 25% comes only from Block fixtures where the
  removal target coincides; models cut situational cards, not basic Strike.
- scout-17b (structured) is the best archetype identifier (75%). No single format wins
  outright: raw helps llama card-pick, structured helps scout archetype ID.

**Note:** the old `67%/100%` archetype figures (RNG-draft era) are RETIRED. They came from a
3-deck RNG sample with an Aggro-biased heuristic and do not reflect the fixed-deck eval.

---

## 2026-06-07 — qwen3-32b DROPPED (no valid data on free tiers)

**Status:** Excluded from the study. Result files deleted.

qwen3-32b (reasoning model) was wired and attempted on both providers; neither free
tier could produce valid data:
- **OpenRouter free:** ~30–80 tok/s → n=5 run-level = 1.5–3h; free credits exhausted
  mid-run → HTTP 402 Payment Required.
- **Groq free:** 6000 TPM cap truncated its reasoning mid-`<think>` → parse-failure
  cascade, 0% across every dimension (turn/combat/synergy/run all 0; combat parse
  errors 7.67/sample).

Root cause is infrastructural, not a model-capability result — so the 0% scores are NOT
reported as qwen3 performance. A reasoning model needs a PAID tier (paid Groq preferred:
uncapped TPM + ~400–1000 tok/s). Revisit = future work. See docs/notes.md, docs/report.md.

---

## 2026-06-07 — Synergy re-run (post synergy-fix): all models, seed=42  [SUPERSEDED]

**Config:** `--only synergy`, n_synergy=3, both formats, both models
**Status:** ⛔ SUPERSEDED by the hand-crafted n=8 run above. These used RNG-drafted decks +
an Aggro-biased heuristic (only ~3/10 decks confidently labelled); the 67%/100% figures are
retired. Kept for history only.

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
