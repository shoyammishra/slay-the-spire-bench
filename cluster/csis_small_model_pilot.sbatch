#!/bin/bash
# Separate development pilot; one-query smoke first, no automatic submission.
#SBATCH --job-name=slay_small_pilot
#SBATCH --no-requeue
#SBATCH --partition=gpu-short
#SBATCH --gres=gpu:a100-80gb:1
#SBATCH --time=08:00:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --output=results/slay_small_pilot_%j.out
#SBATCH --error=results/slay_small_pilot_%j.err

set -euo pipefail
cd "${SLURM_SUBMIT_DIR}"
readonly PILOT_MODEL="${PILOT_MODEL:-qwen3-8b}"
case "$PILOT_MODEL" in qwen3-8b|qwen3-14b) ;; *) exit 2 ;; esac
readonly PILOT_MAX_NEW="${PILOT_MAX_NEW:-1}"
if [[ ! "$PILOT_MAX_NEW" =~ ^[0-9]+$ ]] || (( PILOT_MAX_NEW < 1 || PILOT_MAX_NEW > 16 )); then
  echo "ERROR: PILOT_MAX_NEW must be 1..16."
  exit 2
fi
if ! command -v conda >/dev/null 2>&1; then
  if [[ -n "${CONDA_SH:-}" && -f "$CONDA_SH" ]]; then
    source "$CONDA_SH"
  else
    echo "ERROR: load conda or export CONDA_SH before submission."
    exit 2
  fi
fi
set +u
eval "$(conda shell.bash hook)"
conda activate "${CONDA_ENV:-slaybench08}"
set -u
export HF_HOME="${HF_HOME:-${HOME}/scratch/hf_cache}"
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
export PYTHONUNBUFFERED=1
mkdir -p results

# Hold a separate job-level lock before allocating a server; Python also locks
# evidence writes. The two lock files deliberately have different purposes.
exec 9>results/small_model_development.job.lock
flock -n 9 || { echo "ERROR: another development batch holds the job lock."; exit 2; }

python scripts/small_model_pilot.py preflight --model "$PILOT_MODEL" --max-new "$PILOT_MAX_NEW"

# Query this exact allocation's EndTime. Do not reset an eight-hour stopwatch
# after startup, because queue/site adjustments can change the actual deadline.
PILOT_END=$(scontrol show job "$SLURM_JOB_ID" -o | tr ' ' '\n' | sed -n 's/^EndTime=//p')
PILOT_DEADLINE=$(date -d "$PILOT_END" +%s)
if (( PILOT_DEADLINE - $(date +%s) < 3180 )); then
  echo "ERROR: insufficient allocation time for startup and one guarded query."
  exit 2
fi
readonly PILOT_PORT="$((19000 + SLURM_JOB_ID % 1000))"
readonly PILOT_URL="http://localhost:${PILOT_PORT}/v1"
readonly PILOT_RECEIPT="results/small_model_development_server_${SLURM_JOB_ID}.json"
readonly PILOT_LOG="results/small_model_development_server_${SLURM_JOB_ID}.log"

python - "$PILOT_PORT" <<'PY'
import socket, sys
with socket.socket() as sock:
    sock.bind(('127.0.0.1', int(sys.argv[1])))
PY

PILOT_PID=""
cleanup() {
  if [[ -n "$PILOT_PID" ]]; then
    # The session leader may have died while engine workers remain alive.
    kill -TERM -- "-$PILOT_PID" 2>/dev/null || true
    for cleanup_attempt in $(seq 1 15); do
      kill -0 -- "-$PILOT_PID" 2>/dev/null || break
      sleep 1
    done
    if kill -0 -- "-$PILOT_PID" 2>/dev/null; then
      kill -KILL -- "-$PILOT_PID" 2>/dev/null || true
    fi
  fi
}
trap cleanup EXIT
# Termination must end this shell, not return and begin a new inference call.
trap 'exit 143' TERM
trap 'exit 130' INT
set +m
setsid python scripts/small_model_pilot.py server --model "$PILOT_MODEL" \
  --port "$PILOT_PORT" --receipt "$PILOT_RECEIPT" \
  --authorize-model-inference > "$PILOT_LOG" 2>&1 &
PILOT_PID=$!
PILOT_READY=0
PILOT_STARTUP_STOP="$(( $(date +%s) + 1200 ))"
for attempt in $(seq 1 240); do
  PILOT_NOW=$(date +%s)
  if (( PILOT_NOW >= PILOT_STARTUP_STOP || PILOT_DEADLINE - PILOT_NOW < 1980 )); then
    break
  fi
  kill -0 "$PILOT_PID" 2>/dev/null || break
  if curl --silent --fail --max-time 5 "$PILOT_URL/models" | grep -q "$PILOT_MODEL"; then
    PILOT_READY=1
    break
  fi
  sleep 5
done
if [[ "$PILOT_READY" -ne 1 ]]; then
  echo "ERROR: server failed readiness; no inference started by this launcher."
  tail -n 80 "$PILOT_LOG"
  exit 3
fi

python scripts/small_model_pilot.py run --model "$PILOT_MODEL" \
  --port "$PILOT_PORT" --receipt "$PILOT_RECEIPT" \
  --authorize-model-inference --max-new "$PILOT_MAX_NEW" \
  --stop-at-unix "$PILOT_DEADLINE"
python scripts/small_model_pilot.py status --model "$PILOT_MODEL"
echo "Development batch finished. Inspect results before another submission."
