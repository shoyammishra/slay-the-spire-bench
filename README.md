# slay-bench

A deterministic Python simulator and LLM benchmark for **Slay the Spire**. It measures
planning across four horizons for Ironclad and Silent, with Acts 1–3 implemented.

The benchmark compares two semantically matched prompt formats—compact structured JSON
and raw English—on identical RNG seeds.

| Horizon | Task | Reference |
|---|---|---|
| Turn | Choose the best legal card sequence | Exhaustive legal-sequence search |
| Combat | Play a complete fight | Outcome plus greedy-policy HP anchor |
| Synergy | Identify archetype and choose a card | Fixed expert-labelled fixtures |
| Run | Traverse an act or multi-act run | Survival, progress, floors, and coherence |

The project has a complete seven-configuration open-model matrix through
Qwen3-235B-A22B-FP8 and a regenerated statistical rigor analysis. The strongest 235B
gain over Qwen3-32B is card selection, not a uniform horizon extension. Removal-v1 is
quarantined because every fixture used the same `Strike` target. See
[the handoff](docs/handoff.md), [experiment log](docs/experiment_log.md),
[findings](docs/findings.md), and [statistics report](docs/stats_report.md) for current,
caveated results. Older HTML reports are snapshots, not live status.

## Install

Python 3.10 or newer is required.

```bash
python -m pip install -r requirements.txt
```

Hosted providers read credentials from a gitignored `.env`:

```text
GROQ_API_KEY=...
OPENROUTER_API_KEY=...
```

OpenAI-compatible local servers such as vLLM, TGI, and Ollama use `--provider local`
and `--base-url`; they do not require a hosted-provider key.

## Usage

Run the instant no-API pipeline first:

```bash
python run_benchmark.py --provider mock --model mock --format structured --seed 42
```

Run a hosted model:

```bash
python run_benchmark.py --provider groq --model llama-3.1-8b-instant \
  --n-turn 5 --n-combat 3 --n-synergy 8 --n-run 5 \
  --character ironclad --format structured
```

Run a local OpenAI-compatible server:

```bash
python run_benchmark.py --provider local --model qwen3-32b \
  --base-url http://localhost:8000/v1 --character silent --format raw
```

Use base seeds at least 1000 apart for paper-grade multi-seed runs:

```bash
python run_benchmark.py --provider mock --model mock \
  --seeds 42 1042 2042 3042 4042 --format structured
```

Adjacent base seeds overlap the benchmark's per-sample seed ranges and produce invalid
variance estimates. `--only <dimension>` reruns one dimension and merges unaffected
dimensions from the existing output. `--acts 3` enables Acts 1→3. See
`python run_benchmark.py --help` for all options.

Outputs are written under gitignored `results/` as per-seed JSON/text/PNG artifacts and
multi-seed aggregates.

## Architecture

```text
run_benchmark.py        CLI, seeds, partial reruns, output orchestration
slay_bench/
  benchmark.py          providers, parsing, evaluators, aggregation
  state.py, rng.py      state model and deterministic independent RNG streams
  cards*.py             Ironclad and Silent card content
  enemies*.py           Acts 1–3 enemies and encounters
  combat.py             turn/combat state machine
  run_loop.py           map traversal and full-run evaluation
  prompt_builder.py     structured/raw prompt contracts
  visualize.py          reports and figures
tests/                  no-API regression and statistical known-answer tests
scripts/                baselines, audits, and statistical analysis
cluster/                Slurm serving and benchmark workflows
docs/                   design, decisions, experiments, findings, and paper artifacts
```

The same seed reproduces maps, encounters, draws, rewards, and evaluator fixtures. Read
[the design document](docs/design.md) before modifying engine, prompt, scoring, or RNG
behavior because such changes can invalidate existing benchmark rows.

## Validation

The suite currently contains 174 directly runnable tests:

```bash
python tests/test_benchmark.py
python tests/test_combat.py
python tests/test_run.py
python tests/test_stats.py
```

Engine or harness changes also require mock end-to-end runs for both characters and both
formats. Boundary results, near-zero variance, and oracle-beating scores require a
per-sample instrument audit before publication.

## Security

This is a public repository. Never commit `.env`, result/Slurm logs, private cluster
addresses or account details, SSH material, or private cluster SOP files. Committed
cluster documentation uses placeholders; `.gitignore` protects the known sensitive
artifact classes.

## License

MIT — see [LICENSE](LICENSE).
