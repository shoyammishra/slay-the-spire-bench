# Findings

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

## Post-fix results (llama-3.1-8b-instant + scout-17b, seed=42, synergy re-run 2026-06-07)

### Synergy archetype accuracy (post synergy-fix)
| Model | Structured | Raw |
|---|---|---|
| llama-3.1-8b-instant | 67% | 100% |
| llama-4-scout-17b | 67% | 100% |

Both models identify archetype correctly in raw format. Structured format loses ~33pp — consistent with raw being better for reasoning tasks.

### Card pick accuracy
| Model | Structured | Raw |
|---|---|---|
| llama-3.1-8b-instant | 33% | 33% |
| llama-4-scout-17b | 67% | 33% |

Scout-17b shows improvement in structured format. At n=3 this is noisy but directionally consistent with larger models being better at index-based picking.

### Removal accuracy — confirmed genuine model failure
All four combinations (2 models × 2 formats) score 0% removal_acc. Investigated and confirmed:
- Expert heuristic says remove "Strike" first (verified correct via STS community guides — basics dilute draw quality, Strike is dead weight post-Act 1 with better damage cards in deck)
- Models consistently say: Disarm, Battle Trance, Bash (reasoning about card *quality* for archetype, not deck *cycling*)
- This is a clean finding: LLMs don't internalize the STS meta-principle that basics should be removed because they crowd out better draws, not because they're inherently bad cards
- Failure is systematic (same wrong reasoning pattern), not random — useful signal for the paper

### Format effects (updated)
- Raw format better for reasoning tasks: archetype ID, turn sequencing (+33pp on damage ratio for 8B)
- Structured format better for index-based output: card pick (scout-17b structured 67% vs raw 33%)
- Removal failure is format-independent — both fail equally

### Dimension difficulty ranking (post-fix, structured)
1. Combat (easiest) — 100% win rate, beats greedy bot on HP
2. Synergy archetype (medium) — 67% with real deck, 100% in raw
3. Turn-level (hard) — 37% damage ratio, 60% legal rate in structured
4. Synergy removal (very hard) — 0% both models both formats
5. Run-level (hardest) — 20–40% survival, 13.4 avg floors

### Run-level (post map+EventBus fix)
- llama-3.1-8b: 20% structured, 40% raw survival; 13.4 avg floors both formats
- Floors reached is now real — previously stuck at 5/15 due to map dead-end bug
- Raw format significantly better on survival (40% vs 20%)

## Open hypotheses
- Larger models (17B, 32B) may improve turn legal rate more than damage ratio.
- Run-level failure may be prompt length issue — full run state is very long context.
- Removal failure is likely a framing/knowledge gap: models reason about card strength, not deck cycling. Rephrasing the prompt ("which card hurts your draw quality most?") might improve it — worth testing as an ablation.
- Scout-17b shows improvement on structured card pick (67% vs 33%) — larger model may be better at index-based tasks specifically.
