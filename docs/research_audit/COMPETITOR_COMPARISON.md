# Competitor comparison

| Work | Environment / unit | Control or oracle | Scale / validation | Strongest contribution | Main weakness | Implication for Slay-Bench |
|---|---|---|---|---|---|---|
| AgenticSTS (2026) | STS2 trajectories; typed memory slots | fixed-difficulty memory ablation | 298 archive; 50-run headline; prompts/trajectories/scripts | ablatable bounded-memory contract | headline 3/10→6/10 is underpowered; many choices mechanical/fast-tier | beats current work on long-run trace audit and causal scaffold intervention |
| Orak (ICLR 2026) | 12 original games incl. STS | interactive agent protocol | trajectories and cross-game leaderboard | broad original-game agency | breadth reduces mechanism isolation | defeats “first original-game STS LLM agent benchmark” |
| Language-Driven Play (FDG 2024) | MiniSTS language environment | environment outcomes | released code | direct environment ancestor | simplified domain | must be credited as precursor |
| Rule Synergy Analysis (2025) | STS card pairs | authored synergy labels | dedicated error taxonomy | direct synergy analysis | pair labels omit full deck/run context | defeats first-synergy novelty; offers harder controls |
| LUDOBENCH (2026 preprint) | 480 Ludo spots, 12 categories | depth-2 search reference; paired narrative intervention | 14,400 evals; head-to-head reference validation | same-board paired behavioral test | “game theory” is not exact; handcrafted coverage | its controlled grudge intervention is stronger causal design |
| TSQueryBench (2026 workshop) | same synthetic series across four operations | rule-derived statistics | 500 instances + 100 detection cases | same-input generation/evaluation asymmetry | one annotator; synthetic-only | demonstrates how to isolate operation while holding input fixed |
| GameBench (2024) | nine games | random/human baselines | Bradley–Terry + bootstrap | breadth and standardized outcomes | weak mechanism identification | Slay-Bench can win on traceable decision mechanisms, not breadth |
| PokerBench (AAAI 2025) | 11k poker spots | expert/GTO decisions | 50k-hand checkpoint validation | benchmark-to-play criterion validity | domain-specific and static | sets the label/downstream-validation bar for synergy |
| LMGame-Bench (ICLR 2026) | six games, unified Gym API | environment outcomes | cross-game correlations | interoperable benchmark substrate | less domain depth | raises reproducibility and interface expectations |
| APB (2026) | 4,209 planning cases, 22 domains | verifiable constraints | downstream tool-task checks | criterion validation | not a game agent benchmark | reinforces need to predict downstream play |
| HASOC | annual shared tasks | adjudicated datasets/leaderboards | multi-year community process | adoption and continuity | not planning research | useful only as a community-building template |
| **Slay-Bench current** | four heterogeneous Slay-inspired tasks | turn bounded search; combat greedy; authored labels; absolute run outcomes | 7 configs × 2 chars × 2 formats; five base seeds | inspectable deterministic operation profiles | horizon confound, shortcut labels, hybrid run, weak provenance | current ceiling is a careful domain benchmark paper, not a horizon paper |

## Relative position

Slay-Bench is stronger than several competitors on deterministic replay, explicit
failure accounting, paired prompt-format cells, and code-level auditability. It is
weaker on construct isolation (TSQueryBench/LUDOBENCH), external criterion validation
(PokerBench/APB), original-game ecological validity (Orak), and long-trajectory release
(AgenticSTS).

## Competitive path

The project should not chase breadth. Its credible moat is causal diagnosis inside a
deep, deterministic domain:

1. same-state horizon intervention with an exact oracle;
2. prospective outcome validation for deck choices;
3. full decision-surface agency ablation versus scripted assistance;
4. versioned trajectory release with prompt and provenance records;
5. simulator conformance suite against independently sourced mechanics.
