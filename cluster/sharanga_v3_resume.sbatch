#!/bin/bash
# Resume a v3 model after an infrastructure failure left lost-in-flight queries (recorded as
# permanent ambiguous_query failures, never re-asked). Identical to sharanga_v3_inference.sbatch
# except the run step goes through scripts/heldout_v3_resume.py with the inspected indices:
#   sbatch --partition=gpu_h200_8 --gres=gpu:1 --cpus-per-task=4 --time=24:00:00 --export=ALL,V3_MODEL=qwen3-32b,V3_ACCEPT_LOST=5879:5881 cluster/sharanga_v3_resume.sbatch
#SBATCH --job-name=slay_v3_infer
#SBATCH --no-requeue
#SBATCH --partition=gpu_h100_4
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=30:00:00
#SBATCH --output=results/controlled_h_v3_logs/infer_%j.out

set -eo pipefail
cd "${SLURM_SUBMIT_DIR}"
source "${HOME}/miniconda3/etc/profile.d/conda.sh"
conda activate "${CONDA_ENV:-slaybench08}"
set -u
readonly MODEL="${V3_MODEL:?set V3_MODEL}"
readonly COND="${V3_CONDITION:-base}"
readonly ACCEPT="${V3_ACCEPT_LOST:?set V3_ACCEPT_LOST to the inspected row indices}"
case "$MODEL" in qwen3-8b|qwen3-14b|llama-3.1-8b|deepseek-r1-distill-14b|qwen2.5-7b|mistral-7b|qwen3-32b|llama-3.3-70b|gpt-oss-120b) ;; *) echo "unknown model"; exit 2 ;; esac
export HF_HOME="${HF_HOME:-/scratch/${USER}/hf}" HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
export PYTHONUNBUFFERED=1 PYTHONIOENCODING=utf-8

python scripts/heldout_v3_inference.py status --model "$MODEL" --condition "$COND"

END=$(scontrol show job "$SLURM_JOB_ID" -o | tr ' ' '\n' | sed -n 's/^EndTime=//p')
DEADLINE=$(date -d "$END" +%s)
readonly PORT="$((20000 + SLURM_JOB_ID % 1000))"
readonly RECEIPT="results/controlled_h_v3_logs/server_${SLURM_JOB_ID}.json"
readonly SLOG="results/controlled_h_v3_logs/server_${SLURM_JOB_ID}.log"

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
trap 'exit 130' INT
set +m
setsid python scripts/heldout_v3_inference.py server --model "$MODEL" --condition "$COND" --port "$PORT" \
  --receipt "$RECEIPT" --authorize-model-inference > "$SLOG" 2>&1 &
PID=$!
# Readiness budget (minutes). 20 min was too short for >60 GB checkpoints on Lustre: Qwen3-32B
# spent 8 min loading weights alone (job 374631, 2026-10-02). Must stay below the walltime.
readonly HEALTH_WAIT_MIN="${HEALTH_WAIT_MIN:-90}"
READY=0
for _ in $(seq 1 $((HEALTH_WAIT_MIN * 12))); do
  kill -0 "$PID" 2>/dev/null || break
  if curl --silent --fail --max-time 5 "http://localhost:${PORT}/v1/models" | grep -q "$MODEL"; then
    READY=1; break
  fi
  sleep 5
done
if [[ "$READY" -ne 1 ]]; then
  echo "ERROR: server not ready"; tail -n 80 "$SLOG"; exit 3
fi
V3_ACCEPT_LOST="$ACCEPT" python scripts/heldout_v3_resume.py run --model "$MODEL" --condition "$COND" --port "$PORT" --receipt "$RECEIPT" \
  --authorize-model-inference --stop-at-unix "$DEADLINE"
python scripts/heldout_v3_inference.py status --model "$MODEL" --condition "$COND"
