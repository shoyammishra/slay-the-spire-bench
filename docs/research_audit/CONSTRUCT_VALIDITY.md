# Construct validity: what does Slay-Bench measure?

## Construct map

| Reported dimension | Observable operation | What is held fixed | Major nuisance variables | Defensible label |
|---|---|---|---|---|
| Turn | Select a card-index sequence | starter deck, Cultist, immediate damage objective | opening hand, parse/legal compliance | immediate-damage sequencing |
| Combat | Repeatedly choose play/end-turn | two enemy classes, starter deck | call count, exposure to parsing, greedy comparator, ceiling | short-combat execution |
| Synergy | Name one of four labels and choose 1/3 cards | handcrafted single-label decks | lexical knowledge, label dictionary, multiple-choice recognition | fixed-deck taxonomy recognition/card lookup |
| Run | Combat + reward calls inside scripted traversal | deterministic simulator and seed | routing/shop/event/rest scripts, long call chain, mechanics omissions | hybrid-policy Act-1 rollout |

These are useful operations. They are not levels of a single observed variable.

## Why “horizon” is not identified

A valid horizon experiment would manipulate the number of future transitions while
holding initial states, action vocabulary, observation, objective, oracle, model
agency, and score constant. Current Slay-Bench holds none of those constant across its
four dimensions. Task label and horizon are perfectly confounded.

The ordering is also contestable. A static whole-deck categorization need not require
more lookahead than multi-turn combat; it can be solved without a transition model.
Run duration is long, but duration is not identical to model planning depth when
scripted policies make path, event, merchant, and rest decisions.

## Operationalization failures

### Turn

The target is enemy HP lost on the current turn. Defense, setup, next-turn draw, and
resource conservation receive no value. The task is a bounded combinatorial sequence
problem. The implementation searches within a 20,000-node budget; exactness must be
persisted per sample rather than presumed.

### Combat

Win rate and final-HP ratio combine policy execution and repeated structured-output
reliability. The HP denominator is a greedy current-hand-order policy, not an optimal
combat oracle. Ceiling performance among instruct models limits discrimination.

### Synergy

Archetype is a taxonomy label, not an outcome. Best-card labels are authored from the
same buckets. A lookup policy achieves 100% on all 120 character × fixture × position
cases. This identifies label leakage/recognition capacity, not forward planning.

### Run

The model's default control surface excludes core long-run decisions. Observed floors
can reflect compounding parse errors, weak combat, poor reward picks, scripted routing,
or simulator mechanics. “Longer sequence” is observable; “longer internal plan” is not.

## Convergent and discriminant validity

No external strategic-performance measure is correlated with task scores. No human,
solver, original-game agent, or independent benchmark establishes convergent validity.
Discriminant validity is also absent: no memory, rule recall, parsing, lexical lookup,
or generic multiple-choice control demonstrates that the scores isolate planning.

The cross-task rank/profile analysis can diagnose heterogeneity but cannot recover a
latent planning factor with seven configurations. Factor analysis would be unjustified
at this sample size and with these task definitions.

## Valid construct claims now

- “Models differ on four Slay-inspired operations in this simulator.”
- “The Qwen3 scale/architecture comparison has a selective card-choice gain.”
- “Default Act-1 hybrid-policy rollouts remain on par with a scripted greedy policy.”

Invalid until new data:

- a planning-collapse curve;
- a model-specific maximum planning horizon;
- a common overall strategic score;
- full-run strategic competence;
- synergy understanding from fixed label fixtures.

## Remediation

Use `controlled-decision-horizon-v2`: identical fully observable combat state and prompt contract,
identical next-action vocabulary and terminal utility, exact value-to-go oracle, with
only H ∈ {1,2,4,8} changed. Add memory/retrieval and parse controls, then test the
within-state H slope. Results are **PENDING EXPERIMENT**.
