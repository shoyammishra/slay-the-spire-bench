# Draft

## Working Title
**slay-bench: Where Does LLM Planning Collapse? A Multi-Horizon Decomposition in a Roguelike Environment**

## Abstract (refreshed 2026-07-12 — reflects the full 5-family matrix; supersedes the pilot placeholder)
We present slay-bench, a benchmark that decomposes large-language-model planning ability into four nested horizons — single-turn card sequencing, full-combat tactics, deck-synergy judgment, and full-run survival — inside one faithful Slay the Spire simulator (two characters: Ironclad and Silent), with each horizon scored against its own ground-truth oracle (exhaustive turn optimum, greedy-bot baseline, hand-crafted archetype fixtures, and an empirically measured greedy survival floor). We evaluate six model configurations from five families (Qwen2.5-7B, Llama-3.1-8B, Mistral-7B, Qwen3-32B, DeepSeek-R1-Distill 14B/7B) at n=20 per dimension over 5 seeds, under two seed-matched prompt formats (structured JSON vs. natural English). Three findings. (1) **Inter-model variance concentrates at the reasoning horizons and vanishes at the survival horizons**: turn-level damage ratio spans 0.18–0.84 and archetype identification 0.33–0.80 across models, while at combat and run level every instruct model converges to a shared collapse floor statistically on par with a scripted greedy baseline — we report run-level as this floor rather than as a discriminating dimension. (2) **Reasoning-tuning is not a free win**: the strongest short-horizon model (DeepSeek-R1-14B) is the only mid-size model to lose combats and falls *below* the greedy floor at run level (9.75 vs 12.48 floors) — its verbose deliberation actively taxes the longer horizons, itself a horizon-collapse result; the one larger reasoning model tested (Qwen3-32B) is the only line that bends away from the small-model pack, at the synergy horizon (archetype 0.80, removal 0.55 — both matrix maxima). (3) **Prompt-format effects are real but concentrated**: with identical RNG seeds, structured JSON beats natural English on synergy-removal judgment for 5 of 6 models, while the sign of the format effect at other horizons is model- and character-dependent — format sensitivity is a model property, not a constant. All results are from an audited harness (five adversarial audits, 134 regression tests, measured baselines).

> ⚠️ **Superseded pilot claims — do not reintroduce** (removed in the 2026-07-12 refresh): "raw English outperforms structured JSON" (the matrix shows the robust signal is the *opposite*, on synergy removal, 5 of 6 models); "Ironclad only" (Silent is a complete second matrix); "no valid run-level data" (run-level is complete for the instruct families and reframed as the shared collapse floor).

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

This design lets us ask not just *whether* a model plans, but *at what scale planning breaks down*. The full matrix (Section 4) makes the value concrete: every instruct model wins ~100% of scripted combats and reaches greedy-equivalent run floors (near-zero inter-model variance at the survival horizons), yet the same models span 0.18–0.84 on turn-level damage ratio, 0.33–0.80 on archetype identification, and 0.00–0.55 on card removal — a planning-horizon decomposition that flat single-score game benchmarks would compress into indistinguishable aggregates.

The domain choice is not incidental. Slay the Spire has been used as a long-horizon planning testbed both in the research literature (Bateni and Whitehead, 2024; Orak, 2025) and at the frontier-lab scale (Anthropic, 2026), so measuring per-horizon planning within it builds on an established setting rather than an ad-hoc one. Where those efforts measure the ceiling of scaffolded, whole-game agents, slay-bench deliberately measures the *floor* of raw per-horizon planning by holding memory and tooling fixed across horizons.

A second contribution is **optimality-relative scoring**. Where most game benchmarks report win/loss or Elo, our turn dimension scores damage against the *exhaustive optimum* (the provably best card sequence) and combat against a greedy baseline — measuring *how far from optimal* rather than merely whether the agent won.

A third contribution is **prompt format as a controlled variable**. We run every model on identical RNG seeds in both structured JSON and raw English, allowing a clean ablation of representation effects independent of task difficulty. This is a *format* ablation (whole state representation), complementary to the *content* ablation (card names) of Bateni and Whitehead (2024). Across the matrix, the format effect is concentrated at the deck-building horizon — structured ≥ raw on synergy removal for 5 of 6 models (sole reversal: DeepSeek-R1-14B, whose verbose `<think>` decode favors free prose) — while its sign at the turn horizon flips by model and character. Format sensitivity is thus a *model property*, not a constant, which single-format benchmarks silently absorb into their scores.

