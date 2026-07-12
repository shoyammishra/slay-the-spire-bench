#!/bin/bash
# cluster/parse_probe.sbatch — parse-failure diagnostics probe (2026-07-12).
#
# QUESTION IT ANSWERS: are the DeepSeek distills' parse failures TRUNCATIONS
# (the model thinks past max_tokens=8000 and the JSON answer is never emitted;
# finish_reason=length / unclosed <think>) or MALFORMED OUTPUT within budget?
# The matrix runs predate the diagnostics instrumentation (finish_reason +
# truncated_think, benchmark.py 2026-07-12), so this re-runs a SMALL probe cell
# with the instrumented harness. Requires the repo clone on the cluster to be
# pulled to a commit that includes the instrumentation.
#
# Reads results in: turn summary `parse_fail_n` vs `parse_fail_truncated`;
# combat summary `avg_json_parse_errors` vs `avg_truncation_errors` (subset)
# vs `avg_illegal_action_errors` (valid JSON, illegal action — NOT a parse
# failure; the old conflated `avg_parse_errors` is json+illegal, unchanged).
#
# --run-tag parse_probe suffixes all output stems (`*_parse_probe.json`) so the
# 2026-06-22 matrix files are NEVER overwritten. Single seed, small n — this is
# a diagnostic, not a benchmark cell; do not fold its scores into the matrix.
#
# Default model: deepseek-r1-distill-7b (the collapse case, worst parse rates).
# For the 14b (worst cell = Silent raw), override:
#   HF_REPO=deepseek-ai/DeepSeek-R1-Distill-Qwen-14B SERVED_NAME=deepseek-r1-distill-14b \
#     PROBE_CHAR=silent sbatch --export=ALL cluster/parse_probe.sbatch
#
# ⚠️ SUBMIT GOTCHAS (learned 2026-07-12):
#  - gpu-3day REQUIRES an explicit QOS pin or the submit is rejected with
#    QOSMaxWallDurationPerJobLimit:
#      sbatch --partition=gpu-3day --qos=test-gpu --time=06:00:00 cluster/parse_probe.sbatch
#  - NODE CONTENTION: --gres does NOT guarantee a free GPU here; jobs have landed
#    on `mix`-state nodes where another user pinned both A100s -> CUDA-OOM. Steer
#    to an idle node:  sinfo -p gpu-3day -N -o "%n %t"  (pick t=idle), then add
#      --nodelist=<idle-node>   (e.g. --nodelist=csis.cn3)
#    The hardened lib.sh pre-flight VRAM check will fail fast if the GPU is busy.
#SBATCH --job-name=slay_parse_probe
#SBATCH --partition=gpu-1day
#SBATCH --gres=gpu:a100-80gb:1
#SBATCH --time=06:00:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --output=slay_parse_probe_%j.out
#SBATCH --error=slay_parse_probe_%j.err

cd "${SLURM_SUBMIT_DIR}"
source /nfs_home/software/miniconda/etc/profile.d/conda.sh
conda activate "${CONDA_ENV:-slaybench}"   # R1 distills are Qwen2 arch -> vLLM 0.6.6 ok
export HF_HOME=~/scratch/hf_cache

export HF_REPO="${HF_REPO:-deepseek-ai/DeepSeek-R1-Distill-Qwen-7B}"
export SERVED_NAME="${SERVED_NAME:-deepseek-r1-distill-7b}"
PROBE_CHAR="${PROBE_CHAR:-ironclad}"

source cluster/lib.sh
start_vllm
wait_for_vllm

# Reasoning distill: long <think> generations — keep the generous client timeout.
export LOCAL_TIMEOUT="${LOCAL_TIMEOUT:-600}"

# Both formats: raw had the worse parse rates in the matrix, structured is the
# contrast. turn n=20 (single-shot calls, the clean parse metric) + combat n=3
# (the sequential loop where errors compound). Seed 42 only.
for FMT in structured raw; do
  echo "=== parse probe, model=${SERVED_NAME}, character=${PROBE_CHAR}, format=${FMT} ==="
  python run_benchmark.py --provider local --base-url "${BASE_URL}" \
      --model "${SERVED_NAME}" --character "${PROBE_CHAR}" \
      --only turn combat --n-turn 20 --n-combat 3 \
      --seed 42 --format "${FMT}" --run-tag parse_probe
done

echo "=== parse probe (${SERVED_NAME}, ${PROBE_CHAR}) done ==="
echo "Read: results/${SERVED_NAME}*_seed42_parse_probe.json ->"
echo "  turn.parse_fail_truncated / turn.parse_fail_n ; combat.avg_truncation_errors vs avg_json_parse_errors"
