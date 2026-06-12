# slay-bench: Novelty, Related Work, and Generalizability

*Prepared for review discussion (2026-06-09). Purpose: (1) position slay-bench against existing planning/game/Slay-the-Spire work, (2) give an honest assessment of top-tier-conference viability, (3) lay out a generalizability story and candidate games to broaden the benchmark.*

---

## 1. The honest headline

**slay-bench is *not* the first work to put an LLM in Slay the Spire.** There is direct prior art:

- **"Language-Driven Play: LLMs as Game-Playing Agents in Slay the Spire"** (Bateni & Whitehead, **FDG 2024**) — uses *MiniSTS*, a simplified STS engine, and studies whole-game play + card-synergy understanding from descriptions. **Crucially, they already report that replacing card names with random 6-character strings *improves* LLM play** — i.e. LLMs lean on card descriptions/logic, not memorised names.
- **Orak** (arXiv 2506.03610, 2025) — a 12-game foundational LLM-agent benchmark that **includes Slay the Spire** as one of its titles, with leaderboards, battle arenas, and fine-tuning datasets.
- **"A Modular and Hybrid Architecture for LLM Agents playing [STS]"** (OpenReview) — hybrid LLM + rule-based agents for STS combat.
- Related card-game LLM work: **UrzaGPT** (LoRA-tuned card selection in Magic: The Gathering), **Rule Synergy Analysis using LLMs** (2508.19484).

This matters for two reasons. First, a top-tier reviewer *will* find these, so we must cite them and differentiate explicitly — pretending STS+LLM is virgin territory would sink the paper. Second, **our synergy "name-vs-play dissociation" finding partially re-derives the FDG 2024 name-randomisation result** — we need to frame ours as confirming + extending it (we measure it as a *scored dimension* across formats/models), not as a novel discovery.

The good news: **none of the prior STS work does what slay-bench does structurally.** That is where the real novelty lives (Section 3).

---

## 2. The landscape (three buckets)

