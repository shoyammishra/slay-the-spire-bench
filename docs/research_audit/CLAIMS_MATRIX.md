# Claims matrix

| ID | Claim in current materials | Evidence | Verdict | Allowed replacement |
|---|---|---|---|---|
| H1 | Four tasks are nested planning horizons | task names/order | **Reject** | four heterogeneous Slay-inspired operations |
| H2 | Models exhibit a horizon-collapse curve | arbitrary cross-task normalization and line | **Not identified** | task-specific performance profiles |
| H3 | A model has a maximum planning horizon | no same-task H manipulation | **Not identified** | no replacement without controlled H data |
| T1 | Turn score measures optimal turn planning | immediate damage vs bounded sequence search | **Overstated** | immediate-damage sequence quality; oracle exact only when budget unbound |
| C1 | Combat HP ratio is versus optimal play | greedy hand-order bot | **False** | HP relative to a scripted greedy reference |
| S1 | Archetype accuracy measures deck synergy understanding | authored single-label fixtures | **Overstated** | fixed-deck taxonomy recognition |
| S2 | Card pick measures strategic deck building | sole on-label option; no outcome validation | **Reject** | card-name/category alignment diagnostic |
| S3 | Removal measures pruning | constant `Strike` target | **Quarantined** | none; removal-v2 pending |
| R1 | Run task measures full-run strategic control | LLM combat/rewards; scripted route/rest/shop/events | **False** | hybrid-policy Act-1 rollout |
| R2 | Models beat greedy at run level | survival floor; small progress deltas, n=5 pairs | **Reject** | survival on par; progress generally within ~1 floor |
| V1 | Between-model variance collapses with horizon | different cohorts/tasks/scales | **Not identified** | descriptive within-task eta-squared only |
| F1 | Structured prompts beat raw generally | direction varies by task/model | **Reject** | pooled magnitude effects with 14-stratum direction counts |
| F2 | Format reaches the combat horizon | within-combat pooled effects | **Reject construct** | structured/raw differ within combat, concentrated below ceiling |
| Q1 | Qwen3-235B extends planning horizon over 32B | selective gains | **Reject** | 235B improves card pick in 4/4 cells and 19/20 seed pairs |
| Q2 | Scaling uniformly improves Slay competence | mixed/saturated/floor outcomes | **Reject** | one scale/architecture comparison is operation-selective |
| E1 | Simulator is faithful | internal tests plus documented deviations | **Overstated** | deterministic simulator with documented simplifications |
| N1 | First LLM benchmark for Slay the Spire | MiniSTS, Orak, AgenticSTS, synergy paper | **False** | a deterministic multi-operation profiling instrument |
| N2 | First LLM synergy study in Slay | Rule Synergy Analysis 2025 | **False** | whole-deck fixed-fixture complement, with validity caveats |
| P1 | Overall score summarizes strategic competence | unweighted non-commensurate average | **Invalid** | no overall score; task profile only |

## Central claim permitted now

“Across Slay-Bench's current tasks, model differences are operation-specific rather
than uniform. The clearest matched example is Qwen3-235B's card-choice gain over
Qwen3-32B without a corresponding uniform gain in immediate sequencing, combat
execution, or hybrid Act-1 rollout.”

This remains a descriptive statement in one simulator and one scale/architecture
comparison.

## Claims pending new evidence

- controlled decision-horizon slope: **PENDING EXPERIMENT**;
- externally validated synergy/card utility: **PENDING EXPERIMENT**;
- full-agent run advantage: **PENDING EXPERIMENT**;
- original-game transfer: **PENDING EXPERIMENT**;
- frontier-model ceiling: **PENDING EXPERIMENT**.
