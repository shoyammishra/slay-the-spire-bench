# cluster/lib.sh — shared helpers for serving a model with vLLM and
# benchmarking it, inside a single Slurm job on a CSIS-cluster GPU node.
#
# Source this from an sbatch script AFTER activating the conda env. It exposes:
#   start_vllm     — launch vLLM in the background, serving $HF_REPO as $SERVED_NAME
#   wait_for_vllm  — block until the OpenAI-compatible endpoint answers
#   stop_vllm      — kill the server (also runs automatically on job exit)
# and sets $BASE_URL for the benchmark's --base-url.
#
# Override any default by `export`-ing it before sourcing, e.g.
#   HF_REPO=meta-llama/Llama-3.1-70B-Instruct SERVED_NAME=llama70b TP_SIZE=2 \
#     sbatch cluster/turn_combat.sbatch
# or by editing the defaults below.

: "${HF_REPO:=Qwen/Qwen3-32B}"   # HuggingFace repo to serve (one A100 80GB fits 32B)
: "${SERVED_NAME:=qwen3-32b}"    # clean alias -> benchmark --model + result filenames
: "${VLLM_PORT:=8000}"
: "${TP_SIZE:=1}"                # tensor-parallel GPU count (set 2 for a 70B over 2 A100s)
: "${VLLM_EXTRA:=}"             # any extra `vllm serve` args (e.g. --max-model-len 8192)

BASE_URL="http://localhost:${VLLM_PORT}/v1"
VLLM_LOG="vllm_${SLURM_JOB_ID:-local}.log"
VLLM_PID=""

start_vllm() {
  echo "[lib] serving ${HF_REPO} as '${SERVED_NAME}' on :${VLLM_PORT} (tensor-parallel=${TP_SIZE})"
  vllm serve "${HF_REPO}" \
      --served-model-name "${SERVED_NAME}" \
      --port "${VLLM_PORT}" \
      --tensor-parallel-size "${TP_SIZE}" \
      ${VLLM_EXTRA} > "${VLLM_LOG}" 2>&1 &
  VLLM_PID=$!
  echo "[lib] vLLM pid=${VLLM_PID}  (server log -> ${VLLM_LOG})"
}

wait_for_vllm() {
  # First-time weight load for a 32B model can take several minutes.
  local tries=0 max=240   # 240 * 5s = 20 min ceiling
  echo "[lib] waiting for vLLM to become ready..."
  until curl -s "http://localhost:${VLLM_PORT}/v1/models" >/dev/null 2>&1; do
    if ! kill -0 "${VLLM_PID}" 2>/dev/null; then
      echo "[lib] ERROR: vLLM died during startup. Last 40 log lines:"
      tail -n 40 "${VLLM_LOG}"
      exit 1
    fi
    tries=$((tries + 1))
    if [ "${tries}" -ge "${max}" ]; then
      echo "[lib] ERROR: vLLM not ready after $((max * 5))s. Last 40 log lines:"
      tail -n 40 "${VLLM_LOG}"
      exit 1
    fi
    sleep 5
  done
  echo "[lib] vLLM is ready -> ${BASE_URL}"
}

stop_vllm() {
  if [ -n "${VLLM_PID}" ] && kill -0 "${VLLM_PID}" 2>/dev/null; then
    echo "[lib] stopping vLLM (pid=${VLLM_PID})"
    kill "${VLLM_PID}" 2>/dev/null
    wait "${VLLM_PID}" 2>/dev/null
  fi
}

# Make sure the GPU is released even if the benchmark errors out mid-run.
trap stop_vllm EXIT
