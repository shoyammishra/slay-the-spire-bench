# slay-bench — Codex project instructions

## Purpose and current state

`slay-bench` is a deterministic Python simulator and LLM benchmark for Slay the
Spire. It evaluates planning at four horizons—turn, combat, synergy, and run—across
Ironclad and Silent, with Acts 1–3 implemented. The CLI entry point is
`run_benchmark.py`; the implementation is under `slay_bench/`.

The immediate research milestone is completing and retrieving the
Qwen3-235B-A22B-FP8 full matrix. The smoke passed on 2026-08-09 and three of four
matrix cells have aggregate artifacts on Sharanga. The remaining Silent/raw job
`267038` is running after its stale four-day request was reduced to `23:59:00`; the
partition's current `MaxTime` is one day. Do not rerun the four-cell launcher: preserve
completed cells and split only unfinished Silent/raw work after this pass. Cluster
submission and other paid/limited compute remain user-authorized operations. Before
acting on project status, read the newest entries in `docs/handoff.md`,
`docs/decision_log.md`, and `docs/experiment_log.md` because this summary can age.

## Read-first routing

1. Read `docs/handoff.md` for durable invariants, the active backlog, known risks,
   and the definition of done.
2. Read the newest relevant entries in `docs/decision_log.md` before revisiting a
   settled design or measurement decision.
3. Read `docs/design.md` before changing engine boundaries, scoring, prompts, RNG,
   or state transitions.
4. Read `docs/experiment_log.md` for run provenance and authoritative measurements;
   use `docs/findings.md` and `docs/stats_report.md` for interpreted claims.
5. Treat code, tests, and persisted result artifacts as the final arbiter when docs
   conflict. Record significant resolutions in `docs/decision_log.md`.

`README.md`, `docs/roadmap.md`, `docs/report.md`, and `docs/report.html` contain useful
historical material but are not current project-state authorities.

## Security — public repository

- `.env` contains real Groq and OpenRouter credentials. Never print, stage, or commit
  it.
- Never commit private cluster login addresses, account names, node/user paths,
  contacts, room details, SSH material, or private SOP PDFs. Committed cluster docs
  use placeholders such as `<login-node-ip>`.
- `results/**` is intentionally ignored because result and Slurm logs can contain
  internal infrastructure details. Keep `results/.gitkeep` only.
- On the shared cluster account, target explicit job IDs and PIDs. Never use broad
  account-wide cancellation or process-kill commands.
- Security-scan every diff before commit or push, especially changes under `cluster/`
  or infrastructure-related documentation.

## Engineering invariants

- Treat the instrument as suspect before the model. A score at 0 or 1, `std≈0`, or a
  result that beats its oracle/baseline requires a per-sample audit and a degenerate-
  strategy check.
- Preserve comparability. Before changing prompts, scoring, dynamics, RNG, fixtures,
  or anything feeding a published number, classify which existing data becomes
  invalid and record the re-baseline plan before spending compute.
- Buy information cheapest-first: unit/mock checks → exact-stack smoke → cheap
  dimensions → expensive runs. Never launch a paper-grade run before the exact
  pipeline passes a small smoke test.
- Use base seeds at least 1000 apart (normally `42 1042 2042 3042 4042`). Adjacent
  base seeds overlap per-sample ranges and create false low variance.
- Preserve card object identity when moving cards; do not substitute equality checks.
  Deduct card energy only in `play_card`. Clear and re-register the EventBus for each
  combat. Keep structured and raw prompts semantically equivalent.
- Report floor effects as “on par,” count generalizations, and carry parse-rate,
  conditioning, sample-size, and run-tier caveats with every result. Never blend the
  `N_RUN=5` floor-estimate tier with `N_RUN=20` rows.

## Development commands

Install with Python 3.10+:

```powershell
python -m pip install -r requirements.txt
```

Run the no-API smoke pipeline:

```powershell
python run_benchmark.py --provider mock --model mock --format structured --seed 42
```

Run all tests (the files have direct runners; `pytest` is not a declared dependency):

```powershell
python tests/test_benchmark.py
python tests/test_combat.py
python tests/test_run.py
python tests/test_stats.py
```

For engine, prompt, evaluator, or output changes, also run the mock pipeline for both
characters and both formats. Add deterministic replay, prompt-byte comparison,
greedy-anchor regeneration, statistical known-answer checks, or per-sample audits as
the affected surface requires. Do not call a pre-existing failure fixed unless the
same command passes after the change.

## Architecture map

- `run_benchmark.py`: CLI, seed orchestration, partial-dimension merge, output paths.
- `slay_bench/benchmark.py`: providers, parsing, four evaluators, aggregation.
- `slay_bench/state.py`, `rng.py`: state model and nine deterministic RNG streams.
- `cards*.py`, `enemies*.py`, `relics*.py`, `powers.py`, `potions.py`: game content.
- `combat.py`, `run_loop.py`, `map_gen.py`, `events*.py`, `nodes.py`, `rewards.py`:
  simulation and run traversal.
- `prompt_builder.py`: structured/raw serialization and prompt contracts.
- `visualize.py`: reports and figures.
- `scripts/`: reproducible analyses and baselines; `cluster/`: Slurm launchers.
- `tests/`: 172 directly runnable tests as of 2026-08-09.

## Decisions, documentation, and completion

- Record significant decisions in `docs/decision_log.md`: problem, considered options,
  choice, rationale, trade-offs, limitations, invalidation impact, and reversal path.
- Record every benchmark attempt—including failures—in `docs/experiment_log.md`.
- Update `docs/handoff.md` when active state, backlog, invariants, or operational
  knowledge changes. Update findings/paper docs only when interpretation changes.
- A change is done only when focused tests pass, regressions are covered, required
  broader validation passes, docs are updated in the same change, the final diff is
  reviewed, and the public-repo security scan is clean.

## Codex agents and delegation

Project-scoped agents live in `.codex/agents/`:

- `principal-engineer`: architecture, planning, debugging, integration, and review.
- `engine-auditor`: adversarial game-engine and benchmark-instrument audit.
- `benchmark-operator`: run sizing, Slurm work, retrieval, and result fold-in.
- `security-reviewer`: secret and infrastructure-leak review.
- `paper-writer`: paper framing, results narrative, and reviewer-facing reasoning.
- `docs-formatter`: mechanical transcription and formatting only.

Use the strongest reasoning agent for judgment-bearing work and a fast agent only for
bounded mechanical tasks. Delegated tasks must specify the objective, context paths,
acceptance criteria, tests, documentation updates, and file ownership. The main agent
owns integration and verifies important conclusions; subagent summaries are evidence,
not authority. Parallelize independent read-heavy work, and avoid overlapping writes.

## Legacy Claude configuration

This repository was migrated from Claude Code to Codex. `AGENTS.md`, `.codex/`, normal
project documentation, source, and tests are authoritative. `CLAUDE.md` and `.claude/`
are legacy migration evidence, not active instructions. Do not read them for ordinary
work, modify them, synchronize them, or create compatibility generators. If unique
useful knowledge is later found there, verify it and migrate it to its one appropriate
active home.
