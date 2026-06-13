#!/bin/bash
# cluster/run_level_silent.sbatch — Silent run-level (most expensive Silent
# dimension). Paper-grade n=20, 5 seeds, both formats. Run LAST, once Silent
# turn/combat have proven the pipeline for the character. Writes
# results/qwen2.5-7b_silent_<fmt>_seed*.json.
# Submit from the repo root:  sbatch cluster/run_level_silent.sbatch
#
# Calibrated identically to run_level.sbatch (Qwen2.5-7B, A100 80GB):
#   n-run=20 x 2 formats x 5 seeds ~= 4 h  -> gpu-1day --time=06:00:00
# QOS wall caps (sacctmgr, 2026-06-13): gpu-1day=24h, gpu-short=8h, gpu-long=12h.
# 06:00:00 on gpu-1day is well within the cap (24:00:00 == cap is rejected).
#SBATCH --job-name=slay_run_silent
#SBATCH --partition=gpu-1day
#SBATCH --gres=gpu:a100-80gb:1
#SBATCH --time=06:00:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --output=slay_run_silent_%j.out
#SBATCH --error=slay_run_silent_%j.err

cd "${SLURM_SUBMIT_DIR}"
source /nfs_home/software/miniconda/etc/profile.d/conda.sh
conda activate "${CONDA_ENV:-slaybench}"   # CONDA_ENV=slaybench08 for the qwen3 (vLLM 0.8.x) stack
export HF_HOME=~/scratch/hf_cache

source cluster/lib.sh
start_vllm
wait_for_vllm

for FMT in structured raw; do
  echo "=== Silent run-level paper, format=${FMT} ==="
  python run_benchmark.py --provider local --base-url "${BASE_URL}" \
      --model "${SERVED_NAME}" --character silent \
      --only run --n-run 20 \
      --seeds 42 1042 2042 3042 4042 \
      --format "${FMT}"
done

echo "=== Silent run-level done ==="
