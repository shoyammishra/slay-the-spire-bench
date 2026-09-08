# Automatic bounded confirmation queue

On 2026-09-08 the operator requested automatic successive 32-query batches.
This supersedes the manual-submission requirement in the batch runbook. It
does not change either frozen experiment, prompts, model, scoring, batch
launcher, query order, per-query retry policy, or statistical gates.

`scripts/confirmatory_autoqueue.py` is a lightweight login-node supervisor.
It polls only the exact recorded job ID every 30 seconds. A successor requires
the predecessor to be `COMPLETED` with exit `0:0`, a fully validated canonical
checkpoint, a passing continuation smoke, zero execution failures, no active
session, exactly one additional finalized session, and 1..32 additional rows.
Thus a zero-row deadline stop or unexpected manual interleaving stops the
queue. It does not select batches based on observed model quality.

The starting job is 10613, the first 32-query batch. Before that job the
validated operator-reported state was two total responses and one finalized
amended session. The supervisor expects that job to advance those counters,
then submits one successor at a time, stopping at 2,016 total responses or
the declared maximum of 64 new job submissions. The job cap is a safety
ceiling, not a runtime forecast or a request to execute unused work. If all
batches add 32 rows, only 62 successors after job 10613 are needed. Partial
batches can consume the cap before completion; it never raises its own cap.

## Start on the CSIS login node

Keep job 10613 running. Do not submit additional batches manually once this
supervisor starts. The existing locked launcher rejects duplicate active jobs
as another safeguard. Updating the checkout is safe here because the frozen
runner, launcher, and their source receipts are unchanged.

```bash
cd ~/slay-the-spire-bench
git pull --ff-only origin main
eval "$(conda shell.bash hook)"
conda activate slaybench08
export CONDA_SH="$(conda info --base)/etc/profile.d/conda.sh"
mkdir -p results

nohup python -u scripts/confirmatory_autoqueue.py \
  --after-job 10613 --after-index 2 --after-sessions 1 \
  --max-jobs 64 --authorize-submit \
  >> results/controlled_h_v2_confirmatory_autoqueue.log 2>&1 < /dev/null &
```

`nohup` detaches this supervisor from normal SSH hangups. It uses no GPU on
the login node. The existing detached Slurm batches perform model inference.
No Slurm command was executed during local implementation/testing; the first
automatic handoff remains an operational verification step.

Watch its decisions:

```bash
tail -F results/controlled_h_v2_confirmatory_autoqueue.log
```

Ctrl+C stops watching, not the supervisor. To stop further submissions:

```bash
touch results/controlled_h_v2_confirmatory_autoqueue.stop
```

The stop file does not cancel a submitted job or retract an in-flight
submission. The supervisor stops at its next check and preserves the current
job ID and all evidence. A normal process interruption can be resumed using
the same start command and arguments while its saved phase is `waiting`.
Other terminal phases require inspection; do not delete or edit the state to
force a restart. A second simultaneous supervisor is rejected by a file lock.

## Durable submission accounting

Ignored `results/controlled_h_v2_confirmatory_autoqueue.json` binds the source
hash, frozen amendment digest, canonical journal, initial job/baseline, job
budget, and all confirmed successor job IDs. Before calling `sbatch`, it saves
`submit_pending` and a unique scheduler comment tag. A timeout, malformed
receipt, or crash before recording the returned job ID leaves that marker.
The supervisor refuses to resubmit automatically; an operator must reconcile
the tag with Slurm accounting. Waiting-job failures and source drift also
stop continuation. No job cancellation, query retry, requeue, or automatic
budget increase is performed.

Only declared environment variables are exported to successor jobs. Keep
the queue state/log alongside the original parent, batch journal, sessions,
rows, and serving receipts when retrieving final evidence. They remain ignored.
