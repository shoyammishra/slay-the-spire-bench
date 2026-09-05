# Controlled-H expansion runbook

Established 2026-09-05. This is a local, model-free fixture/oracle procedure.
It does not submit cluster jobs or call a model. Protocol:
`configs/controlled_h_v2_expansion.json`; digest
`bfe8c1306661fb28eb336ec0e3306e4cee11dd47e0f6d2c16c4be83cd7f1288b`.

**Execution update, later 2026-09-05:** the production screen is complete
(800/800 exact; 782 fresh advances). A one-row full-stage smoke passed all H,
including exact H=8 in 93.95 s. The remaining 1,020-row full audit is now
running locally in a hidden background process. Read its explicit process
metadata from `results/controlled_h_v2_expansion_background.json` and inspect
the full checkpoint; do not launch the example commands concurrently against
that output. No release result or model inference exists for the expansion yet.

**Unattended completion:** a separate hidden local supervisor is now armed.
Its status is `results/controlled_h_v2_expansion_supervisor_status.json`, with
its explicit PID in `results/controlled_h_v2_expansion_supervisor_process.json`.
It polls every 30 seconds, stops on incomplete worker exit/source drift, and
only after 1,020 completed dispositions runs release and the independent
fixture check. Do not manually run release concurrently with this supervisor.
Possible final status is `release-go-independently-audited`, `release-no-go`,
`stopped-incomplete`, or `needs-review`. None authorizes model inference.

## Frozen scope

The release target is 252 fixtures per character (63 sensitive + 189 controls).
Planning power covers Qwen3-32B/structured, two character-specific primary
H8-minus-H1 tests at alpha .025 each, .10 absolute effect, and 80% marginal
power under the audited pilot SD bounds. This is a fixture freeze; a complete
confirmatory inference/analysis protocol, including missing-pair treatment,
remains to be frozen. It does not power cross-model contrasts automatically.

The expansion reuses 334 eligible old rows after excluding all 30 pilot
fixtures. It fully audits all 238 untouched old screen-insensitive candidates
(111 Ironclad, 127 Silent) and generates 400 fresh candidates per character.
Fresh generation preserves the recipe distribution, uses seed base 9050000,
character offset 1000000, stride 1009, and a new fixture namespace. Seeds, IDs,
and state digests are checked for overlap. No failed generation is replaced.

Fresh candidates first receive the original H={1,4} screen (250,000 nodes and
10 seconds per H). All eligible fresh screens advance: both the disjoint set
and up to 400 ranked screen-insensitive rows per character, which exhausts
each fresh pool. Untouched old candidates use their existing screen eligibility.
All full-stage candidates receive H={1,2,4,8} with the original 2,000,000-node,
120-second per-H ceilings. Every completed disposition is retained, including
timeouts; old timeouts are never retried. The first Silent extension's four
sensitive rows remain ineligible under their original source restriction.

All seven source files listed in the protocol must be present in `results/`
with matching SHA-256 hashes. They are intentionally ignored by Git. Neither
source artifacts nor older protocols are overwritten. The original pilot
NO-GO and original v2 release failure remain historical outcomes.

## Commands from the repository root

Use the same Python/environment throughout the full oracle audit because
wall-time exclusions are hardware dependent. Preserve execution provenance.
Run at most one writer per output path. Interrupt only between checkpointed
rows when possible; an interrupted row without a disposition restarts.

```powershell
python scripts/controlled_horizon_expansion.py manifest --out results/controlled_h_v2_expansion_manifest.json
```

The manifest is already generated locally: 800/800 fresh candidates, zero
generation failures, 238 old candidates to audit, and 334 reusable eligible rows.
A separate two-fixture H1/H4 smoke (first fresh fixture per character) passed
exactness and prompt-invariance checks. Its output is diagnostic only and
is not silently imported into the production screen checkpoint.

Start with one checkpointed production-screen row and inspect it:

```powershell
python scripts/controlled_horizon_expansion.py screen --max-new-fixtures 1 --out results/controlled_h_v2_expansion_screen.json
```

After the concrete oracle workload is accepted, resume the full screen:

```powershell
python scripts/controlled_horizon_expansion.py screen --out results/controlled_h_v2_expansion_screen.json
```

The full stage refuses an incomplete or mismatched screen. Its first invocation
can likewise be limited to one new row:

```powershell
python scripts/controlled_horizon_expansion.py full --screen-audit results/controlled_h_v2_expansion_screen.json --max-new-fixtures 1 --out results/controlled_h_v2_expansion_full.json
```

Inspect the complete per-H disposition before resuming with the same command
without `--max-new-fixtures`. Node/time failures remain completed rows.
The runner rejects duplicate rows, foreign or changed recipes, altered source
bindings, changed budgets, and inconsistent completion metadata before new work.

After every selected full-stage candidate has a disposition:

```powershell
python scripts/controlled_horizon_expansion.py release --screen-audit results/controlled_h_v2_expansion_screen.json --full-audit results/controlled_h_v2_expansion_full.json --out results/controlled_h_v2_expansion_release_audit.json --fixtures-out results/controlled_h_v2_expansion_release_fixtures.json
```

Release reranks the union of eligible old and newly audited rows using the
new namespace and fixed character/sensitivity quotas. It emits exactly 504
unique fixtures if all gates pass, otherwise zero. Inspect every disposition,
source composition, prompt/oracle gate, exclusion, and quota before treating
the release as usable. A release GO alone never authorizes model inference.

## Workload and limits

The fresh screen has 800 candidates; full audit has at most 1,038 candidates
(800 fresh plus 238 old). Summing configured per-H ceilings gives 4.44 CPU hours
for screening and 138.4 CPU hours for full search, excluding overhead. These
are conservative budget arithmetic, not measured runtimes or guarantees of
wall time; failures can terminate rows early. Exact gating still may fail to
supply 63 sensitive and 189 controls per character. A shortfall requires a new
disclosed decision, not selective additional candidates under this freeze.

No full expansion audit, cluster job, or model query was launched when this
runbook and runner were prepared. The tiny oracle smoke and mock-only
screen/full/release exercise are recorded in the experiment log.
