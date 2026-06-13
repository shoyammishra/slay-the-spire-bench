#!/bin/bash
# cluster/smoke.sbatch — STEP 1: tiny full pass to prove the pipeline + measure
# tokens/sec before committing to the big runs. Submit from the repo root:
#     sbatch cluster/smoke.sbatch
#SBATCH --job-name=slay_smoke
#SBATCH --partition=gpu-short
#SBATCH --gres=gpu:a100-80gb:1
#SBATCH --time=02:00:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --output=slay_smoke_%j.out
#SBATCH --error=slay_smoke_%j.err

cd "${SLURM_SUBMIT_DIR}"
source /nfs_home/software/miniconda/etc/profile.d/conda.sh
conda activate "${CONDA_ENV:-slaybench}"   # CONDA_ENV=slaybench08 for the qwen3 (vLLM 0.8.x) stack
export HF_HOME=~/scratch/hf_cache

source cluster/lib.sh
start_vllm
wait_for_vllm

# Tiny counts across all four dimensions — just enough to exercise every code path.
time python run_benchmark.py --provider local --base-url "${BASE_URL}" \
    --model "${SERVED_NAME}" \
    --n-turn 2 --n-combat 1 --n-synergy 4 --n-run 1 \
    --format structured --seed 42

echo "=== smoke test done; check results/${SERVED_NAME}_structured_seed42.* ==="
