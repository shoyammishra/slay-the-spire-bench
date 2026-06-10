# Decision Log

## 2026-06-07 — Illegal play scoring
**Decision:** If any card in a turn sequence is illegal, `damage_ratio = 0` (zero, not partial credit).
**Why:** Partial credit would reward models that guess randomly and happen to play some valid cards. Zero enforces that legal play is a prerequisite, not an add-on.

## 2026-06-07 — Single source of truth for energy deduction
**Decision:** `play_card()` in `combat.py` is the only place energy is deducted. Cards do NOT subtract energy themselves.
**Why:** Double-charge bug — cards were subtracting energy inside their own `play()` AND `play_card()` was also subtracting. Centralizing prevents this class of bug entirely.

## 2026-06-07 — avg_hp_fraction averaged over survivors only
**Decision:** Deaths contribute 0 to survival_rate but are excluded from avg_hp_fraction. Added avg_progress (floors/15) for partial credit on death.
**Why:** Averaging HP fraction over deaths (where HP=0) would conflate "died early" with "barely survived." Separating the two metrics gives cleaner signal.

## 2026-06-07 — Results overwrite by model+format+seed (no timestamps)
**Decision:** Output files named `<model>_<format>_seed<N>.*` — re-runs overwrite.
**Why:** Easier to compare runs; no accumulation of stale files. Seed makes runs reproducible, so timestamps add no information.

## 2026-06-07 — EventBus.clear() at start of each combat
**Decision:** Clear all listeners at the top of `start_combat`.
**Why:** Listener stacking bug — handlers accumulated across combats in a run, making player progressively invincible. Clearing ensures each combat starts with exactly one registration per relic/power.

## 2026-06-07 — Synergy eval uses greedy card_choice_fn to build a real deck
**Decision:** `run_synergy_eval` now passes `_greedy_pick` (first non-curse offer) as `card_choice_fn` to `run_act`, so the deck has real archetype-defining cards at eval time.
**Why:** With `card_choice_fn=None`, no cards were ever added. The synergy snapshot was always the 10-card starter deck, making `_classify_archetype` always return "Aggro" by default — zero signal. Expert label and model answer were both noise.

## 2026-06-07 — `--only` flag for partial benchmark runs
**Decision:** `run_benchmark.py` accepts `--only turn|combat|synergy|run` to run a single dimension. Skipped dims produce `null` in the summary JSON; merge logic fills them from the previous file on disk.
**Why:** Dimensions are fully independent (separate seed ranges, fresh game state each). Forcing a full re-run to fix one dimension wastes API credits and time.

## 2026-06-07 — Exponential backoff on Groq 429
**Decision:** Retry 429s up to 5 times (1/2/4/8/16s), then raise `RateLimitExhausted` which saves partial results.
**Why:** Uncaught 429 mid-run discarded all completed work. Backoff recovers from transient throttling; graceful degradation saves partial data.

## 2026-06-07 — Synergy ground truth = hand-crafted fixtures, not RNG drafts
**Decision:** Replaced RNG-drafted Act-1 decks in `run_synergy_eval` with fixed hand-crafted `_SYNERGY_FIXTURES` (initially 8, 2/archetype; each with 4–5 signature cards, a basic-Strike removal target, and an on-archetype best-pick offer). Removed the dead `_archetype_draft_fn`.
**Why:** Act-1 RNG decks are too small/RNG-limited to have a crisp archetype — only ~3/10 came out confidently labeled, all model/format combos collapsed to identical archetype_acc=0.333, and even "confident" labels were debatable. Fixed decks give deterministic, unambiguous ground truth.

## 2026-06-07 — Archetype labels decided by signature cards only (+ ambiguity)
**Decision:** Added `_classify_archetype_confident()` — the expert label counts only `_ARCHETYPE_PAYOFFS` signatures (+relics); a deck is labeled only if one archetype uniquely owns the most signatures, else `archetype_correct=None` (excluded from accuracy). Per-sample labels persisted in the JSON for audit.
**Why:** The broad `_ARCHETYPES` list miscategorized generic commons (Armaments/Headbutt → "Exhaust"), producing archetype_acc=0 on all combos with parse_ok=1.0 — the heuristic was wrong, not the models.

## 2026-06-07 — qwen3-32b dropped from the study
**Decision:** No reasoning model in the current model set; result files deleted. Revisit on a paid tier as future work.
**Why:** Infrastructural, not capability: Groq free's 6000 TPM truncates its `<think>` block (parse-failure cascade, 0% everywhere); OpenRouter free is ~30–80 tok/s and returned 402 when credits ran out. Reporting those 0%s as model performance would be wrong.

## 2026-06-10 — Relic lifecycle split: on_pickup vs register
**Decision:** `Relic.on_pickup(state)` = one-time effects at acquisition (max HP, energy/turn, deck mutations); `Relic.register(state)` = event subscriptions only, re-called at every combat start after the bus is cleared. `_obtain_relic()` calls both in order; 20 relics in `relics_full.py` moved their non-idempotent effects to `on_pickup`.
**Why:** With a single `register()` called per combat, non-idempotent effects (e.g. +max HP) stacked every combat across a run — same bug class as the EventBus stacking, one level up.

## 2026-06-10 — Powers reset per combat; poison bypasses block
**Decision:** `start_combat()` does `state.player.powers = {}`; relic-granted powers re-apply via COMBAT_START hooks. Poison ticks subtract HP directly, ignoring block.
**Why:** Per-combat powers (Demon Form, Flex) must not leak across fights; relic powers must not stack. Poison-through-block matches real Slay the Spire mechanics — required for Silent fidelity.

## 2026-06-10 — Silent as second character (same engine)
**Decision:** Added the full Silent card set (~73 cards), powers, pool, and 20 hand-crafted synergy fixtures (5/archetype: Poison/Shiv/Discard/Block). `new_game(seed, character)` factory; `make_card_for`/`card_pool_for`/`system_prompt` dispatch on character. Ironclad fixtures also expanded 8 → 20.
**Why:** Cheapest credible answer to the "too narrow" generalizability critique (see novelty doc): a second character reuses the whole engine while doubling the synergy fixture pool to 40 and enabling n≥20 synergy runs without repeating fixtures.

## 2026-06-10 — Multi-act runs with full-heal act transitions
**Decision:** `RunEvaluator.evaluate(state, n_acts)` plays acts 1→n; `_act_transition()` does a full heal + boss relic pick (LLM if `--llm-routing`, else greedy). `RunScore.acts_completed` / `total_floors` (16×n_acts) track cross-act progress.
**Why:** Act 1 alone caps the run-level horizon at ~16 decisions; Acts 1–3 triple it. Full heal between acts is a simplification (real StS heals partially) accepted to keep act difficulty independent.

## 2026-06-10 — Temperature + multi-seed CLI for paper-grade statistics
**Decision:** All evaluators take a `temperature` kwarg (`--temperature`); `--seeds 42 43 …` runs the benchmark per seed, saves per-seed outputs, and writes a combined JSON with mean ± std.
**Why:** The paper needs error bars. Synergy fixtures are deterministic — variance must come from sampling (temp>0, k completions/fixture) or seed sweeps; both are now one flag away.
