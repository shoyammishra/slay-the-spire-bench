# Claude Code to Codex migration record

**Date:** 2026-08-16  
**Status:** Codex-native instructions and agents implemented; legacy sources retained
as read-only migration evidence pending an explicit cleanup decision.

## Repository and source protection

`slay-bench` is a deterministic Python Slay the Spire simulator and LLM benchmark for
Ironclad and Silent across Acts 1–3. It measures turn-, combat-, synergy-, and run-level
planning. `run_benchmark.py` is the CLI, `slay_bench/` is the implementation, `tests/`
is the no-API suite, `scripts/` contains analyses, and `cluster/` contains Slurm jobs.

At migration start, `main` matched `origin/main`. The only worktree additions were
untracked `AGENTS.md` and `.codex/`, an earlier migration attempt. They were treated as
user-owned work and reconciled rather than discarded. No staged or tracked changes
existed, and there was one worktree.

The earlier `AGENTS.md` was a 120 KB near-copy of `CLAUDE.md`, exceeding Codex's default
32 KiB project-instruction budget. Mechanical substitutions also corrupted scientific
Claude-model references, an Anthropic URL, and path casing. The canonical replacement
is therefore a concise router; detailed history remains in normal documentation.

## Migration inventory

| Claude source | Useful capability | Codex destination | Status |
|---|---|---|---|
| `CLAUDE.md` | State, rules, commands, architecture, results, lessons | `AGENTS.md` plus existing `docs/handoff.md`, `docs/design.md`, decision/experiment logs, and findings | Migrated; archive retained |
| `.claude/agents/principal-engineer.md` | Architecture, decisions, integration | `.codex/agents/principal-engineer.toml` | Migrated |
| `.claude/agents/engine-auditor.md` | Instrument/fidelity audit | `.codex/agents/engine-auditor.toml` | Migrated |
| `.claude/agents/benchmark-operator.md` | Run sizing, cluster operation, fold-in | `.codex/agents/benchmark-operator.toml` | Migrated |
| `.claude/agents/security-reviewer.md` | Public-repo leak prevention | `.codex/agents/security-reviewer.toml` | Migrated |
| `.claude/agents/paper-writer.md` | Paper narrative and review defense | `.codex/agents/paper-writer.toml` | Migrated |
| `.claude/agents/docs-formatter.md` | Mechanical formatting/transcription | `.codex/agents/docs-formatter.toml` | Migrated |

No Claude commands, hooks, settings, permissions, MCP configuration, standalone memory,
or reusable scripts existed under `.claude/`. No Codex hook, MCP layer, config file, or
repository Skill was invented: the six narrow agents and existing project docs/scripts
already preserve the source capabilities without duplication.

## Canonical Codex architecture

- `AGENTS.md`: durable rules and routing, kept below the discovery budget.
- `.codex/agents/*.toml`: six project-scoped specialized responsibilities.
- `docs/handoff.md`: state, invariants, backlog, risks, and review checklist.
- `docs/design.md`: architecture and engine contracts.
- `docs/decision_log.md`: durable judgment and comparability decisions.
- `docs/experiment_log.md`: measurement provenance and failures.
- Source and tests: implementation truth.

There are no nested `AGENTS.md` files because this is one Python system and no subtree
has materially different instructions. Historical/scientific Anthropic and Claude
references remain when they name benchmark subjects, related work, or past events.

## Knowledge preserved

- Architecture, determinism, card identity, EventBus lifecycle, prompt parity, seed
  spacing, public-repo security, and comparability rules.
- Cheapest-first validation, regression coverage, diff/security review, and same-change
  documentation.
- Run provenance, result tables, findings, audits, and research framing in normal docs.
- All six specialist responsibilities, translated to capability-oriented Codex agents.
- Existing deterministic enforcement: tests, analysis scripts, prefetch verifier, and
  smoke-gated Slurm launchers.

## Validation and parity plan

1. Map every Claude source to migrated, independently useful, or archive status.
2. Parse every custom-agent TOML and check its required fields.
3. Confirm a fresh agent can find product, setup, architecture, tests, safety, agents,
   planning rules, and completion criteria without opening legacy files.
4. Run all four test files and the mock matrix for both characters and formats.
5. Scan for stale active instructions that direct agents to update `CLAUDE.md`.
6. Scan the final diff for credentials and internal infrastructure.

## Legacy disposition

`CLAUDE.md` and `.claude/agents/` are **archive material retained for now**. Their active
behavior has a Codex destination, but deletion is deferred because destructive cleanup
was ambiguous. They are not active instructions and must not be synchronized. Other
Claude/Anthropic references are retained when independently meaningful to the science,
provider support, or historical record.

## Fresh-agent result

A new Codex agent can use `AGENTS.md` and its routed active docs to identify the product
and next milestone, install and run it, locate architecture, execute validation, apply
measurement/security invariants, choose a specialist, organize complex work, and decide
when a change is complete—without consulting `CLAUDE.md` or `.claude/`.
