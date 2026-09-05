#!/bin/bash
# Download and verify the exact Qwen3-32B revision frozen for the controlled-H pilot.
# Run on the CSIS login node from the repository root. This performs network and
# storage I/O only; it does not start a model server or consume a GPU.
set -euo pipefail

readonly MODEL_REPO="Qwen/Qwen3-32B"
readonly MODEL_REVISION="9216db5781bf21249d130ec9da846c4624c16137"
readonly PILOT_ENV="${CONDA_ENV:-slaybench08}"
export HF_HOME="${HF_HOME:-${HOME}/scratch/hf_cache}"
unset HF_HUB_OFFLINE || true

if ! command -v conda >/dev/null 2>&1; then
  if [[ -n "${CONDA_SH:-}" && -f "${CONDA_SH}" ]]; then
    source "${CONDA_SH}"
  else
    echo "ERROR: conda is unavailable. Load its module or export CONDA_SH to conda.sh."
    exit 1
  fi
fi
eval "$(conda shell.bash hook)"
if ! conda env list | awk '{print $1}' | grep -Fxq "${PILOT_ENV}"; then
  echo "ERROR: Conda environment '${PILOT_ENV}' is absent."
  echo "Create it first with: bash cluster/setup_vllm08.sh"
  exit 1
fi
conda activate "${PILOT_ENV}"

mkdir -p "${HF_HOME}"
python -m pip install --quiet "huggingface_hub>=0.30,<1"

echo "Downloading ${MODEL_REPO} at immutable revision ${MODEL_REVISION}"
if command -v hf >/dev/null 2>&1; then
  hf download "${MODEL_REPO}" --revision "${MODEL_REVISION}"
else
  huggingface-cli download "${MODEL_REPO}" --revision "${MODEL_REVISION}"
fi

python cluster/verify_prefetch.py "${MODEL_REPO}" "${MODEL_REVISION}"
echo "Pinned Qwen3-32B weights are complete and ready for an offline Slurm job."
