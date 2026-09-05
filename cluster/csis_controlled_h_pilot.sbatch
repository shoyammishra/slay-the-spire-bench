#!/bin/bash
# CSIS controlled-H Qwen3-32B pilot. Submit smoke first, inspect its one query,
# then submit full to resume the same checkpoint for the remaining 119 queries.
#
#   sbatch --export=ALL,PILOT_PHASE=smoke cluster/csis_controlled_h_pilot.sbatch
#   sbatch --export=ALL,PILOT_PHASE=full  cluster/csis_controlled_h_pilot.sbatch
#
# This launcher intentionally does not source cluster/lib.sh: cleanup is limited
# to the vLLM process group started by this job and never uses account-wide pkill.
#SBATCH --job-name=slay_h_pilot
#SBATCH --partition=gpu-short
#SBATCH --gres=gpu:a100-80gb:1
#SBATCH --time=08:00:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --output=slay_h_pilot_%j.out
#SBATCH --error=slay_h_pilot_%j.err

set -euo pipefail
cd "${SLURM_SUBMIT_DIR}"

readonly MODEL_REPO="Qwen/Qwen3-32B"
readonly MODEL_REVISION="9216db5781bf21249d130ec9da846c4624c16137"
readonly PILOT_DIGEST="465bab1dc23dddf5c5566c91943efaebc44ac3ab316ffb2003f15e01046a104f"
readonly SERVED_NAME="qwen3-32b"
readonly PILOT_ENV="${CONDA_ENV:-slaybench08}"
readonly PILOT_PHASE="${PILOT_PHASE:-smoke}"
readonly PILOT_OUTPUT="results/controlled_h_v2_model_pilot_qwen3_32b_csis.json"
readonly POWER_OUTPUT="results/controlled_h_v2_power_qwen3_32b_csis.json"
readonly RELEASE_AUDIT="results/controlled_h_v2_combined_release_audit.json"
readonly RELEASE_FIXTURES="results/controlled_h_v2_combined_release_fixtures.json"
readonly BASE_FULL="results/controlled_h_v2_frozen_full.json"
readonly EXTENSION_FULL="results/controlled_h_v2_silent_control_extension_full.json"
readonly VLLM_PORT="$((18000 + SLURM_JOB_ID % 1000))"
readonly BASE_URL="http://127.0.0.1:${VLLM_PORT}/v1"
readonly VLLM_LOG="vllm_controlled_h_${SLURM_JOB_ID}.log"

if [[ "${PILOT_PHASE}" != "smoke" && "${PILOT_PHASE}" != "full" ]]; then
  echo "ERROR: PILOT_PHASE must be 'smoke' or 'full'."
  exit 2
fi
if [[ "${PILOT_PHASE}" == "smoke" && -e "${PILOT_OUTPUT}" ]]; then
  echo "ERROR: ${PILOT_OUTPUT} already exists; inspect it instead of adding another smoke query."
  exit 2
fi
for required in "${RELEASE_AUDIT}" "${RELEASE_FIXTURES}" \
                "${BASE_FULL}" "${EXTENSION_FULL}"; do
  if [[ ! -f "${required}" ]]; then
    echo "ERROR: missing required controlled-H artifact: ${required}"
    exit 2
  fi
done
if ! command -v conda >/dev/null 2>&1; then
  if [[ -n "${CONDA_SH:-}" && -f "${CONDA_SH}" ]]; then
    source "${CONDA_SH}"
  else
    echo "ERROR: conda is unavailable. Load its module or export CONDA_SH to conda.sh."
    exit 2
  fi
fi
eval "$(conda shell.bash hook)"
conda activate "${PILOT_ENV}"

if [[ "${PILOT_PHASE}" == "full" ]]; then
  if [[ ! -f "${PILOT_OUTPUT}" ]]; then
    echo "ERROR: the one-query smoke checkpoint is absent; run PILOT_PHASE=smoke first."
    exit 2
  fi
  python - "${PILOT_OUTPUT}" "${PILOT_DIGEST}" <<'PY'
import json
import sys
report = json.load(open(sys.argv[1], encoding="utf-8"))
if report.get("protocol_digest") != sys.argv[2]:
    raise SystemExit("ERROR: smoke checkpoint uses a different pilot digest")
if report.get("provider") != "local":
    raise SystemExit("ERROR: smoke checkpoint is not from the local model provider")
if not report.get("provenance", {}).get("cluster_compute"):
    raise SystemExit("ERROR: smoke checkpoint lacks cluster-compute provenance")
if report.get("completed_queries", 0) < 1 or not report.get("rows"):
    raise SystemExit("ERROR: smoke checkpoint contains no completed query")
