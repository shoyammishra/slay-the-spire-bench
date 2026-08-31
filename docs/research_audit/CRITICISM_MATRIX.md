# Criticism and response matrix

| Criticism | Severity | Evidence location | Can current data answer it? | Required action | Status |
|---|---:|---|---:|---|---|
| No controlled horizon variable | Fatal | evaluator/task definitions | No | run controlled-decision-horizon-v2 | infrastructure ready; **PENDING EXPERIMENT** |
| Cross-task line implies a latent scale | Fatal | `visualize.py`, old draft | Yes | retire curve/radar/overall | implemented |
| Default run is not full agency | Fatal to run claim | `RunEvaluator`, `run_loop.py` | Yes | rename hybrid policy; add agency ablation | rename planned; experiment pending |
| Synergy admits lexical lookup | Fatal to planning claim | fixtures/tables | Yes | publish shortcut audit; build card-pick-v2 | lookup audit implemented; v2 pending |
| Removal target constant | Fatal to metric | all 40 fixtures | Yes | quarantine, version v2 | complete |
| Combat reference is not optimal | Major | `_greedy_combat_hp` | Yes | rename and add stronger policies | rename required |
| Turn oracle may hit budget | Major | bounded DFS | Partly | persist node count/exactness; audit all states | pending |
| Simulator lacks external fidelity evidence | Major | design deviations | No | conformance suite and independent trace audit | pending |
| Eta-squared uses different cohorts | Major | stats variance rows | Yes | mark horizon claim not identified | implemented |
| Universal equivalence margin unjustified | Major | stats TOST | Yes | metric-specific SESOIs or remove equivalence | pending |
| n=5 paired tests underpowered | Major | exact p floor | Yes | state power ceiling; size controlled study | documented |
| Sample-level independence overstated | Major | repeated fixed fixtures | Yes | cluster by fixture/seed; secondary McNemar | documented |
| No prospective utility for card labels | Major | synergy design | No | expert ranks + downstream rollouts | pending |
| Missing current direct related work | Major | draft bibliography | Yes | rewrite related work | audit completed |
| Historical result provenance incomplete | Major | 181 artifact inventory | No retroactive repair | new schema + limitation statement | new schema implemented |
| Run traces absent | Major | 0/181 run sample records | No | persist future decision traces | pending |
| Raw completions unavailable | Major | saved JSON schema | No | versioned trace release policy | pending |
| Requirements not closed | Minor/Major artifact | requirements | Partly | declare NumPy; add lock/container | NumPy done; lock pending |
| `route_optimality` placeholder | Minor | `RunScore` | Yes | remove or implement in next schema | pending |
| Historical docs repeat stale thesis | Major communication | draft/report/notes | Yes | supersession banners and manuscript rebuild | in progress |
| No community task/adoption plan | Minor for paper, major for benchmark | repo | No | stable release, leaderboard governance | P2 |

## Response discipline

No response should claim that extra statistics fix construct validity. “Future work” is
not an answer to a fatal current claim; the claim must be removed now. New instruments
receive new version IDs and do not silently replace historical scores.
