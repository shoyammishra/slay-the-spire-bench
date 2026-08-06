# Findings

## 🟢 qwen3-32b FULL 4-dimension matrix (Sharanga H200, retrieved + audited 2026-08-07) — CURRENT for every qwen3-32b cell

qwen3-32b's intentional synergy-only gap is **closed**: all four dimensions × both characters
× both formats, n=20 (turn/combat/synergy), run-level at **n=5 per seed = 25 runs/combo**.
Full tables, wall-clock, and the per-sample audit: `docs/experiment_log.md` 2026-08-07 (top).
⚠️ These cells **SUPERSEDE the CSIS qwen3-32b synergy-only cells** (vLLM 0.8.x there vs 0.25.1
here) — never blend the two; the superseded files are archived at
`results/_csis_qwen3-32b_2026-06-22/` (gitignored).

**A. The instrument was interrogated before the numbers were believed.** Silent-structured
returned `turn dmg_ratio = 1.000 ± 0.000` — boundary value, zero variance across 5 seeds, the
exact signature the project rule says to distrust. Cleared by two audits: per-sample
decomposition (oracle sequences are 2–4 cards, never trivial; 0 sub-optimal samples out of 100;
the 52 non-identical sequences are permutation ties among *optimal* orderings) and a
degenerate-strategy baseline (**`scripts/turn_saturation_check.py`**, reproducible, zero API):
across all 100 states per character, **0/100 are saturated**, only 0.0–1.0% of legal sequences
reach the optimum, a random legal sequence scores 0.145 (Silent) / 0.231 (Ironclad), and a
zero-planning left-to-right policy scores 0.510 / 0.614. **Verdict: the 1.000 is a real
planning result, not an instrument ceiling.**

**B. ⚠️ Turn-level is now SATURATED AT THE TOP — an instrument limit for M3b.** qwen3-32b maxes
Silent-structured at 1.000, so no frontier model can separate above it there. The left edge of
the horizon-collapse curve has lost its headroom; **do not expect turn-level to rank frontier
models**. The discriminating horizons are now synergy and run. (This does not invalidate any
existing number — it bounds what the dimension can still show.)

**C. Best short-horizon performance in the matrix** — turn 0.933–1.000 vs the previous best
(deepseek-r1-14b 0.823/0.839) and the 7–8B pack (0.18–0.81).

**D. First non-zero run-level survival lift in the project's history** — Ironclad structured
**0.12 survival vs the measured greedy 0.01**, floors **13.24 vs greedy 12.48**; Silent
structured 11.56 vs greedy 11.26. ⚠️ **A signal, not a result:** n=25 runs, std 0.179 across
seeds → ~3 survivors concentrated in one or two seeds. Registered as an **n=5 floor estimate**;
never blend with the n=20 run-level rows, and do not write "beats greedy" — write "the first
model to rise off the run-level floor, at n=25 with wide seed spread."

**E. The 2026-07-13 parse-probe verdict replicates in a second model family.**
`avg_json_parse_errors == avg_truncation_errors` **exactly** in all four combos (.06/.06,
.20/.20, .05/.05, .34/.34): every JSON failure is a token-budget truncation, zero
malformed-but-complete outputs — the same identity found for the DeepSeek distills, at ~25×
smaller magnitude. The counter split measures what it claims to, across families.

**F. Format effect reaches the survival horizon for the first time.** Structured wins archetype
(IC .606/.510, Silent .790/.710), removal (IC .334/.190, Silent .530/.230) **and run-level
floors on both characters** (13.24/12.20 IC, 11.56/10.12 Silent) — run-level had been documented
as format-insensitive on outcome. raw wins card_pick on both characters (IC .534/.560, Silent
.370/.430). Combat `illegal_action_errors` is the sharpest format trace: raw 0.93/0.53 vs
structured 0.03/0.08 (~10×) while the JSON-failure component barely moves.

---

## ✅✅ Full 5-model matrix, 5 seeds (2026-06-22; DeepSeek gap-fill folded 2026-07-11) — CURRENT valid data (supersedes Qwen-only)

