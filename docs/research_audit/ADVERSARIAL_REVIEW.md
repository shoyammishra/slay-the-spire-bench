# Adversarial research review

**Audit date:** 2026-08-30
**Recommendation:** Reject in the current form
**Confidence:** 5/5
**Current top-tier readiness:** 2/10
**Potential after the decisive rebuild:** 7/10, conditional on new evidence

## Executive verdict

The implementation is unusually transparent for an early benchmark, and the saved
matrix supports several useful descriptive statements. It does **not** support the
paper's central “planning-horizon collapse” construct. The four columns are different
tasks with different inputs, action spaces, targets, baselines, difficulty, and
amounts of model control. Joining them with a line does not turn task order into an
experimental horizon variable. The resulting curve is a visualization-induced causal
claim.

The strongest surviving result is narrower: **performance is operation-specific in
this simulator.** The cleanest comparison is Qwen3-235B-A22B-FP8 versus Qwen3-32B:
card-addition accuracy improves in all four character/format cells and 19/20 matched
seed cells, while the other tasks do not show a uniform corresponding gain. That is a
valuable profile result, not evidence of a longer planning horizon. It is also
confounded by dense-versus-MoE architecture and one model-family comparison.

## Fatal issues

1. **The independent variable is absent.** “Turn → combat → synergy → run” changes
   task identity rather than manipulating lookahead while holding the decision problem
   fixed. No horizon-length causal effect or latent collapse point is identified.
2. **The run task is misdescribed.** Under the benchmark default, the model controls
   combat actions and card rewards. The harness scripts the leftmost map node, rest
   decisions, merchant policy, and event option 0. This is a hybrid scripted-policy
   rollout, not full-run strategic control.
3. **Synergy ground truth admits a perfect non-planning shortcut.** All fixed decks are
   single-archetype, and every offer contains exactly one card in that archetype's
   shipped name dictionary. `scripts/instrument_diagnostics.py` scores a dictionary
   lookup at 100% on 120/120 fixture-position cases. Removal-v1 is worse: every target
   is `Strike`, and is already correctly quarantined.
4. **The cross-task scalar is invalid.** The horizon line, radar, and overall score
   average or connect non-commensurate quantities. Chance normalization does not
   establish measurement invariance. These outputs are now retired in code.
5. **Simulator validity is asserted, not established.** Internal deterministic tests
   show implementation consistency, not fidelity to Slay the Spire. Known omissions
   include usable potions, several event combats and choices, and timing/content
   approximations. “Faithful simulator” is too strong.

## Major issues

- Turn evaluation is immediate-damage sequencing on starter-deck Cultist openings;
  it explicitly ignores defense and setup. The 20,000-node cap must be audited before
  calling every oracle exact.
- Combat uses only Cultist and Jaw Worm and compares HP to a greedy hand-order bot,
  not an optimal oracle. Win rate is saturated for many instruct models.
- The archetype labels and best-card choices have no independent expert annotation,
  ambiguity adjudication, or prospective run-utility validation.
- Cross-task eta-squared comparisons used seven models for turn/combat/synergy and
  three N_RUN=20 models for run. Even with a common cohort, eta-squared on different
  scales would not establish a horizon effect. Claim C6 is now `NOT-IDENTIFIED`.
- Five base seeds make the smallest two-sided paired sign-flip p-value 0.0625.
  Sample-level McNemar tests reuse the same fixture families and cannot replace the
  cluster-safe result.
- A universal ±0.05 equivalence margin is justified for 20-item rates, not HP ratios
  or progress. Domain-specific smallest effects of interest are missing.
- The historical artifacts have no commit, provider, decoding, dependency, routing,
  or instrument-version record. Of 181 result JSONs inventoried, 0 contain complete
  provenance; run-level per-sample records are absent from all 181.
- Early artifacts also omit turn/combat samples and raw completions, preventing full
  post-hoc error audit.

## Minor issues

- `route_optimality` is a serialized placeholder with no implemented score.
- Structured and raw prompts are semantically intended to match, but semantic
  equivalence is not a substitute for byte-level versioning.
- Requirements use lower bounds and had omitted the direct NumPy dependency.
- Several historical reports preserve superseded claims without a page-level warning.
- “Expert,” “oracle,” “optimal,” and “full run” are used too loosely.

## Evidence that survives

- The benchmark can reproducibly profile immediate-damage sequencing, two-enemy
  combat execution, fixed-deck label recognition/card lookup, and hybrid-policy Act-1
  rollout in its own simulator.
- Across the complete seven-model matrix, prompt format effects are task- and
  model-dependent. The current pooled structured advantage on synergy is a magnitude
  result; direction is not universal.
- Qwen3-235B's card-pick gain over Qwen3-32B is the strongest matched result.
- Act-1 survival is at a floor for all evaluated configurations; progress is generally
  within about one floor of a matched scripted greedy policy. Report this as “on par,”
  not a win and not a horizon collapse.

## Required disposition

Retitle and rewrite the current paper as an instrument/profile study, or run the
versioned controlled-decision-horizon experiment before making any horizon claim.
Do not submit the current horizon manuscript to a top-tier venue.
