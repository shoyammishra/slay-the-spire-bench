# Experiment Log

## 2026-09-04 — Silent extension complete; combined 200-fixture release passes

**No model, API, GPU, or cluster inference ran.** The frozen 50-row Silent-control
extension completed with 22 exact H=1/H=8-insensitive controls, four exact sensitive
rows, and 24 registered H=8 budget failures. Its final artifact has clean provenance
at commit `fdac980`, protocol digest `43d9c7b3…7995`, and SHA-256
`2a73203b…40961`. Together with the 70 base Silent controls, the extension supplied
ample feasibility margin (92 available versus 75 required).

The combined release was frozen separately in
`configs/controlled_h_v2_combined_release.json`, protocol
`controlled-h-v2-plus-silent-extension-release-2026-09-04`, digest
`71461857…db99b`. It binds both full-audit source hashes, preserves
`original_v2_release_gate_passed=false`, and permits extension rows to supply Silent
controls only. Deterministic original-namespace ranking selected 185 base rows and 15
extension controls. The release passed with 200/200 unique fixtures: exactly 25
sensitive + 75 controls for Ironclad and 25 sensitive + 75 controls for Silent;
`sensitive_fraction=0.25` and `shortfalls=[]`.

An independent audit of every selected row confirmed: no oracle errors; exactness at
H={1,2,4,8}; structured/raw prompt invariance; nonzero H=8 value span; positive H=1-
mismatch regret for all 50 sensitive rows; exact character/stratum and source counts;
and unique fixture IDs matching the released fixture payload. After the implementation
checkpoint, the release was regenerated from clean commit `1c6f0e5`; both artifacts
record `git_dirty=false` and retain the identical 185-base/15-extension selection.
Ignored local artifacts are `results/controlled_h_v2_combined_release_audit.json`
(SHA-256 `6cd43d31…8c737`) and
`results/controlled_h_v2_combined_release_fixtures.json` (SHA-256
`2b086a97…2461d`). The fixture/oracle gate is now GO for designing and freezing the
cheap model pilot. Model inference itself remains stopped pending its protocol, power
analysis, exact-stack smoke, and explicit compute authorization.

## 2026-09-04 — Frozen controlled-H v2 full audit fails Silent-control quota; extension frozen

**No model, API, GPU, or cluster inference ran.** The local exact-oracle full stage
completed all 483/483 advanced fixtures under the frozen v2 digest `78a768…f110`.
Ironclad dispositions were 96 exact sensitive, 118 exact controls, and 53 registered
budget failures. Silent dispositions were 59 exact sensitive, 70 exact controls, and
87 budget failures. By advancement source, the 125 ranked screen-insensitive Silent
rows yielded 53 controls, 22 H=1/H=8-sensitive rows, and 50 timeouts; the 91 screen-
sensitive Silent rows yielded 17 controls, 37 sensitive rows, and 37 timeouts. Total
recorded exact-oracle wall time across completed horizons was 19,661.67 seconds.

The release command completed and correctly failed closed. Its sole shortfall is
Silent H=1/H=8-insensitive controls: 70 available versus 75 required. The candidate
selection contains 195 rows, but `release_gate_passed=false`, `released_fixture_count=0`,
and the release fixture artifact is empty. Ironclad passed both quotas; this does not
convert the registered balanced gate into an Ironclad-only pass. Ignored local
artifacts are `results/controlled_h_v2_frozen_full.json`,
`results/controlled_h_v2_frozen_release_audit.json`, and
`results/controlled_h_v2_frozen_release_fixtures.json`.

Before any extension oracle row was evaluated, a separate Silent-control repair was
frozen in `configs/controlled_h_v2_silent_control_extension.json`, protocol
`controlled-h-v2-silent-control-extension-2026-09-04`, digest `43d9c7b3…7995`.
It selects exactly the next 50 original-v2-ranked candidates from the 177 unused,
eligible H=1/H=4-insensitive Silent rows, excluding all base-advanced fixtures. It
uses the unchanged full-oracle budgets and may supplement only exact insensitive
Silent controls. The original v2 outcome remains failed regardless of extension
success. Model inference remains stopped.

Pre-launch verification passed all four direct test files (**189/189**: benchmark 64,
combat 62, run 36, stats 27), Python compilation, source-artifact hash validation,
`git diff --check`, and a targeted public-repository security scan. The extension was
then launched as a hidden, resumable local process. Its first atomic checkpoint
completed exactly at all four horizons with prompt invariance and no budget failure;
the row was H=1/H=8-sensitive and therefore supplied no repair control. The ignored
live artifact is `results/controlled_h_v2_silent_control_extension_full.json` (1/50 at
this checkpoint). The launch provenance records `git_dirty=true` because the frozen
extension implementation and documentation are not yet committed; no model, paid API,
GPU, or cluster work is involved.

## 2026-08-31 — Frozen controlled-H manifest and H={1,4} screen complete; full audit checkpointed

**No model, API, GPU, or cluster inference ran.** The frozen protocol
`controlled-h-v2-fixtures-2026-08-31` (digest `78a768…f110`) generated 800/800
deterministic candidates, 400 per character, with no generation failures or
replacement. The ignored manifest is
`results/controlled_h_v2_frozen_manifest.json`.

The exact H={1,4} screen completed all 800 rows under 250,000 unique nodes and 10
seconds per fixture/H. There were zero node/time failures and zero structured/raw
prompt-invariance failures. Maximum H=4 unique expansions were 5,234; total recorded
oracle wall time was 535.29 seconds. Twenty-nine rows had zero H=4 span and are not
advancement-eligible. Disjoint H=1/H=4 optima occurred in 142/400 Ironclad candidates
(35.5%) and 91/400 Silent candidates (22.75%). Under the frozen rule, all 233 screen-
sensitive rows and 125 SHA-256-ranked screen-insensitive controls per character advance,
for 483 full-audit rows. These rates are screen diagnostics, not H=8 treatment results.

The full H={1,2,4,8} stage was then smoke-resumed and intentionally interrupted after
three atomic checkpoints to expose its cost before leaving a multi-hour foreground
process running. Two rows (`ironclad-0000`, `ironclad-0002`) hit the registered 120
second H=8 ceiling and failed closed. `ironclad-0001` completed exactly: H=8 expanded
64,527 unique states in 66.12 seconds, with value span 93−48, and its H=1 and H=8
optimal sets were not disjoint. The interrupted fourth row produced no disposition and
will restart; the three completed rows will be skipped on resume. Current artifact:
`results/controlled_h_v2_frozen_full.json`, 3/483 rows, `complete=false`.

This checkpoint is neither a passed nor failed release gate. It establishes a material
feasibility risk—2/3 initial rows timed out—and a rough worst-case duration near 16
hours if every remaining row consumes its full ceiling. Do not alter the frozen
protocol in response. Resume the same stage, preserve every timeout, and run release
selection only after all 483 dispositions exist. Model inference remains stopped.

Post-change verification passed all four direct test files (**188/188**: benchmark 63,
combat 62, run 36, stats 27). The no-API mock pipeline passed for both characters in
structured and raw formats. Python compilation and `git diff --check` passed; the final
changed-file credential, private-key, private-IP, and user-path scan was clean.

## 2026-08-31 — Controlled-H v2 exploratory screen finds treatment strength; inference remains stopped

**No model, API, GPU, or cluster inference ran.** This was local CPU oracle work to
test whether the full-observability v2 state family can produce a usable intervention.
The exploratory generator used a deterministic harder-encounter schedule, varied
ten-card decks, HP strata, turns, and model-blind prefixes. The selection procedure was
developed while inspecting oracle results, so these rows are instrument-development
evidence, not a preregistered sample or an estimate of population treatment strength.

A cheap H={1,4} screen evaluated 20 deterministic fixtures (10 per character) from
base seed 62000. All 20 completed exactly in 13.39 s total under a 10 s per-fixture/H
ceiling. Five had disjoint H=1/H=4 optimal-action sets: Ironclad fixtures 001, 006,
and 008, and Silent fixtures 002 and 007. Their H=1-mismatched qualities at H=4 were
0.842, 0.727, 0.250, 0.006, and 0.824 respectively. The ignored local audit is
`results/controlled_h_v2_discovery_stratified_20_audit.json`.

H=8 advancement produced the following exact, model-blind diagnostics:

- Ironclad 001 (Lagavulin): disjoint H=1/H=8 optima; H=1 mismatch quality 0.688,
  regret 5; 58,709 unique states in 63.99 s.
- Ironclad 006: disjoint optima; quality 0.900, regret 1; 79,104 unique states in
  77.74 s.
- Ironclad 008 (Hexaghost): disjoint optima; quality 0.742, regret 8; 51,702 unique
  states in 60.49 s.
- Silent full-HP 005 (Gremlin Nob), found in a separate full-HP screen: disjoint
  optima; quality 0.800, regret 6; 86,483 unique states in 92.67 s.
- Silent 002 (low-HP Slime Boss): exact in 0.07 s but effectively doomed; its broad
  H=8 optimal set included the H=1 action, so sensitivity was false.
- Silent 007 (Slime Boss): H=1/2/4 were exact, but H=8 hit the declared 120 s ceiling
  and raised `OracleTimeBudgetExceeded`; it is a feasibility failure, not a negative
  horizon label.

The exact sensitive rows demonstrate that v2 can manipulate decision horizon and make
the H=1-mismatched control lose. They do **not** authorize a model pilot: the discovery
and advancement rule is not frozen, the sample is adaptively selected and tiny, and
Silent feasibility has both a near-ceiling success and a timeout. Resume by freezing a
model-blind candidate-generation/filter rule, character-balanced strata, feasibility
policy, and exclusion accounting before generating the 200-fixture release. Preserve
all screened rows, including insensitive states and timeouts. Local detailed artifacts
are under `results/controlled_h_v2_*` and remain ignored by git as intended.

Post-change verification passed all four direct test files (**186/186**: benchmark
61, combat 62, run 36, stats 27), including exact-cache equivalence, time-budget,
atomic-checkpoint, and hidden-continuation collision regressions. The no-API mock
pipeline also completed for both characters in structured and raw formats. Python
compilation, `git diff --check`, and the changed-file credential/private-key scan were
clean; only expected Windows LF-to-CRLF working-copy warnings were emitted.

## 2026-08-31 — Varied-state controlled-H v1 pilot STOP; hidden-state collision; v2 fix

**No model, API, GPU, or cluster inference ran.** The resumed compute-free pilot added
per-fixture atomic schema-2.0 checkpoints and a 120 s per-fixture/H wall-time ceiling in
addition to the 2,000,000 unique-node ceiling. Both requested varied ten-card fixture
rows were preserved in `results/controlled_h_rich_pilot_2_audit_v2.json` (the filename
predates the protocol-version decision; its embedded instrument version is v1).

The gate remained a **STOP**:

- Ironclad H=1/2/4 completed exactly, but H=8 raised
  `OracleTimeBudgetExceeded` at 120 s. Its H=1 action already lost at H=2 (quality
  0.0) and was slightly suboptimal at H=4 (quality 0.9), but no H=8 result exists.
- Silent H=8 completed exactly in 118.07 s with 107,054 unique states, 118,339
  search calls, and 11,285 cache hits. H=4 preferred end turn and made the H=1
  action quality 0.0, but at H=8 that H=1 action returned to the broad optimal set
  (quality 1.0). The registered H=1/H=8 sensitivity flag was false.
- Only 1/2 fixtures was exact at every H; 0/1 exact fixtures had disjoint H=1/H=8
  optimal sets. `go_for_model_pilot=false`.

The traces then exposed an observation-contract bug. On a deterministic 15-card
Ironclad/Cultist state, swapping hidden draw-pile positions 0 and 6 left the structured
and raw v1 prompts byte-identical. Under the first ordering, H=2 preferred end turn at
value 21; under the second, it preferred Bash at value 17, with the end-turn value
falling from 21 to 7. The oracle therefore had decision-relevant information the model
did not receive.

`controlled-decision-horizon-v2` supersedes v1 before inference. V2 exposes ordered
piles, combat/enemy runtime state, player runtime flags, RNG streams, and RNG algorithm
in the same full-observability appendix at every H. A regression test reproduces the
v1 collision and verifies that both v2 prompt formats distinguish the states. Focused
benchmark tests pass 61/61. V2 still has **no model evidence** and needs a revised
model-blind fixture/treatment-strength pilot.

## 2026-08-31 — Controlled-H fixture/oracle pilot: exact but no treatment strength

**No model, API, GPU, or cluster inference ran.** This was a compute-free main-track
instrument-development pass. `scripts/controlled_horizon_pilot.py` now creates
deterministic model-blind fixture recipes, regenerates each state through the engine,
checks a SHA-256 digest over visible and hidden combat state, evaluates
H={1,2,4,8}, and records the registered degenerate and H-mismatched baselines.
`slay_bench/controlled_horizon.py` now supports those tamper-evident recipes.

The first completed audit used one opening Cultist state per character with starter
decks. Both fixtures remained exact under the 2,000,000-node ceiling. Before
memoization, H=8 expanded 172,555 nodes in 87.40 s for Ironclad and 454,235 nodes in
256.80 s for Silent; all four H values across both fixtures took 345.29 s. The local
schema-2.0 artifacts are `results/controlled_h_pilot_2_fixtures.json` and
`results/controlled_h_pilot_2_audit.json` (ignored by git, as intended).

The scientific gate was a **STOP**:

- 0/2 fixtures had disjoint H=1 and H=8 optimal first-action sets;
- the conservative H=1-mismatched oracle retained quality 1.0 at H=8 in both states;
- treatment strength was 0%, below the preregistered 20% minimum;
- prompt normalization confirmed that only H changed, and both exact-oracle controls
  remained at quality 1.0.

This is evidence that repeated-card starter openings are a poor controlled-H fixture
family, not evidence that models are horizon-insensitive. No model pilot is authorized
from this result.

A semantics-preserving transposition cache was then added to the exact oracle. On the
same two H=8 states it reproduced best values 41 (Ironclad) and 33 (Silent), reducing
Ironclad from 172,555 raw expansions / 87.40 s to 14,360 unique expansions, 7,394
cache hits, and 18.98 s; Silent fell from 454,235 / 256.80 s to 59,342 unique
expansions, 31,287 cache hits, and 86.05 s. A focused H=4 regression compares the
memoized and full trees exactly. This improves sizing but does not cure missing
treatment strength.

