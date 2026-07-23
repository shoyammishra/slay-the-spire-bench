#!/bin/bash
#SBATCH --job-name=slay_combo
#SBATCH --partition=gpu_h200_8
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=100G
#SBATCH --time=72:00:00
#SBATCH --output=slay_combo_%j.out

# ── Sharanga matrix: ONE (character,format) combo, ALL FOUR dimensions ─────────
# The PARALLEL / fire-and-forget path. This job serves qwen3-32b ONCE and runs
# turn+combat → synergy → run for a SINGLE character+format, writing exactly ONE
# result file:  results/qwen3-32b[_silent]_{structured,raw}_seed*.json
#
# WHY THIS EXISTS (vs sharanga_{turn_combat,synergy,run_level}.sbatch):
# Those dimension-split files each loop over BOTH characters × BOTH formats, so
# each of them touches all 4 result files → they MUST run sequentially or they
# race on read-modify-write (--only merges other dims from disk). This combo file
# instead splits along the OUTPUT FILE: 4 combos (2 char × 2 fmt) write DISJOINT
# files, so up to 3 run CONCURRENTLY under the gpu_h200_8 per-user 3-GPU QOS cap
# with ZERO file race. That is the fast way to fill the matrix while unattended.
#
# DO NOT hand-submit these four one by one — use the smoke-gated launcher:
#   bash cluster/sharanga_submit_qwen3_matrix.sh
# It submits a qwen3-32b smoke first and makes the 4 combos --dependency=afterok
# on it, so a serving/env failure blocks the multi-day jobs instead of burning
# days producing garbage (cheapest-first; the Gemma-3-12B empty-output precedent).
#
# SUPERSESSION (comparability): these full-matrix qwen3-32b cells SUPERSEDE the
# CSIS synergy-only qwen3-32b cells (different serving stack — vLLM 0.8.x there);
# never blend the CSIS qwen3-32b synergy numbers with these.
#
# SIZING (one combo = ¼ of the matrix work; documented anchors only):
#   turn+combat one char one fmt ≈ 3 h of 7B-A100 work; run one char one fmt
#   ≈ 4 h; synergy ≈ 0.5 h. qwen3-32b on H200 ≈ ×0.86–1.3 wall/token (63–95 tok/s
#   vs the 7B's measured 190) and reasoning <think> ≈ 3–5× output tokens/call.
#   ⇒ one combo ≈ (3+4+0.5) h × (2.6–6.5) ≈ 20–50 h central; pathological
#   8k-deliberation tail is unbounded upward. --time=72 h covers the central band
#   + cold start; per-dimension partial saves bound any wall-kill loss to the
#   in-flight dimension (turn+combat+synergy already on disk when run starts).
#
# OVERRIDES (env; the launcher sets CHAR/FMT). Later rungs, e.g. 235B FP8 TP=2:
#   CHAR=ironclad FMT=structured HF_REPO=Qwen/Qwen3-235B-A22B-FP8 \
#     SERVED_NAME=qwen3-235b-a22b-fp8 TP_SIZE=2 HEALTH_WAIT_MIN=180 \
#     sbatch --gres=gpu:2 --cpus-per-task=8 --mem=250G cluster/sharanga_matrix_combo.sbatch
# ──────────────────────────────────────────────────────────────────────────────

# conda's cuda-nvcc activate/deactivate hooks reference unbound vars (CUDAARCHS_BACKUP)
# → they abort under `set -u`. Defer -u until AFTER activation (found 2026-07-24).
set -eo pipefail
source ~/miniconda3/bin/activate slaybench
set -u
export HF_HOME=/scratch/$USER/hf
# Unbuffered Python: without this a wedged vLLM leaves a 0-byte log (job 261007,
# gpu_h200_8, 2026-07-23 — 10 min alive, nothing flushed, no diagnostic survived).
export PYTHONUNBUFFERED=1
# Weights are prefetched into $HF_HOME — skip HF Hub liveness checks (two ~1-min
# stalls seen on gpu_h200_8, 2026-07-23).
export HF_HUB_OFFLINE=1
# FlashInfer JIT sampling kernel won't build here — native torch sampler instead
# (identical sampling semantics; irrelevant at our batch≈1 sequential workload).
export VLLM_USE_FLASHINFER_SAMPLER=0

MODEL_REPO=${HF_REPO:-Qwen/Qwen3-32B}
SERVED_NAME=${SERVED_NAME:-qwen3-32b}
CHAR=${CHAR:-ironclad}       # ironclad | silent   (the launcher always sets this)
FMT=${FMT:-structured}       # structured | raw
TP_SIZE=${TP_SIZE:-1}
HEALTH_WAIT_MIN=${HEALTH_WAIT_MIN:-60}
# Unique port per job: Slurm can co-schedule several single-GPU jobs onto one
# 8-GPU H200 node, so a hardcoded :8000 would let two concurrent combos collide.
PORT=${PORT:-$(( 10000 + SLURM_JOB_ID % 40000 ))}

