# Expanded controlled-H confirmation on CSIS

This runs the separately frozen 2,016-query confirmation, not the old pilot.
Use the existing `slaybench08` environment and pinned Qwen3 cache. The commands
below are for the operator to execute; preparing them does not submit a job.
See `docs/controlled_h_confirmatory_runbook.md` for analysis and failure policy.
Private connection details must be supplied locally.

## Transfer ignored sources from Windows

In local repository PowerShell, transfer exactly the protocol's result sources
to the existing CSIS checkout. Configs and code travel through Git.

```powershell
$CsisLogin = "<username>@<login-node-ip>"
$Protocol = Get-Content configs/controlled_h_v2_confirmatory.json -Raw | ConvertFrom-Json
$Files = @($Protocol.sources.PSObject.Properties | ForEach-Object {
    if ($_.Value.kind -eq "result") { "results/" + $_.Value.filename }
})
scp $Files "${CsisLogin}:slay-the-spire-bench/results/"
```

## Prepare on the CSIS login node

```bash
cd ~/slay-the-spire-bench
git pull --ff-only origin main
# If conda is unavailable, source its private site-specific conda.sh first.
eval "$(conda shell.bash hook)"
conda activate slaybench08
export HF_HOME="${HOME}/scratch/hf_cache"
python scripts/controlled_horizon_confirmatory_analysis.py \
  --out results/controlled_h_v2_confirmatory_preflight.json
```

This validates sources, implementation, and planning without inference. Require
`planning_gate_passed: true`. If the pinned cache is missing, the existing
`bash cluster/csis_prefetch_qwen3_32b.sh` downloads/verifies it on the login node.
Do not reinstall or update the working environment unnecessarily.

## Allocate one GPU and keep this shell alive

The following resource request matches the existing CSIS pilot launcher.
Eight hours is the known request, not a runtime estimate for 2,016 queries.
Confirm the allocation can accommodate the full run before continuing beyond
smoke. If site policy offers a longer suitable allocation, use that approved
partition/time instead. A new server launch cannot resume this protocol's
checkpoint; a time limit, lost allocation, or changed receipt requires review.
There is no validated cross-job restart path under this freeze.

```bash
srun --partition=gpu-short --gres=gpu:a100-80gb:1 --time=08:00:00 \
  --ntasks=1 --cpus-per-task=8 --mem=64G --pty bash -l
```

The commands below run inside that GPU shell, from the same checkout:

```bash
cd ~/slay-the-spire-bench
eval "$(conda shell.bash hook)"
conda activate slaybench08
export HF_HOME="${HOME}/scratch/hf_cache"
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
mkdir -p results
export CONF_PORT="$((18000 + SLURM_JOB_ID % 1000))"
export CONF_URL="http://localhost:${CONF_PORT}/v1"
export CONF_RECEIPT="results/controlled_h_v2_confirmatory_server_${SLURM_JOB_ID}.json"
export CONF_LOG="results/controlled_h_v2_confirmatory_server_${SLURM_JOB_ID}.log"
export CONF_REPORT="results/controlled_h_v2_confirmatory_qwen3_32b.json"

# Refuse replacement runs and accidental connection to an older listener.
test ! -e "$CONF_REPORT" && test ! -e "${CONF_REPORT}.rows" || { echo "Existing run: inspect before proceeding"; exit 1; }
python - <<'PY'
import os, socket
with socket.socket() as sock:
    sock.bind(('127.0.0.1', int(os.environ['CONF_PORT'])))
print('Port available')
PY
test $? -eq 0 || exit 1

# Prevent interactive job control from making setsid fork away from $!.
set +m
setsid python scripts/controlled_horizon_confirmatory_server.py \
  --port "$CONF_PORT" --receipt "$CONF_RECEIPT" \
  --authorize-model-inference > "$CONF_LOG" 2>&1 &
CONF_PID=$!
trap 'kill -TERM -- "-$CONF_PID" 2>/dev/null || true' EXIT
CONF_READY=0
for attempt in $(seq 1 240); do
  kill -0 "$CONF_PID" 2>/dev/null || break
  if curl --silent --fail "$CONF_URL/models" | grep -q 'qwen3-32b'; then
    CONF_READY=1
    break
  fi
  sleep 5
done
if [ "$CONF_READY" -ne 1 ]; then tail -n 80 "$CONF_LOG"; exit 1; fi

python scripts/controlled_horizon_confirmatory.py \
  --provider local --phase smoke --base-url "$CONF_URL" \
  --server-receipt "$CONF_RECEIPT" --authorize-model-inference \
  --cluster-compute --out "$CONF_REPORT"
```

Inspect the saved smoke before continuing in this same shell:

```bash
python - <<'PY'
import json, os
from pathlib import Path
p = Path(os.environ['CONF_REPORT'])
manifest = json.loads(p.read_text())
r = json.loads(Path(str(p) + '.rows/000000.json').read_text())
print('completed=', len(manifest['completed_rows']), 'expected=', manifest['expected_queries'])
print('score=', r['score'], 'diagnostics=', r['diagnostics'])
print('response=', r['response_raw'])
assert all(r['score'][k] for k in ('parse_ok', 'schema_ok', 'legal'))
assert not r['diagnostics']['truncated'] and r['diagnostics']['execution_failure'] is None
PY
tail -n 40 "$CONF_LOG"
```

Require a passing smoke and enough remaining allocation time. A failed smoke
must be preserved; do not request a replacement draw. When proceeding:

```bash
python scripts/controlled_horizon_confirmatory.py \
  --provider local --phase run --base-url "$CONF_URL" \
  --server-receipt "$CONF_RECEIPT" --authorize-model-inference \
  --cluster-compute --out "$CONF_REPORT"
python scripts/controlled_horizon_confirmatory_analysis.py \
  --report "$CONF_REPORT" --out results/controlled_h_v2_confirmatory_analysis.json
```

Completion must say 2,016/2,016 with no pending slot. Analysis can deliberately
report non-confirmatory despite completion; inspect every validity gate.
If interrupted, preserve all files and follow the ambiguous-slot instructions
in the main runbook. Do not relaunch the model or remove a checkpoint to retry.
Exit the GPU shell after analysis to stop this process group and release it.

## Retrieve from local PowerShell

```powershell
scp "${CsisLogin}:slay-the-spire-bench/results/controlled_h_v2_confirmatory_qwen3_32b.json" results/
scp -r "${CsisLogin}:slay-the-spire-bench/results/controlled_h_v2_confirmatory_qwen3_32b.json.rows" results/
scp "${CsisLogin}:slay-the-spire-bench/results/controlled_h_v2_confirmatory_analysis.json" results/
scp "${CsisLogin}:slay-the-spire-bench/results/controlled_h_v2_confirmatory_server_*.json" results/
scp "${CsisLogin}:slay-the-spire-bench/results/controlled_h_v2_confirmatory_server_*.log" results/
python scripts/controlled_horizon_confirmatory_analysis.py --report results/controlled_h_v2_confirmatory_qwen3_32b.json --out results/controlled_h_v2_confirmatory_retrieved_analysis.json
```

Keep all retrieved traces ignored. Obtain independent per-sample audit before
reporting model findings. Linux vLLM startup and the interactive Slurm flow
have not been executed on the Windows development host.
