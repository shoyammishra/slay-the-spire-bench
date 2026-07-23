#!/bin/bash
#SBATCH --job-name=slay_syn
#SBATCH --partition=gpu_h200_8
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=100G
#SBATCH --time=24:00:00
#SBATCH --output=slay_syn_%j.out

# ── Sharanga paper-grade matrix: SYNERGY ──────────────────────────────────────
# Ladder rung-1 default: qwen3-32b, BOTH characters x BOTH formats, n=20
# (20 hand-crafted fixtures/character), --seeds 42 1042 2042 3042 4042.
# One light call per sample — the cheapest dimension. Writes REAL matrix cells
# (no --run-tag on purpose): results/qwen3-32b{,_silent}_{structured,raw}_seed*.json
# — synergy merges into the same per-seed files sharanga_turn_combat wrote.
#
# SUPERSESSION (comparability): qwen3-32b ALREADY has CSIS synergy cells (its
# synergy-only matrix rows, vLLM 0.8.x stack). This job RE-RUNS synergy on the
# Sharanga stack precisely so all four qwen3-32b dimensions share ONE serving
# stack; the new cells SUPERSEDE the CSIS synergy-only cells — NEVER blend the
# CSIS qwen3-32b synergy numbers with these.
#
# JOB ORDER (cheapest-first, handoff §5.3):
#   sharanga_turn_combat -> sharanga_synergy -> sharanga_run_level
# Submit SEQUENTIALLY, never concurrently: all three merge into the SAME
# per-seed result files (--only keeps other dims from disk) and concurrent
# writers race. New model rungs get a sharanga_smoke.sbatch gate first (see the
# sharanga_turn_combat.sbatch header).
#
# SIZING (documented anchors only):
#   Calls: 20 fixtures x 5 seeds x 2 formats x 2 characters = 400 single-call
#     samples. qwen3-32b on H200 ~63-95 tok/s (1/3..1/2 of the 7B's measured
#     190 tok/s); reasoning <think> output ~1,200-2,000 tok/call
#     => ~13-32 s/call => ~1.5-3.5 h central estimate.
#   Pathological tail (every call burning the full 8k budget at ~63 tok/s
#     ~= 127 s/call): 400 x 127 s ~= 14 h. --time=24:00:00 covers that plus the
#     cold start (up to ~35+ min for 32B off Lustre) with margin.
#
# Prefetch on the login node FIRST (scratch purges 15 days idle):
#   HF_HOME=/scratch/$USER/hf hf download Qwen/Qwen3-32B
#
# Later ladder rungs reuse this file via env overrides (decision_log 2026-07-23):
#   # 70B scale axis (BF16 ~140 GB > one H200's ~127 GB usable => TP=2):
#   HF_REPO=Qwen/Qwen2.5-72B-Instruct SERVED_NAME=qwen2.5-72b TP_SIZE=2 \
#     sbatch --export=ALL --gres=gpu:2 --cpus-per-task=8 cluster/sharanga_synergy.sbatch
#   #   (Llama-3.1-70B-Instruct likewise — GATED: prefetch with HF_TOKEN on the login node)
#   # gpt-oss-120b (MXFP4 fits 1x H200; needs Hopper+, NOT A100):
#   HF_REPO=openai/gpt-oss-120b SERVED_NAME=gpt-oss-120b \
#     sbatch --export=ALL cluster/sharanga_synergy.sbatch
#   # Qwen3-235B-A22B FP8 (~235 GB weights => TP=2 H200 = default-QOS ceiling):
#   HF_REPO=Qwen/Qwen3-235B-A22B-FP8 SERVED_NAME=qwen3-235b-a22b-fp8 TP_SIZE=2 HEALTH_WAIT_MIN=180 \
#     sbatch --export=ALL --gres=gpu:2 --cpus-per-task=8 --mem=250G cluster/sharanga_synergy.sbatch
#   # Partition move (ONE --partition per job; <=4 CPUs per H200 GPU but h100 QOS
#   # allows cpu=8; gpu_h100_4 MaxTime is 3 d so cap --time):
#   sbatch --partition=gpu_h100_4 --cpus-per-task=8 --time=1-00:00:00 cluster/sharanga_synergy.sbatch
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

