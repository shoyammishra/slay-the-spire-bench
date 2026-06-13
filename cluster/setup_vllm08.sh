#!/bin/bash
# cluster/setup_vllm08.sh — SECOND env for the qwen3-32b reasoning matrix.
# Run ONCE from the repo root on the login node:
#     bash cluster/setup_vllm08.sh
#
# The working stack (slaybench: vLLM 0.6.6) CANNOT serve the qwen3 architecture.
# This builds a SEPARATE conda env 'slaybench08' on vLLM 0.8.x so the proven
# 0.6.6 env stays intact as a fallback. To use it, point the sbatch jobs at this
# env by exporting CONDA_ENV=slaybench08 (see lib.sh / the sbatch CONDA_ENV hook).
#
# ⚠️ CUDA-12.8 COMPAT IS UNVERIFIED. The cluster driver is CUDA 12.8 (12080).
# vLLM 0.8.x ships built against cu124 wheels (forward-compatible with a 12.8
# driver in practice), but this must be smoke-tested before the real matrix:
#     CONDA_ENV=slaybench08 HF_REPO=Qwen/Qwen3-32B SERVED_NAME=qwen3-32b \
#       sbatch --export=ALL cluster/smoke.sbatch
# Read its vllm_<jobid>.log — if it dies at CUDA init, drop to 0.8.3/0.8.4 or
# rebuild torch against cu128. vLLM 0.22+ needs CUDA 13.x and will NOT work here.
set -e

CONDA_SH=/nfs_home/software/miniconda/etc/profile.d/conda.sh
if [ ! -f "${CONDA_SH}" ]; then
  echo "ERROR: ${CONDA_SH} not found. Check 'module avail' for the miniconda path."
  exit 1
fi
source "${CONDA_SH}"

if ! conda env list | grep -q '^slaybench08 '; then
  conda create -y -n slaybench08 python=3.11
fi
conda activate slaybench08

pip install --upgrade pip
# vLLM 0.8.5.post1 is the last 0.8.x; it adds Qwen3ForCausalLM and pulls a
# compatible torch (2.6.x, cu124 wheels — forward-compatible with the 12.8 driver).
# Let vLLM resolve its own torch/transformers rather than pinning them by hand
# (0.8.x needs transformers>=4.51 for Qwen3 — the 4.47.1 pin from the 0.6.6 env
# would BREAK Qwen3 here).
pip install "vllm==0.8.5.post1" matplotlib

# Share the same weight cache as the 0.6.6 env — weights are stack-independent.
mkdir -p ~/scratch/hf_cache

echo
echo "Setup complete (env: slaybench08, vLLM 0.8.5.post1)."
echo "  Smoke-test Qwen3 FIRST (CUDA-12.8 compat is unverified):"
echo "    CONDA_ENV=slaybench08 HF_REPO=Qwen/Qwen3-32B SERVED_NAME=qwen3-32b \\"
echo "      sbatch --export=ALL cluster/smoke.sbatch"
echo "  Then read vllm_<jobid>.log before launching the full matrix."
