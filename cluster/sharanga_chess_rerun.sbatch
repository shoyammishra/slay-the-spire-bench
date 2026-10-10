#!/bin/bash
# POST HOC chess rerun: the gpt-oss queries that hit the 16k cap, rerun at 32k output tokens.
# Same pinned server command as the pilot (max-model-len 32768 fits 595-token prompts + 32k).
#   sbatch --partition=gpu_h100_4 --gres=gpu:1 --cpus-per-task=8 --mem=96G --time=03:00:00 \
#     --export=ALL,V3_MODEL=gpt-oss-120b,CONDA_ENV=...,TIKTOKEN_ENCODINGS_BASE=... cluster/sharanga_chess_rerun.sbatch
# gpt-oss also needs CONDA_ENV / TIKTOKEN_* exports (see experiment_log 2026-10-02).
#SBATCH --job-name=slay_chessrr
#SBATCH --no-requeue
#SBATCH --partition=gpu_h200_8
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=96G
#SBATCH --time=03:00:00
#SBATCH --output=results/controlled_h_v3_logs/chess_rerun_%j.out

set -eo pipefail
cd "${SLURM_SUBMIT_DIR}"
source "${HOME}/miniconda3/etc/profile.d/conda.sh"
conda activate "${CONDA_ENV:-slaybench08}"
set -u
readonly MODEL="${V3_MODEL:?set V3_MODEL}"
case "$MODEL" in gpt-oss-120b) ;; *) echo "unknown model"; exit 2 ;; esac
export HF_HOME="${HF_HOME:-/scratch/${USER}/hf}" HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
export PYTHONUNBUFFERED=1 PYTHONIOENCODING=utf-8
test -f results/chess_pilot/release.json
python -c "import chess" 2>/dev/null || pip install --quiet --no-deps chess==1.11.2

readonly PORT="$((21000 + SLURM_JOB_ID % 1000))"
readonly RECEIPT="results/controlled_h_v3_logs/chess_server_${SLURM_JOB_ID}.json"
readonly SLOG="results/controlled_h_v3_logs/chess_server_${SLURM_JOB_ID}.log"
PID=""
cleanup() {
  if [[ -n "$PID" ]]; then
    kill -TERM -- "-$PID" 2>/dev/null || true
    for _ in $(seq 1 15); do kill -0 -- "-$PID" 2>/dev/null || break; sleep 1; done
    kill -KILL -- "-$PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT
trap 'exit 143' TERM
set +m
setsid python scripts/heldout_v3_inference.py server --model "$MODEL" --port "$PORT" \
  --receipt "$RECEIPT" --authorize-model-inference > "$SLOG" 2>&1 &
PID=$!
readonly HEALTH_WAIT_MIN="${HEALTH_WAIT_MIN:-90}"
READY=0
for _ in $(seq 1 $((HEALTH_WAIT_MIN * 12))); do
  kill -0 "$PID" 2>/dev/null || break
  if curl --silent --fail --max-time 5 "http://localhost:${PORT}/v1/models" | grep -q "$MODEL"; then READY=1; break; fi
  sleep 5
done
if [[ "$READY" -ne 1 ]]; then echo "ERROR: server not ready"; tail -n 80 "$SLOG"; exit 3; fi

python scripts/chess_rerun_truncated.py run --model "$MODEL" --port "$PORT" --max-tokens 32000
python scripts/chess_rerun_truncated.py analyze --model "$MODEL" --max-tokens 32000
