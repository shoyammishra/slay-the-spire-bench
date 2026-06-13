#!/bin/bash
# cluster/synergy.sbatch — STEP 3: synergy across both characters and formats,
# 5 seeds for error bars (20 hand-crafted fixtures/character). Synergy is one
# light call per sample, so this is cheap. Submit from the repo root:
#     sbatch cluster/synergy.sbatch
#SBATCH --job-name=slay_synergy
#SBATCH --partition=gpu-short
#SBATCH --gres=gpu:a100-80gb:1
#SBATCH --time=06:00:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --output=slay_synergy_%j.out
#SBATCH --error=slay_synergy_%j.err

cd "${SLURM_SUBMIT_DIR}"
source /nfs_home/software/miniconda/etc/profile.d/conda.sh
conda activate "${CONDA_ENV:-slaybench}"   # CONDA_ENV=slaybench08 for the qwen3 (vLLM 0.8.x) stack
export HF_HOME=~/scratch/hf_cache

source cluster/lib.sh
start_vllm
wait_for_vllm

for CHAR in ironclad silent; do
  for FMT in structured raw; do
    echo "=== synergy, character=${CHAR}, format=${FMT} ==="
    python run_benchmark.py --provider local --base-url "${BASE_URL}" \
        --model "${SERVED_NAME}" \
        --only synergy --n-synergy 20 \
        --character "${CHAR}" \
        --seeds 42 1042 2042 3042 4042 \
        --format "${FMT}"
  done
done

echo "=== synergy done ==="
