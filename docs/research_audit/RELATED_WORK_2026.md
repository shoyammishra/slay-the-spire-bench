# Related work audit, current through 2026-08-30

## Search method and scope

The audit searched primary papers and project pages for Slay the Spire agents,
language-model game benchmarks, controlled planning evaluations, long-horizon agent
testbeds, and benchmark-adoption exemplars. Dates and acceptance status are reported
only when present in the primary source. ArXiv claims are not treated as peer-reviewed
merely because they are recent.

## Direct Slay the Spire lineage

- **Language-Driven Play / MiniSTS** (FDG 2024) uses a language-facing simplified
  Slay-style environment and therefore predates the broad “language interface for
  Slay planning” premise. It is the closest environment-design ancestor.
  [DOI record](https://doi.org/10.1145/3649921.3650013) and
  [MiniSTS code](https://github.com/iambb5445/MiniSTS).
- **Rule Synergy Analysis using LLMs** (2025) builds a Slay the Spire card-pair
  synergy dataset with positive/negative/neutral labels and analyzes timing, state,
  and rule errors. Slay-Bench cannot claim first LLM evaluation of Slay synergy.
  [arXiv:2508.19484](https://arxiv.org/abs/2508.19484).
- **Orak** (ICLR 2026) evaluates generalist LLM agents across twelve games, including
  the original Slay the Spire, through MCP-compatible interaction and trajectory
  evaluation. It is stronger prior art for broad original-game agent capability.
  [arXiv:2506.03610](https://arxiv.org/abs/2506.03610).
- **AgenticSTS** (2026 preprint) is the closest long-horizon comparator, although it
  uses Slay the Spire 2. It reports 298 completed tagged trajectories and a balanced
  50-run fixed-difficulty memory ablation. Its 3/10 versus 6/10 difference is correctly
  described as directional (Fisher p≈0.37), and it releases prompts, frozen memory
  snapshots, trajectories, and scripts. A typical run has a median 67 strategic calls,
  while many other choices are mechanical or routed to a fast tier. Its contribution
  is an ablatable memory contract, not an uncontested claim of full autonomous control.
  [arXiv:2607.02255](https://arxiv.org/abs/2607.02255).

## Game benchmarks

- **GameBench** standardizes nine games and compares GPT-family agents with random and
  human baselines, using Bradley–Terry aggregation and bootstrap intervals. It offers
  breadth and common evaluation, but outcome aggregation can obscure decision-level
  mechanisms. [arXiv:2406.06613](https://arxiv.org/abs/2406.06613).
- **PokerBench** provides 11,000 expert/GTO-labeled poker spots and validates benchmark
  scores against 50,000-hand checkpoint matches. The downstream validation between a
  static benchmark and actual play is precisely what Slay-Bench synergy lacks.
  [arXiv:2501.08328](https://arxiv.org/abs/2501.08328).
- **LUDOBENCH** provides 480 handcrafted spots across twelve decision categories and
  14,400 model evaluations. Its paired grudge manipulation holds board state fixed,
  which is methodologically stronger than Slay-Bench's horizon ordering. Its so-called
  game-theory ceiling is only depth-2 expectiminimax/MaxN with a linear cutoff; the
  paper should call it a search reference, not an exact optimum. It also uses
  handcrafted cases and inherits construct/coverage concerns.
  [arXiv:2604.05681](https://arxiv.org/abs/2604.05681).
- **LMGame-Bench** (ICLR 2026) supplies a unified Gym-style interface over six games and
  studies correlations with core LLM abilities. It raises the bar for environment
  interoperability. [ICLR proceedings](https://proceedings.iclr.cc/paper_files/paper/2026/hash/83a4ea71b13bc86308a2bd0b5e07fb61-Abstract-Conference.html).

## Controlled task comparisons and planning

- **TSQueryBench** (2026, ICML FMSD workshop) holds 500 synthetic time-series instances
  across ten query types and compares generation, ranking, scoring, and detection on
  unified inputs. It reports a generation–evaluation asymmetry, randomizes candidate
  order, and exposes rule-derived labels. Its single human generation annotator and
  synthetic-only data limit validity, but the same-instance operation contrast is more
  controlled than Slay-Bench's four-task horizon story.
  [arXiv:2604.02118](https://arxiv.org/abs/2604.02118).
- **Agent Planning Benchmark (APB)** supplies thousands of multimodal planning cases
  and connects benchmark-guided refinement to downstream tool tasks. It exemplifies
  the need for external criterion validity, not just internal scores.
  [arXiv:2606.04874](https://arxiv.org/abs/2606.04874).
- **DeepPlanning** targets long-horizon, constraint-verifiable plans. It is relevant to
  distinguishing long context from verifiable planning depth.
  [arXiv:2601.18137](https://arxiv.org/abs/2601.18137).

## Community-adoption comparator

HASOC is not a scientific competitor. It is an adoption model: repeated annual shared
tasks, stable organizers, released datasets, proceedings, and evolving multilingual
tracks created a durable community surface. Slay-Bench currently has a repository and
matrix, not a shared-task ecosystem. [HASOC official site](https://hasocfire.github.io/hasoc/official/index.html).

## Novelty after correction

The defensible novelty is not “first Slay LLM benchmark,” “first synergy test,” or
“first long-horizon Slay agent.” It is a deterministic, inspectable **within-simulator
operation-profile instrument** spanning immediate sequencing, combat execution,
fixed-deck recognition, and hybrid rollouts across two characters and two encodings,
plus a proposed controlled same-state horizon intervention. The intervention becomes
a contribution only after audited results exist.
