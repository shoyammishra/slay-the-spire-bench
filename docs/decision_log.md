# Decision Log

## 2026-08-09 — 235B matrix: GO at the full scope (`N_RUN=5`), no scope-down

**Context.** The 235B smoke (job 266749) answered all three registered read-offs
(experiment_log 2026-08-09). The decision the two-stage launcher exists to make — *does the
full four-combo matrix fit?* — is now answerable from measurement instead of extrapolation.

### 1. Sizing decision: run all four combos, keep run-level

**The constraint.** 239 GB ⇒ TP=2; the 3-GPU per-user H200 cap means two TP=2 jobs cannot
co-run, so the combos are **strictly sequential** and total wall clock ≈ 4 × per-combo against
a 96 h `MaxTime` *per job*.

**The measurement.** Smoke 75 m 35 s vs the 32B's 53 min on identical config = **1.43×**;
applied to the 32B's measured 27.6–37.1 h/combo ⇒ **≈39–53 h/combo**, ≈6.6–8.8 days total.

**Options.** (a) full matrix at `N_RUN=5` ≈ 6.6–8.8 days; (b) `N_RUN=0` ≈ 3.3–4.4 days,
dropping the run horizon; (c) fewer combos.

**Chose (a).** Every combo clears the cap with ~2× headroom, so the registered scope-down
ladder is not triggered — and the ladder was always conditional on *not fitting*, never a
preference. Scoping down would also break the deliberate symmetry with qwen3-32b, which has
all four dimensions × all four combos at `N_RUN=5`; an asymmetric top rung would put the
frontier model's run-level cell in a different instrument tier from the model it is meant to
be compared against. Cost of being wrong is bounded: per-dimension partial saves mean a
wall-kill can only lose the in-flight (run) dimension, with turn+combat+synergy already on disk.

**Comparability:** run-level stays the **`N_RUN=5` floor-estimate tier** (25 runs/combo) —
never blended with the n=20 run rows, exactly as for qwen3-32b.

### 2. Token budget: matched-8k CONFIRMED for this model

The registered M3b protocol (2026-07-13) required reading truncation diagnostics *before*
committing a frontier model to a budget. All counters came back **zero** across turn, combat
and synergy. ⇒ the matrix runs on the matched-8k default; **no raised-budget condition, no
dual reporting.** This was not a foregone conclusion: Qwen3-235B-A22B is a hybrid-reasoning
model with thinking on by default, i.e. the exact structural setup that made the DeepSeek
distills spend the whole budget inside `<think>`.

**What this settles for the paper:** budget-bound deliberation is an **R1-distill** property,
not a property of reasoning models. Three qwen3 rungs (7B, 32B, 235B) are parse-clean at the
same budget. Frame the DeepSeek mechanism finding as distill-specific — an over-generalisation
to "reasoning models" is now contradicted by our own data at three scales.

### 3. Compile cache: do NOT wipe it before the matrix

The 2026-08-08 rule ("wipe `~/.cache/vllm/torch_compile_cache` when changing these vars")
applies **to a config change**, and is now actively counterproductive: the smoke populated the
cache with a *good* inductor graph for exactly the config the matrix will serve (same repo,
TP=2, `--max-model-len 16384`, `--gpu-memory-utilization 0.95`, same flags). Wiping would pay
the compile cost four more times for nothing. The rule is unchanged in substance — wipe when
the serve config changes, not on principle.

### 4. Gate integrity confirmed

The smoke and the combo file now issue a **byte-identical `vllm serve` invocation** and export
the identical six env vars; they differ only in log filename, port, and `LOCAL_TIMEOUT`
(600 s in the combo, unset ⇒ 300 s in the smoke, which passed). This is the property job
265759 lacked and died for. A gate is only worth its GPU-hours if it serves the model the way
the gated run will.

## 2026-08-08 — FlashInfer is structurally unbuildable on Sharanga: the full account + the validated serving config

**Context.** First attempt to serve Qwen3-235B-A22B-FP8 at TP=2. The model is fine and the
memory arithmetic was right; **every** failure was FlashInfer's JIT compiler.

### 1. The symptom chain (three kernels, each ~8 min to discover)

| # | Kernel | Reached via | Failure |
|---|---|---|---|
| 1 | `trtllm_mnnvl_comm` | TP>1 communication | `ld: cannot find -lcuda` |
| 2 | `flashinfer_trtllm_fused_allreduce_norm` | the `fuse_allreduce_rms` compile pass | baked into the inductor graph, fails at `profile_run` |
| 3 | `fp8_blockscale_gemm_90` | `linear_backend='auto'` → DeepGEMM | ninja build fails |

**Why no previous run ever hit this:** every earlier rung was BF16, dense, TP=1. The comm
kernels require TP>1; blockscale/DeepGEMM are FP8-only. The 2026-07-23
`VLLM_USE_FLASHINFER_SAMPLER=0` workaround was the same root cause surfacing on the one path
a TP=1 BF16 model does touch.

**Root cause.** FlashInfer JIT compiles NVIDIA TRT-LLM internals with the conda toolchain
against a partial CUDA install. Two distinct sub-problems: (a) `libcuda.so` **exists** at
`/usr/lib64` on compute nodes, but conda's `x86_64-conda-linux-gnu-ld` only searches
`$CONDA_PREFIX/lib` and its sysroot, so `-lcuda` never resolves; (b) even with that fixed,
further kernels fail to build.

### 2. DECISION: disable FlashInfer, do not try to fix it

**Options.** (a) install a full CUDA toolkit — blocked in practice: **home quota is 40 GiB
with ~29 used**, no root, and it would change the environment that produced every existing
row; (b) ask the professor for a CUDA-toolkit module — spends goodwill on a dependency we do
not need; (c) **disable every FlashInfer path** — vLLM has native equivalents for all of them.

**Chose (c).** Validated 2026-08-08: server up in **160 s** and scoring a clean pass.

```
export VLLM_USE_FLASHINFER_SAMPLER=0        # 2026-07-23, TP=1 sampler
export VLLM_ALLREDUCE_USE_FLASHINFER=0      # kernel 1
export VLLM_BLOCKSCALE_FP8_GEMM_FLASHINFER=0  # kernel 3
export VLLM_USE_DEEP_GEMM=0
export VLLM_MOE_USE_DEEP_GEMM=0             # pre-empts the MoE DeepGEMM path
export LIBRARY_PATH=/usr/lib64:$LIBRARY_PATH  # link-time only; installs nothing
vllm serve … --disable-custom-all-reduce \
             --compilation-config '{"pass_config":{"fuse_allreduce_rms":false}}'   # kernel 2
```

**COMPARABILITY — the reason this is safe to apply unconditionally:** all four new env vars
and both serve flags are **no-ops for a BF16 dense model at TP=1** (allreduce paths need TP>1;
blockscale/DeepGEMM are FP8-only). The qwen3-32b rows therefore remain valid and that sbatch
stays re-runnable. Now baked into `sharanga_smoke.sbatch` + `sharanga_matrix_combo.sbatch`,
with the serve flags gated behind `TP_SIZE > 1`.

**⚠️ Wipe `~/.cache/vllm/torch_compile_cache` when changing these.** The FlashInfer op is
compiled *into* the inductor graph, and it is not established that these env vars participate
in the compile-cache key — a stale graph replays the old failure. Cheap insurance
(recompile ≈ minutes) against an expensive misdiagnosis.

**ADDENDUM 2026-08-09 — even a SUCCESSFULLY BUILT FlashInfer kernel is unusable here, which
closes the "fix it" option for good.** Once `LIBRARY_PATH=/usr/lib64` let the JIT link,
`trtllm_comm.so` and `trtllm_mnnvl_comm.so` were produced and cached. Job 265759 then failed
at **load** time, not build time:

