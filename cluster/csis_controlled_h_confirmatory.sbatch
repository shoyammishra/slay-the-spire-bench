#!/bin/bash
# Detached, bounded confirmation continuation. No auto-submission or requery.
# Export only the environment variables listed in the amendment runbook.
# First amended-stack smoke: CONF_MAX_NEW=1; later inspected batches: at most 32.
#SBATCH --job-name=slay_h_confirm
#SBATCH --no-requeue
#SBATCH --partition=gpu-short
#SBATCH --gres=gpu:a100-80gb:1
#SBATCH --time=08:00:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --output=results/slay_h_confirm_%j.out
#SBATCH --error=results/slay_h_confirm_%j.err

set -euo pipefail
cd "${SLURM_SUBMIT_DIR}"
readonly CONF_MAX_NEW="${CONF_MAX_NEW:-1}"
if [[ ! "$CONF_MAX_NEW" =~ ^[0-9]+$ ]] || (( CONF_MAX_NEW < 1 || CONF_MAX_NEW > 32 )); then
  echo "ERROR: CONF_MAX_NEW must be 1..32."
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
exec 9>results/controlled_h_v2_confirmatory_batch.job.lock
flock -n 9 || { echo "ERROR: another confirmation batch holds the job lock."; exit 2; }

CONF_PREFLIGHT="results/controlled_h_v2_confirmatory_batch_preflight_${SLURM_JOB_ID}.json"
python scripts/confirmatory_batch.py preflight --out "$CONF_PREFLIGHT"
python - "$CONF_PREFLIGHT" <<'PY'
import json, sys
p = json.load(open(sys.argv[1]))
if not p['runnable']:
    raise SystemExit('No runnable continuation; inspect preflight before allocating a server.')
if p['claim_already_failed']:
    raise SystemExit('An execution failure already blocks claims; review before further compute.')
PY

# Query this exact allocation's EndTime. Do not reset an eight-hour stopwatch
# after startup, because queue/site adjustments can change the actual deadline.
CONF_END=$(scontrol show job "$SLURM_JOB_ID" -o | tr ' ' '\n' | sed -n 's/^EndTime=//p')
CONF_DEADLINE=$(date -d "$CONF_END" +%s)
if (( CONF_DEADLINE - $(date +%s) < 2280 )); then
  echo "ERROR: insufficient allocation time for startup and one guarded query."
  exit 2
fi
readonly CONF_PORT="$((18000 + SLURM_JOB_ID % 1000))"
readonly CONF_URL="http://localhost:${CONF_PORT}/v1"
readonly CONF_RECEIPT="results/controlled_h_v2_confirmatory_server_${SLURM_JOB_ID}.json"
readonly CONF_LOG="results/controlled_h_v2_confirmatory_server_${SLURM_JOB_ID}.log"

python - "$CONF_PORT" <<'PY'
import socket, sys
with socket.socket() as sock:
    sock.bind(('127.0.0.1', int(sys.argv[1])))
PY

CONF_PID=""
cleanup() {
  if [[ -n "$CONF_PID" ]]; then
    # The session leader may have died while engine workers remain alive.
    kill -TERM -- "-$CONF_PID" 2>/dev/null || true
    for cleanup_attempt in $(seq 1 15); do
      kill -0 -- "-$CONF_PID" 2>/dev/null || break
      sleep 1
    done
    if kill -0 -- "-$CONF_PID" 2>/dev/null; then
      kill -KILL -- "-$CONF_PID" 2>/dev/null || true
    fi
  fi
}
trap cleanup EXIT
# Termination must end this shell, not return and begin a new inference call.
trap 'exit 143' TERM
trap 'exit 130' INT
set +m
setsid python scripts/controlled_horizon_confirmatory_server.py \
  --port "$CONF_PORT" --receipt "$CONF_RECEIPT" \
  --authorize-model-inference > "$CONF_LOG" 2>&1 &
CONF_PID=$!
CONF_READY=0
CONF_STARTUP_STOP="$(( $(date +%s) + 1200 ))"
for attempt in $(seq 1 240); do
  CONF_NOW=$(date +%s)
  if (( CONF_NOW >= CONF_STARTUP_STOP || CONF_DEADLINE - CONF_NOW < 1080 )); then
    break
  fi
  kill -0 "$CONF_PID" 2>/dev/null || break
  if curl --silent --fail --max-time 5 "$CONF_URL/models" | grep -q 'qwen3-32b'; then
    CONF_READY=1
    break
  fi
  sleep 5
done
if [[ "$CONF_READY" -ne 1 ]]; then
  echo "ERROR: server failed readiness; no inference started by this launcher."
  tail -n 80 "$CONF_LOG"
  exit 3
fi

python scripts/confirmatory_batch.py run \
  --provider local --base-url "$CONF_URL" --server-receipt "$CONF_RECEIPT" \
  --authorize-model-inference --max-new-queries "$CONF_MAX_NEW" \
  --stop-at-unix "$CONF_DEADLINE"
python scripts/confirmatory_batch.py analyze \
  --out "results/controlled_h_v2_confirmatory_batch_analysis_${SLURM_JOB_ID}.json"
echo "Batch finished. Inspect its disposition before submitting another job."