### 2A. General LLM planning benchmarks
| Benchmark | Domain | Horizon tested | Adversarial? | Irreversible? |
|---|---|---|---|---|
| **PlanBench** (Valmeekam et al. '22/'23) | Blocksworld (PDDL) | Single, short | No | No |
| **NATURAL PLAN** (Google '24) | Trip/meeting/calendar | Single episode | No | No |
| **TravelPlanner** (Xie et al. '24) | Itinerary | Single episode | No | No |
| **PLANET** ('25) | Collection of planning tasks | Mixed | Mostly no | Mostly no |

These test a **single planning horizon**, statically scored, in deterministic or non-adversarial settings.

### 2B. LLM *game* benchmarks
| Benchmark | # games | Structure | What it scores |
|---|---|---|---|
| **Orak** ('25) | 12 (incl. STS) | One score per *whole game* | Win/leaderboard, fine-tuning effects |
| **DSGBench** ('25) | 6 (SC2, Civ, Street Fighter, Diplomacy, Werewolf, Stratego) | **Different game per skill** | Planning, real-time, social, collaboration, adaptation |
| **GameBench** ('24) | 9 board/card/social | One score per whole game | Win-rate vs baselines |
| **BALROG** ('24) | NetHack/MiniHack etc. | Whole-game | Progression score |
| **SmartPlay** | 6 (RPS, Hanoi, Bandit, Messenger, Crafter, Minecraft) | **Different game per skill** | 6 capability axes |
| **Board Game Arena** ('25) | Many board games | Whole-game | Bayesian Elo |
| **lmgame-Bench** ('25) | Suite of video games | Whole-game | Perception/memory/planning |
| **HeroBench** ('25) | Grid RPG world | Long-horizon | Structured long-horizon plan quality |

**The pattern:** game benchmarks either (a) give **one aggregate score per whole game**, or (b) like DSGBench/SmartPlay, **assign a different game to each skill**. Neither isolates *multiple planning horizons inside one domain with a separate ground-truth oracle at each horizon*.

### 2C. Direct STS / card-game + LLM work
Covered in Section 1: FDG 2024 (MiniSTS), Orak's STS, modular/hybrid STS agents, UrzaGPT (MTG).

---

## 3. Where slay-bench is genuinely novel

Three claims survive contact with the prior art. We should lead the paper with #1.

**(1) Single-domain, multi-horizon decomposition with a per-horizon oracle.**
Every other game benchmark scores *whole-game play* (Orak, GameBench, FDG-STS, Board Game Arena) or *maps a different game to each skill* (DSGBench, SmartPlay). slay-bench is the only one that takes **one shared simulator** and slices it into **four nested planning horizons** — turn (≤720-permutation exhaustive optimum), combat (greedy-bot baseline), synergy (hand-crafted archetype ground truth), run (15-floor survival) — each with **its own ground-truth oracle**. Because the cards, enemies, and rules are *identical* across horizons, a score gap between horizons isolates a **planning-horizon effect**, not a domain-shift artifact. This is a controlled-variable design that the whole-game and different-game-per-skill benchmarks structurally cannot offer.

**(2) Optimality-relative scoring, not just win/loss.**
Most game benchmarks report win-rate or Elo — *did the agent win?* slay-bench's turn dimension reports `damage_ratio` against the **exhaustive optimum** (the provably best card sequence), and combat reports HP relative to a greedy baseline. This measures *how far from optimal*, which is a finer signal than binary win/loss and is rare in LLM-game work.

**(3) Prompt-format ablation on identical RNG seeds.**
Every model runs on the same seeds in structured JSON vs. raw English. FDG 2024 ablated *card names* (a content ablation); we ablate the *entire state representation* (a format ablation) with seed-matched controls. Our pilot already shows format effects are model- and horizon-dependent (no single format wins) — a clean, reusable finding.

**What is *not* novel (be upfront):**
- STS as an LLM testbed (FDG 2024, Orak).
- The name-vs-logic effect (FDG 2024 found it first via name randomisation; our synergy result re-derives + quantifies it as a scored dimension).
- LLMs being weak at long-horizon strategy (well established).

---

## 4. Can this fly at a top-tier venue? Honest assessment

**Current state:** the *idea* (nested-horizon decomposition + per-horizon oracles) is genuinely a top-tier-shaped contribution — it reframes "can LLMs plan?" into "*at what horizon does planning break?*" and gives a reusable methodology. **But the current execution is pilot-grade and would be desk-rejected or torn apart at NeurIPS/ICLR/ICML as-is**, for concrete reasons a reviewer will name:

1. **Sample size.** n = 5 / 3 / 8 / (run: none) with single seeds → no error bars, no significance. Top venues expect n ≥ 20–30, ≥ 5 seeds, mean ± std.
2. **Model coverage.** Two models from *one family* (Llama 3.1-8B, Llama-4-Scout). A reviewer wants ≥ 3 families incl. a frontier/reasoning model (GPT/Claude/Gemini/DeepSeek-R1/Qwen-reasoning). The dropped qwen3 left zero reasoning models.
3. **No valid run-level data.** The headline "four horizons" benchmark is missing its longest horizon's data (blocked on free-tier TPM). The flagship claim is currently unsupported empirically.
4. **Narrowness.** Ironclad-only, Act-1-only, one game. Reviewers will ask "does the methodology generalise, or did you just measure one game?" (Section 5).
5. **Novelty proximity to FDG 2024.** Must be cited and differentiated hard; the name-vs-logic overlap needs honest framing.

**Realistic venue ladder:**
- **As-is (pilot):** a workshop (NeurIPS/ICLR workshop, FDG, IEEE CoG, AIIDE) — appropriate and achievable now.
- **With n ≥ 20–30, ≥ 5 seeds, 3+ model families incl. a reasoning model, valid run-level data, and the horizon-decomposition framing as the thesis:** a strong **benchmark-track** submission (NeurIPS Datasets & Benchmarks, or a main-track short/benchmark paper). This is the credible top-tier target.
- **To be a *main-track* NeurIPS/ICLR paper (not just D&B):** add an *analytical* contribution beyond the benchmark — e.g. a quantified "planning-horizon degradation curve" across model scales, or a causal probe of *why* the longest horizon fails (credit assignment? state tracking? deck-memory?). A benchmark alone usually lands in the D&B track; a benchmark + a crisp scientific finding lands main-track.

**Bottom line for the professor:** the framing is competitive for a benchmark track; the blockers are *compute/scale*, not idea quality. The single biggest credibility lever is finishing valid **run-level** data + scaling n and model families.

---

## 5. Generalizability: the methodology-first reframe

The defence against "too narrow" is to **make the contribution the *method*, not the game.** The thesis is:

> *Any game with nested decision horizons can be decomposed into per-horizon benchmark dimensions, each with its own ground-truth oracle, on a shared simulator — isolating planning-horizon effects from domain shift. Slay the Spire (Ironclad) is our first instantiation.*

Framed this way, STS is an *instance* of a general recipe, and breadth is demonstrated by **applying the recipe to additional games/characters** (Section 6). Two complementary moves:

- **Cheap breadth (same engine):** add the other three STS characters (Silent, Defect, Watcher). Different archetypes, same horizons → tests whether per-horizon scores transfer across deck identities with *zero* new simulator work conceptually (more card implementations, same harness). **UPDATE 2026-06-10: Silent is now implemented** (~73 cards, Poison/Shiv/Discard/Block archetypes, 20 synergy fixtures, `--character silent`) — runs pending paid Groq. Defect/Watcher remain future work.
- **Genre breadth (new engine, same recipe):** apply the four-horizon decomposition to a structurally different game (Section 6) to show the methodology isn't STS-specific.

---

## 6. Candidate games to broaden the benchmark

Ranked by effort-to-payoff. The selection criterion is: **does the game have genuinely nested horizons (turn → encounter → build → run) so the four-dimension decomposition applies?**

### Tier 1 — cheapest, strongest payoff
| Game | Why it fits | Cost |
|---|---|---|
| **Other STS characters (Silent / Defect / Watcher)** | Same nested horizons, same harness; different archetypes (poison, orbs, stance). Directly tests cross-archetype generalization of our per-horizon scores. | Low–med (more card defs, existing engine) |
| **Monster Train** | Deckbuilder roguelike with an *extra* spatial horizon (3-floor lane placement) — strictly richer nested planning. | Med (new sim) |

### Tier 2 — strong methodological fit, more build cost
| Game | Why it fits | Cost |
|---|---|---|
| **Into the Breach** | Perfect-information tactical puzzle: turn-level has a *provable* optimum (like ours), plus a meta-progression layer. Great for the optimality-relative scoring story. | Med–high |
| **Dream Quest / MiniSTS-style minimal deckbuilder** | Already used by FDG 2024; a shared, simple engine eases reproducibility and direct comparison to prior STS work. | Low (engine exists) |
| **Hearthstone / MTG (via UrzaGPT-style setup)** | Collectible-card synergy at scale; strong synergy-dimension stress test; existing LLM tooling. | High (rules complexity) |

### Tier 3 — genre-diverse, demonstrates the recipe generalizes beyond cards
| Game | Why it fits | Cost |
|---|---|---|
| **NetHack / MiniHack (BALROG uses these)** | Classic nested horizons: keystroke tactics → dungeon-level → full ascension; resource mgmt + irreversibility. Established LLM benchmark to compare against. | High |
| **Crafter** | Short-horizon survival + long-horizon tech-tree; used in SmartPlay. Bridges to existing benchmark numbers. | Med |
| **FreeCiv / Civilization (DSGBench uses Civ)** | 4X with the clearest turn→era→game horizon stack; very strong "long-horizon" story but heavy. | Very high |

**Recommendation:** for the *paper*, do **Tier 1** — add at least one more STS character (cheap, same engine, directly supports the generalizability claim) and cite Monster Train / Into the Breach as the natural next instantiations in a "Future Work / Extensibility" section. Adding a second STS character is the highest payoff-per-unit-effort way to answer "too narrow" without a multi-month engine build.

---

## 7. How slay-bench differs from synthetic planning benchmarks

An independent line of work tests planning degradation using synthetic domains: Tower of Hanoi, synthetic mazes, SokoBench, the 8-puzzle, seqBench. These all share the same structure — one domain, one difficulty knob (number of disks, path length, solution depth) — and a performance curve as the knob increases. They all answer the same question: **how many steps of identical reasoning can an LLM sustain before it fails?**

slay-bench is doing something different. The four horizons are not just larger versions of the same problem:

- **Turn-level** is combinatorial optimization (≤720 permutations, exhaustive oracle).
- **Combat** is multi-turn state management under adversarial pressure.
- **Synergy** requires understanding emergent interactions between cards that are nowhere stated explicitly.
- **Run-level** is global strategic planning under uncertainty across 15 floors.

The synthetic benchmarks tell you *where the chain breaks* — at what depth the same reasoning fails. Slay-bench tells you *which links were never there* — which qualitatively distinct type of planning is missing. A model could play individual turns near-optimally (high turn score) while completely failing deck construction (low synergy score), not because a longer chain broke but because a different cognitive operation was never present. That distinction is the contribution synthetic difficulty curves cannot provide.

**Framing for the paper:** cite Tower of Hanoi / SokoBench-style work as "depth benchmarks" — they measure how far a single planning type extends. slay-bench is a "breadth benchmark" — it measures across qualitatively distinct planning types. The two are complementary, not competing.

---

## 8. Venue ladder (updated 2026-06-12)

| Paper state | Target venue |
|---|---|
| Current (pilot — missing run data, n < 10, 2 Llama models) | Workshop: NeurIPS/ICLR workshop, FDG, IEEE COG, AIIDE |
| + Valid run-level data + n ≥ 20–30 + ≥ 5 seeds + 3 model families incl. a reasoning model | NeurIPS Datasets & Benchmarks track; benchmark short paper |
| All above + second STS character or Monster Train + horizon degradation curve across model scales | NeurIPS D&B strong submission or ICLR main track |
| All above + causal analysis of why long-horizon planning fails | NeurIPS/ICLR main track (not just D&B) |

The single most important step is valid run-level data + n ≥ 20 + reasoning model. Everything else is secondary to that.

---

## 9. One-paragraph answer to send the professor

> slay-bench is not the first LLM-in-Slay-the-Spire work — FDG 2024 ("Language-Driven Play") and the Orak benchmark already use STS — so we cite and differentiate against them explicitly. Their work, like every other LLM game benchmark (Orak, GameBench, DSGBench, BALROG), scores *whole-game play* or *maps one game to one skill*. Our novelty is structural: we take a **single shared simulator** and decompose it into **four nested planning horizons** (turn → combat → synergy → run), each with **its own ground-truth oracle** (exhaustive optimum, greedy baseline, hand-crafted archetypes, survival), so a score gap *between* horizons isolates a planning-horizon effect rather than a domain change. No prior benchmark does single-domain, multi-horizon, oracle-scored decomposition, and we add a seed-matched structured-vs-raw prompt-format ablation. The contribution is a **reusable methodology**, not one game: we'll demonstrate breadth by extending it to additional STS characters (Silent/Defect/Watcher) and flag Monster Train / Into the Breach / NetHack as natural next instantiations. To be top-tier-competitive on the benchmark track we still need n ≥ 20–30 with ≥ 5 seeds, 3+ model families including a reasoning model, and — most urgently — valid run-level (longest-horizon) data, which is currently blocked on compute, not design.

---

## 10. Sources
- Language-Driven Play: LLMs as Game-Playing Agents in Slay the Spire (FDG 2024) — https://dl.acm.org/doi/10.1145/3649921.3650013
- MiniSTS engine — https://github.com/iambb5445/MiniSTS
- Orak: A Foundational Benchmark for Training and Evaluating LLM Agents on Diverse Video Games — https://arxiv.org/abs/2506.03610
- A Modular and Hybrid Architecture for LLM Agents playing [STS] — https://openreview.net/pdf?id=gC3D2ESSyK
- DSGBench — https://arxiv.org/html/2503.06047v2
- BALROG: Benchmarking Agentic LLM and VLM Reasoning on Games — https://arxiv.org/html/2411.13543v2
- SmartPlay / Tracing LLM Reasoning with Strategic Games — https://arxiv.org/html/2506.12012v1
- HeroBench — https://arxiv.org/pdf/2508.12782
- UrzaGPT (MTG card selection) — https://arxiv.org/html/2508.08382v1
- Rule Synergy Analysis using LLMs — https://arxiv.org/pdf/2508.19484
- PLANET (planning benchmark collection) — https://arxiv.org/pdf/2504.14773
