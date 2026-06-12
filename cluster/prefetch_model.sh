#!/bin/bash
# cluster/prefetch_model.sh — OPTIONAL. Download model weights on the LOGIN node.
#
# Use this only if the GPU compute nodes have no outbound internet (common on
# locked-down clusters). The login node has internet (you cloned the repo with
# it), so pre-pull the weights into the shared HF cache here; the sbatch jobs
# then read them offline. Downloading is I/O, not compute, so it's OK on login.
#
# Usage:  bash cluster/prefetch_model.sh Qwen/Qwen3-32B
set -e

HF_REPO="${1:-Qwen/Qwen3-32B}"
export HF_HOME=~/scratch/hf_cache
mkdir -p "${HF_HOME}"

source /nfs_home/software/miniconda/etc/profile.d/conda.sh
conda activate slaybench
pip install -q "huggingface_hub[cli]"

echo "Downloading ${HF_REPO} into ${HF_HOME} ..."
huggingface-cli download "${HF_REPO}"

echo
echo "Done. If compute nodes are offline, add to your sbatch (or lib.sh):"
echo "    export HF_HUB_OFFLINE=1"
echo "so vLLM uses the cached weights instead of trying to reach huggingface.co."
