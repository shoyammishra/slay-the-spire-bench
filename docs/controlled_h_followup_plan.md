# Controlled-H follow-up after pilot power failure

**Date:** 2026-09-05. **Status:** planning recommendation, not an executable
preregistration or compute authorization. The original pilot remains NO-GO.

**Implementation supersession, later 2026-09-05:** the separate fixture
expansion is now frozen at `configs/controlled_h_v2_expansion.json`, digest
`bfe8c130…1288b`. Its planning scope is Qwen3-32B/structured and two
character-specific primary tests at alpha .025 each, with 252 fixtures per
character. The full inference/analysis protocol remains unfrozen. The new
runner and commands are in `controlled_h_expansion_runbook.md`; the planning
alternatives below are retained as rationale. Only generation and a tiny
oracle smoke have run, alongside mock validation; no full audit or inference.

## Recommendation

Preserve the .10 absolute H8-minus-H1 quality target, paired design, four H
values, exact-oracle gates, and 25% sensitive / 75% control target mixture.
Develop a separately versioned expanded fixture release before further model
inference. Exclude all 30 pilot-exposed fixture IDs from its confirmatory set
as a prospective safeguard; the original pilot prohibited response reuse but
did not itself require fixture exclusion. Preserve the original release and
failed pilot artifacts unchanged.

Use **252 fixtures per character as the provisional planning case for two
primary character-specific tests**, each sized at alpha .025 (a Bonferroni
allocation of familywise .05). This is not a frozen sample size for a
multi-family matrix. Final hypothesis-family definition and fresh-model
variance checks must precede that freeze. Expanding the pool is the next
engineering work; launching the current 100-per-character matrix is not.

## Evidence and sizing

The retrieved pilot has 15 complete H1/H8 pairs per character. Its single
truncation occurs at H=2 and cannot explain the primary variance. All source
bindings, prompt bytes, scores, and legality checks passed the offline audit.
Conservative bootstrap SDs are .44802056 Ironclad and .51325527 Silent.
The frozen normal-approximation method gives:

| Alpha per contrast | Required N Ironclad / Silent | Balanced N per character | Sensitive / controls per character | Queries per model and format |
|---|---:|---:|---:|---:|
| .05, original individual test | 158 / 207 | 208 | 52 / 156 | 1,664 |
| .025, two-test planning case | 191 / 251 | 252 | 63 / 189 | 2,016 |
| .0125, four-test illustration | 224 / 294 | 296 | 74 / 222 | 2,368 |

Balanced sizes round the larger requirement up to a multiple of four to
preserve the exact mixture. These calculations target 80% marginal power for
each .10 contrast under the Qwen3 pilot variance bound; they do not establish
80% joint power across tests, power for cross-model differences, or adequate
power for another model or prompt format. Conservative SD estimation does not
remove the normal approximation's limitations. The pilot has only four
sensitive observations per character and a 4/15 mixture versus the target 1/4.
New strata, models, or format variances may require a larger design.

At N=100, the same calculation gives approximately 60.7% Ironclad and 49.5%
Silent power. Increasing the target effect to match the observed negative
pilot means would change the scientific question after seeing outcomes.

## Actual fixture capacity

Inventory uses persisted release eligibility, not merely exact-oracle counts.
It retains the combined protocol's restriction that the first Silent extension
may supply controls only; its four sensitive rows remain excluded.

| Character | Eligible sensitive, excluding pilot | Eligible controls, excluding pilot | New sensitive / controls needed for N=252 |
|---|---:|---:|---:|
| Ironclad | 92 | 106 | 0 / 83 |
| Silent | 55 | 81 | 8 / 108 |

For the unadjusted N=208 case, control shortages are still 50 Ironclad and
75 Silent. Neither expanded design is available from the current exact pool.

The base audit's 118 exact Ironclad controls include fixture suffix 0394,
whose H=8 best and worst values are both 1045. It fails the nonzero-span gate,
leaving **117 eligible base controls**, or 106 after excluding pilot fixtures.
This clarifies the historical count without changing the released 200 fixtures.

