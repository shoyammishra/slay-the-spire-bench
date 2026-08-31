# Oracle and ground-truth audit

| Surface | Current reference | Is it exact? | Degenerate policy | Verdict |
|---|---|---:|---|---|
| Turn damage | DFS over card-index sequences, node budget 20,000 | conditional on budget not binding | attack-first/order heuristic can be strong on starter hands | persist node count/exact flag; call “bounded exhaustive search” |
| Combat HP | greedy bot plays every playable card in hand order | no | the comparator itself often wins and sits near ceiling | call “greedy HP reference,” never oracle/optimal |
| Combat win | absolute outcome | outcome exact in simulator | greedy policy wins many fixtures | valid simulator outcome, weak discriminator |
| Archetype | authored signature-card dictionary | no external ground truth | same dictionary lookup scores 100% | label-recognition diagnostic only |
| Card pick | sole on-archetype offer | no prospective utility validation | dictionary lookup scores 100% | invalid as planning/synergy utility measure |
| Removal-v1 | always `Strike` | no | constant `Strike` scores 100% | quarantined; never restore in place |
| Run | survival/progress in simulator | exact for implemented simulator | scripted greedy is on par | valid environment outcome, not external game competence |
| Controlled H v2 | exhaustive value-to-go at fixed H | exact or explicit node/time exception | H=1 greedy and H-mismatch controls | appropriate after observability, fixture, and budget audit |

## Turn oracle checks required

`nodes_expanded`, `node_budget`, and `exact` are now persisted in future samples. A
compute-free current-code replay over the paper seed schedule found 0/100 bound hits
for each character (Ironclad maximum 17 nodes; Silent maximum 137, budget 20,000).
This is not proof of historical-commit identity because old JSONs lack commits. Any
future bound hit invalidates the word “optimal.”
Compare against dynamic programming or a second independent enumerator on a small
known-answer suite. Include duplicate-card identity cases and target combinations.

## Synergy label validity plan

Version card-pick-v2 rather than editing historical fixtures. Construct realistic deck
states with 4–6 plausible options, including skip, and obtain at least three blinded
expert rankings with rationale. Predeclare ambiguity handling. Validate chosen cards
prospectively through large matched simulator rollouts or a strong policy, reporting
the causal value difference and uncertainty. Counterbalance card identity and position
so no name-only or position-only rule exceeds chance.

Removal-v2 needs varied targets, balanced candidate identities, deck-state-specific
justification, and downstream value validation. It invalidates all historical synergy
prompt comparability and therefore requires a full re-baseline.

## Controlled-horizon oracle

`slay_bench/controlled_horizon.py` fails closed if its search budget is exceeded. It
values all legal first actions using one fixed utility at every H. Before inference:

- verify that oracle-relevant continuation state is present in the model prompt;

- independently replay every returned optimal action;
- check permutation invariance under duplicate card identities;
- persist ties and oracle span;
- reject zero-span states from the primary quality analysis;
- verify H-sensitive states where the optimal first-action set changes;
- compare a small set against manual trees.

No model result currently exists: **PENDING EXPERIMENT**.