Five model families now run under the post-audit harness: qwen2.5-7b, llama-3.1-8b (2nd
family), mistral-7b (3rd family), qwen3-32b (reasoning), deepseek-r1-distill-14b/7b (reasoning
distill). Full tables in `docs/experiment_log.md`. The two D&B-blocking gaps from the novelty
review — ≥3 model families and a reasoning model — are now closed. **2026-07-11 gap-fill:**
deepseek-14b Silent-raw turn/combat and deepseek-7b turn/combat + synergy (all four combos)
landed and are folded in below — the DeepSeek picture is now complete except intentionally
skipped run-level cells.

1. **The horizon-collapse curve finally separates.** With only 7–8B instruct models the four
   per-horizon lines ran roughly parallel; **qwen3-32b (reasoning) is the first line to bend
   away at the synergy horizon** — Silent-structured archetype **0.80** and removal **0.55** are
   the highest anywhere in the matrix, well above the 7–8B pack (archetype ~0.33–0.72). This is
   exactly the D&B-grade claim the curve needed: a frontier/reasoning model sustains coherent
   *deck-level* planning where smaller models plateau. ~~(qwen3-32b is synergy-only, so the curve's
   turn/combat/run points for it are not yet filled — a known gap, but synergy is the horizon
   where the separation lives.)~~
   **⚠️ UPDATED 2026-08-07 — the gap is closed and the shape of the claim changed.** qwen3-32b now
   has all four dimensions (section 🟢 above). Its line does not merely *bend away at synergy*: it
   is **highest at turn (0.933–1.000), holds combat at the ceiling, leads synergy, and is the only
   model to rise off the run-level floor** (IC structured 13.24 floors / 0.12 survival vs greedy
   12.48 / 0.01). The honest re-statement is **"qwen3-32b degrades least across all four
   horizons"**, not "it separates only at synergy." Two consequences: the curve's turn point is now
   **saturated** (no headroom above 1.000 for M3b frontier models), and the numbers behind
   qwen3-32b's synergy point are the Sharanga ones, not the CSIS ones used when this was written.

