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

# NOTE: the installed stack is vLLM 0.6.6 + transformers 4.47.1, which does NOT
# support the qwen3 architecture (that needs vLLM 0.8.x+ — see CLAUDE.md). So the
# default is a qwen2.5 model that runs on this stack TODAY. To serve qwen3-32b,
# first upgrade vLLM (check CUDA-12.8 compat), then override:
#   HF_REPO=Qwen/Qwen3-32B SERVED_NAME=qwen3-32b sbatch ...
# A bigger qwen2.5 also fits one A100 80GB: HF_REPO=Qwen/Qwen2.5-32B-Instruct.
: "${HF_REPO:=Qwen/Qwen2.5-7B-Instruct}"  # HuggingFace repo to serve
: "${SERVED_NAME:=qwen2.5-7b}"            # clean alias -> --model + result filenames
# Derive a per-job port from the Slurm job id so two jobs landing on the SAME
# node never collide on 8000. (Job 7542 died exactly this way: a stale vLLM from
# a prior job still held :8000, our server got [Errno 98] address already in use
# and shut down, while wait_for_vllm was fooled "ready" by the stale server.)
: "${VLLM_PORT:=$(( 8000 + (${SLURM_JOB_ID:-0} % 1000) ))}"
: "${TP_SIZE:=1}"                # tensor-parallel GPU count (set 2 for a 70B over 2 A100s)
# Cap the KV cache so a 32B model leaves room for it on one 80GB A100, and bump
# memory utilization. Qwen3-32B defaults to max_seq_len=40960, which demands a
# ~10 GiB KV cache; with vLLM 0.8.x's default gpu_memory_utilization=0.9 the
# smoke test (job 7568) found only ~4 GiB free after the ~65 GB weights load and
# died at KV-cache init. We never prompt anywhere near 40k tokens (largest run-
# level prompt ~3.4k, +8k generation budget), so 16384 is ample headroom and
# leaves plenty of KV cache. Override with VLLM_MAX_LEN / VLLM_GPU_UTIL if needed.
: "${VLLM_MAX_LEN:=16384}"       # --max-model-len (context window cap)
: "${VLLM_GPU_UTIL:=0.95}"       # --gpu-memory-utilization
: "${VLLM_EXTRA:=}"             # any extra `vllm serve` args (e.g. --enforce-eager)

BASE_URL="http://localhost:${VLLM_PORT}/v1"
VLLM_LOG="vllm_${SLURM_JOB_ID:-local}.log"
VLLM_PID=""

start_vllm() {
  # Free a stale holder of the port (leftover vLLM from a prior job on this node)
  # so our server can actually bind it instead of dying with [Errno 98].
  fuser -k "${VLLM_PORT}/tcp" 2>/dev/null && sleep 2
  echo "[lib] serving ${HF_REPO} as '${SERVED_NAME}' on :${VLLM_PORT} (tensor-parallel=${TP_SIZE})"
  vllm serve "${HF_REPO}" \
      --served-model-name "${SERVED_NAME}" \
      --port "${VLLM_PORT}" \
      --tensor-parallel-size "${TP_SIZE}" \
      --max-model-len "${VLLM_MAX_LEN}" \
      --gpu-memory-utilization "${VLLM_GPU_UTIL}" \
      ${VLLM_EXTRA} > "${VLLM_LOG}" 2>&1 &
  VLLM_PID=$!
  echo "[lib] vLLM pid=${VLLM_PID}  (server log -> ${VLLM_LOG})"
}

wait_for_vllm() {
  # First-time weight load for a 32B model can take several minutes.
  local tries=0 max=240   # 240 * 5s = 20 min ceiling
  echo "[lib] waiting for vLLM to become ready..."
  # Require the readiness probe to see OUR served model name, not just any server
  # answering on the port (job 7542 was fooled "ready" by a stale vLLM that then
  # vanished -> connection-refused for the whole benchmark).
  until curl -s "http://localhost:${VLLM_PORT}/v1/models" 2>/dev/null | grep -q "${SERVED_NAME}"; do
    # If vLLM logged a bind failure, our server will never come up — fail fast.
    if grep -q 'address already in use' "${VLLM_LOG}" 2>/dev/null; then
      echo "[lib] ERROR: vLLM could not bind :${VLLM_PORT} (address already in use)."
      echo "[lib] A stale server is holding the port. Last 40 log lines:"
      tail -n 40 "${VLLM_LOG}"
      exit 1
    fi
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
