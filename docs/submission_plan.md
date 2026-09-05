# Submission plan

**Established:** 2026-08-31

**Authoritative for:** venue strategy, submission deadlines, manuscript separation,
and the paper critical path.

## Decision

Run two coordinated but scientifically distinct tracks:

1. Submit a short, non-archival workshop paper to **PTA: From Pretrained
   Representations to Acting Agents at NeurIPS 2026**.
2. Build the controlled-decision-horizon study into an **ICML 2027 main-track**
   paper.

CORE A* refers to the NeurIPS and ICML parent conferences, not to a workshop paper.
The workshop contribution is valuable for feedback and visibility but is not an A*
archival publication.

## Track A: NeurIPS 2026 PTA workshop

Official call: <https://ptaworkshop.github.io/call-for-papers.html>

| Item | Requirement |
|---|---|
| Submission deadline | **2026-09-05, Anywhere on Earth** |
| Format | NeurIPS 2026, double-blind |
| Chosen track | Short submission, maximum 4 content pages |
| Archival status | Non-archival; no formal proceedings |
| Notification | 2026-09-29 |
| Camera ready | 2026-11-25 |
| Workshop | 2026-12-11 or 12, Sydney |

### Workshop thesis

Heterogeneous decision tasks reveal operation-specific language-model competence;
they do not identify a single planning horizon. In Slay-Bench, the clearest matched
model-family comparison is a card-selection gain, while an adversarial audit exposes
shortcut labels and invalidates the former cross-task horizon interpretation.

Current title:

> From Pretrained Knowledge to Action: Auditing Language Models in a Deterministic
> Game

### Four-page content contract

1. Measurement problem and bounded thesis.
2. Deterministic environment, four operational tasks, and model-control surfaces.
3. Seven-configuration profile with the Qwen3-235B/32B card-pick comparison.
4. Shortcut audit: removal-v1 constant answer and synergy dictionary lookup.
5. Consequence: retire cross-task scalars and horizon curves.
6. Same-state controlled-H protocol as an audit-derived methodological specification;
   the text and caption explicitly claim no model-level horizon result.

The workshop paper must not claim nested horizons, a general planning score,
full-run autonomous control, simulator faithfulness, or controlled-H model evidence.

### Submission checklist

- four-page anonymized PDF in the current NeurIPS style;
- omit the NeurIPS paper checklist: the official PTA call explicitly exempts workshop
  submissions even though the general template includes it;
- one operation-profile figure with task-specific units;
- one compact construct/shortcut table;
- citations verified against primary sources;
- public-repository and PDF anonymity scan;
- no identifying public repository URL in the blinded paper;
- confirm attendance expectations and travel feasibility with the workshop organizers;
- final author approval before any external submission.

If a polished, independently readable PDF is not ready by **2026-09-04**, do not
submit a rushed manuscript. Fall back to an ICLR 2027 non-archival workshop.

## Track B: ICML 2027 main track

ICML 2027 has not published official submission dates as of 2026-08-31. Recent ICML
full-paper deadlines fell in late January. The dates below are internal planning
targets, not official deadlines:

| Internal target | Date | Status |
|---|---|---|
| Controlled-H preregistration frozen | 2026-09-15 | Completed 2026-08-31 |
| Fixture generator and 200 model-blind fixtures | 2026-10-15 | Completed 2026-09-04 under the disclosed combined protocol |
| Exact-oracle, treatment-strength, and baseline gate | 2026-10-31 | Completed 2026-09-04; combined fixture gate GO |
| Cheap-model pilot and power analysis | 2026-11-15 | Revision-pinned CSIS launcher prepared 2026-09-04; weight prefetch, one-query smoke, and real Qwen3-32B pilot pending user execution |
| Authorized multi-family controlled-H matrix complete | 2026-12-15 | Pending pilot and authorization |
| Statistics, conformance, agency ablation, and traces frozen | 2027-01-05 | Pending |
| Complete ICML-format manuscript | 2027-01-10 | Pending |
| Internal paper and artifact freeze | **2027-01-15** | Pending |
| Provisional abstract planning date | 2027-01-22 | Not an official deadline |
| Provisional full-paper planning date | 2027-01-28 | Not an official deadline |

Official dates replace the provisional dates immediately when ICML publishes its
2027 call.

### ICML thesis

Measure decision horizon causally: vary only required lookahead H while holding the
state, legal actions, objective, response contract, simulator, and scoring rule fixed.
The primary estimand is the within-fixture change in first-action quality from H=1 to
H=8, with the full H in {1,2,4,8} slope reported.

### Main-track gates

- at least 20% of model-blind fixtures change optimal action between H=1 and H=8;
- exact oracle remains exact and budget-audited for every included fixture/H;
- H-mismatched greedy loses on the horizon-sensitive subset;
- adequate power is demonstrated before the registered matrix;
- the H effect is not explained by parsing, legality, prompt length, or action-set
  changes;
- any scaling claim replicates across at least two model families;
- simulator conformance and full-versus-scripted agency results are reported;
- future model artifacts use schema 2.0+ and include complete traces.

Paid APIs, cluster runs, conference submission, registration, and travel remain
separate user-authorized actions. Planning this work does not authorize those actions.

## Dual-submission boundary

The workshop route is compatible with the ICML plan only while the selected workshop
is non-archival and has no formal proceedings. Recheck the final ICML 2027 policy and
the workshop terms immediately before either submission. If either venue treats the
work as archival or prohibits the overlap, stop and resolve the conflict before
submitting.
