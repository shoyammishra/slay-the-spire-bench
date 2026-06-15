#!/bin/bash
# cluster/turn_combat_models.sbatch — turn + combat re-baseline for the two extra
# open-source models (Llama-3.1-8B, Gemma-2-9B), BOTH characters, BOTH formats,
# n=20 each, 5 seeds for mean+/-std. The Groq pilot numbers for these are STALE
# (predate the 2026-06-10..12 engine/instrument fix batches); this re-runs them
# self-hosted under the post-audit harness. Re-running llama also restores a 2nd
# open-source FAMILY (Llama vs Qwen); Gemma adds a 3rd (Google).
# Writes results/<served>_{,_silent}_<fmt>_seed*.json.
#
# Seeds spaced 1000 apart (see turn_combat.sbatch header for the why).
#
# Submit ONE model per job by overriding the model env vars (the README pattern):
#   # Llama-3.1-8B  (vLLM 0.6.6 / slaybench; GATED -> HF_TOKEN):
#   HF_TOKEN=hf_xxx CONDA_ENV=slaybench HF_REPO=meta-llama/Llama-3.1-8B-Instruct \
#     SERVED_NAME=llama-3.1-8b sbatch --export=ALL cluster/turn_combat_models.sbatch
#   # Gemma-2-9B  (Gemma2ForCausalLM -> vLLM 0.6.6 / slaybench; GATED):
#   HF_TOKEN=hf_xxx CONDA_ENV=slaybench HF_REPO=google/gemma-2-9b-it \
#     SERVED_NAME=gemma-2-9b sbatch --export=ALL cluster/turn_combat_models.sbatch
#SBATCH --job-name=slay_turncombat_models
#SBATCH --partition=gpu-1day
#SBATCH --gres=gpu:a100-80gb:1
#SBATCH --time=08:00:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --output=slay_turncombat_models_%j.out
#SBATCH --error=slay_turncombat_models_%j.err

cd "${SLURM_SUBMIT_DIR}"
source /nfs_home/software/miniconda/etc/profile.d/conda.sh
conda activate "${CONDA_ENV:-slaybench}"   # both models run on vLLM 0.6.6 / slaybench
export HF_HOME=~/scratch/hf_cache
# Both models are GATED on HuggingFace -> HF_TOKEN must be exported at submit time.
if [ -z "${HF_TOKEN:-}" ]; then
  echo "ERROR: HF_TOKEN is not set (both models are gated). See header for submit syntax."
  exit 1
fi

source cluster/lib.sh
start_vllm
wait_for_vllm

# Both the 8B and the 9B are fast on vLLM 0.6.6, so 300s would be fine; keep the 600s
# ceiling anyway as cheap insurance against an occasional long generation. (Same knob
# the reasoning-model jobs need, harmless here.)
export LOCAL_TIMEOUT="${LOCAL_TIMEOUT:-600}"

for CHAR in ironclad silent; do
  for FMT in structured raw; do
    echo "=== turn+combat, model=${SERVED_NAME}, character=${CHAR}, format=${FMT} ==="
    python run_benchmark.py --provider local --base-url "${BASE_URL}" \
        --model "${SERVED_NAME}" --character "${CHAR}" \
        --only turn combat --n-turn 20 --n-combat 20 \
        --seeds 42 1042 2042 3042 4042 \
        --format "${FMT}"
  done
done

echo "=== turn+combat (${SERVED_NAME}, both characters) done ==="
