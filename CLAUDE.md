# slay-bench — Project Context for Claude

## What This Is
A Python simulator + LLM benchmark harness for Slay the Spire (Ironclad only).
Tests LLM planning ability across 4 dimensions: turn-level, combat-level, synergy, and run-level.
GitHub: https://github.com/shoyammishra/slay-the-spire-bench (private)

## Security — CRITICAL
- `.env` contains real API keys for BOTH Groq and OpenRouter. It is gitignored. NEVER commit it.
- Never share or print any API key from `.env`.

## Active Context

- **Status:** In progress — synergy archetype scoring fixed (3rd time) + combat null-index crash fixed. qwen3 DROPPED. ALL archetype numbers in this file are now INVALID and must be re-collected.
- **Current task:** Re-run `--only synergy --n-synergy 20` ×4 (llama) with the confident-classifier fix; re-run `--only run` ×4 (scout needs n=5); then merge.
- **Key files:** `slay_bench/benchmark.py`, `slay_bench/run_loop.py`, `run_benchmark.py`
- **Completed this session (2026-06-07):** (1) **Synergy archetype 3rd fix** — `_classify_archetype_confident()`: label from signature cards only, ambiguous decks excluded from acc; per-sample audit persisted to JSON. (2) **Combat null/string index crash fixed** — `_safe_int()` in both combat loops. (3) qwen3 DROPPED + result files deleted. (4) Substring archetype match + `model_said` print. 42 tests pass.
- **⚠️ qwen3-32b DROPPED (2026-06-07):** could not get valid data on free tiers. **OpenRouter free** is too slow (~30–80 tok/s; n=5 run-level = 1.5–3h) and returned **402 Payment Required** once exhausted. **Groq free** 6000 TPM truncates its reasoning mid-`<think>` → parse-failure cascade (0% everywhere). A reasoning model needs a PAID tier (paid OpenRouter for speed, or paid Groq for uncapped TPM). qwen3 result files deleted. Revisit = future work. See docs/report.md + docs/notes.md.
- **⚠️ Synergy numbers invalid:** the `--only synergy` runs done earlier today gave archetype_acc=0 on all 4 combos — that was the OLD broken heuristic (see bug log + findings.md). Re-run with the new confident classifier. **Bump `--n-synergy 20`** — at small card pools only ~1/3 of seeds land a clean signature, so few samples are scored at n=3.
- **Next:** Re-run `--only synergy --n-synergy 20` ×4 + `--only run` ×4 for the llama combos. Then scale to n≥20, fold real numbers into findings.md + report.md + CLAUDE.md.
- **Provider note:** llama models on Groq. Reasoning models (qwen3 etc.) require a paid tier — do not benchmark on free tiers.
- **⚠️ GOTCHA — running process uses startup code:** a launched Python run loads `benchmark.py` once at startup; editing it does NOT affect an in-flight run. Re-launch or use `--only` to pick up code changes.
- **Remaining run plan:** (1) `--only synergy --n-synergy 20` ×4 (llama-3.1-8b struct+raw, llama-4-scout struct+raw); (2) `--only run` ×4 (scout needs n=5 re-run); (3) fold real numbers into findings.md + report.md + CLAUDE.md; (4) merge `synergy-rework` → main.
- **Speed:** Paid Groq (~400–1000 tok/s, no TPM cap) is the real speedup lever for n≥20 — see docs/notes.md.

## Docs
Detail lives in `docs/` — not here.
- `docs/roadmap.md` — milestones, timeline
- `docs/decision_log.md` — architecture & design decisions
- `docs/experiment_log.md` — runs, configs, results, failures
- `docs/findings.md` — observations, hypotheses
- `docs/notes.md` — scratch pad
- `docs/design.md` — architecture, invariants, interfaces
- `docs/draft.md` — paper draft