We hold the harness memory-free by design: adding persistent memory or scaffolding — for example, as a lever to widen the separation between models at the longest horizons, echoing the memory effect Anthropic (2026) report — would break the per-horizon oracle determinism that makes each dimension independently scorable and would require a full re-run. We therefore leave scaffolded, memory-equipped variants to future work, and report the no-memory floor here.

*A fuller novelty/positioning analysis — including an honest assessment of overlap with prior STS work, venue ladder, and synthetic-benchmark comparison — is maintained in `docs/novelty_and_related_work.md`. References to be completed with full citations before submission.*

### Selected references (to be completed)

*Full inline citations (PlanBench, NATURAL PLAN, TravelPlanner, GameBench, Orak, Bateni & Whitehead, etc.) are collected with URLs in `docs/novelty_and_related_work.md` §10 and will be formatted into BibTeX before submission. New entry for this draft:*

- Anthropic (2026). *Claude Fable 5 and Mythos 5* (launch post). Uses Slay the Spire as a long-horizon planning testbed; reports reaching the final act ~3× more often with memory. https://www.anthropic.com/news/claude-fable-5-mythos-5

---

## 4–5. Experiments & Results — summary for assembly (added 2026-07-12; authoritative numbers live in `docs/experiment_log.md` 2026-06-22 section + CLAUDE.md Current Results)

**Setup.** Six model configurations, five families: Qwen2.5-7B, Llama-3.1-8B, Mistral-7B (instruct); Qwen3-32B (reasoning; synergy horizon only); DeepSeek-R1-Distill-14B/7B (reasoning distills). All self-hosted (vLLM on A100 80 GB), n=20 per dimension × 5 seeds (bases spaced 1000 apart), both characters, both formats, parse_ok = 1.0 for all instruct models. Harness validated by five adversarial audits (134 regression tests); baselines measured, not assumed (`scripts/greedy_baseline.py`: greedy floor Ironclad 12.48 floors / 0.780 progress / 1% survival; Silent 11.26 / 0.704 / 0% — per-character anchors).

