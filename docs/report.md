# slay-bench — Project Report

> **Historical report — not current research claims.** The 2026-08-30 adversarial
> audit retired cross-task horizon, radar, and overall-score interpretations. See
> `research_audit/ADVERSARIAL_REVIEW.md`.

**Date:** 2026-06-07  
**Status:** Pilot complete; paper-grade runs in progress  
**Branch:** synergy-rework  
**Shareable version:** a polished standalone HTML report is at [`docs/report.html`](report.html) (open in any browser).

---

## 1. Project Overview

slay-bench measures how well large language models (LLMs) can plan and reason in the card game *Slay the Spire* (Ironclad character, Act 1 only). The game requires sequencing actions under resource constraints, managing a building deck over many decisions, and thinking several steps ahead — making it a useful, concrete planning benchmark.

The project has two parts:

1. **A Python simulator** that faithfully recreates the game's combat engine, map traversal, card drafting, and enemy behavior — deterministically, from a seed.
2. **A benchmark harness** that presents the simulator's state to an LLM, collects its decisions, and scores them against ground truth.

**Goal:** Establish a reproducible, multi-dimensional benchmark for LLM planning ability that goes beyond multiple-choice questions. The results will feed a research paper.

---

## 2. What Was Built

### Key files

| File | Purpose |
|---|---|
| `slay_bench/cards.py` | All Ironclad cards with exact effects |
| `slay_bench/enemies.py` | Enemies with AI intent patterns |
| `slay_bench/combat.py` | Turn engine: draw, play, block, enemy attack |
| `slay_bench/game_map.py` | Map generation and path traversal |
| `slay_bench/run_loop.py` | Full Act 1 floor-by-floor simulation |
| `slay_bench/rng.py` | 9 independent seeded RNG streams (Java-compatible) |
| `slay_bench/prompt_builder.py` | Game state → LLM prompt (two formats) |
| `slay_bench/benchmark.py` | 4-dimension harness + LLM interface |
| `slay_bench/visualize.py` | PNG charts and ASCII text reports |
| `run_benchmark.py` | CLI entry point |
| `tests/test_benchmark.py` | 40 unit tests (all passing, no API calls) |

### Benchmark dimensions

| # | Dimension | What it tests | Ground truth |
|---|---|---|---|
| 1 | Turn-level | Best card sequence in one turn | Exhaustive search (≤720 permutations) |
| 2 | Combat-level | Win a full fight turn-by-turn | Greedy bot baseline |
| 3 | Synergy | Identify deck archetype; pick best / remove worst card | Expert heuristic |
| 4 | Run-level | Survive all 15 floors + boss of Act 1 | Absolute (survival + progress) |

### Prompt formats

Every model is tested in two formats, on **identical seeds**, for a controlled ablation:

- **Structured** — compact JSON (card names, costs, HP numbers in dicts)
- **Raw** — verbose natural English describing the same state

### Architecture decisions

- **Energy deduction** happens only in `play_card()` — cards do not subtract energy themselves. This prevents double-charge bugs.
- **RNG** uses 9 independent LCG streams so map, enemies, draws, and rewards are all reproducible from a single seed.
- **EventBus** is cleared at the start of every combat so relic/power hooks don't accumulate across fights.
- **Illegal play scoring**: if any card in a turn sequence is illegal, the entire sequence scores `damage_ratio = 0`. Partial credit would reward random guessing.
- **Rate limits**: Groq 429s are retried with exponential backoff (1/2/4/8/16s); after 5 failures the run saves partial results instead of crashing.
- **`--only` flag**: any single dimension can be re-run and merged back into an existing result file, saving API credits when fixing one dimension.

---

## 3. Experiments & Results

All results use `seed=42`, n=5 turn, n=3 combat, n=3 synergy, n=5 run unless noted. Scout run-level used n=1 in early pilots.

> **Validity note:** ALL **run-level** rows below are **INVALID and must not be quoted** — they are from pre-fix code (predate the map dead-end, EventBus listener-stacking, and null-index fixes). Run-level currently has NO valid data; a clean pass is pending and blocked on free-tier Groq TPM (needs a paid tier). The non-run dimensions (turn, combat, synergy) for llama-3.1-8b are valid; scout-17b non-run dims are valid too. qwen3-32b was **dropped** — no valid data on free-tier providers (see below).

### llama-3.1-8b-instant (Groq, valid)

| Metric | Structured | Raw |
|---|---|---|
| Turn damage ratio | 36.7% | 69.6% |
| Turn legal rate | 60% | 100% |
| Combat win rate | 100% | 100% |
| Combat HP ratio vs bot | 112.3% | 113.8% |
| Synergy archetype acc (n=8) | 50.0% | 37.5% |
| Synergy card pick acc (n=8) | 100% | 62.5% |
| Synergy removal acc (n=8) | 25.0% | 12.5% |
| Run-level | — INVALID, excluded — | — INVALID, excluded — |

