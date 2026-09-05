# Controlled-H pilot on BITS CSIS

This runbook is for the frozen Qwen3-32B controlled-H pilot only. It contains no
private login address, username, or internal support contact. Obtain those from the
private CSIS SOP and never commit them.

## 1. Update the checkout and prepare the environment

On the CSIS login node:

```bash
cd slay-the-spire-bench
git pull --ff-only origin main
# If `conda` is not already available, obtain its conda.sh path from the private
# CSIS SOP/module system and export it without committing the value:
export CONDA_SH="<path-to-conda.sh>"
source "${CONDA_SH}"
bash cluster/setup_vllm08.sh
bash cluster/csis_prefetch_qwen3_32b.sh
```

The prefetch is idempotent. It downloads only missing data and verifies the exact
frozen Hugging Face revision, `9216db5781bf21249d130ec9da846c4624c16137`.
Do not replace it with an unpinned `main` download.

## 2. Transfer the four ignored source artifacts

`results/**` is intentionally excluded from Git. From PowerShell on the laptop, run
the following after substituting the private values locally:

```powershell
$CsisLogin = "<username>@<login-node-ip>"
$RepoResults = "slay-the-spire-bench/results/"
$Files = @(
  "results/controlled_h_v2_combined_release_audit.json",
  "results/controlled_h_v2_combined_release_fixtures.json",
  "results/controlled_h_v2_frozen_full.json",
  "results/controlled_h_v2_silent_control_extension_full.json"
)
scp $Files "${CsisLogin}:${RepoResults}"
```

Do not copy `.env`; the job uses a localhost vLLM endpoint and needs no API key. The
pilot runner checks every frozen source hash before making a model call.

## 3. Submit the one-query exact-stack smoke

From the repository root on the login node:

```bash
sbatch --export=ALL,PILOT_PHASE=smoke cluster/csis_controlled_h_pilot.sbatch
squeue -u "$USER"
```

After it completes, inspect only the explicit job and output files:

```bash
sacct -j <job-id> --format=JobID,State,Elapsed,ExitCode,MaxRSS
tail -n 120 slay_h_pilot_<job-id>.out
tail -n 120 slay_h_pilot_<job-id>.err
tail -n 120 vllm_controlled_h_<job-id>.log
python - <<'PY'
import json
p = "results/controlled_h_v2_model_pilot_qwen3_32b_csis.json"
r = json.load(open(p, encoding="utf-8"))
row = r["rows"][0]
print({
    "completed_queries": r["completed_queries"],
    "parse_ok": row["score"]["parse_ok"],
    "schema_ok": row["score"]["schema_ok"],
    "legal": row["score"]["legal"],
    "truncated": row["diagnostics"]["truncated"],
    "finish_reason": row["diagnostics"]["finish_reason"],
})
PY
```

Proceed only if there is exactly one checkpointed query, it parsed, it was legal,
it was not truncated, the vLLM process exited with the job, and no source-hash or
model-revision check failed.

## 4. Repair a pre-v2.1 checkpoint without inference

This step is required only for a nonempty checkpoint created before action scorer
`controlled-action-scoring-v2.1`. Back up the ignored artifact, then run the explicit
deterministic migration from the repository root on the login node:

```bash
cp results/controlled_h_v2_model_pilot_qwen3_32b_csis.json \
  results/controlled_h_v2_model_pilot_qwen3_32b_csis_pre_v2_1.json
python scripts/controlled_horizon_model_pilot.py \
  --rescore-existing \
  --release-audit results/controlled_h_v2_combined_release_audit.json \
  --release-fixtures results/controlled_h_v2_combined_release_fixtures.json \
  --base-full-audit results/controlled_h_v2_frozen_full.json \
  --extension-full-audit results/controlled_h_v2_silent_control_extension_full.json \
  --out results/controlled_h_v2_model_pilot_qwen3_32b_csis.json
```

This command performs no model call and preserves every original score under
`score_before_action_normalization`. Inspect the printed correction counts and summary.
Do not resume if the artifact is not marked
`controlled-action-scoring-v2.1`, if its completed-query count changed, or if any
unexpected normalization occurred.

## 5. Resume the remaining queries

```bash
sbatch --export=ALL,PILOT_PHASE=full cluster/csis_controlled_h_pilot.sbatch
```

The same atomic result file is resumed; the first query is not repeated. On successful
completion the job also writes the frozen pilot-informed power analysis. Do not launch
a second full job concurrently against the same output path.

## 6. Retrieve the evidence

From PowerShell on the laptop:

```powershell
$CsisLogin = "<username>@<login-node-ip>"
scp "${CsisLogin}:slay-the-spire-bench/results/controlled_h_v2_model_pilot_qwen3_32b_csis.json" results/
scp "${CsisLogin}:slay-the-spire-bench/results/controlled_h_v2_power_qwen3_32b_csis.json" results/
scp "${CsisLogin}:slay-the-spire-bench/slay_h_pilot_<job-id>.out" results/
scp "${CsisLogin}:slay-the-spire-bench/slay_h_pilot_<job-id>.err" results/
scp "${CsisLogin}:slay-the-spire-bench/vllm_controlled_h_<job-id>.log" results/
```

Keep the logs under ignored `results/`; do not commit cluster paths, hostnames,
usernames, job IDs, or raw infrastructure logs. Audit the complete artifact locally
before interpreting any score or authorizing the confirmatory matrix.
