#!/bin/bash
# cluster/run_level_qwen3.sbatch — MINIMAL run-level for a REASONING model.
# Submit from the repo root:
#     CONDA_ENV=slaybench08 HF_REPO=Qwen/Qwen3-32B SERVED_NAME=qwen3-32b \
#       sbatch --export=ALL cluster/run_level_qwen3.sbatch
#
# WHY THIS EXISTS (smoke job 7569, 2026-06-14):
#   Qwen3-32B serves at ~21.6 tok/s on one A100 (vs the 7B's ~82) AND emits a
#   long <think>...</think> block on EVERY call. A single run-level run is
#   dozens-to-hundreds of stateful calls -> ~1-3 HOURS per run. The smoke's ONE
#   run-level sample alone blew through a 2-hour wall without finishing.
#   => The paper-grade run_level.sbatch (n=20 x 5 seeds x 2 fmt = 200 runs ≈
#      weeks of A100 time) is INFEASIBLE for a reasoning model. This file instead
#      collects a single ILLUSTRATIVE data point: n=3, 1 seed, 1 format. Even
#      this can take most of the wall, hence gpu-3day (72h cap) + --time=24:00:00.
#
#   Reported as a qualitative point ("reasoning-model run-level is compute-
#   prohibitive at scale; here are n=3 illustrative runs"), NOT as a mean±std
#   matrix cell. Paper-grade run-level data stays the non-reasoning Qwen2.5-7B.
#
# Partial results are saved on disk even if killed at the wall (harness
# partial-saves on any error); re-submit to resume more runs into the same JSON.
# QOS: this account's GPU QOS is `test-gpu` (MaxWall 7 days, gres/gpu=4). The
# default `normal` QOS has no GPU wall budget for a 24h request, so a bare submit
# is rejected with QOSMaxWallDurationPerJobLimit (job 7572, 2026-06-14). Pin the
# GPU QOS explicitly. (Allowed QOS for this assoc: bigmem, cpu-short, normal,
# test-gpu — only test-gpu grants both a long wall and a GPU.)
#SBATCH --job-name=slay_run_qwen3
#SBATCH --partition=gpu-3day
#SBATCH --qos=test-gpu
#SBATCH --gres=gpu:a100-80gb:1
#SBATCH --time=24:00:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --output=slay_run_qwen3_%j.out
#SBATCH --error=slay_run_qwen3_%j.err

cd "${SLURM_SUBMIT_DIR}"
source /nfs_home/software/miniconda/etc/profile.d/conda.sh
conda activate "${CONDA_ENV:-slaybench08}"   # reasoning model => vLLM 0.8.x env
export HF_HOME=~/scratch/hf_cache

source cluster/lib.sh
start_vllm
wait_for_vllm

# Single illustrative point: n=3, one seed, structured only.
echo "=== qwen3 run-level (illustrative, n=3, seed=42, structured) ==="
time python run_benchmark.py --provider local --base-url "${BASE_URL}" \
    --model "${SERVED_NAME}" \
    --only run --n-run 3 \
    --seed 42 \
    --format structured

echo "=== qwen3 run-level done; check results/${SERVED_NAME}_structured_seed42.* ==="
