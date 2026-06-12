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

**Agent and game benchmarks.** TextWorld (Côté et al., 2018) and BabyAI (Chevalier-Boisvert et al., 2019) provide text-based and grid-world environments for sequential decision-making, but test a single granularity of action. GameBench (Huang et al., 2024) evaluates LLM game-playing across nine board and card games. BALROG (2024) benchmarks agentic reasoning on NetHack/MiniHack and related roguelikes, and SmartPlay spans six games chosen to stress distinct capabilities. AgentBench (Liu et al., 2023) tests agents across operating-system, database, and web tasks. Two recurring patterns characterize this literature: benchmarks either (a) report a *single aggregate score per whole game* (Orak, GameBench, Board Game Arena, lmgame-Bench), or (b) *map a different game to each skill* (DSGBench: StarCraft II, Civilization, Diplomacy, Werewolf, …; SmartPlay). Neither isolates multiple planning horizons *within one domain*, each with its own ground-truth oracle.

**Direct prior work on Slay the Spire and card games.** Slay the Spire has itself been used as an LLM testbed. Bateni and Whitehead (2024) ("Language-Driven Play", FDG 2024) evaluate LLMs as game-playing agents in a simplified STS engine (MiniSTS), studying whole-game play and card-synergy comprehension; notably, they find that replacing card names with random strings *improves* play, indicating LLMs reason from card descriptions rather than memorized names. The Orak benchmark (2025) includes STS among twelve games for whole-game evaluation and fine-tuning, and hybrid LLM-plus-rule architectures for STS combat have been proposed. In collectible card games, UrzaGPT (2025) fine-tunes LLMs for Magic: The Gathering card selection. slay-bench differs from all of these along the dimension developed next: rather than scoring whole-game play, it decomposes a single STS simulator into four separately-scored planning horizons. Our synergy results — where models name a deck's strategy poorly yet pick on-archetype cards well — are consistent with, and quantify across formats and models, the name-versus-logic dissociation that Bateni and Whitehead first observed via name randomization.

### What slay-bench contributes

The central limitation of prior work is that **each benchmark tests planning at a single scale**. A model that passes PlanBench's short-horizon rearrangement tasks may fail at multi-turn resource allocation; a model that plans a travel itinerary statically may collapse under adversarial pressure. slay-bench addresses this by embedding four planning horizons within one domain:

| Dimension | Horizon | Key challenge |
|---|---|---|
| Turn-level | ~6 cards, 1 turn | Optimal combinatorial sequencing |
| Combat-level | ~5–10 turns | Reactive tactics under HP/block pressure |
| Synergy | Deck snapshot | Strategic archetype recognition |
| Run-level | 15 floors | Long-horizon resource allocation, irreversible card picks |

This design lets us ask not just *whether* a model plans, but *at what scale planning breaks down*. Our pilot results illustrate the value: models achieve ~100% combat win rate (near-optimal at the tactical horizon) yet score 37–75% on archetype identification and 12–25% on card removal (strategic horizon), suggesting a planning-horizon gap that flat single-scale benchmarks would miss entirely.

A second contribution is **optimality-relative scoring**. Where most game benchmarks report win/loss or Elo, our turn dimension scores damage against the *exhaustive optimum* (the provably best card sequence) and combat against a greedy baseline — measuring *how far from optimal* rather than merely whether the agent won.

A third contribution is **prompt format as a controlled variable**. We run every model on identical RNG seeds in both structured JSON and raw English, allowing a clean ablation of representation effects independent of task difficulty. This is a *format* ablation (whole state representation), complementary to the *content* ablation (card names) of Bateni and Whitehead (2024). Our pilot indicates format effects are model- and horizon-dependent, with no single format dominating.

*A fuller novelty/positioning analysis — including an honest assessment of overlap with prior STS work, venue ladder, and synthetic-benchmark comparison — is maintained in `docs/novelty_and_related_work.md`. References to be completed with full citations before submission.*

---

## Publication Notes (updated 2026-06-12)

### Venue ladder

| Paper state | Target venue |
|---|---|
| Current (pilot — missing run data, n < 10, 2 Llama models) | Workshop: NeurIPS/ICLR workshop, FDG, IEEE COG, AIIDE |
| + Valid run-level data + n ≥ 20–30 + ≥ 5 seeds + 3 model families incl. a reasoning model | NeurIPS Datasets & Benchmarks track |
| All above + second STS character or Monster Train + horizon degradation curve | NeurIPS D&B strong or ICLR main track |
| All above + causal analysis of why long-horizon planning fails | NeurIPS/ICLR main track |

### Critical gaps before submission (ranked)
1. **Valid run-level data** — the four-horizon framing cannot be defended without it. This is the most urgent gap. (Unblocked by professor's GPU access, expected 2026-06-13.)
2. **Scale to n ≥ 20–30, ≥ 5 seeds** — current n = 5/3/20/0 with single seeds; no error bars.
3. **3+ model families including a reasoning model** — currently 2 models from one family (Llama). Reasoning model behaviour at different planning horizons is exactly what reviewers will want to see.
4. **Careful FDG 2024 framing** — synergy name-vs-play result must be framed as confirming/extending Bateni & Whitehead (2024), not as an independent discovery.

### What slay-bench vs. synthetic difficulty benchmarks
Synthetic benchmarks (Tower of Hanoi, SokoBench, seqBench) measure *how many steps of the same reasoning sustain* — they tell you where a chain breaks. Slay-bench measures *across qualitatively distinct planning types* — it tells you which cognitive links were never present. A model could score near-optimally at the turn level while completely failing synergy, not because a chain broke but because deck-archetype reasoning was never there.

---
*Experiments section to be filled after paper-grade runs (n ≥ 20 per dimension, ≥ 3 model families).*
