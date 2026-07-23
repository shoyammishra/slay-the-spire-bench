#!/bin/bash
#SBATCH --job-name=slay_smoke
#SBATCH --partition=gpu_a100_8
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=01:30:00
#SBATCH --output=slay_smoke_%j.out

# ── Sharanga smoke test ────────────────────────────────────────────────────────
# Tiny full 4-dimension pass on qwen2.5-7b, 1× A100 (gpu_a100_8 partition).
# Purpose: validate the end-to-end pipeline on THIS cluster + measure tok/s
# before sizing any paper-grade job (buy information cheapest-first).
#
# Sharanga specifics (recon 2026-07-23; details in docs/Sharanga_HPC_SOP.pdf, gitignored):
#   • QOS qos_gpu_a100 caps each user at 2 GPUs here; no QOS wall-time cap
#     (partition MaxTime 5-00:00:00 governs). H100/H200 QOS also cap cpu=8.
#   • Driver CUDA 13.0 (580.126.20) → latest vLLM (cu130 torch). The CSIS
#     vLLM-0.6.6 pin does NOT apply on this cluster.
#   • SHARED ACCOUNT: `conda init` IS in the shared .bashrc (professor-approved
#     2026-07-23, auto_activate_base false) — interactive shells use plain
#     `conda activate slaybench`; this script still sources explicitly (batch shell);
#     HF cache lives on scratch. NEVER `scancel -u` — it kills others' jobs.
#   • Weights should be prefetched on the login node first:
#       HF_HOME=/scratch/$USER/hf hf download Qwen/Qwen2.5-7B-Instruct
# ──────────────────────────────────────────────────────────────────────────────

set -euo pipefail

source ~/miniconda3/bin/activate slaybench
export HF_HOME=/scratch/$USER/hf
# Unbuffered Python: without this a wedged vLLM leaves a 0-byte log (seen job 261007
# on gpu_h200_8 — 10 min alive, nothing flushed, no diagnostic survived the kill).
export PYTHONUNBUFFERED=1
# Everything is prefetched into $HF_HOME — skip HF Hub liveness checks (two ~1-min
# stalls observed on gpu_h200_8, 2026-07-23).
export HF_HUB_OFFLINE=1
# FlashInfer's JIT sampling kernel won't build on this cluster (no system CUDA
# toolkit; env-local nvcc + libcurand-dev got close but ninja still failed,
# 2026-07-23). Native torch sampler instead — identical sampling semantics,
# irrelevant perf delta at our batch≈1 sequential workload.
export VLLM_USE_FLASHINFER_SAMPLER=0

MODEL_REPO=${HF_REPO:-Qwen/Qwen2.5-7B-Instruct}
SERVED_NAME=${SERVED_NAME:-qwen2.5-7b}
PORT=${PORT:-8000}

cd ~/slay-bench

echo "=== GPU ==="
nvidia-smi

echo "=== starting vLLM ($MODEL_REPO as $SERVED_NAME) ==="
vllm serve "$MODEL_REPO" \
  --served-model-name "$SERVED_NAME" \
  --port "$PORT" \
  --max-model-len 16384 \
  --gpu-memory-utilization 0.90 \
  > "vllm_smoke_${SLURM_JOB_ID}.log" 2>&1 &
VLLM_PID=$!
trap 'kill $VLLM_PID 2>/dev/null || true' EXIT

# Wait for the OpenAI-compatible server. Sharanga cold-node startup is SLOW:
# weight load off Lustre alone took 7.2 min (job 261007's interactive repro,
# 2026-07-23) + dynamo/inductor compile — allow 25 min.
UP=0
for i in $(seq 1 300); do
  if curl -sf -o /dev/null "http://localhost:${PORT}/health"; then
    echo "vLLM up after ~$((i * 5))s"
    UP=1
    break
  fi
  if ! kill -0 $VLLM_PID 2>/dev/null; then
    echo "vLLM DIED during startup — tail of log:"
    tail -50 "vllm_smoke_${SLURM_JOB_ID}.log"
    exit 1
  fi
  sleep 5
done
if [ "$UP" -ne 1 ]; then
  echo "vLLM never came up — tail of log:"
  tail -50 "vllm_smoke_${SLURM_JOB_ID}.log"
  exit 1
fi

echo "=== tiny 4-dimension pass (CSIS reference: 1m35s wall on A100 @ ~82 tok/s) ==="
time python run_benchmark.py \
  --provider local --base-url "http://localhost:${PORT}/v1" \
  --model "$SERVED_NAME" \
  --n-turn 2 --n-combat 1 --n-synergy 4 --n-run 1 \
  --format structured --seed 42 \
  --run-tag sharanga_smoke

echo "=== done — results under results/ tagged sharanga_smoke (no matrix overwrite) ==="