# Fail fast if the weights were never prefetched (or the 15-day scratch purge ate
# them): with HF_HUB_OFFLINE=1 vLLM would otherwise die minutes into startup.
HUB_DIR="${HF_HOME}/hub/models--${MODEL_REPO//\//--}"
if [ ! -d "$HUB_DIR" ]; then
  echo "ERROR: $MODEL_REPO is not prefetched (missing $HUB_DIR)."
  echo "On the login node run:  HF_HOME=/scratch/\$USER/hf hf download $MODEL_REPO"
  exit 1
fi

cd ~/slay-bench

echo "=== combo: model=$SERVED_NAME  character=$CHAR  format=$FMT  TP=$TP_SIZE  port=$PORT ==="
echo "=== GPU ==="
nvidia-smi

echo "=== starting vLLM ($MODEL_REPO as $SERVED_NAME, TP=$TP_SIZE, port=$PORT) ==="
vllm serve "$MODEL_REPO" \
  --served-model-name "$SERVED_NAME" \
  --port "$PORT" \
  --tensor-parallel-size "$TP_SIZE" \
  --max-model-len 16384 \
  --gpu-memory-utilization 0.90 \
  > "vllm_combo_${SLURM_JOB_ID}.log" 2>&1 &
VLLM_PID=$!
trap 'kill $VLLM_PID 2>/dev/null || true' EXIT

# Wait for the server. Cold Lustre load scales with model size (7B = 7.2 min for
# ~15 GB → ~65 GB qwen3-32b ≈ 35+ min) + compile; default 60 min, override for
# the biggest rungs (see header). Warm nodes (shared ~/.cache) start in ~90 s.
UP=0
for i in $(seq 1 $(( HEALTH_WAIT_MIN * 12 ))); do
  if curl -sf -o /dev/null "http://localhost:${PORT}/health"; then
    echo "vLLM up after ~$((i * 5))s"
    UP=1
    break
  fi
  if ! kill -0 $VLLM_PID 2>/dev/null; then
    echo "vLLM DIED during startup — tail of log:"
    tail -50 "vllm_combo_${SLURM_JOB_ID}.log"
    exit 1
  fi
  sleep 5
done
if [ "$UP" -ne 1 ]; then
  echo "vLLM never came up — tail of log:"
  tail -50 "vllm_combo_${SLURM_JOB_ID}.log"
  exit 1
fi

# Reasoning models can spend the whole 8k budget in <think> (~127 s/call at
# 63 tok/s) — above the harness's 300 s default is unlikely here but keep headroom.
export LOCAL_TIMEOUT="${LOCAL_TIMEOUT:-600}"

BASE="http://localhost:${PORT}/v1"
FAILED=0

# Cheapest-first within the combo: turn+combat → synergy → run. Each is its own
# python process that saves the merged JSON on completion, so a wall-kill during
# the (longest) run dimension still leaves turn+combat+synergy on disk.
echo "=== [$CHAR/$FMT] turn+combat (n=20, 5 seeds) ==="
if ! python run_benchmark.py --provider local --base-url "$BASE" \
    --model "$SERVED_NAME" --character "$CHAR" --format "$FMT" \
    --only turn combat --n-turn 20 --n-combat 20 \
    --seeds 42 1042 2042 3042 4042; then
  echo "!!!! DIM FAILED (continuing): turn+combat $SERVED_NAME $CHAR $FMT !!!!"; FAILED=1
fi

echo "=== [$CHAR/$FMT] synergy (n=20, 5 seeds) ==="
if ! python run_benchmark.py --provider local --base-url "$BASE" \
    --model "$SERVED_NAME" --character "$CHAR" --format "$FMT" \
    --only synergy --n-synergy 20 \
    --seeds 42 1042 2042 3042 4042; then
  echo "!!!! DIM FAILED (continuing): synergy $SERVED_NAME $CHAR $FMT !!!!"; FAILED=1
fi

echo "=== [$CHAR/$FMT] run-level (n=20, 5 seeds) — longest, last ==="
if ! python run_benchmark.py --provider local --base-url "$BASE" \
    --model "$SERVED_NAME" --character "$CHAR" --format "$FMT" \
    --only run --n-run 20 \
    --seeds 42 1042 2042 3042 4042; then
  echo "!!!! DIM FAILED (continuing): run-level $SERVED_NAME $CHAR $FMT !!!!"; FAILED=1
fi

if [ "${FAILED}" -ne 0 ]; then
  echo "=== combo $SERVED_NAME $CHAR $FMT finished WITH FAILURES — grep 'DIM FAILED' above ==="
  exit 1
fi
echo "=== combo $SERVED_NAME $CHAR $FMT COMPLETE (all four dimensions) ==="
