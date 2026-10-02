# NAACL 2027 (ARR October 2026) paper plan

**Established:** 2026-10-03. **Authoritative for:** the ARR submission's scope, template,
writing rules, and the reader-orientation material the PTA reviewers asked for.

## Venue facts

| Item | Value |
|---|---|
| Submission | ACL Rolling Review, **2026-10-12 AoE** (long paper, 8 pages + unlimited references/appendix) |
| Reviews / meta-reviews | 2026-12-18 |
| Commit to NAACL | by 2026-12-23 |
| Decision / conference | 2027-02-10 / 2027-06-01..05, San Francisco |
| Required | `Limitations` section (does not count toward 8 pages), Responsible NLP checklist, every author registered as a reviewer by 2026-10-12, anonymized PDF (no public-repo link) |
| Template | `naacl/acl_latex.tex` + `naacl/acl.sty` (current acl-org style files, `[review]` option). The `naacl2021.*` files in the folder are the outdated 2021 style; do not use them. |

**ICML conflict.** ARR and ICML both forbid concurrent review. The paper is under ARR review
until meta-reviews arrive on 2026-12-18. On that date, choose: commit to NAACL, or withdraw from ARR and submit
to ICML 2027 (late January). See `submission_plan.md`.

## Writing rules

- Every section goes through the **paper-deslop** skill (`.claude/skills/paper-deslop/`, from
  `docs/paper-deslop.zip`; local only, not committed). It enforces:
  - no em/en dashes or semicolons as connectors;
  - none of the banned LLM vocabulary (delve, leverage, robust-as-praise, moreover, notably, ...);
  - sentences of 25 words or fewer where possible;
  - at most two or three "X, not Y" constructions per page;
  - one point per paragraph, stated first;
  - the non-expert test for the abstract and introduction: no raw metric values before
    they are defined, at most 2–3 numbers, every term defined at first use.
  
  Run `python .claude/skills/paper-deslop/scripts/check.py <section>.tex` on each section.
- Claim scope follows the evidence. The pre-registered results are confirmatory.
  Decomposition, robustness and encounter analyses are post hoc and labeled as such.
  Disclose the untargeted-Skill oracle defect with every v3 number.

## PTA reviewer requirement: a layman must understand the game

PTA Reviewer 1 gave clarity 1/5. The reasons were that the choice of Slay the Spire was not
motivated, the game terminology was not explained, and the use of a clone instead of the real
game was not justified. The NAACL paper therefore carries three things.

### 1. "Why this game" (introduction paragraph + one Method paragraph)

The argument, in order of weight:

1. **We can compute the right answer exactly.** Our question is whether a model uses a stated
   planning horizon. Answering it needs the provably best action for each horizon H in the
   same state. A turn-based card game with a deterministic, seeded simulator lets us find it
   by exhaustive search over at most about a dozen legal actions per step. Open-ended
   environments (web agents, text adventures, robotics) offer no such ground truth.
2. **The horizon changes the answer in natural states.** We did not construct puzzles.
   About half of the released fixtures were selected because their best move differs
   between H=1 and H=8. Investing now to gain later (applying a debuff before attacking,
   blocking before a big enemy hit) is the core of the game.
3. **The state fits in text.** The whole decision state (cards, energy, health, enemy
   intentions, draw order) serializes to about 1,000 tokens. The model does not need vision
   or tools.
4. **It is an established testbed for LLM agents.** Cite Bateni & Whitehead (FDG 2024), Orak
   (2025), and Anthropic's Fable 5 evaluation (2026).
5. **Familiarity is a known confound, and we test it.** Language models have read about this
   game. Name recognition could stand in for reasoning, so we run the `described` and
   `renamed` conditions (Amendment 6), which hold mechanics fixed and remove familiarity.

**Why a clone and not the real game.** The oracle has to copy a game state and branch from it
millions of times (budget: 2 million nodes per fixture and horizon). The commercial game runs on
the Java VM behind a modding interface, with no cheap state copying and no seeded replay of
every random stream. A Python reimplementation with 9 independent seeded random streams gives:
- exact replay and full observability for the oracle;
- a license-clean release;
- reproducible fixtures.

