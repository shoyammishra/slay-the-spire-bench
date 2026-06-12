#!/bin/bash
# cluster/setup.sh — one-time environment setup on the CSIS cluster.
# Run ONCE from the repo root on the login node:
#     bash cluster/setup.sh
#
# Creates a conda env named 'slaybench' with vLLM (the model server) and
# matplotlib (the benchmark's chart output). The benchmark's --provider local
# adapter itself only uses the Python stdlib, so no groq/openai packages are
# needed here.
set -e

CONDA_SH=/nfs_home/software/miniconda/etc/profile.d/conda.sh
if [ ! -f "${CONDA_SH}" ]; then
  echo "ERROR: ${CONDA_SH} not found. Check 'module avail' for the miniconda path"
  echo "       and update CONDA_SH in this script + the sbatch files."
  exit 1
fi
source "${CONDA_SH}"

if ! conda env list | grep -q '^slaybench '; then
  conda create -y -n slaybench python=3.11
fi
conda activate slaybench

pip install --upgrade pip
# Pin to CUDA 12.x compatible versions (cluster driver = CUDA 12.8 / version 12080).
# vLLM 0.22+ requires CUDA 13.x — pin to 0.6.x which supports CUDA 12.4/12.8.
# transformers must stay on 4.x — 5.x removed all_special_tokens_extended which vLLM 0.6.6 calls.
pip install torch==2.5.1 --index-url https://download.pytorch.org/whl/cu124
pip install vllm==0.6.6 "transformers==4.47.1" matplotlib

# Keep large model weights off the 300 GB home quota — scratch is 1 TB.
mkdir -p ~/scratch/hf_cache

echo
echo "Setup complete."
echo "  Activate:        conda activate slaybench"
echo "  HF cache (once per shell, also set inside every sbatch):"
echo "                   export HF_HOME=~/scratch/hf_cache"
echo "  Next:            sbatch cluster/smoke.sbatch   (from the repo root)"
