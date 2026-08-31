# Statistical audit

## Verdict

The current statistical pipeline is substantially better than the draft's original
mean±SD reporting, but it cannot rescue the invalid horizon construct. Within-task
descriptive results are usable with stronger scope and denominator language.

## Design and units

- Five base seeds are the cluster-safe paired unit for format comparisons.
- Per base seed, turn/combat/synergy generally use 20 samples. Run uses 20 for the
  original three balanced instruct models but only 5 for Qwen3-32B and Qwen3-235B.
- The minimum attainable two-sided exact sign-flip p with five nonzero pairs is
  0.0625. A single model/character contrast cannot cross 0.05 by construction.
- Synergy sample McNemar tests have up to 100 paired observations per cell, but the
  same 20 fixture families recur. Treat them as secondary to seed/fixture-clustered
  inference.

## Correct choices already present

- exact sign-flip tests rather than paired t-tests at n=5;
- Holm correction within declared metric families;
- boundary Clopper–Pearson intervals;
- hierarchical bootstrap for synergy fixtures;
- matched greedy run replay rather than a global anchor alone;
- removal-v1 exclusion from all composites and claims;
- separation of parse and illegal-action errors in later artifacts.

## Problems

### Cross-task variance claim

The legacy C6 comparison used seven models for turn/combat/synergy and only
`llama-3.1-8b`, `mistral-7b`, and `qwen2.5-7b` for N_RUN=20 run rows. The descriptive
model eta-squared shares (0.865 turn damage, 0.896 combat win, 0.629 archetype, 0.021
run floors) therefore change cohort as well as scale and task. Eta-squared is not a
unit-free latent discrimination measure. C6 is now `NOT-IDENTIFIED`.

### Equivalence margins

The historical ±0.05 margin corresponded to one observation in a 20-item rate, but
that rationale did not apply to HP ratio or progress (for Act-1 progress, 0.05 equals
0.8 floors). The pipeline now restricts equivalence tests to Bernoulli/rate metrics and
marks HP ratio/progress `NOT-ASSESSED-NO-SESOI`. Pre-register domain-specific smallest
effects of interest before restoring equivalence language for non-rate metrics.

### Multiple testing and pooling

Holm correction is within metric families, not across all headline searches. Pooled
stratified tests estimate an average magnitude and can be significant when the sign is
heterogeneous. Every pooled result must report 14-stratum direction counts. The
current structured synergy effects are magnitude-only, not universal direction.

### Missingness and selection

Early turn/combat per-sample records are unavailable, and run sample records are
unavailable for all historical artifacts. Missingness is instrumentation-era
dependent. Do not present sample-level analyses as if they cover the whole matrix.

## Current claims after correction

- Structured prompt magnitude on archetype and card pick: supported at the pooled
  matrix level, but direction is only 9/14 and 10/14 strata respectively.
- Within combat, structured prompt effects exist for win rate and HP ratio; they are
  concentrated in non-ceiling cells and are task-specific.
- Turn format sign is model-dependent.
- Hybrid-policy Act-1 survival is on par with greedy; progress differences are small,
  underpowered, and sometimes seed-consistent.
- Qwen3-235B's card-pick improvement over Qwen3-32B is the strongest paired result;
  do not generalize beyond that comparison.

## Required next analysis

For controlled-horizon-v1, use fixture-paired slopes, hierarchical intervals,
predeclared H contrasts, parse/legality mediation checks, and a power simulation before
the full matrix. Publish all fixture-level values and oracle spans.
