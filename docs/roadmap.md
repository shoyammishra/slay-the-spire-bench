# Roadmap

## Milestones

### M1 — Working simulator + harness (DONE)
- Ironclad card set, enemies, combat engine, map generation
- 4-dimension benchmark: turn, combat, synergy, run
- Mock provider for offline testing

### M2 — Pilot runs (DONE 2026-06-07)
- llama-3.1-8b-instant: structured + raw, seed=42
- meta-llama/llama-4-scout-17b-16e-instruct: structured + raw, seed=42
- Key bugs fixed: map dead-end, EventBus stacking, rate-limit crash

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

### M3 — Paper-grade evaluation (IN PROGRESS — blocked on paid Groq)
- n≥20 samples per dimension per model, ≥5 seeds, both formats, mean±std
- Models: llama-3.1-8b, llama-4-scout-17b + a 3rd family (qwen3-32b dropped —
  a reasoning model needs a paid tier; revisit as model #4)

### M4 — Write-up
- findings.md → draft.md → final paper/report
- Figures: radar charts, bar charts per dimension
- Ablations: structured vs raw; Ironclad vs Silent; greedy vs LLM routing

## What can be done NOW (free tier, before paid Groq)

1. **Merge `synergy-rework` → main.** Code is complete, tested, and mock-verified;
   nothing pending blocks the merge. Waiting on results to merge code only adds drift risk.
2. **(Optional) refresh synergy at n=20 on the free tier.** Synergy is 1 light call per
   sample — free Groq sustains it (~10–20 min per model×format). Worth doing because the
   n=8 numbers predate the pick-coercion fix (a model answering `"1"` as a string is now
   scored correct) and n=20 halves the step size to 5pp. Run:
   `--only synergy --n-synergy 20` ×4 combos, then `--character silent` ×4.
   Turn-level (1 call/sample) is also free-tier-feasible if needed for a demo.

## Paper-grade run matrix (M3)

Everything below is **compute/credit-bound, not code-bound**. The single hard blocker is
the free-tier Groq 6000 TPM cap for combat/run dimensions; a **paid Groq Dev tier**
unblocks all of it. Check items off as runs land.

### Models (capability ladder)
| # | Model | Provider | Status | Notes |
|---|---|---|---|---|
| 1 | llama-3.1-8b-instant | Groq | synergy valid (n=8); turn/combat stale (pre-sweep); run none | small baseline |
| 2 | meta-llama/llama-4-scout-17b | Groq | synergy valid (n=8); turn/combat stale (pre-sweep); run none | mid baseline |
| 3 | **a 3rd family** (e.g. GPT-4o-mini / Claude Haiku / Gemini Flash) | TBD | **not started** | needed for cross-family signal |
| 4 | **a reasoning model** (qwen3-32b or similar) | paid OpenRouter/Groq | **dropped on free tier** | optional but strengthens scale story |

Minimum for a credible paper: **3 models across ≥2 families**. Models 1–2 alone are same-family.

### Sample sizes (per model, per format)
| Dimension | Current data | Paper-grade target | Why |
|---|---|---|---|
| Turn-level | stale (pre-sweep, n=5) | **≥20** | 5 → 20pp steps; need ≥20 for mean±std |
| Combat-level | stale (pre-sweep, n=3) | **≥20** | 3 → 33pp steps; high-variance win/HP |
| Synergy | valid n=8 (Ironclad) | **n=20/character** (fixtures ready: 20 IC + 20 Silent) AND/OR k≥5 completions/fixture at `--temperature 0.7` | deterministic fixtures need temp>0 sampling or seed sweeps for error bars |
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

### Run order (when paid tier is available)

Ordered **cheapest → most expensive**: since ALL dimensions need fresh data post-sweep
(no old baseline to extend), the rational order validates the pipeline on cheap calls
before committing the bulk of the credits to run-level, where a mid-run failure wastes
the most money.

1. **Paid smoke test** — one tiny full pass (`--n-turn 2 --n-combat 1 --n-synergy 2
   --n-run 1`) on llama-3.1-8b to confirm key, throughput, and post-sweep outputs
   end-to-end. Minutes, pennies.
2. **Turn + combat, n≥20 × 5 seeds** (`--only turn combat --seeds ...`) × 2 models ×
   2 formats. Cheap (1 call/turn-sample; ~5–15 calls/combat), re-baselines the
   dimensions invalidated by the engine fix, and produces the first publishable
   mean±std tables.
3. **Synergy, n=20 × 2 characters** (+ `--temperature 0.7` k-sampling for error bars).
   Light calls; doubles as the Silent generalization result.
4. **Run-level, n≥20 × 5 seeds** — the longest pole and biggest spend, run once the
   pipeline is proven above. Start single-act; this is the headline "no valid data yet"
   gap. (`--only run --n-run 20 --seeds ...`)
5. **Model #3 (new family)** — repeat steps 2–4; optionally model #4 (reasoning, paid).
6. **Optional breadth ablations:** `--acts 3` multi-act run-level; `--llm-routing`
   (decision-scope ablation); Silent run-level.
7. **Fold numbers** (mean±std) into findings.md → report.md/report.html → draft.md.

## Timeline
- Pilot complete: 2026-06-07
- Harness paper-ready (Silent, multi-act, temp/seeds CLI): 2026-06-10
- Bug sweep / hardening (21 fixes, 47 tests): 2026-06-10
- Paper-grade runs: TBD (gated on paid Groq Dev tier)
- Draft: TBD
