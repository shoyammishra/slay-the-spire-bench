# Engineering Handoff — slay-bench

*Written 2026-07-12 by the departing principal engineer (Claude Fable 5). Migrated to
the Codex-native agent roster on 2026-08-16; `.codex/agents/principal-engineer.toml` is
the active successor role. A new engineer should be productive after reading this
document plus the read-first list below.*

This document does NOT duplicate the project docs — it curates them, records the tacit
judgment that was never written down, and defines how work is delegated from here on.
Single source of truth stays where it already lives (see §2).

---

## 1. Project status snapshot (2026-07-12)

- **Construct supersession (2026-08-30):** a repository-wide adversarial research
  audit rejects the four-task “planning horizon” interpretation. The tasks are now
  operation profiles; the horizon curve, radar, and overall scalar fail closed.
  `docs/research_audit/` contains the 15-file review/rebuild package.
- **P0 implementation:** future result schema 2.0 records provenance and per-dimension
  merge sources; a compute-free dictionary policy solves 120/120 fixed synergy cases;
  `controlled-decision-horizon-v1` infrastructure is implemented and smoke-tested.
  No model inference has run; all controlled-H results are PENDING EXPERIMENT.

- **Active supersession (2026-08-30):** the open-model matrix now has 28 canonical
  aggregates (7 configurations × 2 characters × 2 formats), including the complete
  Qwen3-235B rung. Its strongest relative gain over Qwen3-32B is card selection
  (all 4 cells; 19/20 seed pairs), not a uniform horizon extension. Removal-v1 is
  quarantined because every fixture's expert target is `Strike`; raw removal fields are
  diagnostic only and the regenerated synergy composite uses archetype + best pick.

- **Superseded snapshot:** the then-current 5-family result matrix was complete. 24 multi-seed aggregates
  (`results/*_seeds42_1042_2042_3042_4042.json`, 4 character×format combos × 6 model
  configs) are on this laptop and folded into all docs. Every remaining `—` cell in the
  legacy result tables was *intentional*, not pending. Nothing is running on the cluster.
- **Engine + harness are post-audit stable**: 5 full audits (2026-06-10 → 06-12) found and
  fixed ~130 bugs; **180/180 tests pass** (as of 2026-08-30); mock pipeline green for both characters × both
  formats.
- **The two D&B-blocking gaps from the novelty review are closed** (≥3 model families +
  a reasoning model).
- **Open work** is paper-side, not harness-side: see §6 backlog. The top item
  (horizon-collapse curve in `visualize.py`) was delegated to an Opus 4.8 agent on
  2026-07-12.
- Uncommitted doc changes may exist in the working tree; the user triggers commits with
  the word "checkpoint" (protocol in the user-level memory store).

## 2. Read-first order & where truth lives

| Order | File | What it is authoritative for |
|---|---|---|
| 1 | `AGENTS.md` | Active routing, current milestone, invariants, commands, safety |
| 2 | `docs/handoff.md` | (this) judgment, delegation, backlog, risks |
| 3 | `docs/design.md` | Architecture, interfaces, invariants in depth |
| 4 | `docs/decision_log.md` | Why every design decision was made (rationale record) |
| 5 | `docs/experiment_log.md` | Every run: config, numbers, failures. 2026-06-22 section = current matrix |
| 6 | `docs/findings.md` | Interpretations/hypotheses over the numbers |
| 6b | `docs/stats_report.md` | **Uncertainty** on every headline number: CIs, effect sizes, paired format tests, variance decomposition, claim verdicts (regenerate with `scripts/stats_rigor.py`) |
| 7 | `docs/novelty_and_related_work.md` | What's novel vs FDG-2024/Orak; D&B viability |
| 7b | `docs/review_2026-07-14.md` | External expert review (ADOPTED evaluation baseline for paper-side decisions) + response + derived priorities |
| 8 | `docs/roadmap.md` | Milestones M3a/M3b, run order |
| 9 | `docs/draft.md` | Paper draft (Related Work drafted) |
| 10 | `docs/bug_audit_2026-06-*.md` | Per-bug specs + fix notes from the 5 audits |

Rule: **project state goes in these files, never only in chat.** If a decision is made,
it goes in `decision_log.md`; if a run happens, `experiment_log.md`; if a number changes,
`docs/handoff.md` when active state changes. Detailed chronology belongs in the decision
and experiment logs with supersession markers (✅/⚠️/⛔), not in `AGENTS.md`.

