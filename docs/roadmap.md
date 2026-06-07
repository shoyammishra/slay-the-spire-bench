# Roadmap

## Milestones

### M1 — Working simulator + harness (DONE)
- Ironclad card set, enemies, combat engine, map generation
- 4-dimension benchmark: turn, combat, synergy, run
- Mock provider for offline testing
- 40 unit tests, all passing

### M2 — Pilot runs (DONE)
- llama-3.1-8b-instant: structured + raw, seed=42
- meta-llama/llama-4-scout-17b-16e-instruct: structured + raw, seed=42
- Key bugs fixed: map dead-end, EventBus stacking, rate-limit crash

### M3 — Paper-grade evaluation (IN PROGRESS)
- n≥20 samples per dimension per model
- Models: llama-3.1-8b, llama-4-scout-17b (qwen3-32b dropped — free tiers can't run a
  reasoning model; a 32B+ reasoning model needs a paid tier — future work)
- Both formats (structured, raw) for each model
- Statistical summary: mean ± std per metric

### M4 — Write-up
- findings.md → draft.md → final paper/report
- Figures: radar charts, bar charts per dimension
- Ablation: structured vs raw per model

## Timeline
- Pilot complete: 2026-06-07
- Paper-grade runs: TBD
- Draft: TBD
