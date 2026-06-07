# Draft

## Working Title
**slay-bench: Benchmarking LLM Planning in a Roguelike Environment**

## Abstract (placeholder)
We present slay-bench, a benchmark for evaluating large language model planning ability using a faithful Python simulator of Slay the Spire (Ironclad). The benchmark tests four dimensions of planning: single-turn card sequencing, full combat, deck synergy identification, and long-horizon run survival. We evaluate [N] models across two prompt formats (structured JSON, natural English) and report per-dimension scores. Preliminary results suggest raw English prompting outperforms structured JSON for reasoning-heavy tasks, while structured format aids parseable output generation.

## Sections (outline)
1. Introduction
2. Related Work
3. Benchmark Design
   - Simulator
   - Dimensions & scoring
   - Prompt formats
4. Experiments
   - Models evaluated
   - Results table
   - Format ablation
5. Analysis
   - Per-dimension difficulty
   - Format effects
   - Failure modes
6. Conclusion

---
*Content to be filled after paper-grade runs (n≥20 per dimension, ≥3 models).*
