# Findings

## ⚠️ The pilot "LLM beats the greedy bot on HP" result was an instrument artifact (2026-06-10, 2nd audit)

The stale combat-level hp_ratio values >1.0 (103.5–113.8% across both models/formats) were
NOT model skill: `CombatEvaluator` read the LLM's HP *after* `end_combat()` fired Burning
Blood's +6 COMBAT_END heal, while the greedy baseline never emits COMBAT_END. Verified: an
LLM playing *identically* to the bot scored hp_ratio = 1.095. Fixed (HP now captured
pre-heal); never cite the >100% numbers. The bias was also Ironclad-only (Silent's starter
relic fires at COMBAT_START), so it would have confounded cross-character combat comparisons.

Two sibling instrument findings from the same audit (both fixed, both with regression tests):
(1) the turn-level oracle capped its search at the first 6 playable cards — wrong for
Silent's 7-card opening hand (understated the optimum on 6/10 seeds, up to 2×); (2)
multi-seed synergy runs sent byte-identical prompts for every seed (fixture+rotation came
from the loop index), so `--seeds` error bars would have reported std≈0 by construction.
Full audit + the still-pending engine-fidelity fix batch: `docs/bug_audit_2026-06-10.md`.

Reassuring negatives from the same audit: the de-biased synergy n=20 results SURVIVE (all 40
fixtures classify confidently as labeled; no string-matching near-misses in removal scoring —
wrong answers are genuinely wrong cards, mostly "Defend"); Ironclad turn-level oracle values
are unaffected by the cap bug (5-card opening hand → byte-identical before/after the rewrite).

## ⭐ Mechanic-defined archetypes are a cross-character blind spot (n=20 de-biased, 2026-06-10)

The strongest synergy signal, confirmed across BOTH characters at n=20 on a **de-biased
instrument** (see synergy-instrument fix below): models fail to identify the one archetype
defined by a *payoff mechanic* rather than a surface card-name pattern. Pooled per-archetype
archetype-ID accuracy over all 8 model×format×character combos:

| Archetype | Acc | | Archetype | Acc |
|---|---|---|---|---|
| Aggro (IC)  | 95% | | Strength (IC) | 40% |
| Poison (Si) | 95% | | **Exhaust (IC)** | **5%** |
| Shiv (Si)   | 90% | | **Discard (Si)** | **5%** |
| Block (both)| 85% | | | |

- **Ironclad Exhaust → 1/20 (5%)** (labeled "Aggro", sometimes "Strength") even with
  Corruption / Feel No Pain / Dark Embrace / Fiend Fire signatures present.
- **Silent Discard → 1/20 (5%)** (always "Block" or "Shiv"). Same shape, one character over.
- Surface-readable archetypes (Aggro/Poison/Shiv/Block) all 85–95%. Strength (40%) is the
  intermediate case — frequently "Aggro" because Strength decks are Strike-heavy.

**Why it matters for the paper:** a clean, mechanistic, reproducible failure mode that the
multi-horizon decomposition isolates — the model picks good cards locally (dissociation below)
but cannot name the *strategy* when the strategy is a payoff loop rather than a keyword. Two
characters give it cross-domain support within one engine, and the two blind-spot archetypes
are the structurally analogous ones (exhaust-payoff ↔ discard-payoff).

**Name-vs-play dissociation is REAL, not an artifact.** Card-pick held at 0.65–0.75 after the
instrument was de-biased (a model that always answered offer-index-0 would now score ~0.33).
So models judge local card quality well even on decks they cannot label. (Lone weak spot:
Silent llama structured 0.35 — genuine, not the old positional bias.)

**Secondary (n=20):** Silent archetype-ID ≥ Ironclad (0.60–0.80 vs 0.40–0.70), plausibly
because Silent labels read literally off the cards. scout-17b Silent structured removal 0.60
is the standout; removal near-floor (0.05–0.25) everywhere else. Full table: docs/experiment_log.md.

## ⛔ Existing run-level numbers are INVALID — do not report (2026-06-07)

The run-level results currently sitting in the `results/*.json` files (llama-3.1-8b
20%/40% survival, 13.4 floors; scout-17b floors=5) are from **old, pre-fix code** and must
be **ignored entirely** — treat run-level as having NO valid data yet. They predate the
map dead-end fix, the EventBus listener-stacking fix, and the `_safe_int`/null-index fix, any
of which can change run outcomes. A clean run-level pass on the current code is **pending**
and is **blocked on free-tier TPM** (next section). Until that pass lands on a paid tier, the
paper has no run-level numbers. The 13.4-floors / 20–40% figures still appearing in
report.md tables are stale and should not be quoted.