```
Failed to load dynamic shared library …/trtllm_mnnvl_comm.so
/lib64/libstdc++.so.6: version `GLIBCXX_3.4.32' not found
```

The kernels are compiled by conda's g++ 15.2.0 against conda's newer libstdc++, but the
loader resolves the **system** `/lib64/libstdc++.so.6`, which is older. Making them loadable
would mean forcing `LD_LIBRARY_PATH=$CONDA_PREFIX/lib` for the whole vLLM process — shadowing
system libraries globally to satisfy an optional dependency we do not need. **Not done.**
Disabling stands as the decision, now on two independent grounds (unbuildable *and*
unloadable). **Delete stale artifacts when they exist** — a cached broken `.so` is loadable-
looking state that fails only at runtime:
`rm -rf ~/.cache/flashinfer/*/*/cached_ops/trtllm_comm ~/.cache/flashinfer/*/*/cached_ops/trtllm_mnnvl_comm`

**Root cause of job 265759 (my error, recorded so it is not repeated): the TP>1 serve flags
were added to `sharanga_matrix_combo.sbatch` but NOT to `sharanga_smoke.sbatch`.** The gate
served with a different configuration from the run it gates, which is worse than having no
gate. Both files now derive `EXTRA_SERVE_ARGS` identically, gated on `TP_SIZE > 1`.
**Durable rule: the smoke and the combo file must serve with byte-identical flags — if a knob
is added to one, it goes in both, in the same commit.**

### 3. Measurements that settle earlier open questions

- **Weights load in 44.55 s**; server ready in **160 s** total. The ~2 h cold-start budget
  extrapolated from the 32B was wrong by two orders of magnitude — startup contributes
  essentially nothing to per-combo cost. The generous 6 h walltime / 180 min health budget
  stay (harmless, and a genuinely cold node is untested).
- **`Model loading took 110.19 GiB` per worker** ⇒ ~220 GiB total, matching the 239.1 GB
  manifest, leaving **~24 GiB per GPU** free at `--gpu-memory-utilization 0.95`.
  **The memory arithmetic is confirmed; `--max-model-len 16384` is retained** and the
  contingency plan to reduce context is not needed.

### 4. Process lessons (durable)

- **Never run a measurement pass inside a time-boxed interactive session you may walk away
  from.** The 2 h `srun` expired unattended mid-pass ⇒ **no results file, zero data**, despite
  the serving problem being solved. Interactive sessions are for *debugging serving*;
  measurement belongs in batch, where per-dimension partial saves protect the work.
- **Never reuse a log filename across attempts.** Attempt A's log was overwritten by attempt
  B, so whether A failed on `-lcuda` could not be confirmed. Use `probe1/2/3…`.
- **Enumerate the knobs, don't guess them.** `python -c "import vllm.envs as e; print(dir(e))"`
  named all five variables in one shot after three failed guesses had cost ~25 minutes.
- Grep from the FIRST `ERROR` (`awk '/ERROR/{f=1} f'`), not the tail — vLLM's tail shows only
  the outer wrapper (`Engine core initialization failed`), never the cause.
- **Login shells have conda on PATH but no env activated** (`conda init` is in the shared
  `.bashrc` with `auto_activate_base false`), so a login-node script that imports project
  packages dies with a bare `huggingface_hub not importable`. `sharanga_submit_235b.sh` now
  self-activates — wrapped in `set +u` / `set -u`, since conda's `cuda-nvcc` hooks reference
  unbound vars and abort under `set -u` (the 2026-07-24 blocker). **Any future login-node
  script that imports project packages must do the same.**

## 2026-08-07 (latest) — Qwen3-235B-A22B-FP8 rung: two-stage launch, and why the 32B playbook does not transfer

**Context.** Top of the registered model ladder (2026-07-23 §1): the largest model runnable
under the default QOS. Prefetched and verified this session; smoke pending. R1-671B stays
parked (~700 GB ⇒ full-node QOS exception).

### 1. TP=2 under a 3-GPU cap destroys the parallelism — this is the governing constraint

Qwen3-235B-A22B-FP8 is **239.1 GB** (measured from the Hub manifest, not estimated), so it
needs **TP=2** on 141 GB H200s. The `gpu_h200_8` per-user cap is **3 GPUs**, therefore **two
TP=2 jobs cannot co-run**. The qwen3-32b matrix landed in ~2.7 days only because 1 GPU/combo
let 3 of 4 combos run concurrently; here the four combos are **strictly sequential**.

Consequence: total wall-clock ≈ **4 × per-combo**, against a **96 h MaxTime per job**. Per-combo
throughput is no longer a detail — it decides whether the full matrix is feasible at all.

**Decision: launch in TWO STAGES (`sharanga_submit_235b.sh {smoke|matrix}`), not
fire-and-forget.** The 32B launcher submitted a smoke gate and the combos together with
`--dependency=afterok`, which was right when the matrix cost ~one combo of wall-clock. Here the
smoke's *measured throughput* determines the scope decision, so a human must read it before
stage 2. Sizing a multi-day sequential chain from an estimate would be guessing (handoff §5.3).

**Registered scope-down ladder if the smoke says >96 h/combo:** drop run-level first
(`N_RUN=0`) — it is ~half the cost and P4b measured its between-model variance share at **2%**,
the least discriminating horizon; then cut to one character; then one format.

### 2. `GPU_MEM_UTIL` raised to 0.95 for this rung only (default stays 0.90)

239.1 GB of weights in a 282 GB TP=2 budget leaves **~15 GB at 0.90** vs **~29 GB at 0.95**.
Batch is ~1 and 16k of GQA KV is ~3 GB, so the extra is genuinely spare rather than risky.
If it OOMs anyway, the registered first move is `--max-model-len 8192` (halves KV) *before*
touching utilisation further.

### 3. Base `Qwen3-235B-A22B-FP8`, not the 2507 Instruct/Thinking split

Keeps the **qwen3 family axis consistent** (7B → 32B → 235B, same series and same
thinking-capable mode) so the scale line is not confounded by a mode change. The risk is
budget-bound deliberation (the DeepSeek-distill failure), but qwen3-32b was **parse-clean at
the same 8k budget**, which is direct evidence the family handles it. `HF_REPO` is a knob;
the smoke's truncation counters are the gate, per the registered M3b budget protocol
(2026-07-13).

### 4. Two staging bugs found and fixed BEFORE any GPU was claimed

- **`sharanga_smoke.sbatch` had no `--tensor-parallel-size`** — it could not serve any model
  too big for one card, so it would have failed this rung *at the gate*, before a single combo
  ran. `TP_SIZE` + `GPU_MEM_UTIL` now parametrized in both the smoke and the combo file.
- **Smoke walltime (3 h) was ≤ its own health budget (180 min)** — a cold start could consume
  the entire allocation and be wall-killed having run **zero** samples while holding 2× H200.
  Now 6 h. **Durable rule: walltime must strictly exceed the health-wait budget, with room for
  the actual work.**

### 5. Prefetch completeness is verified against the manifest, never by `du`

`du -sh` reported **212 GiB** for a **complete** 239.1 GB model — a 5% gap that looks exactly
like truncation but was Xet chunk dedup plus block accounting. Meanwhile the sbatch guards only
check that the cache *directory exists*, which a truncated download passes.

**Decision: new `cluster/verify_prefetch.py`** — checks every file in the remote manifest for
presence and exact byte size, reports orphaned `*.incomplete` blobs, and is wired into the
235B launcher's guard so it **refuses to submit** an unverified model. Login-node only (needs
network; `HF_HUB_OFFLINE` must be unset). Generic over repo id, so every later rung gets it.

### 6. Operational gotchas learned this session (durable)

- **A multi-line paste into `tmux new` is swallowed.** The session was created but the
  `conda activate` / `hf download` lines never ran — the pane held only the login banner while
  the outer shell looked busy. Use `tmux send-keys -t <sess> '<cmd>' C-m` (discrete lines), or
  `nohup env HF_HOME=… hf download … > ~/log 2>&1 &`. Verify with
  `tmux capture-pane -p -t <sess> | tail`, which reads the pane **without attaching**.
- **A returning shell prompt does not mean the download died.** It kept running; relaunching
  "the failed" download produced **two concurrent processes writing the same HF cache**,
  racing on the same blobs.
- **Kill by explicit PID on the shared account.** `pkill -f "hf download"` would also kill
  another student's transfer — the same reasoning as the standing "never `scancel -u`" rule.
- Unauthenticated Hub pulls warn about lower rate limits; setting `HF_TOKEN` is the cheap
  mitigation for large multi-shard fetches.

## 2026-08-07 (later) — P4b statistical rigor pass: unit of analysis, test family, and what it corrected

**Context.** Backlog row P4b (`handoff.md` §6; `review_2026-07-14.md` §2.4 item 1) — the
external review named statistics as a top-5 rejection reason, and the seed-matched format
ablation *had never actually been tested as paired data*. Zero GPU: everything below is
computed from files already on disk. Deliverables: **`scripts/stats_rigor.py`** (reusable,
model-discovering), **`tests/test_stats.py`** (26 known-answer tests), **`docs/stats_report.md`**
(committed human artifact), `results/stats/stats_rigor.json` (machine artifact, gitignored).

**§5.1 data-validity classification: NONE of the three invalidating rows is touched.** No
engine change, no prompt byte, no scoring change — the script only reads results. No published
mean moves. Comparability is untouched by construction.

### 1. Unit of analysis — dictated by what was persisted, not by preference

| Dimension | Unit | Why |
|---|---|---|
| turn / combat / run | **seed** (5 per combo) | `turn.samples[]`/`combat.samples[]` were instrumented 2026-07-13, *after* the matrix ran — only qwen3-32b has them. Per-seed summaries are all that exist for the other five models. |
| synergy | **sample** (100 per model×character) | `synergy.samples[]` has persisted since 2026-06-10 for every combo. |

**Precondition verified before any paired test, not assumed:** for all **60** (model ×
character × seed) triples, the structured and raw sample streams carry byte-identical
`(expert_archetype, expert_pick_idx)` sequences — the two formats saw the *same fixtures in
the same rotated offer positions*. The script re-checks this on every run and refuses
sample-level tests if it ever fails.

### 2. Exact sign-flip permutation, not a t-test — and its hard power ceiling

**Choice:** exact two-sided sign-flip permutation on the 5 seed-matched differences. n=5
cannot support a normality assumption, and the design's exchangeability under H0 is exactly
what a permutation test needs.

**The consequence had to be registered, not discovered later: 2⁵ = 32 sign assignments ⇒ the
smallest attainable two-sided p for ANY single combo is 0.0625.** No per-combo test in this
matrix can reach α=0.05 — *by construction, not by weakness of effect*. Therefore per-combo
rows are **descriptive**, and inference is carried by (a) the pooled stratified permutation
test across all 12 model×character strata and (b) sample-level McNemar on synergy. This
ceiling is printed in the report header and must travel with any per-combo p-value cited.

### 3. Two pooled tests, deliberately — magnitude AND direction

The stratified permutation statistic is a *mean of stratum means*, so one model with a huge
effect can produce a "significant" pooled result while the sign flips across models. Added an
exact **sign test on per-stratum direction** (ties dropped) alongside it. A claim is called
**general** only when both are significant; magnitude-only results are labelled
`SUPPORTED-MAGNITUDE-ONLY` and must be reported as *model-dependent*. This is what kept the
turn-level result honest (§6 below).

### 4. Multiplicity, equivalence, and boundary cells

- **Holm–Bonferroni** within each family (family = one metric across the 12 combos).
- **A non-significant result is never reported as "no effect."** Format *insensitivity* is
  tested as **equivalence** (TOST via the 90% bootstrap CI) against a **pre-declared margin of
  ±0.05** — chosen as the instrument's own granularity, since one sample in 20 moves any rate
  by exactly 0.05. Outcomes are `equivalent` or `inconclusive`; "inconclusive" is a real,
  reportable state that means *neither* equivalence nor difference was shown.
- **Clopper–Pearson exact intervals for every boundary cell.** A bootstrap of a constant
  vector returns a zero-width CI, which reads as certainty and is not. `turn dmg_ratio` is
  included at the boundary only, where its k/n reading is exact (mean 1.0 with all ratios ≤ 1
  ⇒ every sample hit the oracle).
- **Bootstrap:** percentile, B=10,000, fixed RNG seed 20260807 ⇒ byte-reproducible. Seed-level
  CIs resample 5 numbers and are labelled **COARSE** everywhere they appear. Synergy uses a
  **hierarchical** (seed → sample) bootstrap because the same 20 fixtures recur across seeds;
  a flat bootstrap would understate the interval.

### 5. Run-level compared against a *run-seed-matched* greedy anchor (new, and it mattered)

`run_all` draws run seeds `range(base+300, base+300+n_run)`; `scripts/greedy_baseline.py`
swept the same scheme at n_run=20 **and kept per-run records**. So greedy can be subset to the
*exact same run seeds* the model played before pairing. Adopted as the standard run-level
comparator — it is strictly tighter than comparing against greedy's 100-run global average.
**This immediately corrected a published number** (§6, C5).

### 6. What the pass CORRECTED (the reason it was worth doing)

1. **"combat/run are format-insensitive on outcome" — NOT supported as stated.** Format
   reaches combat `hp_ratio` with a consistent direction (10 of 12 strata favour structured,
   sign test p=0.039, pooled p=0.0001). Diagnosis: the old reading was a **ceiling artifact** —
   for `win_rate`, *every* combo whose effect exceeds the margin sits below the combat ceiling
   (all four R1-distill combos); models that win 100% of fights leave format nothing to move.
   `hp_ratio` is the finer instrument and moves even for two win-saturated combos
   (mistral/Silent +0.112, qwen3-32b/Silent +0.064). Restate as: *format-insensitivity at
   combat holds only where the win-rate ceiling removes the variance.*
2. **The turn-level pooled effect favours RAW (−0.076, p=0.0005) but the direction splits
   5 S / 7 R (sign test n.s.).** Registered reading: **"format matters at turn level; its sign
   is a model property"** — never "raw beats structured at turn level". The existing
   format-as-model-property framing is now quantified rather than asserted.
3. **qwen3-32b's run-level lift shrinks under the matched anchor.** Published comparison was
   the model's 25 runs vs greedy's *100-run* anchor (.01 survival / 12.48 floors). On the
   **same 25 run seeds** greedy scores .04 / 12.76 — so the honest gap is **3/25 vs 1/25
   survivors (+0.08, p=0.75)** and **+0.48 floors (p=0.5625)**, not ".12 vs .01". The
   registered phrasing ("signal, not a win; needs n=20") stands and is now quantified;
   the *numbers quoted alongside it* must be the matched ones.
4. **Synergy `archetype` and `card_pick` are downgraded to `SUPPORTED-MAGNITUDE-ONLY`**
   (direction 7/5 and 8/4, n.s.). Only **`removal`** survives as a general structured>raw
   effect (10/2, sign p=0.039, McNemar significant in 4 combos after Holm). The paper's format
   claim should lead with removal.
5. **`card_pick` is the noisiest synergy metric** — seed residual 0.362 vs model 0.229. It
   should not carry a headline claim on its own.

### 7. What it CONFIRMED

- **"5 of 6 models" on synergy removal** — exactly reproduced at sample level; deepseek-14b is
  the sole reversal and its reversal is *significant* (Silent p=0.0001 after Holm), so it is a
  real property of that model, not noise.
- **The horizon-collapse story, now as a variance statement.** Between-model η² share:
  turn **0.83**, combat **0.89**, synergy **0.51**, run **0.02** — while at run level
  *character* explains **0.57** and seed noise **0.34**. One line for the paper: **at the run
  horizon, which model you use explains ~2% of the variance; which character you play explains
  ~57%.** That is the collapse-floor claim in a single number.
- Seed noise is small at short horizons (turn 0.07, combat 0.01–0.03), so n=5 seeds was
  adequate *there*; it is the dominant term at run level, which is why run-level needs n=20.

**Known limitations (recorded, not hidden):** per-combo tests cannot reach α=0.05 (§2); run
rows in the variance decomposition use only the 3 models with complete n=20 run data;
McNemar assumes independent pairs while the 20 fixtures recur across seeds (mitigated by
reporting the cluster-safe seed-level test beside it, and by the hierarchical bootstrap);
deepseek-7b synergy pairs drop 37–38 of 100 to parse failures and its accuracies stay
conditioned on the parseable subset.

## 2026-08-07 — qwen3-32b matrix retrieval: turn-saturation verdict, run-n=5 reporting rule, `.gitignore` leak fix

**Context.** The Sharanga qwen3-32b full matrix (jobs 261120–261123) completed and was
retrieved. Three decisions had to be made before any number entered the docs.

### 1. The `turn dmg_ratio = 1.000 ± 0.000` boundary value — ACCEPTED as real

**Problem.** Silent/structured returned a perfect exhaustive-oracle match on 100/100 samples
with zero variance across 5 seeds. Standing rule: a boundary + std≈0 measurement is a harness
bug until a per-sample audit clears it. The specific failure mode to rule out: if most legal
play sequences tie at the optimum, `1.000` means "played legally", the dimension does not
discriminate, and the number is an instrument ceiling.

**Options.** (a) accept it — a 32B reasoning model plausibly maxes a short-horizon task;
(b) reject/flag it pending a re-run; (c) **measure what a non-planning policy scores on the
identical states** and let that decide.

**Choice: (c).** Built `scripts/turn_saturation_check.py` — reconstructs all 100 turn states
per character (same seeds, same `new_game`+`start_combat`+Cultist construction the harness
uses), enumerates the full space of maximal legal sequences, and reports the fraction that are
optimal plus two degenerate baselines. Zero API cost, deterministic, committed so the claim is
reproducible by a teammate.

**Result.** 0/100 saturated states for BOTH characters; only 1.0% (Ironclad) / 0.0% (Silent) of
legal sequences reach the optimum; random legal sequence scores 0.231/0.145; naive
left-to-right scores 0.614/0.510. Cross-check: qwen2.5-7b scored 0.663 Silent-structured with
legal_rate 0.87 — below its own legal rate, so legal-but-suboptimal play exists.
**Verdict: real planning result, folded in unqualified.**

**Trade-off / limitation registered.** The dimension is now **saturated at the top**: nothing
can score above 1.000 on Silent-structured. **This bounds M3b** — turn-level cannot rank
frontier models, and the horizon-collapse curve's left edge has no headroom. If frontier
ranking at short horizon is wanted later, the turn task must be made harder (deeper hands,
multi-enemy targeting, or scoring defense as well as damage) — which would be an
instrument-version boundary requiring a full re-baseline. Not doing that now; the
discriminating horizons (synergy, run) are unaffected.

### 2. Run-level at n=5 — reporting rule fixed BEFORE the number gets quoted

Ironclad/structured produced the project's **first non-zero run survival lift**: 0.12 vs the
measured greedy 0.01, floors 13.24 vs 12.48. Tempting headline, weak evidence: n=25 runs
(5/seed × 5 seeds) with std 0.179 across seeds → roughly 3 survivors concentrated in one or two
seeds.

**Decision: quote it as a signal, never as a win.** Registered phrasing — *"the first model to
rise off the run-level floor, at n=25 with wide seed spread; needs n=20 to confirm."* Forbidden
phrasings: "beats greedy", "solves run-level", any bare 0.12 without the n and the spread. The
n=5 rows are a **floor estimate** and must never be blended with n=20 run-level rows in a table
or a mean. If the lift matters to the paper, the cost to confirm is one Ironclad/structured
combo re-run at N_RUN=20 (~50–67 h on one H200) — deferred, not scheduled.

### 3. `.gitignore` leak — results/ subdirectories were committable (fixed)

**Found during this retrieval.** The ignore rules were `results/*.json`, `results/*.txt`,
`results/*.png` — per-extension globs that match only the TOP level. Creating
`results/_sharanga_logs/` (Slurm `.out` logs) and `results/_csis_qwen3-32b_2026-06-22/`
(superseded-run backup) staged **88 files clean for `git add -A`** in this PUBLIC repo,
including cluster job logs. `.out` was not in the ignore list at any level.

**This run's logs were scanned and are clean** (nvidia-smi + vLLM startup + benchmark progress;
no usernames, no IPs, no node hostnames) — so nothing leaked. But Slurm logs *can* carry
`/home/<user>` paths and node names, and this is the same failure class as the 2026-06-12 CSIS
IP incident.

**Fix:** `results/**` + `!results/.gitkeep`. Verified: `git add -An` now stages nothing from
`results/`, `.gitkeep` remains trackable. **Durable rule: ignore result/artifact directories
recursively (`dir/**`), never per-extension — a per-extension glob is one `mkdir` away from
being bypassed.**

---

## 2026-07-23 — Sharanga HPC access (BITS Hyderabad): recon done, large-open-model ladder registered

**Context.** The professor granted access to the **Sharanga HPC cluster** (BITS Hyderabad;
public docs: `https://sharanga.hpc.bits-hyderabad.ac.in/docs/`) via a **shared account**, to
run the largest open-source models before/alongside the M3b frontier-API runs. Access details
(key-only SSH auth — password auth is disabled server-side; MobaXterm setup; account
etiquette) live in the **gitignored** `docs/Sharanga_HPC_SOP.pdf` (`*Sharanga*SOP*.pdf` in
`.gitignore`) — per the standing public-repo rule, no usernames/credentials/SSH keys are ever
committed; the cluster hostname appears only via the university's public docs URL.

**Recon (verified on-cluster 2026-07-23 — partition table + QOS + driver in the SOP §4):**
- GPU partitions / per-user QOS caps: **gpu_a100_8** (8× A100 SXM4 80 GB, MaxTime 5 d,
  **cap 2 GPUs** = 160 GB) · **gpu_h100_4** (2 nodes × 4× H100 80 GB, 3 d, **cap 3 GPUs /
  cpu=8 / mem=300G** = 240 GB) · **gpu_h200_8** (8× H200 141 GB, 4 d, same 3-GPU cap =
  **423 GB pooled, the per-user ceiling**). Exception tiers exist by name
  (`qos_gpu_a100_priority` 8 GPU/300 d, `qos_gpu_h100_unlimited`) → full-node jobs are
  grantable on request. The docs' "GPU jobs max 12 h" policy is NOT enforced; partition
  MaxTime governs.
- **Driver CUDA 13.0** (580.126.20) → **latest vLLM, no pin** (installed: vLLM 0.25.1,
  torch 2.11.0+cu130, python 3.12). The CSIS vLLM-0.6.6 ladder explicitly does NOT apply.
- Storage: home on Lustre (first `import torch` ≈ 100 s of pure I/O — normal), scratch
  purges after 15 days idle; `HF_HOME=/scratch/$USER/hf` (set per-job, weights prefetched
  on the login node).

**Decisions.**
1. **Model ladder registered (cheapest-information-first):** smoke qwen2.5-7b (1× A100,
   validates pipeline + measures tok/s vs the CSIS 82 tok/s anchor) → **qwen3-32b FULL
   4-dim matrix** (fills the intentional synergy-only gap; modern vLLM supports it now) →
   **70B within-family scale axis** (Llama-3.1-70B and/or Qwen2.5-72B — same families as
   the existing 8B/7B rows under identical prompts/seeds → a clean scale line on the
   horizon-collapse curve) → **gpt-oss-120b** (open reasoning model, 1× H100/H200, MXFP4
   needs Hopper+, not A100) → **Qwen3-235B-A22B FP8 on TP=2 H200** (largest model under
   default QOS; extends the qwen 7B→32B→235B family axis; reasoning MoE).
2. **R1-671B parked**: needs ~700 GB = a full-node QOS exception on gpu_h200_8. The ask is
   concrete ("temporary priority QOS for one job") but deferred — Qwen3-235B answers the
   same scale question under default QOS; revisit only if M3b results argue for it.
3. **Shared-account etiquette (binding):** ~~zero global footprint — no `conda init`/`.bashrc`
   edits~~ **superseded 2026-07-23: professor directed `conda init bash` in the shared
   `.bashrc` (done; `auto_activate_base false` — conda on PATH at every login, base NOT
   auto-activated). Interactive shells (login + `srun --pty`) now use plain
   `conda activate slaybench`.** Sbatch scripts KEEP the explicit
   `source ~/miniconda3/bin/activate slaybench` (batch shells don't reliably source
   `.bashrc`); personal Miniconda at `~/miniconda3`; namespaced dirs; **never `scancel -u`**
   (kills other users' jobs on the shared account); Anaconda ToS accepted with the
   professor's explicit approval.
4. **CSIS sbatch files stay untouched** (their headers encode CSIS-specific gotchas);
   Sharanga gets parallel `cluster/sharanga_*.sbatch` variants. First: `sharanga_smoke.sbatch`
   (1× A100, tiny 4-dim pass, `--run-tag sharanga_smoke` = no matrix overwrite). ~~Smoke NOT
   yet run — next session's first action.~~ **✅ RUN + PASSED 2026-07-23** — on H200, not A100
   (gpu_a100_8 down for admin driver stress-testing): ~190 tok/s gen (2.3× CSIS), 57 s wall,
   scores sanity-clean. Three env blockers found + fixed (non-executable system `nvcc` broke
   AOT compile → env-local `cuda-nvcc`+`libcurand-dev`; flashinfer JIT sampling unbuildable →
   `VLLM_USE_FLASHINFER_SAMPLER=0`, native sampler, same semantics; 0-byte-log/HF-stall/timeout
   observability patches in the sbatch). Full record: experiment_log 2026-07-23. New submit
   rules learned: ≤4 CPUs per H200 GPU; one `--partition` per job (per-partition associations).
5. **Comparability:** same harness + current engine version (post-2026-07-14 audit batch) =
   the same instrument version planned for M3b; gpu_a100_8 is hardware-like-for-like with
   the CSIS A100 results. New-model rows extend the matrix without re-baselining anything.
6. **Matrix sbatch variants STAGED (2026-07-23 addendum, post-smoke):**
   `cluster/sharanga_{turn_combat,synergy,run_level}.sbatch` — ladder rung-1 jobs
   (qwen3-32b FULL 4-dim matrix, both characters × both formats, n=20,
   `--seeds 42 1042 2042 3042 4042`, NO `--run-tag` = real matrix cells), model-
   parametrized for every later rung via `HF_REPO`/`SERVED_NAME`/`TP_SIZE`
   (+`HEALTH_WAIT_MIN`) overrides with documented partition-move and TP=2-H200 submit
   forms. Conventions inherited from the validated `sharanga_smoke.sbatch` (same env
   block; health loop parametrized to a 60-min default because cold Lustre weight load
   scales with model size — 7.2 min for the 7B's ~15 GB ⇒ ~35+ min for the 32B's
   ~65 GB, past the smoke's 25-min budget). Two deliberate improvements over the CSIS
   loop files: a login-node **prefetch check** (fail-fast when the 15-day scratch purge
   ate the weights, since `HF_HUB_OFFLINE=1` would otherwise kill vLLM minutes in) and
   **fail-loud-keep-going loops** (a failed combo prints a `COMBO FAILED` marker and
   continues — partial results > lost job — but the job exits non-zero at the end; the
   CSIS files silently continued AND exited 0). **Sizing, documented anchors only**
   (H200 7B = 190 tok/s; CSIS A100 7B = 82 tok/s with turn+combat ≈3 h/character and
   run-level ≈4 h/character; qwen3-32b budgeted at ~1/3–1/2 the 7B's per-token speed
   ⇒ ~63–95 tok/s, and 3–5× the output tokens for `<think>`): **turn_combat 72 h**
   (central 15–39 h; 8k-budget-bound tail >50 h), **synergy 24 h** (400 single calls,
   central 1.5–3.5 h; all-8k tail ~14 h), **run_level 96 h = gpu_h200_8 MaxTime**
   (central 21–52 h; per-seed partial saves bound a wall-kill's loss to the in-flight
   seed). Jobs submit SEQUENTIALLY tc → syn → run — all three merge into the same
   per-seed JSONs, concurrent writers race. **Supersession rule (comparability): the
   new full-matrix qwen3-32b cells SUPERSEDE its CSIS synergy-only cells** (those ran
   on the CSIS vLLM-0.8.x stack); synergy is re-run on Sharanga precisely so all four
   qwen3-32b dimensions share ONE serving stack — never blend the CSIS qwen3-32b
   synergy numbers with the Sharanga ones.
7. **PARALLEL fire-and-forget path added (2026-07-24)** — for the ~6-day unattended
   window (user on exams, back 2026-07-30) the dimension-split files above are the WRONG
   shape: each touches all 4 result files, so they can't overlap. Added
   `cluster/sharanga_matrix_combo.sbatch` (one job = one character×format = all 4 dims →
   ONE result file) + launcher `cluster/sharanga_submit_qwen3_matrix.sh`. Split the work
   along the OUTPUT FILE instead of the dimension: 4 combos write disjoint files, so up to
   **3 run concurrently under the gpu_h200_8 3-GPU QOS cap with no race**, and matrix
   wall-clock collapses from ~sequential (tc→syn→run, days each) to ≈ one combo (~20–50 h,
   3 of 4 parallel + 1 queued). **Two correctness guards this needed:** (a) **unique port
   per job** `PORT=$((10000 + SLURM_JOB_ID % 40000))` — Slurm can co-schedule several
   1-GPU jobs on one 8-GPU H200 node, so a hardcoded :8000 would let two concurrent combos
   collide on the server socket; (b) **smoke-gated `--dependency=afterok` chain** — the
   launcher submits a qwen3-32b smoke first (`HEALTH_WAIT_MIN=60`, `--time=02:30:00`) and
   makes all 4 combos depend on it, so a serving/env failure blocks the multi-day jobs
   (cheapest-first; the Gemma-3-12B empty-output precedent) instead of burning the whole
   absence. Honest limit recorded in the launcher: afterok gates on the smoke's exit code,
   NOT result quality — but qwen3-32b already parsed on CSIS, so the Sharanga-specific risk
   (serving/env) is exactly what afterok catches; over-deliberation would still run but
   stays diagnosable via partial-save + parse counters. The dimension-split files are kept
   (valid for a future one-model-at-a-time sequential run); the combo path is the default
   for filling the matrix. Same supersession + comparability rules as §6.

## 2026-07-14 — External expert review adopted as evaluation baseline; backlog re-prioritized (stats pass promoted, P6 scope extended)

**Context.** The user provided a NeurIPS-grade external review of the current project
state (full text + project-side assessment preserved in `docs/review_2026-07-14.md`)
and directed that it be adopted as the evaluation baseline for all future paper-side
decisions. Verdict: 6.6/10 weak reject at D&B today; top rejection reasons = missing
frontier models (sev 10), single-environment generalization (10), external validation /
benchmark correlations (9/8), statistical rigor, claims-vs-evidence scoping. The
review's gap ranking independently converged with our own venue ladder — treated as
validation of the existing plan plus four concrete deltas.

**Decisions.**
1. **M3b stays #1, gains scope:** when frontier results land, correlate per-model
   collapse points against *published* external agent-benchmark scores (GAIA /
   SWE-Bench / WebArena etc.) — no external benchmarks run by us; n≈8–10 models
   reported as directional only. Answers the "why should anyone care" / Reviewer-D
   criticism at near-zero cost.
2. **NEW P4b — statistical rigor pass, promoted ahead of paper assembly:** bootstrap
   CIs, effect sizes, **paired seed-matched tests for the format ablation** (the
   design was built for this; the test has never been run), variance decomposition.
   Zero GPU — pure analysis on the 24 aggregates + persisted per-sample records.
   Unblocked now; must be trivially re-runnable when M3b rows land.
3. **P6 scope extended:** explicit oracle-quality limitations taxonomy (turn exact →
   combat greedy → synergy expert → run baseline); three named rebuttal arguments we
   already hold evidence for — (a) difficulty≠horizon via the dissociation pattern
   (deepseek-7b execution collapse vs matrix-2nd synergy removal; qwen3-32b bends only
   at synergy), (b) run-level collapse ≠ context accumulation (memoryless harness,
   bounded prompts), (c) budget-bound deliberation as a mechanistic account for one
   family; plus a claim-scoping pass ("in this benchmark" until M3b/second-domain
   evidence) and the explicit memory/tools scope-out defense (floor vs ceiling).
4. **Second environment: explicitly deferred**, acknowledged in the paper as the known
   generalization gap; revisit after M3b. TMLR (review: 65–80%) is the honest fallback.

**Not adopted (recorded to avoid re-litigation):** memory + tools ablations (break
per-horizon oracle determinism / measure scaffolding ceiling, not planning floor —
documented design scope-out, must be stated in the paper); "dataset weak" (fixture
protocol is small-by-design and part of the method); citation projections (noise).

**Trade-offs.** Promoting the stats pass ahead of assembly delays prose but every
number it produces feeds the assembly anyway; the correlation study is deliberately
cheap-and-directional rather than a run-it-ourselves validation (cost would be an
entire second project). Revisit trigger: if M3b frontier models also floor at run
level, the second-environment question becomes the binding constraint for D&B.

## 2026-07-14 — Act 2/3 audit fix batch: encounter-pool reclassification, draw=loss symmetry, fail-loud spawning

**Context.** Full adversarial audit of `enemies_act2.py` + multi-act plumbing
(`docs/bug_audit_2026-07-14.md`: 1 critical + 3 high + 9 medium + 12 low). Acts 2/3 have
never produced kept data (`--acts 3` is the M3b-gated appendix probe, decision_log
2026-07-12 P3), so this was the last free window to fix them without a re-baseline.
All items implemented + verified same day; per-item notes in the audit doc. Three items
rise to decision level:

1. **Encounter pools reclassified to real-game roles (M1).** Elites had sat in normal
   pools (BookOfStabbing 160-175 HP, GiantHead 500 HP as Act-3 "normal") and Act-3
   encounters in Act 2 (Transient, WrithingMass) — any `--acts 3` difficulty numbers
   would have been fidelity-distorted in both directions. New tables use the real-game
   classification restricted to our implemented roster; TorchHead×2 is a documented
   stand-in; SpireShield/Spear (Act-4 Heart guards) leave the tables but stay registered.
   Trade-off: our Act-2/3 pools are smaller than the real game's — accepted, documented.

2. **100-turn combat draw = LOSS in both paths (M2).** `run_loop._resolve_combat`
   previously let a timed-out combat continue the run while `benchmark._llm_combat`
   scored it dead — an asymmetry that biased the greedy anchor against the LLM
   exactly where Act-2/3 stalls are realistic (500-HP GiantHead). Conservative +
   symmetric now. **Acceptance verified:** greedy baseline re-run both characters —
   all anchor metrics identical (IC 12.48/.780/1%; Silent 11.26/.7037/0%). Per-sample
   death-overkill `final_hp` shifted (~10 samples/char) via the Hexaghost M3 companion
   fix (an Act-1 change: Sear Burn → discard, Divider Burns removed) — no outcome
   flipped, no published metric feeds on death `final_hp`. **Consequence: this batch
   is an instrument-version boundary for run-level** — never blend the existing
   matrix's run-level numbers with post-batch run-level numbers (M3b runs on the new
   engine, which was already the plan).

3. **Unknown enemy ids now fail loud (C1).** "DonuAndDeca" was not a registry key;
   `spawn_enemies` silently skipped it → the Act-3 boss fight spawned ZERO enemies →
   instant free win on 1/3 of boss rolls. Fixed at three layers (real `["Donu","Deca"]`
   table entry; `spawn_enemies` raises on unknown id; `start_combat` raises on an empty
   enemy list) + an executable invariant test that every id in all 9 encounter tables
   resolves. Principle applied: a silent fallback that can manufacture a perfect score
   is an instrument bug even when dormant.

**Spec correction during implementation (audit L8):** real Wither = 10 dmg + 2 Weak +
2 **Vulnerable** (wiki-checked; the audit's "Frail" recollection was wrong).
**Verification:** 146/146 tests (+8), mock pipeline ×4 green, multi-act mock smoke
green, full Act-2/3 encounter sweep honest (no instant wins, no timeouts, sane
difficulty gradient). No prompt bytes changed → the existing matrix stays valid.

## 2026-07-13 — M3b frontier-run token-budget protocol: matched-8k first, escalate only on measured truncation

**Problem.** The parse probe established that the DeepSeek distills' collapse is *budget-bound
deliberation* (100% of JSON failures = truncation at max_tokens=8000 mid-`<think>`). Frontier
reasoning models (Claude/GPT, backlog P4/M3b) could in principle hit the same wall — in which
case M3b would measure budget compliance, not the raw planning ability the frontier-bend claim
needs. Conversely, simply raising the frontier budget breaks budget-matching against the 8k
small-model matrix.

**Decision (registered before any M3b spend).**
1. **Smoke test reads the truncation diagnostics first.** Every M3b smoke MUST check
   `turn.parse_fail_truncated`/`parse_fail_n` and `combat.avg_truncation_errors` (instrumented
   2026-07-12) before sizing full cells. No full cell launches on an unverified budget.
2. **Matched budget is the default condition:** run frontier models at the same effective
   8k completion budget as the matrix. If smoke truncation ≈ 0 (expected — frontier reasoning
   models terminate deliberation; the distills' pathology is that they can't), the cells are
   directly budget-comparable and no protocol fork is needed.
3. **Escalation is conditional and additive:** only if smoke truncation > 0, add a
   raised-budget condition and report BOTH — "planning ability at adequate budget" and
   "budget discipline at matched budget" as separate numbers, never blended. Under matched
   budget, truncation is a real result (budget-bound deliberation is an established failure
   mode, per the probe), but it does not answer the frontier-bend question — the raised
   condition does.
4. **Provider-class note:** reasoning APIs decouple the budgets — Claude extended thinking
   takes a separate thinking budget with answer tokens on top; OpenAI reasoning models count
   reasoning inside `max_completion_tokens`. "Matched 8k" must be defined per provider when
   the class is written (document the mapping in the provider code + experiment_log), since
   an exact token-for-token match across APIs with hidden/billed-separately reasoning tokens
   is not possible — match the *answer-generation* ceiling and disclose the thinking budget.

**Trade-offs.** Matched-first costs one smoke round before full cells (cheap); the alternative
(raise budgets preemptively) would silently forfeit budget comparability and invite a reviewer
question we can't answer. **Revisit trigger:** if BOTH conditions in (3) are needed for any
model, the paper's §5.4 must state which condition each headline number comes from.

## 2026-07-12 — Parse-failure diagnostics: instrument truncation-vs-malformed + additively split the conflated combat `parse_errors` counter

**Problem.** Two related instrument gaps found while answering "are the DeepSeek `<think>` parse
failures our fault or the model's?": (1) `complete_json` discards the raw completion and the API's
`finish_reason` on failure, so truncation ("thought past max_tokens, answer never emitted") is
indistinguishable from malformed output — unanswerable from any saved artifact; (2) the combat
`parse_errors` counter **conflates** true JSON-parse failures with *valid-JSON-but-illegal actions*
(out-of-range index, unplayable card, unknown action) in both `CombatEvaluator` and the run-level
`_llm_combat` — so "deepseek-7b ~8 parse_errors/combat" is really "invalid-action errors."

**Decision (all additive — comparability preserved by construction):**
- `LLMInterface.last_finish_reason` set by all providers (Groq/OpenRouter/Local read the API's
  `finish_reason`; Mock scriptable via `finish_reasons=[...]`). `complete_json` failure dicts now
  carry `raw_len`, `finish_reason`, `truncated_think` (`<think>` opened, never closed).
- `CombatScore`/`RunScore` gain `json_parse_errors` + `illegal_action_errors` +
  `truncation_errors` (subset of json, = finish_reason "length" or unclosed think).
  **`parse_errors` keeps its historical conflated semantics** (`== json + illegal`) so the
  2026-06-22 matrix aggregates remain directly comparable; the new fields default 0 and old
  result JSONs read back cleanly (`_agg_dim` is `.get()`-based).
- `TurnScore` gains `fail_json_parse` / `fail_finish_reason` / `fail_truncated_think` /
  `fail_raw_len` (set only for true JSON failures, NOT schema misses like valid JSON without
  `"plays"`). Summaries add turn `parse_fail_n`/`parse_fail_truncated` and combat
  `avg_json_parse_errors`/`avg_illegal_action_errors`/`avg_truncation_errors`; `_aggregate_summaries`
  keys extended to match (the key-mismatch trap from the 2026-06-10 audit item 20).
- **No prompt bytes changed** (verified: diff contains no prompt-string edits) → all existing
  data stays valid; 137/137 tests (+3 regression: failure-dict diagnostics, combat split sums,
  turn truncation recording + schema-miss exclusion).

**Reporting rule (effective immediately, §5.4):** call the historical combat metric
**"invalid-action errors"** when citing the matrix (it includes legality failures with perfectly
parsed JSON); reserve "parse errors" for `json_parse_errors` once probe/new data exists.

**Registered probe (`cluster/parse_probe.sbatch`, not yet run):** deepseek-r1-distill-7b (default;
14b/Silent via env override), IC, both formats, turn n=20 + combat n=3, seed 42,
`--run-tag parse_probe` so matrix files are never overwritten — a diagnostic cell, NOT foldable
into the matrix (post-instrumentation harness). Expected read: `parse_fail_truncated/parse_fail_n`
≈ 1 ⇒ report DeepSeek failures as "budget-bound deliberation"; ≈ 0 ⇒ "output-discipline failure."
Requires the cluster clone pulled past this commit.

### Addendum 2026-07-12 — vLLM GPU-memory leak fix + cluster contention lessons (`lib.sh`, commit `9bcfae5`)
Submitting the probe hit CUDA-OOM (7B model, "1.01 GiB free, Process 1301334 has 64.38 GiB in
use"). Diagnosis + fixes: vLLM 0.6.6 spawns CUDA **worker children**; the old `stop_vllm` killed
only the launcher PID, so hard-killed jobs (scancel/OOM/`wait_for_vllm` exit-1) leaked workers that
pinned VRAM into the next job. `lib.sh` now: (1) `start_vllm` pre-flight VRAM check (nvidia-smi) —
reaps `$USER`'s own strays if <20 GiB free, else **fails fast** with `nvidia-smi` + `sinfo` hint;
(2) `stop_vllm` kills the whole process **group** (`kill -- -$PID`) + pkill sweep; (3) `setsid` so
vLLM leads its own group. Cluster-ops only, no measured code touched.
**Two operational lessons (also baked into `parse_probe.sbatch` header):** (a) **gpu-3day needs
`--qos=test-gpu`** or the submit is rejected (`QOSMaxWallDurationPerJobLimit`). (b) **`--gres` does
NOT guarantee a free GPU on this cluster** — a first probe attempt landed on a `mix`-state node
where another user's `pose` job pinned both A100s at ~66 GiB/100% util. **Steer to an `idle` node**
(`sinfo -p gpu-3day -N -o "%n %t"` → `--nodelist=<idle>`). The hardened pre-flight check confirmed
it caught this correctly (failed fast, did NOT kill the stranger's process — only `$USER` strays).

### Addendum 2026-07-13 — PROBE RESULT: budget-bound deliberation (`ratio = 1.0` in all four cells)
The probe ran clean (four cells: deepseek-7b IC + deepseek-14b Silent, both formats; turn n=20 +
combat n=3, seed 42). **`parse_fail_truncated/parse_fail_n` = 1.0 everywhere** (7b: 10/10
structured, 7/7 raw; 14b Silent: 1/1, 5/5) and combat `truncation_errors == json_parse_errors`
exactly in every cell — zero malformed-but-complete completions. Per the registered decision rule
above ⇒ **DeepSeek parse failures are reported as "budget-bound deliberation."** The counter-split
arithmetic was verified in the field (`parse_errors == json + illegal` in all cells) and the probe
replicated the matrix numbers (7b win .33/.00; 14b Silent raw win .33/hp .21 ≈ matrix .34/.21),
confirming the instrumentation was additive in practice, not just by construction. The reporting
rule stands: matrix combat metric = "invalid-action errors"; probe cells stay out of matrix
tables. Folded into `experiment_log.md` (2026-07-13), `findings.md` (probe section + finding 2
supersession), `draft.md` (results skeleton finding 3 + §5.4 limitations), `report_matrix.html`
(metric rename + one-line mechanism note). One instrumentation gap noted for any future probe:
the per-sample `fail_finish_reason`/`fail_raw_len` records are computed but not persisted in the
output JSON — only the summary counters survive; sufficient here, but raw truncated completions
are unrecoverable. *(⚠️ Superseded same day — gap CLOSED, see the next addendum.)*

### Addendum 2026-07-13 (later) — GAP CLOSED: per-sample diagnostics now persisted (additive)
The persistence gap above is fixed. `BenchmarkResult.summary()` now writes per-sample records
into the result JSON, following the synergy `samples` pattern:
- **`turn.samples[]`** — one record per turn sample: `seed` (the sample's generation seed, new
  `TurnScore.sample_seed`), `parse_ok`, `legal`, `damage_ratio`, `llm_sequence`,
  `optimal_sequence`, plus the full failure split `fail_json_parse` / `fail_finish_reason` /
  `fail_truncated_think` / `fail_raw_len`, and a new **`fail_raw_excerpt`**.
- **`combat.samples[]`** — one record per combat: `seed`, `won`, `turns`, `hp_ratio`,
  `cards_played`, `parse_errors` (historical conflated total, unchanged semantics) and the
  three-way split `json_parse_errors` / `illegal_action_errors` / `truncation_errors`.
- **Raw-excerpt size bound:** on a true JSON-parse failure only, `fail_raw_excerpt` stores the
  first 200 + last 200 chars of the raw completion (`_bounded_excerpt`, middle elided with a
  char count). Rationale: head shows how the deliberation started, tail shows whether it was cut
  mid-thought — the probe's evidentiary need — while a full 8k-token `<think>` dump per failed
  sample (~30 KB × up to 20 samples × 5 seed files) is file bloat with no added diagnostic
  power. Worst case adds ≈8 KB per per-seed JSON. "Raw truncated completions are unrecoverable"
  is now only true for the middle of the dump.
- **Scope notes:** combat per-CALL excerpts were NOT added — combat interleaves many calls per
  sample and capturing per-call raws needs restructuring the evaluator loop's error handling;
  the per-combat counter split covers the probe's read. Run-level `samples` also not added
  (RunScore already carries the split counters; run is the floor dimension, no probe planned).
- Additive only: no prompt bytes changed (diff verified), no key renamed/removed;
  `_aggregate_summaries` ignores unknown keys (`.get()`-based), old JSONs read back cleanly.
  Tests **138/138** (+`test_per_sample_diagnostics_persisted`: induced MockLLM truncation →
  serialized summary carries seed/finish_reason/raw_len/bounded excerpt; old-style dicts still
  aggregate). Mock pipeline green ×4.

## 2026-07-12 (P3 research decision) — Run-level discriminability: REFRAME as the shared collapse floor; hold `--acts 3` for a post-M3b appendix probe (Option C, conditional)

**Problem.** Run-level (the longest horizon) does not discriminate between the current models.
All 7–8B instruct models floor at ~12.5 floors ≈ the greedy baseline, so the right edge of every
horizon-collapse curve converges to a single point. Backlog P3 (handoff §6) asks whether to make
the run harder (Option A: `--acts 3` multi-act) or reframe it (Option B), or a hybrid (Option C).

**Context / evidence (the numbers this decision rests on).**
- Run-level, both characters, mean floors (structured / raw), from the 24 aggregates:
  qwen2.5-7b IC **12.81 / 13.36**, Silent **11.85 / 10.86**; llama-3.1-8b IC 13.37 / 13.76,
  Silent 11.42 / 11.34; mistral-7b IC 12.72 / 12.83, Silent 11.63 / 11.04. Greedy baseline
  survives Act 1 ~1% at avg **~12.5 floors**. Every instruct model ≈ greedy → floor effect.
- The only run-level *deviations* are the reasoning models, and they deviate DOWNWARD:
  deepseek-r1-14b IC run **9.75 < greedy ~12.5** (over-deliberates to death). This is not
  discrimination in the useful direction — the frontier line does not bend *up* at run, it
  collapses *below* the floor. So even our one non-instruct data point argues that a longer
  run would deepen collapse, not create separation.
- By contrast the benchmark's discriminating power is empirically at the SHORT/MID horizons:
  turn spread across the matrix 0.18→0.84, synergy archetype 0.33→0.80 (qwen3-32b Silent .80 /
  removal .55 = matrix max, the one frontier line that bends away). Combat win and run floors
  are near-zero variance (findings.md item 4). The curve already tells its story at turn+synergy.
- External corroboration for the floor being real, not an artifact: Anthropic's Fable 5 STS eval
  (claude-fable-5-mythos-5 launch post) reports reaching the final act only ~3× more often *with*
  memory — i.e. full-run survival is a severe bottleneck even for a scaffolded frontier model.
  Our floor is consistent with theirs; making our unscaffolded run 3× longer would widen the gap
  to that floor, not close it.

**Options considered.**
- **A — make run harder (`--acts 3`), whole matrix.** `--acts 3` triples the floors and thus
  roughly triples the sequential, stateful, un-batchable calls/tokens per run sample.
  *Cost (computed from the measured anchor: 1-act run-level n=20×5 seeds ≈ 4h per
  model×format×character at ~82 tok/s, experiment_log.md L211):* ~3× ⇒ **~12h per
  (model × format × character)** cell. A full core re-run (3 instruct families × 2 characters ×
  2 formats = 12 cells) = **~144 GPU-hours** of purely sequential single-A100 time; even a
  minimal IC-only probe (3 families × 1 character × 2 formats = 6 cells) = **~72 GPU-hours**.
  On top of the wall-clock, `--acts 3` carries **unaudited-code risk**: Act-2/3 multi-act paths
  (`_act_transition`, boss-relic picks, cross-act HP/deck carry) were built in M2.5 but never
  exercised at paper scale — per handoff §5.2 an unexercised path feeding a headline number
  needs an engine audit + smoke first, adding an audit pass + smoke-test to the cost before any
  paper-grade run. Cluster access is semester-bound (§7), so ~72–144 sequential GPU-hours is a
  material fraction of a scarce, expiring budget.
- **B — reframe as the shared collapse floor.** Keep run-level single-act; report it honestly as
  the convergence floor where model differences wash out (avg_floors/progress, "on par with
  greedy, NOT beating," never survival_rate alone — §5.4). The interesting separation is stated
  to land at synergy. Zero new compute, zero new code-path risk.
- **C — hybrid: reframe now, probe one model with `--acts 3` as a validation/appendix.** Adopt B
  for the current paper; run a single `--acts 3` cell as an appendix probe to show whether a
  longer run separates or just deepens collapse.

**Chosen option: B now, with C's probe DEFERRED and made conditional on M3b (a scoped hybrid).**
For the current paper we reframe run-level as the shared collapse floor (Option B). We do **not**
spend GPU-hours on `--acts 3` now. We register a **conditional appendix probe** (the C variant):
run exactly **one** `--acts 3` cell — but only AFTER the M3b frontier runs land and only if they
still floor at 1 act. If a frontier model floors at 1 act, a single 3-act probe on that model is
the cheapest possible test of "does a longer horizon separate frontier from small models, or just
kill everyone deeper?" — and it is an appendix data point, not a matrix commitment.

**Why (3-sentence version).** Run-level's convergence is a *finding*, not a defect — inter-model
variance is large at turn/synergy and vanishes at survival, which is precisely the multi-horizon
thesis, and both our own downward-only reasoning-model deviation and Anthropic's Fable 5 memory
result say a longer run would deepen the shared floor rather than create separation. Option A costs
~72–144 sequential GPU-hours plus a mandatory Act-2/3 engine audit, against a semester-bound
cluster budget, to (most likely) confirm a deeper floor — poor information-per-GPU-hour by the
cheapest-first doctrine (§5.3). M3b may hand us run-level separation with 1 act for free (a frontier
model whose line bends up), which would make Option A pointless; if M3b *also* floors, that only
strengthens B — so the correct move is to reframe now and let the frontier data decide whether the
one-cell probe is even worth running.

**Trade-offs / what we give up.**
- We accept that the horizon-collapse figure's right edge (run) is a convergence point, not a
  spread. This is a weaker "leaderboard" story at run but a stronger *thesis* story (the collapse
  is the point). The figure caption must render it honestly (see impact below).
- We forgo, for now, any chance that `--acts 3` reveals separation among the *small* models. The
  data makes this unlikely (they already ≈ greedy at 1 act and the one reasoning deviation is
  downward), so the expected information is low — but it is a real, acknowledged gap.
- A reviewer could ask "why not just make it harder?" We answer with the cost + the downward-only
  deviation + the Fable-5 corroboration; the conditional probe is our concrete good-faith answer.

**Known limitations.**
- The ~72–144h estimate is a throughput-scaled extrapolation from a 1-act anchor (~82 tok/s,
  n=20×5); actual 3-act cost could differ if per-call context grows super-linearly across acts
  (longer decks/relic lists → longer prompts) — likely making A *more* expensive, not less.
- "Separation lives at synergy" leans on qwen3-32b being synergy-only; the frontier turn/combat
  points are not yet filled (accepted coverage gap, 2026-06-22 entry). If M3b frontier models
  turn out to separate at combat or run too, the "run = pure floor" framing may need softening.

**Expected failure modes.**
- If B is written as spin rather than a finding, it fails §5.4. Guard: the figure and text must
  show the convergence explicitly (all lines meeting at run), report avg_floors/progress with the
  greedy floor drawn, and never resurrect the invalid pre-fix 13.4-floors/20–40% numbers.
- If the deferred `--acts 3` probe is ever run without an Act-2/3 engine audit + smoke first, its
  number is untrustworthy (§5.2/§5.3) — the audit is a hard precondition, not optional.

**How / when to revisit (explicit trigger).** **Revisit when the M3b frontier (Claude/GPT) run-level
results land (backlog P4).** Decision rule at that point: (i) if a frontier model separates at
run-level with 1 act (line bends *up*, floors > greedy), Option A is unnecessary — keep B, done.
(ii) If frontier models *also* floor at 1 act, B is confirmed and strengthened; THEN run the single
conditional `--acts 3` appendix probe (on the best frontier model, IC, one format — ~12h + a
prior Act-2/3 audit) purely to report whether a longer horizon separates or deepens collapse.
Either branch is a small, well-scoped follow-up, not a matrix re-run.

**Confidence: high** that reframing (B) is correct for the current paper; **medium** on whether the
conditional `--acts 3` probe will ever be worth running (depends entirely on the M3b outcome).

**Impact on the rest of the project.**
- **Horizon-collapse figure caption (P1 done / P6):** state the right edge as an intended
  convergence — "all models collapse to the greedy floor at the run horizon; discrimination lives
  at turn+synergy." Do not present run as a leaderboard axis. (Consistent with the P1 combat-baseline
  note already in the 2026-07-12 P1 decision.)
- **Paper claims (P6):** Claim 1 (multi-horizon decomposition) is *strengthened* — the collapse
  floor is evidence the horizons differ in discriminating power. Add the honesty framing from §5.4
  and the Fable-5 corroboration (P2 lit note) as external support for run being a genuine bottleneck.
- **Backlog:** P3 closes as "reframe (B); conditional `--acts 3` probe deferred to after P4." P4
  (M3b) gains an explicit sub-task: on landing, evaluate the revisit rule above. P6 paper assembly
  inherits the caption + claim guidance. Roadmap M3a step 6 (`--acts 3` "optional breadth ablation")
  should be re-tagged from "optional" to "conditional appendix probe, gated on M3b + an Act-2/3
  engine audit" — flagged for a follow-up edit, not edited here (draft.md is being edited
  concurrently; roadmap edit deferred to avoid a collision, see report).

## 2026-06-22 (model matrix) — qwen3-32b REVIVED + reasoning-distill family added; coverage gaps accepted
**Decision:** The full benchmark matrix now spans **5 model families** (qwen2.5-7b, llama-3.1-8b,
mistral-7b, qwen3-32b, deepseek-r1-distill-14b/7b). **qwen3-32b is un-dropped:** the reason it
was dropped (free-tier TPM truncated its `<think>` mid-reasoning → parse-failure cascade) is gone
once self-hosted on an A100 — it now runs at parse_ok=1.0. It was collected **synergy-only** by
choice: synergy is the horizon where a reasoning model is expected to (and does) separate from the
7–8B pack, and it's the cheapest cell to prove that on a 32B. We are **not** back-filling its
turn/combat/run unless a reviewer asks — synergy carries the separation claim. Two DeepSeek-R1
distills added to probe "does reasoning help, and does distillation size matter": 14b (full
Ironclad incl. run; partial Silent) and 7b (Silent raw turn/combat probe only).
**Why:** Closes the two D&B-blocking gaps the novelty review named — ≥3 model families and a
reasoning model. The finding justifies the spend: reasoning is **not** a monotone win — the 14b
distill's verbose decode *hurts* the long horizons (only model to lose combats; Ironclad run
floors 9.75, below the greedy floor) and the 7b distill collapses (parse_errors 7.93). qwen3-32b,
which stays terse, is the one clean frontier-line that bends away at synergy (Silent archetype
0.80). The remaining holes (qwen3 turn/combat/run; deepseek Silent raw turn/combat + run) are
accepted because they fall on the horizons that are either the convergence floor (run) or where
the separation isn't (combat) — documented as "Coverage gaps" in experiment_log.md, not silently
omitted.

## 2026-06-12 (GPU access) — `cluster/` Slurm toolkit + public-repo IP scrub
**Decision:** Added a `cluster/` toolkit for the BITS CSIS Slurm cluster (the M3a GPU): `setup.sh` (conda env + vLLM), `lib.sh` (shared vLLM serve/wait/stop helpers, model selected via `HF_REPO`/`SERVED_NAME`/`TP_SIZE` env vars, default `Qwen/Qwen3-32B`→alias `qwen3-32b`), `prefetch_model.sh` (login-node weight pull for offline compute nodes), `README.md`, and 4 staged sbatch jobs cheapest→most-expensive (`smoke`→`turn_combat`→`synergy`→`run_level`). Each job serves a model with vLLM on one A100 80 GB then runs `run_benchmark.py --provider local --base-url http://localhost:8000/v1`. Also added `.gitattributes` pinning `*.sh`/`*.sbatch` to LF (CRLF breaks bash on the Linux cluster).
**Why:** Turns the roadmap's M3a run order into paste-and-submit jobs so the GPU phase starts the moment the user SSHes in. One sbatch job runs both the server and the benchmark on the same node, so `localhost` works and the GPU is released on exit (trap).
**Security incident (same session, resolved):** the cluster login-node IP was accidentally committed (in `cluster/README.md` + CLAUDE.md) and pushed to this **public** repo. Fix: scrubbed all occurrences to a `<login-node-ip>` placeholder, removed the internal support email/room, gitignored the SOP PDF, then **purged the IP from all git history** with `git filter-repo --replace-text` and force-pushed `main` (verified: no commit contains the IP, old commit `74cf854` unreachable). Force-push required temporarily enabling GitHub branch protection's `allow_force_pushes`, **restored to disabled afterward (verified)**. Lesson codified in CLAUDE.md Security: never commit cluster IP/SOP to this public repo; placeholders only. Residual: GitHub may cache the old SHA by direct URL (optional GitHub-Support purge; low risk — internal RFC1918 IP, no creds).

## 2026-06-12 (5th audit) — Partial-save catches ALL exceptions, not just rate limits
**Decision:** `run_run_eval` and `run_all` now catch any `Exception` (KeyboardInterrupt re-raised) at the run-seed and dimension boundaries: print the error loudly, stop the affected scope, keep everything completed so far. No retry, no silent swallowing.
**Why:** Only `RateLimitExhausted` triggered partial-save. On the GPU box, vLLM returns HTTP 400 when a prompt overflows the model's context window — `LocalLLM` (correctly) surfaces that as `RuntimeError`, which would have killed the process hundreds of calls into a run-level pass and discarded every completed run. The error must still be loud (it usually means a misconfigured endpoint or an undersized context), but losing finished work to it is never right.

## 2026-06-12 (5th audit) — `complete_json` fallback uses raw_decode, not an end-position scan
**Decision:** The JSON-extraction fallback tries `json.JSONDecoder().raw_decode(text[m.start():])` once per `{` (first success wins) instead of attempting `json.loads` on every (start, end) substring pair.
**Why:** The old scan was ~O(#braces × len²) on garbage input. A truncated 32k-char `<think>` dump (the exact qwen3 failure mode the GPU phase revives) contains no valid JSON and many braces — each parse failure burned minutes of CPU on top of the lost call. `raw_decode` parses a prefix and ignores trailing junk, so accepted inputs are identical and cost is linear-ish.

## 2026-06-12 (5th audit) — justApplied extends to the end-of-turn window (`turn_end_window`)
**Decision:** `CombatState.turn_end_window` is True during the TURN_END emit in `end_player_turn`; `_apply_power` marks player debuffs `just_applied` when applied during the enemy phase OR this window.
**Why:** Doubt/Shame apply Weak/Frail from `end_of_turn_effect` (inside the TURN_END handler). With only the enemy-phase flag, `_tick_player_debuffs` deleted the single stack at the end of the same round — both curses were complete no-ops. Real StS marks these justApplied so they cover the player's next turn. Berserk's self-Vulnerable (applied mid-turn, neither flag set) still ticks the same round, as it should.

## 2026-06-12 (GPU prep) — `--provider local` adapter for self-hosted models
**Decision:** Added `LocalLLM` (OpenAI-compatible `/v1/chat/completions` over urllib, no new deps) and wired `--provider local --base-url URL` into the CLI (falls back to `$LOCAL_BASE_URL` then `http://localhost:8000/v1`). It is `OpenRouterLLM` with the endpoint parametrized and the 402 path removed; a non-429 HTTP error is surfaced with the response body instead of swallowed. 300s timeout, 8000 max_tokens, optional `$LOCAL_API_KEY`.
**Why:** The M3a GPU phase serves open-source models (incl. the revived reasoning model) via vLLM/TGI/Ollama — all OpenAI-shaped. One thin adapter unblocks the entire self-hosted matrix the moment the professor's GPU access lands (~2026-06-13), with no Groq TPM cap. A local server never bills, so OpenRouter's 402-as-payment-wall logic is wrong here — failures should be loud (misconfig) not silently fatal.

## 2026-06-11 (3rd audit) — Block resets at its OWNER's turn start
**Decision:** Player block resets in `_begin_player_turn`; ENEMY block resets at the start of the enemy phase in `end_player_turn`. Enemy block gained during the enemy phase therefore persists through the player's next turn.
**Why:** Resetting enemy block at the player's turn start wiped every enemy blocking move (Jaw Worm Bellow, The Champ Defensive Stance, enemy Metallicize, Curl Up...) before the player could attack into it — all enemy defense was a silent no-op, making every combat easier than real StS for BOTH the LLM and the greedy baseline.

## 2026-06-11 (3rd audit) — Three player-damage modes in `_damage_player`
**Decision:** (1) default = enemy ATTACK damage: block + Intangible + Vulnerable + Torii apply; (2) `from_attack=False` = non-attack damage (Thorns retaliation, Burn/Decay ticks): blockable + Intangible-capped, but never Vulnerable-amplified, no Torii; (3) `is_hp_loss=True` = HP loss (Offering, Combust, player poison, curse ticks): bypasses block/Intangible/Vulnerable entirely. Tungsten Rod applies to all three.
**Why:** Block used to absorb HP-loss effects (neutering Offering/player-poison/Combust), and player Vulnerable amplified Thorns. These are distinct StS damage classes; one boolean couldn't express them.

## 2026-06-11 (3rd audit) — play_card is identity-strict and raising; repeated turn-eval indices are illegal
**Decision:** `play_card` checks hand membership by object identity and raises if `_remove_identical` fails; `_simulate_play_sequence` rejects duplicate indices; the turn oracle uses identity membership.
**Why:** Equality membership let `plays: [2, 2]` replay an already-played card through an identical twin — scored LEGAL with full damage, and hand-counting cards (Fiend Fire) could beat the legal optimum. The same hole let the oracle play side-effect-removed cards. Closes the instrument loophole at engine, simulator, and oracle level.

## 2026-06-11 (3rd audit) — Neow is floor-0 only; events never repeat within a run
**Decision:** Neow's Lament gets `condition: floor == 0` (events fire at floor ≥ 1, so it is out of the mid-run pool); `random_event` tracks `state._seen_events` and excludes seen events until the pool is exhausted. Unimplemented event fights grant no reward (Mind Bloom "I am War" gold removed).
**Why:** Run-level integrity: the auto-picked Neow boon (1-HP enemies ×3 combats) could trivialize combats from any event node, and repeatable events let free-reward events compound — both inflated run-level scores.

## 2026-06-11 (3rd audit) — Time Warp ≈ play-lock (engine-level), not an extra enemy turn
**Decision:** `play_card` checks enemies for `PowerId.TIME_WARP`; every Nth (12th) card play sets `combat.time_warp_lock` (all `can_play` → False until next turn) and grants the boss +2 Strength. `_begin_player_turn` clears the lock.
**Why:** Real Time Warp ends your turn and the boss acts; a forced mid-call turn-end doesn't fit the play_card API. The lock reproduces the strategic constraint (≤12 plays between enemy turns + ramp) without restructuring the turn loop. The old `check_time_warp` method was dead code — the Act-3 boss's signature mechanic simply didn't exist.

## 2026-06-11 (3rd audit) — Potions are inventory-only BY DESIGN (but registered for passive hooks)
**Decision:** No policy (greedy or LLM) drinks potions; `Potion.use()` has no callers and POTION_USED is never emitted. `start_combat` now registers potion `register()` hooks so PASSIVE potions (Fairy in a Bottle) work. Documented simplification, revisit if a potion-action dimension is ever wanted.
**Why:** Wiring potion-drinking into the LLM action space changes every prompt/action schema and the greedy baseline; not worth it pre-paper. But Fairy is passive — leaving it dead was just a bug.
**Decision:** All pile mutations for a specific card object go through `cards._remove_identical()` / `any(c is card for c in pile)`. `list.remove(card)` and `card in pile` are banned for combat piles.
**Why:** `Card` is a `@dataclass` → field-based `__eq__`; equality checks matched identical twins (another Strike), so played cards VANISHED from the game whenever a duplicate was in hand, and `_exhaust_card`/`_discard_from_hand` could remove or duplicate the wrong copy. Starter decks (5 Strikes/4 Defends) hit this constantly.

## 2026-06-11 — CARD_DISCARD means MANUAL discards only
**Decision:** Playing a card never emits CARD_DISCARD; only `_discard_from_hand` (Silent discard mechanics, Gambling Chip mulligan) does. End-of-turn hand discard also emits nothing.
**Why:** Real StS discard triggers (Tingsha, Tough Bandages, Hovering Kite) count manual discards during your turn — emitting on every card play made those relics fire constantly.

## 2026-06-11 — Relic counter lifecycles: class attr = per-run, TURN_START reset = per-turn
**Decision:** Per-RUN counters (Pen Nib, Nunchaku, Sundial, Happy Flower, Incense Burner, Tiny Chest, Omamori) live as class attributes never touched in `register()`; per-TURN counters (Shuriken, Letter Opener, Orange Pellets) reset via a TURN_START subscription; per-COMBAT counters (Centennial Puzzle) reset in `register()` (which runs at every combat start).
**Why:** `register()` re-runs each combat, so `self._count = 0` there silently made every counter per-combat — Tiny Chest could NEVER fire (needs 4 combat-ends).

## 2026-06-11 — Energy granted at COMBAT_START / TURN_END goes through ENERGIZED
**Decision:** Relics granting energy outside the player's turn window (Lantern, Ancient Tea Set, Art of War) queue `PowerId.ENERGIZED`, consumed at TURN_START after the energy reset. Direct `player.energy +=` is only valid mid-turn or in TURN_START hooks.
**Why:** `_begin_player_turn` SETS `energy = energy_per_turn` after COMBAT_START and at every turn start — direct additions before that point were silently wiped (three dead relics).

## 2026-06-11 — Character-gated relic pools via `relic_allowed()`
**Decision:** `relics_full.relic_allowed(relic_id, character)` + `_DEFECT_ONLY/_WATCHER_ONLY/_IRONCLAD_ONLY/_SILENT_ONLY` sets, applied with owned-relic dedup in `random_relic` and `generate_boss_relic_choices`. Boss relics removed from the chest "rare" pool; Nuclear Battery (Defect) removed from boss pools.
**Why:** Silent runs were drawing Brimstone/Magic Flower (Ironclad-only) and dead Defect/Watcher relics; boss-pool leakage gave chests run-warping energy relics. Mirrors the existing `card_pool_for` precedent.

## 2026-06-11 — MERCHANT = deterministic greedy shop, shared by both run loops
**Decision:** `nodes.greedy_shop_visit(state)`: Meal Ticket heal, then pay to remove the worst card (curse → basic Strike → basic Defend), buy nothing else. Used identically by `run_loop.resolve_node` and `RunEvaluator._play_act`.
**Why:** Shop floors were no-ops (gold accumulated unused — a dead stat). A conservative deterministic policy makes gold matter without injecting policy noise into the LLM-vs-greedy comparison; both sides get the same shop behavior.

## 2026-06-11 — Elite/boss room tags on enemies at spawn
**Decision:** `spawn_enemies(state, ids, elite=, boss=)` stamps `_elite`/`_boss` on each enemy; Preserved Insect, Slaver's Collar, and elite relic drops key on the tags. Elites now drop 1 relic (2 with Black Star) at real-StS rarity odds (50/33/17) in both run loops.
**Why:** Room type was invisible to relic hooks (Preserved Insect used a `max_hp>100` proxy that hit bosses); elites dropping no relics removed the core risk/reward of elite routing.

## 2026-06-10 (2nd audit) — Combat HP scored pre-COMBAT_END
**Decision:** `CombatEvaluator` captures `hp_remaining` BEFORE `end_combat()`; the greedy baseline keeps its no-COMBAT_END convention. Both sides now exclude post-combat relic heals.
**Why:** Burning Blood's COMBAT_END heal applied only to the LLM's score → identical play scored hp_ratio 1.095. Symmetric pre-heal reading restores 1.0 = parity.

## 2026-06-10 (2nd audit) — Turn oracle = prefix-pruned DFS, no positional cap
**Decision:** `_exhaustive_best_sequence` does DFS over ALL playable cards with illegal-prefix pruning, per-node dedup of identical cards, and a deterministic 20k-node budget (replaces permutations over the first 6 playable).
**Why:** The cap understated the optimum for any >6-playable hand (Silent's 7-card opener: 6/10 seeds wrong, up to 2×). DFS is complete AND faster (legal sequences are energy-bounded). Ironclad values verified byte-identical pre/post.

## 2026-06-10 (2nd audit) — Synergy instrument keyed on seed
**Decision:** Fixture selection (`seed % 20`) and offer rotation (`seed % 3`) derive from the sample's seed, not the loop index.
**Why:** Index-keyed selection made every `--seeds` run byte-identical → fake std=0 error bars. Seed-keying keeps per-run balance (consecutive seeds cover all fixtures once, uniform pick positions) while making seeds real treatments. Cost: per-sample pairing differs from the saved seed-42 n=20 files (aggregates comparable, rows not).

## 2026-06-10 (2nd audit) — Turn prompt states the scored objective
**Decision:** The turn system prompt explicitly says: maximize total damage THIS TURN; block/defense/setup are NOT scored; an illegal card zeroes the answer.
**Why:** The scorer is damage-only vs a damage-only oracle, but "optimal play" invited (correct!) defensive play that scored as failure — construct validity requires the model to know the objective. Turn scores are not comparable across this change (they were already stale pre-sweep).

## 2026-06-10 (2nd audit) — Intent display shows effective damage
**Decision:** `effective_move_damage()` (enemies.py) is the single source for Strength/Weak-adjusted per-hit damage, used by `_enemy_attack` and BOTH prompt formats. Enemies must store BASE damage in Moves (RedLouse violated this and double-counted).
**Why:** Real StS shows adjusted intent; showing base damage misinformed the LLM (Cultist "6 dmg" while Ritual hits grew 9/12/15) while the greedy baseline doesn't read prompts — an asymmetric handicap.

## 2026-06-07 — Illegal play scoring
**Decision:** If any card in a turn sequence is illegal, `damage_ratio = 0` (zero, not partial credit).
**Why:** Partial credit would reward models that guess randomly and happen to play some valid cards. Zero enforces that legal play is a prerequisite, not an add-on.

## 2026-06-07 — Single source of truth for energy deduction
**Decision:** `play_card()` in `combat.py` is the only place energy is deducted. Cards do NOT subtract energy themselves.
**Why:** Double-charge bug — cards were subtracting energy inside their own `play()` AND `play_card()` was also subtracting. Centralizing prevents this class of bug entirely.

## 2026-06-07 — avg_hp_fraction averaged over survivors only
**Decision:** Deaths contribute 0 to survival_rate but are excluded from avg_hp_fraction. Added avg_progress (floors/15) for partial credit on death.
**Why:** Averaging HP fraction over deaths (where HP=0) would conflate "died early" with "barely survived." Separating the two metrics gives cleaner signal.

## 2026-06-07 — Results overwrite by model+format+seed (no timestamps)
**Decision:** Output files named `<model>_<format>_seed<N>.*` — re-runs overwrite.
**Why:** Easier to compare runs; no accumulation of stale files. Seed makes runs reproducible, so timestamps add no information.

## 2026-06-07 — EventBus.clear() at start of each combat
**Decision:** Clear all listeners at the top of `start_combat`.
**Why:** Listener stacking bug — handlers accumulated across combats in a run, making player progressively invincible. Clearing ensures each combat starts with exactly one registration per relic/power.

## 2026-06-07 — Synergy eval uses greedy card_choice_fn to build a real deck
**Decision:** `run_synergy_eval` now passes `_greedy_pick` (first non-curse offer) as `card_choice_fn` to `run_act`, so the deck has real archetype-defining cards at eval time.
**Why:** With `card_choice_fn=None`, no cards were ever added. The synergy snapshot was always the 10-card starter deck, making `_classify_archetype` always return "Aggro" by default — zero signal. Expert label and model answer were both noise.

## 2026-06-07 — `--only` flag for partial benchmark runs
**Decision:** `run_benchmark.py` accepts `--only turn|combat|synergy|run` to run a single dimension. Skipped dims produce `null` in the summary JSON; merge logic fills them from the previous file on disk.
**Why:** Dimensions are fully independent (separate seed ranges, fresh game state each). Forcing a full re-run to fix one dimension wastes API credits and time.

## 2026-06-07 — Exponential backoff on Groq 429
**Decision:** Retry 429s up to 5 times (1/2/4/8/16s), then raise `RateLimitExhausted` which saves partial results.
**Why:** Uncaught 429 mid-run discarded all completed work. Backoff recovers from transient throttling; graceful degradation saves partial data.

## 2026-06-07 — Synergy ground truth = hand-crafted fixtures, not RNG drafts
**Decision:** Replaced RNG-drafted Act-1 decks in `run_synergy_eval` with fixed hand-crafted `_SYNERGY_FIXTURES` (initially 8, 2/archetype; each with 4–5 signature cards, a basic-Strike removal target, and an on-archetype best-pick offer). Removed the dead `_archetype_draft_fn`.
**Why:** Act-1 RNG decks are too small/RNG-limited to have a crisp archetype — only ~3/10 came out confidently labeled, all model/format combos collapsed to identical archetype_acc=0.333, and even "confident" labels were debatable. Fixed decks give deterministic, unambiguous ground truth.

## 2026-06-07 — Archetype labels decided by signature cards only (+ ambiguity)
**Decision:** Added `_classify_archetype_confident()` — the expert label counts only `_ARCHETYPE_PAYOFFS` signatures (+relics); a deck is labeled only if one archetype uniquely owns the most signatures, else `archetype_correct=None` (excluded from accuracy). Per-sample labels persisted in the JSON for audit.
**Why:** The broad `_ARCHETYPES` list miscategorized generic commons (Armaments/Headbutt → "Exhaust"), producing archetype_acc=0 on all combos with parse_ok=1.0 — the heuristic was wrong, not the models.

## 2026-06-07 — qwen3-32b dropped from the study
**Decision:** No reasoning model in the current model set; result files deleted. Revisit on a paid tier as future work.
**Why:** Infrastructural, not capability: Groq free's 6000 TPM truncates its `<think>` block (parse-failure cascade, 0% everywhere); OpenRouter free is ~30–80 tok/s and returned 402 when credits ran out. Reporting those 0%s as model performance would be wrong.

## 2026-06-10 — Relic lifecycle split: on_pickup vs register
**Decision:** `Relic.on_pickup(state)` = one-time effects at acquisition (max HP, energy/turn, deck mutations); `Relic.register(state)` = event subscriptions only, re-called at every combat start after the bus is cleared. `_obtain_relic()` calls both in order; 20 relics in `relics_full.py` moved their non-idempotent effects to `on_pickup`.
**Why:** With a single `register()` called per combat, non-idempotent effects (e.g. +max HP) stacked every combat across a run — same bug class as the EventBus stacking, one level up.

## 2026-06-10 — Powers reset per combat; poison bypasses block
**Decision:** `start_combat()` does `state.player.powers = {}`; relic-granted powers re-apply via COMBAT_START hooks. Poison ticks subtract HP directly, ignoring block.
**Why:** Per-combat powers (Demon Form, Flex) must not leak across fights; relic powers must not stack. Poison-through-block matches real Slay the Spire mechanics — required for Silent fidelity.

## 2026-06-10 — Silent as second character (same engine)
**Decision:** Added the full Silent card set (~73 cards), powers, pool, and 20 hand-crafted synergy fixtures (5/archetype: Poison/Shiv/Discard/Block). `new_game(seed, character)` factory; `make_card_for`/`card_pool_for`/`system_prompt` dispatch on character. Ironclad fixtures also expanded 8 → 20.
**Why:** Cheapest credible answer to the "too narrow" generalizability critique (see novelty doc): a second character reuses the whole engine while doubling the synergy fixture pool to 40 and enabling n≥20 synergy runs without repeating fixtures.

## 2026-06-10 — Multi-act runs with full-heal act transitions
**Decision:** `RunEvaluator.evaluate(state, n_acts)` plays acts 1→n; `_act_transition()` does a full heal + boss relic pick (LLM if `--llm-routing`, else greedy). `RunScore.acts_completed` / `total_floors` (16×n_acts) track cross-act progress.
**Why:** Act 1 alone caps the run-level horizon at ~16 decisions; Acts 1–3 triple it. Full heal between acts is a simplification (real StS heals partially) accepted to keep act difficulty independent.

## 2026-06-10 — Temperature + multi-seed CLI for paper-grade statistics
**Decision:** All evaluators take a `temperature` kwarg (`--temperature`); `--seeds 42 43 …` runs the benchmark per seed, saves per-seed outputs, and writes a combined JSON with mean ± std.
**Why:** The paper needs error bars. Synergy fixtures are deterministic — variance must come from sampling (temp>0, k completions/fixture) or seed sweeps; both are now one flag away.

## 2026-07-12 — Horizon-collapse curve + cross-horizon normalization (`visualize.py`)
**Decision:** Added `horizon_collapse_curve()` (+ `normalized_horizon_vector()`, `_discover_aggregates()`, and a `python slay_bench/visualize.py --horizon-curve` CLI) that reads the 24 on-disk multi-seed aggregates and renders `results/horizon_collapse_{structured,raw}.png` — one line per model over the planning-horizon x-axis (turn → combat → synergy → run), two panels (Ironclad / Silent), dark theme matching the existing charts. Read-only over saved results; no engine/harness/prompt bytes touched; 133/133 tests still pass.

**Normalization (common "vs-baseline" 0–1 axis; 0 = non-planning floor, 1 = perfect):**
- **turn** = `avg_damage_ratio_mean`, used as-is (already 0–1 vs the exhaustive oracle; illegal/no-damage = 0, oracle-optimal = 1).
- **combat** = `win_rate_mean × min(1, avg_hp_ratio_mean)`. hp_ratio is LLM-HP / greedy-bot-HP, so this centers the greedy bot at 1.0 (win all, HP ≈ bot → ≈1.0) and drives losers toward 0. Matching-or-beating the bot's HP (ratio ≥ 1) counts full; taking more damage than the bot scales the win down.
- **synergy** = mean over {archetype, card_pick, removal} of `clamp01((acc − chance)/(1 − chance))`, so each metric's chance floor maps to 0. Chance floors: archetype 0.25 (4 archetypes, uniform), card_pick 1/3 (3 rotated offers), removal 0.10 (1 basic target in a ~10-card fixture deck). This is the composite representing the deck-building horizon.
- **run** = `clamp01((avg_progress_mean − 0.78)/(1 − 0.78))` — greedy Act-1 survival (~12.5/16 floors ≈ 0.78 progress) → 0, full act (progress 1.0) → 1.

**Options considered / why chosen:**
- *Combat as raw hp_ratio centered on 0 (bot → 0, negative for losers).* Rejected: it makes the near-ceiling instruct baseline read as "floor," visually inverting the actual finding (instruct models win Act-1 combats). The chosen win×hp form keeps the bot near 1.0 and shows the collapse as reasoning models dropping *below* the bot — which is the honest §5.4 story ("combat/run = shared collapse floor; only the over-deliberating reasoning models fall off").
- *Synergy = archetype only, or removal only.* Rejected in favor of the 3-metric mean so no single metric's quirk (e.g. raw-archetype's constant-"Block" collapse) dominates the horizon point; per-metric detail stays in the CLAUDE.md tables.
- *Run = survival_rate.* Rejected (§5.4): survival is ~0–3% for everyone; avg_progress with the greedy floor is the discriminating, honest signal.
- *Interpolating missing cells.* Rejected outright — missing dims are intentional (qwen3-32b non-synergy; deepseek run) and stay `None`, breaking the line (NaN gap) with an explicit isolated marker for single-point series like qwen3-32b synergy.

**Known limitations / the two required caveats:**
- **(a) Run does not discriminate — the right edge converges.** All small instruct models floor at greedy progress → normalized run ≈ 0 (qwen2.5/mistral IC ≈ 0.07–0.09, most Silent = 0.00). This convergence *is* the "shared collapse floor" finding, rendered honestly, not smoothed away.
- **(b) Full separation needs a frontier model (M3b).** With only 7–8B instruct + distills the lines mostly run parallel (or spike at combat); qwen3-32b's isolated synergy point (Silent structured 0.529, the panel max) is the one line that bends away — visible as a standalone marker because its other horizons are intentionally uncollected.
- **Combat plateau, not collapse, for instruct models.** Because Act-1 is winnable by greedy play, the instruct lines *spike* to 1.0 at combat rather than descending monotonically. Documented, not a bug: it reflects that combat's baseline is a near-ceiling, so the discriminating horizons are turn + synergy (findings.md #4). Not a §5.2 instrument artifact — verified against the per-metric tables.
- Chance floors are approximations (esp. removal 0.10); they shift the synergy point but not model ordering. A later engineer changing them should re-render both PNGs and re-spot-check.

**Degenerate-input check (§5.2 / deliverable 4):** a model sitting exactly at each dimension's non-planning baseline maps to y = 0 on every horizon → a flat line along the floor. Confirmed by the formulas: turn damage_ratio 0 → 0; a combat model that only matches greedy-with-no-wins (win 0) → 0, and one that exactly ties the bot's *winning* baseline is by construction ≈1 (the bot is a planner, not a null model — the true "floor" for combat is losing, which → 0); synergy at chance → 0; run at greedy progress 0.78 → 0. The greedy baselines therefore map to the floor line as required. Empirically the closest-to-floor observed runs (mistral IC run 0.068; several Silent runs 0.000; raw qwen2.5 IC synergy 0.000) confirm the floor is reachable and rendered at y≈0.

**When M3b frontier results arrive:** drop the new aggregate JSONs into `results/` (same `*_seeds…json` naming, with `character`/`prompt_format` keys) and re-run `python slay_bench/visualize.py --horizon-curve`; `_discover_aggregates` picks them up automatically and `_MODEL_COLORS` extends by index. Expect the frontier line to sit high across turn/synergy and bend away from the small-model pack at synergy (and possibly hold combat without the deepseek-style crash) — that is the separation the curve was built to show. If a frontier model also survives run above greedy, revisit the run floor constant (0.78) so the right edge stops being a shared 0.

### Addendum 2026-07-12 — run-level anchor is now MEASURED and PER-CHARACTER (was hard-coded 0.78 for both)
**What changed & why.** Review flagged a traceability gap: the run normalization above used `GREEDY_PROGRESS = 0.78` from an *unreproduced* session note, applied identically to both characters despite Silent's documented harsher greedy Act 1. Fixed: `scripts/greedy_baseline.py` (new, committed) measures the greedy floor empirically — FREE, deterministic engine code, zero API calls — by reusing `RunEvaluator` with only the LLM decision hooks overridden by the greedy policy (identical run protocol, same run-dimension seeds `range(base+300, base+300+20)` for bases 42/1042/2042/3042/4042, `n_run=20`, same per-base-then-across-base aggregation as the matrix). Full config + validity/determinism checks in experiment_log 2026-07-12.

**Measured anchors** (replace the single 0.78): **Ironclad progress 0.780 ± 0.012** (12.48 floors, survival 1% — the old note held up exactly), **Silent progress 0.7037 ± 0.062** (11.26 floors, survival 0% — materially lower). `visualize.py` now: `GREEDY_PROGRESS_BY_CHAR = {ironclad: 0.78, silent: 0.7037}` as documented fallback constants, but `load_greedy_anchors()` reads `results/greedy_baseline_<char>.json` when present (single source of truth); `_norm_run` and `normalized_horizon_vector` are now character-aware (`run = clamp01((progress − greedy_floor[char])/(1 − greedy_floor[char]))`). Both PNGs regenerated.

**Before → after normalized run value, per model per character** (Ironclad anchor unchanged → Ironclad column unchanged; only Silent moves):

| Char | Fmt | Model | progress | run (old, 0.78) | run (new) |
|---|---|---|---|---|---|
| Ironclad | struct | qwen2.5-7b | 0.801 | 0.094 | 0.094 |
| Ironclad | struct | llama-3.1-8b | 0.836 | 0.253 | 0.253 |
| Ironclad | struct | mistral-7b | 0.795 | 0.068 | 0.068 |
| Ironclad | struct | deepseek-14b | 0.609 | 0.000 | 0.000 |
| Ironclad | raw | qwen2.5-7b | 0.835 | 0.250 | 0.250 |
| Ironclad | raw | llama-3.1-8b | 0.860 | 0.364 | 0.364 |
| Ironclad | raw | mistral-7b | 0.802 | 0.100 | 0.100 |
| **Silent** | struct | qwen2.5-7b | 0.741 | 0.000 | **0.125** |
| **Silent** | struct | mistral-7b | 0.727 | 0.000 | **0.078** |
| **Silent** | struct | llama-3.1-8b | 0.714 | 0.000 | **0.034** |
| **Silent** | raw | llama-3.1-8b | 0.709 | 0.000 | **0.017** |
| Silent | raw | mistral-7b | 0.690 | 0.000 | 0.000 (progress < 0.704 floor) |
| Silent | raw | qwen2.5-7b | 0.679 | 0.000 | 0.000 (progress < 0.704 floor) |

**Did any qualitative conclusion change?** The Silent run edge was **NOT purely an anchor artifact — it was partly artifact, partly real.** Anchored to Silent's own greedy floor, the Silent-**structured** edge lifts off zero (qwen2.5-7b 0.125, mistral 0.078, llama 0.034) instead of the flat wall it showed under the Ironclad-derived 0.78. But Silent-**raw** mistral/qwen stay at 0 because their progress (0.690/0.679) is genuinely at/below the Silent greedy floor (0.704) — those are real floorings, not anchoring. So: the right edge no longer fully converges to a single 0 on the Silent panel; the "shared collapse floor / on par with greedy, never beating" framing (§5.4) still holds — the lifts are small (≤0.13) and several cells remain at the floor. Caveat (a) above is refined: the run edge converges *near* the floor, exactly-0 only where a model genuinely under-performs greedy. Ironclad panel is unchanged.

**Provenance/validity.** Measured on the same engine the matrix ran on (`git log -- slay_bench/`: last engine change `15d4ffb` 2026-06-12 predates the 2026-06-22 matrix; only later `slay_bench/` commit added `visualize.py`). Determinism verified (repeat run byte-identical). 134/134 tests pass (added `test_greedy_baseline_determinism`).
