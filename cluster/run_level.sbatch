#!/bin/bash
# cluster/run_level.sbatch — STEP 4: run-level (most expensive dimension).
# Run LAST, once smoke + turn_combat + synergy have proven the pipeline.
# Submit from the repo root:  sbatch cluster/run_level.sbatch
#
# CALIBRATED from smoke test (2026-06-13, Qwen2.5-7B, A100 80GB):
#   gen throughput ~82 tok/s, prompt ~700 tok/s, vLLM startup ~3.5 min
#   1 run ≈ 22 LLM calls × ~3 s/call ≈ 60-90 s
#   n-run=5  × 2 formats            ≈  18 min total  → gpu-short is fine
#   n-run=20 × 2 formats × 5 seeds  ≈ 4.0 h total   → gpu-1day with --time=06:00:00
#
# CURRENT SETTING: validation pass (n=5, seed=42, ~18 min).
# To scale to paper-grade, swap the SBATCH lines and benchmark call below
# to the PAPER-GRADE block in the comments.
#
# Further scale-up options (after Act-1 run-level is solid):
#   - multi-act:  --acts 3   (Acts 1->3)
#   - gpu-3day partition for very long multi-seed multi-act runs

# --- VALIDATION PASS (~18 min) — commented out; using paper-grade below ---
##SBATCH --job-name=slay_run
##SBATCH --partition=gpu-short
##SBATCH --gres=gpu:a100-80gb:1
##SBATCH --time=01:00:00
##SBATCH --ntasks=1
##SBATCH --cpus-per-task=8
##SBATCH --mem=64G
##SBATCH --output=slay_run_%j.out
##SBATCH --error=slay_run_%j.err

# --- PAPER-GRADE PASS (~4 h) ---
# QOS wall caps (sacctmgr, 2026-06-13): gpu-1day=24h, gpu-short=8h, gpu-long=12h.
# 06:00:00 on gpu-1day is well within the cap. (An earlier 24:00:00 was rejected
# because it equals the cap exactly — stay strictly under it.)
#SBATCH --job-name=slay_run_paper
#SBATCH --partition=gpu-1day
#SBATCH --gres=gpu:a100-80gb:1
#SBATCH --time=06:00:00
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

# PAPER-GRADE PASS — n=20, 5 seeds
for FMT in structured raw; do
  echo "=== run-level paper, format=${FMT} ==="
  python run_benchmark.py --provider local --base-url "${BASE_URL}" \
      --model "${SERVED_NAME}" \
      --only run --n-run 20 \
      --seeds 42 43 44 45 46 \
      --format "${FMT}"
done

# VALIDATION PASS — n=5, single seed (kept for reference)
# for FMT in structured raw; do
#   echo "=== run-level, format=${FMT} ==="
#   python run_benchmark.py --provider local --base-url "${BASE_URL}" \
#       --model "${SERVED_NAME}" \
#       --only run --n-run 5 \
#       --seed 42 \
#       --format "${FMT}"
# done

echo "=== run-level done ==="
