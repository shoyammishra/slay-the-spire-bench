# Notes (scratch pad)

## TODO for paper-grade runs
- Re-run llama-3.1-8b-instant with n_turn=20, n_combat=20, n_synergy=20, n_run=10
- Run meta-llama/llama-4-scout-17b-16e-instruct same config
- ~~Run qwen/qwen3-32b same config~~ — DROPPED (free tiers can't run it; needs a paid tier)
- Collect mean ± std per metric per model per format

## Questions to answer in paper
- Does model size improve legal play rate?
- Does raw vs structured gap persist at larger model sizes?
- Is run-level failure universal or model-dependent?

## Notes on results/ files
- Pre-fix run results (map dead-end + EventBus bugs) are in results/ but invalid for run-level dimension
- Radar charts exist for all pilot runs

## qwen3-32b DROPPED (2026-06-07) — why
- qwen3-32b is a REASONING model: 600-4000 reasoning tokens per call, calls are
  sequential within a run. Wall-clock is dominated by token-generation throughput.
- **OpenRouter free tier:** providers serve at ~30-80 tok/s → run-level (~30-60 calls/run
  x 5 runs) takes 1.5-3 hours. Free credits also ran out mid-run → HTTP 402 Payment Required.
- **Groq free tier:** the 6000 TPM cap truncates qwen3 mid-`<think>` → it never emits a
  complete parseable answer → parse-failure cascade (0% across all dimensions).
- **Conclusion:** a reasoning model can't be benchmarked on free tiers. Needs PAID:
  paid Groq (~400-1000 tok/s, no TPM cap, no truncation) is the best lever; paid OpenRouter
  is only marginally faster than free (same upstream providers). Revisiting qwen3 (or another
  reasoning model) on a paid tier is FUTURE WORK. Result files deleted.

## Status snapshot (2026-06-12) — compute blocker resolved by GPU plan
- The "gated on paid Groq" blocker below is **superseded**: the professor provides GPU
  access (~2026-06-13) to self-host all open-source models (M3a), then a path to run
  Claude/GPT (M3b). qwen3-32b is REVIVED — self-hosting removes the exact free-tier
  truncation/throttling that killed it (see the qwen3 section above).
- **Prep done:** `--provider local` adapter landed (`LocalLLM`, commit `a36b42d`) — vLLM/
  Ollama/TGI ready. 118/118 tests. Next = pick model ladder by VRAM + GPU smoke test
  (record tok/s → sizes run-level n). Full plan: roadmap.md M3a/M3b + "Prep for the GPU phase".

## Status snapshot (2026-06-10)
- A* acceptance changes landed (commit d35771e): Silent character, multi-act (`--acts`),
  `--temperature`, `--seeds` (mean±std aggregation), `--llm-routing`; relic on_pickup/register
  split; synergy fixtures 8 → 20/character (40 total). All 40 tests pass.
- Still ZERO valid run-level data — clean pass + everything at n≥20 gated on paid Groq.
- When paid Groq lands, follow the run order in docs/roadmap.md (run-level first).

## Status snapshot (2026-06-07, checkpoint)
- Branch `synergy-rework` pushed to origin (NOT merged to main yet — merge later with
  the synergy re-run results folded in).
- qwen3 DROPPED (see above). Study now covers llama-3.1-8b + llama-4-scout only.
- Still TODO: (1) `--only synergy` ×4 (llama-3.1-8b struct+raw, llama-4-scout struct+raw)
  using the reworked code; (2) `--only run` ×4 (scout needs an n=5 re-run); (3) fold real
  numbers into findings.md + CLAUDE.md; (4) merge synergy-rework -> main.
- KEY GOTCHA: edits to benchmark.py do NOT affect an already-running run. Re-launch to
  pick up code changes, or refresh the affected dimension with `--only`.
