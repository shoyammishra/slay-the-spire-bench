# Draft

## Working Title
**slay-bench: Where Does LLM Planning Collapse? A Multi-Horizon Decomposition in a Roguelike Environment**

## Abstract (refreshed 2026-08-30 — seven-configuration audited matrix)

We present slay-bench, a benchmark that decomposes large-language-model planning ability into four nested horizons — single-turn card sequencing, full-combat tactics, deck-synergy judgment, and full-run survival — inside one faithful Slay the Spire simulator (Ironclad and Silent). Each horizon uses a distinct reference: exhaustive turn optimum, a greedy combat baseline, hand-crafted archetype and best-pick fixtures, and an empirically measured greedy run floor. We evaluate seven model configurations from five families (Qwen2.5-7B, Llama-3.1-8B, Mistral-7B, Qwen3-32B, Qwen3-235B-A22B-FP8, and DeepSeek-R1-Distill 14B/7B) over five spaced seeds under seed-matched structured-JSON and natural-English prompts. Three findings. (1) **Inter-model variance concentrates before the run horizon**: on representative metrics, between-model variance shares are .865 for turn damage, .896 for combat win, .629 for synergy archetype, and .021 for run floors, where the balanced models converge on the measured greedy floor. (2) **Capacity gains are operation-selective**: relative to seed-matched Qwen3-32B, Qwen3-235B improves card-pick accuracy by .110–.280 in all four cells and 19/20 seed pairs, but turn, combat, and run effects are mixed or saturated rather than a uniform horizon extension. (3) **Prompt-format effects depend on the operation**: structured prompts produce a general combat-HP advantage, while turn and valid synergy effects vary by model/character. A degenerate-strategy audit invalidated the original removal metric—all expert targets were `Strike`—so we quarantine it rather than report a pruning claim. All results use an audited harness with measured baselines and 174 regression tests.

> ⛔ **Superseded claims — do not reintroduce:** any removal-v1 capability or format
> claim (including “structured ≥ raw for 5 of 6 models”) is invalid because a constant
> `Strike` answer scores 100%. Also superseded: “Qwen3-32B is synergy-only” and “the
> open-model result stops at 32B.” Raw removal fields remain provenance diagnostics only.

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

Slay the Spire has also been adopted as a long-horizon planning testbed at the frontier-lab scale: Anthropic (2026) report using Slay the Spire to probe long-horizon planning when launching their Claude Fable 5 / Mythos 5 models. This is external validation for the domain choice — it answers the natural reviewer question "why this game?" by establishing STS as an accepted frontier-lab planning testbed rather than an idiosyncratic pick. It also positions slay-bench as a deliberate complement rather than a competitor: their agent is *scaffolded* (equipped with persistent memory and vision) and measures the **ceiling** of an engineered end-to-end agent, whereas our unscaffolded, memory-free harness holds each planning horizon fixed and measures the **floor** of raw per-horizon planning. Relatedly, Anthropic report reaching the game's final act roughly three times more often *with* memory than without — a signal consistent with our own run-level results (Section 5), where full-run survival is a severe bottleneck even for the strongest models we test. We treat this only as corroboration of a floor effect, not as a controlled comparison: their setup differs from ours in model scale, scaffolding, and evaluation protocol.

### What slay-bench contributes

The central limitation of prior work is that **each benchmark tests planning at a single scale**. A model that passes PlanBench's short-horizon rearrangement tasks may fail at multi-turn resource allocation; a model that plans a travel itinerary statically may collapse under adversarial pressure. slay-bench addresses this by embedding four planning horizons within one domain:

| Dimension | Horizon | Key challenge |
|---|---|---|
| Turn-level | ~6 cards, 1 turn | Optimal combinatorial sequencing |
| Combat-level | ~5–10 turns | Reactive tactics under HP/block pressure |
| Synergy | Deck snapshot | Strategic archetype recognition |
| Run-level | 15 floors | Long-horizon resource allocation, irreversible card picks |

This design lets us ask not just *whether* a model plans, but *at what scale planning breaks down*. The full matrix (Section 4) makes the value concrete: several instruct models win nearly all scripted combats and the balanced run rows converge on greedy-equivalent floors, yet turn-level damage and valid archetype/best-pick judgments separate models substantially. A flat whole-game score would compress these dissociations. Removal-v1 is excluded: its universal `Strike` target lets a constant answer score perfectly.

The domain choice is not incidental. Slay the Spire has been used as a long-horizon planning testbed both in the research literature (Bateni and Whitehead, 2024; Orak, 2025) and at the frontier-lab scale (Anthropic, 2026), so measuring per-horizon planning within it builds on an established setting rather than an ad-hoc one. Where those efforts measure the ceiling of scaffolded, whole-game agents, slay-bench deliberately measures the *floor* of raw per-horizon planning by holding memory and tooling fixed across horizons.

