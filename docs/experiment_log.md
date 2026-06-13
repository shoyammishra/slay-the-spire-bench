# Experiment Log

## 2026-06-13 (CLUSTER) — PAPER-GRADE 4-DIMENSION RESULTS, Qwen2.5-7B, 5 seeds (CURRENT valid data)

**First complete paper-grade matrix.** Qwen2.5-7B-Instruct, self-hosted (vLLM 0.6.6, A100
80 GB, csis.cn2), `--seeds 42 1042 2042 3042 4042` (spaced 1000 apart → disjoint per-sample
windows, real std), both prompt formats. Turn/combat/run = Ironclad n=20 (run n=20); synergy
= n=20 for BOTH Ironclad and Silent. All four `results/qwen2.5-7b*_seeds42_1042_2042_3042_4042.json`
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

### Silent — synergy only (n=20, 5 seeds, mean ± std)

| Metric | structured | raw |
|---|---|---|
| archetype_acc | 0.60 ± 0.0 | 0.42 ± 0.027 |
| card_pick_acc | 0.53 ± 0.084 | 0.45 ± 0.05 |
| removal_acc | 0.36 ± 0.022 | 0.18 ± 0.045 |

(Silent turn/combat/run not run this pass — the sbatch jobs scope those to Ironclad.)

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
- **raw archetype_acc has std = 0.0** for Ironclad (always 5/20) and near-0 for Silent — the
  model gives essentially seed-invariant (and wrong) archetype labels in raw format. Likely a
  real finding (raw collapses archetype reasoning to a fixed guess), not an instrument bug;
  worth a per-sample look before the paper.

**Greedy baseline anchor (for the paper):** scripted greedy bot survives Act 1 ~1/100,
avg ~12.5 floors. Use this to frame run-level/combat as "on par with greedy," never "beats."

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