**Headline findings (order for the paper):**
1. **The discriminating power of planning evaluation lives at the reasoning horizons.** Turn spread 0.18→0.84, synergy archetype 0.33→0.80 across models; combat win rate and run floors have near-zero inter-model variance (all instruct models: win = 1.00, floors ≈ each character's greedy floor). This is the multi-horizon thesis in one sentence.
2. **Run-level is reported as the shared collapse floor, not a discriminating dimension** (decision 2026-07-12). Every instruct model lands on par with the measured greedy floor and none beats it (largest normalized lift ≤ 0.13, Silent structured); the only deviations are *downward* (DeepSeek-14B: 9.75 floors < greedy 12.48 — over-deliberation into death). Report avg_floors/avg_progress, never survival_rate alone, and never "beats the baseline."
3. **Reasoning ≠ free win, and the cost lands on the long horizons.** DeepSeek-14B is the best turn-level model on both characters (0.823 IC / 0.839 Silent) yet the only mid-size model that loses combats (down to win 0.34 / hp_ratio 0.21 Silent-raw) and floors below greedy at run. DeepSeek-7B collapses at every execution horizon (combat win 0.14–0.28, ~8 parse errors/combat) yet its synergy-removal *judgment* survives (0.41–0.54; 2nd in the matrix — caveat: conditioned on parse_ok 0.69–0.92). Qwen3-32B is the one line that bends away from the pack, at synergy (Silent archetype 0.80, removal 0.55, matrix maxima).
4. **Format ablation** (seed-matched): robust signal = synergy removal, structured ≥ raw for 5 of 6 models; sign elsewhere is model/character-dependent (e.g. Llama/Mistral prefer raw at turn level; Qwen2.5 the reverse on Ironclad). Cleanest illustration: Qwen2.5 raw-format archetype answers collapse to a constant "Block" guess (17/20 fixtures, every seed — verified per-sample, parse_ok = 1.0), scoring exactly the Block base rate, while the same model on the same seeds in structured spreads its answers and scores higher.
5. **Mechanic-defined archetypes are a cross-character blind spot** (recomputed 2026-07-12 from the full matrix's 2,400 per-sample synergy records — supersedes the 2026-06-10-era pooled table): surface-signature archetypes Block **0.81** / Poison **0.81** (Aggro 0.60; Shiv 0.44, Strength 0.31 intermediate); the two payoff-mechanic archetypes — Ironclad Exhaust **0.017** and Silent Discard **0.14** — score *below* the 0.25 four-way chance floor: systematic mislabeling, not guessing. Name-vs-play dissociation (Bateni & Whitehead 2024) confirmed on the same data: card-pick on those unlabelable decks holds at 0.43 vs 0.33 chance.

**Central figure — the horizon-collapse curve** (`results/horizon_collapse_{structured,raw}.png`, from `visualize.py --horizon-curve`): per-model normalized planning score vs. horizon (turn → combat → synergy → run), one panel per character. **Required caption language:** the y-axis is normalized so **0 = the non-planning floor** (chance / greedy baseline) and 1 = perfect; note that combat is normalized as `win_rate × min(1, hp_ratio)`, which by construction places the *winning* greedy bot near 1.0 — the combat baseline is a near-ceiling, so instruct lines plateau there and the collapse story is carried by the reasoning models dropping below it and by the right edge (run) converging to the shared floor. Normalization formulas + degenerate-input check: `docs/decision_log.md` 2026-07-12.

**Known limitations to state honestly (§5.4):** Qwen3-32B has synergy-only coverage (its curve is an isolated point at the horizon where the separation lives); DeepSeek-7B synergy accuracies are conditioned on its parse rate; no frontier proprietary model yet (the M3b runs are the decisive missing experiment — with only ≤32B open models, the curves mostly run parallel and the frontier-bend claim rests on one model at one horizon); single domain (mitigated by two characters within one engine and by the reusable-method framing).

---

## Publication Notes (updated 2026-07-12; supersedes 2026-06-12 notes)

### Venue ladder

| Paper state | Target venue | Status |
|---|---|---|
| Pilot — missing run data, n < 10, 2 Llama models | Workshop: NeurIPS/ICLR workshop, FDG, IEEE COG, AIIDE | ✅ exceeded |
| + Valid run-level data + n ≥ 20–30 + ≥ 5 seeds + 3 model families incl. a reasoning model | NeurIPS Datasets & Benchmarks track | ✅ **met 2026-06-22** (5 families, n=20 × 5 seeds, run-level complete for instruct models) |
| All above + second STS character + horizon degradation curve | NeurIPS D&B strong or ICLR main track | ✅ Silent matrix (2026-06-14) + horizon-collapse curve (2026-07-12); **⚠️ curve separation still rests on one open reasoning model — frontier runs (M3b) are the make-or-break addition** |
| All above + causal analysis of why long-horizon planning fails | NeurIPS/ICLR main track | Future work (DeepSeek over-deliberation result is a first data point) |

### Critical gaps before submission (re-ranked 2026-07-12)
1. **M3b frontier runs (Claude/GPT)** — the decisive missing experiment. The headline claim ("the horizon at which models collapse differs by capability class") currently rests on Qwen3-32B's synergy-only point. Either frontier outcome completes the paper: separation confirms the claim; frontier flooring at 1 act triggers the registered `--acts 3` appendix probe (decision_log 2026-07-12 P3) and is itself a strong negative result.
2. **Full draft assembly** — Sections 1, 3–6 unwritten; this file holds the refreshed abstract, Related Work, and the results-summary skeleton (above). No stale pilot claims may survive assembly (see the superseded-claims box under the Abstract).
3. **Citations** — venue/year completion + BibTeX from `novelty_and_related_work.md` §10 (mechanical; Sonnet-eligible).
4. **Careful FDG 2024 framing** — synergy name-vs-play result must be framed as confirming/extending Bateni & Whitehead (2024), not as an independent discovery. (Already reflected in Related Work; keep it through assembly.)

### What slay-bench vs. synthetic difficulty benchmarks
Synthetic benchmarks (Tower of Hanoi, SokoBench, seqBench) measure *how many steps of the same reasoning sustain* — they tell you where a chain breaks. Slay-bench measures *across qualitatively distinct planning types* — it tells you which cognitive links were never present. A model could score near-optimally at the turn level while completely failing synergy, not because a chain broke but because deck-archetype reasoning was never there.

---
*Paper-grade runs complete (n = 20 per dimension, 5 seeds, 5 families, both characters). Experiments/Analysis prose to be expanded from the §4–5 summary above during full assembly (P6), ideally after the M3b frontier runs land.*
