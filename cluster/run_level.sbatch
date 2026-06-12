#!/bin/bash
# cluster/run_level.sbatch — STEP 4: run-level (the most expensive dimension —
# hundreds of stateful calls per full run). Run this LAST, once smoke + the
# cheaper dims have proven the pipeline. Submit from the repo root:
#     sbatch cluster/run_level.sbatch
#
# Starts conservative: n=5 runs per format at a single seed. ONLY after you see
# from the smoke test's tok/s that there's time budget, scale up by:
#   - adding seeds:        --seeds 42 43 44 45 46   (auto-aggregates mean+/-std)
#   - raising --n-run      toward the paper target (>=20)
#   - moving to gpu-3day   (--partition=gpu-3day, --time=72:00:00) for headroom
#   - multi-act:           --acts 3   (Acts 1->3) once Act-1 run-level is solid
#SBATCH --job-name=slay_run
#SBATCH --partition=gpu-1day
#SBATCH --gres=gpu:a100-80gb:1
#SBATCH --time=24:00:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --output=slay_run_%j.out
#SBATCH --error=slay_run_%j.err

cd "${SLURM_SUBMIT_DIR}"
source /nfs_home/software/miniconda/etc/profile.d/conda.sh
conda activate slaybench
export HF_HOME=~/scratch/hf_cache

source cluster/lib.sh
start_vllm
wait_for_vllm

for FMT in structured raw; do
  echo "=== run-level, format=${FMT} ==="
  python run_benchmark.py --provider local --base-url "${BASE_URL}" \
      --model "${SERVED_NAME}" \
      --only run --n-run 5 \
      --seed 42 \
      --format "${FMT}"
done

echo "=== run-level done ==="
