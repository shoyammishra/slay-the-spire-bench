# Engineering Handoff — slay-bench

*Written 2026-07-12 by the departing principal engineer (Claude Fable 5). The successor
principal engineer is **Claude Opus 4.8** (`.claude/agents/principal-engineer.md`). A new
engineer should be productive after reading this document plus the read-first list below.*

This document does NOT duplicate the project docs — it curates them, records the tacit
judgment that was never written down, and defines how work is delegated from here on.
Single source of truth stays where it already lives (see §2).

---

## 1. Project status snapshot (2026-07-12)

- **The full 5-family result matrix is COMPLETE.** 24 multi-seed aggregates
  (`results/*_seeds42_1042_2042_3042_4042.json`, 4 character×format combos × 6 model
  configs) are on this laptop and folded into all docs. Every remaining `—` cell in the
  CLAUDE.md tables is *intentional*, not pending. Nothing is running on the cluster.
- **Engine + harness are post-audit stable**: 5 full audits (2026-06-10 → 06-12) found and
  fixed ~130 bugs; **172/172 tests pass** (as of 2026-08-07); mock pipeline green for both characters × both
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
| 1 | `CLAUDE.md` | Active context, current result tables, invariants, gotchas, run commands |
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
the CLAUDE.md tables. CLAUDE.md's Active Context is a stack — new bullets on top, old
bullets kept as history with supersession markers (✅/⚠️/⛔).

## 3. System architecture (one screen)

Pure-Python Slay the Spire simulator + LLM benchmark harness. No services, no DB, no
frontend, no deployment — a research CLI. (`CLAUDE.md` Project Structure has the full
module map; `docs/design.md` the interfaces.)

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
  CLAUDE.md's cluster bullets.
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
- Generalizations across the matrix must be counted, not asserted: "structured ≥ raw for
  synergy removal" is true for **5 of 6 models** (deepseek-14b reverses) — state it that
  way. When a model's parse_ok < 1.0, its accuracies are conditioned on the parseable
  subset; say so.
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
  (Architecture Notes in CLAUDE.md); add a regression test in the matching test file;
  run all three test files directly (no pytest); run the mock pipeline both characters ×
  both formats; then apply §5.1 before any real run.
- **New synergy fixture**: obey the executable design-rule tests (added 2026-06-10) —
  unique signature ownership, on-archetype best pick, basic-card removal target; the
  harness rotates offer positions, don't hand-balance them.
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