## 3. System architecture (one screen)

Pure-Python Slay the Spire simulator + LLM benchmark harness. No services, no DB, no
frontend, no deployment — a research CLI. (`AGENTS.md` has the module map;
`docs/design.md` has the interfaces.)

- **Engine** (`combat.py`, `cards*.py`, `enemies*.py`, `relics*.py`, `powers.py`,
  `map_gen.py`, `run_loop.py`, `rng.py`): deterministic game simulation. Same seed →
  identical map/enemies/draws/rewards. 9 independent Java-compatible LCG streams.
  EventBus pub/sub for relic/power hooks; bus cleared at every `start_combat`.
- **Harness** (`benchmark.py`, `prompt_builder.py`, `run_benchmark.py`): 4 evaluators
  (turn/combat/synergy/run), each with its own ground truth (exhaustive oracle / greedy
  bot / 40 hand-crafted fixtures / survival). Provider abstraction: groq, openrouter,
  local (any OpenAI-compatible endpoint — this is how cluster vLLM runs work), mock.
- **Cluster toolkit** (`cluster/`): one Slurm job = vLLM serves a model + runs
  `run_benchmark.py --provider local` against it. All the version/QOS gotchas are in
  the newest handoff, decision-log, and experiment-log entries.
- **Output contract**: `results/<model>[_silent]_<format>_seed<N>.json/.txt/.png`
  (+ `_seeds…` aggregates for multi-seed). Overwrite-by-config, no timestamps. Gitignored.

## 4. Non-negotiable invariants

These have each caused (or fixed) real data-invalidating bugs. Violating any of them
invalidates results silently.

1. **Energy is deducted in exactly one place** — `play_card()` in `combat.py`. Cards
   never deduct their own energy.
2. **Card membership/removal is by object identity, never `__eq__`.** `Card` is a
   dataclass; equality matches twins. Three separate audits found vanish/duplicate/replay
   bugs from `card in pile` / `pile.remove(card)`. Use `_remove_identical` /
   `any(c is card …)`.
3. **The EventBus is cleared at every combat start.** Handler accumulation once made an
   8B model immortal (fake 100% survival).
4. **Prompt bytes are part of the instrument.** Any change to prompt text, fixture decks,
   or state rendering makes new numbers non-comparable to old ones (§5.1).
5. **Multi-seed bases must be ≥1000 apart** (e.g. `42 1042 2042 …`). Per-sample seeds are
   contiguous from each base; adjacent bases share 19/20 samples → fake std≈0.
6. **Real runs use `.venv\Scripts\python.exe`.** System Python lacks groq/dotenv/
   matplotlib and dies instantly. Tests/mock runs work on either.
7. **A running process uses startup code.** Editing `benchmark.py` mid-run does nothing;
   relaunch (use `--only` to redo one dimension — others merge from disk).
8. **Security (public repo):** never commit `.env` (real Groq+OpenRouter keys), the CSIS
   cluster login IP, support contacts, or the SOP PDF. Cluster files use
   `<login-node-ip>`; the real IP is substituted locally only. This was violated once
   (2026-06-12), caught, and purged from all git history — do not repeat.
9. **Illegal plays score 0**; parse failures are scored as failures, never silently
   dropped (except where explicitly conditioned, e.g. deepseek-7b synergy — always state
   the parse_ok caveat when reporting).
10. **Windows consoles:** set `PYTHONIOENCODING=utf-8` before running test files or the
    box-drawing prints spuriously crash 2 tests.

## 5. Externalized engineering judgment

This is the section that exists nowhere else. It is the decision *procedure* I used,
written down so the successor doesn't have to rediscover it.

### 5.1 Data-validity doctrine

The core asset of this project is comparability of numbers. A result is invalidated by:
- any engine change that alters combat dynamics (damage, block, debuff timing, enemy AI),
- any prompt-byte change (system prompt, state rendering, fixture contents/offers),
- any scoring change (oracle, legality rules, aggregation keys).

Procedure before merging ANY engine/harness change: classify it against the three rows
above; if it hits one, decide explicitly which dimensions need re-baselining and record
that in the merge notes/decision_log *before* spending compute. History shows the cost of
skipping this: three full re-baselines. Synergy survives engine changes that don't touch
its fixtures or prompts; turn/combat almost never survive engine changes; run never does.

### 5.2 Instrument-first skepticism ("too good = bug")