Synergy uses the hand-crafted n=8 fixtures (current). Run-level is excluded — its on-disk
numbers are from pre-fix code.

### meta-llama/llama-4-scout-17b (Groq, run-level pending re-run)

| Metric | Structured | Raw |
|---|---|---|
| Turn damage ratio | 49.8% | 37.5% |
| Turn legal rate | 100% | 100% |
| Combat win rate | 100% | 100% |
| Combat HP ratio vs bot | 111.4% | 103.5% |
| Synergy archetype acc (n=8) | 75.0% | 50.0% |
| Synergy card pick acc (n=8) | 75.0% | 100% |
| Synergy removal acc (n=8) | 25.0% | 12.5% |
| Run-level | — INVALID, excluded — | — INVALID, excluded — |

Synergy uses the hand-crafted n=8 fixtures (current). Run-level excluded (pre-fix data).

### qwen/qwen3-32b — DROPPED from the study

qwen3-32b was attempted but **excluded** because neither provider could run it viably:

- **OpenRouter (free tier):** too slow — ~30–80 tok/s, making a single n=5 run-level eval take 1.5–3 hours. The free tier was also exhausted partway, returning `402 Payment Required` (paid credits needed to continue).
- **Groq (free tier):** the 6000 tokens-per-minute (TPM) rate limit truncated qwen3's reasoning mid-`<think>`, so the model never emitted a complete, parseable answer. This produced a parse-failure cascade (0% across all dimensions).

