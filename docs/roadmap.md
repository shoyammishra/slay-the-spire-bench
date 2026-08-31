# Roadmap

> **Submission supersession (2026-08-31):** the active plan is a four-page,
> non-archival PTA at NeurIPS 2026 workshop paper due 2026-09-05 AoE and an ICML 2027
> main-track paper built around controlled-H evidence. See `docs/submission_plan.md`
> for the authoritative deadlines, paper separation, and stop/go gates. Historical
> roadmap items that assume a cross-task horizon curve no longer define the paper.

> **Active supersession (2026-08-30):** M3a's open-model matrix is complete for seven
> configurations through Qwen3-235B-A22B-FP8, with both characters/formats and all four
> dimensions. The current backlog is in `docs/handoff.md`: M3b frontier validation,
> paper assembly, and an optional removal-v2 redesign. Removal-v1 is quarantined because
> every fixture targeted `Strike`; any older removal task/result below is historical and
> must not be cited or folded into composites.

## Milestones

### M1 — Working simulator + harness (DONE)
- Ironclad card set, enemies, combat engine, map generation
- 4-dimension benchmark: turn, combat, synergy, run
- Mock provider for offline testing

### M2 — Pilot runs (DONE 2026-06-07) — ⛔ ALL NUMBERS NOW STALE
- llama-3.1-8b-instant: structured + raw, seed=42
- meta-llama/llama-4-scout-17b-16e-instruct: structured + raw, seed=42
- Key bugs fixed: map dead-end, EventBus stacking, rate-limit crash
- ⛔ **These pilot numbers (incl. the n=20 synergy) are INVALID for comparison:**
  the harness changed substantially after them (2026-06-10..12 engine fix batches +
  synergy fixture/instrument de-bias). They are NOT comparable to the post-audit
  Qwen2.5-7B matrix and must be re-run locally before use. Kept as history only.

### M2.5 — A* acceptance harness extensions (DONE 2026-06-10, code-side)
- Silent character: full card set (~73), powers, pool, 20 hand-crafted synergy fixtures
  (Ironclad fixtures also expanded 8 → 20 → 40 total across both characters)
- Multi-act runs (`--acts 3`): acts 1→3 with full-heal transitions + boss relic picks
- `--temperature` (sampling variance / error bars), `--seeds` (multi-seed mean±std),
  `--llm-routing` (LLM picks paths/rest/boss relics in run-level)
- Relic lifecycle split (on_pickup/register) — fixes relic stacking across a run

### M2.6 — Bug sweep + harness hardening (DONE 2026-06-10)
- 21 bugs fixed (engine fidelity, relic stacking, harness crashes, CLI aggregation —
  full list in CLAUDE.md "Bugs Fixed"). 47 tests pass; mock-verified end-to-end
  (Silent, 3-act, multi-seed, llm-routing).
- **Data consequence:** the debuff-timing fix changes combat dynamics → pre-sweep
  **turn/combat pilot numbers are stale** (kept as history only). **Synergy pilot
  numbers remain valid** (static deck snapshot, no combat). Run-level never had
  valid data. ⇒ Every dimension needs fresh runs anyway, which simplifies M3:
  there is no old data worth preserving compatibility with.
- The multi-seed aggregator bug (null means) was caught BEFORE any paid run.

### M2.7 — Engine-fidelity fix batch (DONE 2026-06-11)
- All of `docs/bug_audit_2026-06-10.md` Part 2 implemented (~45 fixes: engine flag
  consumers, relic energy-wipe/counter-lifecycle/stubs, elite relic drops, pool +
  character gating, MERCHANT greedy shop, rest policies, Maw Bank, prompts, charts).
- **Part 3:** the pass over previously-unread files found 8 more bugs, two critical:
  played cards VANISHED when an identical copy was in hand (dataclass `__eq__`),
  and self-exhausting cards double-exhausted (double CARD_EXHAUST). Full list in
  the audit doc + CLAUDE.md "Bugs Fixed".
- 77/77 tests (was 56; +21 regression tests); mock pipeline green both characters.
- **Data consequence:** combat dynamics changed AGAIN (decks no longer shrink
  mid-combat; exhaust hooks fire once) — turn/combat numbers were already stale,
  still are. **Synergy n=20 stays the only valid data**, but the 4 Aggro fixture
  decks changed (Perfected-Strike removal) → the next synergy run regenerates;
  aggregates comparable, per-row values not.

