#!/bin/bash
# ── Qwen3-235B-A22B-FP8 on Sharanga H200 (TP=2) — the top of the model ladder ──
# The largest model runnable under the DEFAULT QOS (decision_log 2026-07-23 §1;
# R1-671B stays parked — it needs ~700 GB = a full-node QOS exception).
#
# TWO STAGES ON PURPOSE. Run stage 1, read the numbers, THEN run stage 2:
#     bash cluster/sharanga_submit_235b.sh smoke      # ~2-4 h, 2 GPUs
#     bash cluster/sharanga_submit_235b.sh matrix     # only after smoke passes
#
# WHY NOT ONE FIRE-AND-FORGET COMMAND (unlike the qwen3-32b launcher)?
# Qwen3-235B-A22B-FP8 is ~240 GB, so it needs TP=2. The gpu_h200_8 per-user cap is
# 3 GPUs ⇒ TWO TP=2 jobs (4 GPUs) CANNOT run at once. The parallelism that landed
# the 32B matrix in ~2.7 days is gone: the four combos run STRICTLY SEQUENTIALLY.
# That makes total wall-clock ≈ 4 × per-combo, against a 96 h partition MaxTime per
# job — so per-combo throughput is no longer a detail, it decides whether the full
# matrix is even feasible. The smoke measures it. Sizing before measuring would be
# guessing with multi-day jobs (compute-cost ordering, handoff §5.3).
#
# WHAT TO READ OFF THE SMOKE BEFORE RUNNING STAGE 2 (all three, in order):
#   1. WALL TIME of the tiny pass. Anchors on identical smoke config:
#        qwen2.5-7b  57 s      qwen3-32b  53 min (≈55×)
#      Multiply the 32B's measured 27.6-37.1 h/combo by (235B_smoke / 32B_smoke).
#      >96 h/combo ⇒ the full matrix does NOT fit; scope down (fewer combos, or
#      N_RUN=0 to drop the run dimension, which is ~half the cost and the least
#      discriminating horizon — P4b put its between-model variance share at 2%).
#   2. TRUNCATION COUNTERS — the registered M3b budget protocol (decision_log
#      2026-07-13). Qwen3-235B-A22B is a HYBRID REASONING model with thinking ON by
#      default, i.e. exactly the DeepSeek-distill failure mode (budget-bound
#      deliberation: the 8k budget is spent inside <think> and the answer never
#      arrives). In the smoke JSON check:
#        turn.parse_ok_rate ≈ 1.0 and turn.samples[].fail_finish_reason absent
#        combat.truncation_errors == 0
#      Nonzero ⇒ do NOT launch the matrix on the matched-8k default; report both
#      budgets or use a non-thinking variant, and never blend the two.
#   3. SCORES SANITY — non-degenerate, not all-zero, JSON actually parsed.
#
# PREREQ: weights prefetched on the LOGIN node (~240 GB, hours — and /scratch
# purges after 15 days idle, so re-check before every rung):
#     conda activate slaybench
#     df -h /scratch/$USER                     # confirm >260 GB free FIRST
#     HF_HOME=/scratch/$USER/hf hf download Qwen/Qwen3-235B-A22B-FP8
#
# H200 submit rules encoded below (recon 2026-07-23): one --partition per job;
# <=4 CPUs per GPU (so 8 for TP=2); mem cap 300G; MaxTime 4 days.
# SHARED ACCOUNT: never `scancel -u` — cancel by job id only.
# ──────────────────────────────────────────────────────────────────────────────
set -euo pipefail
cd ~/slay-bench

STAGE=${1:-}
if [ "$STAGE" != "smoke" ] && [ "$STAGE" != "matrix" ]; then
  echo "usage: bash cluster/sharanga_submit_235b.sh {smoke|matrix}"
  echo "  smoke   tiny 4-dim gate on 2 GPUs; read wall time + truncation counters"
  echo "  matrix  four sequential combos (only after the smoke passed + was read)"
  exit 2
fi

# Repo id is a knob: Qwen ships several 235B variants (base A22B, and the later
# 2507 Instruct/Thinking splits). If `hf download` 404s, the id changed — set
# HF_REPO rather than editing this file, so the served name stays traceable.
REPO=${HF_REPO:-Qwen/Qwen3-235B-A22B-FP8}
NAME=${SERVED_NAME:-qwen3-235b-a22b-fp8}
# Run-level runs per seed. Default 5 = the "floor estimate" tier used for qwen3-32b
# (never blended with n=20 rows); 0 skips the run dimension entirely.
N_RUN=${N_RUN:-5}
# 0.95, not the usual 0.90: ~240 GB of weights in a 282 GB TP=2 budget leaves only
# ~14 GB at 0.90. Batch is ~1 and 16k of GQA KV is ~3 GB, so the extra is spare.
GPU_MEM_UTIL=${GPU_MEM_UTIL:-0.95}

