#!/bin/bash
# cluster/turn_combat_silent.sbatch — Silent turn + combat (the Silent
# counterparts to turn_combat.sbatch; synergy already loops both characters,
# so only turn/combat/run are Silent-specific). n=20 each, 5 seeds for
# mean+/-std, both prompt formats. Seeds spaced 1000 apart (see turn_combat
# .sbatch header for the why). Writes results/qwen2.5-7b_silent_<fmt>_seed*.json.
# Submit from the repo root:
#     sbatch cluster/turn_combat_silent.sbatch
#SBATCH --job-name=slay_turncombat_silent
#SBATCH --partition=gpu-1day
#SBATCH --gres=gpu:a100-80gb:1
#SBATCH --time=08:00:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --output=slay_turncombat_silent_%j.out
#SBATCH --error=slay_turncombat_silent_%j.err

cd "${SLURM_SUBMIT_DIR}"
source /nfs_home/software/miniconda/etc/profile.d/conda.sh
conda activate "${CONDA_ENV:-slaybench}"   # CONDA_ENV=slaybench08 for the qwen3 (vLLM 0.8.x) stack
export HF_HOME=~/scratch/hf_cache

source cluster/lib.sh
start_vllm
wait_for_vllm

for FMT in structured raw; do
  echo "=== Silent turn+combat, format=${FMT} ==="
  python run_benchmark.py --provider local --base-url "${BASE_URL}" \
      --model "${SERVED_NAME}" --character silent \
      --only turn combat --n-turn 20 --n-combat 20 \
      --seeds 42 1042 2042 3042 4042 \
      --format "${FMT}"
done

echo "=== Silent turn+combat done ==="