The cost is fidelity. Our engine deviates from the real game in recorded places (the
`real_game` notes in the effect table), and the paper must say so.

### 2. Glossary (box or table in Section 2; one line each)

| Term | Plain meaning |
|---|---|
| Card | One action the player can take; each costs energy |
| Energy | Budget per turn (3); unspent energy is lost |
| Hand / draw pile / discard pile | Cards available now / cards to come, in a known order / cards already used, shuffled back when the draw pile runs out |
| Exhaust | A card removed for the rest of the fight |
| HP | Health points; at 0 the fighter loses |
| Block | Temporary shield that absorbs damage until the owner's next turn |
| Attack / Skill / Power | Damage card / utility card (block, draw, debuff) / card with a lasting effect |
| Intent | The enemy's announced next move (for example "attack for 12"), visible to the player |
| Strength | +1 damage per hit for each point |
| Vulnerable | Takes 50% more attack damage |
| Weak | Deals 25% less attack damage |
| Poison | Loses that much HP each turn, decreasing by 1 |
| Turn / round | The player plays cards until ending the turn; then every enemy acts |
| Character | Ironclad (strength and self-sacrifice) or Silent (poison and card cycling); different card pools |
| Encounter | One fight. The fixtures come from 5: Lagavulin, Slime Boss, Hexaghost, Gremlin Nob, two Sentries |
| Relic | Passive item with a fixed rule (for example, heal 6 after a fight) |
| **Decision transition** | One choice: play one card or end the turn. H counts these |
| **Horizon H** | How many decision transitions ahead the stated goal is measured (1, 2, 4, 8) |
| **Fixture** | One frozen game state, with the exact best action computed for every H |
| **Sensitive / control fixture** | The best action differs / does not differ between H=1 and H=8 |
| **Oracle** | Exhaustive search giving the exact value of every legal action at each H |
| **H-blind baseline** | What a model would score if it ignored H (its H=1 answer, scored at H) |
| **Myopic choice** | Picking the action that is best for H=1 when the stated goal is H=8 |

### 3. One worked example figure (Figure 1)

The figure is a single sensitive fixture drawn as a small hand of cards with enemy intent:
- **H=1:** the best play is the highest immediate damage, for example Strike.
- **H=8:** the best play is the setup card, for example Bash (applies Vulnerable) or a Block card
  before the enemy's big attack, because it pays off within 8 transitions.

Annotate the oracle values under both horizons. Pick the fixture from the release by searching
for a short, readable hand. This figure carries the whole paper's question for a layman.

## Paper skeleton (8 pages)

1. **Introduction:** the question (do LLMs use a stated lookahead?), why existing benchmarks
   cannot isolate it, why this game (short version), and contributions.
2. **The game in one page:** glossary box and Figure 1.
3. **Controlled-H protocol:**
   - fixtures and the exact oracle;
   - the same-state H manipulation;
   - the DiD primary, the H-blind baseline and the gates;
   - pre-registration and amendments.
4. **Models and setup:**
   - 7–8 open models and 4 families: Qwen3 8B/14B/32B, Llama 3.1-8B/3.3-70B, Mistral-7B,
     Qwen2.5-7B, gpt-oss-120b;
   - pinned serving stacks.
5. **Results:**
   - the lookahead curve per model;
   - gpt-oss as the only model whose choices track H, with value flat and the effect
     control-driven;
   - nulls elsewhere;
   - the post hoc decomposition (greedy moves abandoned, not replaced by lookahead moves).
6. **Is it knowledge or planning?** The Amendment 6 described/renamed conditions.
7. **Robustness:** encounter leave-one-out and exclusion of the untargeted-Skill fixtures.
8. **Related work:**
   - planning benchmarks: PlanBench, NATURAL PLAN, TravelPlanner;
   - game benchmarks: Orak, GameBench, BALROG;
   - prior work on this game;
   - the shortcut audit, briefly, from PTA.
9. **Limitations:**
   - simulator fidelity and the engine bugs;
   - the oracle defect;
   - open models only;
   - one game;
   - post hoc analyses;
   - hardware and stack differences across runs.

**Appendix:** full per-model tables, prompts (base, described, renamed), the effect-reference
excerpt, amendment digests, and the engine-vs-game deviation list.