An exploratory generator for varied ten-card decks, HP strata, turns 1–3, and
single/multi-enemy encounters was implemented next. Its first two-fixture audit was
stopped at the user's request before the first row completed; it produced no result
and must not be treated as a failed or passed gate. The script currently writes its
combined audit only at completion, so per-fixture checkpointing is required before
resuming a longer pass. The exploratory generator is not the frozen preregistration
or the final 200-fixture release.

Verification after stopping: all four direct test files passed (**183/183**: benchmark
58, combat 62, run 36, stats 27). Four no-API mock commands initially failed before
sampling because nested `--out-dir` parents did not exist and the CLI uses non-recursive
`mkdir`; after creating the common parent, the exact commands passed for Ironclad and
Silent in structured and raw formats. Outputs are isolated under
`results/controlled_h_verification/`. This did not exercise the interrupted rich-state
H=8 pass; that remains explicitly pending.

## 2026-08-30 — Compute-free adversarial instrument audit and controlled-H smoke

**No API, GPU, or cluster compute was used.** `scripts/instrument_diagnostics.py`
evaluated a deterministic name-dictionary policy over all 20 fixed fixtures per
character and all three rotated expert positions. It achieved archetype accuracy 1.0,
unique on-label-offer rate 1.0, and card-pick accuracy 1.0 for Ironclad (60/60) and
Silent (60/60). This proves that the current fixture labels do not require planning; it
does not prove evaluated LLMs used the shortcut.

The same script inventoried 181 model JSON artifacts: 0 carry the new provenance or
instrument-version fields; 46 persist turn samples, 46 combat samples, 147 synergy
samples, and 0 run samples. These are historical schema limitations.

The current-code turn fixture replay covered 100 states per character on the paper
seed schedule. All 200 searches completed exactly: Ironclad max/mean nodes 17/13.23,
Silent 137/64.48, against a 20,000-node budget. Historical artifacts lack commits, so
this validates the current generator rather than retroactively proving old binaries.

`controlled-decision-horizon-v1` passed a no-inference smoke on a seeded Cultist state:
the H=1 search enumerated every legal first action exactly under the test budget, did
not mutate the fixture, and prompt-byte comparison confirmed that H was the only user
prompt change between H=1 and H=2. Model results are **PENDING EXPERIMENT**.

Oracle sizing on that same state expanded 6 / 37 / 618 / 168,487 nodes at
H=1/2/4/8. H=8 completed below the declared 2,000,000-node budget with best value
1040 and three tied optimal first actions. This is a smoke result, not a representative
runtime claim; fixture-wide sizing and model-blind filtering remain required.


## 2026-08-30 — ✅ Qwen3-235B full matrix recovered, audited, reaggregated, and folded in

**Status: complete at the registered tier.** Recovery jobs `329871`, `329872`, and
`329873` completed the missing Silent/raw work; one timed-out request was retried
successfully. The laptop now has 20/20 per-seed artifacts: four character×format cells ×
five spaced base seeds (`42 1042 2042 3042 4042`). Every artifact contains 20 turn, 20
combat, 20 synergy, and 5 run samples, for matrix totals of **400 / 400 / 400 / 100**.
Per-dimension sample-seed streams are exact and non-overlapping across base seeds.

The Silent/raw canonical aggregate initially had a null run block even though all five
per-seed run blocks were complete. It was regenerated through the authoritative
`run_benchmark._aggregate_summaries` path. Its corrected run result is survival `.00`,
floors `10.68 ± 1.0640`, and progress `.6675 ± .0665`.

### Canonical Qwen3-235B results

| Character / format | Turn damage ratio | Combat win / HP ratio | Archetype / pick | Removal-v1 diagnostic | Run floors / progress / survival |
|---|---:|---:|---:|---:|---:|
| Ironclad structured | .9644 | 1.00 / 1.0832 | .70 / .79 | .18 | 12.60 / .7875 / .04 |
| Ironclad raw | .9765 | .99 / 1.0317 | .68 / .67 | .12 | 12.00 / .7500 / .00 |
| Silent structured | .9786 | 1.00 / 1.0444 | .80 / .65 | .48 | 11.44 / .7150 / .00 |
| Silent raw | .9586 | .99 / .9893 | .79 / .64 | .27 | 10.68 / .6675 / .00 |

Removal-v1 is shown only to identify the preserved artifact field. A constant `Strike`
answer scores every fixed fixture, so it is quarantined from scientific analysis (see the
2026-08-30 decision entry).

### Qwen3-235B versus seed-matched Qwen3-32B

- Card-pick deltas are **+.2558 / +.1100 / +.2800 / +.2100** in the table order and
  improve in **19/20** seed pairs.
- Archetype deltas are **+.0937 / +.1700 / +.0100 / +.0800**; 15 pairs improve, 3 tie,
  and 2 worsen.
- Turn deltas are +.0044 / +.0429 / −.0214 / −.0314, with 91–97 of 100 samples per
  cell already at the exact oracle. Combat HP deltas are +.0080 / −.0196 / −.0142 /
  −.0053. These horizons are mixed and substantially ceiling-limited.
- Run-floor deltas are −.64 / −.20 / −.12 / +.56. At the exact `N_RUN=5` matched greedy
  anchors, Qwen3-235B floors are 12.60 vs 12.76, 12.00 vs 12.76, 11.44 vs 11.32, and
  10.68 vs 11.32. These are descriptive floor estimates, not wins or losses.

### Parse, truncation, and provenance audit

| Cell | Turn parse failures | Combat errors: total / JSON / illegal | Combat samples affected |
|---|---:|---:|---:|
| Ironclad structured | 0 | 19 / 17 / 2 | 15 |
| Ironclad raw | 1 | 61 / 47 / 14 | 40 |
| Silent structured | 1 | 13 / 12 / 1 | 11 |
| Silent raw | 0 | 50 / 32 / 18 | 35 |

Structured combat won 200/200 samples; raw combat won 198/200. Recovery server logs
contain 568, 1,861, and 1,042 HTTP 200 responses with no server errors. The original
Slurm stdout for jobs `267035`–`267037` is absent, while `267038` stdout records 150
run parse errors across 25 Silent/raw runs. Current run JSON does not persist per-run
error counters, so the other three cells' run error burden is unrecoverable and is not
silently estimated.

### Statistical fold-in

`scripts/stats_rigor.py` now discovers seven configurations and 28 complete cells. All
70 structured/raw fixture pairings match. With removal-v1 excluded, pooled structured
effects are magnitude-only for archetype (`+0.0350`, p=.0137; 9/14 directions) and
card pick (`+0.0717`, p=.0005; 10/14); neither direction sign test is significant.
Between-model variance shares on the representative metrics are turn damage `.865`,
combat win `.896`, synergy archetype `.629`, and run floors `.021` (the run row remains
restricted to the three balanced `N_RUN=20` models).
The complete fold-in supports selective card-choice improvement, not a uniform horizon
extension.

## 2026-08-22 — ⏱ Qwen3-235B Silent/raw job 267038 wall-killed; partial results retrieved and recovery split registered

**Status: incomplete but recoverable.** Job `267038` ran for the partition maximum and
was cancelled at the time limit. The laptop now has its Slurm stdout, vLLM log, and four
per-seed JSONs. Direct JSON inspection confirms:

- seeds `42`, `1042`, `2042`, `3042`: turn and combat present; synergy and run absent;
- seed `4042`: no JSON; stdout ends during combat sample 11/20 after completing all 20
  turn samples and the first 10 combat samples;
- no Silent/raw aggregate exists, and neither synergy nor run-level started.

The recovery instrument is `cluster/sharanga_matrix_combo.sbatch` with new
default-preserving phase/seed selectors. Registered chain: A reruns turn+combat only for
`4042` and synergy for all five seeds; B runs `N_RUN=5` for `42 1042 2042`; C runs it
for `3042 4042`. Each requests 2× H200 for `23:59:00`, and B/C use `afterok`
dependencies. No recovery job has been submitted as part of this repository change;
cluster compute remains user-authorized.

## 2026-08-21 — ⚠️ Qwen3-235B three-cell retrieval audited; paper signal is selective, matrix still incomplete

**Status: preliminary and not citation-ready.** The laptop now holds the five per-seed JSON
files plus aggregate for Ironclad structured, Ironclad raw, and Silent structured. Silent/raw
is still absent. Four server logs were retrieved as `vllm_combo_267035.log` through
`vllm_combo_267038.log`; the corresponding Slurm `slay_combo_*.out` files were not retrieved.

### Provenance and completion audit

- Jobs 267035–267037 contain 4,101 / 3,874 / 5,438 successful HTTP 200 completions,
  respectively, no HTTP or engine errors, and a normal shutdown sequence. Their result cells
  each contain seeds 42/1042/2042/3042/4042 with n=20 turn, combat, and synergy samples plus
  `N_RUN=5` per seed.
- Job 267038's retrieved log is only a startup/live snapshot: two successful requests and no
  shutdown. It proves that the validated TP=2 server started, not that the job or any benchmark
  phase completed. No Silent/raw JSON is present.
- The full matrix therefore remains 3/4 complete. Do not rerun the four-cell launcher and do
  not fold these scores into the paper tables before the recovery procedure in the 2026-08-21
  decision entry is complete.

### Preliminary three-cell scores and Qwen3-32B deltas

| Character / format | Turn | Combat win / HP ratio | Synergy archetype / pick / removal | Run floors / progress |
|---|---:|---:|---:|---:|
| Ironclad structured | .964 | 1.00 / 1.083 | .70 / .79 / .18 | 12.60 / .788 |
| Ironclad raw | .977 | .99 / 1.032 | .68 / .67 / .12 | 12.00 / .750 |
| Silent structured | .979 | 1.00 / 1.044 | .80 / .65 / .48 | 11.44 / .715 |

Against seed-matched Qwen3-32B, card-pick accuracy changes by **+.256 / +.110 / +.280**
in the three rows above and improves in **14 of 15 seed pairs**. Archetype changes by
+.094 / +.170 / +.010. Removal moves in the opposite direction in every landed cell:
**−.154 / −.070 / −.050**. Turn changes are only +.004 / +.043 / −.021, with 91–97 of
100 samples per cell already at damage ratio 1.0; the short-horizon instrument is saturated
for this comparison. Combat win is also saturated at .99–1.00.

Run-level remains at the registered floor-estimate tier. Against the exact `N_RUN=5`
run-seed-matched greedy anchors, floors are 12.60 vs 12.76 (Ironclad structured), 12.00 vs
12.76 (Ironclad raw), and 11.44 vs 11.32 (Silent structured). These are descriptive, small-n
floor comparisons, not evidence that 235B beats or loses to greedy.

### Instrument audit and interpretation boundary

- Turn and combat sample records are non-duplicated across all 100 samples in each landed
  cell. Synergy offer positions remain balanced (expert positions 34/33/33; model selections
  range 29–40 per position), clearing the constant-position degenerate strategy.
- The smoke's zero-truncation read-off does **not** generalize literally to the full matrix.
  Combat records contain 17 / 47 / 12 truncation events and 2 / 14 / 1 valid-JSON illegal
  actions in Ironclad structured / Ironclad raw / Silent structured; turn adds two truncations
  total. All server requests still returned HTTP 200. The raw Ironclad cell is less
  output-stable, so parse/truncation caveats must travel with its scores.
- HP ratios above 1 are model HP divided by the greedy reference HP and can reflect better play;
  the per-sample distribution is varied rather than the old identical-play Burning Blood
  asymmetry. They remain subject to the final full-matrix boundary audit.

**Paper implication to test after cell 4:** within the Qwen3 family, greater total capacity
appears to improve particular deck-building operations—most clearly choosing additions—without
uniformly improving card removal or unscaffolded run survival. This is a selective-capability
claim, not “larger models plan farther.” Architecture is a confound: 235B is an FP8 MoE with
22B active parameters while 32B is dense.

## 2026-08-21 — ▶ Qwen3-235B matrix recovery ACTIVE; 3/4 cells landed, Silent/raw running as job 267038

**Status: in progress; not yet audited or reportable.** Remote artifact inventory shows
complete five-seed aggregates for Ironclad structured, Ironclad raw, and Silent
structured. Silent/raw has no files yet. Its queued job `267038`
(`slay235_si_raw`, stdout `slay_combo_267038.out`) was blocked as
`PENDING (PartitionTimeLimit)`: requested `4-00:00:00`, while `gpu_h200_8` now reports
`MaxTime=1-00:00:00`.

The user updated job `267038` in place to `23:59:00`; it is now running with the original
validated TP=2 235B environment. This preserves the three landed cells and avoids
resubmitting the four-cell launcher. Because the registered per-cell estimate is 39–53
hours, this pass may be partial. The combo script saves each completed dimension and
each completed seed, so after the job exits the next action is to inspect
`slay_combo_267038.out` plus `results/qwen3-235b-a22b-fp8_silent_raw*`, then submit only
the unfinished Silent/raw phases/seeds in jobs below the current 24-hour cap.

**Remote artifacts observed (not yet copied or audited):** five per-seed files and one
aggregate each for the other three character×format cells. No scores are folded into
findings from this inventory alone. Completion still requires: finish Silent/raw; pull
all result and Slurm/vLLM logs to the laptop; verify completion and parse/truncation
counters per sample; rerun `scripts/stats_rigor.py`; then update findings, tables, and
handoff with the `N_RUN=5` floor-estimate caveat.

## 2026-08-09 — ✅ Qwen3-235B-A22B-FP8 SMOKE PASSED (job 266749) — all three read-offs answered; matrix sized and FEASIBLE

**Status: the rung is GO.** First complete measurement of this model. Batch job, the config
validated 2026-08-08, no manual flags — `bash cluster/sharanga_submit_235b.sh smoke`.

| Slurm | Value |
|---|---|
| Job | 266749, `COMPLETED` |
| Elapsed (whole job) | 01:27:04 |
| Benchmark pass alone | `real 75m35.447s` (`elapsed_seconds: 4523.23`) |
| MaxRSS | 240032800 K ≈ **228.9 GiB** of `--mem=290G` |

