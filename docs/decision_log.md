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