2. **Reasoning is not a free win — the deepseek distills split hard by size, and verbose decode
   actively hurts long horizons.** deepseek-r1-distill-**14b** is the *best* model at the
   shortest horizon on BOTH characters (turn dmg IC **0.823**, Silent **0.839** vs the 0.18–0.71
   pack) but pays for its `<think>` verbosity downstream: it is the **only mid-size model that
   loses combats** (Ironclad win 0.92/0.73; Silent 0.57 structured, **0.34 raw** with hp_ratio
   0.21 and ~5 parse_errors/combat — the 2026-07-11 gap-fill's sharpest new cell), its combat
   hp_ratio drops to 0.21–0.75 (everyone else ≈1.0), and its Ironclad run-level floors crash to
   **9.75 — below the greedy ~12.5 floor**: it over-deliberates into death.
   deepseek-r1-distill-**7b** collapses in **every one of the four combos** (turn 0.26–0.43,
   combat win 0.14–0.28, hp_ratio 0.05–0.15, **~8 invalid-action errors/combat**; turn parse_ok
   as low as 0.38) — ⚠️ mechanism identified 2026-07-13 (parse-probe section below): NOT a
   failure to hold the terse-JSON contract, but **budget-bound deliberation** — 100% of its true
   JSON failures are token-budget truncations mid-`<think>`.
   **New anomaly from the gap-fill:** 7b's synergy **removal acc stays high (.41–.54; IC
   structured .54 is 2nd in the whole matrix, behind only qwen3-32b's .55)** while everything
   execution-shaped collapses around it — the single-shot judgment call survives when multi-step
   execution dies. Caveat: 7b synergy parse_ok is 0.69–0.92, so those accs are conditioned on
   the parseable ~14–18 of 20 fixtures. **Lesson for the paper:** "reasoning model" is not a
   monolith; distillation size and output discipline gate whether reasoning helps, and the cost
   lands on the *long* horizons — itself a horizon-collapse result.
   **⚠️ CORRECTED 2026-08-07 — attribute the collapse to DISTILLATION, not to reasoning.** With
   qwen3-32b's full matrix in hand the contrast is direct: a *full* reasoning model at 32B holds
   combat win 0.99–1.00 with hp_ratio 0.995–1.075 (≥ the greedy bot) and run floors **at or
   above** the greedy anchor, while the R1 *distills* lose combats and die below it. The
   verbose-decode penalty is a property of **the distills' budget-bound deliberation**
   (parse-probe, 2026-07-13), not of reasoning training as such. Do NOT write "reasoning models
   over-deliberate into death" — write "the R1 distills do; the full 32B reasoning model does not,
   and is the strongest model in the matrix at every horizon." The distill-vs-full dissociation
   the P6 rebuttal plan leans on is unaffected — it was always distill against full.

3. **Format ablation replicates across families but its *sign* is model- and character-dependent
   — synergy removal is the most robust signal, with exactly one exception.** Structured ≥ raw on
   **synergy removal for 5 of 6 models** (mistral .15→.00, qwen2.5 .24→.02, llama .15→.07,
   qwen3-32b .29→.22 & .55→.32, deepseek-7b .54→.42 & .45→.41; Silent likewise), so removal is
   the cleanest cross-model format effect. **The sole reversal is deepseek-14b — raw beats
   structured on removal in BOTH characters** (IC .18/.30, Silent .15/.41), consistent with the
   verbose-`<think>` model treating the terse structured contract worse than free prose. The
   direction also flips elsewhere: mistral *reverses* on Ironclad archetype (raw .45 > structured
   .33); llama and mistral are **better in raw at turn-level** on both characters (llama Silent
   raw 0.810 vs structured 0.472) — the opposite of qwen2.5's Ironclad turn. So "structured helps
   reasoning" is true *in aggregate and most strongly at the synergy/removal horizon*, not as a
   blanket per-cell rule. Report it as: format matters, the effect is concentrated at the
   deck-building horizon, and its magnitude/sign varies by model — which is itself a finding
   (format sensitivity is a model property, not a constant).
   **⚠️ UPDATED 2026-08-07 (count unchanged, one number restated, one scope EXTENDED).** The
   qwen3-32b removal figures above are the superseded CSIS ones; the current values are
   **IC .334→.190 and Silent .530→.230** (Sharanga full matrix). qwen3-32b stays on the structured
   side, so **"5 of 6 models" is unchanged** — qwen3-32b was always one of the 6, and deepseek-14b
   remains the sole reversal. **New and worth a sentence in the paper: the format effect now
   reaches the RUN horizon.** qwen3-32b structured beats raw on run-level floors for both
   characters (13.24/12.20 IC, 11.56/10.12 Silent), the first breach of the standing
   "combat/run are format-insensitive on outcome" claim — see finding 4's marker.

4. **Combat/run remain the shared collapse floor — model differences wash out where engine
   survival dominates.** All instruct models win ~100% of scripted combats with hp_ratio ≈ 1.0
   and reach ~11–13.8 floors ≈ greedy; the *only* deviations are the reasoning models (deepseek
   losing combats). This is the multi-horizon thesis in one sentence: **inter-model variance is
   large at the reasoning horizons (turn spread 0.18→0.84, synergy archetype 0.33→0.80) and
   near-zero at the survival horizons (combat win, run floors)** — so the benchmark's
   discriminating power lives at turn + synergy, and run is honestly the convergence floor.
   **⚠️ FIRST CRACK IN THE FLOOR, 2026-08-07 — keep the claim, weaken the "never".** qwen3-32b is
   the first model to rise off the run-level floor: IC structured **0.12 survival / 13.24 floors**
   vs measured greedy **0.01 / 12.48**, and structured > raw on floors for both characters — so
   run-level is not *perfectly* format-insensitive or *perfectly* non-discriminating. It is still
   the convergence floor for the other five models, and this lift rests on **n=25 runs with std
   0.179 across seeds** (~3 survivors, likely one or two seeds). Write it as "the floor holds for
   every model except the strongest, where a first lift appears at n=25 and needs n=20 to
   confirm" — not as a refutation. The turn spread quoted above also widens to **0.18→1.00**.

5. **Family-level synergy ordering holds: Silent > Ironclad almost everywhere** (qwen3-32b
   archetype .80 vs .53 — *current Sharanga values .790 vs .606, ordering unchanged*, llama .72
   vs .51, qwen2.5 .60 vs .37) — replicating that Silent's
   Poison/Shiv/Block/Discard labels read more literally off card text than Ironclad's
   abstractions. mistral is the exception (≈ flat .33/.34), consistent with it being the weakest
   reasoner overall.

## 🔬 Parse-probe verdict (2026-07-13): DeepSeek parse failures are BUDGET-BOUND DELIBERATION, not output-discipline failure

Diagnostic probe (`cluster/parse_probe.sbatch`, `--run-tag parse_probe` — **diagnostic cells,
never folded into matrix tables**; turn n=20 + combat n=3, **seed 42 only**, max_tokens 8000).
Four cells: deepseek-7b Ironclad + deepseek-14b Silent, both formats. Full table:
`docs/experiment_log.md` 2026-07-13 entry.

**The decisive number: `parse_fail_truncated / parse_fail_n` = 1.0 in every cell, at both
horizons.** 7b IC: 10/10 structured, 7/7 raw; 14b Silent: 1/1 structured, 5/5 raw; combat
`truncation_errors == json_parse_errors` exactly everywhere. Zero malformed-but-complete
outputs. Every single true JSON failure = the model hit the 8000-token budget inside `<think>`
and never emitted the answer. **Paper framing: "budget-bound deliberation"** — the DeepSeek
collapse is a deliberation-*length* property, not a formatting one. This sharpens finding 2
above: the distills don't *break* the JSON contract, they never *reach* it.

Corollaries: (a) the matrix's conflated combat counter decomposes ≈70–75% truncation +
25–30% valid-JSON-but-illegal actions — keep citing it as **"invalid-action errors"**
(reporting rule, decision_log 2026-07-12); (b) the probe replicates the matrix numbers
(7b win .33/.00, ~7–9 errors/combat; 14b Silent raw win .33 / hp .21 ≈ the matrix's worst
cell .34/.21) — the instrumentation decomposed the counts without moving them; (c) 7b
**structured is worse than raw on turn parse** (10 vs 7 truncations) — the structured prompt
provokes *longer* deliberation in the small distill, consistent with its .38 parse_ok floor.
Caveats travel with the number: single seed, combat n=3, post-instrumentation harness.

## ✅ Paper-grade Qwen2.5-7B, 4 dimensions, 5 seeds (2026-06-13) — CURRENT valid data

First complete self-hosted, multi-seed, post-audit matrix (full tables in
`docs/experiment_log.md`). Headline findings:

1. **Seed-matched format ablation lands.** Structured beats raw on every reasoning-heavy
   metric for BOTH characters — sharpest on synergy: Ironclad card_pick 0.47→0.27, removal
   0.24→**0.02**, archetype 0.37→0.25; Silent archetype 0.60→0.42, removal 0.36→0.18. Turn
   raw also carries ~2× the variance (±0.175 vs ±0.078). This is the core novelty claim
   (same RNG seed, only the prompt rendering changes) confirmed on a self-hosted model, not
   just the Groq llama/scout pilots.
2. **Format is invisible to combat/run.** Both formats win 100% of scripted combats
   (hp_ratio ≈ 1.04–1.07, on par with greedy — not beating it) and reach ~12.8–13.4/16
   floors before dying at the Act-1 boss. These dimensions are gated by engine survival, not
   prompt comprehension. → The format effect is **specific to the planning/labeling
   dimensions**, which is exactly the multi-horizon decomposition story: format matters where
   reasoning matters, not where raw survival dominates.
3. **Run-level survival is a floor effect, report progress instead.** Greedy baseline
   **measured 2026-07-12** (per character, same seeds as the matrix; `scripts/greedy_baseline.py`
   — free, deterministic, zero API): **Ironclad 12.48 floors / 0.780 progress / 1% survival;
   Silent 11.26 floors / 0.704 progress / 0% survival** (Silent's greedy Act 1 is harsher — lower-
   block starter). The old "~12.5 floors / ~1%" note held up for Ironclad; Silent is materially
   lower (this is why the horizon-curve run anchor is now per-character — decision_log 2026-07-12).
   Qwen 12.8–13.4 (IC) / 10.9–11.9 (Silent) floors ≈ each character's greedy → on par. Always cite
   avg_floors_reached / avg_progress, never survival_rate alone, and never "beats the bot."
4. **Silent synergy > Ironclad synergy** (archetype 0.60 vs 0.37 structured) — replicates the
   earlier finding that Silent's mechanic labels (Poison/Shiv/Block/Discard) read more
   literally off card text than Ironclad's abstractions.
5. **raw archetype collapses to a single guess — VERIFIED per-sample, not a bug.** In raw
   format the model labels **17/20 fixtures "Block" on every seed** (the rest jitter by one
   between Aggro/Strength), so std≈0 is the *signature* of the collapse, not a measurement
   artifact. The 20 Ironclad fixtures are exactly 5 Exhaust / 5 Aggro / 5 Strength / 5 Block;
   raw scores **5/20 = precisely the 5 Block decks and nothing else** → raw archetype accuracy
   = the **Block base rate of its constant guess** (0.25), which is actually *below* the same
   model's structured 0.35–0.40 and only a hair above 6-way chance. Confirmed it's a prompt
   effect, not an instrument bug, by three checks: (a) `expert_archetype` cycles all 4
   archetypes so the model *is* receiving different decks; (b) the same model on the same
   fixtures in **structured spreads its answers** (Block 10–11, Strength 6–8, Aggro 1–3, occ.
   Exhaust) and scores 7–8/20 — if the instrument were broken both formats would collapse
   identically, they don't; (c) parse_ok=1.0, so it's emitting a valid chosen label, not
   defaulting. **Interpretation:** the verbose English prompt mentions Block/defense in nearly
   every card description, so the 7B anchors on "Block" and stops discriminating; compact JSON
   forces it to read the actual card list. This is the cleanest single illustration of the
   format-ablation thesis — same seed/deck, only rendering changes, and raw kills per-deck
   reasoning. (Per-sample data: `results/qwen2.5-7b_{raw,structured}_seed*.json` → `synergy.samples`.)

6. **Silent is now a complete 4-dimension matrix (added 2026-06-14).** Two Silent-specific
   results sharpen the story: (a) **the turn-level format effect is character-dependent** —
   on Silent raw ≈ structured (0.681 vs 0.663, raw even nudges ahead), the opposite of
   Ironclad where structured won turn; so the *robust* format signal is synergy, not turn.
   (b) **Silent reaches fewer run floors than Ironclad** (10.9–11.9 vs 12.8–13.4, survival ≈ 0)
   — its lower-block starter makes the post-audit Act-1 greedy combat harsher; still a floor
   effect, report avg_floors/progress. (c) Combat stays format-insensitive on outcome, with the
   only trace in parse_errors (Silent raw 3.38 vs structured 0.92 — verbose state is messier to
   parse even when the win is unchanged).

**Carry-forward caveats:** combat hp_ratio just above 1.0 is "on par," not "beats" (the old
>100% was a Burning-Blood artifact, fixed). Both characters now complete on all four
dimensions. Still single-model — paper needs a 2nd/3rd family + (ideally) a reasoning model
(qwen3-32b once vLLM 0.8.x is up).

## ⚠️ 3rd audit (2026-06-11): enemy block was a no-op, HP-loss was blockable, and the turn eval had a replay loophole

A third full-source audit (after the engine-fidelity batch landed) found 40 more bugs —
all fixed same day, 102/102 tests (`docs/bug_audit_2026-06-11.md`). Three matter for
interpreting any past or future numbers:

1. **Every enemy blocking move was a silent no-op** — enemy block was reset at the
   *player's* turn start, so Bellow/Defensive Stance/enemy Metallicize/Curl Up never
   protected anything. All simulated combats were easier than real StS (symmetric for
   LLM and greedy bot, but it shifts win rates and HP margins for both). Block now
   resets at the enemy phase start.
2. **HP-loss effects (Offering, Combust, player-side poison) were absorbed by block** —
   notably, poison *against the player* was largely neutralized by leftover block.
   Now bypasses block, per StS rules.
3. **Turn-eval replay loophole:** `plays: [i, i]` with an identical twin in hand
   replayed an already-played card and was scored *legal* — a model could (and with
   hand-counting cards like Fiend Fire, would) exceed the legal optimum; damage_ratio's
   1.0 cap masked it. The duplicate-index path is now illegal and the whole stack
   (play_card / simulator / oracle) is identity-strict. Stale turn-level legal-rate and
   damage-ratio numbers are tainted by this in an unmeasurable direction — one more
   reason they are history-only.

Also closed: **Neow's Lament sat in the mid-run event pool** — its auto-picked boon
(enemies at 1 HP for 3 combats) could trigger from any EVENT node, an upward bias lying
in wait for the first valid run-level pass (run-level never had valid data, so no
published number is affected). Synergy n=20 is untouched by all of the above.

## ⚠️ Played cards VANISHED from combat — every prior combat simulation under-decked (2026-06-11)

The engine-fidelity batch's pass over the card implementations found that `Card` (a
`@dataclass`, field-based `__eq__`) made `play_card`'s pile bookkeeping match identical
TWINS: playing a Strike while another Strike was in hand meant the played copy never
reached the discard pile — it vanished from the combat. With 5 Strikes + 4 Defends in the
starter deck this fired constantly, so every combat ever simulated ran on a silently
shrinking deck (fewer reshuffles, weaker late turns — symmetric for the LLM and the greedy
bot, but not the real game). Sibling bug: self-exhausting cards (31 callsites)
double-entered the exhaust pile and double-emitted CARD_EXHAUST (Feel No Pain / Dark
Embrace triggered 2×). Both fixed with identity-based pile ops + regression tests.
Consequence: pre-2026-06-11 turn/combat numbers (already stale from the debuff-timing fix)
are doubly non-comparable. Synergy is unaffected (static deck snapshot, no combat).

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
Full audit: `docs/bug_audit_2026-06-10.md` (its engine-fidelity fix batch was completed
2026-06-11 — Part 2 + Part 3 in that doc).

