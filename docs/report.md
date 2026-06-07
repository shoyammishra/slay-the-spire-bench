# slay-bench — Project Report

**Date:** 2026-06-07  
**Status:** Pilot complete; paper-grade runs in progress  
**Branch:** synergy-rework

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

> **Validity note:** llama-3.1-8b results are fully valid. Scout-17b run-level results (floors=5) are **invalid** — recorded before the map dead-end bug was fixed; a proper n=5 re-run is pending. qwen3-32b was attempted but **dropped** — no valid data could be collected on free-tier providers (see below).

### llama-3.1-8b-instant (Groq, valid)

| Metric | Structured | Raw |
|---|---|---|
| Turn damage ratio | 36.7% | 69.6% |
| Turn legal rate | 60% | 100% |
| Combat win rate | 100% | 100% |
| Combat HP ratio vs bot | 112.3% | 113.8% |
| Synergy archetype acc | 66.7% | 100% |
| Synergy card pick acc | 33.3% | 33.3% |
| Synergy removal acc | 0% | 0% |
| Run survival rate | 20% | 40% |
| Run avg floors reached | 13.4 / 15 | 13.4 / 15 |
| Run HP fraction (survivors) | 93.8% | 60.6% |
| Run draft coherence | 36.4% | 40.9% |
| **Overall score** | **47.5%** | **63.5%** |

### meta-llama/llama-4-scout-17b (Groq, run-level pending re-run)

| Metric | Structured | Raw |
|---|---|---|
| Turn damage ratio | 49.8% | 37.5% |
| Turn legal rate | 100% | 100% |
| Combat win rate | 100% | 100% |
| Combat HP ratio vs bot | 111.4% | 103.5% |
| Synergy archetype acc | 66.7% | 100% |
| Synergy card pick acc | 66.7% | 33.3% |
| Synergy removal acc | 0% | 0% |
| Run survival rate | 0% ⚠ | 0% ⚠ |
| Run avg floors reached | 5.0 ⚠ | 5.0 ⚠ |
| **Overall score** | **48.6%** | **45.5%** |

⚠ Run-level recorded before map dead-end fix; floors=5 is a simulator bug, not model performance. Re-run pending.

### qwen/qwen3-32b — DROPPED from the study

qwen3-32b was attempted but **excluded** because neither provider could run it viably:

- **OpenRouter (free tier):** too slow — ~30–80 tok/s, making a single n=5 run-level eval take 1.5–3 hours. The free tier was also exhausted partway, returning `402 Payment Required` (paid credits needed to continue).
- **Groq (free tier):** the 6000 tokens-per-minute (TPM) rate limit truncated qwen3's reasoning mid-`<think>`, so the model never emitted a complete, parseable answer. This produced a parse-failure cascade (0% across all dimensions).

Because qwen3 is a reasoning model that spends 600–4000 tokens thinking per call, it needs either paid OpenRouter (for speed) or paid Groq (for an uncapped TPM that won't truncate it). With only free-tier access available, no valid qwen3 data could be collected, so it has been removed from the results. Its result files have been deleted. Revisiting qwen3 (or another reasoning model) on a paid tier is left as future work.

### Key findings

**Raw format outperforms structured for reasoning tasks.** The clearest example: llama-3.1-8b turn damage ratio jumps from 36.7% to 69.6%, and archetype accuracy from 67% to 100%, when switching from JSON to natural English. The model's reasoning about game state is stronger when it can read prose.

**Structured format can be better for index-based tasks.** Scout-17b card pick accuracy: 66.7% structured vs 33.3% raw. When the output is a precise index into a list, JSON structure helps.

**Removal accuracy is 0% for all models in all formats — a genuine finding.** Expert heuristic says to remove "Strike" first (basics dilute draw quality as the deck improves). All models instead suggest removing Disarm, Battle Trance, or Bash — reasoning about card quality for the current archetype, not deck cycling. This is a systematic failure, not random noise, and is a clean paper result.

**Combat is easy; run-level is hard.** All tested models win 100% of isolated combats and beat the greedy bot on HP. Survival rate across a full 15-floor run drops to 20–40%, showing the difficulty lives in multi-decision consistency under accumulating state.

**Dimension difficulty ranking** (structured format, llama-3.1-8b):
1. Combat — 100% win rate, beats bot on HP
2. Synergy archetype — 67% structured, 100% raw
3. Turn-level damage ratio — 37% structured, 70% raw
4. Synergy removal — 0% all models all formats
5. Run-level survival — 20–40%

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
- **`--only synergy` ×4** — all 4 llama model+format combos need synergy re-run with the reworked classifier (payoff-weighted + archetype-targeted drafting)
- **Scout-17b run-level** — needs n=5 re-run after map+EventBus bug fixes
- **Scale to n≥20** — current pilot uses n=5; paper requires n≥20 with mean ± std

### What doesn't work / known limitations
- **qwen3-32b dropped** — free-tier OpenRouter too slow (~30–80 tok/s; 402 once exhausted) and free-tier Groq's 6000 TPM cap truncated its reasoning mid-`<think>`. No valid data; needs a paid tier to revisit.
- n=5 is too small for statistical claims; all numbers are directional only
- Scout-17b run-level results are invalid (pre-fix); pending re-run
- **Synergy archetype numbers invalid** — the heuristic was mislabeling decks (signature-card scoring fix landed late 2026-06-07); all archetype accuracy must be re-collected with `--n-synergy 20`

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