A second contribution is **optimality-relative scoring**. Where most game benchmarks report win/loss or Elo, our turn dimension scores damage against the *exhaustive optimum* (the provably best card sequence) and combat against a greedy baseline — measuring *how far from optimal* rather than merely whether the agent won.

A third contribution is **prompt format as a controlled variable**. We run every model on identical RNG seeds in both structured JSON and raw English, allowing a clean ablation of representation effects independent of task difficulty. This is a *format* ablation (whole state representation), complementary to the *content* ablation (card names) of Bateni and Whitehead (2024). Across 14 model×character strata, structured prompts have a general positive effect on combat HP ratio (12/14 directions; sign p=.0129), while turn effects split 6/8 and valid synergy effects are magnitude-only rather than directionally general. Format sensitivity is thus operation- and model-dependent, which single-format benchmarks silently absorb into their scores.

We hold the harness memory-free by design: adding persistent memory or scaffolding — for example, as a lever to widen the separation between models at the longest horizons, echoing the memory effect Anthropic (2026) report — would break the per-horizon oracle determinism that makes each dimension independently scorable and would require a full re-run. We therefore leave scaffolded, memory-equipped variants to future work, and report the no-memory floor here.

*A fuller novelty/positioning analysis — including an honest assessment of overlap with prior STS work, venue ladder, and synthetic-benchmark comparison — is maintained in `docs/novelty_and_related_work.md`. References to be completed with full citations before submission.*

### Selected references (to be completed)

*Full inline citations (PlanBench, NATURAL PLAN, TravelPlanner, GameBench, Orak, Bateni & Whitehead, etc.) are collected with URLs in `docs/novelty_and_related_work.md` §10 and will be formatted into BibTeX before submission. New entry for this draft:*

- Anthropic (2026). *Claude Fable 5 and Mythos 5* (launch post). Uses Slay the Spire as a long-horizon planning testbed; reports reaching the final act ~3× more often with memory. https://www.anthropic.com/news/claude-fable-5-mythos-5

---

## 4–5. Experiments & Results — summary for assembly (added 2026-07-12; authoritative numbers live in `docs/experiment_log.md` 2026-06-22 section + CLAUDE.md Current Results)

**Setup.** Seven model configurations, five families: Qwen2.5-7B, Llama-3.1-8B, Mistral-7B; Qwen3-32B and Qwen3-235B-A22B-FP8; DeepSeek-R1-Distill-14B/7B. All are self-hosted with vLLM; the smaller rows ran on A100s and the 235B FP8 MoE on 2×H200. Turn, combat, and synergy use n=20 per seed × 5 base seeds spaced 1000 apart, both characters, both formats. Qwen3 run cells use the registered `N_RUN=5` floor-estimate tier and are not pooled with balanced `N_RUN=20` variance rows. The harness has five adversarial audits and 174 regression tests; baselines are measured, not assumed (`scripts/greedy_baseline.py`: Ironclad 12.48 floors / .780 progress / 1% survival; Silent 11.26 / .704 / 0%).

