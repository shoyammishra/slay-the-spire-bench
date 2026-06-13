#!/bin/bash
# cluster/turn_combat.sbatch — STEP 2: re-baseline turn + combat (pre-audit
# numbers are stale). n=20 each, 5 seeds for mean+/-std, both prompt formats.
# Seeds are spaced 1000 apart: per-sample seeds are contiguous ranges from the
# base (base..base+n-1, +100/+200/+300 per dimension), so adjacent bases like
# 42,43 share 19/20 samples -> fake std. Spacing >=1000 keeps every window and
# dimension offset disjoint; 1000 is a multiple of 20 so each base still covers
# all 20 synergy fixtures once.
# Submit from the repo root:
#     sbatch cluster/turn_combat.sbatch
#SBATCH --job-name=slay_turncombat
#SBATCH --partition=gpu-1day
#SBATCH --gres=gpu:a100-80gb:1
#SBATCH --time=08:00:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --output=slay_turncombat_%j.out
#SBATCH --error=slay_turncombat_%j.err

cd "${SLURM_SUBMIT_DIR}"
source /nfs_home/software/miniconda/etc/profile.d/conda.sh
conda activate "${CONDA_ENV:-slaybench}"   # CONDA_ENV=slaybench08 for the qwen3 (vLLM 0.8.x) stack
export HF_HOME=~/scratch/hf_cache

source cluster/lib.sh
start_vllm
wait_for_vllm

for FMT in structured raw; do
  echo "=== turn+combat, format=${FMT} ==="
  python run_benchmark.py --provider local --base-url "${BASE_URL}" \
      --model "${SERVED_NAME}" \
      --only turn combat --n-turn 20 --n-combat 20 \
      --seeds 42 1042 2042 3042 4042 \
      --format "${FMT}"
done

echo "=== turn+combat done ==="