## Project Structure
```
slay_bench/
  cards.py          — All Ironclad cards with exact effects
  enemies.py        — Enemies: Cultist, JawWorm, AcidSlimeL, SpikeSlimeL, etc.
  combat.py         — Turn engine: draw, play, enemy attack, block
  game_map.py       — Map generation, node types, path traversal
  run_loop.py       — Full act simulation floor-by-floor
  rng.py            — Java-compatible LCG, 9 independent seeded streams
  prompt_builder.py — GameState → text prompt (structured JSON or raw English)
  benchmark.py      — 4-dimension benchmark harness + LLM interface
  visualize.py      — PNG charts + ASCII text reports from results
run_benchmark.py    — CLI entry point
tests/
  test_benchmark.py — 40 unit tests (all passing, no API calls)
results/            — Output files (gitignored): .json, .txt, .png, _radar.png
docs/               — Project documentation (roadmap, decisions, findings, draft)
```

## Running the Benchmark
```powershell
# Mock run (instant, no API)
python run_benchmark.py --provider mock --model mock --format structured --seed 42

# Real run — structured format
python run_benchmark.py --provider groq --model llama-3.1-8b-instant --n-turn 5 --n-combat 3 --n-synergy 3 --n-run 5 --format structured

# Real run — raw format (ablation)
python run_benchmark.py --provider groq --model llama-3.1-8b-instant --n-turn 5 --n-combat 3 --n-synergy 3 --n-run 5 --format raw

# Another model
python run_benchmark.py --provider groq --model meta-llama/llama-4-scout-17b-16e-instruct --n-turn 5 --n-combat 3 --n-synergy 3 --n-run 5 --format structured

# Re-run only one dimension (merges others from disk)
python run_benchmark.py --provider groq --model llama-3.1-8b-instant --format structured --only synergy
python run_benchmark.py --provider groq --model llama-3.1-8b-instant --format structured --only run
python run_benchmark.py --provider groq --model llama-3.1-8b-instant --format structured --only synergy run
```

Output files per run (overwrites if same model+format+seed):
- `results/<model>_<format>_seed<N>.json` — raw scores
- `results/<model>_<format>_seed<N>.txt`  — human-readable ASCII report
- `results/<model>_<format>_seed<N>.png`  — 2×2 bar chart (dark theme)
- `results/<model>_<format>_seed<N>_radar.png` — spider chart

## Benchmark Dimensions
| # | Name | What it tests | Ground truth |
|---|---|---|---|
| 1 | Turn-level | Best card sequence in one turn | Exhaustive search (≤720 permutations) |
| 2 | Combat-level | Win a full fight turn-by-turn | Greedy bot baseline |
| 3 | Synergy | Archetype ID, best pick, worst removal | Expert heuristic |
| 4 | Run-level | Survive full Act 1 (15 floors) | Absolute (survival + progress) |

## Key Metrics
- `damage_ratio` — LLM damage / optimal damage (0–1, illegal plays score 0)
- `win_rate` — fraction of combats won
- `hp_ratio` — LLM HP remaining / greedy bot HP remaining (>1 = better than bot)
- `archetype_acc` — correctly identified deck strategy
- `card_pick_acc` — picked the expert-labeled best card
- `removal_acc` — suggested removing the expert-labeled worst card
- `survival_rate` — fraction of full runs survived
- `avg_progress` — floors reached / 15 (partial credit on death)
- `avg_draft_coherence` — fraction of non-basic cards fitting dominant archetype

## Prompt Formats
- `structured` — compact JSON state (dicts with card names, costs, HP numbers)
- `raw` — verbose natural English description of the same state
- Both formats get identical RNG seeds so comparisons are fair

## Architecture Notes
- Energy payment: `play_card()` in `combat.py` is the ONLY place energy is deducted (single source of truth). Cards do NOT deduct energy themselves.
- RNG: 9 independent LCG streams (hp_rng, card_rng, etc.) — Java-compatible seed math
- EventBus: pub/sub for relic/power hooks (DAMAGE_DEALT, CARD_PLAYED, etc.)
- Determinism: same seed → same map, enemies, draws, rewards every time
- Illegal play scoring: if any card in the sequence is illegal, `damage_ratio = 0`
- Draft coherence: uses expanded `_ARCHETYPES` dict (~14 cards per archetype)
- Run HP fraction: only averaged over survivors; deaths contribute 0 and are excluded