The original screen has 111 Ironclad and 127 Silent screen-insensitive
candidates not yet fully audited. Their full-H outcomes are unknown: screen
insensitivity does not guarantee an H1/H8 control. The first Silent extension
yielded 22 controls from 50 candidates; that observation is not a guaranteed
yield or an independent probability model for the remaining ranks. The N=252
control shortages would require roughly 75% and 85% control yields from the
remaining pools. Plan for possible new candidates rather than promising that
this remainder will fill the release.

## Follow-up protocol to implement before expensive work

1. Define the primary hypothesis family and analysis population. The two-test
   planning case covers one designated model/format and two characters. A
   scaling claim needs direct model contrasts and separate power analysis;
   two significant within-model results do not establish a scaling effect.
2. Freeze a candidate-expansion protocol binding all source hashes, excluding
   pilot IDs, retaining original dispositions, and specifying a fixed candidate
   count, nonoverlapping seeds, recipe distribution, ranking, advancement,
   budgets, and every stop/exclusion rule. Do not choose fixtures by model loss.
   Any newly permitted source stratum must be disclosed explicitly.
3. Use a tiny model-free generator/oracle smoke before the full new funnel.
   Audit all predeclared candidates and fail closed on quota shortfalls.
   Keep current per-H exactness limits (2,000,000 nodes and 120 seconds) unless
   a separate comparability decision changes them. Do not rerun old timeouts
   under a larger budget and silently pool them with old eligible rows.
4. Validate the expanded release's prompt invariance, uniqueness, source
   composition, oracle spans, H-mismatch losses, and degenerate policies. Use
   deterministic ranking within fixed strata; do not pick successful rows by
   completion order. Freeze the artifact hashes before new model outputs.
5. Freeze model revisions, response budgets, query ordering, failure handling,
   inference family, and power procedure. In particular, specify how incomplete
   H1/H8 pairs affect the primary analysis before collecting them; all pilot
   pairs are complete, so they do not resolve this future analysis choice.
6. Run a separately authorized exact-stack smoke and any required fresh-model
   variance pilot, then assess gates before separately authorizing the matrix.

The first remaining-pool audit alone would be 238 candidates. Four 120-second
per-H ceilings imply a nominal maximum sum of 31.73 CPU hours of oracle-budget
time if every candidate reaches every ceiling, excluding overhead; this is not
a measured runtime or a job wall-time estimate. Additional generation can
increase cost. No such audit was launched for this plan.

For N=252, one model/format requires 2,016 queries; two models in one format
require 4,032, and two models in both formats require 8,064. At an 8,000-token
output cap those are caps of 16.128M, 32.256M, and 64.512M output tokens,
respectively, excluding input tokens, smoke/pilot calls, and overhead. These
are workload arithmetic, not price or runtime forecasts, and their larger
hypothesis families are not covered by the two-test power case automatically.

## Alternatives considered

- Keep N=100 and accept low power: could support a separately framed estimation
  study, but cannot be called a passed version of the registered matrix.
- Relax alpha, drop controls, change normalized quality, or use the observed
  effect magnitude for sizing: changes the target or decision rule after the
  pilot. No such change is adopted.
- Repeat deterministic queries on the same states: does not supply additional
  independent fixture pairs; a repeated-response study needs a new estimand and
  variance model.
- Expand fixtures while preserving the scientific target: recommended, with
  disclosed adaptive study sizing, fresh confirmatory fixtures/responses, and
  explicit model-family and multiplicity scope before freezing compute.

## Comparability and reproducibility

No engine, prompt, scorer, frozen protocol, or published number changes here.
An expanded release changes the evaluated fixture population and must have a
new protocol ID and separately reported results. Do not merge pilot responses
or silently replace the old NO-GO. Negative pilot effects remain exploratory.

Offline arithmetic and source hashes are saved in ignored
`results/controlled_h_followup_sizing.py` and
`results/controlled_h_followup_sizing.json`; the per-row audit is in
`results/controlled_h_v2_retrieved_pilot_audit.json`. Significant choices and
attempts are also recorded in the decision and experiment logs. No production
code changes or inference were needed for this recommendation.