## ⚠️ Run-level scaling blocked on free-tier Groq TPM (2026-06-07)

Attempting `--only run --n-run 3` on llama-3.1-8b (both formats) hit the free-tier Groq
**6000 TPM** cap and could not complete. Run-level is the most token-heavy dimension: each
combat turn ships the full game state (~3000+ tokens/call) and a run makes dozens-to-hundreds
of stateful calls. The 429 error showed `Used 2725, Requested 3367` — a single prompt nearly
exhausts the per-minute budget, so throttling hit nearly every call. Structured completed
**0 runs** (partial-save kept the prior valid run-level results); raw hung in an infinite
retry loop and was manually stopped.

**Takeaway:** free Groq sustains only ~2 calls/min, so even n=1 run-level is impractical
(~30+ min and constant throttling). Synergy/turn/combat survive because they are short
single-shot calls. **Unblocking run-level — and paper-grade n≥20 anywhere — requires a paid
Groq Dev tier** (uncapped/higher TPM; the 429 message itself recommends it). No code fix
helps; the limit is structural.

## 📊 Paper-grade vs pilot-grade (2026-06-07)

All current results are **pilot-grade**. The harness, ground truth, and design are
paper-ready (bugs fixed, fixtures deterministic), but the *runs* are not:

- **Synergy is now n=8** (hand-crafted fixtures) — real signal at 12.5pp resolution, NOT the
  old 33pp noise. But it's a **deterministic fixed set**: re-running gives the same 8
  questions, so there's no sampling variance to compute std over. It's a clean mini-exam, not
  a sampled distribution. For paper-grade error bars: either add fixtures (4–5/archetype →
  n=16–20) or sample each fixture k times at temp>0.
- **Turn (n=5), combat (n=3), run (n=3)** still move in coarse steps and need n≥20–30.
- **Model lineup is thin**: two Llama models, same family. Paper wants a capability ladder
  across families and ideally a frontier/reasoning model (the dropped qwen3 left none).
- All numbers need **mean ± std / CI**, not point estimates.

Bottom line: the remaining work is **scale + model breadth**, which is compute/credit-bound,
not code-bound. Paid Groq (or another paid provider) is the unblock.

## ✅ Synergy redesigned to hand-crafted archetype decks (2026-06-07)

**Decision:** the synergy dimension no longer evaluates RNG-drafted Act-1 decks. It now
uses 8 fixed, hand-crafted decks (`_SYNERGY_FIXTURES` in benchmark.py) — 2 per archetype,
each with 4–5 signature payoff cards so the archetype is unmistakable, a basic Strike as the
removal target, and a 3-card offer whose on-archetype card is the expert best pick.

**Why:** the `--n-synergy 10` RNG run exposed that RNG Act-1 decks are a dead end for
archetype ID. Evidence (per-sample audit, all 4 combos): only **3/10 decks** came out
confidently labeled, archetype_acc was an identical **0.333** everywhere, and the models
**collapsed to "Aggro"** on ~8/10 samples regardless of deck. Worse, the few "confident"
labels were debatable — seed 243 was labeled Block off a *single* Body Slam in an otherwise
aggressive deck, so the model answering "Aggro" was arguably *more* correct than the
heuristic. Root cause: Act-1 decks (6–13 cards, RNG-limited payoffs) simply don't have a
crisp archetype yet — those crystallize in Acts 2–3. Grounding "what's this deck's
archetype?" on them measures noise.

**Result:** ground truth is now deterministic and unambiguous (verified: all 8 fixtures
classify confident + match intended archetype; best-pick offer is on-archetype; removal =
Strike). The synergy test becomes a clean "given an obviously-X deck, does the model
identify X, pick the X card, and remove the dead basic?" — a measurement that can go in the
paper. The old `_archetype_draft_fn` (RNG-toward-target drafting) was removed as dead code.
**All prior synergy numbers are superseded — re-run `--only synergy --n-synergy 8` (8 = one
pass over all fixtures; multiples of 8 for repeats).**

