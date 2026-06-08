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

## 2. Related Work

### LLM Planning Benchmarks

Several benchmarks evaluate LLM planning ability, but each targets a single decision horizon or a single type of planning challenge.

**Classical and symbolic planning.** Valmeekam et al. (2022, 2023) introduced PlanBench, testing models on PDDL-style domains (Blocksworld, Mystery Blocksworld) where state transitions are fully observable and deterministic. They find that LLMs fail even simple multi-step rearrangement under these conditions. Our benchmark extends this line of inquiry to *stochastic, adversarial* settings where resource constraints and irreversible decisions compound across time.

**Natural-language scheduling and logistics.** NATURAL PLAN (Zheng et al., 2024) evaluates LLMs on trip planning, meeting scheduling, and calendar management expressed in natural language. TravelPlanner (Xie et al., 2024) similarly evaluates multi-day itinerary construction. These benchmarks test constraint satisfaction over a single planning episode and produce a plan evaluated statically. In contrast, slay-bench requires *reactive* replanning at every turn against an adversarial opponent.

**Agent and game benchmarks.** TextWorld (Côté et al., 2018) and BabyAI (Chevalier-Boisvert et al., 2019) provide text-based and grid-world environments for sequential decision-making, but test a single granularity of action. GameBench (Huang et al., 2024) evaluates LLM game-playing across ten board and card games with a focus on strategic reasoning. AgentBench (Liu et al., 2023) tests agents across operating-system, database, and web tasks. These works treat planning as monolithic; none decompose performance across nested decision horizons on the same underlying domain.

### What slay-bench contributes

The central limitation of prior work is that **each benchmark tests planning at a single scale**. A model that passes PlanBench's short-horizon rearrangement tasks may fail at multi-turn resource allocation; a model that plans a travel itinerary statically may collapse under adversarial pressure. slay-bench addresses this by embedding four planning horizons within one domain:

| Dimension | Horizon | Key challenge |
|---|---|---|
| Turn-level | ~6 cards, 1 turn | Optimal combinatorial sequencing |
| Combat-level | ~5–10 turns | Reactive tactics under HP/block pressure |
| Synergy | Deck snapshot | Strategic archetype recognition |
| Run-level | 15 floors | Long-horizon resource allocation, irreversible card picks |

This design lets us ask not just *whether* a model plans, but *at what scale planning breaks down*. Our pilot results illustrate the value: models achieve ~100% combat win rate (near-optimal at the tactical horizon) yet score 37–75% on archetype identification and 12–25% on card removal (strategic horizon), suggesting a planning-horizon gap that flat single-scale benchmarks would miss entirely.

A second contribution is **prompt format as a controlled variable**. We run every model on identical RNG seeds in both structured JSON and raw English, allowing a clean ablation of representation effects independent of task difficulty. Prior benchmarks rarely vary prompt format systematically.

*References to be completed with full citations before submission.*

---
*Content to be filled after paper-grade runs (n≥20 per dimension, ≥3 models).*