Because qwen3 is a reasoning model that spends 600–4000 tokens thinking per call, it needs either paid OpenRouter (for speed) or paid Groq (for an uncapped TPM that won't truncate it). With only free-tier access available, no valid qwen3 data could be collected, so it has been removed from the results. Its result files have been deleted. Revisiting qwen3 (or another reasoning model) on a paid tier is left as future work.

### Key findings

**Models cannot recognise the Exhaust archetype.** On the hand-crafted n=8 fixtures, all eight Exhaust decks (across both models and both formats) were labelled "Aggro" — 0/8. Strength was also weak (2/8), while Block (7/8) and Aggro (8/8) were reliable. Models name an archetype only when its signature is a simple surface pattern; they miss strategies defined by a *mechanical interaction* (exhaust-for-payoff) even when the deck is full of signature cards. A clean, systematic knowledge gap.

**Naming the strategy and playing it are dissociated.** Card-pick accuracy is high (62.5–100%) even on decks the model cannot label — llama-3.1-8b (structured) picks the right card 100% of the time while scoring only 50% on archetype ID. Local card-quality judgement is strong; the abstract strategic label is weak.

**Removal accuracy is near-zero (12.5–25%).** Expert heuristic removes basic "Strike" first (basics dilute draw quality as the deck improves). Models instead suggest removing Disarm, Battle Trance, or Bash — reasoning about a card's standalone quality, not deck cycling. The small non-zero values come only from Block fixtures where the targets coincide. Systematic, not random.

**Prompt format matters, and which format wins depends on the task.** Raw helps reasoning: llama-3.1-8b turn damage ratio jumps 36.7%→69.6% and legal rate 60%→100%. Structured helps index-based output: scout-17b archetype ID is 75% structured vs 50% raw. Not a wash either way.

**Combat is saturated; difficulty lives upstream.** All tested models win 100% of isolated combats and beat the greedy bot on HP (103–114%). The hard part of planning is the longer-horizon work (archetype reasoning, deck-building), where scores drop sharply.

**Dimension difficulty ranking** (pilot, fixed-fixture synergy):
1. Combat — 100% win rate, beats bot on HP
2. Synergy card-pick — 62.5–100%
3. Synergy archetype ID — 37.5–75%, collapses on Exhaust/Strength
4. Turn-level damage ratio — 37–70%, format-sensitive
5. Synergy removal — 12.5–25%
   (Run-level: hardest in principle, but NO valid data yet — excluded.)

---

## 4. Key Decisions

| Decision | Rationale |
|---|---|
| Illegal turn sequences score `damage_ratio = 0` | Partial credit rewards random guessing; zero enforces legal play as a prerequisite |
| Energy deducted only in `play_card()` | Prevents double-charge bugs; single source of truth |
| `avg_hp_fraction` averaged over survivors only; deaths get `avg_progress` (floors/15) | Averaging HP=0 deaths conflates "died early" with "barely survived"; separating gives cleaner signal |
| Results overwrite by model+format+seed (no timestamps) | Re-runs are reproducible by seed; timestamps add no information and clutter the results folder |
| `EventBus.clear()` at start of each combat | Listener stacking bug made the player progressively invincible across a run (relic/power handlers registered multiple times) |
| Synergy eval uses archetype-targeted drafting | Greedy-first-pick decks had no real archetype, making archetype accuracy meaningless. Cycling Strength→Block→Exhaust→Aggro targets produces coherent, evaluable decks |
| `--only` flag for single-dimension re-runs | Dimensions are independent; forcing a full re-run to fix one wastes API credits |
| Exponential backoff on rate-limit errors | Uncaught 429s mid-run discarded all completed work; backoff recovers transient throttling and saves partial results on exhaustion |

---

## 5. Current Status

### What works
- Full simulator: combat, map traversal, card drafting, enemies, relics, events, potions
- All 4 benchmark dimensions with ground truth scoring
- Two prompt formats (structured JSON, raw English) on identical seeds
- Groq provider (llama models) and OpenRouter provider (reasoning models)
- `<think>` block stripping for reasoning models
- Rate-limit retry with partial-result saving
- `--only` flag for efficient single-dimension re-runs
- 40 unit tests, all passing

### What's pending
- **Run-level (all combos)** — no valid data yet; on-disk numbers are pre-fix. First priority for a clean pass; blocked on free-tier Groq TPM (needs paid tier).
- **Scale to n≥20** — current pilot uses small n; paper requires n≥20 with mean ± std and ≥5 seeds.
- **3rd model from another family** — current lineup is two Llama models; cross-family signal needed.
- See [`docs/roadmap.md`](roadmap.md) → "Paper-grade run matrix" for the full checklist.

### What doesn't work / known limitations
- **qwen3-32b dropped** — free-tier OpenRouter too slow (~30–80 tok/s; 402 once exhausted) and free-tier Groq's 6000 TPM cap truncated its reasoning mid-`<think>`. No valid data; needs a paid tier to revisit.
- Small n (3–8) is too small for statistical claims; all numbers are directional only
- **Run-level has no valid data** — pre-fix numbers excluded; clean pass pending (blocked on free-tier TPM)
- Synergy n=8 is a fixed deterministic set — real signal but no sampling variance; needs more fixtures or k-sampling for error bars

---

## 6. How to Run

**Prerequisites:** Python 3.10+, `pip install groq python-dotenv`. `.env` file with `GROQ_API_KEY` and `OPENROUTER_API_KEY`.

```powershell
# Verify harness works (instant, no API, no credits)
python run_benchmark.py --provider mock --model mock --format structured --seed 42

# llama-3.1-8b-instant — structured (Groq)
python run_benchmark.py --provider groq --model llama-3.1-8b-instant --n-turn 5 --n-combat 3 --n-synergy 3 --n-run 5 --format structured

# llama-3.1-8b-instant — raw (Groq)
python run_benchmark.py --provider groq --model llama-3.1-8b-instant --n-turn 5 --n-combat 3 --n-synergy 3 --n-run 5 --format raw

# llama-4-scout-17b — structured (Groq)
python run_benchmark.py --provider groq --model meta-llama/llama-4-scout-17b-16e-instruct --n-turn 5 --n-combat 3 --n-synergy 3 --n-run 5 --format structured

# llama-4-scout-17b — raw (Groq)
python run_benchmark.py --provider groq --model meta-llama/llama-4-scout-17b-16e-instruct --n-turn 5 --n-combat 3 --n-synergy 3 --n-run 5 --format raw

# NOTE: qwen3-32b (reasoning model) was dropped — free-tier OpenRouter is too slow
# and free-tier Groq's TPM cap truncates its reasoning. Revisiting needs a paid tier.

# Re-run only synergy (merges other dims from existing JSON on disk)
python run_benchmark.py --provider groq --model llama-3.1-8b-instant --format structured --only synergy
```

**Output files** (per run, overwrites if same model+format+seed):
- `results/<model>_<format>_seed42.json` — raw scores
- `results/<model>_<format>_seed42.txt` — human-readable ASCII report
- `results/<model>_<format>_seed42.png` — 2×2 bar chart
- `results/<model>_<format>_seed42_radar.png` — spider chart

**Speed notes:**
- llama models on Groq: fast (~400–1000 tok/s on paid tier)
- Reasoning models (e.g. qwen3) on free-tier OpenRouter: slow (~30–80 tok/s); run-level takes 1.5–3 hours for n=5 — and free-tier Groq truncates them. A paid tier is required to benchmark them viably.
- Always run mock first to catch bugs before spending credits
