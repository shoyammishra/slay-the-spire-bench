#!/bin/bash
# v3 held-out controlled-H fixtures: exact-oracle audit, one shard per array task.
# Model-free, CPU only. Protocol: configs/controlled_h_v3_heldout.json (frozen digest in
# scripts/controlled_horizon_v3.py). Each shard checkpoints after every fixture, so a
# resubmitted task resumes; completed dispositions (incl. budget failures) are never retried.
#
# Build the manifest ONCE on the login node first:
#   python scripts/controlled_horizon_v3.py manifest
# Smoke (one shard), then the rest, throttled for the shared account:
#   sbatch --array=0 cluster/sharanga_v3_oracle.sbatch
#   sbatch --array=1-799%300 cluster/sharanga_v3_oracle.sbatch
# Merge + release after every shard is complete:
#   python scripts/controlled_horizon_v3.py merge --shards 800
#   python scripts/controlled_horizon_v3.py release
#SBATCH --job-name=slay_v3_oracle
#SBATCH --partition=big_compute
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=6G
#SBATCH --time=24:00:00
#SBATCH --output=results/controlled_h_v3_logs/oracle_%A_%a.out

set -eo pipefail
cd "${SLURM_SUBMIT_DIR}"
source "${HOME}/miniconda3/etc/profile.d/conda.sh"
conda activate "${CONDA_ENV:-slaybench08}"
set -u
export PYTHONUNBUFFERED=1 PYTHONIOENCODING=utf-8
readonly SHARDS="${V3_SHARDS:-800}"
echo "node=$(hostname -s) shard=${SLURM_ARRAY_TASK_ID}/${SHARDS} start=$(date -Is)"
# stderr (per-fixture progress + /usr/bin/time's peak-RSS report) lands in the .out file.
/usr/bin/time -v python scripts/controlled_horizon_v3.py shard \
  --shard "${SLURM_ARRAY_TASK_ID}" --shards "${SHARDS}"
echo "end=$(date -Is)"