### M2.8 — Third full audit + same-day fix batch (DONE 2026-06-11)
- Fresh full-source re-read found **40 NEW bugs** (none regressions); all fixed same
  day. Full spec + per-item fix notes: `docs/bug_audit_2026-06-11.md`.
- Instrument: turn-eval **duplicate-index loophole** closed (identity-strict
  play_card/simulator/oracle; repeated indices illegal); **Neow's Lament removed from
  the mid-run event pool** (its auto-picked 1-HP boon inflated run-level); events no
  longer repeat in a run.
- Engine (3 combat-dynamics changes): **HP-loss effects now bypass block**;
  **Havoc no longer duplicates the top draw card**; **enemy block now persists
  through the player's turn** (it was wiped at player-turn start — every enemy
  blocking move was a no-op; enemies are tougher now). Plus ~15 card fixes
  (Searing Blow ½-damage, Reaper overheal, Choke/Finisher/BfB/Corruption/
  Perfected Strike...), relic fixes (Snecko Skull poisoned the PLAYER, Blue Candle
  no-op, Pandora's Box substring match, Fairy-in-a-Bottle never registered), enemy
  fidelity (Lagavulin Metallicize, Time Eater Time Warp implemented, Acid Slime
  Slimed, Slime Boss split HP).
- **102/102 tests** (was 77; +25 regression tests); mock pipeline green both
  characters + formats.
- **Data consequence:** turn/combat stale for a FOURTH reason (B1+B2+B12) —
  re-baseline before any paid turn/combat collection. **Synergy n=20 stays valid**
  (no synergy-path change). Run-level still has no valid data (and is now free of
  the Neow inflation source).

### M3 — Paper-grade evaluation (IN PROGRESS — professor's two-phase compute plan, 2026-06-12)

The compute blocker is resolved by the professor's plan (announced 2026-06-12,
GPU access expected 2026-06-13):

- **M3a — GPU phase (open-source models, self-hosted).** Professor provides a GPU;
  run all open-source experiments there. No TPM caps, no per-token cost → the
  full n≥20 × 5-seed matrix (including run-level, the long pole) becomes feasible.
  Also **revives the reasoning-model slot**: qwen3-32b (or a DeepSeek-R1 distill)
  was dropped only because free tiers truncated/throttled it — self-hosting fixes
  exactly that failure mode.
- **M3b — Frontier API phase (Claude / GPT).** Once the M3a results are in, the
  professor shares a way to run the same experiments on Claude/GPT models. This
  fills the "3rd family / frontier model" gap the novelty review flagged as
  required for NeurIPS D&B credibility. Same seeds, same formats, same n — the
  M3a tables define the exact protocol M3b repeats.
- Targets unchanged: n≥20 samples per dimension per model, ≥5 seeds, both
  formats, mean±std.

### M4 — Write-up
- findings.md → draft.md → final paper/report
- Figures: radar charts, bar charts per dimension
- Ablations: structured vs raw; Ironclad vs Silent; greedy vs LLM routing

## Prep for the GPU phase (do BEFORE access arrives, ~tomorrow 2026-06-13)

0. ~~**Checkpoint/commit the 2026-06-12 fix batch**~~ DONE (4th audit committed as
   `0de519a`; experiments must run on a committed state so results are reproducible
   against a SHA).
0b. ~~**5th audit ("one last pass")**~~ DONE 2026-06-12 — line-by-line review of the
   two newest commits + fresh full engine/harness read found **2 HIGH + 5 MEDIUM +
   10 LOW**; all fixed same day by an Opus 4.8 subagent (spec + per-item notes in
   `docs/bug_audit_2026-06-12b.md`). The two GPU-phase-critical ones: (H1) a single
   non-429 server error (e.g. vLLM HTTP 400 on a context-overflow prompt) crashed the
   whole benchmark and discarded every completed run — partial-save now catches ALL
   exceptions at the run-seed and dimension level; (H2) the `complete_json` brace-scan
   fallback was ~O(n²) per parse failure (minutes of CPU on a truncated 32k `<think>`
   dump — exactly the revived-reasoning-model failure mode) — now one `raw_decode` per
   `{`. Also: Doubt/Shame curses were no-ops (debuff ticked away same round), Blue
   Candle+Pride double-exhaust, Dead Branch added curses/statuses, Tiny House granted
   +1 energy/turn it shouldn't, Nemesis intangible off-by-one, eggs were dead relics.
   **133/133 tests, mock pipeline green ×4.** No synergy prompt bytes changed →
   synergy n=20 stays valid.
