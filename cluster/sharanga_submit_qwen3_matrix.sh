#!/bin/bash
# ── Fire-and-forget qwen3-32b FULL matrix on Sharanga H200 (smoke-gated) ───────
# Paste ONE command on the login node:
#     bash cluster/sharanga_submit_qwen3_matrix.sh
#
# What it submits:
#   1) a qwen3-32b SMOKE (tiny 4-dim pass, --run-tag = no matrix overwrite) as a
#      serving/env GATE — validates that qwen3-32b actually serves + emits
#      parseable JSON on this cluster before any multi-day job runs.
#   2) FOUR combo jobs (ironclad/silent × structured/raw), each --dependency=
#      afterok on the smoke and each writing its OWN result file → up to 3 run
#      concurrently under the gpu_h200_8 per-user 3-GPU QOS cap, no file race.
#
# If the smoke FAILS (crash / OOM / never-serves), the four combos stay PENDING
# forever (DependencyNeverSatisfied) and burn NO GPU — you cancel + investigate
# on return. If the smoke passes, the combos launch automatically. Total matrix
# wall-clock ≈ one combo (~20–50 h) since 3 of 4 run in parallel + 1 queues.
#
# NOTE (residual risk, honest): afterok gates on the smoke EXITING 0, not on
# result quality. qwen3-32b already parsed on CSIS (it produced real synergy
# numbers), so the main Sharanga-specific risk (serving/env) IS gated; if it
# over-deliberates here the combos still run but partial-save + the parse
# counters keep everything diagnosable — nothing is lost.
# ──────────────────────────────────────────────────────────────────────────────
# Knobs (env):
#   N_RUN       run-level runs/seed passed to each combo (default 20 = matrix n;
#               5 = cheaper floor estimate ~12–17 h/combo; 0 = skip run-level).
#   SKIP_SMOKE  1 = don't submit the smoke gate (use when qwen3-32b already passed
#               the smoke this session — combos then submit with NO dependency).
# Examples:
#   bash cluster/sharanga_submit_qwen3_matrix.sh                 # full: smoke + n=20
#   N_RUN=5 SKIP_SMOKE=1 bash cluster/sharanga_submit_qwen3_matrix.sh   # relaunch, run n=5
set -euo pipefail
cd ~/slay-bench

N_RUN=${N_RUN:-20}
SKIP_SMOKE=${SKIP_SMOKE:-0}

# 0) prefetch guard — the jobs fail-fast on missing weights anyway, but catch it
#    here before we submit a dependency chain that can't run.
HUB="/scratch/${USER}/hf/hub/models--Qwen--Qwen3-32B"
if [ ! -d "$HUB" ]; then
  echo "Qwen3-32B is not prefetched (missing $HUB)."
  echo "Run first on the login node:"
  echo "  conda activate slaybench && HF_HOME=/scratch/\$USER/hf hf download Qwen/Qwen3-32B"
  exit 1
fi

# 1) smoke gate — bigger health budget (60 min) + walltime (2.5 h) for the 32B's
#    cold Lustre load; --run-tag inside the smoke keeps it out of the matrix.
#    Pin to gpu_h200_8 (the smoke file defaults to gpu_a100_8, which was DOWN for
#    driver stress-testing 2026-07-23+; also correct on principle — gate on the
#    SAME GPU type the combos run on). H200 rule: --cpus-per-task=4 for 1 GPU.
DEP=""
if [ "$SKIP_SMOKE" = "1" ]; then
  echo "SKIP_SMOKE=1 → no gate (qwen3-32b already validated); combos submit directly."
else
  SMOKE=$(HF_REPO=Qwen/Qwen3-32B SERVED_NAME=qwen3-32b HEALTH_WAIT_MIN=60 \
    sbatch --parsable --job-name=slay_smoke_q3 --time=02:30:00 \
    --partition=gpu_h200_8 --cpus-per-task=4 \
    cluster/sharanga_smoke.sbatch)
  echo "smoke gate submitted: job $SMOKE (gpu_h200_8)"
  DEP="--dependency=afterok:${SMOKE}"
fi

# 2) four combos, each its own (char,fmt) → own file, run-level at N_RUN.
echo "combos: N_RUN=$N_RUN run-level runs/seed"
for combo in "ironclad structured" "ironclad raw" "silent structured" "silent raw"; do
  # shellcheck disable=SC2086
  set -- $combo; C=$1; F=$2
  JID=$(CHAR=$C FMT=$F N_RUN=$N_RUN sbatch --parsable \
    ${DEP} --job-name=slay_${C:0:2}_${F:0:3} \
    cluster/sharanga_matrix_combo.sbatch)
  echo "  combo ${C}/${F}: job ${JID}  ${DEP:-(no gate)}"
done

echo
echo "Submitted. Check:  squeue -u \$USER"
echo "On return: aggregates land in results/qwen3-32b*_seeds42_1042_2042_3042_4042.json;"
echo "  scp them to the laptop, then fold into the docs."
