# The decisive experiment: controlled decision horizon

**Protocol:** `controlled-decision-horizon-v2`
**Implementation:** `slay_bench/controlled_horizon.py`
**Status (superseded 2026-09-05):** Combined 200-fixture release passed; real
120-query pilot completed and was audited. All interface gates pass, but the
power gate fails (required N=158 Ironclad / 207 Silent, ceiling 100 each).
Confirmatory model evidence remains **PENDING EXPERIMENT**. The run plan and
100-per-character target below describe the original protocol; the failed
gate must not be relabelled. A separately labelled fixture expansion is now
frozen and its full oracle audit is running; see
`../controlled_h_expansion_runbook.md`. The confirmatory model inference and
analysis protocol remains unfrozen.

V2 supersedes v1 before model inference. V1 admitted identical model prompts with
different oracle labels because hidden draw order affected future value. V2 appends a
canonical full-observability continuation block at every H, including pile order,
combat/enemy runtime state, and deterministic RNG stream state. Only H may differ
within a fixture/format treatment contrast.

The original frozen v2 funnel audited all 483 advanced rows but failed closed because
Silent produced 70 of the required 75 controls. That registered outcome remains a
failure. A separately frozen, fully disclosed Silent-control extension audited the
next 50 eligible original-rank candidates and yielded 22 controls, four sensitive
rows, and 24 timeouts. The combined protocol
`controlled-h-v2-plus-silent-extension-release-2026-09-04` (digest
`71461857…db99b`) binds both source artifacts and reruns the original model-blind rank
rule over eligible rows. It passed with 200 unique fixtures: exactly 25 sensitive and
75 controls per character, using 185 base rows and 15 extension controls. An
independent per-fixture audit passed exactness, prompt invariance, nonzero-span,
mismatch-regret, balance, source, and uniqueness checks. The 25% sensitive ratio is a
designed stratum, not a prevalence estimate, and the sequential repair must accompany
every use of this release.

## Question

Does next-action quality deteriorate as the amount of future state that must be
considered increases, when the state, action vocabulary, model, prompt encoding,
objective, simulator, and oracle are otherwise held fixed?

## Intervention

For each frozen post-draw combat state, query the model four times with H ∈ {1,2,4,8}
future **decision transitions**. A transition is either playing one legal card or
ending the turn. The prompt differs only in the integer H. The response contract is
always `{action, card_index, target_index, reasoning}`.

The oracle exhaustively values every legal first action to exactly H transitions.
Terminal utility is fixed across H:

`enemy HP lost − player HP lost + 1000·win − 1000·loss`.

Search exceeding the declared node budget raises `OracleBudgetExceeded`; it must not
be silently labeled exact. Search exceeding the declared wall-time ceiling likewise
raises `OracleTimeBudgetExceeded`. Persist unique expanded states, total search calls,
cache hits, wall time, budget failures, and exactness per fixture/H.

## Primary estimand

Within `(model, character, format, fixture)`, estimate the change in normalized
first-action quality per log2 increase in H. Quality is 1 for an H-optimal action and
0 for the worst legal first action under the same H, with value interpolation between.
Report raw regret alongside normalized quality because zero oracle spans make the
normalized score uninformative.

The confirmatory contrast is H=8 minus H=1. Use a fixture-clustered paired bootstrap
and a permutation test that swaps H labels within fixture only where exchangeability
is justified. Report the complete distribution, ties, illegal/parse rates, and oracle
span. Do not pool characters or prompt formats until interaction estimates are shown.

## Fixtures

Release 100 engine-generated frozen states per character (200 total) stratified by:

- combat turn and current HP;
- one versus multiple enemies;
- hand branching factor and energy;
- attack/defense/setup tradeoff;
- whether the H-optimal first-action set changes between H=1 and H=8.

The last stratum is fixed at 25 disjoint H=1/H=8 states and 75 controls per character.
States whose optimal set never changes test execution, not lookahead. The complete
800-candidate funnel and release fixture JSON must be preserved before running evaluated
models. No model-specific fixture selection is permitted.

Historical base stages were run with:

```powershell
python scripts/controlled_horizon_funnel.py manifest --out results/controlled_h_v2_frozen_manifest.json
python scripts/controlled_horizon_funnel.py screen --out results/controlled_h_v2_frozen_screen.json
python scripts/controlled_horizon_funnel.py full --screen-audit results/controlled_h_v2_frozen_screen.json --out results/controlled_h_v2_frozen_full.json
python scripts/controlled_horizon_funnel.py release --full-audit results/controlled_h_v2_frozen_full.json --fixtures-out results/controlled_h_v2_release_fixtures.json --out results/controlled_h_v2_release_audit.json
```

The original release command correctly emitted no fixtures. The usable 200-row
artifact comes only from the separately labelled combined-release procedure recorded
in `docs/experiment_log.md`.

## Baselines and falsifiers

- uniform legal action;
- always end turn;
- first legal card;
- immediate-damage greedy;
- one-step utility greedy;
- H-aware exact oracle;
- H-mismatched oracle (use the H=1 action at H>1);
- shuffled state/card-name control;
- rules-hidden and rules-provided prompt control;
- parse-perfect deterministic adapter.

The intervention is valid only if H-mismatched greedy loses on the horizon-sensitive
fixture subset and the exact oracle remains 1.0. If no fixture changes its optimal
action across H, the instrument has no treatment strength.

## Power and run plan

Buy information cheapest-first:

1. unit tests, exactness audit, and the combined 200-fixture release — complete;
2. freeze a model-blind 30-fixture pilot (15 per character; four sensitive + 11
   controls), Qwen3-32B, structured format, all four H, and balanced query order —
   complete under active protocol digest `465bab1d…104f` (the earlier no-inference
   mock digest was superseded when the deployment revision and serving stack were
   pinned);
3. run all 120 calls through the exact stack with a no-inference mock, preserving
   prompts, hashes, raw responses, parsed traces, and checkpoint resume — complete;
4. run the prospective power table and freeze the conservative pilot-bootstrap gate —
   complete;
5. after explicit compute authorization, run the real Qwen3-32B pilot and use it only
   for interface feasibility and variance sizing;
6. seek separate authorization for the registered multi-family matrix only if the
   frozen pilot gate passes. Pilot responses are not reused confirmatorily.

No API, GPU, or cluster call is authorized by this document. All model runs remain
**PENDING EXPERIMENT**.

## Decision rule

- A consistently negative within-state H slope, with nontrivial treatment strength and
  no corresponding parse/legality slope, supports a bounded claim about decision
  horizon in these combat states.
- A flat slope falsifies the proposed collapse within this range.
- A slope explained by parse failures, prompt length, or action-set changes is an
  interface result, not planning.
- Cross-model differences require direct slope contrasts, not separate significance.

## Threats remaining after this design

The fixed terminal utility is still an authored proxy; exact search is only as valid as
the simulator; H counts actions rather than semantic plans; model pretraining may
contain card knowledge; and combat microstates do not establish full-run competence.
These are limitations, not reasons to return to the invalid four-task curve.
