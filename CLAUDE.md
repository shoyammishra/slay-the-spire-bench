# slay-bench — Project Context for Claude

## What This Is
A Python simulator + LLM benchmark harness for Slay the Spire (Ironclad + Silent; Acts 1–3).
Tests LLM planning ability across 4 dimensions: turn-level, combat-level, synergy, and run-level.
GitHub: https://github.com/shoyammishra/slay-the-spire-bench (public)

## Security — CRITICAL
- `.env` contains real API keys for BOTH Groq and OpenRouter. It is gitignored. NEVER commit it.
- Never share or print any API key from `.env`.

## Active Context

- **Status:** In progress — synergy REDESIGNED to hand-crafted decks + RE-RUN at n=8 (done). Run-level re-run BLOCKED by free-tier Groq TPM (see below). qwen3 DROPPED. **A* acceptance changes IMPLEMENTED (2026-06-10):** Silent character + multi-act + temperature + multi-seed CLI — all code-side. Awaiting paid Groq for actual runs.
- **Current task:** Run-level n=3 re-run is blocked on free Groq's 6000 TPM cap (run-level is too token-heavy — hundreds of stateful calls; one prompt alone requests ~3367 tok and trips 429 on nearly every call). Need PAID Groq Dev tier to scale run-level + everything else to n≥20. Synergy n=8 already re-run with hand-crafted fixtures.
- **⛔ ALL existing run-level numbers INVALID (2026-06-07):** the run-level data in `results/*.json` (llama 20%/40%, 13.4 floors; scout floors=5) is from OLD pre-fix code (predates map dead-end + EventBus stacking + `_safe_int` fixes). IGNORE it — run-level has NO valid data yet. A clean pass is pending + blocked on free TPM. (report.md/findings.md/report.html now all EXCLUDE run-level — do not re-introduce the old 13.4/20–40% figures.)
- **⚠️ Run-level blocked on free tier (2026-06-07):** `--only run --n-run 3` on llama-3.1-8b hit the 6000 TPM wall — structured completed 0 runs (kept prior valid run results via partial-save), raw hung in an infinite retry loop and was Ctrl-C'd. Free Groq sustains ~2 calls/min; a single run needs dozens-to-hundreds → infeasible. Partial-save logic worked: existing run-level + fresh synergy results both intact. **Unblock = paid Groq Dev tier** (the 429 error itself recommends it). This is the same lever needed for paper-grade n≥20.
- **Paper-grade gap (discussed 2026-06-07):** all current numbers are PILOT-grade. Synergy n=8 is real signal (12.5pp steps, not 33pp) but DETERMINISTIC (8 fixed fixtures = a fixed mini-exam, no sampling variance/std). Turn (n=5), combat (n=3), run (n=3) still move in coarse steps. Paper needs: (1) n≥20–30 per dim, (2) multiple seeds, (3) a 3rd model from another family (ideally a frontier/reasoning model — the dropped qwen3 left no reasoning model), (4) mean±std reporting. For synergy variance: add more fixtures (4–5/archetype → n=16–20) OR sample each fixture k times at temp>0 for error bars. Harness is paper-READY; blocker is compute/credits, not code.
- **Key files:** `slay_bench/benchmark.py`, `slay_bench/run_loop.py`, `run_benchmark.py`
- **Completed this session (2026-06-07):** (1) **Synergy REDESIGNED** — RNG drafts dropped; now 8 hand-crafted `_SYNERGY_FIXTURES` decks for clean ground truth (removed dead `_archetype_draft_fn`). (2) `_classify_archetype_confident()` (signature-only labels + ambiguity) + per-sample JSON audit. (3) **Combat null/string index crash fixed** — `_safe_int()` in both combat loops. (4) **Robust Groq 429 handling** — typed detection + `max_retries=0` + 6-attempt backoff. (5) qwen3 DROPPED + files deleted. All tests pass. (6) **Synergy n=8 RE-RUN done** — real numbers folded into all docs (Exhaust 0/8, name-vs-play dissociation). (7) **`docs/report.html`** — standalone shareable pilot report for the professor. (8) **All run-level numbers flagged INVALID** (pre-fix code).
- **⚠️ qwen3-32b DROPPED (2026-06-07):** could not get valid data on free tiers. **OpenRouter free** is too slow (~30–80 tok/s; n=5 run-level = 1.5–3h) and returned **402 Payment Required** once exhausted. **Groq free** 6000 TPM truncates its reasoning mid-`<think>` → parse-failure cascade (0% everywhere). A reasoning model needs a PAID tier (paid OpenRouter for speed, or paid Groq for uncapped TPM). qwen3 result files deleted. Revisit = future work. See docs/report.md + docs/notes.md.
- **✅ Synergy DONE (n=8 hand-crafted fixtures):** real numbers collected for all 4 combos and folded into all docs + `docs/report.html`. Key result: Exhaust 0/8 (always "Aggro"), Strength 2/8, Block 7/8, Aggro 8/8; name-vs-play dissociation; removal 12.5–25%. Earlier RNG-draft synergy numbers (67%/100%) are RETIRED.
- **Next:** Run-level is the only remaining dimension with no valid data — clean pass blocked on free TPM (needs paid Groq). Then scale all dims to n≥20 + ≥5 seeds + a 3rd-family model. See `docs/roadmap.md` run matrix.
- **Provider note:** llama models on Groq. Reasoning models (qwen3 etc.) require a paid tier — do not benchmark on free tiers.
- **⚠️ GOTCHA — running process uses startup code:** a launched Python run loads `benchmark.py` once at startup; editing it does NOT affect an in-flight run. Re-launch or use `--only` to pick up code changes.
- **Remaining run plan:** (1) ~~synergy n=8 ×4~~ DONE; (2) `--only run --n-run ≥20` ×4 — clean run-level pass, blocked on free TPM (needs paid Groq); (3) scale turn/combat to n≥20 + ≥5 seeds; (4) add a 3rd-family model; (5) merge `synergy-rework` → main. Full checklist in `docs/roadmap.md`.
- **Speed:** Paid Groq (~400–1000 tok/s, no TPM cap) is the real speedup lever for n≥20 — see docs/notes.md.
- **➡️ Next steps = the paper-grade run matrix in `docs/roadmap.md`** (models, per-dim n≥20, ≥5 seeds, both formats, mean±std, run order). When a paid Groq Dev tier is available: run-level first (no valid data), then scale turn/combat, then expand synergy, then add a 3rd-family model.
- **Completed 2026-06-09:** Drafted the **Related Work** section in `docs/draft.md` — positions slay-bench against PlanBench, NATURAL PLAN, TravelPlanner, TextWorld/BabyAI/GameBench/AgentBench. Core thesis: prior planning benchmarks test a *single* decision horizon; slay-bench embeds four nested horizons (turn→combat→synergy→run) in one shared simulator so per-dimension score differences isolate planning-horizon effects, not domain shift. Citations still need full venue/year details before submission.
- **⚠️ Completed 2026-06-09 — NOVELTY REALITY CHECK (`docs/novelty_and_related_work.md`):** Web research found **slay-bench is NOT the first LLM+Slay-the-Spire work.** Direct prior art a reviewer WILL find: (1) **"Language-Driven Play"** (Bateni & Whitehead, **FDG 2024**, MiniSTS engine) — and they ALREADY report that randomizing card names *improves* LLM play, which **overlaps our synergy "name-vs-play dissociation"** → must frame ours as confirming/quantifying, not discovering. (2) **Orak** (arXiv 2506.03610, 2025) — 12-game LLM benchmark that *includes STS*. (3) Modular/hybrid STS combat agents; UrzaGPT (MTG). **Real novelty that survives:** single-domain **multi-horizon decomposition with a per-horizon ground-truth oracle** (every other game bench scores whole-game play [Orak/GameBench] or maps one-game-per-skill [DSGBench/SmartPlay]); **optimality-relative scoring** (vs win/loss); **seed-matched format ablation**. **Top-tier viability:** framing is benchmark-track-shaped but execution is pilot-grade → workshop now; NeurIPS D&B needs n≥20–30, ≥5 seeds, 3+ model families incl. a reasoning model, and **valid run-level data** (currently missing). **Generalizability fix for "too narrow":** reframe contribution as a reusable *method*; cheapest breadth = add another STS character (Silent/Defect/Watcher, same engine); cite Monster Train / Into the Breach / NetHack as next instantiations. Full ranked game table + ready-to-send professor paragraph in the doc. Direct-STS prior work now also cited in `docs/draft.md` Related Work.