MODEL_REPO=${HF_REPO:-Qwen/Qwen3-32B}
SERVED_NAME=${SERVED_NAME:-qwen3-32b}
PORT=${PORT:-8000}
TP_SIZE=${TP_SIZE:-1}
HEALTH_WAIT_MIN=${HEALTH_WAIT_MIN:-60}

# Fail fast if the weights were never prefetched (or the 15-day scratch purge ate
# them): with HF_HUB_OFFLINE=1 vLLM would otherwise die minutes into startup.
HUB_DIR="${HF_HOME}/hub/models--${MODEL_REPO//\//--}"
if [ ! -d "$HUB_DIR" ]; then
  echo "ERROR: $MODEL_REPO is not prefetched (missing $HUB_DIR)."
  echo "On the login node run:  HF_HOME=/scratch/\$USER/hf hf download $MODEL_REPO"
  exit 1
fi

cd ~/slay-bench

echo "=== GPU ==="
nvidia-smi

echo "=== starting vLLM ($MODEL_REPO as $SERVED_NAME, TP=$TP_SIZE) ==="
vllm serve "$MODEL_REPO" \
  --served-model-name "$SERVED_NAME" \
  --port "$PORT" \
  --tensor-parallel-size "$TP_SIZE" \
  --max-model-len 16384 \
  --gpu-memory-utilization 0.90 \
  > "vllm_syn_${SLURM_JOB_ID}.log" 2>&1 &
VLLM_PID=$!
trap 'kill $VLLM_PID 2>/dev/null || true' EXIT

# Wait for the OpenAI-compatible server. Sharanga cold-node startup is SLOW and
# scales with model size: the 7B alone took 7.2 min of pure Lustre weight load
# (job 261007's interactive repro, 2026-07-23) + dynamo/inductor compile. The
# smoke's 25 min budget scaled to qwen3-32b's ~65 GB of weights needs ~35+ min,
# so default 60 min here; biggest rungs override HEALTH_WAIT_MIN (see header).
UP=0
for i in $(seq 1 $(( HEALTH_WAIT_MIN * 12 ))); do
  if curl -sf -o /dev/null "http://localhost:${PORT}/health"; then
    echo "vLLM up after ~$((i * 5))s"
    UP=1
    break
  fi
  if ! kill -0 $VLLM_PID 2>/dev/null; then
    echo "vLLM DIED during startup — tail of log:"
    tail -50 "vllm_syn_${SLURM_JOB_ID}.log"
    exit 1
  fi
  sleep 5
done
if [ "$UP" -ne 1 ]; then
  echo "vLLM never came up — tail of log:"
  tail -50 "vllm_syn_${SLURM_JOB_ID}.log"
  exit 1
fi

# Reasoning models can spend the whole 8k budget in <think>: qwen3-32b at ~63 tok/s
# ~= 127 s/call — fine, but a slower future rung could approach the harness's 300 s
# default. Keep the CSIS 600 s ceiling; raise via env for very slow rungs.
export LOCAL_TIMEOUT="${LOCAL_TIMEOUT:-600}"

# Fail-loud, keep-going: one bad combo must not discard the other three (partial
# results > lost job), but the job still exits non-zero if anything failed.
FAILED=0
for CHAR in ironclad silent; do
  for FMT in structured raw; do
    echo "=== synergy, model=${SERVED_NAME}, character=${CHAR}, format=${FMT} ==="
    if ! python run_benchmark.py \
        --provider local --base-url "http://localhost:${PORT}/v1" \
        --model "${SERVED_NAME}" --character "${CHAR}" \
        --only synergy --n-synergy 20 \
        --seeds 42 1042 2042 3042 4042 \
        --format "${FMT}"; then
      echo "!!!! COMBO FAILED (continuing): synergy ${SERVED_NAME} ${CHAR} ${FMT} !!!!"
      FAILED=1
    fi
  done
done

if [ "${FAILED}" -ne 0 ]; then
  echo "=== synergy (${SERVED_NAME}) finished WITH FAILURES — grep 'COMBO FAILED' above ==="
  exit 1
fi
echo "=== synergy (${SERVED_NAME}, both characters, both formats) done ==="