The ~11 min between job elapsed and pass wall is serve startup + inductor compile. `MaxRSS`
confirms the 250G→290G bump was necessary, not defensive: the old limit would have left
under 25 GiB of host headroom.

### Read-off 1 — WALL TIME ⇒ ≈39–53 h/combo, under the 96 h cap

The launcher's registered method: scale the 32B's *measured* per-combo time by the ratio of
the two models' **identical-config** smoke passes.

| Model | Smoke wall | Ratio vs 32B | Measured per-combo |
|---|---|---|---|
| qwen2.5-7b | 57 s | 0.018× | — |
| qwen3-32b | 53 min | 1.00× | **27.6–37.1 h** |
| **qwen3-235b-a22b-fp8** | **75 m 35 s** | **1.43×** | **≈39–53 h (predicted)** |

⇒ each combo carries ~2× headroom against the 96 h `MaxTime`, and four sequential combos
come to **≈6.6–8.8 days** wall clock. **The registered scope-down ladder (`N_RUN=0` first)
is NOT triggered.** Note the method's one prior validation: the same extrapolation predicted
the 32B's 20–50 h band, which landed at 27.6–37.1 h.

The 1.43× also settles the MoE sizing question — 235B total but 22B active decodes at ~⅔ the
speed of a 32B dense model, not at 235B-dense speed.

### Read-off 2 — TRUNCATION: ZERO. The thinking-mode risk did not materialise

This was the real gate. Qwen3-235B-A22B is a hybrid-reasoning model with thinking **on by
default** — structurally the DeepSeek-distill budget-bound-deliberation failure mode, at 235B
scale. Every counter is clean at the matched-8k default:

| Dimension | Counters |
|---|---|
| turn | `parse_ok_rate 1.0`, `parse_fail_n 0`, `parse_fail_truncated 0` |
| combat | `avg_truncation_errors 0.0`, `avg_json_parse_errors 0.0`, `avg_illegal_action_errors 0.0` |
| synergy | `parse_ok_rate 1.0` |

⇒ the registered M3b token-budget protocol (decision_log 2026-07-13) is **satisfied on the
matched-8k default**: no raised-budget condition, no dual reporting, nothing to keep unblended.
The qwen3 family is parse-clean at 7B, 32B and 235B; over-deliberation is an **R1-distill**
property, not a reasoning-model property — this is the third family-level datum for that
correction.

### Read-off 3 — SCORES: sane, and not findings

| Dim | n | Numbers |
|---|---|---|
| turn | 2 | `avg_damage_ratio 1.0`, `legal_rate 1.0` — `llm_sequence == optimal_sequence` exactly on both |
| combat | 1 | `win_rate 1.0`, `avg_hp_ratio 1.327` |
| synergy | 4 | `archetype_acc 0.75`, `card_pick_acc 0.75`, `removal_acc 0.25` |
| run | 1 | `avg_floors_reached 16.0`, `avg_progress 1.0`, `survival_rate 0.0` (reached the boss, died fighting it) |

Non-degenerate, nothing all-zero, JSON parsed throughout. **At n=1–4 these are instrument
checks and must never be quoted as results.** The turn 1.0 is the documented saturation
ceiling reappearing, not new information (`scripts/turn_saturation_check.py`, 2026-08-07).

**Next:** `bash cluster/sharanga_submit_235b.sh matrix` at the default `N_RUN=5`.

## 2026-08-08 — ⚙️ Qwen3-235B-A22B-FP8 SERVES at TP=2 (FlashInfer solved); smoke pass NOT yet measured

**Status: serving problem SOLVED and validated; no benchmark numbers yet.** Full rationale +
the working config: decision_log 2026-08-08 (top).

**Batch attempt (job 264929, gpu_h200_8, 2× H200):** FAILED at 13:19 elapsed, exit 1.
Not memory — the model loaded, then died in `profile_run` building a FlashInfer JIT kernel.
`MaxRSS 226 GiB` of `--mem=250G` (90%, close enough that later runs use **290G**).

**Interactive debugging (job 265639, 2 h `srun` on the shared H200 node):** four serve attempts,
~8 min each. Every failure was FlashInfer's JIT, never the model:

| Attempt | Config | Outcome |
|---|---|---|
| A | `--disable-custom-all-reduce` | died — the fused-allreduce pass is a separate path |
| B | + `LIBRARY_PATH=/usr/lib64` (fixes `ld: cannot find -lcuda`) | died — `flashinfer_trtllm_fused_allreduce_norm` baked into the inductor graph |
| C | + `--compilation-config '{"pass_config":{"fuse_allreduce_rms":false}}'` | died — `fp8_blockscale_gemm_90` via `linear_backend=auto` → DeepGEMM |
| **D** | **+ 5 FlashInfer/DeepGEMM env vars + compile-cache wipe** | ✅ **UP after 160 s**, turn samples scoring, no new kernel |

**Validated serving numbers (the ones that change sizing):**

| Metric | Value | Supersedes |
|---|---|---|
| Weight load | **44.55 s** | the ~2 h extrapolation from the 32B's 65 GB / 35 min |
| Server ready | **160 s** total | — |
| Weights on GPU | **110.19 GiB per worker** (~220 GiB total) | matches the 239.1 GB manifest |
| Free per GPU @ util 0.95 | **~24 GiB** | memory arithmetic CONFIRMED; `--max-model-len 16384` retained |

⇒ **Cold start contributes essentially nothing to per-combo cost**, and the contingency to cut
context to 12288 is not needed.

**⛔ No wall-time measurement: the 2 h interactive session expired unattended mid-pass, so
`results/qwen3-235b-a22b-fp8_*_sharanga_smoke.json` was never written.** The harness writes on
completion, and nothing survived. Early observations only, from terminal output — turn-level
`dmg_ratio=1.00, parse_ok=True, legal=True` on both samples (n=2, worthless statistically, and
consistent with the documented turn-level saturation ceiling). **The three smoke read-offs —
wall time, truncation counters, score sanity — all remain OPEN.**

**Durable lesson (decision_log §4): measurement passes belong in BATCH, not in a time-boxed
interactive session.** Interactive is for debugging serving; batch has per-dimension partial
saves. Also: never reuse a probe log filename (attempt A's log was overwritten, so its exact
failure is unconfirmed).

**Next:** `bash cluster/sharanga_submit_235b.sh smoke` — the working config is now baked into
`sharanga_smoke.sbatch` + `sharanga_matrix_combo.sbatch`, so this needs no manual flags and no
babysitting.

## 2026-08-07 (latest) — ▶ Qwen3-235B-A22B-FP8 rung STAGED + PREFETCHED (smoke pending)

**Status: weights on scratch and verified; nothing submitted yet.** Top of the registered
ladder — the largest model runnable under the default QOS. Decisions + rationale:
decision_log 2026-08-07 (latest).

**Prefetch (login node, `HF_HOME=/scratch/$USER/hf`):**

| Item | Value |
|---|---|
| Repo | `Qwen/Qwen3-235B-A22B-FP8` |
| Manifest size | **239.1 GB** across **58 files** (measured via `HfApi(files_metadata=True)`, not estimated) |
| Verified | **58/58 present, 0 missing, 0 size-mismatch, local total 239.1 GB** |
| Transfer rate | 90–114 MB/s (Xet reconstruction 205–442 MB/s); ~1 h wall |
| Scratch | no per-user block quota (`quota`/`limit` = 0); ~633 GB in use, 159 TB free |

**⚠️ `du -sh` read 212 GiB for this COMPLETE model** (expected 222.7 GiB) — a 5% gap that
looks exactly like truncation but is Xet chunk dedup + block accounting. Completeness is now
established only by `cluster/verify_prefetch.py` (per-file manifest check), which the launcher
runs as a hard guard.

**Planned serving config:** 1 job × **2× H200, TP=2**, `--cpus-per-task=8`, `--mem=250G`,
`--max-model-len 16384`, **`--gpu-memory-utilization 0.95`** (239.1 GB weights in a 282 GB
budget ⇒ ~29 GB headroom at 0.95 vs ~15 GB at 0.90; 16k GQA KV at batch ~1 is ~3 GB).

**⚠️ Governing constraint — the 32B playbook does NOT transfer.** TP=2 under the 3-GPU
per-user cap means two such jobs cannot co-run ⇒ the four combos are **strictly sequential**,
so matrix wall-clock ≈ 4 × per-combo against a **96 h MaxTime per job**. The smoke therefore
gates a *scope* decision, not just a go/no-go — hence the two-stage launcher
(`bash cluster/sharanga_submit_235b.sh {smoke|matrix}`).

**Smoke read-off order (registered, in the launcher header):** (1) wall time of the tiny pass
— anchors on identical config are qwen2.5-7b **57 s** and qwen3-32b **53 min**; scale the 32B's
measured 27.6–37.1 h/combo by the ratio. (2) truncation counters — this is a hybrid-reasoning
model with thinking on by default, i.e. the DeepSeek budget-bound-deliberation risk at 235B
scale; qwen3-32b was parse-clean at the same 8k budget, which is the encouraging precedent.
(3) score sanity. **If >96 h/combo:** drop run-level first (`N_RUN=0`, ~half the cost, and P4b
put its between-model variance share at 2%), then one character, then one format.

**Two staging bugs fixed before any GPU was claimed** (see decision_log §4): the smoke sbatch
had **no `--tensor-parallel-size`** (would have failed this rung at the gate), and its walltime
(3 h) was **≤ its own health budget** (180 min) — a cold start could have consumed the whole
allocation and been wall-killed with zero samples run on 2× H200. Now 6 h.

**Operational gotchas recorded** (decision_log §6): a multi-line paste into `tmux new` is
swallowed (use `send-keys`/`nohup`; read panes with `capture-pane` without attaching); a
returning prompt does not mean a download died — relaunching produced **two concurrent
processes writing the same HF cache**; kill by explicit PID, never `pkill -f` on the shared
account.

**Next:** `bash cluster/sharanga_submit_235b.sh smoke` → read the three items above → size and
scope stage 2.

## 2026-08-07 (later) — ✅ P4b STATISTICAL RIGOR PASS (zero GPU, zero API)

**What ran:** `scripts/stats_rigor.py` over the 24 on-disk combos (6 models × 2 characters ×
2 formats × 5 seeds) + the 2,400 persisted synergy per-sample records + the two greedy-baseline
files. **No benchmark re-run, no API call, no published mean changed** — this is additive
analysis. Human artifact: **`docs/stats_report.md`** (committed). Machine artifact:
`results/stats/stats_rigor.json` (gitignored). Methods + rationale: decision_log 2026-08-07
(later). Reproducible: fixed RNG seed 20260807, B=10,000 → identical numbers every run
(~77 s wall). Tests: **172/172** (146 + 26 new in `tests/test_stats.py`); mock pipeline green.

**Precondition verified, not assumed:** structured vs raw synergy streams are byte-identical on
`(expert_archetype, expert_pick_idx)` for **60/60** (model × character × seed) triples ⇒ the
formats saw the same fixtures in the same rotated positions, licensing sample-level paired
tests. The script re-checks this every run.

**⚠️ Power ceiling that travels with every per-combo p-value below:** the paired test is an
exact sign-flip permutation over 5 seed differences; 2⁵ = 32 sign assignments ⇒ **minimum
attainable two-sided p per combo = 0.0625**. No single combo can reach α=0.05 *by
construction*. Per-combo rows are descriptive; inference comes from the pooled stratified test
and sample-level McNemar.

### Format ablation, pooled across the matrix (the paired test that had never been run)

Stratified sign-flip permutation (magnitude) + exact sign test on per-stratum direction. A
claim is **general** only when both are significant; magnitude-only = model-dependent.

| Dim | Metric | mean diff (S−R) | p (magnitude) | S>R / R>S / tie | p (direction) | reading |
|---|---|---|---|---|---|---|
| turn | dmg_ratio | −0.0758 | **0.0005** | 5/7/0 | 0.774 | model-specific |
| turn | legal_rate | −0.0558 | 0.0125 | 6/6/0 | 1.000 | model-specific |
| combat | win_rate | +0.0542 | **0.0002** | 5/0/7 | 0.0625 | model-specific* |
| combat | hp_ratio | +0.0603 | **0.0001** | 10/2/0 | **0.0386** | **general** |
| combat | invalid_action_errors | −1.0308 | **0.0001** | 2/10/0 | **0.0386** | **general** (fewer with structured) |
| synergy | archetype | +0.0384 | 0.0187 | 7/5/0 | 0.774 | model-specific |
| synergy | card_pick | +0.0729 | 0.0012 | 8/4/0 | 0.388 | model-specific |
| synergy | removal | +0.0764 | **0.0007** | 10/2/0 | **0.0386** | **general** |
| run | floors | +0.3862 | 0.0641 | 5/3/0 | 0.727 | no evidence |
| run | progress | +0.0241 | 0.0629 | 5/3/0 | 0.727 | no evidence |
| run | survival | +0.0175 | 0.2012 | 3/3/2 | 1.000 | no evidence |

\* win_rate: all 5 non-tied strata favour structured, but 7 combos are exactly tied at the
ceiling, so the sign test only reaches its own floor of 0.0625.

### Synergy removal at the sample level (McNemar exact, fixture-matched, n=100 pairs/combo)

| Model | Char | pairs | dropped | structured | raw | risk diff | b/c | p | p (Holm) |
|---|---|---|---|---|---|---|---|---|---|
| qwen2.5-7b | ironclad | 100 | 0 | .240 | .020 | +0.220 | 22/0 | <0.0001 | **<0.0001** |
| qwen2.5-7b | silent | 100 | 0 | .360 | .180 | +0.180 | 25/7 | 0.0021 | **0.0168** |
| qwen3-32b | silent | 100 | 0 | .530 | .230 | +0.300 | 36/6 | <0.0001 | **<0.0001** |
| qwen3-32b | ironclad | 99 | 1 | .333 | .192 | +0.141 | 24/10 | 0.0243 | 0.1459 |
| mistral-7b | ironclad | 100 | 0 | .150 | .000 | +0.150 | 15/0 | 0.0001 | **0.0006** |
| mistral-7b | silent | 100 | 0 | .040 | .000 | +0.040 | 4/0 | 0.1250 | 0.5000 |
| llama-3.1-8b | ironclad | 100 | 0 | .150 | .070 | +0.080 | 8/0 | 0.0078 | 0.0547 |
| llama-3.1-8b | silent | 100 | 0 | .180 | .160 | +0.020 | 8/6 | 0.7905 | 1.0000 |
| deepseek-7b | ironclad | 62 | **38** | .452 | .371 | +0.081 | 13/8 | 0.3833 | 1.0000 |
| deepseek-7b | silent | 63 | **37** | .444 | .444 | 0.000 | 10/10 | 1.0000 | 1.0000 |
| deepseek-14b | ironclad | 93 | 7 | .183 | .323 | **−0.140** | 15/28 | 0.0660 | 0.3300 |
| deepseek-14b | silent | 99 | 1 | .151 | .404 | **−0.253** | 7/32 | 0.0001 | **0.0006** |