## Docs
Detail lives in `docs/` — not here.
- `docs/roadmap.md` — milestones, timeline
- `docs/decision_log.md` — architecture & design decisions
- `docs/experiment_log.md` — runs, configs, results, failures
- `docs/findings.md` — observations, hypotheses
- `docs/notes.md` — scratch pad
- `docs/design.md` — architecture, invariants, interfaces
- `docs/draft.md` — paper draft
- `docs/novelty_and_related_work.md` — novelty vs prior STS/game/planning work, top-tier viability, generalizability + candidate games

## Project Structure
```
slay_bench/
  cards.py          — All Ironclad cards with exact effects
  cards_silent.py   — All Silent cards (~73), archetypes, SILENT_POOL, SILENT_SYNERGY_FIXTURES
  enemies.py        — Enemies: Cultist, JawWorm, AcidSlimeL, SpikeSlimeL, etc.
  enemies_act2.py   — Act 2/3 enemies (Gremlin, Book of Stabbing, etc.)
  combat.py         — Turn engine: draw, play, enemy attack, block; powers reset per combat
  map_gen.py        — Map generation, node types, path traversal
  run_loop.py       — Full act simulation floor-by-floor
  rng.py            — Java-compatible LCG, 9 independent seeded streams
  prompt_builder.py — GameState → text prompt; system_prompt(kind, character)
  benchmark.py      — 4-dimension benchmark harness + LLM interface; character/temperature/n_acts
  visualize.py      — PNG charts + ASCII text reports from results
  relics.py         — Relic base class (on_pickup + register split); BurningBlood, RingOfTheSnake, …
  relics_full.py    — Full relic registry; 20 relics corrected to on_pickup for non-idempotent effects
  rewards.py        — card_pool_for(state): character-aware card pool; generate_card_reward
  nodes.py          — _obtain_relic calls on_pickup then register; shop uses card_pool_for
  enums.py          — PowerId entries for Silent powers added
  state.py          — CombatState.attacks_played_this_turn, .discarded_this_turn; GameState.character
  powers.py         — Silent power hooks (Noxious Fumes, Infinite Blades, Wraith Form, etc.)
  __init__.py       — new_game(seed, character); CHARACTERS tuple; new_ironclad_game (compat)
run_benchmark.py    — CLI entry point; --character --acts --temperature --llm-routing --seeds
tests/
  test_benchmark.py — 24 harness tests (MockLLM, no API calls)
  test_combat.py    — 10 combat-engine tests
  test_run.py       — 13 map/run/relic tests
  (47 total, all passing; run each file directly — no pytest installed. On Windows consoles
   set PYTHONIOENCODING=utf-8 first or the box-drawing prints crash 2 tests spuriously.)
results/            — Output files (gitignored): .json, .txt, .png, _radar.png
docs/               — Project documentation (roadmap, decisions, findings, draft)
```

