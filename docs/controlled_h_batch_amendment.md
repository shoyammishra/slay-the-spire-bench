# Controlled-H batch execution amendment

> **Scheduling supersession, 2026-09-08:** the operator requested automatic
> successive batches. `controlled_h_autoqueue.md` documents the separate
> bounded supervisor. Historical manual-only instructions below remain as
> provenance; the frozen inference and batch execution contract is unchanged.


Date: 2026-09-08, after one completed response and before any continuation.
This is a disclosed post-smoke operational amendment, not the original
single-server freeze. The implementation and amendment must pass offline
validation before another model query. No new compute is authorized here.

The frozen amendment digest is
`ba73b91d23336923b8ea96f693df5cc836c0f13e51b4f2bd1b44bf311863caad`.
Original protocol digest remains `76bf7f91...de1da`; its source bytes and the
retrieved real response remain unchanged.

## Reason and scope

The original interactive allocation ended after a valid smoke response.
Its measured command elapsed time was 252.331 seconds; eight hours was a
resource request inherited from the pilot, not a defensible budget for all
2,016 queries. The same-server-only contract made restarting impossible.
Detached Slurm batches separate execution from an SSH session and allow
clean checkpoints between allocations.

Retain `configs/controlled_h_v2_confirmatory.json` and all original
`controlled_horizon*.py` files unchanged. The new
`scripts/confirmatory_batch.py` orchestration has its own hash-bound
`configs/controlled_h_v2_batch_amendment.json`. It references the original
frozen protocol and immutable retrieved parent evidence. The new script's
name keeps it outside the original implementation glob; this preserves the
old freeze while the amendment separately freezes the added implementation.

The one original response is global query 0 (Ironclad, H=4). Preserve its
original manifest, row, and server receipt bytes. Do not copy the response
into a replacement original report, change the old server contract, or draw
it again. The first amended batch starts at global query 1. The source
fixtures, query schedule, Qwen3 revision, serving arguments, temperature,
token budget, timeout, parser, scorer, effective-quality policy, and all
statistical gates stay exactly as originally frozen.

## Evidence chain and interruption policy

One canonical amendment journal references immutable, sequential sessions.
Each session owns a contiguous slice of the global query schedule and its
own pinned server-launch receipt. Analysis validates the original parent,
every session and row checksum, all prompt/scorer replays, and exact
contiguous coverage before applying the original statistical functions.
Missing, overlapping, substituted, or foreign response files are errors.
Report results under the amended protocol and disclose the one pre-amendment
response; do not label the amended run as fully governed by the old freeze.

An in-flight marker precedes every HTTP call. A saved row whose manifest
update was interrupted can be reconciled by replaying that same row. An
unsaved in-flight response cannot be queried again; explicit no-inference
resolution records an ambiguous zero-quality slot. Transport failures also
record zero and stop the batch. Such failures continue to suppress primary
claims under the original zero-execution-failure gate. Session changes may
occur only at audited boundaries. Preserve all failed attempts.

## Bounded execution

The detached launcher is `cluster/csis_controlled_h_confirmatory.sbatch`.
It checks the frozen chain before server startup, uses a dedicated job lock
to reject duplicate jobs, starts only its own server process group, and
cleans up that group at exit. Slurm logs and server receipts remain ignored.
The Python journal lock independently protects evidence writes.

The first amended-stack smoke permits one **new** scheduled query. Later
batches permit at most 32 new queries each, declared before execution. The
runner refuses to begin a query unless at least 900+180 seconds remain until
the supplied Slurm end time. This bounds unfinished work near the time limit;
it does not protect against preemption, hardware failure, or early cancellation.
There is no automatic resubmission, replacement sampling, or speculative
parallel model querying. Inspect every batch before submitting the next.

Session restarts can still expose numerical nondeterminism in GPU inference.
Pinned weights, package versions, arguments, and GPU class reduce this risk
but do not constitute cryptographic proof of identical loaded weights or
guaranteed bitwise determinism. Keep server logs and session provenance for
audit. Scheduling changes do not establish new statistical power or make the
single-model run a complete main-track evidence package.

## Operator commands after offline validation

Preserve the already retrieved and remote original evidence. Update the
cluster checkout only after the amendment is committed and transferred.
The initial preflight runs on the login node in `slaybench08`:

```bash
cd ~/slay-the-spire-bench
git pull --ff-only origin main
eval "$(conda shell.bash hook)"
conda activate slaybench08
export CONDA_SH="$(conda info --base)/etc/profile.d/conda.sh"
mkdir -p results
python scripts/confirmatory_batch.py preflight
```

Require parent verification and `next_global_index=1` before the first batch.
Submit the new one-query batch smoke after explicit execution authorization:

```bash
sbatch --export=CONF_MAX_NEW=1,CONDA_SH,CONDA_ENV,HF_HOME,HOME,PATH cluster/csis_controlled_h_confirmatory.sbatch
```

This `sbatch` job persists independently of the SSH connection. Inspect the
explicit returned job ID, its `results/slay_h_confirm_<job-id>.out/.err`, and
its analysis artifact. Require the next global index to become 2 with no
pending or execution-failure slot, and require the new row to be parsed,
schema-valid, legal, and nontruncated. Inspect server logs and resource use
before proceeding; this is not a second sample of query 0.
Only after that check, subsequent authorized batches use:

```bash
sbatch --export=CONF_MAX_NEW=32,CONDA_SH,CONDA_ENV,HF_HOME,HOME,PATH cluster/csis_controlled_h_confirmatory.sbatch
```

Never submit a second concurrent batch or an automatic chain. Original source
artifacts are still required alongside the new journal, all session reports
and `.rows` directories, and every session's server receipt. Retrieve that
whole evidence chain before independent final analysis. Do not commit it.

The original manifest will permanently remain at 1/2,016; it is historical
evidence, not the amended progress counter. Check amended progress with:

```bash
python scripts/confirmatory_batch.py preflight
python scripts/confirmatory_batch.py analyze --out results/controlled_h_v2_confirmatory_batch_analysis.json
```

If preflight reports an unresolved active session, inspect it first. The
explicit `python scripts/confirmatory_batch.py resolve` command performs
no inference: it reconciles an already saved response, finalizes a clean
interruption, or accounts an unsaved pending response as ambiguous. The last
case fails the original execution-integrity gate; do not request a replacement.

## Offline validation completed

All 218 tests and four standard mock pipelines passed. A full continuation
exercise covered 2,015 new mock slots in 64 sessions while retaining the one
original response; standalone source/row replay passed at 2,016 total slots.
Every new mock score matches the original frozen mock at that global index.
The original real evidence is unchanged, and no real amended session exists.
Independent security and source review passed. The first real detached job
is still required to test the amended Slurm/runtime path.
