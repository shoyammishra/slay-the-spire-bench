# slay-bench — Project Context for Claude

## What This Is
A Python simulator + LLM benchmark harness for Slay the Spire (Ironclad only).
Tests LLM planning ability across 4 dimensions: turn-level, combat-level, synergy, and run-level.
GitHub: https://github.com/shoyammishra/slay-the-spire-bench (private)

## Security — CRITICAL
- `.env` contains real API keys for BOTH Groq and OpenRouter. It is gitignored. NEVER commit it.
- Never share or print any API key from `.env`.

## Active Context

- **Status:** In progress — synergy REDESIGNED to hand-crafted decks + RE-RUN at n=8 (done). Run-level re-run BLOCKED by free-tier Groq TPM (see below). qwen3 DROPPED.
- **Current task:** Run-level n=3 re-run is blocked on free Groq's 6000 TPM cap (run-level is too token-heavy — hundreds of stateful calls; one prompt alone requests ~3367 tok and trips 429 on nearly every call). Need PAID Groq Dev tier to scale run-level + everything else to n≥20. Synergy n=8 already re-run with hand-crafted fixtures.
- **⛔ ALL existing run-level numbers INVALID (2026-06-07):** the run-level data in `results/*.json` (llama 20%/40%, 13.4 floors; scout floors=5) is from OLD pre-fix code (predates map dead-end + EventBus stacking + `_safe_int` fixes). IGNORE it — run-level has NO valid data yet. A clean pass is pending + blocked on free TPM. (report.md/findings.md/report.html now all EXCLUDE run-level — do not re-introduce the old 13.4/20–40% figures.)
- **⚠️ Run-level blocked on free tier (2026-06-07):** `--only run --n-run 3` on llama-3.1-8b hit the 6000 TPM wall — structured completed 0 runs (kept prior valid run results via partial-save), raw hung in an infinite retry loop and was Ctrl-C'd. Free Groq sustains ~2 calls/min; a single run needs dozens-to-hundreds → infeasible. Partial-save logic worked: existing run-level + fresh synergy results both intact. **Unblock = paid Groq Dev tier** (the 429 error itself recommends it). This is the same lever needed for paper-grade n≥20.
- **Paper-grade gap (discussed 2026-06-07):** all current numbers are PILOT-grade. Synergy n=8 is real signal (12.5pp steps, not 33pp) but DETERMINISTIC (8 fixed fixtures = a fixed mini-exam, no sampling variance/std). Turn (n=5), combat (n=3), run (n=3) still move in coarse steps. Paper needs: (1) n≥20–30 per dim, (2) multiple seeds, (3) a 3rd model from another family (ideally a frontier/reasoning model — the dropped qwen3 left no reasoning model), (4) mean±std reporting. For synergy variance: add more fixtures (4–5/archetype → n=16–20) OR sample each fixture k times at temp>0 for error bars. Harness is paper-READY; blocker is compute/credits, not code.
- **Key files:** `slay_bench/benchmark.py`, `slay_bench/run_loop.py`, `run_benchmark.py`
- **Completed this session (2026-06-07):** (1) **Synergy REDESIGNED** — RNG drafts dropped; now 8 hand-crafted `_SYNERGY_FIXTURES` decks for clean ground truth (removed dead `_archetype_draft_fn`). (2) `_classify_archetype_confident()` (signature-only labels + ambiguity) + per-sample JSON audit. (3) **Combat null/string index crash fixed** — `_safe_int()` in both combat loops. (4) **Robust Groq 429 handling** — typed detection + `max_retries=0` + 6-attempt backoff. (5) qwen3 DROPPED + files deleted. 43 tests pass. (6) **Synergy n=8 RE-RUN done** — real numbers folded into all docs (Exhaust 0/8, name-vs-play dissociation). (7) **`docs/report.html`** — standalone shareable pilot report for the professor. (8) **All run-level numbers flagged INVALID** (pre-fix code).
- **⚠️ qwen3-32b DROPPED (2026-06-07):** could not get valid data on free tiers. **OpenRouter free** is too slow (~30–80 tok/s; n=5 run-level = 1.5–3h) and returned **402 Payment Required** once exhausted. **Groq free** 6000 TPM truncates its reasoning mid-`<think>` → parse-failure cascade (0% everywhere). A reasoning model needs a PAID tier (paid OpenRouter for speed, or paid Groq for uncapped TPM). qwen3 result files deleted. Revisit = future work. See docs/report.md + docs/notes.md.
- **✅ Synergy DONE (n=8 hand-crafted fixtures):** real numbers collected for all 4 combos and folded into all docs + `docs/report.html`. Key result: Exhaust 0/8 (always "Aggro"), Strength 2/8, Block 7/8, Aggro 8/8; name-vs-play dissociation; removal 12.5–25%. Earlier RNG-draft synergy numbers (67%/100%) are RETIRED.
- **Next:** Run-level is the only remaining dimension with no valid data — clean pass blocked on free TPM (needs paid Groq). Then scale all dims to n≥20 + ≥5 seeds + a 3rd-family model. See `docs/roadmap.md` run matrix.
- **Provider note:** llama models on Groq. Reasoning models (qwen3 etc.) require a paid tier — do not benchmark on free tiers.
- **⚠️ GOTCHA — running process uses startup code:** a launched Python run loads `benchmark.py` once at startup; editing it does NOT affect an in-flight run. Re-launch or use `--only` to pick up code changes.
- **Remaining run plan:** (1) ~~synergy n=8 ×4~~ DONE; (2) `--only run --n-run ≥20` ×4 — clean run-level pass, blocked on free TPM (needs paid Groq); (3) scale turn/combat to n≥20 + ≥5 seeds; (4) add a 3rd-family model; (5) merge `synergy-rework` → main. Full checklist in `docs/roadmap.md`.
- **Speed:** Paid Groq (~400–1000 tok/s, no TPM cap) is the real speedup lever for n≥20 — see docs/notes.md.
- **➡️ Next steps = the paper-grade run matrix in `docs/roadmap.md`** (models, per-dim n≥20, ≥5 seeds, both formats, mean±std, run order). When a paid Groq Dev tier is available: run-level first (no valid data), then scale turn/combat, then expand synergy, then add a 3rd-family model.

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
| 3 | Synergy | Archetype ID, best pick, worst removal | Hand-crafted archetype decks (8 fixtures) |
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
- **Synergy redesigned to hand-crafted decks (2026-06-07)**: RNG-drafted Act-1 decks proved a dead end for archetype ID — only ~3/10 came out confidently labeled, models collapsed to "Aggro" (archetype_acc=0.333 identical across all 4 combos), and even "confident" labels were debatable (Block off a lone Body Slam). Root cause: Act-1 decks are too small/RNG-limited to have a crisp archetype (those form in Acts 2–3). Replaced RNG drafting in `run_synergy_eval` with 8 fixed `_SYNERGY_FIXTURES` (2/archetype; 4–5 signatures each, a basic Strike removal target, and an on-archetype best-pick offer). Ground truth now deterministic + unambiguous (all 8 verified confident). Removed dead `_archetype_draft_fn`. Run `--only synergy --n-synergy 8`. See docs/findings.md.
- **Synergy archetype mislabeling (3rd synergy fix, 2026-06-07)**: post-2nd-rework `--only synergy` gave archetype_acc=0 on ALL 4 llama combos (incl. raw, normally 100%) with parse_ok=1.0 — the heuristic was mislabeling decks, not the models failing. seed 244 → "Exhaust" with zero Exhaust cards (Armaments/Headbutt are miscategorized in the broad `_ARCHETYPES` list); seed 242 a 4/5/4/3 near-tie decided by a generic common (Corruption 3× payoff overruled). Fixed: added `_classify_archetype_confident()` — LABEL now decided by **signature cards only** (`_ARCHETYPE_PAYOFFS` + relics); deck is confidently labeled only if one archetype uniquely owns the most signatures, else **ambiguous** → `archetype_correct=None` → excluded from acc. `_classify_archetype` unchanged (still drives draft coherence / best-pick). Synergy JSON now persists per-sample `expert_archetype`/`model_archetype`/`confident` + `archetype_n_scored`/`archetype_n_ambiguous`. **Post-2nd-rework archetype numbers INVALID — re-run `--only synergy`, and bump n_synergy (~1/3 of seeds land a clean signature at small pools).** See docs/findings.md.
- **null/string LLM indices crashed combat (2026-06-07)**: a model returning `"target_index": null` crashed run-level with `TypeError: None < int`. Added `_safe_int()`; applied to both `RunEvaluator._llm_combat` and `CombatEvaluator` (same latent bug). Regression test added.
- **qwen3-32b reasoning model (wired, then DROPPED)**: outputs `<think>...</think>` blocks. `complete_json` strips them; `max_tokens` raised to 3000 (Groq) / 8000 (OpenRouter). `OpenRouterLLM.complete` retries 429s + network drops with backoff and fails fast on 402. **Dropped from the study:** Groq free-tier TPM (6000) truncates it mid-think (parse-failure cascade, 0%), and OpenRouter free tier is too slow (~30–80 tok/s) and hit 402 Payment Required. A reasoning model needs a PAID tier to benchmark viably. Result files deleted.