| P | Task | Owner | Acceptance criteria |
|---|---|---|---|
| 1 | ~~**Horizon-collapse curve + cross-horizon normalization** in `visualize.py`~~ — **✅ DONE 2026-07-12** (Opus 4.8 agent; reviewed against §8, all criteria met). Formulas in decision_log 2026-07-12; PNGs in `results/horizon_collapse_*.png`; note the combat-baseline deviation (greedy ≈1.0, y-axis = "0 = non-planning floor") — caption implication for P6. **Anchor correction (same day, user-caught):** run anchor is now MEASURED per character (`scripts/greedy_baseline.py` → `results/greedy_baseline_*.json`; IC .780 ≈ the old note, Silent .704 lower); Silent run edge was partly an anchor artifact (structured lifts to ≤.13, raw mistral/qwen genuinely floored); 134 tests | done | Met: normalization documented; one line per model; renders from the 24 aggregates; 133 tests pass; both caveats addressed |
| 2 | ~~**Fable 5 lit note** into `docs/draft.md` Related Work~~ — **✅ DONE 2026-07-12** (Opus 4.8 agent; 4 insertions in draft.md + Anthropic entry in `novelty_and_related_work.md` §10) | done | Met: domain validation cited; floor-vs-ceiling complement framing; ~3×-with-memory as corroboration-only; memory = future-work only |
| 3 | ~~**Run-level discriminability decision**~~ — **✅ DECIDED 2026-07-12** (decision_log P3 entry): **reframe run as the shared collapse floor (Option B)**; `--acts 3` = conditional appendix probe gated on M3b frontier results also flooring at 1 act, preceded by an Act-2/3 engine audit + smoke (~12h/cell; full matrix would be ~72–144 GPU-h). roadmap step 6 re-tagged | done | Met: decision + trade-offs + revisit trigger (M3b) recorded; no compute spent |
| 4 | **M3b frontier runs** (Claude/GPT via professor's channel) — fills the frontier gap; expected to bend the collapse curve. **⚠️ Budget protocol registered 2026-07-13 (decision_log): matched-8k first, escalate only on measured truncation** — the smoke test MUST read `parse_fail_truncated`/`truncation_errors` before any full cell (the DeepSeek budget-bound confound now instrumented); reasoning APIs need their decoupled budgets configured (Claude thinking budget separate from answer tokens; OpenAI `max_completion_tokens` covers reasoning too). **Scope added 2026-07-14 (review-driven, decision_log): fold-in includes a cross-benchmark correlation** — per-model collapse points vs *published* external agent-benchmark scores (GAIA/SWE-Bench/WebArena…); we run nothing external, n≈8–10 models, reported as directional only | Opus 4.8 + user (credentials) | Same harness, same seeds, all 4 combos; provider class may need adding to `benchmark.py`; smoke truncation check ≈ 0 (or the raised-budget condition added + both reported); correlation table with the directional caveat |
| 4b | ~~**Statistical rigor pass**~~ — **✅ DONE 2026-08-07.** `scripts/stats_rigor.py` (models discovered from filenames → M3b rows join with no code change) + `tests/test_stats.py` (26 known-answer tests, **172/172 total**) + `docs/stats_report.md` (committed) + `results/stats/stats_rigor.json`. Methods/limitations: decision_log 2026-08-07 (later); numbers: experiment_log 2026-08-07 (later); wording impact: findings 📊 section. **⚠️ Registered power ceiling: exact sign-flip over 5 seed pairs ⇒ min attainable two-sided p per combo = 0.0625**, so inference rests on the pooled stratified test + sample-level McNemar. **Corrected two published claims** — "combat/run format-insensitive" (ceiling artifact; format reaches combat hp_ratio, 10/12 strata) and qwen3-32b's run lift (run-seed-matched greedy = .04/12.76, not .01/12.48). **Delivered the paper's cleanest number:** between-model η² share turn .83 / combat .89 / synergy .51 / **run .02**. **Re-run it as step 1 of the M3b fold-in.** | done | Met: reusable script (not a notebook); CIs + effect sizes on every headline claim; paired format test with p-values (+ direction test); no published mean changed |
| 4c | **Open-model ladder, top rung: Qwen3-235B-A22B-FP8** (pre-M3b; ladder registered decision_log 2026-07-23 §1). **STAGED + PREFETCHED 2026-08-07; SERVING SOLVED 2026-08-08, smoke still unmeasured** — 239.1 GB verified byte-exact on scratch; two-stage launcher `cluster/sharanga_submit_235b.sh {smoke\|matrix}`. **FlashInfer JIT is structurally unbuildable here and blocks TP>1 / FP8 / MoE paths; the disable-set is now baked into both sbatch files** (decision_log 2026-08-08) — server comes up in 160 s, ~24 GiB/GPU spare. **No wall-time number yet:** a 2 h interactive session expired mid-pass, so the smoke must be re-run **in batch**. **⚠️ Not a repeat of the 32B run: TP=2 under the 3-GPU cap ⇒ combos are STRICTLY SEQUENTIAL** (≈4 × per-combo vs a 96 h MaxTime), so the smoke gates a *scope* decision. Read in order: wall time → truncation counters → score sanity; scope-down ladder is run-level first (`N_RUN=0`), then one character, then one format | user (runs it) + Opus 5 (sizing/fold-in) | Smoke passes with truncation ≈ 0 and a wall time implying ≤96 h/combo before stage 2; on retrieval re-run `stats_rigor.py` (auto-discovers the new model) then fold into experiment_log/findings/tables |
| 5 | Complete qwen3-32b non-synergy dims (needs vLLM 0.8.x env) — optional | Opus 4.8 | Only if P3/P4 make the curve need it |
| 5b | ~~**Run the parse probe** and fold the truncation-vs-malformed answer into findings + the paper's DeepSeek framing~~ — **✅ DONE 2026-07-13.** Four cells ran (deepseek-7b IC + 14b Silent, both formats): **`parse_fail_truncated/parse_fail_n` = 1.0 in every cell** ⇒ verdict = **budget-bound deliberation** (models exhaust the 8k budget mid-`<think>`; zero malformed-but-complete outputs). Folded into experiment_log (2026-07-13), findings (probe section + finding-2 supersession), draft.md (finding 3 mechanism + §5.4), report_matrix.html. Probe caveats recorded (seed 42 only, combat n=3); diagnostic cells kept OUT of matrix tables. The **"invalid-action errors"** reporting rule for the matrix metric remains in force | done | Met: answer recorded as budget-bound with n/seed caveat; no diagnostic scores in matrix tables |
| 6 | **Paper assembly** for a D&B-track submission; citations need venue/year completion. ~~**Scope added 2026-07-12 (found during P2): full draft-refresh pass**~~ — **✅ REFRESH SUBTASK DONE 2026-07-12** (draft.md: new matrix-accurate Abstract + superseded-claims box, "contributes" numbers updated, §4–5 results-summary skeleton added with the run-as-collapse-floor framing + horizon-figure caption language ("0 = non-planning floor"; combat = `win×min(1,hp)` so greedy ≈ 1.0), venue ladder + gaps re-ranked — no stale pilot claims remain). **Also delivered: `docs/report_matrix.html`** — standalone professor-facing results report (both horizon-collapse PNGs base64-embedded, full matrix tables, 5 findings, honest caveats, M3b ask; supersedes the pilot `docs/report.html`). **REMAINING P6 scope:** full paper assembly (Sections 1, 3–6 prose from the draft.md skeleton) + BibTeX completion — best done after P4/M3b lands. **Scope extended 2026-07-14 (review-driven, decision_log + `docs/review_2026-07-14.md` §2.3):** (a) explicit oracle-quality limitations taxonomy (turn exact → combat greedy → synergy expert → run baseline); (b) three named rebuttal arguments — difficulty≠horizon (dissociation pattern: deepseek-7b execution collapse vs matrix-2nd synergy removal, qwen3-32b bends only at synergy), run collapse ≠ context accumulation (memoryless harness, bounded prompts), budget-bound deliberation as mechanism (promote from footnote to first-class finding); (c) claim-scoping pass — every general claim reads "in this benchmark" until M3b/second-domain evidence; (d) explicit memory/tools scope-out defense (floor vs ceiling); (e) positioning vs FDG-2024/Orak LEADS the paper (the review estimates 45% of reviewers open with "already done") | Opus 4.8 (writing) + Sonnet (formatting/BibTeX mechanics) | Novelty framing follows `novelty_and_related_work.md` + §5.4 honesty rules; no stale pilot claims survive the refresh; all five 2026-07-14 scope items present; P4b numbers used wherever stats are cited |

## 7. Risks & failure modes

- **Results exist only on this laptop.** `results/` is gitignored; cluster `~/scratch`
  purges after 30 days. The 24 aggregates are the project's crown jewels — back them up
  (private location, NOT this public repo) before any machine change.
- **Public-repo leak** (invariant 8). GitHub may still serve old commit SHA `74cf854`
  by direct URL (internal RFC1918 IP only; low risk; purge via GitHub Support if desired).
- **Cluster access is professor-granted** and semester-bound; assume it can vanish —
  batch any remaining GPU work.
- **Fake-precision risk**: n=20 × 5 seeds is paper-grade for this scope, but any new
  claim needs its own power check (12.5pp steps at n=8 was the old trap).
- **No CI** (see §9): the 172 tests only run when someone runs them. Run all four files
  before every commit.

## 8. Review checklist (no merge without)

1. All 4 test files pass (**172 tests**: benchmark 48, combat 62, run 36, stats 26), run
   directly with `PYTHONIOENCODING=utf-8`.
2. Mock pipeline green: both characters × both formats.
3. §5.1 classification done: does this change invalidate data? If yes, re-baseline plan
   is written down first.
4. Security scan of the diff: no IP, no keys, no SOP contents, `.env` untouched.
5. Docs updated in the same change: decision_log (why), experiment_log (if a run),
   CLAUDE.md Active Context + tables (if numbers/status changed).
6. New behavior has a regression test; instrument changes have a degenerate-model check.

## 9. Technical debt & known limitations (accepted, documented)

- Documented design no-ops (intentional): Juzu Bracelet (event combats unimplemented),
  player REGENERATE (potions undrinkable by design), Mummified Hand permanence, string
  power keys ("Calm"/"enrage").
- No pytest, no CI/CD — tests are three directly-run files. Fine at this scale; add
  GitHub Actions only if contributors appear (mind the public repo + no secrets).
- Run-level dimension doesn't discriminate between current models (floor effect) — this
  is a *finding* to be framed, and P3's decision point.
- deepseek-7b synergy accuracies conditioned on parse_ok .69–.92.
- qwen3-32b has synergy-only coverage (deliberate: the horizon where it separates).
- `visualize.py` predates the matrix — P1 modernizes it.

## 10. Delegation & the agent roster

**Model policy (permanent, also recorded at user level in `~/.claude/CLAUDE.md`):**
all reasoning-bearing work — architecture, research, debugging, security, performance,
review, planning, integration, non-trivial implementation — goes to **Opus 4.8**
(`model: opus`). **Sonnet** only for mechanical work: formatting, table transcription,
BibTeX cleanup, boilerplate moves. Target allocation ≈ 90–95% Opus / 5–10% Sonnet.
Never assign judgment work to Sonnet.

Roster (`.claude/agents/` — committed with the repo, so it travels with the project):

| Agent | Model | Mission |
|---|---|---|
| `principal-engineer` | opus | Successor lead; owns decisions, plans, integration; enforces §5 + §8 |
| `engine-auditor` | opus | Adversarial audits of engine/harness fidelity (the 5-audit tradition) |
| `benchmark-operator` | opus | Runs/cluster ops: sbatch, smoke-first sizing, result retrieval + fold-in |
| `security-reviewer` | opus | Public-repo hygiene: diff/history scans for keys, IPs, SOP content |
| `paper-writer` | opus | draft.md, novelty framing, honesty rules (§5.4) |
| `docs-formatter` | sonnet | Mechanical doc/table/BibTeX formatting only; escalates anything judgment-shaped |

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