"dropped" = pairs where either format failed to parse (deepseek-7b's conditioning caveat,
now quantified: 37–38 of 100). **The "5 of 6 models" claim reproduces exactly**, and
deepseek-14b's reversal is *significant* — a real model property, not noise.

### Variance decomposition (η² shares, balanced model × character × format, seeds as replicates)

| Dim | Metric | models | model | character | format | interactions | residual (seed) |
|---|---|---|---|---|---|---|---|
| turn | dmg_ratio | 6 | **0.832** | 0.000 | 0.021 | 0.077 | 0.070 |
| combat | win_rate | 6 | **0.891** | 0.011 | 0.007 | 0.065 | 0.025 |
| combat | hp_ratio | 6 | **0.935** | 0.013 | 0.006 | 0.033 | 0.013 |
| synergy | archetype | 6 | **0.506** | 0.149 | 0.017 | 0.222 | 0.106 |
| synergy | removal | 6 | **0.609** | 0.016 | 0.052 | 0.237 | 0.086 |
| synergy | card_pick | 6 | 0.229 | 0.028 | 0.060 | 0.321 | **0.362** |
| run | floors / progress | 3 | **0.021** | **0.565** | 0.002 | 0.068 | **0.345** |
| run | survival | 3 | 0.048 | 0.114 | 0.005 | 0.176 | **0.657** |

**The headline number of this pass:** at the run horizon *which model you use* explains
**~2%** of the variance while *which character you play* explains **~57%** and seed noise
**~34%**. At the turn horizon the model explains **83%**. That is the horizon-collapse claim
stated as variance rather than as a curve. (Run rows use only the 3 models with complete n=20
run data — qwen2.5-7b, llama-3.1-8b, mistral-7b — never blended with qwen3-32b's n=5 rows.
floors and progress share identical shares because progress = floors/16, a linear transform:
a built-in sanity check that the decomposition is wired correctly.)

### Run level vs a RUN-SEED-MATCHED greedy anchor (new comparator)

Greedy is subset to the exact run seeds each model played (`range(base+300, base+300+n_run)`)
before pairing — strictly tighter than the 100-run global anchor.

| Combo | Metric | model | greedy (matched) | diff | 95% CI | p |
|---|---|---|---|---|---|---|
| qwen3-32b IC structured | survival | .120 (3/25) | **.040 (1/25)** | +0.080 | [−0.08, +0.24] | 0.750 |
| qwen3-32b IC structured | floors | 13.24 | **12.76** | +0.48 | [−0.56, +1.64] | 0.5625 |
| llama-3.1-8b IC raw | floors | 13.76 | 12.48 | **+1.28** | [+0.67, +1.77] | 0.0625† |
| llama-3.1-8b IC structured | floors | 13.37 | 12.48 | +0.89 | [+0.40, +1.39] | 0.0625† |
| deepseek-14b IC structured | floors | 9.75 | 12.48 | **−2.73** | [−3.50, −1.93] | 0.0625† |

† = the most extreme result the 5-pair design can produce (all seeds same sign).
**Exact binomial CI on qwen3-32b's survival: 3/25 → [0.026, 0.312].**

