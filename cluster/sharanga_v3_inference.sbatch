#!/bin/bash
# Confirmatory controlled-H v3 inference (held-out release), one model per job.
# Protocol: configs/controlled_h_v3_inference.json (frozen digest in
# scripts/heldout_v3_inference.py). The runner does an automatic 8-query smoke gate,
# then continues through the schedule in the same allocation. Resubmitting resumes;
# no query is ever retried (an in-flight query lost to a crash is recorded as a failure).
#   sbatch --export=ALL,V3_MODEL=qwen3-8b  cluster/sharanga_v3_inference.sbatch
#   sbatch --export=ALL,V3_MODEL=qwen3-14b cluster/sharanga_v3_inference.sbatch
# Prompt-definition ablation (Amendment 2): add V3_CONDITION=defined
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
case "$MODEL" in qwen3-8b|qwen3-14b|llama-3.1-8b|deepseek-r1-distill-14b|qwen2.5-7b|mistral-7b|qwen3-32b) ;; *) echo "unknown model"; exit 2 ;; esac
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
READY=0
for _ in $(seq 1 240); do
  kill -0 "$PID" 2>/dev/null || break
  if curl --silent --fail --max-time 5 "http://localhost:${PORT}/v1/models" | grep -q "$MODEL"; then
    READY=1; break
  fi
  sleep 5
done
if [[ "$READY" -ne 1 ]]; then
  echo "ERROR: server not ready"; tail -n 80 "$SLOG"; exit 3
fi
python scripts/heldout_v3_inference.py run --model "$MODEL" --condition "$COND" --port "$PORT" --receipt "$RECEIPT" \
  --authorize-model-inference --stop-at-unix "$DEADLINE"
python scripts/heldout_v3_inference.py status --model "$MODEL" --condition "$COND"
