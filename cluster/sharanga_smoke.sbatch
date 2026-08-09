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

# conda's cuda-nvcc activate/deactivate hooks reference unbound vars (CUDAARCHS_BACKUP)
# → they abort under `set -u`. Defer -u until AFTER activation (found 2026-07-24: it
# killed the batch smoke at activation; never showed in the interactive smoke).
set -eo pipefail
source ~/miniconda3/bin/activate slaybench
set -u
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
# FlashInfer is structurally unbuildable here (full account in
# sharanga_matrix_combo.sbatch, decision_log 2026-08-08). TP>1 / FP8 / MoE reach
# three further FlashInfer kernels; these disable every such path. All are no-ops
# for a BF16 dense TP=1 model, so existing rows stay comparable.
export VLLM_ALLREDUCE_USE_FLASHINFER=0
export VLLM_BLOCKSCALE_FP8_GEMM_FLASHINFER=0
export VLLM_USE_DEEP_GEMM=0
export VLLM_MOE_USE_DEEP_GEMM=0
# `-lcuda` is in /usr/lib64 on compute nodes; conda's linker doesn't search there.
export LIBRARY_PATH=/usr/lib64:${LIBRARY_PATH:-}

MODEL_REPO=${HF_REPO:-Qwen/Qwen2.5-7B-Instruct}
SERVED_NAME=${SERVED_NAME:-qwen2.5-7b}
PORT=${PORT:-8000}
# Health-wait budget (minutes). Default 25 (the validated 7B smoke). Bigger models
# have longer cold Lustre loads (~65 GB qwen3-32b ≈ 35+ min) → override, e.g.
# HEALTH_WAIT_MIN=60 when using this file as a gate for a 32B+ rung.
HEALTH_WAIT_MIN=${HEALTH_WAIT_MIN:-25}
# Multi-GPU. Added 2026-08-07: this file had NO --tensor-parallel-size, so it could
# not gate any model too big for one card — it would have failed the 235B rung at
# the gate, before a single combo ran. Remember to match --gres=gpu:$TP_SIZE and
# the H200 rule of <=4 CPUs per GPU when overriding.
TP_SIZE=${TP_SIZE:-1}
# KV-cache/activation headroom. 0.90 is right for models that leave slack; the
# 235B-FP8 rung needs ~240 GB of a 282 GB TP=2 budget, so it must run higher.
GPU_MEM_UTIL=${GPU_MEM_UTIL:-0.90}
# TP>1 serve flags. These MUST match sharanga_matrix_combo.sbatch — job 265759
# failed precisely because this file had the FlashInfer env vars but NOT these two
# flags, so the custom all-reduce path still engaged and tried to load
# trtllm_mnnvl_comm.so. A gate that serves differently from the run it gates is
# worse than no gate.
#   --disable-custom-all-reduce            -> plain NCCL instead of a custom kernel
#   pass_config.fuse_allreduce_rms=false   -> keeps the FlashInfer fused
#                                             allreduce+RMSNorm op out of the graph
# Both are no-ops at TP=1, so the 7B/32B gates are unaffected.
if [ "$TP_SIZE" -gt 1 ]; then
  EXTRA_SERVE_ARGS=${EXTRA_SERVE_ARGS:-"--disable-custom-all-reduce --compilation-config {\"pass_config\":{\"fuse_allreduce_rms\":false}}"}
else
  EXTRA_SERVE_ARGS=${EXTRA_SERVE_ARGS:-}
fi

cd ~/slay-bench

echo "=== GPU ==="
nvidia-smi

echo "=== starting vLLM ($MODEL_REPO as $SERVED_NAME, TP=$TP_SIZE, mem_util=$GPU_MEM_UTIL) ==="
vllm serve "$MODEL_REPO" \
  --served-model-name "$SERVED_NAME" \
  --port "$PORT" \
  --tensor-parallel-size "$TP_SIZE" \
  --max-model-len 16384 \
  --gpu-memory-utilization "$GPU_MEM_UTIL" \
  ${EXTRA_SERVE_ARGS} \
  > "vllm_smoke_${SLURM_JOB_ID}.log" 2>&1 &
VLLM_PID=$!
trap 'kill $VLLM_PID 2>/dev/null || true' EXIT

# Wait for the OpenAI-compatible server. Sharanga cold-node startup is SLOW:
# weight load off Lustre alone took 7.2 min (job 261007's interactive repro,
# 2026-07-23) + dynamo/inductor compile — default 25 min, override HEALTH_WAIT_MIN.
UP=0
for i in $(seq 1 $(( HEALTH_WAIT_MIN * 12 ))); do
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