The genuine findings from the RNG run still hold and are worth reporting: models show a
strong **Aggro-bias** (default to "Aggro" regardless of deck — the same bias the old
*heuristic* had), `removal_acc ≈ 0`, and low `card_pick_acc`. The fixed-deck eval will show
whether the Aggro-bias persists when the deck is unmistakably non-Aggro.

## ⚠️ Synergy archetype scoring — 3rd fix (2026-06-07): confident/ambiguous labels

The `--only synergy` re-runs (post 2nd-rework) produced **archetype_acc = 0.0 on ALL
4 llama combos** — including raw, which historically scored 100%. Investigation showed
this was the **expert heuristic mislabeling decks**, not model failure (parse_ok was 1.0,
i.e. the models WERE answering):

- **seed 244** was labeled `Exhaust` despite having **zero Exhaust cards** — the score
  came entirely from `Armaments` + `Headbutt`, which are miscategorized in the broad
  `_ARCHETYPES["Exhaust"]` list (added there for draft-coherence, but they're not Exhaust
  payoffs). The deck is plainly Aggro/Strength; a model answering "Aggro" was marked wrong.
- **seed 242** was a near-tie (Strength 4 / Block 5 / Exhaust 4 / Aggro 3) decided by one
  generic common. `Corruption` (a real Exhaust payoff, weighted 3×) lost to Juggernaut +
  filler. The deck has no dominant archetype; "Block" was arbitrary.
- **seed 243** was labeled `Block` off a single `Body Slam` in an otherwise aggressive deck.

**Root causes:** (1) miscategorized cards in the broad key-lists polluted the label;
(2) no confidence margin — when the targeted draft fails to land a payoff (common at small
card pools), the label is decided by generic-common noise.

**Fix:** added `_classify_archetype_confident(deck, relics) -> (label, confident)`. The
LABEL is now decided by **signature cards only** (`_ARCHETYPE_PAYOFFS`, relics count as a
signature). A deck is confidently labeled only when exactly one archetype uniquely owns the
most signatures; otherwise (no payoff, or a tie) it is **ambiguous** and `archetype_correct`
is set to `None` → excluded from `archetype_acc` (same pattern as survivors-only HP). The
plain `_classify_archetype` is unchanged (still used for draft coherence / best-pick, which
need a concrete answer). Synergy JSON now persists per-sample `expert_archetype`,
`model_archetype`, `confident`, plus `archetype_n_scored` / `archetype_n_ambiguous` so labels
are auditable. Verified on seeds 242/243/244: 242 & 244 → ambiguous (excluded), 243 → Block
(scored). 42 tests pass.

**Consequence:** the archetype_acc=0 numbers from the post-2nd-rework `--only synergy` runs
are INVALID (measured a broken heuristic). Re-run `--only synergy` with this fix. NOTE: at
n=3 the targeted draft lands a clean signature on roughly 1/3 of seeds, so few samples are
scored — **bump n_synergy** (≥10–20) so enough confident decks accumulate. A further
improvement would be making `_archetype_draft_fn` land payoffs more reliably (RNG-limited).

## ⚠️ Synergy eval reworked again (2026-06-07) — prior synergy numbers INVALID

The synergy dimension had two compounding problems, now fixed:

1. **Greedy-first-pick decks had no real archetype.** `run_synergy_eval` drafted with
   `_greedy_pick` (first non-curse offer), producing an incoherent pile of cards. There
   was no ground-truth strategy to identify — "archetype accuracy" was measuring agreement
   between two guesses on noise.
2. **Aggro-bias in the classifier.** `_classify_archetype` counted card *presence* equally,
   and the Aggro bucket is stuffed with generic Strike-variants (Twin Strike, Pommel Strike,
   Clash, Clothesline, Wild Strike) that appear in nearly *every* random Ironclad draft. So
   almost every greedy deck got labeled "Aggro" regardless of its actual contents. Verified:
   seeds 242/243/244 ALL classified "Aggro" — even seed 242, whose single most defining card
   was **Corruption** (the canonical Exhaust payoff). A model answering "Exhaust" there was
   *more* correct than the heuristic.

**Fix (option A):**
- Added `_ARCHETYPE_PAYOFFS` — signature cards weighted **3×** over generic support in
  `_classify_archetype` (payoff `Corruption` now outweighs three filler Aggro commons).
- Added `_archetype_draft_fn(target)`; `run_synergy_eval` now cycles targets
  Strength→Block→Exhaust→Aggro, drafting *toward* each so decks are coherent and all four
  archetypes get tested.
