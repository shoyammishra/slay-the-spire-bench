#!/bin/bash
# cluster/synergy_models.sbatch — synergy for the two extra open-source models
# (Llama-3.1-8B, Mistral-7B), BOTH characters, BOTH formats, 5 seeds for error
# bars (20 hand-crafted fixtures/character). One light call per sample, so cheap.
# The Groq pilot synergy numbers for these are STALE (synergy fixtures changed in
# the 2026-06-11 batch); this re-runs them self-hosted under the post-audit harness.
# Writes results/<served>_{,_silent}_<fmt>_seed*.json.
#
# Submit ONE model per job by overriding the model env vars:
#   # Llama-3.1-8B  (vLLM 0.6.6 / slaybench; GATED -> HF_TOKEN required):
#   HF_TOKEN=hf_xxx CONDA_ENV=slaybench HF_REPO=meta-llama/Llama-3.1-8B-Instruct \
#     SERVED_NAME=llama-3.1-8b sbatch --export=ALL cluster/synergy_models.sbatch
#   # Mistral-7B  (MistralForCausalLM -> vLLM 0.6.6 / slaybench; NOT gated, no HF_TOKEN):
#   CONDA_ENV=slaybench HF_REPO=mistralai/Mistral-7B-Instruct-v0.3 \
#     SERVED_NAME=mistral-7b sbatch --export=ALL cluster/synergy_models.sbatch
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
conda activate "${CONDA_ENV:-slaybench}"   # both models run on vLLM 0.6.6 / slaybench
export HF_HOME=~/scratch/hf_cache
# Llama-3.1-8B is GATED -> needs HF_TOKEN; Mistral-7B is NOT gated.
if [[ "${HF_REPO:-}" == meta-llama/* && -z "${HF_TOKEN:-}" ]]; then
  echo "ERROR: HF_REPO is a gated meta-llama model but HF_TOKEN is not set. See header."
  exit 1
fi

source cluster/lib.sh
start_vllm
wait_for_vllm

# Both the 8B and the 7B are fast on vLLM 0.6.6; keep the 600s ceiling as cheap
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