Every headline artifact in this project's history was an instrument bug, not a model
property: >100% hp_ratio (Burning Blood healed the LLM but not the bot), 100% survival at
full HP (EventBus stacking), std=0 across seeds (byte-identical prompts), 75–100%
card-pick from an always-answer-"0" model (positional confound), oracle understating the
optimum (6-card cap on Silent).

**Rule: any result at a boundary (1.0, 0.0, std≈0) or that beats the oracle/baseline is
an instrument bug until a per-sample audit proves otherwise.** The audit method that
works: read the per-sample JSON records line-by-line (they persist `expert_*`/`model_*`
fields for exactly this reason), and ask "what would a degenerate model (constant answer,
empty answer) score on this instrument?" If a degenerate strategy scores above chance,
the instrument is biased.

### 5.3 Compute-cost ordering

Always run cheapest → most expensive: mock → smoke (tiny full pass, measure tok/s, size
n from wall-time) → turn/combat → synergy → run-level. Run-level is dozens-to-hundreds
of stateful calls per sample; it goes last, only after the pipeline is proven on that
exact model/version. Never launch a paper-grade run without a smoke test on the same
serving stack (the Gemma-3-12B failure — model loads fine, then buries the JSON in
chain-of-thought — is only catchable by smoke).

### 5.4 Reporting honesty rules

- Run-level is a **floor effect** (~everyone ≈ greedy ~12.5 floors): report
  avg_floors/progress, phrase as "on par with greedy, NOT beating." Never resurrect the
  pre-fix 13.4-floors/20–40% numbers — that data is invalid.
- Frame the name-vs-play dissociation as **confirming and quantifying FDG 2024**
  (Bateni & Whitehead), never as a discovery — a reviewer finds that paper in minutes.
- Generalizations across the matrix must be counted, not asserted. Removal-v1 is not a
  capability metric: all 40 expert targets are `Strike`, so a constant answer scores
  100%. Exclude it from claims and composites. When a model's parse_ok < 1.0, valid
  accuracies are conditioned on the parseable subset; say so.
- Old numbers never get silently blended with new ones. When an instrument changes, the
  old files are deleted or marked ⛔ in docs (see the 2026-06-14 Groq-file deletion).
- **(added 2026-08-07, P4b)** Statistics have their own honesty rules, all enforced by
  `scripts/stats_rigor.py`: (a) every per-combo p-value travels with **"min attainable
  p = 0.0625 at 5 seed pairs"** — the design cannot reach α=0.05 per combo, so never present
  a per-combo null as evidence of no effect; (b) a pooled effect is **general** only if the
  magnitude test *and* the direction (sign) test agree — otherwise say **model-dependent**;
  (c) *insensitivity* claims must pass an **equivalence** test (TOST, ±0.05 margin), never be
  inferred from a non-significant result; (d) run-level comparisons against greedy use the
  **run-seed-matched** anchor (greedy subset to the exact seeds the model played), not the
  100-run global average; (e) before believing a "format-insensitive" or "no difference"
  result, check whether a **ceiling** is removing the variance.

### 5.5 Model/serving selection heuristics (cluster)

