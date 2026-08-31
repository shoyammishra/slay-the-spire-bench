# The decisive experiment: controlled decision horizon

**Protocol:** `controlled-decision-horizon-v1`
**Implementation:** `slay_bench/controlled_horizon.py`
**Status:** Infrastructure implemented and smoke-tested; model evidence **PENDING EXPERIMENT**

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
be silently labeled exact. Persist node counts and exactness per fixture/H.

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

Create at least 100 engine-generated frozen states per character stratified by:

- combat turn and current HP;
- one versus multiple enemies;
- hand branching factor and energy;
- attack/defense/setup tradeoff;
- whether the H-optimal first-action set changes between H=1 and H=8.

The last stratum is essential. States whose optimal set never changes test execution,
not lookahead. Pre-register the fixture generator and release fixture JSON before
running evaluated models. No model-specific fixture selection.

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

1. unit tests and exactness audit on H=1/2;
2. 10 fixtures × both characters × all H with mock and greedy baselines;
3. oracle sizing for H=8; prune fixtures only by predeclared, model-blind criteria;
4. one cheap open model, 30 fixtures, one format;
5. power simulation from the observed within-fixture variance;
6. registered model matrix.

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
