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
