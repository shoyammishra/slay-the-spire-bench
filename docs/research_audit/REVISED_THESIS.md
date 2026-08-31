# Revised thesis

## One-sentence thesis

**Current language models show operation-specific, not uniformly scaling, competence
across deterministic Slay-inspired decision tasks; the strongest matched scale contrast
improves card selection without establishing a longer planning horizon.**

## Candidate title

**Slay-Bench: Diagnosing Operation-Specific LLM Decision Competence in a Deterministic
Deck-Building Simulator**

## Revised abstract

Game environments offer verifiable outcomes, but benchmark labels such as “planning”
often conflate lookahead with task, interface, and control surface. We present
Slay-Bench, a deterministic Slay the Spire simulator and diagnostic suite covering two
characters, structured and natural-language encodings, and four decision operations:
immediate-damage sequencing, short-combat execution, fixed-deck taxonomy/card
selection, and hybrid-policy Act-1 rollout. We evaluate seven model configurations on
matched seeds and report exact paired tests, clustered uncertainty, parse/legality
failures, and scripted-policy references. The results do not support a single
cross-task planning score. Instead, model and format effects are operation-specific.
The clearest matched comparison is Qwen3-235B-A22B-FP8 versus Qwen3-32B: card-selection
accuracy improves in all four character/format cells and 19 of 20 seed pairs, without a
uniform corresponding gain on the other operations. Act-1 survival remains on par
with a scripted greedy policy. An adversarial instrument audit further shows that a
card-name lookup solves all fixed synergy fixtures, limiting those scores to
recognition rather than forward planning. We release compute-free diagnostics and a
versioned same-state decision-horizon protocol whose model results are pending. The
study argues for reporting decision profiles and causal benchmark interventions rather
than inferring latent planning depth from heterogeneous task aggregates.

## Contributions that can be claimed now

1. A deterministic, inspectable two-character simulator and decision-profile harness.
2. A complete seven-configuration × two-character × two-format matrix with matched
   seed analysis and explicit run-tier caveats.
3. Evidence of operation-selective capacity in the Qwen3 scale/architecture contrast.
4. An adversarial shortcut and provenance audit that falsifies parts of the original
   instrument interpretation.
5. Implemented infrastructure for a controlled same-state H intervention, with no
   fabricated results.

## Claims deliberately abandoned

- four nested planning horizons;
- horizon-collapse curves or model horizon limits;
- one overall strategic score;
- full-run autonomous strategy under default settings;
- externally faithful simulation;
- fixed-fixture synergy as forward planning.

## Scientific ceiling

This thesis can support a strong benchmark/instrument paper if simulator validity and
label utility are independently validated. A top-tier planning paper additionally
requires successful controlled-H evidence, adequate power, multi-family replication,
and complete traces.
