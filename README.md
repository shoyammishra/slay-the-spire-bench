# slay-bench

A Python simulator + LLM benchmark harness for **Slay the Spire** (Ironclad character only).
It measures how well large language models plan in a complex, stateful game across four
distinct reasoning dimensions.

> **Status: pilot-grade.** Current numbers come from small samples (n=3–8) on a single seed
> and are *directional, not statistically significant*. See [Limitations](#limitations).

## What it tests

The harness drives an LLM through a faithful re-implementation of Slay the Spire's Act 1 and
scores it on four dimensions:

| # | Dimension | What it tests | Ground truth |
|---|-----------|---------------|--------------|
| 1 | **Turn-level** | Best card sequence in a single turn | Exhaustive search (≤720 permutations) |
| 2 | **Combat-level** | Winning a full fight turn-by-turn | Greedy bot baseline |
| 3 | **Synergy** | Archetype ID, best card pick, worst-card removal | 8 hand-crafted archetype decks |
| 4 | **Run-level** | Surviving all 15 floors of Act 1 | Absolute (survival + progress) |

Each dimension is run under **two prompt formats** — `structured` (compact JSON game state)
and `raw` (verbose natural-English description of the same state) — given identical RNG seeds
so the comparison is fair.

## Key findings (pilot)

From the synergy dimension (n=8 hand-crafted fixtures, llama-3.1-8b + llama-4-scout-17b):

- **Surface patterns are easy, mechanical interactions are hard.** Models reliably name
  Aggro (8/8) and Block (7/8) — archetypes identifiable by counting card types — but score
  **0/8 on Exhaust**, an archetype defined by a *generator + payoff interaction* rather than a
  card-frequency signal. Every model, in every format, mislabels Exhaust decks as "Aggro."
- **Name-vs-play dissociation.** Models often pick the right card (62.5–100%) even for decks
  they cannot correctly label — recognising a good *card* without recognising the *strategy*.
- **Removal is near-random** (12.5–25%). Expert play removes a basic Strike first (basics
  dilute draw quality as the deck improves); models instead cut situational cards.
- **No format wins outright.** `structured` helps archetype ID; `raw` helps card-picking.
  Format is a variable worth controlling for in any LLM-planning study.

Full results: [`docs/report.html`](docs/report.html) (polished, shareable) ·
[`docs/findings.md`](docs/findings.md) (detail) · [`docs/experiment_log.md`](docs/experiment_log.md).

## Install

```bash
pip install -r requirements.txt
```

Requires Python 3.10+. To run against real models, create a `.env` file (gitignored) with:

```
GROQ_API_KEY=your_groq_key
OPENROUTER_API_KEY=your_openrouter_key   # optional
```

## Usage

```bash
# Mock run — instant, no API calls (verify the harness first)
python run_benchmark.py --provider mock --model mock --format structured --seed 42

# Real run — structured prompt format
python run_benchmark.py --provider groq --model llama-3.1-8b-instant \
    --n-turn 5 --n-combat 3 --n-synergy 8 --n-run 5 --format structured

# Raw prompt format (ablation)
python run_benchmark.py --provider groq --model llama-3.1-8b-instant \
    --n-turn 5 --n-combat 3 --n-synergy 8 --n-run 5 --format raw

# Re-run a single dimension (merges the others from the previous run on disk)
python run_benchmark.py --provider groq --model llama-3.1-8b-instant \
    --format structured --only synergy
```

Each run writes to `results/` (gitignored): a `.json` of raw scores, a `.txt` ASCII report,
and `.png` bar/radar charts.

## Project structure

```
slay_bench/
  cards.py          Ironclad cards with exact effects
  enemies.py        Act 1 enemies (Cultist, Jaw Worm, slimes, ...)
  combat.py         Turn engine: draw, play, enemy attacks, block
  map_gen.py        Map generation, node types, path traversal
  run_loop.py       Full-act simulation, floor by floor
  rng.py            Java-compatible LCG, 9 independent seeded streams
  prompt_builder.py GameState → text prompt (structured JSON or raw English)
  benchmark.py      4-dimension benchmark harness + LLM interface
  visualize.py      PNG charts + ASCII reports
run_benchmark.py    CLI entry point
tests/              Unit tests (no API calls)
docs/               Roadmap, decisions, findings, paper draft
```

The simulator is deterministic: the same seed reproduces the same map, enemies, draws, and
rewards every time.

## Limitations

This is a **pilot study**, not a finished benchmark:

- **Small samples** (n=3–8 per dimension) — numbers are directional; no significance claimed.
- **Single seed** (42) — multiple seeds are needed to rule out RNG artefacts.
- **Run-level has no valid data yet** — a clean pass is blocked on free-tier API rate limits
  (the dimension is too token-heavy for free Groq's TPM cap).
- **Two models, one family** (both Llama). A reasoning model and a third model family are
  needed for stronger claims.

Reaching paper-grade results requires n≥20–30, multiple seeds, mean±std reporting, and an
additional model family — the harness is ready; the blocker is compute/credits, not code.
See [`docs/roadmap.md`](docs/roadmap.md) for the full run matrix.

## License

MIT — see [LICENSE](LICENSE).
