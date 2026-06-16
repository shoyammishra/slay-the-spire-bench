#!/bin/bash
# cluster/synergy_models.sbatch — synergy for the two extra open-source models
# (Llama-3.1-8B, Gemma-3-12B), BOTH characters, BOTH formats, 5 seeds for error
# bars (20 hand-crafted fixtures/character). One light call per sample, so cheap.
# The Groq pilot synergy numbers for these are STALE (synergy fixtures changed in
# the 2026-06-11 batch); this re-runs them self-hosted under the post-audit harness.
# Writes results/<served>_{,_silent}_<fmt>_seed*.json.
#
# Submit ONE model per job by overriding the model env vars:
#   # Llama-3.1-8B  (vLLM 0.6.6 / slaybench; GATED -> HF_TOKEN):
#   HF_TOKEN=hf_xxx CONDA_ENV=slaybench HF_REPO=meta-llama/Llama-3.1-8B-Instruct \
#     SERVED_NAME=llama-3.1-8b sbatch --export=ALL cluster/synergy_models.sbatch
#   # Gemma-3-12B  (Gemma3ForCausalLM -> needs vLLM 0.8.x / slaybench08; GATED):
#   #   128k native context, so the lib.sh default --max-model-len 16384 works as-is.
#   HF_TOKEN=hf_xxx CONDA_ENV=slaybench08 HF_REPO=google/gemma-3-12b-it \
#     SERVED_NAME=gemma-3-12b sbatch --export=ALL cluster/synergy_models.sbatch
#SBATCH --job-name=slay_synergy_models
#SBATCH --partition=gpu-short
#SBATCH --gres=gpu:a100-80gb:1
#SBATCH --time=06:00:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --output=slay_synergy_models_%j.out
#SBATCH --error=slay_synergy_models_%j.err

cd "${SLURM_SUBMIT_DIR}"
source /nfs_home/software/miniconda/etc/profile.d/conda.sh
conda activate "${CONDA_ENV:-slaybench}"   # Llama -> slaybench (0.6.6); Gemma-3 -> slaybench08 (0.8.x)
export HF_HOME=~/scratch/hf_cache
if [ -z "${HF_TOKEN:-}" ]; then
  echo "ERROR: HF_TOKEN is not set (both models are gated). See header for submit syntax."
  exit 1
fi

source cluster/lib.sh
start_vllm
wait_for_vllm

# The 8B and the 12B (a non-reasoning model) are fast; keep the 600s ceiling as cheap
# insurance against an occasional long generation. Harmless here.
export LOCAL_TIMEOUT="${LOCAL_TIMEOUT:-600}"

for CHAR in ironclad silent; do
  for FMT in structured raw; do
    echo "=== synergy, model=${SERVED_NAME}, character=${CHAR}, format=${FMT} ==="
    python run_benchmark.py --provider local --base-url "${BASE_URL}" \
        --model "${SERVED_NAME}" --character "${CHAR}" \
        --only synergy --n-synergy 20 \
        --seeds 42 1042 2042 3042 4042 \
        --format "${FMT}"
  done
done

echo "=== synergy (${SERVED_NAME}, both characters) done ==="
