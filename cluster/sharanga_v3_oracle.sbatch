#!/bin/bash
# v3 held-out controlled-H fixtures: exact-oracle audit. Model-free, CPU only.
# Protocol: configs/controlled_h_v3_heldout.json (frozen digest in scripts/controlled_horizon_v3.py).
#
# Sharanga CPU QOS forbids 1-CPU array tasks (compute: >=4 CPUs, <=7 jobs; big_compute:
# >=128 CPUs, <=8 jobs), so one job runs shards [SHARD_START, SHARD_END) with one worker
# per allocated CPU. Each shard checkpoints after every fixture: resubmitting the same range
# resumes; finished dispositions (incl. budget failures) are never recomputed.
#
# Build the manifest ONCE on the login node first:
#   python scripts/controlled_horizon_v3.py manifest
# Smoke (8 shards on compute), then production ranges on big_compute, e.g.:
#   sbatch --partition=compute --cpus-per-task=8 --mem=32G \
#          --export=ALL,SHARD_START=0,SHARD_END=8 cluster/sharanga_v3_oracle.sbatch
#   sbatch --export=ALL,SHARD_START=8,SHARD_END=200 cluster/sharanga_v3_oracle.sbatch
# Merge + release after every shard is complete:
#   python scripts/controlled_horizon_v3.py merge --shards 800
#   python scripts/controlled_horizon_v3.py release
#SBATCH --job-name=slay_v3_oracle
#SBATCH --partition=big_compute
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=192
#SBATCH --mem=0
#SBATCH --time=48:00:00
#SBATCH --output=results/controlled_h_v3_logs/oracle_%j.out

set -eo pipefail
cd "${SLURM_SUBMIT_DIR}"
source "${HOME}/miniconda3/etc/profile.d/conda.sh"
conda activate "${CONDA_ENV:-slaybench08}"
set -u
export PYTHONUNBUFFERED=1 PYTHONIOENCODING=utf-8
readonly SHARDS="${V3_SHARDS:-800}"
readonly START="${SHARD_START:?set SHARD_START}" END="${SHARD_END:?set SHARD_END}"
readonly WORKERS="${SLURM_CPUS_PER_TASK:-1}"
(( 0 <= START && START < END && END <= SHARDS )) || { echo "bad shard range"; exit 2; }
readonly LOGDIR="results/controlled_h_v3_logs/job_${SLURM_JOB_ID}"
mkdir -p "$LOGDIR"
echo "node=$(hostname -s) shards=[${START},${END})/${SHARDS} workers=${WORKERS} start=$(date -Is)"

run_shard() {
  local s="$1"
  # stderr = per-fixture progress + /usr/bin/time peak RSS; one log per shard.
  /usr/bin/time -v python scripts/controlled_horizon_v3.py shard --shard "$s" --shards "$SHARDS" \
    > "${LOGDIR}/shard_${s}.log" 2>&1 || echo "shard ${s} FAILED (see ${LOGDIR}/shard_${s}.log)"
}
export -f run_shard
export SHARDS LOGDIR
seq "$START" $((END - 1)) | xargs -P "$WORKERS" -I{} bash -c 'run_shard {}'
echo "end=$(date -Is)"
grep -h "Maximum resident" "${LOGDIR}"/shard_*.log | sort -k6 -n | tail -1