HUB="/scratch/${USER}/hf/hub/models--${REPO//\//--}"
if [ ! -d "$HUB" ]; then
  echo "ERROR: $REPO is not prefetched (missing $HUB)."
  echo "On the login node:"
  echo "  df -h /scratch/\$USER    # need >260 GB free"
  echo "  conda activate slaybench && HF_HOME=/scratch/\$USER/hf hf download $REPO"
  exit 1
fi

if [ "$STAGE" = "smoke" ]; then
  # WALLTIME MUST EXCEED THE HEALTH BUDGET. Cold Lustre load scales with size: the
  # 32B's ~65 GB took 35+ min, so 239 GB extrapolates to ~2 h, plus compile. The
  # health wait therefore needs 180 min -- but an earlier version of this file paired
  # that with --time=03:00:00, i.e. the startup wait alone could consume the ENTIRE
  # walltime and the job would be killed having run zero benchmark samples on 2 GPUs.
  # 6 h = up to 3 h of cold start + 3 h for the tiny pass (the 32B smoke took 53 min;
  # a 235B MoE could be several times that).
  JID=$(HF_REPO="$REPO" SERVED_NAME="$NAME" TP_SIZE=2 \
        GPU_MEM_UTIL="$GPU_MEM_UTIL" HEALTH_WAIT_MIN=180 \
    sbatch --parsable --job-name=slay_smoke_235b --time=06:00:00 \
      --partition=gpu_h200_8 --gres=gpu:2 --cpus-per-task=8 --mem=250G \
      cluster/sharanga_smoke.sbatch)
  echo "235B smoke submitted: job $JID (gpu_h200_8, 2× H200, TP=2)"
  echo
  echo "Watch:   squeue -u \$USER  |  tail -f slay_smoke_${JID}.out"
  echo "Serving: tail -f vllm_smoke_${JID}.log     # OOM shows up here, not in the .out"
  echo "Then read, IN ORDER: wall time -> truncation counters -> scores"
  echo "  cat results/${NAME}_structured_seed42_sharanga_smoke.json"
  exit 0
fi

# ── matrix ────────────────────────────────────────────────────────────────────
# No --dependency chain between combos: the 3-GPU cap already serialises them
# (Slurm runs one TP=2 job and queues the rest), and chaining would add
# DependencyNeverSatisfied as a failure mode for zero benefit. --time is the full
# partition MaxTime because sequential execution removes all slack.
echo "Submitting 4 SEQUENTIAL combos (3-GPU cap ⇒ one TP=2 job runs at a time)."
echo "  model=$NAME  TP=2  N_RUN=$N_RUN  mem_util=$GPU_MEM_UTIL"
echo "  Expect ~4 × per-combo wall clock. Each job caps at 96 h; per-dimension"
echo "  partial saves bound any wall-kill loss to the in-flight dimension."
echo
for combo in "ironclad structured" "ironclad raw" "silent structured" "silent raw"; do
  # shellcheck disable=SC2086
  set -- $combo; C=$1; F=$2
  JID=$(CHAR=$C FMT=$F N_RUN=$N_RUN \
        HF_REPO="$REPO" SERVED_NAME="$NAME" TP_SIZE=2 \
        GPU_MEM_UTIL="$GPU_MEM_UTIL" HEALTH_WAIT_MIN=180 \
    sbatch --parsable --job-name=slay235_${C:0:2}_${F:0:3} --time=96:00:00 \
      --partition=gpu_h200_8 --gres=gpu:2 --cpus-per-task=8 --mem=250G \
      cluster/sharanga_matrix_combo.sbatch)
  echo "  combo ${C}/${F}: job ${JID}"
done

echo
echo "Submitted. Check:  squeue -u \$USER"
echo "Results land in results/${NAME}*_seeds42_1042_2042_3042_4042.json"
echo "On retrieval: scp to the laptop, per-sample audit (parse/truncation counters),"
echo "  re-run scripts/stats_rigor.py (new model joins every table automatically),"
echo "  then fold into experiment_log / findings / CLAUDE.md."