1. ~~**Add a `--provider local` adapter**~~ DONE 2026-06-12. `LocalLLM` in
   `slay_bench/benchmark.py` — OpenAI-compatible chat-completions client (urllib, no
   new deps), wired into `run_benchmark.py` via `--provider local --base-url URL`
   (falls back to `$LOCAL_BASE_URL` then `http://localhost:8000/v1`). Clone of
   `OpenRouterLLM` with the endpoint parametrized; dropped the 402 wall (a local
   server never bills → any non-429 HTTP error is surfaced with the response body so a
   misconfigured endpoint is obvious), 300s timeout (slow 32B serving), 8000 max_tokens
   (reasoning `<think>` blocks). Optional `$LOCAL_API_KEY` for vLLM `--api-key` servers;
   defaults to a harmless "EMPTY" Bearer. 3 regression tests (stubbed urlopen): request
   shape/URL, server-error surfacing, build_llm wiring. Works with vLLM
   (`:8000/v1`), Ollama (`:11434/v1`), TGI — all OpenAI-shaped. **118/118 tests, mock
   pipeline green.** Smoke command:
   `python run_benchmark.py --provider local --base-url http://localhost:8000/v1 --model <m> --n-turn 2 --n-combat 1 --n-synergy 2 --n-run 1`
2. **Decide the open-source model ladder by VRAM** (confirm GPU size first):
   - llama-3.1-8b-instruct — re-run locally even though Groq numbers exist: same
     weights / different serving stack = a free **provider-robustness check**.
   - llama-4-scout-17b (if it fits) — continuity with the pilot.
   - **qwen3-32b or DeepSeek-R1-distill (reasoning)** — the revived model #4;
     needs high max_tokens for `<think>` blocks (already handled in complete_json).
   - One more family if VRAM allows (gemma / mistral) for cross-family breadth.
3. **Throughput sanity math before committing to run-level:** run-level is sequential
   and stateful (dozens–hundreds of calls/run, no batching possible). On a single GPU
   at ~50–100 tok/s for a 32B model, one run can take 30–60+ min. Measure with the
   smoke test, THEN size n for run-level per model.

## What can be done NOW (free tier, before the GPU)

1. ~~**Merge `synergy-rework` → main.**~~ DONE 2026-06-10 (merge commit `6398bb1`,
   47/47 tests verified on main). Work continues on main.
2. ~~**Refresh synergy at n=20 on the free tier.**~~ DONE 2026-06-10 — **all 8 combos** have
   clean n=20 (Ironclad + Silent, both models, both formats), re-run on the **de-biased
   instrument** (commit `5db7063`). Headline result airtight: Exhaust 5% / Discard 5% pooled
   vs 85–95% for surface-readable archetypes; card-pick survived de-biasing (0.65–0.75 ≠
   chance). Full numbers in docs/experiment_log.md.
