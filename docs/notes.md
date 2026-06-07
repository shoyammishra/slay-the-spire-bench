# Notes (scratch pad)

## TODO for paper-grade runs
- Re-run llama-3.1-8b-instant with n_turn=20, n_combat=20, n_synergy=20, n_run=10
- Run meta-llama/llama-4-scout-17b-16e-instruct same config
- Run qwen/qwen3-32b same config
- Collect mean ± std per metric per model per format

## Questions to answer in paper
- Does model size improve legal play rate?
- Does raw vs structured gap persist at larger model sizes?
- Is run-level failure universal or model-dependent?

## Notes on results/ files
- Pre-fix run results (map dead-end + EventBus bugs) are in results/ but invalid for run-level dimension
- Radar charts exist for all pilot runs

## qwen3-32b performance / cost (2026-06-07)
- qwen3-32b is a REASONING model: 600-4000 reasoning tokens per call, calls are
  sequential within a run. Wall-clock is dominated by token-generation throughput,
  NOT rate limits.
- On OpenRouter, providers (DeepInfra / Nebius / Alibaba) serve at ~30-80 tok/s.
  Run-level (~30-60 calls/run x 5 runs) can take 1.5-3 hours.
- **Speed lever for n>=20:** paid Groq runs qwen3 at ~400-1000 tok/s (5-10x faster)
  AND lifts the 6000 TPM cap that forced us off Groq in the first place. OpenRouter
  paid is only a marginal improvement (same provider throughput). If qwen3 wall-clock
  is painful at n>=20, switch qwen3 to paid Groq — same model, far faster, no truncation.
- Cost so far is tiny (~$0.0003-0.0017 per call on OpenRouter credits).

## Status snapshot (2026-06-07, checkpoint)
- Branch `synergy-rework` pushed to origin (NOT merged to main yet — merge later with
  the synergy re-run results folded in).
- In progress: qwen3-32b STRUCTURED pilot on OpenRouter, currently in run-level eval.
  NOTE: this process was launched BEFORE the synergy rework edits. A running Python
  process loads the module once at startup, so it is executing the OLD synergy code —
  its synergy data (which already ran, before run-level) is FLAWED. Must `--only synergy`.
- Still TODO: (1) qwen3 raw full run; (2) `--only synergy` refresh for ALL 6 combos
  (qwen3 struct+raw on openrouter, llama-3.1-8b struct+raw, llama-4-scout struct+raw)
  using the reworked code; (3) fold real synergy numbers into findings.md + CLAUDE.md;
  (4) merge synergy-rework -> main.
- KEY GOTCHA: edits to benchmark.py do NOT affect an already-running run. Re-launch to
  pick up code changes, or refresh the affected dimension with `--only`.
