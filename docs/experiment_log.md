# Experiment Log

## 2026-07-23 (SHARANGA, gpu_h200_8) — SMOKE PASSED on H200: ~190 tok/s gen (2.3× CSIS A100), 57 s wall — pipeline validated, env unblocked after 3 fixes

**Why:** first run on the Sharanga cluster (BITS Hyderabad, shared account) — validate the exact
pipeline end-to-end + measure tok/s before sizing the registered model ladder (decision_log
2026-07-23). Buy-information-cheapest-first: tiny 4-dim pass, qwen2.5-7b, 1× H200.

**Config.** Interactive `srun` on gpunode7 (gpu_h200_8) after the batch job hit env blockers
(below); vLLM 0.25.1 / torch 2.11.0+cu130, `--max-model-len 16384 --gpu-memory-utilization 0.90`,
benchmark `--n-turn 2 --n-combat 1 --n-synergy 4 --n-run 1 --format structured --seed 42
--run-tag sharanga_smoke` (= no matrix overwrite). Artifacts on-cluster:
`results/qwen2.5-7b_structured_seed42_sharanga_smoke.{json,txt,png}`.

**Anchors (vs CSIS A100 references):**
| Metric | Sharanga H200 | CSIS A100 | Ratio |
|---|---|---|---|
| Generation throughput (batch-1) | **~190 tok/s** sustained | ~82 tok/s | ~2.3× |
| Prompt throughput | ~1,070–1,275 tok/s | ~700–900 | ~1.4× |
| Smoke wall (benchmark only) | **57 s** (`elapsed_seconds` 38.2) | 1m35s | ~1.7× |
| Server cold start (cold node) | ~12–15 min (Lustre load 7.2 min + first compile) | ~3.5 min | — |
| Server warm start (caches hit) | **~90 s** (weights 3.6 s, compile 4 s AOT hit) | — | — |