3. **Paper-grade synergy = error bars (the remaining gap, free-tier-feasible).** The n=20
   numbers are point estimates at seed=42 (one deterministic fixture pass — no variance to
   std over). Close it ONE of two ways, both supported by the harness:
   - **k-sampling at temp>0:** `--only synergy --n-synergy 20 --temperature 0.7` ×8 combos,
     repeated k≥5 times → mean±std per metric (sampling variance on a fixed exam).
   - **seed sweep:** `--only synergy --n-synergy 20 --seeds 42 142 242 342 442` ×8 combos →
     per-seed JSON + auto-aggregated mean±std (the `_aggregate_summaries` path, key-bug-fixed).
     - ⚠️ **H6 (don't over-interpret the std):** synergy fixture selection is keyed on
       `seed % 20`, and the recommended seeds `42 142 242 342 442` are all ≡ 2 (mod 20).
       So every seed in that sweep sees the *identical* fixture sequence; the multi-seed std
       then measures only offer-rotation pairing (+ sampling variance at temp>0), NOT
       different fixtures. This is the intended post-2nd-audit design (seed-keyed prompts);
       just report the std as "instrument/rotation variance," not "fixture-set variance."
       For fixture-set variance, choose base seeds that differ mod 20 (e.g. `42 43 44 45 46`).
     - To avoid the overwrite-by-seed filename collision when k-sampling the same command,
       pass `--run-tag <s>` (e.g. `--run-tag rep1`) so each repeat writes a distinct stem.
   Either yields the mean±std synergy tables the paper needs. **This is the planned next-session
   task** (along with re-confirming all 8 clean n=20 — NOTE: the re-confirm regenerates the
   numbers anyway, since the 4 Aggro fixture decks changed in the 2026-06-11 batch and the
   seed↔fixture mapping changed in the 2nd audit). Turn-level (1 call/sample) is also
   free-tier-feasible if a demo is wanted; turn/combat/run paper-grade still need paid Groq.

## Paper-grade run matrix (M3)

Everything below is **compute-bound, not code-bound**. The old blocker (free-tier Groq
6000 TPM) is superseded by the professor's plan: **GPU (M3a) for open-source models,
then frontier API access (M3b) for Claude/GPT**. Check items off as runs land.

### Models (capability ladder)
| # | Model | Provider | Phase | Status | Notes |
|---|---|---|---|---|---|
| 1 | llama-3.1-8b(-instruct) | **local GPU** | M3a | ⛔ old Groq numbers DELETED (2026-06-14) — predated the 2026-06-10..12 engine/instrument fix batches; not comparable to the post-audit matrix. **Re-running self-hosted** via `cluster/{turn_combat,synergy,run_level}_models.sbatch` (`HF_REPO=meta-llama/Llama-3.1-8B-Instruct SERVED_NAME=llama-3.1-8b`). | small baseline; restores a 2nd open-source FAMILY (Llama vs Qwen). vLLM 0.6.6 (`slaybench`); gated → `HF_TOKEN` |
| 2 | mistralai/Mistral-7B-Instruct-v0.3 | **local GPU** | M3a | not started — replaces scout-17b as the mid model. Run via the same `*_models.sbatch` (`CONDA_ENV=slaybench HF_REPO=mistralai/Mistral-7B-Instruct-v0.3 SERVED_NAME=mistral-7b`). | mid baseline + a 3rd open-source FAMILY (Mistral AI). Mistral → vLLM 0.6.6 (`slaybench`, same env as the 8B); 32k native context; NOT gated (no `HF_TOKEN`). Replaced Gemma after both Gemma options failed — see CLAUDE.md mid-slot history. |
| 3 | **reasoning model** (qwen3-32b / DeepSeek-R1-distill) | **local GPU** | M3a | dropped on free tier — **REVIVED by GPU** | the truncation/throttling failure mode disappears when self-hosted |
| 4 | **Claude (e.g. Haiku/Sonnet)** | professor's API path | M3b | not started | frontier family #1 |
| 5 | **GPT (e.g. 4o-mini/4o)** | professor's API path | M3b | not started | frontier family #2 |

Minimum for a credible paper: **3 models across ≥2 families** — the two-phase plan
delivers up to 4 families (Llama, Qwen/DeepSeek, Anthropic, OpenAI) incl. a reasoning
model, which is exactly the matrix `docs/novelty_and_related_work.md` says NeurIPS
D&B reviewers will expect.

### Sample sizes (per model, per format)
| Dimension | Current data | Paper-grade target | Why |
|---|---|---|---|
| Turn-level | stale (pre-sweep, n=5) | **≥20** | 5 → 20pp steps; need ≥20 for mean±std |
| Combat-level | stale (pre-sweep, n=3) | **≥20** | 3 → 33pp steps; high-variance win/HP |
| Synergy | valid n=20 ×2 characters (seed-42 point est.; ⚠️ 4 Aggro decks changed 2026-06-11 → next run regenerates) | **n=20/character** AND/OR k≥5 completions/fixture at `--temperature 0.7` | deterministic fixtures need temp>0 sampling or seed sweeps for error bars |
| Run-level | none | **≥20** | highest variance; most expensive (dozens–hundreds of calls/run) |

### Seeds
- Pilot used **seed=42 only** (one fixed map/enemy/draw layout).
- Paper-grade: sweep **≥5 seeds** via `--seeds 42 142 242 342 442` (per-seed JSON+charts
  plus aggregated mean±std land automatically). Run-level especially must vary seeds.

### Formats
- Both **structured** and **raw** for every model, on **identical seeds** (controlled ablation).

### Reporting
- Every metric reported as **mean ± std (or 95% CI)** across the n samples — no point estimates.
- Per-dimension bar/radar charts + structured-vs-raw ablation per model.

### Run order (M3a, when the GPU is available — same logic applies to M3b later)

> **GPU landed 2026-06-12 (BITS CSIS Slurm cluster).** The steps below are now
> codified as ready-to-submit Slurm jobs in **`cluster/`** (see `cluster/README.md`):
> `smoke.sbatch` (step 1) → `turn_combat.sbatch` (step 2) → `synergy.sbatch` (step 3)
> → `run_level.sbatch` (step 4). Each job serves a model with vLLM on one A100 80 GB
> then runs `run_benchmark.py --provider local`. Switch model/GPU-count via the
> `HF_REPO`/`SERVED_NAME`/`TP_SIZE` env vars documented in `cluster/lib.sh`.

Ordered **cheapest → most expensive**: since ALL dimensions need fresh data post-sweep
(no old baseline to extend), the rational order validates the pipeline on cheap calls
before committing the bulk of GPU-hours to run-level, where a mid-run failure wastes
the most time. (On the GPU the cost is wall-clock hours, not credits — the ordering
logic is identical. For M3b it is credits again, so the order matters even more.)

1. **Smoke test** — serve one model (vLLM/Ollama), then one tiny full pass
   (`--n-turn 2 --n-combat 1 --n-synergy 2 --n-run 1`) via `--provider local` to
   confirm endpoint, throughput, and post-fix-batch outputs end-to-end. Record
   tok/s — it sizes the run-level budget (step 4).
2. **Turn + combat, n≥20 × 5 seeds** (`--only turn combat --seeds ...`) × 2 models ×
   2 formats. Cheap (1 call/turn-sample; ~5–15 calls/combat), re-baselines the
   dimensions invalidated by the engine fix, and produces the first publishable
   mean±std tables.
3. **Synergy, n=20 × 2 characters** (+ `--temperature 0.7` k-sampling for error bars).
   Light calls; doubles as the Silent generalization result.
4. **Run-level, n≥20 × 5 seeds** — the longest pole and biggest spend, run once the
   pipeline is proven above. Start single-act; this is the headline "no valid data yet"
   gap. (`--only run --n-run 20 --seeds ...`)
5. **Reasoning model (qwen3-32b / R1-distill)** — repeat steps 2–4 on the GPU. Watch
   max_tokens (think blocks) and tok/s; this model dominates wall-clock, so run it
   after the protocol is proven on the small models.
6. **Optional breadth ablations:** `--llm-routing` (decision-scope ablation); Silent
   run-level. ⚠️ `--acts 3` multi-act run-level RE-TAGGED 2026-07-12 (decision_log P3
   entry): now a **conditional appendix probe** — run only if M3b frontier models ALSO
   floor at 1 act, and only after an Act-2/3 engine audit + smoke (multi-act paths never
   exercised at paper scale). Run-level is reframed as the shared collapse floor for the
   current paper; do not spend GPU-hours on `--acts 3` before the M3b gate fires.
7. **Fold M3a numbers** (mean±std) into findings.md → report.md/report.html → draft.md.
   **These tables define the locked protocol for M3b.**
8. **M3b — Claude/GPT via the professor's access:** repeat steps 2–4 verbatim (same
   seeds, same n, same formats, same fixture set — zero protocol drift), starting with
   the cheapest tier models. Run-level last, sized by observed cost per run.

## Timeline
- Pilot complete: 2026-06-07
- Harness paper-ready (Silent, multi-act, temp/seeds CLI): 2026-06-10
- Bug sweep / hardening (21 fixes, 47 tests): 2026-06-10
- 2nd instrument audit (5 fixes, 56 tests) + synergy n=20 de-biased: 2026-06-10
- Engine-fidelity batch (audit Part 2 + Part 3, 77 tests): 2026-06-11
- 3rd full audit + fix batch (40 bugs, 102 tests): 2026-06-11
- 4th full audit + fix batch (Sentinel crash + 22 more, 115 tests): 2026-06-12
- Professor's compute plan announced (GPU → frontier API): 2026-06-12
- **M3a GPU runs (open-source): expected start 2026-06-13**
- M3b frontier runs (Claude/GPT): after M3a results
- Draft: after M3b
