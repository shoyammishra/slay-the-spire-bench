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

### M3 — Paper-grade evaluation (IN PROGRESS — blocked on paid Groq)
- n≥20 samples per dimension per model, ≥5 seeds, both formats, mean±std
- Models: llama-3.1-8b, llama-4-scout-17b + a 3rd family (qwen3-32b dropped —
  a reasoning model needs a paid tier; revisit as model #4)

### M4 — Write-up
- findings.md → draft.md → final paper/report
- Figures: radar charts, bar charts per dimension
- Ablations: structured vs raw; Ironclad vs Silent; greedy vs LLM routing

## What can be done NOW (free tier, before paid Groq)

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
   Either yields the mean±std synergy tables the paper needs. **This is the planned next-session
   task** (along with re-confirming all 8 clean n=20 — NOTE: the re-confirm regenerates the
   numbers anyway, since the 4 Aggro fixture decks changed in the 2026-06-11 batch and the
   seed↔fixture mapping changed in the 2nd audit). Turn-level (1 call/sample) is also
   free-tier-feasible if a demo is wanted; turn/combat/run paper-grade still need paid Groq.

## Paper-grade run matrix (M3)

Everything below is **compute/credit-bound, not code-bound**. The single hard blocker is
the free-tier Groq 6000 TPM cap for combat/run dimensions; a **paid Groq Dev tier**
unblocks all of it. Check items off as runs land.

### Models (capability ladder)
| # | Model | Provider | Status | Notes |
|---|---|---|---|---|
| 1 | llama-3.1-8b-instant | Groq | synergy valid (n=20, seed-42 point est.); turn/combat stale; run none | small baseline |
| 2 | meta-llama/llama-4-scout-17b | Groq | synergy valid (n=20, seed-42 point est.); turn/combat stale; run none | mid baseline |
| 3 | **a 3rd family** (e.g. GPT-4o-mini / Claude Haiku / Gemini Flash) | TBD | **not started** | needed for cross-family signal |
| 4 | **a reasoning model** (qwen3-32b or similar) | paid OpenRouter/Groq | **dropped on free tier** | optional but strengthens scale story |

Minimum for a credible paper: **3 models across ≥2 families**. Models 1–2 alone are same-family.

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
- 2nd instrument audit (5 fixes, 56 tests) + synergy n=20 de-biased: 2026-06-10
- Engine-fidelity batch (audit Part 2 + Part 3, 77 tests): 2026-06-11
- Paper-grade runs: TBD (gated on paid Groq Dev tier)
- Draft: TBD