Reassuring negatives from the same audit: the de-biased synergy n=20 results SURVIVE (all 40
fixtures classify confidently as labeled; no string-matching near-misses in removal scoring —
wrong answers are genuinely wrong cards, mostly "Defend"); Ironclad turn-level oracle values
are unaffected by the cap bug (5-card opening hand → byte-identical before/after the rewrite).

## ⭐ Mechanic-defined archetypes are a cross-character blind spot (RECOMPUTED on the full matrix 2026-07-12; original 2026-06-10)

**2026-07-12 update — numbers below recomputed from the CURRENT matrix** (all 120 per-seed
result files = 6 model configs × 2 characters × 2 formats × 5 seeds, 2,400 synergy samples;
one-off pool over each sample's `expert_archetype`/`archetype_correct`, `None` excluded).
The original 2026-06-10 pooled table (Aggro 95 / Poison 95 / Shiv 90 / Block 85 / Strength 40 /
Exhaust 5 / Discard 5) was computed on the Groq llama+scout era whose result files were later
deleted (2026-06-14) — do not cite it. The qualitative shape SURVIVES on current data; the
magnitudes changed (current models are weaker on Aggro/Shiv):

| Archetype | Acc (matrix) | | Archetype | Acc (matrix) |
|---|---|---|---|---|
| Block (both) | 0.81 (464/573) | | Shiv (Si) | 0.44 (126/288) |
| Poison (Si)  | 0.81 (233/288) | | Strength (IC) | 0.31 (91/291) |
| Aggro (IC)   | 0.60 (175/291) | | **Discard (Si)** | **0.14 (42/295)** |
| | | | **Exhaust (IC)** | **0.017 (5/288)** |

Both blind-spot archetypes score **below the 0.25 four-way chance floor** → systematic
mislabeling, not guessing. Card-pick on those same Exhaust+Discard decks: **0.43 (252/583)
vs 0.33 chance** — the name-vs-play dissociation holds on current data.

*(Historical 2026-06-10-era detail — deleted Groq data, superseded by the matrix table above;
kept for the qualitative failure modes, which still hold: Exhaust decks get labeled
"Aggro"/"Strength" even with Corruption / Feel No Pain / Dark Embrace / Fiend Fire present;
Discard decks get labeled "Block"/"Shiv"; Strength is frequently "Aggro" because Strength
decks are Strike-heavy.)*

**Why it matters for the paper:** a clean, mechanistic, reproducible failure mode that the
multi-horizon decomposition isolates — the model picks good cards locally (dissociation below)
but cannot name the *strategy* when the strategy is a payoff loop rather than a keyword. Two
characters give it cross-domain support within one engine, and the two blind-spot archetypes
are the structurally analogous ones (exhaust-payoff ↔ discard-payoff).

**Name-vs-play dissociation is REAL, not an artifact.** Current-matrix numbers: card-pick on
the blind-spot (Exhaust+Discard) decks is 0.43 vs the 0.33 rotated-offer chance floor, while
archetype-ID on the same decks is 0.02–0.14. Models judge local card quality above chance even
on decks they systematically mislabel. *(Historical 2026-06-10-era version of this paragraph
cited 0.65–0.75 card-pick and scout-17b removal 0.60 — deleted Groq data, do not cite.)*

**Secondary:** Silent archetype-ID ≥ Ironclad holds in the matrix (see the 5-model section at
the top of this file). Full tables: docs/experiment_log.md.

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
