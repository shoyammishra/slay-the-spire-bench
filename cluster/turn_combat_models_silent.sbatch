#!/bin/bash
# cluster/turn_combat_models_silent.sbatch — turn + combat for the extra open-source
# models (Llama-3.1-8B, Mistral-7B), SILENT ONLY, RAW format ONLY, n=20 each, 5 seeds for
# mean+/-std. Use this when Ironclad turn/combat (both formats) AND Silent structured are
# already collected for a model and only the Silent RAW half remains — avoids re-running
# everything else. (Set up for DeepSeek-R1-Distill, where structured finished but the job
# wall ran out before raw; resubmit on a fresh GPU allocation to finish just the raw cell.)
# Writes results/<served>_silent_raw_seed*.json.
#
# Seeds spaced 1000 apart (see turn_combat.sbatch header for the why).
#
# Submit ONE model per job by overriding the model env vars (the README pattern):
#   # Llama-3.1-8B  (vLLM 0.6.6 / slaybench; GATED -> HF_TOKEN required):
#   HF_TOKEN=hf_xxx CONDA_ENV=slaybench HF_REPO=meta-llama/Llama-3.1-8B-Instruct \
#     SERVED_NAME=llama-3.1-8b sbatch --export=ALL cluster/turn_combat_models_silent.sbatch
#   # Mistral-7B  (MistralForCausalLM -> vLLM 0.6.6 / slaybench; NOT gated, no HF_TOKEN):
#   CONDA_ENV=slaybench HF_REPO=mistralai/Mistral-7B-Instruct-v0.3 \
#     SERVED_NAME=mistral-7b sbatch --export=ALL cluster/turn_combat_models_silent.sbatch
#SBATCH --job-name=slay_turncombat_models_silent
#SBATCH --partition=gpu-1day
#SBATCH --gres=gpu:a100-80gb:1
#SBATCH --time=08:00:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --output=slay_turncombat_models_silent_%j.out
#SBATCH --error=slay_turncombat_models_silent_%j.err

cd "${SLURM_SUBMIT_DIR}"
source /nfs_home/software/miniconda/etc/profile.d/conda.sh
conda activate "${CONDA_ENV:-slaybench}"   # both models run on vLLM 0.6.6 / slaybench
export HF_HOME=~/scratch/hf_cache
# Llama-3.1-8B is GATED -> needs HF_TOKEN; Mistral-7B is NOT gated. Only hard-fail
# when serving the gated Llama without a token.
if [[ "${HF_REPO:-}" == meta-llama/* && -z "${HF_TOKEN:-}" ]]; then
  echo "ERROR: HF_REPO is a gated meta-llama model but HF_TOKEN is not set. See header."
  exit 1
fi

source cluster/lib.sh
start_vllm
wait_for_vllm

# Both the 8B and the 7B are fast on vLLM 0.6.6, so 300s would be fine; keep the 600s
# ceiling anyway as cheap insurance against an occasional long generation.
export LOCAL_TIMEOUT="${LOCAL_TIMEOUT:-600}"

echo "=== turn+combat, model=${SERVED_NAME}, character=silent, format=raw ==="
python run_benchmark.py --provider local --base-url "${BASE_URL}" \
    --model "${SERVED_NAME}" --character silent \
    --only turn combat --n-turn 20 --n-combat 20 \
    --seeds 42 1042 2042 3042 4042 \
    --format raw

echo "=== turn+combat (${SERVED_NAME}, silent raw only) done ==="
