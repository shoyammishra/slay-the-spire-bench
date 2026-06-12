#!/bin/bash
# cluster/turn_combat.sbatch — STEP 2: re-baseline turn + combat (pre-audit
# numbers are stale). n=20 each, 5 seeds for mean+/-std, both prompt formats.
# Submit from the repo root:
#     sbatch cluster/turn_combat.sbatch
#SBATCH --job-name=slay_turncombat
#SBATCH --partition=gpu-1day
#SBATCH --gres=gpu:a100-80gb:1
#SBATCH --time=24:00:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --output=slay_turncombat_%j.out
#SBATCH --error=slay_turncombat_%j.err

cd "${SLURM_SUBMIT_DIR}"
source /nfs_home/software/miniconda/etc/profile.d/conda.sh
conda activate slaybench
export HF_HOME=~/scratch/hf_cache

source cluster/lib.sh
start_vllm
wait_for_vllm

for FMT in structured raw; do
  echo "=== turn+combat, format=${FMT} ==="
  python run_benchmark.py --provider local --base-url "${BASE_URL}" \
      --model "${SERVED_NAME}" \
      --only turn combat --n-turn 20 --n-combat 20 \
      --seeds 42 43 44 45 46 \
      --format "${FMT}"
done

echo "=== turn+combat done ==="