**Score sanity (per-sample audit vs known 7B matrix behavior — all clean, no boundary values):**
turn dmg .67/1.00 parse_ok=1.0 (expected quantization); combat Cultist win, hp_ratio 1.15,
3 illegal-action / 0 JSON errors; synergy 1/4 archetype (matches the 7B's weak .37); run =
floors 16/16 with hp −16 = died at the boss (correct semantics), survival 0. Instrument behaves
identically to CSIS ⇒ **pipeline valid on Sharanga; ladder sizing can proceed.**

**Env blockers found + fixed (all durable in the env / sbatch, none need root):**
1. **`nvcc` PermissionError killed vLLM's AOT torch.compile** — a non-executable `nvcc` sits in a
   system PATH dir (execvp EACCES; `which` skips it). Fix: `conda install -c nvidia cuda-nvcc`
   into `slaybench` (env bin precedes PATH). CSIS never hit this (vLLM 0.6.6 predates AOT compile).
2. **flashinfer JIT sampling kernel: `curand.h` missing** — conda `cuda-nvcc` ships no library
   headers. `libcurand-dev` fixed the include; ninja STILL failed further in (conda `-ccbin`
   toolchain). Resolution: **`VLLM_USE_FLASHINFER_SAMPLER=0`** (native torch sampler — identical
   sampling semantics, irrelevant at batch≈1; we run temperature 0 anyway). Both packages kept:
   future JIT paths (deep_gemm for the 235B FP8 rung) may want them.
3. **Observability**: first batch job died with a 0-byte vLLM log (block buffering) →
   `PYTHONUNBUFFERED=1`; two ~1-min HF Hub stalls → `HF_HUB_OFFLINE=1`; health-check timeout
   10 → 25 min (cold-node Lustre load alone is 7 min). All baked into `sharanga_smoke.sbatch`.

**Cluster facts learned (also in CLAUDE.md bullet):** gpu_a100_8 DOWN for admin driver
stress-testing (do not trust early A100 tok/s when it returns); **≤4 CPUs per H200 GPU**
submit-time rule; **multi-partition submits rejected** (per-partition associations);
compile/JIT caches live in shared `~/.cache` → warm starts on ANY node after the first.
From the login MOTD (2026-07-23): **scratch auto-purges 15 days after last modification**
(CSIS was 30 — model weights evaporate across gaps; re-prefetch is the plan, scratch is never
storage; results always scp'd to the laptop); **home quota is 40 GiB** (29 used / 11 free at
smoke time — miniconda + `~/.cache` compile caches live there; rules out installing the full
`cuda-toolkit` (~5+ GB) as a flashinfer fallback; if tight: `du -sh ~/miniconda3 ~/.cache/*`).

**Next:** sync the patched sbatch to the cluster (commit+push+pull), then ladder rung 1:
qwen3-32b prefetch + FULL 4-dim matrix (fills the synergy-only gap).

## 2026-07-13 (CLUSTER, gpu-3day) — PARSE PROBE: truncation-vs-malformed ANSWERED — budget-bound deliberation (ratio = 1.0 in all four cells)

**Why:** decide whether the DeepSeek distills' JSON parse failures are token-budget truncation
mid-`<think>` ("budget-bound deliberation") or malformed output ("output-discipline failure") —
unanswerable from pre-instrumentation data (decision_log 2026-07-12 diagnostics entry).

**Config.** `cluster/parse_probe.sbatch` (commit `1e8cd77`+), post-instrumentation harness,
`--run-tag parse_probe` → **diagnostic cells, NEVER foldable into the matrix tables.** Turn
n=20 + combat n=3, **seed 42 only**, max_tokens 8000. Four cells: deepseek-r1-distill-**7b
Ironclad** (both formats) + deepseek-r1-distill-**14b Silent** (both formats). Submitted
2026-07-12 late IST per the contention SOP (`--qos=test-gpu --nodelist=<idle node>`); ~54 min
wall per 7b cell, ~1h44m per 14b cell. Artifacts:
`results/deepseek-r1-distill-{7b,14b_silent}_{structured,raw}_seed42_parse_probe.{json,txt,png}`.

| Cell | Turn parse_fail (of 20) | …truncated | Combat json_parse_err | trunc_err | illegal_act_err | win / hp |
|---|---|---|---|---|---|---|
| 7b IC structured | 10 | **10 (100%)** | 5.67 | **5.67** | 1.67 | .33 / .30 |
| 7b IC raw | 7 | **7 (100%)** | 6.33 | **6.33** | 2.33 | .00 / .00 |
| 14b Silent structured | 1 | **1 (100%)** | 2.33 | **2.33** | 0.33 | 1.00 / .50 |
| 14b Silent raw | 5 | **5 (100%)** | 3.00 | **3.00** | 1.00 | .33 / .21 |

**Verdict: `parse_fail_truncated / parse_fail_n` = 1.0 in ALL four cells, at BOTH horizons**
(combat `truncation_errors == json_parse_errors` exactly). Zero malformed-but-complete
completions anywhere. Per the registered decision rule ⇒ report DeepSeek parse failures as
**"budget-bound deliberation"**: the model spends the entire 8000-token budget inside `<think>`
and never emits the answer. Not a formatting/output-discipline failure.

**Secondary observations.**
- **Counter-split arithmetic verified**: `parse_errors == json_parse_errors +
  illegal_action_errors` exactly in every cell (e.g. 7b raw 8.67 = 6.33 + 2.33). The matrix's
  conflated metric decomposes ≈70–75% truncation + 25–30% valid-JSON-but-illegal — keep citing
  it as **"invalid-action errors."**
- **Probe replicates the matrix** (instrumentation moved nothing): 7b combat win .33/.00 and
  parse_errors 7.3–8.7 ≈ matrix ~8; 14b Silent raw win .33 / hp .21 ≈ the matrix's worst cell
  (.34 / .21).
- **7b structured is WORSE than raw on turn parse** (10 vs 7 truncations; dmg .43 vs .56) —
  consistent with the matrix's structured turn parse_ok floor (.38): the structured prompt
  provokes longer deliberation in the 7b.
- Saved JSONs carry summary counters only (per-sample finish_reason/raw_len records were not
  persisted in the output file) — sufficient for the verdict; raw truncated completions are gone.

**Caveats (travel with any citation):** seed 42 only, combat n=3, four cells; diagnostic
(post-instrumentation) harness run under `--run-tag parse_probe`.

## 2026-07-12 (LOCAL, no API) — GREEDY RUN-LEVEL BASELINE MEASURED (per character; replaces the unreproduced 0.78 anchor)

**Why:** the horizon-collapse curve normalized run-level against a hard-coded
`GREEDY_PROGRESS = 0.78` derived from an *unreproduced* session note ("greedy bot survives
Act 1 ~1/100, avg ~12.5 floors") — no artifact, no seeds, no n — and applied that single
Ironclad-flavoured value to BOTH characters even though Silent's greedy Act 1 is documented
as harsher. Measured it properly (it is FREE: the greedy policy is deterministic engine code,
zero API calls).

**Method / config.** New committed script `scripts/greedy_baseline.py`. It subclasses
`RunEvaluator` (`GreedyRunEvaluator`) and overrides ONLY the LLM decision hooks
(`_llm_combat` → play-every-playable-card greedy AI mirroring `run_loop._resolve_combat`;
`_llm_card_choice` → first non-curse offer; `_llm_boss_relic_choice` → 0), so
`evaluate`/`_play_act` — map traversal, reward/offer counts, elite drops, potion drops, event
auto-pick-0, greedy shop, rest handling — run BYTE-IDENTICAL to the LLM matrix protocol; only
the decisions change from LLM to greedy. `llm_routing=False` (matches the matrix → path pick=0,
rest=REST). Combat capped at `max_combat_turns=50` exactly as the LLM `_llm_combat` is (NOT
run_loop's standalone 100), because this clones the LLM *run* protocol.
- **Seeds:** the exact run-dimension per-sample seeds, derived from code
  (`BenchmarkHarness.run_all`: `run_seeds = range(base+300, base+300+n_run)`), bases
  `42 1042 2042 3042 4042`, `n_run=20` (the matrix's `--n-run 20`) → 20 runs × 5 bases = 100
  runs/character. Aggregation reproduces `_aggregate_summaries`: average the 20 runs within each
  base, then mean ± std of the 5 per-base averages.
- Artifacts: `results/greedy_baseline_ironclad.json`, `results/greedy_baseline_silent.json`
  (per-sample floors/progress/survived + per-base + overall). Gitignored → numbers recorded here.

**Measured greedy baseline (Act 1, n=20/base × 5 bases):**

| Character | avg_floors ± std | avg_progress ± std | survival ± std |
|---|---|---|---|
| Ironclad | 12.48 ± 0.19 | **0.780 ± 0.012** | 0.01 ± 0.022 (1/100) |
| Silent   | 11.26 ± 0.99 | **0.7037 ± 0.062** | 0.00 ± 0.0 (0/100) |

**Did the old "~12.5 / ~1%" note hold up?** For **Ironclad, essentially exactly** — 12.48
floors, 0.780 progress, 1% survival: the session note was a good Ironclad anchor. For **Silent,
NO** — the greedy floor is materially lower (11.26 floors, 0.704 progress, 0% survival). The
shared 0.78 anchor was Ironclad-derived and understated the Silent run edge.

**Validity.** `git log --oneline -- slay_bench/` confirms the last engine/harness change was
`15d4ffb` (5th audit, 2026-06-12); the matrix ran 2026-06-22 and the only later commit touching
`slay_bench/` (`7135bc6`) added `visualize.py` only — so this greedy measurement is on the SAME
engine the matrix ran on. Determinism verified: a repeated run reproduced byte-identical JSONs.
Boundary triage: Ironclad landing at 0.780 (the old note's value) is strong evidence the script's
protocol matches `RunEvaluator`, not a coincidence at a boundary.

**Consequence** (curve anchor now measured + per-character; full before/after per model in
decision_log 2026-07-12 addendum): Ironclad normalized run values unchanged; the **Silent
structured run edge lifts off zero** once anchored to Silent's own floor (qwen2.5-7b 0→0.125,
mistral 0→0.078, llama 0→0.034), while Silent-raw mistral/qwen stay 0 (their progress 0.690/0.679
is at/below the Silent greedy floor 0.704 — genuinely floored, not an artifact). So the Silent
all-zero run edge was **partly an anchor artifact and partly real**. Regression test added
(`test_greedy_baseline_determinism`) → 134 tests pass.

---

## 2026-06-22, completed 2026-07-11 (CLUSTER) — FULL 5-MODEL MATRIX, 5 seeds (CURRENT valid data, supersedes the Qwen-only table)

The four extra models are in: **llama-3.1-8b** (2nd family), **mistral-7b** (3rd family),
**qwen3-32b** (revived reasoning model, synergy-only), **deepseek-r1-distill-14b** and
**deepseek-r1-distill-7b** (reasoning-distill family). All self-hosted (A100 80 GB), same
harness, `--seeds 42 1042 2042 3042 4042` (mean ± std), all 24 aggregates scp'd to the laptop
(`results/<model>*_seeds42_1042_2042_3042_4042.json`). Qwen2.5-7B numbers unchanged (re-pulled,
identical to the 2026-06-13 pass). **Coverage is now ≥3 model families + a reasoning model — the
two biggest D&B gaps from the novelty review are closed.** **2026-07-11: the DeepSeek gap-fill
jobs landed** (14b Silent-raw turn/combat; 7b turn/combat + synergy, all four combos) — every
number below was re-read from the on-disk aggregates on 2026-07-12 and the tables are now the
complete, authoritative matrix (remaining `—` cells are *intentionally not collected*, not
pending; see "Coverage gaps").

### Ironclad — all models, n=20, 5 seeds (mean; structured / raw)

| Model | Turn dmg | Combat win | Combat hp_ratio | Syn archetype | Syn pick | Syn removal | Run floors | Run progress |
|---|---|---|---|---|---|---|---|---|
| qwen2.5-7b | .701 / .665 | 1.00 / 1.00 | 1.04 / 1.07 | .37 / .25 | .47 / .27 | .24 / .02 | 12.81 / 13.36 | .80 / .835 |
| llama-3.1-8b | .487 / .711 | 1.00 / 1.00 | 1.04 / 1.04 | .51 / .41 | .69 / .61 | .15 / .07 | 13.37 / 13.76 | .836 / .86 |
| mistral-7b | .177 / .416 | 1.00 / 1.00 | 1.04 / 1.01 | .33 / .45 | .58 / .36 | .15 / .00 | 12.72 / 12.83 | .795 / .802 |
| deepseek-r1-14b | **.823** / .754 | .92 / .73 | .75 / .55 | .48 / .50 | .53 / .57 | .18 / **.30** | 9.75 / — | .609 / — |
| deepseek-r1-7b | .343 / .427 | .27 / .19 | .11 / .08 | .38 / .43 | .63 / .62 | **.54** / .42 | — / — | — / — |
| qwen3-32b | — / — | — / — | — / — | .53 / .50 | .59 / .58 | .29 / .22 | — / — | — / — |

(qwen3-32b ran synergy only — turn/combat/run not collected. deepseek-r1-14b raw run-level and
deepseek-r1-7b run-level not collected — intentional, see Coverage gaps. ⚠️ deepseek-7b synergy
parse_ok is degraded — 0.92 structured / 0.70 raw, so only ~18.4 / ~14.0 of 20 fixtures scored
per seed; its synergy accs are conditioned on the parseable subset.)

### Silent — all models, n=20, 5 seeds (mean; structured / raw)

| Model | Turn dmg | Combat win | Combat hp_ratio | Syn archetype | Syn pick | Syn removal | Run floors |
|---|---|---|---|---|---|---|---|
| qwen2.5-7b | .663 / .681 | 1.00 / 1.00 | 1.02 / 1.01 | .60 / .42 | .53 / .45 | .36 / .18 | 11.85 / 10.86 |
| llama-3.1-8b | .472 / .810 | 1.00 / 1.00 | 1.01 / 1.01 | .72 / .61 | .49 / .57 | .18 / .16 | 11.42 / 11.34 |
| mistral-7b | .200 / .394 | 1.00 / 1.00 | 1.02 / 0.90 | .34 / .43 | .56 / .20 | .04 / .00 | 11.63 / 11.04 |
| deepseek-r1-14b | .839 / .721 | .57 / .34 | .39 / .21 | .60 / **.66** | .68 / .61 | .15 / .41 | — / — |
| deepseek-r1-7b | .261 / .334 | .28 / .14 | .15 / .05 | .42 / .31 | .50 / .45 | .45 / .41 | — / — |
| qwen3-32b | — / — | — / — | — / — | **.80** / .64 | .57 / .46 | **.55** / .32 | — / — |

(⚠️ deepseek-7b Silent synergy parse_ok 0.91 structured / 0.69 raw → ~18.2 / ~13.8 of 20 scored
per seed. deepseek-14b Silent-raw turn parse_ok 0.78; its combat parse_errors 4.97/combat.)

### ✅ Gap-fill jobs LANDED (submitted 2026-06-22, retrieved 2026-07-11, folded 2026-07-12)
- **deepseek-r1-distill-14b Silent raw turn/combat** (`gpu-3day`, `turn_combat_models_silent.sbatch`):
  turn dmg **.721** (legal .75, parse_ok .78), combat win **.34**, hp_ratio **.21**, parse_errors
  4.97 — the 14b's worst combat line; Silent raw is where its `<think>` verbosity costs the most.
  14b Silent is now turn/combat/synergy complete in both formats; only Silent run remains open
  (a floor dim, intentionally skipped).
- **deepseek-r1-distill-7b turn/combat + synergy, all four combos** (`gpu-1day` + `gpu-short`):
  the collapse generalizes matrix-wide — turn dmg .26–.43, combat win .14–.28, hp_ratio .05–.15,
  combat parse_errors 7.9–8.3 in every combo. **7b run-level intentionally skipped** (it's the
  "small distill fails the JSON contract" data point, not a competitive line; run is a floor
  effect anyway). One surprise in the wreckage: **7b synergy removal is strong** (.41–.54;
  IC structured **.54** is the 2nd-best removal in the whole matrix, behind only qwen3-32b
  Silent .55) — but read with the parse_ok caveat above (only the parseable ~70–92% scored).

### Coverage gaps (what is NOT collected, so the matrix is read honestly)
- **qwen3-32b: synergy only** (turn/combat/run all null). It's a synergy data point — but the
  decisive one: its Silent-structured archetype **0.80** and removal **0.55** are the highest
  in the entire matrix, and it's the only reasoning model that *stays terse* (parse_ok=1.0).
- **deepseek-r1-14b: Ironclad complete incl. run; Silent complete on turn/combat/synergy both
  formats** (gap-fill 2026-07-11); no Silent run (floor dim, skipped).
- **deepseek-r1-7b: turn/combat + synergy complete, all four combos** (gap-fill 2026-07-11);
  run-level intentionally skipped (collapse line — see findings).
- New models' run-level is sparse (only deepseek-14b Ironclad, llama, mistral have it) but
  run-level is a floor effect anyway → not a blocker for the headline claims.

### Headline findings (full prose in docs/findings.md)
1. **The horizon-collapse story now has model separation.** qwen3-32b (reasoning) tops synergy
   (Silent archetype 0.80, removal 0.55) — the *only* model that pulls clearly away from the
   7–8B pack at the deck-building horizon. This is the frontier-model line the curve needed.
2. **Reasoning ≠ free win — the distill *family* splits hard by size.** deepseek-r1-**14b** is
   strong at short horizons (best turn dmg both characters: IC 0.823, Silent 0.839) but its
   verbose `<think>` decode *hurts* longer horizons: combat win drops to 0.92/0.73 on Ironclad
   (first model below 1.0), Silent combat to 0.57 structured / **0.34 raw** (hp_ratio 0.21),
   and Ironclad run floors crash to **9.75 — below the greedy ~12.5 floor** (it overthinks
   itself to death). deepseek-r1-**7b** collapses outright in *every* combo (turn 0.26–0.43,
   combat win 0.14–0.28, parse_errors ~8/combat) — the small distill can't keep the JSON
   contract. Anomaly worth a sentence in the paper: 7b's synergy **removal** stays high
   (.41–.54, 2nd-best in the matrix on IC structured) — the judgment task survives the
   execution collapse (with the parse_ok-conditioning caveat).
3. **Format ablation replicates across families but is character/model-dependent in sign.**
   Structured wins synergy for qwen2.5/llama; mistral *reverses* on Ironclad archetype
   (raw .45 > structured .33). Turn: llama & mistral are *better in raw* on both characters
   (llama Silent raw .810 vs structured .472) — opposite of qwen2.5 Ironclad. The most robust
   cross-model format signal is **synergy removal** (structured ≥ raw for qwen2.5, llama,
   mistral, qwen3-32b AND deepseek-7b: e.g. mistral .15→.00, qwen2.5 .24→.02) — with **one
   documented exception: deepseek-14b reverses removal in BOTH characters** (IC .18
   structured / **.30** raw; Silent .15 / **.41**), so state it as "structured ≥ raw for 5 of
   6 models; the sole reversal is the verbose-`<think>` 14b distill."
4. **Combat/run stay format- and largely model-insensitive on outcome** (almost everyone wins
   1.0, hp_ratio ≈ 1.0, floors ≈ greedy ~12.5) — except the reasoning models, which are the only
   ones that *lose* combats. Confirms the multi-horizon thesis: model differences surface at the
   reasoning horizons (synergy), wash out at the engine-survival horizons (combat/run).

## 2026-06-13 (CLUSTER) — PAPER-GRADE 4-DIMENSION RESULTS, Qwen2.5-7B, 5 seeds (CURRENT valid data)

**First complete paper-grade matrix.** Qwen2.5-7B-Instruct, self-hosted (vLLM 0.6.6, A100
80 GB, csis.cn2), `--seeds 42 1042 2042 3042 4042` (spaced 1000 apart → disjoint per-sample
windows, real std), both prompt formats. Ironclad n=20 all four dimensions; **Silent now also
complete on all four** (synergy 2026-06-13; turn/combat/run added 2026-06-14). All
`results/qwen2.5-7b*_seeds42_1042_2042_3042_4042.json`
scp'd to the laptop. This **supersedes all stale pilot turn/combat numbers and all earlier
synergy data** (this is the first multi-seed, self-hosted, post-5-audit pass). parse_ok=1.0
on every dimension/format → instrument clean.

**Cluster jobs:** turn+combat (job 7539), synergy (both characters), run-level structured +
raw (jobs 7542 fixed → resubmit, 7545). The lone failure (7542 run-level, 0 completed runs)
was a stale vLLM holding :8000 — fixed in `cluster/lib.sh` (`f2c9a6b`: per-job port,
`fuser -k` before launch, readiness probe matches SERVED_NAME, bind-failure fast-fail).

### Ironclad — turn / combat / synergy / run (n=20, 5 seeds, mean ± std)

| Dimension | Metric | structured | raw |
|---|---|---|---|
| Turn | avg_damage_ratio | 0.701 ± 0.078 | 0.665 ± 0.175 |
| Turn | legal_rate | 0.78 ± 0.057 | 0.73 ± 0.179 |
| Combat | win_rate | 1.00 ± 0.0 | 1.00 ± 0.0 |
| Combat | avg_hp_ratio | 1.042 ± 0.025 | 1.065 ± 0.020 |
| Combat | avg_parse_errors | 2.51 ± 0.26 | 2.59 ± 0.34 |
| Synergy | archetype_acc | 0.37 ± 0.027 | 0.25 ± 0.0 |
| Synergy | card_pick_acc | 0.47 ± 0.076 | 0.27 ± 0.067 |
| Synergy | removal_acc | 0.24 ± 0.022 | 0.02 ± 0.027 |
| Run | survival_rate | 0.03 ± 0.027 | 0.00 ± 0.0 |
| Run | avg_floors_reached | 12.81 ± 1.19 | 13.36 ± 0.79 |
| Run | avg_progress | 0.80 ± 0.075 | 0.835 ± 0.049 |
| Run | avg_draft_coherence | 0.36 ± 0.034 | 0.33 ± 0.033 |

(parse_ok = 1.0 on turn + synergy in both formats.)

### Silent — turn / combat / synergy / run (n=20, 5 seeds, mean ± std)

Synergy collected in the 2026-06-13 pass; **turn/combat/run added 2026-06-14** via the new
`cluster/turn_combat_silent.sbatch` + `cluster/run_level_silent.sbatch` (Silent counterparts —
the Ironclad turn/combat/run sbatch jobs scope themselves to Ironclad). Silent is now a
**complete 4-dimension matrix**, both formats. parse_ok=1.0 throughout.

| Dimension | Metric | structured | raw |
|---|---|---|---|
| Turn | avg_damage_ratio | 0.663 ± 0.035 | 0.681 ± 0.047 |
| Turn | legal_rate | 0.87 ± 0.045 | 0.84 ± 0.082 |
| Combat | win_rate | 1.00 ± 0.0 | 1.00 ± 0.0 |
| Combat | avg_hp_ratio | 1.024 ± 0.015 | 1.007 ± 0.021 |
| Combat | avg_parse_errors | 0.92 ± 0.179 | 3.38 ± 0.192 |
| Synergy | archetype_acc | 0.60 ± 0.0 | 0.42 ± 0.027 |
| Synergy | card_pick_acc | 0.53 ± 0.084 | 0.45 ± 0.05 |
| Synergy | removal_acc | 0.36 ± 0.022 | 0.18 ± 0.045 |
| Run | survival_rate | 0.00 ± 0.0 | 0.01 ± 0.022 |
| Run | avg_floors_reached | 11.85 ± 0.449 | 10.86 ± 0.781 |
| Run | avg_progress | 0.741 ± 0.028 | 0.679 ± 0.049 |
| Run | avg_draft_coherence | 0.344 ± 0.035 | 0.348 ± 0.005 |

**Silent-specific observations (new turn/combat/run):**
- **Turn-level format effect vanishes / mildly reverses on Silent** (raw 0.681 ≈ structured
  0.663, within noise; raw even nudges ahead). Unlike Ironclad, where structured won turn
  (0.701 vs 0.665). → The turn-format effect is **character-dependent**, not universal; the
  robust format signal lives in synergy for both characters.
- **Combat format-insensitive on outcome** (both win 1.0, hp_ratio ≈ 1.0–1.02, on par with
  greedy). The only format trace is parse_errors: raw 3.38 vs structured 0.92 — the verbose
  English combat state is harder to act on cleanly even when it doesn't change the win.
- **Silent reaches fewer floors than Ironclad** (10.9–11.9 vs 12.8–13.4) and survival ≈ 0.
  Silent's lower-block starter makes the post-audit Act-1 greedy combat harsher; survival is
  still a floor effect → report avg_floors / avg_progress, frame "on par, not beating."

**Key results:**
- **Structured beats raw on every reasoning-heavy metric, both characters.** Synergy is the
  sharpest: Ironclad card_pick 0.47→0.27, removal 0.24→**0.02**, archetype 0.37→0.25; Silent
  archetype 0.60→0.42, removal 0.36→0.18. **This is the seed-matched format ablation landing
  cleanly on a self-hosted model** (the novelty claim). Turn raw also has ~2× the variance of
  structured (±0.175 vs ±0.078) — verbose prompts make the 7B less consistent.
- **Combat / run are format-insensitive.** Both formats win 100% of the scripted combats with
  hp_ratio ≈ 1.04–1.07 (on par with the greedy bot, NOT beating it — the prior >100% artifact
  is fixed) and reach ~12.8–13.4 of 16 floors before dying at the Act-1 boss. These dimensions
  are dominated by engine survival, not prompt comprehension, so format barely moves them.
- **Run-level survival is near-floor (0.03 / 0.0).** Expected: the scripted greedy baseline
  itself survives Act 1 only ~1% of the time under the post-audit engine (avg ~12.5 floors).
  So survival_rate has a floor effect; **avg_floors_reached / avg_progress are the
  discriminating run-level metrics** (Qwen 12.8–13.4 floors ≈ greedy ~12.5 → on par).
- **Silent synergy > Ironclad synergy** (archetype 0.60 vs 0.37; removal 0.36 vs 0.24,
  structured) — consistent with the earlier llama/scout finding that Silent's
  Poison/Shiv/Block/Discard labels read more literally off the cards.
- **raw archetype collapses to a constant "Block" guess — VERIFIED per-sample (not a bug).**
  Ironclad raw labels **17/20 fixtures "Block" every seed** (std≈0 is the collapse signature).
  The 20 fixtures are 5 each Exhaust/Aggro/Strength/Block; raw's 5/20 is **exactly the 5 Block
  decks** → raw archetype acc = the Block base rate of its single guess (0.25), *below* the
  same model's structured 0.35–0.40. Confirmed prompt-driven, not instrument: (a) fixtures do
  cycle all archetypes; (b) structured on the same fixtures spreads answers (Block 10–11,
  Strength 6–8, Aggro 1–3) and scores 7–8/20 — both formats would collapse if the instrument
  were broken; (c) parse_ok=1.0. Verbose English mentions Block/defense in nearly every card
  description → 7B anchors on it; compact JSON forces reading the card list. Per-sample data in
  `results/qwen2.5-7b_{raw,structured}_seed*.json` (`synergy.samples`). See docs/findings.md.

**Greedy baseline anchor (for the paper):** scripted greedy bot survives Act 1 ~1/100,
avg ~12.5 floors. Use this to frame run-level/combat as "on par with greedy," never "beats."
> ⚠️ **Superseded 2026-07-12 — now MEASURED per character** (see the 2026-07-12 entry at the top).
> This note was an unreproduced Ironclad-flavoured estimate. Measured: **Ironclad 12.48 floors /
> 0.780 progress / 1% survival** (the note held up for Ironclad), **Silent 11.26 floors / 0.704
> progress / 0% survival** (Silent's greedy floor is lower — the shared 0.78 anchor understated
> the Silent run edge). Framing ("on par with greedy, never beats") is unchanged and still correct.

---

## 2026-06-13 (CLUSTER) — first real self-hosted runs on BITS CSIS Slurm (Qwen2.5-7B)

**Hardware:** A100 80 GB (csis.cn2), vLLM 0.6.6 + transformers 4.47.1 + torch 2.5.1+cu124,
served `Qwen/Qwen2.5-7B-Instruct` as `qwen2.5-7b` via `cluster/*.sbatch`.

**Smoke (job 7536) — PASSED.** Tiny full pass (`--n-turn 2 --n-combat 1 --n-synergy 4
--n-run 1`, structured, seed 42) ran end-to-end and wrote `results/qwen2.5-7b_structured_seed42.*`.
- Wall time: **1m35s** (`time` real) for the benchmark; vLLM startup ~3.5 min separately.
- Throughput from `vllm_7536.log`: **~82 tok/s generation**, ~700–900 tok/s prompt.
- Used to calibrate `run_level.sbatch`: n=5 validation ≈18 min; paper-grade n=20×5 seeds ≈4h.

**Turn+combat re-baseline (job 7539) — RUNNING.** `--only turn combat --n-turn 20 --n-combat 20
--seeds 42 43 44 45 46` ×2 formats, Ironclad, Qwen2.5-7B. Early turn-level signal healthy:
parse_ok=1.0 (instrument clean), ~50/50 legal-optimal vs illegal-bust for the 7B, dmg_ratios
clustering at 1.0/0.67/0.0 (quantization from short low-energy opening turns, not a bug).

**Cluster issues hit + resolved (full notes in CLAUDE.md "CLUSTER GOTCHAS"):**
- `lib.sh` defaulted to `Qwen/Qwen3-32B` which vLLM 0.6.6 can't load → defaulted to Qwen2.5-7B (`30551a9`).
- `#SBATCH --time=24:00:00` rejected by QOS (`QOSMaxWallDurationPerJobLimit`) → submit with `--time=03:00:00` override.
- Confirmed result filenames are character-namespaced (Ironclad untagged, Silent `_silent`),
  so the `--only` merge + synergy's both-character loop don't collide — no code change needed.

**Next:** finish 7539 → verify tail → `sbatch --time=03:00:00 cluster/synergy.sbatch` → run_level.

---

## 2026-06-12 (GPU prep) — `--provider local` adapter (NO API runs; mock + unit verification)

**What ran:** full test suite (**118/118**, +3 new LocalLLM regression tests over the
4th-audit 115/118 baseline — request shape/URL via stubbed `urlopen`, server-error
surfacing, `build_llm` wiring) and the mock pipeline (`--provider mock`, seed 42, tiny
full pass) — green end-to-end. No paid/free/GPU API calls (the GPU is not yet available).

**What changed:** added `LocalLLM` (OpenAI-compatible self-hosted client) + `--provider
local --base-url`. Commit `a36b42d`. No engine/scoring change → **no data-validity impact**;
synergy n=20 (2026-06-10, de-biased) remains the only valid data. This is pure
infrastructure prep for the M3a GPU phase. Next experiment is the GPU smoke test once
access lands (record tok/s → sizes run-level n).

## 2026-06-11 (later) — 3rd audit + fix batch (NO API runs; mock verification only)

**What ran:** full test suite (**102/102**, was 77; +25 regression tests) and mock
pipeline (`--provider mock`, seed 42) for Ironclad structured + raw and Silent
structured — green end-to-end. No API calls.

**What changed (data-validity consequences):** 40 new bugs fixed
(`docs/bug_audit_2026-06-11.md`). Combat dynamics changed for a FOURTH time:
HP-loss now bypasses block, Havoc no longer shrinks/duplicates decks, and —
biggest — **enemy block now actually exists** (it was wiped before the player's
turn, so all enemy blocking moves were no-ops; enemies are tougher). Turn-eval
duplicate-index replay loophole closed (legality is stricter — turn scores not
comparable to stale ones for this reason too). Run-level: Neow's 1-HP boon removed
from the mid-run event pool, events no longer repeat → the first valid run-level
pass will be on a fairer, harder run loop. **Synergy n=20 (2026-06-10, de-biased)
remains the only valid data — unaffected** (one prompt-byte change: Blood for
Blood's exhaust flag in a single Aggro offer is now false).

## 2026-06-11 — Engine-fidelity fix batch (NO API runs; mock verification only)

**What ran:** full test suite (77/77, was 56; +21 regression tests) and mock pipeline
(`--provider mock`, structured, seed 42) for BOTH characters — green end-to-end, charts
written. No paid/free API calls this session.

**What changed (data-validity consequences):**
- All of `docs/bug_audit_2026-06-10.md` Part 2 implemented + 9 new Part 3 fixes (2 critical:
  vanishing played cards via dataclass `__eq__`; double exhaust emit). Combat dynamics
  changed → turn/combat numbers remain stale (now for a third reason); **synergy n=20
  below is still the only valid data** (static deck snapshot, no combat involved).
- ⚠️ The 4 **Aggro fixture decks changed** (Perfected Strike → Cleave/Wild Strike/Clash,
  audit item 2.8): the next synergy run regenerates point estimates. Aggregates stay
  comparable (same archetype balance, same offers/picks/removals); per-row values for the
  4 Aggro fixtures do not line up with the saved seed-42 files.
- Elites now drop relics, MERCHANT floors act, Maw Bank/Peace Pipe/etc. live → the
  (still-pending) first valid run-level pass will exercise a substantially richer run loop.

## 2026-06-10 — Synergy n=20, both characters, DE-BIASED instrument (CURRENT valid synergy data)

**Config:** `--only synergy --n-synergy 20`, seed=42, free Groq, post-bug-sweep code.
8 runs = 2 models × 2 formats × {Ironclad, Silent}. Silent is **first-ever synergy data**.
Ran via `.venv\Scripts\python.exe` (system Python lacks `groq` — gotcha logged below).

⚠️ **These numbers REPLACE an earlier biased run from the same day.** The first n=20 pass
ran on a synergy instrument with a positional confound (expert pick was at offer index 0 in
35/40 fixtures) + one mislabeled fixture; those card-pick numbers were not interpretable.
Fixed in commit `5db7063` (offer rotation cycles the correct index 0→1→2; fixture #18 pick
corrected; strict single-name archetype match) and re-run. Rotation verified: expert-pick
position is now uniform {0:7,1:7,2:6} and the model spreads its answers {0:5,1:9,2:6} rather
than parroting 0. See "Bugs Fixed" #synergy-instrument in CLAUDE.md.

| Character | Model | Format | n | Archetype | Card Pick | Removal | Parse |
|---|---|---|---|---|---|---|---|
| Ironclad | llama-3.1-8b | structured | 20 | 0.55 | 0.65 | 0.15 | 1.0 |
| Ironclad | llama-3.1-8b | raw | 20 | 0.40 | 0.65 | 0.05 | 1.0 |
| Ironclad | scout-17b | structured | 20 | 0.70 | 0.75 | 0.25 | 1.0 |
| Ironclad | scout-17b | raw | 20 | 0.45 | 0.70 | 0.15 | 1.0 |
| Silent | llama-3.1-8b | structured | 20 | 0.75 | 0.35 | 0.15 | 1.0 |
| Silent | llama-3.1-8b | raw | 20 | 0.60 | 0.65 | 0.15 | 1.0 |
| Silent | scout-17b | structured | 20 | 0.75 | 0.70 | **0.60** | 1.0 |
| Silent | scout-17b | raw | 20 | **0.80** | **0.75** | 0.20 | 1.0 |

**Per-archetype archetype-ID, all 8 combos pooled (20 attempts each, 40 for Block):**

| Archetype | Correct | Character |
|---|---|---|
| Aggro | 19/20 = 95% | Ironclad |
| Poison | 19/20 = 95% | Silent |
| Shiv | 18/20 = 90% | Silent |
| Block | 34/40 = 85% | both |
| Strength | 8/20 = 40% | Ironclad |
| **Exhaust** | **1/20 = 5%** | Ironclad |
| **Discard** | **1/20 = 5%** | Silent |

**Key results (n=20, both characters, de-biased):**
- **Mechanic-defined archetypes are the universal blind spot — now airtight.** Pooled over
  all 8 combos, **Exhaust 5% and Discard 5%** sit far below every surface-readable archetype
  (Aggro/Poison/Shiv/Block 85–95%). Both characters' miss is exactly the archetype defined by
  a *payoff mechanic* (exhaust / discard), not a card-name keyword. Strength (40%) is the
  intermediate case — frequently "Aggro" because Strength decks are Strike-heavy.
- **Card-pick survived de-biasing** (0.65–0.75 for both models on most combos, vs ~0.33
  chance) — so the **name-vs-play dissociation is real, not a positional artifact**: models
  judge local card quality well even on decks they cannot label. (The lone exception, Silent
  llama structured at 0.35, is a genuine weak spot, not the old bias.)
- **Silent archetype-ID ≥ Ironclad** (0.60–0.80 vs 0.40–0.70). Plausibly Silent labels
  (Poison/Shiv/Block/Discard) read more literally off the cards than Ironclad's abstractions.
- **scout-17b Silent structured removal 0.60** is still the standout — the removal blind spot
  is much weaker on Silent for the bigger model. Removal stays near-floor (0.05–0.25)
  everywhere else.
- parse_ok = 1.0 everywhere.

**Caveat:** all 8 are seed=42 only (one fixture pass; deterministic). For paper-grade error
bars still need `--temperature 0.7` k-sampling or a seed sweep — the harness supports both.

---

## 2026-06-10 — No new runs; harness extended for A* acceptance (code-only)

**Status:** No experiments — run-level remains blocked on free Groq TPM (paid tier pending).
Harness changes that affect FUTURE runs (commit d35771e):
- Silent character (full card set + 20 synergy fixtures; Ironclad fixtures expanded 8 → 20)
- Multi-act runs (`--acts 3`), `--temperature`, `--seeds` (mean±std), `--llm-routing`
- Relic lifecycle split (on_pickup/register) — relics no longer stack across a run

**Comparability note:** the relic-stacking fix changes run-level dynamics, so any future
run-level numbers are NOT comparable to pre-2026-06-10 ones — which is moot, since all
existing run-level data was already invalid (map dead-end + EventBus bugs).

**Bug sweep (same day, later):** a full logic+code audit fixed 21 bugs (see CLAUDE.md
"Bugs Fixed"). The player-debuff timing fix (tick at end of round, not before enemy
attacks) **changes combat-level dynamics too**: enemy-applied Weak/Vulnerable now actually
affect the player, so the greedy baseline and LLM combats both take more damage (the Act-1
determinism fixture flipped from survived=True/hp=74 to survived=False/hp=0). ⇒ **Pilot
turn/combat numbers in the tables below were collected on the pre-sweep engine and are not
comparable to future runs.** Synergy is unaffected (static deck snapshot, no combat).
Also fixed before any paid run could be burned: the multi-seed aggregator was emitting
`null` for most means (wrong metric key names). 47 tests pass (24 benchmark + 10 combat +
13 run; needs `PYTHONIOENCODING=utf-8` on Windows consoles).

---

## 2026-06-07 — Synergy re-run on HAND-CRAFTED fixtures, n=8 (CURRENT valid synergy data)

**Config:** `--only synergy --n-synergy 8`, both formats, both models, seed=42.
**Status:** Valid + current. Supersedes ALL earlier synergy numbers (which used RNG-drafted
decks). 8 fixtures = one pass over the fixed set (2 per archetype × 4 archetypes); all 8
classify confident, 0 ambiguous.

| Model | Format | Archetype | Card Pick | Removal | Parse OK |
|---|---|---|---|---|---|
| llama-3.1-8b-instant | structured | 50.0% | 100% | 25.0% | 100% |
| llama-3.1-8b-instant | raw | 37.5% | 62.5% | 12.5% | 100% |
| llama-4-scout-17b | structured | 75.0% | 75.0% | 25.0% | 100% |
| llama-4-scout-17b | raw | 50.0% | 100% | 12.5% | 100% |

**Per-archetype identification (8 attempts each = 2 decks × 2 models × 2 formats):**

| True archetype | Correct | Models said instead |
|---|---|---|
| Block | 7/8 | one "Strength" |
| Aggro | 8/8 | — |
| Strength | 2/8 | almost always "Aggro" |
| Exhaust | 0/8 | ALWAYS "Aggro" |

**Key findings (NEW, from clean fixtures):**
- **Exhaust archetype is never recognised** (0/8) — every model/format calls it "Aggro".
  Strength also weak (2/8). Models name an archetype only when its signature is a simple
  surface pattern (Block, generic Aggro); they miss mechanic-defined strategies (Exhaust
  payoff) even with signature cards present. Systematic, not noise.
- **Name-vs-play dissociation:** card-pick is high (62.5–100%) even on decks the model can't
  label — local card-quality judgement is strong, abstract strategic label is weak.
- **Removal still near-zero** (12.5–25%) — the 25% comes only from Block fixtures where the
  removal target coincides; models cut situational cards, not basic Strike.
- scout-17b (structured) is the best archetype identifier (75%). No single format wins
  outright: raw helps llama card-pick, structured helps scout archetype ID.

**Note:** the old `67%/100%` archetype figures (RNG-draft era) are RETIRED. They came from a
3-deck RNG sample with an Aggro-biased heuristic and do not reflect the fixed-deck eval.

---

## 2026-06-07 — qwen3-32b DROPPED (no valid data on free tiers)

**Status:** Excluded from the study. Result files deleted.

qwen3-32b (reasoning model) was wired and attempted on both providers; neither free
tier could produce valid data:
- **OpenRouter free:** ~30–80 tok/s → n=5 run-level = 1.5–3h; free credits exhausted
  mid-run → HTTP 402 Payment Required.
- **Groq free:** 6000 TPM cap truncated its reasoning mid-`<think>` → parse-failure
  cascade, 0% across every dimension (turn/combat/synergy/run all 0; combat parse
  errors 7.67/sample).

Root cause is infrastructural, not a model-capability result — so the 0% scores are NOT
reported as qwen3 performance. A reasoning model needs a PAID tier (paid Groq preferred:
uncapped TPM + ~400–1000 tok/s). Revisit = future work. See docs/notes.md, docs/report.md.

---

## 2026-06-07 — Synergy re-run (post synergy-fix): all models, seed=42  [SUPERSEDED]

**Config:** `--only synergy`, n_synergy=3, both formats, both models
**Status:** ⛔ SUPERSEDED by the hand-crafted n=8 run above. These used RNG-drafted decks +
an Aggro-biased heuristic (only ~3/10 decks confidently labelled); the 67%/100% figures are
retired. Kept for history only.

| Model | Format | Archetype | Card Pick | Removal | Parse OK |
|---|---|---|---|---|---|
| llama-3.1-8b-instant | structured | 67% | 33% | 0% | 100% |
| llama-3.1-8b-instant | raw | 100% | 33% | 0% | 100% |
| llama-4-scout-17b | structured | 67% | 67% | 0% | 100% |
| llama-4-scout-17b | raw | 100% | 33% | 0% | 100% |

**Key findings:**
- Removal 0% confirmed genuine model failure (not a bug). Expert says remove Strike; models say Disarm/Battle Trance/Bash — reasoning about card quality, not deck cycling.
- Raw format = 100% archetype acc for both models. Structured = 67%.
- Scout-17b better at structured card pick (67% vs 33%).

---

## 2026-06-07 — Post-fix run: llama-3.1-8b-instant, seed=42

**Config:** n_turn=5, n_combat=3, n_synergy=3, n_run=5, both formats
**Status:** Turn/combat/run valid. Synergy invalid (pre-synergy-fix) — needs re-run with `--only synergy`.

| Metric | Structured | Raw |
|---|---|---|
| Turn damage ratio | 36.7% | 69.6% |
| Turn legal rate | 60% | 100% |
| Combat win rate | 100% | 100% |
| Combat HP ratio | 112.3% | 113.8% |
| Synergy archetype | 0% ⚠ | 66.7% ⚠ |
| Synergy best card | 33.3% ⚠ | 33.3% ⚠ |
| Synergy removal | 0% ⚠ | 0% ⚠ |
| Run survival | 20% | 40% |
| Run avg floors | 13.4/15 | 13.4/15 |
| Run HP fraction | 93.8% survivors | 60.6% survivors |
| Run draft coherence | 36.4% | 40.9% |
| **Overall** | **41.9%** | **60.7%** |

**Notes:** Run-level now real (map+EventBus bugs fixed). Raw significantly outperforms structured overall. Synergy marked ⚠ — synergy eval used starter deck throughout; fix landed after this run.

---

## 2026-06-07 — Pilot: llama-3.1-8b-instant, seed=42

**Config:** n_turn=5, n_combat=3, n_synergy=3, n_run=1, both formats

| Metric | Structured | Raw |
|---|---|---|
| Turn damage ratio | 36.7% | 69.6% |
| Turn legal rate | 60% | 100% |
| Combat win rate | 100% | 100% |
| Combat HP ratio | 112.3% | 108.5% |
| Synergy archetype | 66.7% | 100% |
| Synergy best card | 100% | 33.3% |
| Synergy removal | 0% | 0% |
| Run survival | 0% | 0% |
| Run floors | 5/15 | 5/15 |
| **Overall** | **48.1%** | **53.5%** |

**Notes:** Run floors were artificially stuck at 5/15 due to map dead-end bug (now fixed). Run results invalid — need re-run.

---

## 2026-06-07 — Pilot: meta-llama/llama-4-scout-17b-16e-instruct, seed=42

**Config:** n_turn=5, n_combat=3, n_synergy=3, n_run=1, both formats

Results saved in `results/meta-llama-llama-4-scout-17b-16e-instruct_*.txt`. Need to review.

---

## Bugs that invalidated earlier results

1. **Map dead-end** — all pre-fix run results show floors=5/15, invalid.
2. **EventBus stacking** — survival=1.0, hp_fraction=1.0 for weak models, invalid.
Both fixed as of 2026-06-07. Any runs before these fixes need to be discarded and re-run.
