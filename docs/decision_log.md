# Decision Log

## 2026-06-22 (model matrix) — qwen3-32b REVIVED + reasoning-distill family added; coverage gaps accepted
**Decision:** The full benchmark matrix now spans **5 model families** (qwen2.5-7b, llama-3.1-8b,
mistral-7b, qwen3-32b, deepseek-r1-distill-14b/7b). **qwen3-32b is un-dropped:** the reason it
was dropped (free-tier TPM truncated its `<think>` mid-reasoning → parse-failure cascade) is gone
once self-hosted on an A100 — it now runs at parse_ok=1.0. It was collected **synergy-only** by
choice: synergy is the horizon where a reasoning model is expected to (and does) separate from the
7–8B pack, and it's the cheapest cell to prove that on a 32B. We are **not** back-filling its
turn/combat/run unless a reviewer asks — synergy carries the separation claim. Two DeepSeek-R1
distills added to probe "does reasoning help, and does distillation size matter": 14b (full
Ironclad incl. run; partial Silent) and 7b (Silent raw turn/combat probe only).
**Why:** Closes the two D&B-blocking gaps the novelty review named — ≥3 model families and a
reasoning model. The finding justifies the spend: reasoning is **not** a monotone win — the 14b
distill's verbose decode *hurts* the long horizons (only model to lose combats; Ironclad run
floors 9.75, below the greedy floor) and the 7b distill collapses (parse_errors 7.93). qwen3-32b,
which stays terse, is the one clean frontier-line that bends away at synergy (Silent archetype
0.80). The remaining holes (qwen3 turn/combat/run; deepseek Silent raw turn/combat + run) are
accepted because they fall on the horizons that are either the convergence floor (run) or where
the separation isn't (combat) — documented as "Coverage gaps" in experiment_log.md, not silently
omitted.

## 2026-06-12 (GPU access) — `cluster/` Slurm toolkit + public-repo IP scrub
**Decision:** Added a `cluster/` toolkit for the BITS CSIS Slurm cluster (the M3a GPU): `setup.sh` (conda env + vLLM), `lib.sh` (shared vLLM serve/wait/stop helpers, model selected via `HF_REPO`/`SERVED_NAME`/`TP_SIZE` env vars, default `Qwen/Qwen3-32B`→alias `qwen3-32b`), `prefetch_model.sh` (login-node weight pull for offline compute nodes), `README.md`, and 4 staged sbatch jobs cheapest→most-expensive (`smoke`→`turn_combat`→`synergy`→`run_level`). Each job serves a model with vLLM on one A100 80 GB then runs `run_benchmark.py --provider local --base-url http://localhost:8000/v1`. Also added `.gitattributes` pinning `*.sh`/`*.sbatch` to LF (CRLF breaks bash on the Linux cluster).
**Why:** Turns the roadmap's M3a run order into paste-and-submit jobs so the GPU phase starts the moment the user SSHes in. One sbatch job runs both the server and the benchmark on the same node, so `localhost` works and the GPU is released on exit (trap).
**Security incident (same session, resolved):** the cluster login-node IP was accidentally committed (in `cluster/README.md` + CLAUDE.md) and pushed to this **public** repo. Fix: scrubbed all occurrences to a `<login-node-ip>` placeholder, removed the internal support email/room, gitignored the SOP PDF, then **purged the IP from all git history** with `git filter-repo --replace-text` and force-pushed `main` (verified: no commit contains the IP, old commit `74cf854` unreachable). Force-push required temporarily enabling GitHub branch protection's `allow_force_pushes`, **restored to disabled afterward (verified)**. Lesson codified in CLAUDE.md Security: never commit cluster IP/SOP to this public repo; placeholders only. Residual: GitHub may cache the old SHA by direct URL (optional GitHub-Support purge; low risk — internal RFC1918 IP, no creds).

