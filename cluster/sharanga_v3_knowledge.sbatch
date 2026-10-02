#!/bin/bash
# Controlled-H v3 Amendment 6: game-knowledge conditions (described | renamed) on the
# 1,169-fixture subset without untargeted Skills. Wrapper: scripts/heldout_v3_knowledge.py
# (the frozen runner and launcher are reused unchanged). Same smoke gate and resume rules.
#   sbatch --export=ALL,V3_MODEL=llama-3.1-8b,V3_CONDITION=described cluster/sharanga_v3_knowledge.sbatch
#   gpt-oss-120b also needs CONDA_ENV/TIKTOKEN exports as for its base run (experiment_log 2026-10-02).
#SBATCH --job-name=slay_v3_know
#SBATCH --no-requeue
#SBATCH --partition=gpu_h100_4
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=30:00:00
#SBATCH --output=results/controlled_h_v3_logs/know_%j.out

set -eo pipefail
cd "${SLURM_SUBMIT_DIR}"
source "${HOME}/miniconda3/etc/profile.d/conda.sh"
conda activate "${CONDA_ENV:-slaybench08}"
set -u
readonly MODEL="${V3_MODEL:?set V3_MODEL}"
readonly COND="${V3_CONDITION:?set V3_CONDITION}"
case "$MODEL" in llama-3.1-8b|gpt-oss-120b) ;; *) echo "model not in amendment 6"; exit 2 ;; esac
case "$COND" in described|renamed) ;; *) echo "unknown condition"; exit 2 ;; esac
export HF_HOME="${HF_HOME:-/scratch/${USER}/hf}" HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
export PYTHONUNBUFFERED=1 PYTHONIOENCODING=utf-8

python scripts/heldout_v3_knowledge.py status --model "$MODEL" --condition "$COND"

END=$(scontrol show job "$SLURM_JOB_ID" -o | tr ' ' '\n' | sed -n 's/^EndTime=//p')
DEADLINE=$(date -d "$END" +%s)
readonly PORT="$((20000 + SLURM_JOB_ID % 1000))"
readonly RECEIPT="results/controlled_h_v3_logs/kserver_${SLURM_JOB_ID}.json"
readonly SLOG="results/controlled_h_v3_logs/kserver_${SLURM_JOB_ID}.log"

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
setsid python scripts/heldout_v3_knowledge.py server --model "$MODEL" --condition "$COND" --port "$PORT" \
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
python scripts/heldout_v3_knowledge.py run --model "$MODEL" --condition "$COND" --port "$PORT" --receipt "$RECEIPT" \
  --authorize-model-inference --stop-at-unix "$DEADLINE"
python scripts/heldout_v3_knowledge.py status --model "$MODEL" --condition "$COND"
