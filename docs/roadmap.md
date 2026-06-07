# Roadmap

## Milestones

### M1 — Working simulator + harness (DONE)
- Ironclad card set, enemies, combat engine, map generation
- 4-dimension benchmark: turn, combat, synergy, run
- Mock provider for offline testing
- 40 unit tests, all passing

### M2 — Pilot runs (DONE)
- llama-3.1-8b-instant: structured + raw, seed=42
- meta-llama/llama-4-scout-17b-16e-instruct: structured + raw, seed=42
- Key bugs fixed: map dead-end, EventBus stacking, rate-limit crash

### M3 — Paper-grade evaluation (IN PROGRESS)
- n≥20 samples per dimension per model
- Models: llama-3.1-8b, llama-4-scout-17b (qwen3-32b dropped — free tiers can't run a
  reasoning model; a 32B+ reasoning model needs a paid tier — future work)
- Both formats (structured, raw) for each model
- Statistical summary: mean ± std per metric

### M4 — Write-up
- findings.md → draft.md → final paper/report
- Figures: radar charts, bar charts per dimension
- Ablation: structured vs raw per model

## Paper-grade run matrix

Concrete target for M3. Everything below is **compute/credit-bound, not code-bound** — the
harness is ready. The single hard blocker is the free-tier Groq 6000 TPM cap; a **paid Groq
Dev tier** unblocks all of it. Check items off as runs land.

### Models (capability ladder)
| # | Model | Provider | Status | Notes |
|---|---|---|---|---|
| 1 | llama-3.1-8b-instant | Groq | non-run dims valid (pilot n) | small baseline |
| 2 | meta-llama/llama-4-scout-17b | Groq | non-run dims valid (pilot n) | mid baseline |
| 3 | **a 3rd family** (e.g. GPT-4o-mini / Claude Haiku / Gemini Flash) | TBD | **not started** | needed for cross-family signal |
| 4 | **a reasoning model** (qwen3-32b or similar) | paid OpenRouter/Groq | **dropped on free tier** | optional but strengthens scale story |

Minimum for a credible paper: **3 models across ≥2 families**. Models 1–2 alone are same-family.

### Sample sizes (per model, per format)
| Dimension | Pilot n | Paper-grade target | Why |
|---|---|---|---|
| Turn-level | 5 | **≥20** | 5 → 20pp steps; need ≥20 for mean±std |
| Combat-level | 3 | **≥20** | 3 → 33pp steps; high-variance win/HP |
| Synergy | 8 (fixed fixtures) | **n=16–20 fixtures** OR k≥5 sampled completions/fixture at temp>0 | current 8 is deterministic (no variance/std) — need more fixtures or repeated sampling for error bars |
| Run-level | 3 (INVALID, pre-fix) | **≥20** | highest variance; currently NO valid data — re-run first |

### Seeds
- Pilot used **seed=42 only** (one fixed map/enemy/draw layout).
- Paper-grade: sweep **≥5 seeds** (e.g. 42, 142, 242, 342, 442) so results aren't an artifact
  of one RNG layout. Run-level especially must vary the seed per sample.

### Formats
- Both **structured** and **raw** for every model, on **identical seeds** (controlled ablation).

### Reporting
- Every metric reported as **mean ± std (or 95% CI)** across the n samples — no point estimates.
- Per-dimension bar/radar charts + structured-vs-raw ablation per model.

### Run order (when paid tier is available)
1. **Run-level first** — it has no valid data and is the longest pole. `--only run --n-run 20`
   × (2 models × 2 formats), seed-swept.
2. Scale turn/combat to n≥20 (`--only turn combat`).
3. Expand synergy (more fixtures or k-sampling).
4. Add model #3 (new family); optionally model #4 (reasoning, paid).
5. Fold all numbers (mean±std) into findings.md → report.md → draft.md.

## Timeline
- Pilot complete: 2026-06-07
- Paper-grade runs: TBD (gated on paid Groq Dev tier)
- Draft: TBD