## 2026-06-12 (5th audit) — Partial-save catches ALL exceptions, not just rate limits
**Decision:** `run_run_eval` and `run_all` now catch any `Exception` (KeyboardInterrupt re-raised) at the run-seed and dimension boundaries: print the error loudly, stop the affected scope, keep everything completed so far. No retry, no silent swallowing.
**Why:** Only `RateLimitExhausted` triggered partial-save. On the GPU box, vLLM returns HTTP 400 when a prompt overflows the model's context window — `LocalLLM` (correctly) surfaces that as `RuntimeError`, which would have killed the process hundreds of calls into a run-level pass and discarded every completed run. The error must still be loud (it usually means a misconfigured endpoint or an undersized context), but losing finished work to it is never right.

## 2026-06-12 (5th audit) — `complete_json` fallback uses raw_decode, not an end-position scan
**Decision:** The JSON-extraction fallback tries `json.JSONDecoder().raw_decode(text[m.start():])` once per `{` (first success wins) instead of attempting `json.loads` on every (start, end) substring pair.
**Why:** The old scan was ~O(#braces × len²) on garbage input. A truncated 32k-char `<think>` dump (the exact qwen3 failure mode the GPU phase revives) contains no valid JSON and many braces — each parse failure burned minutes of CPU on top of the lost call. `raw_decode` parses a prefix and ignores trailing junk, so accepted inputs are identical and cost is linear-ish.

## 2026-06-12 (5th audit) — justApplied extends to the end-of-turn window (`turn_end_window`)
**Decision:** `CombatState.turn_end_window` is True during the TURN_END emit in `end_player_turn`; `_apply_power` marks player debuffs `just_applied` when applied during the enemy phase OR this window.
**Why:** Doubt/Shame apply Weak/Frail from `end_of_turn_effect` (inside the TURN_END handler). With only the enemy-phase flag, `_tick_player_debuffs` deleted the single stack at the end of the same round — both curses were complete no-ops. Real StS marks these justApplied so they cover the player's next turn. Berserk's self-Vulnerable (applied mid-turn, neither flag set) still ticks the same round, as it should.

## 2026-06-12 (GPU prep) — `--provider local` adapter for self-hosted models
**Decision:** Added `LocalLLM` (OpenAI-compatible `/v1/chat/completions` over urllib, no new deps) and wired `--provider local --base-url URL` into the CLI (falls back to `$LOCAL_BASE_URL` then `http://localhost:8000/v1`). It is `OpenRouterLLM` with the endpoint parametrized and the 402 path removed; a non-429 HTTP error is surfaced with the response body instead of swallowed. 300s timeout, 8000 max_tokens, optional `$LOCAL_API_KEY`.
**Why:** The M3a GPU phase serves open-source models (incl. the revived reasoning model) via vLLM/TGI/Ollama — all OpenAI-shaped. One thin adapter unblocks the entire self-hosted matrix the moment the professor's GPU access lands (~2026-06-13), with no Groq TPM cap. A local server never bills, so OpenRouter's 402-as-payment-wall logic is wrong here — failures should be loud (misconfig) not silently fatal.

## 2026-06-11 (3rd audit) — Block resets at its OWNER's turn start
**Decision:** Player block resets in `_begin_player_turn`; ENEMY block resets at the start of the enemy phase in `end_player_turn`. Enemy block gained during the enemy phase therefore persists through the player's next turn.
**Why:** Resetting enemy block at the player's turn start wiped every enemy blocking move (Jaw Worm Bellow, The Champ Defensive Stance, enemy Metallicize, Curl Up...) before the player could attack into it — all enemy defense was a silent no-op, making every combat easier than real StS for BOTH the LLM and the greedy baseline.

## 2026-06-11 (3rd audit) — Three player-damage modes in `_damage_player`
**Decision:** (1) default = enemy ATTACK damage: block + Intangible + Vulnerable + Torii apply; (2) `from_attack=False` = non-attack damage (Thorns retaliation, Burn/Decay ticks): blockable + Intangible-capped, but never Vulnerable-amplified, no Torii; (3) `is_hp_loss=True` = HP loss (Offering, Combust, player poison, curse ticks): bypasses block/Intangible/Vulnerable entirely. Tungsten Rod applies to all three.
**Why:** Block used to absorb HP-loss effects (neutering Offering/player-poison/Combust), and player Vulnerable amplified Thorns. These are distinct StS damage classes; one boolean couldn't express them.

## 2026-06-11 (3rd audit) — play_card is identity-strict and raising; repeated turn-eval indices are illegal
**Decision:** `play_card` checks hand membership by object identity and raises if `_remove_identical` fails; `_simulate_play_sequence` rejects duplicate indices; the turn oracle uses identity membership.
**Why:** Equality membership let `plays: [2, 2]` replay an already-played card through an identical twin — scored LEGAL with full damage, and hand-counting cards (Fiend Fire) could beat the legal optimum. The same hole let the oracle play side-effect-removed cards. Closes the instrument loophole at engine, simulator, and oracle level.

## 2026-06-11 (3rd audit) — Neow is floor-0 only; events never repeat within a run
**Decision:** Neow's Lament gets `condition: floor == 0` (events fire at floor ≥ 1, so it is out of the mid-run pool); `random_event` tracks `state._seen_events` and excludes seen events until the pool is exhausted. Unimplemented event fights grant no reward (Mind Bloom "I am War" gold removed).
**Why:** Run-level integrity: the auto-picked Neow boon (1-HP enemies ×3 combats) could trivialize combats from any event node, and repeatable events let free-reward events compound — both inflated run-level scores.

## 2026-06-11 (3rd audit) — Time Warp ≈ play-lock (engine-level), not an extra enemy turn
**Decision:** `play_card` checks enemies for `PowerId.TIME_WARP`; every Nth (12th) card play sets `combat.time_warp_lock` (all `can_play` → False until next turn) and grants the boss +2 Strength. `_begin_player_turn` clears the lock.
**Why:** Real Time Warp ends your turn and the boss acts; a forced mid-call turn-end doesn't fit the play_card API. The lock reproduces the strategic constraint (≤12 plays between enemy turns + ramp) without restructuring the turn loop. The old `check_time_warp` method was dead code — the Act-3 boss's signature mechanic simply didn't exist.

## 2026-06-11 (3rd audit) — Potions are inventory-only BY DESIGN (but registered for passive hooks)
**Decision:** No policy (greedy or LLM) drinks potions; `Potion.use()` has no callers and POTION_USED is never emitted. `start_combat` now registers potion `register()` hooks so PASSIVE potions (Fairy in a Bottle) work. Documented simplification, revisit if a potion-action dimension is ever wanted.
**Why:** Wiring potion-drinking into the LLM action space changes every prompt/action schema and the greedy baseline; not worth it pre-paper. But Fairy is passive — leaving it dead was just a bug.
**Decision:** All pile mutations for a specific card object go through `cards._remove_identical()` / `any(c is card for c in pile)`. `list.remove(card)` and `card in pile` are banned for combat piles.
**Why:** `Card` is a `@dataclass` → field-based `__eq__`; equality checks matched identical twins (another Strike), so played cards VANISHED from the game whenever a duplicate was in hand, and `_exhaust_card`/`_discard_from_hand` could remove or duplicate the wrong copy. Starter decks (5 Strikes/4 Defends) hit this constantly.

## 2026-06-11 — CARD_DISCARD means MANUAL discards only
**Decision:** Playing a card never emits CARD_DISCARD; only `_discard_from_hand` (Silent discard mechanics, Gambling Chip mulligan) does. End-of-turn hand discard also emits nothing.
**Why:** Real StS discard triggers (Tingsha, Tough Bandages, Hovering Kite) count manual discards during your turn — emitting on every card play made those relics fire constantly.

## 2026-06-11 — Relic counter lifecycles: class attr = per-run, TURN_START reset = per-turn
**Decision:** Per-RUN counters (Pen Nib, Nunchaku, Sundial, Happy Flower, Incense Burner, Tiny Chest, Omamori) live as class attributes never touched in `register()`; per-TURN counters (Shuriken, Letter Opener, Orange Pellets) reset via a TURN_START subscription; per-COMBAT counters (Centennial Puzzle) reset in `register()` (which runs at every combat start).
**Why:** `register()` re-runs each combat, so `self._count = 0` there silently made every counter per-combat — Tiny Chest could NEVER fire (needs 4 combat-ends).

## 2026-06-11 — Energy granted at COMBAT_START / TURN_END goes through ENERGIZED
**Decision:** Relics granting energy outside the player's turn window (Lantern, Ancient Tea Set, Art of War) queue `PowerId.ENERGIZED`, consumed at TURN_START after the energy reset. Direct `player.energy +=` is only valid mid-turn or in TURN_START hooks.
**Why:** `_begin_player_turn` SETS `energy = energy_per_turn` after COMBAT_START and at every turn start — direct additions before that point were silently wiped (three dead relics).

## 2026-06-11 — Character-gated relic pools via `relic_allowed()`
**Decision:** `relics_full.relic_allowed(relic_id, character)` + `_DEFECT_ONLY/_WATCHER_ONLY/_IRONCLAD_ONLY/_SILENT_ONLY` sets, applied with owned-relic dedup in `random_relic` and `generate_boss_relic_choices`. Boss relics removed from the chest "rare" pool; Nuclear Battery (Defect) removed from boss pools.
**Why:** Silent runs were drawing Brimstone/Magic Flower (Ironclad-only) and dead Defect/Watcher relics; boss-pool leakage gave chests run-warping energy relics. Mirrors the existing `card_pool_for` precedent.

## 2026-06-11 — MERCHANT = deterministic greedy shop, shared by both run loops
**Decision:** `nodes.greedy_shop_visit(state)`: Meal Ticket heal, then pay to remove the worst card (curse → basic Strike → basic Defend), buy nothing else. Used identically by `run_loop.resolve_node` and `RunEvaluator._play_act`.
**Why:** Shop floors were no-ops (gold accumulated unused — a dead stat). A conservative deterministic policy makes gold matter without injecting policy noise into the LLM-vs-greedy comparison; both sides get the same shop behavior.

## 2026-06-11 — Elite/boss room tags on enemies at spawn
**Decision:** `spawn_enemies(state, ids, elite=, boss=)` stamps `_elite`/`_boss` on each enemy; Preserved Insect, Slaver's Collar, and elite relic drops key on the tags. Elites now drop 1 relic (2 with Black Star) at real-StS rarity odds (50/33/17) in both run loops.
**Why:** Room type was invisible to relic hooks (Preserved Insect used a `max_hp>100` proxy that hit bosses); elites dropping no relics removed the core risk/reward of elite routing.

## 2026-06-10 (2nd audit) — Combat HP scored pre-COMBAT_END
**Decision:** `CombatEvaluator` captures `hp_remaining` BEFORE `end_combat()`; the greedy baseline keeps its no-COMBAT_END convention. Both sides now exclude post-combat relic heals.
**Why:** Burning Blood's COMBAT_END heal applied only to the LLM's score → identical play scored hp_ratio 1.095. Symmetric pre-heal reading restores 1.0 = parity.

## 2026-06-10 (2nd audit) — Turn oracle = prefix-pruned DFS, no positional cap
**Decision:** `_exhaustive_best_sequence` does DFS over ALL playable cards with illegal-prefix pruning, per-node dedup of identical cards, and a deterministic 20k-node budget (replaces permutations over the first 6 playable).
**Why:** The cap understated the optimum for any >6-playable hand (Silent's 7-card opener: 6/10 seeds wrong, up to 2×). DFS is complete AND faster (legal sequences are energy-bounded). Ironclad values verified byte-identical pre/post.

## 2026-06-10 (2nd audit) — Synergy instrument keyed on seed
**Decision:** Fixture selection (`seed % 20`) and offer rotation (`seed % 3`) derive from the sample's seed, not the loop index.
**Why:** Index-keyed selection made every `--seeds` run byte-identical → fake std=0 error bars. Seed-keying keeps per-run balance (consecutive seeds cover all fixtures once, uniform pick positions) while making seeds real treatments. Cost: per-sample pairing differs from the saved seed-42 n=20 files (aggregates comparable, rows not).

## 2026-06-10 (2nd audit) — Turn prompt states the scored objective
**Decision:** The turn system prompt explicitly says: maximize total damage THIS TURN; block/defense/setup are NOT scored; an illegal card zeroes the answer.
**Why:** The scorer is damage-only vs a damage-only oracle, but "optimal play" invited (correct!) defensive play that scored as failure — construct validity requires the model to know the objective. Turn scores are not comparable across this change (they were already stale pre-sweep).

## 2026-06-10 (2nd audit) — Intent display shows effective damage
**Decision:** `effective_move_damage()` (enemies.py) is the single source for Strength/Weak-adjusted per-hit damage, used by `_enemy_attack` and BOTH prompt formats. Enemies must store BASE damage in Moves (RedLouse violated this and double-counted).
**Why:** Real StS shows adjusted intent; showing base damage misinformed the LLM (Cultist "6 dmg" while Ritual hits grew 9/12/15) while the greedy baseline doesn't read prompts — an asymmetric handicap.

## 2026-06-07 — Illegal play scoring
**Decision:** If any card in a turn sequence is illegal, `damage_ratio = 0` (zero, not partial credit).
**Why:** Partial credit would reward models that guess randomly and happen to play some valid cards. Zero enforces that legal play is a prerequisite, not an add-on.

## 2026-06-07 — Single source of truth for energy deduction
**Decision:** `play_card()` in `combat.py` is the only place energy is deducted. Cards do NOT subtract energy themselves.
**Why:** Double-charge bug — cards were subtracting energy inside their own `play()` AND `play_card()` was also subtracting. Centralizing prevents this class of bug entirely.

## 2026-06-07 — avg_hp_fraction averaged over survivors only
**Decision:** Deaths contribute 0 to survival_rate but are excluded from avg_hp_fraction. Added avg_progress (floors/15) for partial credit on death.
**Why:** Averaging HP fraction over deaths (where HP=0) would conflate "died early" with "barely survived." Separating the two metrics gives cleaner signal.

## 2026-06-07 — Results overwrite by model+format+seed (no timestamps)
**Decision:** Output files named `<model>_<format>_seed<N>.*` — re-runs overwrite.
**Why:** Easier to compare runs; no accumulation of stale files. Seed makes runs reproducible, so timestamps add no information.

## 2026-06-07 — EventBus.clear() at start of each combat
**Decision:** Clear all listeners at the top of `start_combat`.
**Why:** Listener stacking bug — handlers accumulated across combats in a run, making player progressively invincible. Clearing ensures each combat starts with exactly one registration per relic/power.

## 2026-06-07 — Synergy eval uses greedy card_choice_fn to build a real deck
**Decision:** `run_synergy_eval` now passes `_greedy_pick` (first non-curse offer) as `card_choice_fn` to `run_act`, so the deck has real archetype-defining cards at eval time.
**Why:** With `card_choice_fn=None`, no cards were ever added. The synergy snapshot was always the 10-card starter deck, making `_classify_archetype` always return "Aggro" by default — zero signal. Expert label and model answer were both noise.

## 2026-06-07 — `--only` flag for partial benchmark runs
**Decision:** `run_benchmark.py` accepts `--only turn|combat|synergy|run` to run a single dimension. Skipped dims produce `null` in the summary JSON; merge logic fills them from the previous file on disk.
**Why:** Dimensions are fully independent (separate seed ranges, fresh game state each). Forcing a full re-run to fix one dimension wastes API credits and time.

## 2026-06-07 — Exponential backoff on Groq 429
**Decision:** Retry 429s up to 5 times (1/2/4/8/16s), then raise `RateLimitExhausted` which saves partial results.
**Why:** Uncaught 429 mid-run discarded all completed work. Backoff recovers from transient throttling; graceful degradation saves partial data.

## 2026-06-07 — Synergy ground truth = hand-crafted fixtures, not RNG drafts
**Decision:** Replaced RNG-drafted Act-1 decks in `run_synergy_eval` with fixed hand-crafted `_SYNERGY_FIXTURES` (initially 8, 2/archetype; each with 4–5 signature cards, a basic-Strike removal target, and an on-archetype best-pick offer). Removed the dead `_archetype_draft_fn`.
**Why:** Act-1 RNG decks are too small/RNG-limited to have a crisp archetype — only ~3/10 came out confidently labeled, all model/format combos collapsed to identical archetype_acc=0.333, and even "confident" labels were debatable. Fixed decks give deterministic, unambiguous ground truth.

## 2026-06-07 — Archetype labels decided by signature cards only (+ ambiguity)
**Decision:** Added `_classify_archetype_confident()` — the expert label counts only `_ARCHETYPE_PAYOFFS` signatures (+relics); a deck is labeled only if one archetype uniquely owns the most signatures, else `archetype_correct=None` (excluded from accuracy). Per-sample labels persisted in the JSON for audit.
**Why:** The broad `_ARCHETYPES` list miscategorized generic commons (Armaments/Headbutt → "Exhaust"), producing archetype_acc=0 on all combos with parse_ok=1.0 — the heuristic was wrong, not the models.

## 2026-06-07 — qwen3-32b dropped from the study
**Decision:** No reasoning model in the current model set; result files deleted. Revisit on a paid tier as future work.
**Why:** Infrastructural, not capability: Groq free's 6000 TPM truncates its `<think>` block (parse-failure cascade, 0% everywhere); OpenRouter free is ~30–80 tok/s and returned 402 when credits ran out. Reporting those 0%s as model performance would be wrong.

## 2026-06-10 — Relic lifecycle split: on_pickup vs register
**Decision:** `Relic.on_pickup(state)` = one-time effects at acquisition (max HP, energy/turn, deck mutations); `Relic.register(state)` = event subscriptions only, re-called at every combat start after the bus is cleared. `_obtain_relic()` calls both in order; 20 relics in `relics_full.py` moved their non-idempotent effects to `on_pickup`.
**Why:** With a single `register()` called per combat, non-idempotent effects (e.g. +max HP) stacked every combat across a run — same bug class as the EventBus stacking, one level up.

## 2026-06-10 — Powers reset per combat; poison bypasses block
**Decision:** `start_combat()` does `state.player.powers = {}`; relic-granted powers re-apply via COMBAT_START hooks. Poison ticks subtract HP directly, ignoring block.
**Why:** Per-combat powers (Demon Form, Flex) must not leak across fights; relic powers must not stack. Poison-through-block matches real Slay the Spire mechanics — required for Silent fidelity.

## 2026-06-10 — Silent as second character (same engine)
**Decision:** Added the full Silent card set (~73 cards), powers, pool, and 20 hand-crafted synergy fixtures (5/archetype: Poison/Shiv/Discard/Block). `new_game(seed, character)` factory; `make_card_for`/`card_pool_for`/`system_prompt` dispatch on character. Ironclad fixtures also expanded 8 → 20.
**Why:** Cheapest credible answer to the "too narrow" generalizability critique (see novelty doc): a second character reuses the whole engine while doubling the synergy fixture pool to 40 and enabling n≥20 synergy runs without repeating fixtures.

## 2026-06-10 — Multi-act runs with full-heal act transitions
**Decision:** `RunEvaluator.evaluate(state, n_acts)` plays acts 1→n; `_act_transition()` does a full heal + boss relic pick (LLM if `--llm-routing`, else greedy). `RunScore.acts_completed` / `total_floors` (16×n_acts) track cross-act progress.
**Why:** Act 1 alone caps the run-level horizon at ~16 decisions; Acts 1–3 triple it. Full heal between acts is a simplification (real StS heals partially) accepted to keep act difficulty independent.

## 2026-06-10 — Temperature + multi-seed CLI for paper-grade statistics
**Decision:** All evaluators take a `temperature` kwarg (`--temperature`); `--seeds 42 43 …` runs the benchmark per seed, saves per-seed outputs, and writes a combined JSON with mean ± std.
**Why:** The paper needs error bars. Synergy fixtures are deterministic — variance must come from sampling (temp>0, k completions/fixture) or seed sweeps; both are now one flag away.