**⚠️ CORRECTION this table forces:** the published qwen3-32b run-level comparison (".12 survival
/ 13.24 floors vs measured greedy .01 / 12.48") used greedy's *100-run* anchor. On the **same
25 run seeds** greedy scores **.04 / 12.76**, so the honest gap is **3 vs 1 survivors
(+0.08, p=0.75)** and **+0.48 floors (p=0.5625)**. The registered phrasing ("signal, not a win;
needs n=20") stands — the *numbers* quoted with it must now be the matched ones.

### Claim verdicts (full detail + evidence in `docs/stats_report.md` §1)

| ID | Claim | Verdict |
|---|---|---|
| C1 | structured ≥ raw on synergy removal for 5 of 6 models | **SUPPORTED** |
| C2-removal | structured beats raw on synergy removal matrix-wide | **SUPPORTED** (general) |
| C2-archetype / C2-card_pick | same for archetype / card_pick | SUPPORTED-**MAGNITUDE-ONLY** |
| C3-combat-win_rate | combat win_rate is format-insensitive | PARTIAL (8/12 equivalent) |
| C3-combat-hp_ratio | combat hp_ratio is format-insensitive | **NOT-SUPPORTED-AS-STATED** (5/12) |
| C3-run-progress | run progress is format-insensitive | **NOT-SUPPORTED-AS-STATED** (3/8) |
| C7-hp_ratio | format reaches the COMBAT horizon | **SUPPORTED** |
| C8 | the turn-level format effect has no consistent direction | **SUPPORTED** |
| C4 | run level is a shared collapse floor | SUPPORTED-WITH-NUANCE |
| C5 | qwen3-32b first off the run floor | **UNDERPOWERED** (see correction above) |
| C6 | model variance large at reasoning horizons, small at survival | **SUPPORTED** |

**Ceiling diagnosis behind C3/C7:** for combat `win_rate`, *every* combo whose format effect
exceeds the ±0.05 margin sits **below** the combat ceiling (all four R1-distill combos; 0 of
the 8 win-saturated combos move materially). Models that win 100% of fights leave format
nothing to move ⇒ the old "combat is format-insensitive" reading was a **ceiling artifact**,
not a property of the horizon. `hp_ratio` is the finer instrument and moves even for two
win-saturated combos (mistral/Silent +0.112, qwen3-32b/Silent +0.064).

**Re-run trigger:** models are discovered from `results/` filenames, so M3b frontier rows join
every table with no code change — re-run `stats_rigor.py` as the first step of the M3b fold-in.

## 2026-08-07 (SHARANGA) — ✅ qwen3-32b FULL 4-DIMENSION MATRIX RETRIEVED + AUDITED

**Status: complete and clean.** Jobs **261120–261123** (ironclad/silent × structured/raw)
all logged `=== combo qwen3-32b <char> <fmt> COMPLETE (all four dimensions) ===`; no
`DIM FAILED`, no wall-clock kill, no partial saves. Retrieved 2026-08-07 to the laptop:
four aggregates `results/qwen3-32b*_seeds42_1042_2042_3042_4042.json` + 20 per-seed files
(per-sample records) + the four Slurm logs (`results/_sharanga_logs/`, gitignored).
The `--run-tag sharanga_smoke` gate file stayed out of the matrix as designed.

**Wall clock (validates the 2026-07-23 §6 sizing arithmetic):** combos ran 27.6 / 33.4 /
34.5 / 37.1 h of summed evaluator time — inside the predicted **20–50 h central band**.
Jobs started staggered Jul 25 07:06 → Jul 27 15:39 (gpu_h200_8 is one shared node,
gpunode7, so the 4th combo queued behind the 3-GPU per-user cap). vLLM cold start
305–475 s on warm nodes, as predicted by the shared `~/.cache` compile cache.

**Config:** vLLM 0.25.1 / torch 2.11.0+cu130 on 1× H200, `Qwen/Qwen3-32B` TP=1,
`--max-model-len 16384`, n=20 turn/combat/synergy, `--seeds 42 1042 2042 3042 4042`,
**run-level n=5 per seed (25 runs/combo)** per the 2026-07-24 decision.

### Results — qwen3-32b, all four dimensions, 5 seeds (mean ± std)

| Dim | Metric | IC structured | IC raw | Silent structured | Silent raw |
|---|---|---|---|---|---|
| Turn | dmg_ratio | 0.960±0.018 | 0.933±0.041 | **1.000±0.000** | 0.990±0.022 |
| Turn | legal_rate | 0.99±0.022 | 0.98±0.027 | 1.00±0.0 | 0.99±0.022 |
| Turn | parse_ok | 1.00±0.0 | 0.99±0.022 | 1.00±0.0 | 1.00±0.0 |
| Combat | win_rate | 1.00±0.0 | 1.00±0.0 | 1.00±0.0 | 0.99±0.022 |
| Combat | hp_ratio | 1.075±0.029 | 1.051±0.031 | 1.059±0.028 | 0.995±0.050 |
| Combat | parse_errors (conflated) | 0.09±0.042 | 1.13±0.115 | 0.13±0.027 | 0.87±0.261 |
| Combat | ├ json_parse_errors | 0.06±0.065 | 0.20±0.128 | 0.05±0.035 | 0.34±0.185 |
| Combat | ├ illegal_action_errors | 0.03±0.027 | 0.93±0.182 | 0.08±0.027 | 0.53±0.091 |
| Combat | └ truncation_errors | 0.06±0.065 | 0.20±0.128 | 0.05±0.035 | 0.34±0.185 |
| Synergy | archetype_acc | 0.606±0.095 | 0.510±0.065 | **0.790±0.103** | 0.710±0.065 |
| Synergy | card_pick_acc | 0.534±0.091 | 0.560±0.096 | 0.370±0.076 | 0.430±0.115 |
| Synergy | removal_acc | 0.334±0.048 | 0.190±0.082 | **0.530±0.135** | 0.230±0.027 |
| Synergy | parse_ok | 0.99±0.022 | 1.00±0.0 | 1.00±0.0 | 1.00±0.0 |
| Run (n=5) | survival_rate | **0.12±0.179** | 0.00±0.0 | 0.00±0.0 | 0.00±0.0 |
| Run (n=5) | avg_floors_reached | **13.24±2.14** | 12.20±2.09 | 11.56±0.95 | 10.12±2.16 |
| Run (n=5) | avg_progress | 0.828±0.134 | 0.763±0.131 | 0.723±0.060 | 0.633±0.135 |
| Run (n=5) | draft_coherence | 0.353±0.089 | 0.302±0.040 | 0.346±0.033 | 0.335±0.079 |

Measured greedy anchors for comparison (2026-07-12, same seeds): **Ironclad 12.48 floors /
0.780 progress / 1% survival; Silent 11.26 / 0.704 / 0%.**

### ⚠️ Per-sample instrument audit — the 1.000 was interrogated before it was believed

`turn.avg_damage_ratio = 1.000 ± 0.000` on Silent/structured is the textbook boundary +
zero-variance signature the project rule says to distrust. Two audits were run before any
number was folded in:

**(a) Per-sample decomposition** (from the persisted `turn.samples[]`, n=100 per combo):

| Combo | exact oracle sequence | tied at optimum, different sequence | sub-optimal |
|---|---|---|---|
| IC structured | 64 | 22 | 14 |
| IC raw | 61 | 20 | 19 |
| Silent structured | 48 | **52** | **0** |
| Silent raw | 49 | 50 | 1 (a single illegal play → 0.0) |

No trivial states: oracle sequences are 2–3 cards (Ironclad) and 3–4 cards (Silent), never
≤1. The 52 "different sequence" samples are permutation ties among *optimal* orderings.

**(b) Degenerate-strategy baseline** — new reproducible artifact
**`scripts/turn_saturation_check.py`** (zero API, deterministic). Rebuilds all 100 turn
states per character and enumerates the FULL space of maximal legal play sequences:

| | Ironclad | Silent |
|---|---|---|
| oracle optimal damage (mean / min / max) | 16.26 / 6 / 18 | 18.18 / 9 / 21 |
| fraction of all legal sequences that are optimal | 0.010 | 0.000 |
| states where EVERY legal sequence is optimal | **0 / 100** | **0 / 100** |
| random legal sequence | 0.231 | 0.145 |
| naive "play hand left-to-right" (zero planning) | 0.614 | 0.510 |
| **qwen3-32b (structured)** | **0.960** | **1.000** |

**Verdict: the 1.000 is REAL, not an instrument ceiling.** The optimal set is a vanishing
slice of the legal space (0.0–1.0%); a non-planning policy scores 0.15–0.61. qwen3-32b
found a damage-maximizing sequence on 100/100 Silent-structured states. Consistency check:
qwen2.5-7b scored 0.663 Silent-structured with legal_rate 0.87 — below its own legal rate,
so legal-but-suboptimal play exists and the dimension discriminates.

**Consequence for M3b (important):** turn-level is now **saturated at the top**. A frontier
model cannot separate above 1.000 on Silent-structured, so the left edge of the
horizon-collapse curve has no headroom left. Do not expect turn-level to rank frontier
models; the discriminating horizons are synergy and run.

### Findings from this run

1. **Best short-horizon scores in the matrix, by a wide margin.** Turn 0.933–1.000 vs the
   previous best (deepseek-r1-14b 0.823 IC / 0.839 Silent) and the 7–8B pack (0.18–0.81).
2. **Reasoning ≠ free win needs correction — the collapse is a property of the DISTILLS,
   not of reasoning models.** deepseek-r1-14b *lost* combats (Silent raw win 0.34,
   hp_ratio 0.21) and its IC run floors crashed to 9.75 (below greedy 12.48). qwen3-32b,
   a full reasoning model, holds win 0.99–1.00 with hp_ratio 0.995–1.075 (≥ greedy bot) and
   its run floors sit **at or above** the greedy anchor. See findings.md finding 2
   supersession marker.
3. **First non-zero run-level survival lift in the project's history** — IC structured
   0.12 survival vs the measured greedy 0.01, floors 13.24 vs 12.48. ⚠️ **Report as a
   signal, not a result:** n=25 runs (5/seed × 5 seeds), std 0.179 across seeds → 3
   survivors concentrated in one or two seeds. At n=5 this cannot be strengthened; it is a
   **floor estimate** and must never be blended with the n=20 run-level rows.
4. **The parse-probe verdict replicates in a second model family.**
   `avg_json_parse_errors == avg_truncation_errors` EXACTLY in all four combos
   (.06/.06, .20/.20, .05/.05, .34/.34) — every JSON failure is a truncation, zero
   malformed-but-complete outputs. Same identity the 2026-07-13 DeepSeek probe found, at
   ~25× smaller magnitude (0.05–0.34 vs ~8 parse_errors/combat). Confirms the counter split
   is measuring what it claims to across families.
5. **Format effect: structured wins archetype, removal, and run; raw wins card_pick.**
   Removal IC 0.334/0.190 and Silent 0.530/0.230; archetype IC 0.606/0.510 and Silent
   0.790/0.710 — qwen3-32b stays on the structured side, so the standing "**5 of 6 models**,
   deepseek-14b the sole reversal" claim is unchanged (qwen3-32b was already one of the 6;
   its cell now rests on this full-matrix data instead of the CSIS synergy-only data).
   card_pick reverses on both characters (IC 0.534/0.560, Silent 0.370/0.430).
   New: **structured also wins run-level floors on both characters** (13.24/12.20 IC,
   11.56/10.12 Silent) — the first time the format ablation reaches the survival horizon,
   where it had been documented as format-insensitive.
6. **Combat `illegal_action_errors` is a strong format signal**: raw 0.93 / 0.53 vs
   structured 0.03 / 0.08 — a ~10× difference in action legality, while the JSON-failure
   component barely moves. Cite the matrix combat metric as **"invalid-action errors"**
   (standing rule).

### ⚠️ SUPERSESSION — these cells replace the CSIS qwen3-32b synergy-only cells

Different serving stack (CSIS vLLM 0.8.x vs Sharanga vLLM 0.25.1) → **never blend**. Old
vs new synergy, for the record only:

| Combo | archetype (CSIS → Sharanga) | card_pick | removal |
|---|---|---|---|
| IC structured | .53 → .606 | .59 → .534 | .29 → .334 |
| IC raw | .50 → .510 | .58 → .560 | .22 → .190 |
| Silent structured | .80 → .790 | **.57 → .370** | .55 → .530 |
| Silent raw | .64 → .710 | .46 → .430 | .32 → .230 |

Cross-stack agreement is close on archetype and removal (≤0.07 except Silent-raw archetype
0.07). **Silent-structured card_pick moved 0.20** — the single large disagreement; flag it
if cross-stack stability is ever claimed. The superseded CSIS files are preserved locally
at `results/_csis_qwen3-32b_2026-06-22/` (gitignored).

### Coverage after this run
qwen3-32b is now **complete on all four dimensions for all four combos** — the last
intentional matrix gap for this model is closed. Remaining `—` cells in the matrix tables
are deepseek-14b Silent run and deepseek-7b run, both intentionally skipped (floor
dimension / execution collapse).

---

## 2026-07-24 (SHARANGA) — qwen3-32b FULL matrix LAUNCHED (parallel fire-and-forget, smoke-gated); results expected ~2026-07-30

**Why:** user on exams until 2026-07-30 → fill the qwen3-32b full 4-dim matrix unattended,
fast. Parallel path (decision_log 2026-07-23 §7): `cluster/sharanga_submit_qwen3_matrix.sh`
submits a qwen3-32b smoke gate + 4 combo jobs (ironclad/silent × structured/raw), each an
own-file `sharanga_matrix_combo.sbatch`, `--dependency=afterok` on the smoke → up to 3 run
concurrently under the gpu_h200_8 3-GPU QOS cap, no result-file race.

**Launch gotchas caught + fixed (durable cluster/env facts):**
1. **A100-partition misroute** (`2e6b9eb`) — first launch put the smoke gate on `gpu_a100_8`
   (the smoke file's default partition), which is **DOWN for admin driver stress-testing**, so
   the smoke sat `PD (Priority)` forever and the 4 combos hung `PD (Dependency)`. Launcher now
   pins the smoke `--partition=gpu_h200_8 --cpus-per-task=4` (also correct on principle — gate
   on the same GPU type the combos use).
2. **`set -u` × cuda-nvcc conda hook** (`706b287`) — the `cuda-nvcc` package's activate/
   deactivate hooks reference `CUDAARCHS_BACKUP` unbound; with `set -euo pipefail` placed
   BEFORE `source activate`, the `-u` made that fatal and **every BATCH job aborted at
   activation** (the `.out` held only the `CUDAARCHS_BACKUP: unbound variable` line). Invisible
   in the interactive smoke (login shells don't set `-u`). Fixed in all five Sharanga sbatch:
   `set -eo pipefail` → `source activate` → `set -u`. **Durable rule: never source conda
   activation under `set -u`** — conda's own hooks aren't `-u`-clean.
After both fixes the smoke cleared activation, ran `nvidia-smi` (H200), and began loading
qwen3-32b — matrix chain genuinely in flight.

**qwen3-32b SMOKE PASSED (H200, `--run-tag sharanga_smoke`, gate for the matrix chain):**
- **The key risk is CLEARED — qwen3-32b does NOT over-deliberate/truncate.** `parse_ok_rate`
  = 1.0 on turn AND synergy; combat `parse_errors`/`json_parse_errors`/`truncation_errors` all
  0; no empty `model_said`. Unlike the DeepSeek distills (budget-bound deliberation, parse_probe
  2026-07-13), qwen3-32b finishes its `<think>` and emits clean JSON at 16k ctx / 8k gen. So
  the matrix combos are safe to run.
- Scores sane: turn dmg **.91** (parse 1.0, legal 1.0), combat win 1.0 / hp .98 / 0 errors,
  synergy **2/4** archetype+pick+removal (n=4; > the 7B smoke's 1/4), run died at boss
  (survival 0, floors 16 = correct). Artifacts: `results/qwen3-32b_structured_seed42_sharanga_smoke.*`.
- **⚠️ SIZING SIGNAL (drives the run-level decision below): the tiny smoke pass took 53 min**
  (`elapsed_seconds` 3187, model already served) vs **57 s** for the same pass on the 7B —
  **~55× slower**. The single run-level run dominated (~30–40 min); a reasoning call spends
  ~30–60 s emitting thinking tokens. Extrapolated to the matrix (`run_all` runs the full n
  once PER seed → `--n-run 20 --seeds ×5` = **100 full runs/combo**): turn+combat+synergy
  ≈ 7–15 h/combo (cheap, run FIRST → land safely), but **run-level ≈ 50–67 h/combo**
  (~200–270 GPU-h across 4 combos) — for the dimension the matrix already treats as the
  non-discriminating floor (qwen3-32b's run cell is currently "—" like the other reasoning
  models).
- **DECISION (2026-07-24, user): reduce run-level to `N_RUN=5`** (revised from an initial
  "let it ride at n=20" while the combos sat queued `PD (Priority)` — they hadn't started, so
  no compute lost). Rationale: run-level at n=20 = ~50–67 h/combo of the non-discriminating
  floor dimension; n=5 (25 runs/combo ≈ 12–17 h) still confirms qwen3-32b floors while keeping
  each combo to ~20–32 h → all 4 done in ~2–2.7 days, comfortably before the 30th. Comparability
  caveat (documented): run-n=5 differs from the matrix's n=20 elsewhere — fine for a floor dim
  (most reasoning-model run cells are "—" anyway); label qwen3-32b run-level "n=5 floor
  estimate," never blend its magnitude with n=20 rows. turn+combat+synergy stay full n=20 (the
  discriminating horizons — synergy is where qwen3-32b bends away from the 7–8B pack).
  Implemented by parametrizing the combo (`N_RUN`, default 20; 0 skips run) + launcher
  (`N_RUN`, `SKIP_SMOKE`). Relaunch after `scancel 261116–261119`:
  `N_RUN=5 SKIP_SMOKE=1 bash cluster/sharanga_submit_qwen3_matrix.sh` (SKIP_SMOKE=1 because the
  qwen3-32b smoke already passed this session — no need to burn another 53-min gate).
- **Cluster note (sinfo 2026-07-24):** `gpu_h200_8` is a SINGLE node (gpunode7, 8× H200),
  usually `mix` (shared) → combos queue `PD (Priority)` until 3 GPUs free; real contention with
  other users on the one H200 node, but the 6-day window has slack.
- **▶▶ RELAUNCHED + LIVE (2026-07-24):** `N_RUN=5 SKIP_SMOKE=1 bash cluster/sharanga_submit_qwen3_matrix.sh`
  submitted the final matrix — **jobs 261120 (IC/structured), 261121 (IC/raw), 261122
  (Silent/structured), 261123 (Silent/raw)**, no gate (qwen3-32b already validated), queued
  `PD (Priority)` on gpu_h200_8. This is the in-flight run; expect the four
  `results/qwen3-32b*_seeds42_1042_2042_3042_4042.json` aggregates by ~2026-07-30.

**Expected artifacts on return:** `results/qwen3-32b{,_silent}_{structured,raw}_seed*.json`
+ the `_seeds42_1042_2042_3042_4042` aggregates (all 4 dims). Fold-in checklist: scp to laptop
→ per-sample sanity audit (watch for reasoning-model over-deliberation: parse counters,
truncation_errors, run-level wall time) → experiment_log + findings + Current Results tables;
these SUPERSEDE the CSIS synergy-only qwen3-32b cells (never blend serving stacks).

## 2026-07-23 (SHARANGA, gpu_h200_8) — SMOKE PASSED on H200: ~190 tok/s gen (2.3× CSIS A100), 57 s wall — pipeline validated, env unblocked after 3 fixes

**Why:** first run on the Sharanga cluster (BITS Hyderabad, shared account) — validate the exact
pipeline end-to-end + measure tok/s before sizing the registered model ladder (decision_log
2026-07-23). Buy-information-cheapest-first: tiny 4-dim pass, qwen2.5-7b, 1× H200.

**Config.** Interactive `srun` on gpunode7 (gpu_h200_8) after the batch job hit env blockers
(below); vLLM 0.25.1 / torch 2.11.0+cu130, `--max-model-len 16384 --gpu-memory-utilization 0.90`,
benchmark `--n-turn 2 --n-combat 1 --n-synergy 4 --n-run 1 --format structured --seed 42
--run-tag sharanga_smoke` (= no matrix overwrite). Artifacts on-cluster:
`results/qwen2.5-7b_structured_seed42_sharanga_smoke.{json,txt,png}`.

**Anchors (vs CSIS A100 references):**
| Metric | Sharanga H200 | CSIS A100 | Ratio |
|---|---|---|---|
| Generation throughput (batch-1) | **~190 tok/s** sustained | ~82 tok/s | ~2.3× |
| Prompt throughput | ~1,070–1,275 tok/s | ~700–900 | ~1.4× |
| Smoke wall (benchmark only) | **57 s** (`elapsed_seconds` 38.2) | 1m35s | ~1.7× |
| Server cold start (cold node) | ~12–15 min (Lustre load 7.2 min + first compile) | ~3.5 min | — |
| Server warm start (caches hit) | **~90 s** (weights 3.6 s, compile 4 s AOT hit) | — | — |

**Score sanity (per-sample audit vs known 7B matrix behavior — all clean, no boundary values):**
turn dmg .67/1.00 parse_ok=1.0 (expected quantization); combat Cultist win, hp_ratio 1.15,
3 illegal-action / 0 JSON errors; synergy 1/4 archetype (matches the 7B's weak .37); run =
floors 16/16 with hp −16 = died at the boss (correct semantics), survival 0. Instrument behaves
identically to CSIS ⇒ **pipeline valid on Sharanga; ladder sizing can proceed.**

**Env blockers found + fixed (all durable in the env / sbatch, none need root):**
1. **`nvcc` PermissionError killed vLLM's AOT torch.compile** — a non-executable `nvcc` sits in a
   system PATH dir (execvp EACCES; `which` skips it). Fix: `conda install -c nvidia cuda-nvcc`
   into `slaybench` (env bin precedes PATH). CSIS never hit this (vLLM 0.6.6 predates AOT compile).
2. **flashinfer JIT sampling kernel: `curand.h` missing** — conda `cuda-nvcc` ships no library
   headers. `libcurand-dev` fixed the include; ninja STILL failed further in (conda `-ccbin`
   toolchain). Resolution: **`VLLM_USE_FLASHINFER_SAMPLER=0`** (native torch sampler — identical
   sampling semantics, irrelevant at batch≈1; we run temperature 0 anyway). Both packages kept:
   future JIT paths (deep_gemm for the 235B FP8 rung) may want them.
3. **Observability**: first batch job died with a 0-byte vLLM log (block buffering) →
   `PYTHONUNBUFFERED=1`; two ~1-min HF Hub stalls → `HF_HUB_OFFLINE=1`; health-check timeout
   10 → 25 min (cold-node Lustre load alone is 7 min). All baked into `sharanga_smoke.sbatch`.

**Cluster facts learned (also in CLAUDE.md bullet):** gpu_a100_8 DOWN for admin driver
stress-testing (do not trust early A100 tok/s when it returns); **≤4 CPUs per H200 GPU**
submit-time rule; **multi-partition submits rejected** (per-partition associations);
compile/JIT caches live in shared `~/.cache` → warm starts on ANY node after the first.
From the login MOTD (2026-07-23): **scratch auto-purges 15 days after last modification**
(CSIS was 30 — model weights evaporate across gaps; re-prefetch is the plan, scratch is never
storage; results always scp'd to the laptop); **home quota is 40 GiB** (29 used / 11 free at
smoke time — miniconda + `~/.cache` compile caches live there; rules out installing the full
`cuda-toolkit` (~5+ GB) as a flashinfer fallback; if tight: `du -sh ~/miniconda3 ~/.cache/*`).

**Next:** sync the patched sbatch to the cluster (commit+push+pull), then ladder rung 1:
qwen3-32b prefetch + FULL 4-dim matrix (fills the synergy-only gap).

## 2026-07-13 (CLUSTER, gpu-3day) — PARSE PROBE: truncation-vs-malformed ANSWERED — budget-bound deliberation (ratio = 1.0 in all four cells)

**Why:** decide whether the DeepSeek distills' JSON parse failures are token-budget truncation
mid-`<think>` ("budget-bound deliberation") or malformed output ("output-discipline failure") —
unanswerable from pre-instrumentation data (decision_log 2026-07-12 diagnostics entry).

**Config.** `cluster/parse_probe.sbatch` (commit `1e8cd77`+), post-instrumentation harness,
`--run-tag parse_probe` → **diagnostic cells, NEVER foldable into the matrix tables.** Turn
n=20 + combat n=3, **seed 42 only**, max_tokens 8000. Four cells: deepseek-r1-distill-**7b
Ironclad** (both formats) + deepseek-r1-distill-**14b Silent** (both formats). Submitted
2026-07-12 late IST per the contention SOP (`--qos=test-gpu --nodelist=<idle node>`); ~54 min
wall per 7b cell, ~1h44m per 14b cell. Artifacts:
`results/deepseek-r1-distill-{7b,14b_silent}_{structured,raw}_seed42_parse_probe.{json,txt,png}`.

| Cell | Turn parse_fail (of 20) | …truncated | Combat json_parse_err | trunc_err | illegal_act_err | win / hp |
|---|---|---|---|---|---|---|
| 7b IC structured | 10 | **10 (100%)** | 5.67 | **5.67** | 1.67 | .33 / .30 |
| 7b IC raw | 7 | **7 (100%)** | 6.33 | **6.33** | 2.33 | .00 / .00 |
| 14b Silent structured | 1 | **1 (100%)** | 2.33 | **2.33** | 0.33 | 1.00 / .50 |
| 14b Silent raw | 5 | **5 (100%)** | 3.00 | **3.00** | 1.00 | .33 / .21 |

**Verdict: `parse_fail_truncated / parse_fail_n` = 1.0 in ALL four cells, at BOTH horizons**
(combat `truncation_errors == json_parse_errors` exactly). Zero malformed-but-complete
completions anywhere. Per the registered decision rule ⇒ report DeepSeek parse failures as
**"budget-bound deliberation"**: the model spends the entire 8000-token budget inside `<think>`
and never emits the answer. Not a formatting/output-discipline failure.

**Secondary observations.**
- **Counter-split arithmetic verified**: `parse_errors == json_parse_errors +
  illegal_action_errors` exactly in every cell (e.g. 7b raw 8.67 = 6.33 + 2.33). The matrix's
  conflated metric decomposes ≈70–75% truncation + 25–30% valid-JSON-but-illegal — keep citing
  it as **"invalid-action errors."**
- **Probe replicates the matrix** (instrumentation moved nothing): 7b combat win .33/.00 and
  parse_errors 7.3–8.7 ≈ matrix ~8; 14b Silent raw win .33 / hp .21 ≈ the matrix's worst cell
  (.34 / .21).
- **7b structured is WORSE than raw on turn parse** (10 vs 7 truncations; dmg .43 vs .56) —
  consistent with the matrix's structured turn parse_ok floor (.38): the structured prompt
  provokes longer deliberation in the 7b.
- Saved JSONs carry summary counters only (per-sample finish_reason/raw_len records were not
  persisted in the output file) — sufficient for the verdict; raw truncated completions are gone.

**Caveats (travel with any citation):** seed 42 only, combat n=3, four cells; diagnostic
(post-instrumentation) harness run under `--run-tag parse_probe`.

## 2026-07-12 (LOCAL, no API) — GREEDY RUN-LEVEL BASELINE MEASURED (per character; replaces the unreproduced 0.78 anchor)

**Why:** the horizon-collapse curve normalized run-level against a hard-coded
`GREEDY_PROGRESS = 0.78` derived from an *unreproduced* session note ("greedy bot survives
Act 1 ~1/100, avg ~12.5 floors") — no artifact, no seeds, no n — and applied that single
Ironclad-flavoured value to BOTH characters even though Silent's greedy Act 1 is documented
as harsher. Measured it properly (it is FREE: the greedy policy is deterministic engine code,
zero API calls).

**Method / config.** New committed script `scripts/greedy_baseline.py`. It subclasses
`RunEvaluator` (`GreedyRunEvaluator`) and overrides ONLY the LLM decision hooks
(`_llm_combat` → play-every-playable-card greedy AI mirroring `run_loop._resolve_combat`;
`_llm_card_choice` → first non-curse offer; `_llm_boss_relic_choice` → 0), so
`evaluate`/`_play_act` — map traversal, reward/offer counts, elite drops, potion drops, event
auto-pick-0, greedy shop, rest handling — run BYTE-IDENTICAL to the LLM matrix protocol; only
the decisions change from LLM to greedy. `llm_routing=False` (matches the matrix → path pick=0,
rest=REST). Combat capped at `max_combat_turns=50` exactly as the LLM `_llm_combat` is (NOT
run_loop's standalone 100), because this clones the LLM *run* protocol.
- **Seeds:** the exact run-dimension per-sample seeds, derived from code
  (`BenchmarkHarness.run_all`: `run_seeds = range(base+300, base+300+n_run)`), bases
  `42 1042 2042 3042 4042`, `n_run=20` (the matrix's `--n-run 20`) → 20 runs × 5 bases = 100
  runs/character. Aggregation reproduces `_aggregate_summaries`: average the 20 runs within each
  base, then mean ± std of the 5 per-base averages.
- Artifacts: `results/greedy_baseline_ironclad.json`, `results/greedy_baseline_silent.json`
  (per-sample floors/progress/survived + per-base + overall). Gitignored → numbers recorded here.

**Measured greedy baseline (Act 1, n=20/base × 5 bases):**

| Character | avg_floors ± std | avg_progress ± std | survival ± std |
|---|---|---|---|
| Ironclad | 12.48 ± 0.19 | **0.780 ± 0.012** | 0.01 ± 0.022 (1/100) |
| Silent   | 11.26 ± 0.99 | **0.7037 ± 0.062** | 0.00 ± 0.0 (0/100) |

**Did the old "~12.5 / ~1%" note hold up?** For **Ironclad, essentially exactly** — 12.48
floors, 0.780 progress, 1% survival: the session note was a good Ironclad anchor. For **Silent,
NO** — the greedy floor is materially lower (11.26 floors, 0.704 progress, 0% survival). The
shared 0.78 anchor was Ironclad-derived and understated the Silent run edge.

**Validity.** `git log --oneline -- slay_bench/` confirms the last engine/harness change was
`15d4ffb` (5th audit, 2026-06-12); the matrix ran 2026-06-22 and the only later commit touching
`slay_bench/` (`7135bc6`) added `visualize.py` only — so this greedy measurement is on the SAME
engine the matrix ran on. Determinism verified: a repeated run reproduced byte-identical JSONs.
Boundary triage: Ironclad landing at 0.780 (the old note's value) is strong evidence the script's
protocol matches `RunEvaluator`, not a coincidence at a boundary.

**Consequence** (curve anchor now measured + per-character; full before/after per model in
decision_log 2026-07-12 addendum): Ironclad normalized run values unchanged; the **Silent
structured run edge lifts off zero** once anchored to Silent's own floor (qwen2.5-7b 0→0.125,
mistral 0→0.078, llama 0→0.034), while Silent-raw mistral/qwen stay 0 (their progress 0.690/0.679
is at/below the Silent greedy floor 0.704 — genuinely floored, not an artifact). So the Silent
all-zero run edge was **partly an anchor artifact and partly real**. Regression test added
(`test_greedy_baseline_determinism`) → 134 tests pass.

---

## 2026-06-22, completed 2026-07-11 (CLUSTER) — FULL 5-MODEL MATRIX, 5 seeds (CURRENT valid data, supersedes the Qwen-only table)

The four extra models are in: **llama-3.1-8b** (2nd family), **mistral-7b** (3rd family),
**qwen3-32b** (revived reasoning model, synergy-only), **deepseek-r1-distill-14b** and
**deepseek-r1-distill-7b** (reasoning-distill family). All self-hosted (A100 80 GB), same
harness, `--seeds 42 1042 2042 3042 4042` (mean ± std), all 24 aggregates scp'd to the laptop
(`results/<model>*_seeds42_1042_2042_3042_4042.json`). Qwen2.5-7B numbers unchanged (re-pulled,
identical to the 2026-06-13 pass). **Coverage is now ≥3 model families + a reasoning model — the
two biggest D&B gaps from the novelty review are closed.** **2026-07-11: the DeepSeek gap-fill
jobs landed** (14b Silent-raw turn/combat; 7b turn/combat + synergy, all four combos) — every
number below was re-read from the on-disk aggregates on 2026-07-12 and the tables are now the
complete, authoritative matrix (remaining `—` cells are *intentionally not collected*, not
pending; see "Coverage gaps").

### Ironclad — all models, n=20, 5 seeds (mean; structured / raw)

| Model | Turn dmg | Combat win | Combat hp_ratio | Syn archetype | Syn pick | Syn removal | Run floors | Run progress |
|---|---|---|---|---|---|---|---|---|
| qwen2.5-7b | .701 / .665 | 1.00 / 1.00 | 1.04 / 1.07 | .37 / .25 | .47 / .27 | .24 / .02 | 12.81 / 13.36 | .80 / .835 |
| llama-3.1-8b | .487 / .711 | 1.00 / 1.00 | 1.04 / 1.04 | .51 / .41 | .69 / .61 | .15 / .07 | 13.37 / 13.76 | .836 / .86 |
| mistral-7b | .177 / .416 | 1.00 / 1.00 | 1.04 / 1.01 | .33 / .45 | .58 / .36 | .15 / .00 | 12.72 / 12.83 | .795 / .802 |
| deepseek-r1-14b | **.823** / .754 | .92 / .73 | .75 / .55 | .48 / .50 | .53 / .57 | .18 / **.30** | 9.75 / — | .609 / — |
| deepseek-r1-7b | .343 / .427 | .27 / .19 | .11 / .08 | .38 / .43 | .63 / .62 | **.54** / .42 | — / — | — / — |
| qwen3-32b | — / — | — / — | — / — | .53 / .50 | .59 / .58 | .29 / .22 | — / — | — / — |

(qwen3-32b ran synergy only — turn/combat/run not collected. deepseek-r1-14b raw run-level and
deepseek-r1-7b run-level not collected — intentional, see Coverage gaps. ⚠️ deepseek-7b synergy
parse_ok is degraded — 0.92 structured / 0.70 raw, so only ~18.4 / ~14.0 of 20 fixtures scored
per seed; its synergy accs are conditioned on the parseable subset.)

### Silent — all models, n=20, 5 seeds (mean; structured / raw)

| Model | Turn dmg | Combat win | Combat hp_ratio | Syn archetype | Syn pick | Syn removal | Run floors |
|---|---|---|---|---|---|---|---|
| qwen2.5-7b | .663 / .681 | 1.00 / 1.00 | 1.02 / 1.01 | .60 / .42 | .53 / .45 | .36 / .18 | 11.85 / 10.86 |
| llama-3.1-8b | .472 / .810 | 1.00 / 1.00 | 1.01 / 1.01 | .72 / .61 | .49 / .57 | .18 / .16 | 11.42 / 11.34 |
| mistral-7b | .200 / .394 | 1.00 / 1.00 | 1.02 / 0.90 | .34 / .43 | .56 / .20 | .04 / .00 | 11.63 / 11.04 |
| deepseek-r1-14b | .839 / .721 | .57 / .34 | .39 / .21 | .60 / **.66** | .68 / .61 | .15 / .41 | — / — |
| deepseek-r1-7b | .261 / .334 | .28 / .14 | .15 / .05 | .42 / .31 | .50 / .45 | .45 / .41 | — / — |
| qwen3-32b | — / — | — / — | — / — | **.80** / .64 | .57 / .46 | **.55** / .32 | — / — |

(⚠️ deepseek-7b Silent synergy parse_ok 0.91 structured / 0.69 raw → ~18.2 / ~13.8 of 20 scored
per seed. deepseek-14b Silent-raw turn parse_ok 0.78; its combat parse_errors 4.97/combat.)

### ✅ Gap-fill jobs LANDED (submitted 2026-06-22, retrieved 2026-07-11, folded 2026-07-12)
- **deepseek-r1-distill-14b Silent raw turn/combat** (`gpu-3day`, `turn_combat_models_silent.sbatch`):
  turn dmg **.721** (legal .75, parse_ok .78), combat win **.34**, hp_ratio **.21**, parse_errors
  4.97 — the 14b's worst combat line; Silent raw is where its `<think>` verbosity costs the most.
  14b Silent is now turn/combat/synergy complete in both formats; only Silent run remains open
  (a floor dim, intentionally skipped).
- **deepseek-r1-distill-7b turn/combat + synergy, all four combos** (`gpu-1day` + `gpu-short`):
  the collapse generalizes matrix-wide — turn dmg .26–.43, combat win .14–.28, hp_ratio .05–.15,
  combat parse_errors 7.9–8.3 in every combo. **7b run-level intentionally skipped** (it's the
  "small distill fails the JSON contract" data point, not a competitive line; run is a floor
  effect anyway). One surprise in the wreckage: **7b synergy removal is strong** (.41–.54;
  IC structured **.54** is the 2nd-best removal in the whole matrix, behind only qwen3-32b
  Silent .55) — but read with the parse_ok caveat above (only the parseable ~70–92% scored).

### Coverage gaps (what is NOT collected, so the matrix is read honestly)
- **qwen3-32b: synergy only** (turn/combat/run all null). It's a synergy data point — but the
  decisive one: its Silent-structured archetype **0.80** and removal **0.55** are the highest
  in the entire matrix, and it's the only reasoning model that *stays terse* (parse_ok=1.0).
- **deepseek-r1-14b: Ironclad complete incl. run; Silent complete on turn/combat/synergy both
  formats** (gap-fill 2026-07-11); no Silent run (floor dim, skipped).
- **deepseek-r1-7b: turn/combat + synergy complete, all four combos** (gap-fill 2026-07-11);
  run-level intentionally skipped (collapse line — see findings).
- New models' run-level is sparse (only deepseek-14b Ironclad, llama, mistral have it) but
  run-level is a floor effect anyway → not a blocker for the headline claims.

### Headline findings (full prose in docs/findings.md)
1. **The horizon-collapse story now has model separation.** qwen3-32b (reasoning) tops synergy
   (Silent archetype 0.80, removal 0.55) — the *only* model that pulls clearly away from the
   7–8B pack at the deck-building horizon. This is the frontier-model line the curve needed.
2. **Reasoning ≠ free win — the distill *family* splits hard by size.** deepseek-r1-**14b** is
   strong at short horizons (best turn dmg both characters: IC 0.823, Silent 0.839) but its
   verbose `<think>` decode *hurts* longer horizons: combat win drops to 0.92/0.73 on Ironclad
   (first model below 1.0), Silent combat to 0.57 structured / **0.34 raw** (hp_ratio 0.21),
   and Ironclad run floors crash to **9.75 — below the greedy ~12.5 floor** (it overthinks
   itself to death). deepseek-r1-**7b** collapses outright in *every* combo (turn 0.26–0.43,
   combat win 0.14–0.28, parse_errors ~8/combat) — the small distill can't keep the JSON
   contract. Anomaly worth a sentence in the paper: 7b's synergy **removal** stays high
   (.41–.54, 2nd-best in the matrix on IC structured) — the judgment task survives the
   execution collapse (with the parse_ok-conditioning caveat).
3. **Format ablation replicates across families but is character/model-dependent in sign.**
   Structured wins synergy for qwen2.5/llama; mistral *reverses* on Ironclad archetype
   (raw .45 > structured .33). Turn: llama & mistral are *better in raw* on both characters
   (llama Silent raw .810 vs structured .472) — opposite of qwen2.5 Ironclad. The most robust
   cross-model format signal is **synergy removal** (structured ≥ raw for qwen2.5, llama,
   mistral, qwen3-32b AND deepseek-7b: e.g. mistral .15→.00, qwen2.5 .24→.02) — with **one
   documented exception: deepseek-14b reverses removal in BOTH characters** (IC .18
   structured / **.30** raw; Silent .15 / **.41**), so state it as "structured ≥ raw for 5 of
   6 models; the sole reversal is the verbose-`<think>` 14b distill."
4. **Combat/run stay format- and largely model-insensitive on outcome** (almost everyone wins
   1.0, hp_ratio ≈ 1.0, floors ≈ greedy ~12.5) — except the reasoning models, which are the only
   ones that *lose* combats. Confirms the multi-horizon thesis: model differences surface at the
   reasoning horizons (synergy), wash out at the engine-survival horizons (combat/run).

## 2026-06-13 (CLUSTER) — PAPER-GRADE 4-DIMENSION RESULTS, Qwen2.5-7B, 5 seeds (CURRENT valid data)

**First complete paper-grade matrix.** Qwen2.5-7B-Instruct, self-hosted (vLLM 0.6.6, A100
80 GB, csis.cn2), `--seeds 42 1042 2042 3042 4042` (spaced 1000 apart → disjoint per-sample
windows, real std), both prompt formats. Ironclad n=20 all four dimensions; **Silent now also
complete on all four** (synergy 2026-06-13; turn/combat/run added 2026-06-14). All
`results/qwen2.5-7b*_seeds42_1042_2042_3042_4042.json`
scp'd to the laptop. This **supersedes all stale pilot turn/combat numbers and all earlier
synergy data** (this is the first multi-seed, self-hosted, post-5-audit pass). parse_ok=1.0
on every dimension/format → instrument clean.

**Cluster jobs:** turn+combat (job 7539), synergy (both characters), run-level structured +
raw (jobs 7542 fixed → resubmit, 7545). The lone failure (7542 run-level, 0 completed runs)
was a stale vLLM holding :8000 — fixed in `cluster/lib.sh` (`f2c9a6b`: per-job port,
`fuser -k` before launch, readiness probe matches SERVED_NAME, bind-failure fast-fail).

### Ironclad — turn / combat / synergy / run (n=20, 5 seeds, mean ± std)

| Dimension | Metric | structured | raw |
|---|---|---|---|
| Turn | avg_damage_ratio | 0.701 ± 0.078 | 0.665 ± 0.175 |
| Turn | legal_rate | 0.78 ± 0.057 | 0.73 ± 0.179 |
| Combat | win_rate | 1.00 ± 0.0 | 1.00 ± 0.0 |
| Combat | avg_hp_ratio | 1.042 ± 0.025 | 1.065 ± 0.020 |
| Combat | avg_parse_errors | 2.51 ± 0.26 | 2.59 ± 0.34 |
| Synergy | archetype_acc | 0.37 ± 0.027 | 0.25 ± 0.0 |
| Synergy | card_pick_acc | 0.47 ± 0.076 | 0.27 ± 0.067 |
| Synergy | removal_acc | 0.24 ± 0.022 | 0.02 ± 0.027 |
| Run | survival_rate | 0.03 ± 0.027 | 0.00 ± 0.0 |
| Run | avg_floors_reached | 12.81 ± 1.19 | 13.36 ± 0.79 |
| Run | avg_progress | 0.80 ± 0.075 | 0.835 ± 0.049 |
| Run | avg_draft_coherence | 0.36 ± 0.034 | 0.33 ± 0.033 |

(parse_ok = 1.0 on turn + synergy in both formats.)

### Silent — turn / combat / synergy / run (n=20, 5 seeds, mean ± std)

Synergy collected in the 2026-06-13 pass; **turn/combat/run added 2026-06-14** via the new
`cluster/turn_combat_silent.sbatch` + `cluster/run_level_silent.sbatch` (Silent counterparts —
the Ironclad turn/combat/run sbatch jobs scope themselves to Ironclad). Silent is now a
**complete 4-dimension matrix**, both formats. parse_ok=1.0 throughout.

| Dimension | Metric | structured | raw |
|---|---|---|---|
| Turn | avg_damage_ratio | 0.663 ± 0.035 | 0.681 ± 0.047 |
| Turn | legal_rate | 0.87 ± 0.045 | 0.84 ± 0.082 |
| Combat | win_rate | 1.00 ± 0.0 | 1.00 ± 0.0 |
| Combat | avg_hp_ratio | 1.024 ± 0.015 | 1.007 ± 0.021 |
| Combat | avg_parse_errors | 0.92 ± 0.179 | 3.38 ± 0.192 |
| Synergy | archetype_acc | 0.60 ± 0.0 | 0.42 ± 0.027 |
| Synergy | card_pick_acc | 0.53 ± 0.084 | 0.45 ± 0.05 |
| Synergy | removal_acc | 0.36 ± 0.022 | 0.18 ± 0.045 |
| Run | survival_rate | 0.00 ± 0.0 | 0.01 ± 0.022 |
| Run | avg_floors_reached | 11.85 ± 0.449 | 10.86 ± 0.781 |
| Run | avg_progress | 0.741 ± 0.028 | 0.679 ± 0.049 |
| Run | avg_draft_coherence | 0.344 ± 0.035 | 0.348 ± 0.005 |

**Silent-specific observations (new turn/combat/run):**
- **Turn-level format effect vanishes / mildly reverses on Silent** (raw 0.681 ≈ structured
  0.663, within noise; raw even nudges ahead). Unlike Ironclad, where structured won turn
  (0.701 vs 0.665). → The turn-format effect is **character-dependent**, not universal; the
  robust format signal lives in synergy for both characters.
- **Combat format-insensitive on outcome** (both win 1.0, hp_ratio ≈ 1.0–1.02, on par with
  greedy). The only format trace is parse_errors: raw 3.38 vs structured 0.92 — the verbose
  English combat state is harder to act on cleanly even when it doesn't change the win.
- **Silent reaches fewer floors than Ironclad** (10.9–11.9 vs 12.8–13.4) and survival ≈ 0.
  Silent's lower-block starter makes the post-audit Act-1 greedy combat harsher; survival is
  still a floor effect → report avg_floors / avg_progress, frame "on par, not beating."

**Key results:**
- **Structured beats raw on every reasoning-heavy metric, both characters.** Synergy is the
  sharpest: Ironclad card_pick 0.47→0.27, removal 0.24→**0.02**, archetype 0.37→0.25; Silent
  archetype 0.60→0.42, removal 0.36→0.18. **This is the seed-matched format ablation landing
  cleanly on a self-hosted model** (the novelty claim). Turn raw also has ~2× the variance of
  structured (±0.175 vs ±0.078) — verbose prompts make the 7B less consistent.
- **Combat / run are format-insensitive.** Both formats win 100% of the scripted combats with
  hp_ratio ≈ 1.04–1.07 (on par with the greedy bot, NOT beating it — the prior >100% artifact
  is fixed) and reach ~12.8–13.4 of 16 floors before dying at the Act-1 boss. These dimensions
  are dominated by engine survival, not prompt comprehension, so format barely moves them.
- **Run-level survival is near-floor (0.03 / 0.0).** Expected: the scripted greedy baseline
  itself survives Act 1 only ~1% of the time under the post-audit engine (avg ~12.5 floors).
  So survival_rate has a floor effect; **avg_floors_reached / avg_progress are the
  discriminating run-level metrics** (Qwen 12.8–13.4 floors ≈ greedy ~12.5 → on par).
- **Silent synergy > Ironclad synergy** (archetype 0.60 vs 0.37; removal 0.36 vs 0.24,
  structured) — consistent with the earlier llama/scout finding that Silent's
  Poison/Shiv/Block/Discard labels read more literally off the cards.
- **raw archetype collapses to a constant "Block" guess — VERIFIED per-sample (not a bug).**
  Ironclad raw labels **17/20 fixtures "Block" every seed** (std≈0 is the collapse signature).
  The 20 fixtures are 5 each Exhaust/Aggro/Strength/Block; raw's 5/20 is **exactly the 5 Block
  decks** → raw archetype acc = the Block base rate of its single guess (0.25), *below* the
  same model's structured 0.35–0.40. Confirmed prompt-driven, not instrument: (a) fixtures do
  cycle all archetypes; (b) structured on the same fixtures spreads answers (Block 10–11,
  Strength 6–8, Aggro 1–3) and scores 7–8/20 — both formats would collapse if the instrument
  were broken; (c) parse_ok=1.0. Verbose English mentions Block/defense in nearly every card
  description → 7B anchors on it; compact JSON forces reading the card list. Per-sample data in
  `results/qwen2.5-7b_{raw,structured}_seed*.json` (`synergy.samples`). See docs/findings.md.

**Greedy baseline anchor (for the paper):** scripted greedy bot survives Act 1 ~1/100,
avg ~12.5 floors. Use this to frame run-level/combat as "on par with greedy," never "beats."
> ⚠️ **Superseded 2026-07-12 — now MEASURED per character** (see the 2026-07-12 entry at the top).
> This note was an unreproduced Ironclad-flavoured estimate. Measured: **Ironclad 12.48 floors /
> 0.780 progress / 1% survival** (the note held up for Ironclad), **Silent 11.26 floors / 0.704
> progress / 0% survival** (Silent's greedy floor is lower — the shared 0.78 anchor understated
> the Silent run edge). Framing ("on par with greedy, never beats") is unchanged and still correct.

---

## 2026-06-13 (CLUSTER) — first real self-hosted runs on BITS CSIS Slurm (Qwen2.5-7B)

**Hardware:** A100 80 GB (csis.cn2), vLLM 0.6.6 + transformers 4.47.1 + torch 2.5.1+cu124,
served `Qwen/Qwen2.5-7B-Instruct` as `qwen2.5-7b` via `cluster/*.sbatch`.

**Smoke (job 7536) — PASSED.** Tiny full pass (`--n-turn 2 --n-combat 1 --n-synergy 4
--n-run 1`, structured, seed 42) ran end-to-end and wrote `results/qwen2.5-7b_structured_seed42.*`.
- Wall time: **1m35s** (`time` real) for the benchmark; vLLM startup ~3.5 min separately.
- Throughput from `vllm_7536.log`: **~82 tok/s generation**, ~700–900 tok/s prompt.
- Used to calibrate `run_level.sbatch`: n=5 validation ≈18 min; paper-grade n=20×5 seeds ≈4h.

**Turn+combat re-baseline (job 7539) — RUNNING.** `--only turn combat --n-turn 20 --n-combat 20
--seeds 42 43 44 45 46` ×2 formats, Ironclad, Qwen2.5-7B. Early turn-level signal healthy:
parse_ok=1.0 (instrument clean), ~50/50 legal-optimal vs illegal-bust for the 7B, dmg_ratios
clustering at 1.0/0.67/0.0 (quantization from short low-energy opening turns, not a bug).

**Cluster issues hit + resolved (full notes in CLAUDE.md "CLUSTER GOTCHAS"):**
- `lib.sh` defaulted to `Qwen/Qwen3-32B` which vLLM 0.6.6 can't load → defaulted to Qwen2.5-7B (`30551a9`).
- `#SBATCH --time=24:00:00` rejected by QOS (`QOSMaxWallDurationPerJobLimit`) → submit with `--time=03:00:00` override.
- Confirmed result filenames are character-namespaced (Ironclad untagged, Silent `_silent`),
  so the `--only` merge + synergy's both-character loop don't collide — no code change needed.

**Next:** finish 7539 → verify tail → `sbatch --time=03:00:00 cluster/synergy.sbatch` → run_level.

---

## 2026-06-12 (GPU prep) — `--provider local` adapter (NO API runs; mock + unit verification)

**What ran:** full test suite (**118/118**, +3 new LocalLLM regression tests over the
4th-audit 115/118 baseline — request shape/URL via stubbed `urlopen`, server-error
surfacing, `build_llm` wiring) and the mock pipeline (`--provider mock`, seed 42, tiny
full pass) — green end-to-end. No paid/free/GPU API calls (the GPU is not yet available).

**What changed:** added `LocalLLM` (OpenAI-compatible self-hosted client) + `--provider
local --base-url`. Commit `a36b42d`. No engine/scoring change → **no data-validity impact**;
synergy n=20 (2026-06-10, de-biased) remains the only valid data. This is pure
infrastructure prep for the M3a GPU phase. Next experiment is the GPU smoke test once
access lands (record tok/s → sizes run-level n).

## 2026-06-11 (later) — 3rd audit + fix batch (NO API runs; mock verification only)

**What ran:** full test suite (**102/102**, was 77; +25 regression tests) and mock
pipeline (`--provider mock`, seed 42) for Ironclad structured + raw and Silent
structured — green end-to-end. No API calls.

**What changed (data-validity consequences):** 40 new bugs fixed
(`docs/bug_audit_2026-06-11.md`). Combat dynamics changed for a FOURTH time:
HP-loss now bypasses block, Havoc no longer shrinks/duplicates decks, and —
biggest — **enemy block now actually exists** (it was wiped before the player's
turn, so all enemy blocking moves were no-ops; enemies are tougher). Turn-eval
duplicate-index replay loophole closed (legality is stricter — turn scores not
comparable to stale ones for this reason too). Run-level: Neow's 1-HP boon removed
from the mid-run event pool, events no longer repeat → the first valid run-level
pass will be on a fairer, harder run loop. **Synergy n=20 (2026-06-10, de-biased)
remains the only valid data — unaffected** (one prompt-byte change: Blood for
Blood's exhaust flag in a single Aggro offer is now false).

## 2026-06-11 — Engine-fidelity fix batch (NO API runs; mock verification only)

**What ran:** full test suite (77/77, was 56; +21 regression tests) and mock pipeline
(`--provider mock`, structured, seed 42) for BOTH characters — green end-to-end, charts
written. No paid/free API calls this session.

**What changed (data-validity consequences):**
- All of `docs/bug_audit_2026-06-10.md` Part 2 implemented + 9 new Part 3 fixes (2 critical:
  vanishing played cards via dataclass `__eq__`; double exhaust emit). Combat dynamics
  changed → turn/combat numbers remain stale (now for a third reason); **synergy n=20
  below is still the only valid data** (static deck snapshot, no combat involved).
- ⚠️ The 4 **Aggro fixture decks changed** (Perfected Strike → Cleave/Wild Strike/Clash,
  audit item 2.8): the next synergy run regenerates point estimates. Aggregates stay
  comparable (same archetype balance, same offers/picks/removals); per-row values for the
  4 Aggro fixtures do not line up with the saved seed-42 files.
- Elites now drop relics, MERCHANT floors act, Maw Bank/Peace Pipe/etc. live → the
  (still-pending) first valid run-level pass will exercise a substantially richer run loop.

## 2026-06-10 — Synergy n=20, both characters, DE-BIASED instrument (CURRENT valid synergy data)

**Config:** `--only synergy --n-synergy 20`, seed=42, free Groq, post-bug-sweep code.
8 runs = 2 models × 2 formats × {Ironclad, Silent}. Silent is **first-ever synergy data**.
Ran via `.venv\Scripts\python.exe` (system Python lacks `groq` — gotcha logged below).

⚠️ **These numbers REPLACE an earlier biased run from the same day.** The first n=20 pass
ran on a synergy instrument with a positional confound (expert pick was at offer index 0 in
35/40 fixtures) + one mislabeled fixture; those card-pick numbers were not interpretable.
Fixed in commit `5db7063` (offer rotation cycles the correct index 0→1→2; fixture #18 pick
corrected; strict single-name archetype match) and re-run. Rotation verified: expert-pick
position is now uniform {0:7,1:7,2:6} and the model spreads its answers {0:5,1:9,2:6} rather
than parroting 0. See "Bugs Fixed" #synergy-instrument in CLAUDE.md.

| Character | Model | Format | n | Archetype | Card Pick | Removal | Parse |
|---|---|---|---|---|---|---|---|
| Ironclad | llama-3.1-8b | structured | 20 | 0.55 | 0.65 | 0.15 | 1.0 |
| Ironclad | llama-3.1-8b | raw | 20 | 0.40 | 0.65 | 0.05 | 1.0 |
| Ironclad | scout-17b | structured | 20 | 0.70 | 0.75 | 0.25 | 1.0 |
| Ironclad | scout-17b | raw | 20 | 0.45 | 0.70 | 0.15 | 1.0 |
| Silent | llama-3.1-8b | structured | 20 | 0.75 | 0.35 | 0.15 | 1.0 |
| Silent | llama-3.1-8b | raw | 20 | 0.60 | 0.65 | 0.15 | 1.0 |
| Silent | scout-17b | structured | 20 | 0.75 | 0.70 | **0.60** | 1.0 |
| Silent | scout-17b | raw | 20 | **0.80** | **0.75** | 0.20 | 1.0 |

**Per-archetype archetype-ID, all 8 combos pooled (20 attempts each, 40 for Block):**

| Archetype | Correct | Character |
|---|---|---|
| Aggro | 19/20 = 95% | Ironclad |
| Poison | 19/20 = 95% | Silent |
| Shiv | 18/20 = 90% | Silent |
| Block | 34/40 = 85% | both |
| Strength | 8/20 = 40% | Ironclad |
| **Exhaust** | **1/20 = 5%** | Ironclad |
| **Discard** | **1/20 = 5%** | Silent |

**Key results (n=20, both characters, de-biased):**
- **Mechanic-defined archetypes are the universal blind spot — now airtight.** Pooled over
  all 8 combos, **Exhaust 5% and Discard 5%** sit far below every surface-readable archetype
  (Aggro/Poison/Shiv/Block 85–95%). Both characters' miss is exactly the archetype defined by
  a *payoff mechanic* (exhaust / discard), not a card-name keyword. Strength (40%) is the
  intermediate case — frequently "Aggro" because Strength decks are Strike-heavy.
- **Card-pick survived de-biasing** (0.65–0.75 for both models on most combos, vs ~0.33
  chance) — so the **name-vs-play dissociation is real, not a positional artifact**: models
  judge local card quality well even on decks they cannot label. (The lone exception, Silent
  llama structured at 0.35, is a genuine weak spot, not the old bias.)
- **Silent archetype-ID ≥ Ironclad** (0.60–0.80 vs 0.40–0.70). Plausibly Silent labels
  (Poison/Shiv/Block/Discard) read more literally off the cards than Ironclad's abstractions.
- **scout-17b Silent structured removal 0.60** is still the standout — the removal blind spot
  is much weaker on Silent for the bigger model. Removal stays near-floor (0.05–0.25)
  everywhere else.
- parse_ok = 1.0 everywhere.

**Caveat:** all 8 are seed=42 only (one fixture pass; deterministic). For paper-grade error
bars still need `--temperature 0.7` k-sampling or a seed sweep — the harness supports both.

---

## 2026-06-10 — No new runs; harness extended for A* acceptance (code-only)

**Status:** No experiments — run-level remains blocked on free Groq TPM (paid tier pending).
Harness changes that affect FUTURE runs (commit d35771e):
- Silent character (full card set + 20 synergy fixtures; Ironclad fixtures expanded 8 → 20)
- Multi-act runs (`--acts 3`), `--temperature`, `--seeds` (mean±std), `--llm-routing`
- Relic lifecycle split (on_pickup/register) — relics no longer stack across a run

**Comparability note:** the relic-stacking fix changes run-level dynamics, so any future
run-level numbers are NOT comparable to pre-2026-06-10 ones — which is moot, since all
existing run-level data was already invalid (map dead-end + EventBus bugs).

**Bug sweep (same day, later):** a full logic+code audit fixed 21 bugs (see CLAUDE.md
"Bugs Fixed"). The player-debuff timing fix (tick at end of round, not before enemy
attacks) **changes combat-level dynamics too**: enemy-applied Weak/Vulnerable now actually
affect the player, so the greedy baseline and LLM combats both take more damage (the Act-1
determinism fixture flipped from survived=True/hp=74 to survived=False/hp=0). ⇒ **Pilot
turn/combat numbers in the tables below were collected on the pre-sweep engine and are not
comparable to future runs.** Synergy is unaffected (static deck snapshot, no combat).
Also fixed before any paid run could be burned: the multi-seed aggregator was emitting
`null` for most means (wrong metric key names). 47 tests pass (24 benchmark + 10 combat +
13 run; needs `PYTHONIOENCODING=utf-8` on Windows consoles).

---

## 2026-06-07 — Synergy re-run on HAND-CRAFTED fixtures, n=8 (CURRENT valid synergy data)

**Config:** `--only synergy --n-synergy 8`, both formats, both models, seed=42.
**Status:** Valid + current. Supersedes ALL earlier synergy numbers (which used RNG-drafted
decks). 8 fixtures = one pass over the fixed set (2 per archetype × 4 archetypes); all 8
classify confident, 0 ambiguous.

| Model | Format | Archetype | Card Pick | Removal | Parse OK |
|---|---|---|---|---|---|
| llama-3.1-8b-instant | structured | 50.0% | 100% | 25.0% | 100% |
| llama-3.1-8b-instant | raw | 37.5% | 62.5% | 12.5% | 100% |
| llama-4-scout-17b | structured | 75.0% | 75.0% | 25.0% | 100% |
| llama-4-scout-17b | raw | 50.0% | 100% | 12.5% | 100% |

**Per-archetype identification (8 attempts each = 2 decks × 2 models × 2 formats):**

| True archetype | Correct | Models said instead |
|---|---|---|
| Block | 7/8 | one "Strength" |
| Aggro | 8/8 | — |
| Strength | 2/8 | almost always "Aggro" |
| Exhaust | 0/8 | ALWAYS "Aggro" |

**Key findings (NEW, from clean fixtures):**
- **Exhaust archetype is never recognised** (0/8) — every model/format calls it "Aggro".
  Strength also weak (2/8). Models name an archetype only when its signature is a simple
  surface pattern (Block, generic Aggro); they miss mechanic-defined strategies (Exhaust
  payoff) even with signature cards present. Systematic, not noise.
- **Name-vs-play dissociation:** card-pick is high (62.5–100%) even on decks the model can't
  label — local card-quality judgement is strong, abstract strategic label is weak.
- **Removal still near-zero** (12.5–25%) — the 25% comes only from Block fixtures where the
  removal target coincides; models cut situational cards, not basic Strike.
- scout-17b (structured) is the best archetype identifier (75%). No single format wins
  outright: raw helps llama card-pick, structured helps scout archetype ID.

**Note:** the old `67%/100%` archetype figures (RNG-draft era) are RETIRED. They came from a
3-deck RNG sample with an Aggro-biased heuristic and do not reflect the fixed-deck eval.

---

## 2026-06-07 — qwen3-32b DROPPED (no valid data on free tiers)

**Status:** Excluded from the study. Result files deleted.

qwen3-32b (reasoning model) was wired and attempted on both providers; neither free
tier could produce valid data:
- **OpenRouter free:** ~30–80 tok/s → n=5 run-level = 1.5–3h; free credits exhausted
  mid-run → HTTP 402 Payment Required.
- **Groq free:** 6000 TPM cap truncated its reasoning mid-`<think>` → parse-failure
  cascade, 0% across every dimension (turn/combat/synergy/run all 0; combat parse
  errors 7.67/sample).

Root cause is infrastructural, not a model-capability result — so the 0% scores are NOT
reported as qwen3 performance. A reasoning model needs a PAID tier (paid Groq preferred:
uncapped TPM + ~400–1000 tok/s). Revisit = future work. See docs/notes.md, docs/report.md.

---

## 2026-06-07 — Synergy re-run (post synergy-fix): all models, seed=42  [SUPERSEDED]

**Config:** `--only synergy`, n_synergy=3, both formats, both models
**Status:** ⛔ SUPERSEDED by the hand-crafted n=8 run above. These used RNG-drafted decks +
an Aggro-biased heuristic (only ~3/10 decks confidently labelled); the 67%/100% figures are
retired. Kept for history only.

| Model | Format | Archetype | Card Pick | Removal | Parse OK |
|---|---|---|---|---|---|
| llama-3.1-8b-instant | structured | 67% | 33% | 0% | 100% |
| llama-3.1-8b-instant | raw | 100% | 33% | 0% | 100% |
| llama-4-scout-17b | structured | 67% | 67% | 0% | 100% |
| llama-4-scout-17b | raw | 100% | 33% | 0% | 100% |

**Key findings:**
- Removal 0% confirmed genuine model failure (not a bug). Expert says remove Strike; models say Disarm/Battle Trance/Bash — reasoning about card quality, not deck cycling.
- Raw format = 100% archetype acc for both models. Structured = 67%.
- Scout-17b better at structured card pick (67% vs 33%).

---

## 2026-06-07 — Post-fix run: llama-3.1-8b-instant, seed=42

**Config:** n_turn=5, n_combat=3, n_synergy=3, n_run=5, both formats
**Status:** Turn/combat/run valid. Synergy invalid (pre-synergy-fix) — needs re-run with `--only synergy`.

| Metric | Structured | Raw |
|---|---|---|
| Turn damage ratio | 36.7% | 69.6% |
| Turn legal rate | 60% | 100% |
| Combat win rate | 100% | 100% |
| Combat HP ratio | 112.3% | 113.8% |
| Synergy archetype | 0% ⚠ | 66.7% ⚠ |
| Synergy best card | 33.3% ⚠ | 33.3% ⚠ |
| Synergy removal | 0% ⚠ | 0% ⚠ |
| Run survival | 20% | 40% |
| Run avg floors | 13.4/15 | 13.4/15 |
| Run HP fraction | 93.8% survivors | 60.6% survivors |
| Run draft coherence | 36.4% | 40.9% |
| **Overall** | **41.9%** | **60.7%** |

**Notes:** Run-level now real (map+EventBus bugs fixed). Raw significantly outperforms structured overall. Synergy marked ⚠ — synergy eval used starter deck throughout; fix landed after this run.

---

## 2026-06-07 — Pilot: llama-3.1-8b-instant, seed=42

**Config:** n_turn=5, n_combat=3, n_synergy=3, n_run=1, both formats

| Metric | Structured | Raw |
|---|---|---|
| Turn damage ratio | 36.7% | 69.6% |
| Turn legal rate | 60% | 100% |
| Combat win rate | 100% | 100% |
| Combat HP ratio | 112.3% | 108.5% |
| Synergy archetype | 66.7% | 100% |
| Synergy best card | 100% | 33.3% |
| Synergy removal | 0% | 0% |
| Run survival | 0% | 0% |
| Run floors | 5/15 | 5/15 |
| **Overall** | **48.1%** | **53.5%** |

**Notes:** Run floors were artificially stuck at 5/15 due to map dead-end bug (now fixed). Run results invalid — need re-run.

---

## 2026-06-07 — Pilot: meta-llama/llama-4-scout-17b-16e-instruct, seed=42

**Config:** n_turn=5, n_combat=3, n_synergy=3, n_run=1, both formats

Results saved in `results/meta-llama-llama-4-scout-17b-16e-instruct_*.txt`. Need to review.

---

## Bugs that invalidated earlier results

1. **Map dead-end** — all pre-fix run results show floors=5/15, invalid.
2. **EventBus stacking** — survival=1.0, hp_fraction=1.0 for weak models, invalid.
Both fixed as of 2026-06-07. Any runs before these fixes need to be discarded and re-run.
