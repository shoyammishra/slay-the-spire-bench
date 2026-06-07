# Findings

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
