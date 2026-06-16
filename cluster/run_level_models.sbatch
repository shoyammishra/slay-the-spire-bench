#!/bin/bash
# cluster/run_level_models.sbatch — run-level (the most expensive dimension) for the
# two extra open-source models (Llama-3.1-8B, Mistral-7B), BOTH characters, BOTH
# formats, n=20, 5 seeds. Run LAST, after turn_combat_models + synergy_models prove
# the pipeline for the model. The Groq pilot run-level numbers for these never
# existed / are invalid; this is the first valid run-level pass under the post-audit
# harness. Writes results/<served>_{,_silent}_<fmt>_seed*.json.
#
# Calibrated from the 7B run_level.sbatch (~82 tok/s, 1 run ~60-90 s, n=20 x 2 fmt x
# 5 seeds ~4 h/character). Mistral-7B runs at roughly 7B speed, so 12h covers both
# characters of either model comfortably (partial-save resumes into the same JSON if
# it ever runs long). Wall stays under the gpu-1day 24h QOS cap.
#
# Submit ONE model per job by overriding the model env vars:
#   # Llama-3.1-8B  (vLLM 0.6.6 / slaybench; GATED -> HF_TOKEN required):
#   HF_TOKEN=hf_xxx CONDA_ENV=slaybench HF_REPO=meta-llama/Llama-3.1-8B-Instruct \
#     SERVED_NAME=llama-3.1-8b sbatch --export=ALL cluster/run_level_models.sbatch
#   # Mistral-7B  (MistralForCausalLM -> vLLM 0.6.6 / slaybench; NOT gated, no HF_TOKEN):
#   CONDA_ENV=slaybench HF_REPO=mistralai/Mistral-7B-Instruct-v0.3 \
#     SERVED_NAME=mistral-7b sbatch --export=ALL cluster/run_level_models.sbatch
#SBATCH --job-name=slay_run_models
#SBATCH --partition=gpu-1day
#SBATCH --gres=gpu:a100-80gb:1
#SBATCH --time=12:00:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --output=slay_run_models_%j.out
#SBATCH --error=slay_run_models_%j.err

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
    echo "=== run-level, model=${SERVED_NAME}, character=${CHAR}, format=${FMT} ==="
    python run_benchmark.py --provider local --base-url "${BASE_URL}" \
        --model "${SERVED_NAME}" --character "${CHAR}" \
        --only run --n-run 20 \
        --seeds 42 1042 2042 3042 4042 \
        --format "${FMT}"
  done
done

echo "=== run-level (${SERVED_NAME}, both characters) done ==="