## Bugs Fixed (session history)
- Double energy charge: each card was subtracting energy AND play_card() was — removed 63 redundant lines
- Curl Up never triggered: `on_damage_taken` was defined but never called in `_apply_damage_to_enemy`
- Slimes never split: `on_hp_threshold` in combat.py was a no-op pass — wired into `_apply_damage_to_enemy`
- Perfected Strike upgraded: `2 if upgraded else 2` (same) → `3 if upgraded else 2`
- Double boss fight: `reachable_from()` returned boss twice — excluded `boss_node` from traversal queue
- legal=False but high dmg_ratio: illegal sequences now score dmg=0
- Draft coherence=0: `_ARCHETYPES` was too narrow (5 cards) → expanded to ~14 cards per archetype
- avg_hp_fraction on death: now only averaged over survivors; added `avg_progress` for partial credit
- complete_json crash on multi-block JSON: now scans for first valid JSON object instead of greedy regex
- **Map dead-end (run always "floor 5")**: `generate_map` wired each floor's edges to `_choose_active_cols(rng, floor+1)`, but that fn was re-rolled when the next floor was actually built — edges pointed to non-existent columns. Greedy path dead-ended at floor ~3, then teleported to the boss and lost → fake "floor 5" for EVERY model/format. Fixed: active cols chosen once up-front, edges wired to real next-floor cols, added `_ensure_connectivity()`. Run now traverses all 15 floors. **Old llama run-level results are invalid — re-run.**
- ShiningLight event crashed (`_shining_light` referenced, never defined) — masked by the dead-end. Added helper (lose 30% max HP, upgrade 2 random cards).
- Curse cards crashed via `make_card` (`Injury(upgraded)` — curses take no args). `make_card` now falls back to no-arg construction.
- avg_progress could exceed 1.0 on survival (boss counted as extra node) — now clamped to 1.0.
- **EventBus listener stacking (fake 100% run survival at full HP)**: `start_combat` re-registers all relic + power hooks every combat, but the bus was never cleared, so handlers accumulated across a run. Burning Blood's COMBAT_END heal grew 6→12→18→24→30…, and TURN_START block/strength hooks stacked too, making the player progressively invincible. Run-level showed survival=1.0, hp_fraction=1.0 for a weak 8B in BOTH formats. Fixed: added `EventBus.clear()`, called at the top of `start_combat`. Did NOT affect combat-level dimension (fresh state per sample = 1 listener). **llama run-level results from this run are invalid — re-run.**
- **Rate-limit crash lost completed runs**: a Groq 429 mid-run threw an uncaught exception, killing the process and discarding finished work. Fixed: `GroqLLM.complete` now retries 429s with exponential backoff (1/2/4/8/16s); after 5 tries it raises `RateLimitExhausted`, which `run_run_eval`/`run_all` catch to save partial results. NOTE: `floors_reached=16 + negative HP` is CORRECT — it means "reached the boss (node 16 = 15 floors + boss) and died fighting it"; surviving the boss shows `floors=16` with positive HP.
- **Synergy eval always used starter deck**: `run_synergy_eval` called `run_act(state, act=1)` with `card_choice_fn=None`, so no cards were ever added during the greedy traversal. The synergy snapshot was always the 10-card starter deck (5 Strike, 4 Defend, 1 Bash). `_classify_archetype` on that scores 0 everywhere → default "Aggro". Expert label was always "Aggro" with zero signal. Fixed: added `_greedy_pick` (picks first non-curse offer) and passes it as `card_choice_fn`. Deck now has ~15–20 real cards at eval time. **All prior synergy results are invalid — re-run with `--only synergy`.**
- **`--only` flag for partial runs**: `run_benchmark.py` now accepts `--only turn|combat|synergy|run` (one or more). Skipped dimensions produce `null` in the summary; the existing merge logic fills them in from the previous JSON on disk. Charts and text are regenerated from the merged result.
- **Synergy eval Aggro-bias + incoherent decks (2nd synergy rework, 2026-06-07)**: even after the greedy-pick fix above, two problems remained. (1) `_greedy_pick` (first non-curse offer) built incoherent decks with no real archetype — accuracy measured agreement on noise. (2) `_classify_archetype` counted card presence equally, and the Aggro bucket is full of generic Strike-variants present in any draft, so nearly every deck was labeled "Aggro" (seeds 242/243/244 all → Aggro, even one whose defining card was Corruption = Exhaust payoff). Fixed: added `_ARCHETYPE_PAYOFFS` (signature cards weighted 3× in the classifier), added `_archetype_draft_fn(target)`, and `run_synergy_eval` now cycles targets Strength→Block→Exhaust→Aggro drafting toward each. Expert label still derived from the actual built deck (not the target), so RNG-constrained decks are scored honestly (3/4 seeds hit target; mismatches are real Block/etc. leans). **All prior synergy results invalid — re-run with `--only synergy`.** See docs/findings.md.
- **Synergy archetype mislabeling (3rd synergy fix, 2026-06-07)**: post-2nd-rework `--only synergy` gave archetype_acc=0 on ALL 4 llama combos (incl. raw, normally 100%) with parse_ok=1.0 — the heuristic was mislabeling decks, not the models failing. seed 244 → "Exhaust" with zero Exhaust cards (Armaments/Headbutt are miscategorized in the broad `_ARCHETYPES` list); seed 242 a 4/5/4/3 near-tie decided by a generic common (Corruption 3× payoff overruled). Fixed: added `_classify_archetype_confident()` — LABEL now decided by **signature cards only** (`_ARCHETYPE_PAYOFFS` + relics); deck is confidently labeled only if one archetype uniquely owns the most signatures, else **ambiguous** → `archetype_correct=None` → excluded from acc. `_classify_archetype` unchanged (still drives draft coherence / best-pick). Synergy JSON now persists per-sample `expert_archetype`/`model_archetype`/`confident` + `archetype_n_scored`/`archetype_n_ambiguous`. **Post-2nd-rework archetype numbers INVALID — re-run `--only synergy`, and bump n_synergy (~1/3 of seeds land a clean signature at small pools).** See docs/findings.md.
- **null/string LLM indices crashed combat (2026-06-07)**: a model returning `"target_index": null` crashed run-level with `TypeError: None < int`. Added `_safe_int()`; applied to both `RunEvaluator._llm_combat` and `CombatEvaluator` (same latent bug). Regression test added.
- **qwen3-32b reasoning model (wired, then DROPPED)**: outputs `<think>...</think>` blocks. `complete_json` strips them; `max_tokens` raised to 3000 (Groq) / 8000 (OpenRouter). `OpenRouterLLM.complete` retries 429s + network drops with backoff and fails fast on 402. **Dropped from the study:** Groq free-tier TPM (6000) truncates it mid-think (parse-failure cascade, 0%), and OpenRouter free tier is too slow (~30–80 tok/s) and hit 402 Payment Required. A reasoning model needs a PAID tier to benchmark viably. Result files deleted.