- vLLM version ladder is pinned by the CUDA 12.8 driver: 0.6.6 works (no Qwen3),
  0.8.x adds Qwen3, 0.22+ needs CUDA 13 (won't work). Check this FIRST when adding a model.
- A candidate model must follow the terse-JSON contract; verbose CoT instruct models
  (Gemma-3-12B) burn 3 min/call and parse to ''. Reasoning models are worth it only when
  self-hosted (free-tier TPM truncates mid-`<think>` → 0% everywhere, the qwen3 story).
- QOS caps wall-time below partition limits — submit with explicit `sbatch --time=…`.

### 5.6 How to modify things safely (recipes)

- **New card/relic/enemy**: follow the EventBus + on_pickup/register split
  (`docs/design.md`); add a regression test in the matching test file;
  run all four test files directly (no pytest); run the mock pipeline both characters ×
  both formats; then apply §5.1 before any real run.
- **New synergy fixture**: obey the executable design-rule tests — unique signature
  ownership and an on-archetype best pick; the harness rotates offer positions. Do not
  add removal-v2 by editing the v1 fixture set in place: targets and candidate positions
  must vary and be balanced, constant-answer baselines must stay at chance, metadata must
  persist per sample, and the shared synergy prompt requires a full versioned re-baseline.
- **New model**: add sbatch overrides (`HF_REPO`/`SERVED_NAME`/`CONDA_ENV`), smoke first
  (§5.3), gated models need `HF_TOKEN`. **Verify the prefetch with
  `cluster/verify_prefetch.py <repo>` before submitting** — the sbatch guards only check the
  cache directory *exists*, and `du` is not a completeness test (Xet dedup made a complete
  239.1 GB model read as 212 GiB). **Any model needing TP>1 loses the parallel-combo
  strategy** under the 3-GPU per-user cap: check `weights_GB` vs `141 × cap` first, because
  sequential combos change the feasible scope, not just the schedule. **Walltime must strictly
  exceed the health-wait budget** or a cold start alone can consume the allocation.
- **New dimension/metric**: it must ship with its own ground-truth oracle and a
  degenerate-model analysis (§5.2), or it doesn't ship.

## 6. Backlog (priority order, with owners)

**2026-08-30 P4c status supersession:** recovery jobs `329871`–`329873` completed the
missing Silent/raw phases. All 20 per-seed artifacts and four canonical aggregates are on
the laptop, the null Silent/raw run aggregate was regenerated from its complete per-seed
blocks, the full per-sample audit passed, statistics and horizon figures were regenerated,
and the results are folded into the authoritative docs. The earlier recovery instructions
and three-cell quarantine are historical only.

| P | Task | Owner | Acceptance criteria |
|---|---|---|---|
| 1 | ~~**Horizon-collapse curve + cross-horizon normalization** in `visualize.py`~~ — **✅ DONE 2026-07-12** (Opus 4.8 agent; reviewed against §8, all criteria met). Formulas in decision_log 2026-07-12; PNGs in `results/horizon_collapse_*.png`; note the combat-baseline deviation (greedy ≈1.0, y-axis = "0 = non-planning floor") — caption implication for P6. **Anchor correction (same day, user-caught):** run anchor is now MEASURED per character (`scripts/greedy_baseline.py` → `results/greedy_baseline_*.json`; IC .780 ≈ the old note, Silent .704 lower); Silent run edge was partly an anchor artifact (structured lifts to ≤.13, raw mistral/qwen genuinely floored); 134 tests | done | Met: normalization documented; one line per model; renders from the 24 aggregates; 133 tests pass; both caveats addressed |
| 2 | ~~**Fable 5 lit note** into `docs/draft.md` Related Work~~ — **✅ DONE 2026-07-12** (Opus 4.8 agent; 4 insertions in draft.md + Anthropic entry in `novelty_and_related_work.md` §10) | done | Met: domain validation cited; floor-vs-ceiling complement framing; ~3×-with-memory as corroboration-only; memory = future-work only |
| 3 | ~~**Run-level discriminability decision**~~ — **✅ DECIDED 2026-07-12** (decision_log P3 entry): **reframe run as the shared collapse floor (Option B)**; `--acts 3` = conditional appendix probe gated on M3b frontier results also flooring at 1 act, preceded by an Act-2/3 engine audit + smoke (~12h/cell; full matrix would be ~72–144 GPU-h). roadmap step 6 re-tagged | done | Met: decision + trade-offs + revisit trigger (M3b) recorded; no compute spent |
| 4 | **M3b frontier runs** (Claude/GPT via professor's channel) — fills the frontier gap; expected to bend the collapse curve. **⚠️ Budget protocol registered 2026-07-13 (decision_log): matched-8k first, escalate only on measured truncation** — the smoke test MUST read `parse_fail_truncated`/`truncation_errors` before any full cell (the DeepSeek budget-bound confound now instrumented); reasoning APIs need their decoupled budgets configured (Claude thinking budget separate from answer tokens; OpenAI `max_completion_tokens` covers reasoning too). **Scope added 2026-07-14 (review-driven, decision_log): fold-in includes a cross-benchmark correlation** — per-model collapse points vs *published* external agent-benchmark scores (GAIA/SWE-Bench/WebArena…); we run nothing external, n≈8–10 models, reported as directional only | `benchmark-operator` + user (credentials/spend) | Same harness, same seeds, all 4 combos; provider class may need adding to `benchmark.py`; smoke truncation check ≈ 0 (or the raised-budget condition added + both reported); correlation table with the directional caveat |
| 4b | ~~**Statistical rigor pass**~~ — **✅ REFRESHED 2026-08-30.** `scripts/stats_rigor.py` discovers 7 configurations/28 cells and verifies 70/70 structured/raw fixture pairings. `tests/test_stats.py` has 27 known-answer tests (**180/180 repository total**). Removal-v1 is quarantined. The old cross-task η² horizon claim is `NOT-IDENTIFIED`: run uses only three balanced `N_RUN=20` models and every task/scale differs. **⚠️ Power ceiling:** five seed pairs imply min attainable two-sided per-combo p=.0625. | done | Met: reusable script; CIs + effect sizes; paired tests; removal quarantine enforced; Qwen3-235B folded in without blending run tiers |
| 4c | ~~**Open-model ladder, top rung: Qwen3-235B-A22B-FP8**~~ — **✅ COMPLETE 2026-08-30.** All four cells, 20 per-seed artifacts, and 400/400/400/100 observations recovered and audited. Silent/raw's canonical null run block was reaggregated correctly. Relative to Qwen3-32B, card pick improves in all four cells and 19/20 seed pairs; other horizons are mixed or saturated. Parse/truncation counts, matched-greedy floor comparisons, MoE-vs-dense caveat, and missing-original-stdout limitation are recorded in the 2026-08-30 experiment/decision entries. | complete | Met: no landed work recomputed; exact sample inventory and seed audit; canonical aggregate; statistics/figures/docs refreshed; run remains `N_RUN=5` floor-estimate tier |
| 4d | **Removal-v2 redesign and synergy re-baseline** — only if strategic pruning is needed as a paper claim. Version the instrument; vary/balance expert targets and candidate positions; persist target metadata; demonstrate constant-answer chance baselines; then rerun all synergy cells because the prompt is joint. Never mix v1 and v2. | `engine-auditor` + `benchmark-operator` + user (compute) | Design decision and degenerate tests before spend; exact-stack smoke; full versioned matrix; statistics and figures regenerated |
| 5 | ~~Complete qwen3-32b non-synergy dimensions~~ — **✅ DONE 2026-08-07; full four-dimension matrix retrieved, audited, and folded in.** | complete | See experiment log 2026-08-07 |
| 5b | ~~**Run the parse probe** and fold the truncation-vs-malformed answer into findings + the paper's DeepSeek framing~~ — **✅ DONE 2026-07-13.** Four cells ran (deepseek-7b IC + 14b Silent, both formats): **`parse_fail_truncated/parse_fail_n` = 1.0 in every cell** ⇒ verdict = **budget-bound deliberation** (models exhaust the 8k budget mid-`<think>`; zero malformed-but-complete outputs). Folded into experiment_log (2026-07-13), findings (probe section + finding-2 supersession), draft.md (finding 3 mechanism + §5.4), report_matrix.html. Probe caveats recorded (seed 42 only, combat n=3); diagnostic cells kept OUT of matrix tables. The **"invalid-action errors"** reporting rule for the matrix metric remains in force | done | Met: answer recorded as budget-bound with n/seed caveat; no diagnostic scores in matrix tables |
| 6 | **Paper assembly** for a D&B-track submission; citations need venue/year completion. The 2026-08-30 fold-in adds the complete Qwen3-235B selective-capability result and removes all removal-v1 claims/composites. `docs/report_matrix.html` is the professor-facing report; `docs/draft.md` is the paper skeleton. **REMAINING P6 scope:** full Sections 1 and 3–6 prose, BibTeX completion, and a final claim-scope pass. Preserve the run-as-collapse-floor framing, explicit oracle-quality taxonomy, difficulty≠horizon evidence (Qwen3-235B card-selection gains without uniform long-horizon gains), memoryless-run defense, and budget-bound-deliberation mechanism. | `paper-writer` + `docs-formatter` for mechanical work | No removal-v1 capability claims; current 7-configuration statistics and figures; all caveats attached; novelty framing follows related-work and review docs |

**2026-08-16 ownership supersession:** historical Opus/Sonnet labels in completed rows
record who performed that work. For remaining work, use the Codex roles in §10:
`paper-writer` owns judgment-bearing paper work and `docs-formatter` handles only exact
mechanical formatting or transcription.

## 7. Risks & failure modes

- **Results exist only on this laptop.** `results/` is gitignored; cluster `~/scratch`
  purges after 30 days. The 28 aggregates are the project's crown jewels — back them up
  (private location, NOT this public repo) before any machine change.
- **Public-repo leak** (invariant 8). GitHub may still serve old commit SHA `74cf854`
  by direct URL (internal RFC1918 IP only; low risk; purge via GitHub Support if desired).
- **Cluster access is professor-granted** and semester-bound; assume it can vanish —
  batch any remaining GPU work.
- **Fake-precision risk**: n=20 × 5 seeds is paper-grade for this scope, but any new
  claim needs its own power check (12.5pp steps at n=8 was the old trap).
- **No CI** (see §9): the 180 tests only run when someone runs them. Run all four files
  before every commit.

## 8. Review checklist (no merge without)

1. All 4 test files pass (**180 tests**: benchmark 55, combat 62, run 36, stats 27), run
   directly with `PYTHONIOENCODING=utf-8`.
2. Mock pipeline green: both characters × both formats.
3. §5.1 classification done: does this change invalidate data? If yes, re-baseline plan
   is written down first.
4. Security scan of the diff: no IP, no keys, no SOP contents, `.env` untouched.
5. Docs updated in the same change: decision_log (why), experiment_log (if a run),
   handoff/experiment/finding docs as applicable (if numbers or status changed).
6. New behavior has a regression test; instrument changes have a degenerate-model check.

## 9. Technical debt & known limitations (accepted, documented)

- Documented design no-ops (intentional): Juzu Bracelet (event combats unimplemented),
  player REGENERATE (potions undrinkable by design), Mummified Hand permanence, string
  power keys ("Calm"/"enrage").
- No pytest, no CI/CD — tests are four directly-run files. Fine at this scale; add
  GitHub Actions only if contributors appear (mind the public repo + no secrets).
- Run-level dimension doesn't discriminate between current models (floor effect) — this
  is a *finding* to be framed, and P3's decision point.
- deepseek-7b synergy accuracies conditioned on parse_ok .69–.92.
- Qwen3 run cells are `N_RUN=5` floor estimates and must not be pooled with the
  balanced `N_RUN=20` rows.
- Removal-v1 is a known invalid instrument (universal `Strike` target); a valid
  removal-v2 requires full versioned synergy re-baselining.
- `visualize.py` is matrix-aware as of 2026-08-30; removal is excluded from its
  synergy composites and both horizon figures are current.

## 10. Delegation & the agent roster

**Capability policy (migrated 2026-08-16):** use a high-reasoning engineering agent for
architecture, research, debugging, security, performance, review, planning, integration,
and non-trivial implementation. Use the fast `docs-formatter` only for bounded mechanical
formatting, exact transcription, BibTeX cleanup, and verbatim moves.

Roster (`.codex/agents/` — project-scoped Codex agents):

| Agent | Mission |
|---|---|
| `principal-engineer` | Successor lead; owns decisions, plans, integration; enforces §5 + §8 |
| `engine-auditor` | Adversarial audits of engine/harness fidelity (the 5-audit tradition) |
| `benchmark-operator` | Runs/cluster ops: sbatch, smoke-first sizing, result retrieval + fold-in |
| `security-reviewer` | Public-repo hygiene: diff/history scans for keys, IPs, SOP content |
| `paper-writer` | draft.md, novelty framing, honesty rules (§5.4) |
| `docs-formatter` | Mechanical doc/table/BibTeX formatting only; escalates judgment-shaped work |

This roster is right-sized on purpose: the classic org chart (frontend, infra, platform,
release teams…) maps to nothing here — a Python research CLI has no frontend, no deploys,
no fleet. If the project grows a web leaderboard or a service, add agents then; don't
pre-create empty roles.

Every delegated task must carry: objective, context pointer (which docs/§), acceptance
criteria, test requirement, and which docs to update. Review loop: principal-engineer
reviews all work against §8 before it's considered done; security-reviewer sees every
diff that touches `cluster/`, docs mentioning infrastructure, or anything committed.

## 11. Lessons learned (the short version)

1. The instrument lies before the model does — audit the harness, not the leaderboard.
2. Determinism is the product: seeds, oracles, byte-stable prompts. Guard them jealously.
3. Buy information cheapest-first: a 95-second smoke test has repeatedly saved multi-hour
   GPU jobs.
4. Write the decision down when you make it, not when you remember it — the decision_log
   is why this handoff was possible at all.
5. Honest framing beats grand claims: "confirming FDG 2024, quantified across horizons"
   survives review; "we discovered it" does not.