first = report["rows"][0]
if not (first["score"]["parse_ok"] and first["score"]["schema_ok"]
        and first["score"]["legal"] and not first["diagnostics"]["truncated"]):
    raise SystemExit("ERROR: first real-stack query did not pass the smoke gate")
if report.get("complete"):
    raise SystemExit("ERROR: pilot is already complete; do not submit it again")
print(f"Resuming validated checkpoint at {report['completed_queries']}/120 queries.")
PY
fi

export HF_HOME="${HF_HOME:-${HOME}/scratch/hf_cache}"
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
mkdir -p results

python - "${MODEL_REPO}" "${MODEL_REVISION}" <<'PY'
import sys
from huggingface_hub import snapshot_download
snapshot_download(repo_id=sys.argv[1], revision=sys.argv[2], local_files_only=True)
print("Pinned model snapshot is present in the offline cache.")
PY

VLLM_PID=""
cleanup() {
  if [[ -n "${VLLM_PID}" ]] && kill -0 "${VLLM_PID}" 2>/dev/null; then
    echo "Stopping this job's vLLM process group ${VLLM_PID}."
    kill -TERM -- "-${VLLM_PID}" 2>/dev/null || \
      kill -TERM "${VLLM_PID}" 2>/dev/null || true
    wait "${VLLM_PID}" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

if command -v ss >/dev/null 2>&1 && ss -ltn | grep -q ":${VLLM_PORT} "; then
  echo "ERROR: selected localhost port ${VLLM_PORT} is already in use; resubmit."
  exit 2
fi

python - <<'PY'
import importlib.metadata
expected = {"vllm": "0.8.5.post1", "transformers": "4.51.3"}
for package in ("vllm", "transformers", "torch"):
    actual = importlib.metadata.version(package)
    print(f"{package}={actual}")
    if package in expected and actual != expected[package]:
        raise SystemExit(
            f"ERROR: {package}={actual} differs from frozen {expected[package]}")
PY
echo "git_commit=$(git rev-parse HEAD)"
echo "pilot_phase=${PILOT_PHASE}"
echo "model_revision=${MODEL_REVISION}"
nvidia-smi --query-gpu=name,driver_version,memory.total \
  --format=csv,noheader || true

setsid vllm serve "${MODEL_REPO}" \
  --revision "${MODEL_REVISION}" \
  --served-model-name "${SERVED_NAME}" \
  --port "${VLLM_PORT}" \
  --tensor-parallel-size 1 \
  --max-model-len 16384 \
  --gpu-memory-utilization 0.95 \
  > "${VLLM_LOG}" 2>&1 &
VLLM_PID=$!

for attempt in $(seq 1 240); do
  if curl --silent --fail "http://127.0.0.1:${VLLM_PORT}/v1/models" \
      | grep -q "${SERVED_NAME}"; then
    echo "vLLM is ready after ${attempt} readiness checks."
    break
  fi
  if ! kill -0 "${VLLM_PID}" 2>/dev/null; then
    echo "ERROR: vLLM exited during startup."
    tail -n 80 "${VLLM_LOG}"
    exit 3
  fi
  if [[ "${attempt}" -eq 240 ]]; then
    echo "ERROR: vLLM did not become ready within 20 minutes."
    tail -n 80 "${VLLM_LOG}"
    exit 3
  fi
  sleep 5
done

pilot_args=(
  python scripts/controlled_horizon_model_pilot.py
  --provider local
  --base-url "${BASE_URL}"
  --authorize-model-inference
  --cluster-compute
  --release-audit "${RELEASE_AUDIT}"
  --release-fixtures "${RELEASE_FIXTURES}"
  --base-full-audit "${BASE_FULL}"
  --extension-full-audit "${EXTENSION_FULL}"
  --out "${PILOT_OUTPUT}"
)
if [[ "${PILOT_PHASE}" == "smoke" ]]; then
  pilot_args+=(--max-new-queries 1)
fi
"${pilot_args[@]}"

python - "${PILOT_OUTPUT}" <<'PY'
import json
import sys
report = json.load(open(sys.argv[1], encoding="utf-8"))
print({
    "complete": report["complete"],
    "completed_queries": report["completed_queries"],
    "expected_queries": report["expected_queries"],
    "summary": report["summary"],
})
PY

if [[ "${PILOT_PHASE}" == "full" ]]; then
  python scripts/controlled_horizon_power.py \
    --pilot-report "${PILOT_OUTPUT}" \
    --out "${POWER_OUTPUT}"
  echo "Full pilot and frozen power gate completed."
else
  echo "One-query checkpoint completed. Inspect it before submitting PILOT_PHASE=full."
fi