## Post-fix Results (seed=42, n_turn=5, n_combat=3, n_synergy=3, n_run=5)
These are valid post-fix results. Synergy numbers below are **still pre-synergy-fix** and should be re-run.

### llama-3.1-8b-instant
| Metric | Structured | Raw |
|---|---|---|
| Turn damage ratio | 36.7% | 69.6% |
| Turn legal rate | 60% | 100% |
| Combat win rate | 100% | 100% |
| Combat HP ratio | 112.3% | 113.8% |
| Synergy archetype | 67% | 100% |
| Synergy best card | 33% | 33% |
| Synergy removal | 0% | 0% |
| Run survival | 20% | 40% |
| Run avg floors | 13.4/15 | 13.4/15 |
| Run HP fraction | 93.8% (survivors) | 60.6% (survivors) |
| Run draft coherence | 36.4% | 40.9% |
| **Overall** | **41.9%** | **60.7%** |

Key findings: Raw format clearly outperforms structured (60.7% vs 41.9%). Run-level is now real — 13.4 avg floors, 20–40% survival. Removal acc = 0% is genuine model failure — both models reason about card quality instead of deck cycling (see docs/findings.md).

## Available Groq Models (as of 2026-06-07)
- `llama-3.1-8b-instant` — small, fast (tested)
- `meta-llama/llama-4-scout-17b-16e-instruct` — medium, newer (testing)
- `qwen/qwen3-32b` — reasoning model, DROPPED (free tiers can't run it; needs paid — see Active Context)

## User Preferences
- Progress prints in terminal for every sample (added flush=True prints)
- Results overwrite by model+format+seed (no timestamps in filenames)
- Mock run first to verify harness before spending API credits
- Pilot results are preliminary — proper paper needs n≥20 samples and 3+ models