## Current Results (seed=42; turn n=5, combat n=3, synergy n=8). Run-level EXCLUDED (no valid data).
Polished shareable report: `docs/report.html`. Full detail: `docs/findings.md`, `docs/experiment_log.md`.

### llama-3.1-8b-instant
| Metric | Structured | Raw |
|---|---|---|
| Turn damage ratio | 36.7% | 69.6% |
| Turn legal rate | 60% | 100% |
| Combat win rate | 100% | 100% |
| Combat HP ratio | 112.3% | 113.8% |
| Synergy archetype (n=8) | 50.0% | 37.5% |
| Synergy best card (n=8) | 100% | 62.5% |
| Synergy removal (n=8) | 25.0% | 12.5% |

### meta-llama/llama-4-scout-17b
| Metric | Structured | Raw |
|---|---|---|
| Turn damage ratio | 49.8% | 37.5% |
| Turn legal rate | 100% | 100% |
| Combat win rate | 100% | 100% |
| Combat HP ratio | 111.4% | 103.5% |
| Synergy archetype (n=8) | 75.0% | 50.0% |
| Synergy best card (n=8) | 75.0% | 100% |
| Synergy removal (n=8) | 25.0% | 12.5% |

**Per-archetype ID (8 attempts each = 2 decks × 2 models × 2 formats):** Block 7/8, Aggro 8/8, Strength 2/8, **Exhaust 0/8 (always "Aggro")**.

Key findings (from hand-crafted n=8 fixtures): (1) **Exhaust archetype never recognised** — every model/format calls it "Aggro" despite signature cards. (2) **Name-vs-play dissociation** — card-pick high (62.5–100%) even on decks the model can't label. (3) **Removal near-zero** (12.5–25%) — models cut situational cards, not basic Strike. (4) **No single format wins** — raw helps llama card-pick, structured helps scout archetype ID. See docs/findings.md.

## Available Groq Models (as of 2026-06-07)
- `llama-3.1-8b-instant` — small, fast (tested)
- `meta-llama/llama-4-scout-17b-16e-instruct` — medium, newer (testing)
- `qwen/qwen3-32b` — reasoning model, DROPPED (free tiers can't run it; needs paid — see Active Context)

## User Preferences
- Progress prints in terminal for every sample (added flush=True prints)
- Results overwrite by model+format+seed (no timestamps in filenames)
- Mock run first to verify harness before spending API credits
- Pilot results are preliminary — proper paper needs n≥20 samples and 3+ models