**Headline findings (order for the paper):**
1. **The discriminating power of planning evaluation lives at the reasoning horizons.** Turn spread 0.18→0.84, synergy archetype 0.33→0.80 across models; combat win rate and run floors have near-zero inter-model variance (all instruct models: win = 1.00, floors ≈ each character's greedy floor). This is the multi-horizon thesis in one sentence.
2. **Run-level is reported as the shared collapse floor, not a discriminating dimension** (decision 2026-07-12). Every instruct model lands on par with the measured greedy floor and none beats it (largest normalized lift ≤ 0.13, Silent structured); the only deviations are *downward* (DeepSeek-14B: 9.75 floors < greedy 12.48 — over-deliberation into death). Report avg_floors/avg_progress, never survival_rate alone, and never "beats the baseline."
3. **Reasoning and capacity are not free wins.** DeepSeek-14B is strongest at turn level yet loses combats and falls below the greedy run floor; the instrumented probe attributes its true JSON failures to token-budget truncation mid-`<think>`. At the other end of the ladder, Qwen3-235B improves card selection over Qwen3-32B in every cell and 19/20 seed pairs, but not turn, combat, or run uniformly. These two dissociations show why “reasoning model” or parameter count cannot substitute for per-operation measurement. (Probe caveats: seed 42 only, combat n=3; Qwen3-235B is a 22B-active MoE versus dense 32B.)
4. **Format ablation** (seed-matched): structured has a general combat-HP advantage (+.0593 pooled; 12/14 directions), while turn direction is mixed and valid synergy effects are model-dependent. The cleanest degeneracy illustration remains Qwen2.5 raw-format archetype answers collapsing to a constant “Block” guess at the Block base rate. Removal-v1 is not part of this ablation because a constant `Strike` answer scores every fixture.
5. **Mechanic-defined archetypes are a cross-character blind spot** (recomputed 2026-08-30 from 2,800 current per-sample synergy records): surface-signature archetypes Block **0.82** / Poison **0.84**, while the payoff-mechanic archetypes Ironclad Exhaust **0.024** and Silent Discard **0.217** land at or below the 0.25 four-way chance floor. Best-pick accuracy on those decks remains about **0.43** vs 0.33 chance. This confirms and extends Bateni & Whitehead's name-vs-play dissociation; it is not framed as a new discovery.

**Central figure — the horizon-collapse curve** (`results/horizon_collapse_{structured,raw}.png`, from `visualize.py --horizon-curve`): per-model normalized planning score vs. horizon (turn → combat → synergy → run), one panel per character. The synergy point is the chance-normalized mean of **archetype + best pick only**; removal-v1 is excluded. **Required caption language:** the y-axis is normalized so **0 = the non-planning floor** (chance / greedy baseline) and 1 = perfect; combat is `win_rate × min(1, hp_ratio)`, which places the winning greedy bot near 1.0. Qwen3 run points are descriptive `N_RUN=5` floor estimates. Normalization formulas and the removal supersession are in the decision log.

**Known limitations to state honestly (§5.4):** removal-v1 is invalid for strategic pruning and needs a versioned full-synergy re-baseline; DeepSeek-7B valid synergy accuracies are conditioned on parse rate; the budget-bound-deliberation attribution rests on a single-seed diagnostic probe; Qwen3 run results use `N_RUN=5`; Qwen3-235B is a 22B-active FP8 MoE rather than a dense scaling match; original Slurm stdout is missing for three 235B cells, so their run error burden cannot be reconstructed; no proprietary frontier model is included; and the benchmark covers one domain, mitigated by two characters.

---

## Publication Notes (updated 2026-07-12; supersedes 2026-06-12 notes)

### Venue ladder

| Paper state | Target venue | Status |
|---|---|---|
| Pilot — missing run data, n < 10, 2 Llama models | Workshop: NeurIPS/ICLR workshop, FDG, IEEE COG, AIIDE | ✅ exceeded |
| + Valid run-level data + n ≥ 20–30 + ≥ 5 seeds + 3 model families incl. a reasoning model | NeurIPS Datasets & Benchmarks track | ✅ **met 2026-06-22** (5 families, n=20 × 5 seeds, run-level complete for instruct models) |
| All above + second STS character + horizon degradation curve | NeurIPS D&B strong or ICLR main track | ✅ Silent matrix + audited curve + complete Qwen3-32B/235B ladder; **⚠️ proprietary frontier validation remains absent** |
| All above + causal analysis of why long-horizon planning fails | NeurIPS/ICLR main track | Future work (DeepSeek over-deliberation is a first data point — mechanism now probe-confirmed as budget-bound deliberation, 2026-07-13) |

### Critical gaps before submission (re-ranked 2026-07-12)
1. **M3b frontier runs (Claude/GPT)** — the decisive external-capability validation. The open-model ladder now includes complete Qwen3-32B and Qwen3-235B matrices, but it shows selective card-choice gains rather than a universal horizon extension. Either proprietary-frontier outcome is informative: separation extends the claim; flooring at 1 act triggers the registered `--acts 3` appendix probe.
2. **Full draft assembly** — Sections 1, 3–6 unwritten; this file holds the refreshed abstract, Related Work, and the results-summary skeleton (above). No stale pilot claims may survive assembly (see the superseded-claims box under the Abstract).
3. **Citations** — venue/year completion + BibTeX from `novelty_and_related_work.md` §10 (mechanical; Sonnet-eligible).
4. **Careful FDG 2024 framing** — synergy name-vs-play result must be framed as confirming/extending Bateni & Whitehead (2024), not as an independent discovery. (Already reflected in Related Work; keep it through assembly.)

### What slay-bench vs. synthetic difficulty benchmarks
Synthetic benchmarks (Tower of Hanoi, SokoBench, seqBench) measure *how many steps of the same reasoning sustain* — they tell you where a chain breaks. Slay-bench measures *across qualitatively distinct planning types* — it tells you which cognitive links were never present. A model could score near-optimally at the turn level while completely failing synergy, not because a chain broke but because deck-archetype reasoning was never there.

---
*Open-model runs are complete for seven configurations from five families and both characters. Qwen3 run rows remain the registered `N_RUN=5` floor-estimate tier. Experiments/Analysis prose should be expanded from the §4–5 summary during full assembly, with removal-v1 kept quarantined.*