## Running the Benchmark
```powershell
# Mock run (instant, no API)
python run_benchmark.py --provider mock --model mock --format structured --seed 42

# Real run — structured format, Ironclad, Act 1 (default)
python run_benchmark.py --provider groq --model llama-3.1-8b-instant --n-turn 5 --n-combat 3 --n-synergy 8 --n-run 5 --format structured

# Silent character
python run_benchmark.py --provider groq --model llama-3.1-8b-instant --character silent --n-synergy 8 --format structured

# Multi-act run (Acts 1→2→3)
python run_benchmark.py --provider groq --model llama-3.1-8b-instant --acts 3 --n-run 5 --format structured

# Multi-seed run (mean ± std — paper-grade)
python run_benchmark.py --provider groq --model llama-3.1-8b-instant --seeds 42 43 44 45 46 --n-turn 20 --n-combat 20 --n-synergy 20 --n-run 5 --format structured

# Sampling temperature (for synergy variance / error bars)
python run_benchmark.py --provider groq --model llama-3.1-8b-instant --temperature 0.7 --only synergy --n-synergy 20

# LLM routing (LLM picks paths/rest/boss relics in run-level instead of greedy)
python run_benchmark.py --provider groq --model llama-3.1-8b-instant --llm-routing --only run --n-run 5

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
| 3 | Synergy | Archetype ID, best pick, worst removal | Hand-crafted archetype decks (20/character × 2 characters = 40 total) |
| 4 | Run-level | Survive Acts 1–N (15 floors/act) | Absolute (survival + progress per act) |

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
- **Relic lifecycle split (2026-06-10):** `Relic.on_pickup(state)` = one-time effects at acquisition (max HP, energy/turn, deck mutations). `Relic.register(state)` = subscribe to events only — called at every combat start (bus is cleared first), so only idempotent subscriptions go here. `_obtain_relic()` in nodes.py calls both in order. This fixes relic-stacking across a run.
- **Powers reset per combat (2026-06-10):** `start_combat()` does `state.player.powers = {}` — relic-granted powers (Vajra/Shuriken/etc.) re-apply via their COMBAT_START hooks. Demon Form, Flex, etc. are correctly per-combat.
- **Poison bypasses block (2026-06-10):** poison tick is `enemy.hp -= amt` directly (not through block). Matches real StS mechanics.
- **Character-aware factory:** `new_game(seed, character)` creates the correct starter deck + relic. `make_card_for(character, name)` dispatches to Ironclad or Silent. `card_pool_for(state)` returns the correct rarity pool. `system_prompt(kind, character)` injects character name into system prompts.
- **Multi-act run:** `RunEvaluator.evaluate(state, n_acts=1)` plays acts 1→n_acts in sequence. `_act_transition()` does full heal + LLM (or greedy) boss relic pick between acts. `RunScore.acts_completed` + `RunScore.total_floors` (16×n_acts) track cross-act progress.
- **Synergy fixtures:** `_SYNERGY_FIXTURES` (20 Ironclad) + `SILENT_SYNERGY_FIXTURES` (20 Silent) in `_SYNERGY_FIXTURES_BY_CHAR`. Expanded from 8 → 20 (5/archetype) so n≥20 synergy runs are possible without repeating.
- **Temperature:** all evaluators accept `temperature` kwarg — passed through to `LLMInterface.complete`. Use `--temperature 0.7` for sampling variance / error bars.

## Bugs Fixed (session history)
- **2026-06-10 full bug sweep (logic + code), post-A*-changes.** Engine: (1) **player debuff timing** — Weak/Vuln/Frail/Intangible ticked at end of PLAYER turn, before enemies attacked, so Wraith Form/Apparition Intangible never covered an enemy attack and Incense Burner did literally nothing; now ticked at end of ROUND with a StS-style `just_applied` guard (CombatState.enemy_phase + _apply_power marks enemy-applied debuffs to skip their first tick). This CHANGES combat dynamics — pre-sweep combat numbers not comparable. (2) Double Tap popped ALL stacks for one attack → consumes 1/attack. (3) Pain curse triggered from draw/discard piles → hand only. (4) Thorns retaliated against Combust/Juggernaut/etc. → attack damage only (`from_attack` param). (5) Pen Nib was +999 Vigor → proper 2× via one-shot `_pen_nib_ready` consumed in `_deal_damage`. Relics: (6) **Inserter permanently ramped `energy_per_turn` every 2 turns across the whole run** (same stacking class the on_pickup/register split was meant to kill) → transient energy + removed from boss pools (Defect-only). (7) Omamori recharged 2 charges every combat → per-run class attr. (8) Centennial Puzzle never reset → per-combat. (9) Sundial/The Abacus fired per card DRAW → new `Event.SHUFFLE` emitted on reshuffle. (10) Pocketwatch drew 3 at TURN_END straight into the discard → queues NEXT_TURN_DRAW. (11) Cursed Key cursed on EVERY relic (incl. its own pickup + boss relics) → only chests (source="chest" tag on RELIC_OBTAINED). (12) Pandora's Box used the Ironclad pool for Silent → character-aware. (13) Dead Branch bypassed the hand limit. (14) Ectoplasm/Sozu flags were never enforced → gold_reward/potion_drop respect them (RNG still rolled for seed-stability). Harness: (15) **`run_turn_eval`/`run_combat_eval` didn't pass `character`** — Silent got Ironclad system prompts. (16) **Turn evaluator crashed on string/null indices in `plays`** (TypeError) and accepted negative indices as end-of-hand plays → sanitized, non-ints/negatives = illegal. (17) **Synergy evaluator crashed on `null` archetype/worst_card_name** (None.strip) → coerced; string `"1"` best_card_index now scored as 1. (18) `RunScore.parse_errors`/`llm_calls` were never populated (combat errors lost) → `_llm_combat` accumulates into counters. (19) "Dead Branch" listed as a CARD in Exhaust archetype tables (it's a relic — never matched) → moved to `_relic_archetype_hints`. CLI: (20) **multi-seed `_aggregate_summaries` used wrong metric key names** (`damage_ratio`/`hp_ratio`/`parse_ok` vs real `avg_damage_ratio`/`avg_hp_ratio`/`parse_ok_rate`) — every affected mean came out `null`; would have silently gutted the first paid mean±std run. (21) Multi-seed path claimed per-seed charts were saved but never called `save_all`. 7 regression tests added (47 total).
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
