# Reviewer 2 report

## Summary

This paper claims to localize where language-model planning collapses by evaluating
four “nested horizons” in a Slay the Spire simulator. The engineering effort is
substantial, the failure logs are unusually candid, and the model matrix is larger
than the draft's closest internal predecessor. Unfortunately, the paper does not
measure the named construct. It compares four heterogeneous benchmarks and interprets
their ordered display as a dose-response curve.

## What I checked

I traced the CLI, evaluators, prompt builders, simulator transitions, statistics,
visualization code, tests, saved aggregates, experiment log, decision log, and current
draft. I also compared the work with 2024–2026 game and agent benchmarks. I treated
saved artifacts and code as authoritative when prose disagreed.

## Strengths

- Deterministic RNG streams and matched base seeds make many within-task comparisons
  auditable.
- The authors preserve failures and have already quarantined a broken removal metric.
- Both characters and two surface forms are covered.
- Exact paired tests, boundary intervals, and matched greedy replays are better than
  mean-only reporting.
- The Qwen3-235B/32B card-choice contrast is interesting and honestly bounded in the
  latest logs.

## Core objection

There is no controlled “horizon” factor. The first task asks for immediate damage on
a starter opening. The second asks for repeated actions against two easy enemies. The
third is a static classification/multiple-choice lookup. The fourth is a long hybrid
rollout where scripted code makes most strategic route/resource choices. Any decline
could be caused by task difficulty, stochastic exposure, number of calls, parsing,
oracle quality, action-space mismatch, or reduced agency. The paper cannot assign it
to horizon.

Worse, the central plot applies arbitrary transformations and draws connected lines
between those quantities. This presentation manufactures continuity. A reader will
reasonably infer a common latent scale and monotone intervention that do not exist.

## Additional scientific concerns

1. The synergy fixtures are tautological. Their construction guarantees exactly one
   on-label offer. A deterministic card-name dictionary solves all cases. The paper is
   measuring recognition of the authors' taxonomy, not synergy planning or downstream
   value.
2. The “run agent” is not an agent over the full decision surface at default settings.
   It cannot choose ordinary routing, shops, or event options.
3. The combat “oracle” is a greedy comparator. Calling HP ratio optimality is wrong.
4. Internal unit tests do not validate external simulator fidelity. The known mechanic
   deviations are consequential to full-run claims.
5. The model-variance decomposition compares different cohorts and tasks. Statistical
   significance cannot repair construct invalidity.
6. The literature review misses the most direct Slay the Spire work, including
   AgenticSTS, Orak, Language-Driven Play/MiniSTS, and Rule Synergy Analysis.

## Questions the authors must answer

- What observation would falsify “planning-horizon collapse” rather than merely move
  a point on the authors' arbitrary normalization?
- Why should a static label-selection task be longer-horizon than a multi-turn fight?
- What decisions does the model actually control in the reported run cells?
- What is the prospective utility of the “expert” synergy choices?
- How often does the turn oracle hit its node budget?
- Can an input-only shortcut, random policy, always-first policy, label lookup, greedy
  combat policy, and scripted run policy reproduce each headline metric?
- Which original-game mechanics were validated against an independent reference?
- Are any cross-task model rankings stable after using a common model cohort?

## Recommendation

**Reject.** The gap is conceptual rather than cosmetic. A publishable revision must
either (a) abandon the horizon thesis and present task-specific profiles with strong
simulator/label validation, or (b) implement a controlled same-state horizon
intervention. The new `controlled-decision-horizon-v1` infrastructure is an appropriate
start, but it currently has no model results: **PENDING EXPERIMENT**.