- Expert label is still derived from the **actual built deck**, not the target — if RNG can't
  supply enough on-archetype cards (seed 242 → genuinely Block-leaning), the model is fairly
  scored against what the deck really is.

Verified: 3/4 seeds draft to target; the 1 "mismatch" is correct (deck honestly came out Block).
All 40 unit tests pass. **All synergy numbers below predate this change and must be re-run with
`--only synergy` before going in the paper.**

## ✅ Synergy results on hand-crafted fixtures, n=8 (seed=42, 2026-06-07) — CURRENT

These supersede every earlier synergy table (the 67%/100% RNG-era numbers are retired).
All 8 fixtures classify confident, 0 ambiguous.

### Archetype accuracy
| Model | Structured | Raw |
|---|---|---|
| llama-3.1-8b-instant | 50.0% | 37.5% |
| llama-4-scout-17b | 75.0% | 50.0% |

### Card-pick accuracy
| Model | Structured | Raw |
|---|---|---|
| llama-3.1-8b-instant | 100% | 62.5% |
| llama-4-scout-17b | 75.0% | 100% |

### Removal accuracy
| Model | Structured | Raw |
|---|---|---|
| llama-3.1-8b-instant | 25.0% | 12.5% |
| llama-4-scout-17b | 25.0% | 12.5% |

### Per-archetype identification (8 attempts each: 2 decks × 2 models × 2 formats)
| True archetype | Correct | Models said instead |
|---|---|---|
| Block | 7/8 | one "Strength" |
| Aggro | 8/8 | — |
| Strength | 2/8 | almost always "Aggro" |
| Exhaust | **0/8** | **always "Aggro"** |

### New findings from the clean fixtures
1. **Models cannot recognise the Exhaust archetype.** 0/8 across all model/format combos — all
   eight Exhaust decks were called "Aggro" despite being stuffed with Exhaust signature cards.
   Strength is also weak (2/8). Models name an archetype only when its signature is a simple
   surface pattern (Block, generic Aggro); they miss strategies defined by a *mechanical
   interaction* (exhaust-for-payoff). Clean, systematic knowledge gap.
2. **Naming and playing are dissociated.** Card-pick is high (62.5–100%) even on decks the model
   can't label — e.g. llama-8b structured picks the right card 100% of the time while scoring
   only 50% on archetype ID. Local card-quality judgement is strong; the abstract strategic
   label is weak. This dissociation is itself a paper-worthy result.
3. **Removal is a near-total failure (12.5–25%).** The non-zero values come only from Block
   fixtures where the expert removal target coincides with what the model would cut. Expert says
   remove basic Strike (basics dilute draw quality); models instead remove situational cards
   (Disarm, Battle Trance, Bash), reasoning about standalone card quality, not deck cycling.
4. **No single format wins.** Raw helps llama's card-pick on some decks; structured helps
   scout's archetype ID (75% vs 50%). Format is task-dependent, not uniformly better either way.
   scout-17b (structured) is the strongest archetype identifier overall.

### Dimension difficulty ranking (pilot, fixed-fixture synergy)
1. Combat (easiest) — 100% win rate, beats greedy bot on HP
2. Synergy card-pick — 62.5–100%, surprisingly strong
3. Synergy archetype ID — 37.5–75%, collapses on Exhaust/Strength
4. Turn-level — 37–70% damage ratio, format-sensitive
5. Synergy removal — 12.5–25%, systematic conceptual failure
   (Run-level: hardest in principle, but NO valid data yet — excluded.)

### Run-level — NO valid data (see top of file)
The run-level numbers on disk (llama 20%/40%, 13.4 floors) are from pre-fix code and are
**excluded**. Run-level has no valid measurement yet; a clean pass is pending and blocked on
free-tier TPM (needs paid Groq). Do not quote the old figures.

## Open hypotheses
- Larger models (17B, 32B) may improve turn legal rate more than damage ratio.
- Run-level failure may be prompt length issue — full run state is very long context.
- Removal failure is likely a framing/knowledge gap: models reason about card strength, not deck cycling. Rephrasing the prompt ("which card hurts your draw quality most?") might improve it — worth testing as an ablation.
- On the n=8 fixtures the format effect on card-pick reversed vs the old n=3 RNG run: scout-17b now scores 75% structured / 100% raw, and llama-8b 100% structured / 62.5% raw. No clean "structured helps index tasks" story at this n — worth re-testing at n≥20.
