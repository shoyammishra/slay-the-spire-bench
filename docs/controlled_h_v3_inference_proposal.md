# Controlled-H v3 confirmatory inference — PROPOSAL (not frozen)

**Status:** draft for user approval, 2026-09-30. Nothing here is frozen or authorized.
It becomes binding only as a separately versioned config + digest, written **before** any
model sees a v3 fixture. Fixture protocol: `configs/controlled_h_v3_heldout.json`
(decision_log 2026-09-29). Rationale for the estimand: decision_log 2026-09-29 (DiD proposal)
and experiment_log 2026-09-29/30 (8B/14B development pilots).

## 1. Question

Does a model use additional required lookahead? Operationally: when the H8-optimal first
action differs from the H1-optimal one (sensitive fixtures), does moving the stated horizon
from 1 to 8 change first-action quality *beyond* the generic effect of stating a longer
horizon, measured on fixtures where the optimal action does not change (controls)?

## 2. Design

- **Fixtures:** the v3 release — 440 sensitive + 440 control per character (Ironclad,
  Silent), never shown to any model. Development fixtures (v2 release, 8B/14B/32B pilots)
  are never pooled with v3 data.
- **Horizons:** H1 and H8 only (primary). H2/H4 dropped from the confirmatory run: they are
  not needed for the estimand, and "control" is defined on H1/H8 only (8B H2 dip).
  Optional descriptive H2/H4 run later, labelled exploratory.
- **Queries per model/format:** 1,760 fixtures × 2 = **3,520**. Query order: H1/H8 order
  counterbalanced by fixture-ID hash; one response per cell, no re-sampling.
- **Generation (as in the dev pilots):** thinking on, temperature 0, top-p 1, seed 42,
  16,000 output tokens, 32,768 context, pinned vLLM 0.8.5.post1 / Transformers 4.51.3,
  structured format.
- **Throughput change (needs your OK):** the pilots ran one request at a time. Allowing
  **8 concurrent requests** would cut wall time ~4–6×. Batching can make greedy decoding
  slightly non-deterministic across runs; that would be recorded as a stated property of
  the run, not hidden.

## 3. Estimands and tests

- **Primary (per character, per model):** `DiD = mean_sens(q8 − q1) − mean_ctrl(q8 − q1)`,
  with q = effective quality (truncated/unparseable/illegal = 0, as frozen in v2).
  Two-sided, α = .025 per character (Bonferroni over 2), stratified bootstrap CI
  (10,000 replicates, seed fixed per character). Smallest effect of interest ±.10.
- **Power (pooled SDs from 8B+14B+32B dev data: IC sens .50 / ctrl .30; Silent sens .42 /
  ctrl .48):** 440/440 gives SE ≈ .028–.030 ⇒ **power .91 (IC) / .86 (Silent)** at .10.
  Planning values only — n = 10–17 per stratum behind the SDs.
- **Pre-specified secondary — action switch (myopia):** on sensitive fixtures, the rate at
  which the H8 response picks an H8-optimal action vs an H1-optimal action; McNemar-style
  paired comparison against the H1 response. Motivated by the dev signal (8/12 H8 choices
  were H1-optimal, 1/12 H8-optimal) — that signal is NOT itself evidence.
- **Secondary — legacy mixture** (.25 sens + .75 ctrl ΔH), for continuity with v2 only.
- **Cross-model contrasts (only if ≥2 models run):** difference of DiDs between models,
  paired by fixture, with its own multiplicity correction. Never "model A significant,
  model B not".

## 4. Validity gates (fail-closed)

- Truncation ≤ 1% of queries per model/character (dev pilots: 1/48 per model).
- Missing pairs: a pair with a transport/execution failure is excluded and reported;
  truncation/parse/illegal responses stay in as quality 0 (they are model behaviour).
  If > 2% of pairs are excluded, primary inference is withheld.
- Report per H: parse rate, legality, truncation, prompt length, completion tokens — to rule
  out "the H effect is a parsing/length artifact" (main-track gate).

## 5. Decisions needed from you

1. **Approve DiD as the primary** (replacing the v2 mixture) — yes / no.
2. **Models:** proposed Qwen3-8B, Qwen3-14B, Qwen3-32B (within-family size axis) **plus one
   other family** (ICML gate: any scaling claim needs ≥2 families). Candidates already
   cached on Sharanga scratch: Llama-3.3-70B-Instruct, Mistral-Small-3.1-24B, Gemma-3-27B
   (none is a thinking model — that is a confound to disclose), or a frontier API model via
   the professor's M3b access.
3. **Allow 8-way request concurrency** (§2).

## 6. Cost estimate (H100, from measured pilot latency; serial / with 8-way concurrency)

| Model | Mean latency | 3,520 queries serial | ~8-way concurrent |
|---|---|---|---|
| Qwen3-8B | 30 s | ~29 GPU-h | ~6–8 h |
| Qwen3-14B | 37 s | ~36 GPU-h | ~7–9 h |
| Qwen3-32B | ~2–4 min (8k tokens, CSIS A100) | ~120–235 GPU-h | ~25–50 h |

The H100 QOS allows 2 running jobs per user on the shared account.
