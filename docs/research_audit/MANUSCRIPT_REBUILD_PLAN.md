# Manuscript rebuild plan

## Narrative arc

The rebuilt paper should open with a measurement problem: heterogeneous game tasks are
often treated as levels of planning without a causal horizon intervention. Slay-Bench
then becomes both a diagnostic suite and a case study in instrument self-audit.

## Dual-track output strategy (2026-08-31)

The rebuild now produces two manuscripts with different evidentiary ceilings:

1. **PTA at NeurIPS 2026 workshop short paper (four pages, non-archival).** Report
   the existing operation profile, Qwen3 card-selection contrast, shortcut audit, and
   construct correction. Present controlled-H only as an implemented protocol with
   model results PENDING EXPERIMENT. Deadline: 2026-09-05 AoE; internal quality gate:
   2026-09-04.
2. **ICML 2027 main-track paper.** Make the controlled same-state H intervention the
   central contribution. Require treatment strength, exact-oracle audits, adequate
   power, multi-family replication, interface controls, simulator conformance, agency
   ablation, and complete traces. Internal freeze: 2027-01-15; official conference
   dates remain unannounced.

The short paper is not a compressed version of unsupported future claims. It is the
bounded instrument-audit result that exists now. The ICML paper earns a planning claim
only through new controlled evidence. Full dates, venue links, policy constraints, and
submission checklists are in `docs/submission_plan.md`.

## Proposed outline

1. **Introduction**
   - motivate verifiable decision profiles;
   - state the revised operation-specific thesis;
   - explicitly deny that current tasks identify horizon.
2. **Related work**
   - direct STS lineage first: MiniSTS, Rule Synergy Analysis, Orak, AgenticSTS;
   - game benchmarks: GameBench, PokerBench, LUDOBENCH, LMGame-Bench;
   - controlled planning/evaluation: TSQueryBench, APB, DeepPlanning.
3. **Simulator and control surfaces**
   - mechanics coverage and known deviations;
   - table of LLM-controlled versus scripted decisions;
   - versioning and RNG.
4. **Decision tasks**
   - use operational names, not horizon labels;
   - exact inputs, outputs, samples, references, and failure policies;
   - label shortcut caveat before results.
5. **Experimental design**
   - model/config table, decoding, seeds, N_RUN tiers;
   - provenance limitations of historical artifacts;
   - predeclared statistical families and power ceiling.
6. **Results: task profiles**
   - within-task tables/heatmaps only;
   - Qwen3-235B/32B paired card-choice result as central figure;
   - prompt-format heterogeneity;
   - hybrid-run versus greedy.
7. **Instrument falsification**
   - removal-v1 constant shortcut;
   - synergy dictionary 120/120 shortcut;
   - cross-task scalar invalidation;
   - what conclusions change.
8. **Controlled decision-horizon protocol**
   - design and validation only until inference is run;
   - label all results **PENDING EXPERIMENT**.
9. **Limitations and validity**
   - simulator fidelity, authored utility, ecological transfer, model cohort, traces.
10. **Conclusion**
   - profiles now; causal horizon measurement next.

## Figure plan

Remove:

- horizon-collapse line;
- radar/spider plots;
- any overall score;
- figures that join tasks on a common y-axis.

Keep or build:

1. task/control-surface schematic;
2. model × operation heatmap with separate legends/units per panel;
3. Qwen3 paired seed slopegraph for card pick across four cells;
4. prompt-format forest plot with 14-stratum directions;
5. hybrid-run progress distribution against matched greedy;
6. shortcut baseline table;
7. controlled-H protocol diagram marked pending.

## Table plan

- task construct/oracle/agency table;
- exact model and sample-count table separating N_RUN=5 and N_RUN=20;
- direct competitor comparison;
- claims/limitations matrix;
- simulator conformance status;
- artifact completeness table.

## Required edits to existing files

- `docs/draft.md`: supersession banner now, then full rewrite from this outline.
- `docs/novelty_and_related_work.md`: remove first-in-domain claims and add direct STS
  work.
- `docs/findings.md`: replace horizon language with operation profiles; preserve dated
  old entries as superseded.
- `docs/stats_report.md`: regenerate after C4/C6/C7 corrections.
- `README.md`: advertise deterministic profiling and pending controlled-H work.
- `docs/report.md`, `docs/report.html`, `docs/report_matrix.html`, `docs/notes.md`: add
  historical/non-authoritative warning; do not silently rewrite old evidence.

## Submission gates

### Minimum defensible workshop/domain paper

- all current claims corrected;
- shortcut audit and artifact limitations included;
- no invalid cross-task scalar;
- focused tests and four mock pipelines pass;
- public-repo security scan clean.

### Strong benchmark venue

- expert/prospective label validation;
- simulator conformance results;
- complete schema-2.0 traces for a representative matrix;
- external reproduction.

### Top-tier planning venue

- controlled-H model results with treatment strength and adequate power;
- replicated slope across multiple model families;
- interface/memory/parse controls;
- original-game or independent-environment transfer;
- claims registered before expensive inference.

## Immediate status

The code-side P0 guardrails and controlled-H infrastructure are implemented. The
existing numerical matrix remains historical evidence; no model result has been
invented or reinterpreted as a controlled horizon result.
