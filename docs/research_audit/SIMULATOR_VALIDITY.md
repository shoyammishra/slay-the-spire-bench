# Simulator validity audit

## Conclusion

The codebase implements a large deterministic Slay-inspired simulator with Acts 1–3,
two characters, cards, relics, enemies, events, shops, and run traversal. The 180
directly runnable tests after this audit establish substantial internal
consistency. They do not establish external fidelity. The manuscript must say
“deterministic Slay the Spire simulator with documented simplifications,” not
“faithful simulator.”

## Evidence tiers

| Tier | Evidence in repository | What it supports | What it does not support |
|---|---|---|---|
| Unit/mechanics | card, combat, run, stats tests | deterministic implemented behavior | agreement with original game |
| Replay | nine RNG streams; seed tests | reproducibility inside one version | cross-version equivalence |
| Integration | four mock pipelines and run tests | end-to-end execution | realistic policy quality |
| External conformance | no systematic suite | — | fidelity claim |
| Human/agent criterion | none | — | ecological validity |

## Known consequential deviations

- Potions are not actively usable; only an automatic Fairy in a Bottle path exists.
- Several event combats resolve as flavor without combat or rewards.
- Event choice in default runs is fixed to option 0; some outcomes are deterministic
  approximations.
- Some draw-pile/status placement, relic eligibility/effects, and timing rules differ
  from the original game.
- The run evaluator's default policy scripts map, rest, shop, and event decisions.
- Current headline runs are Act 1 even though Acts 2–3 exist.

These gaps directly affect deck value, routing, risk, resource use, and survival. They
are not peripheral to “full-run planning.”

## Required conformance program

Create a versioned mechanics table with, for every implemented card/relic/enemy/event:
source rule, expected trace, implementation test, known deviation, and benchmark
exposure. Use an independent public reference or original-game observation without
copying protected game assets. Sample at least:

- 50 high-exposure card interactions per character;
- all benchmark enemy intents and debuff timings;
- all relics observed in released run fixtures;
- reward, shop, rest, event, and boss transitions;
- seeded trace comparisons over complete Act-1 paths.

Blind a second implementer to write expected traces for a stratified subset. Report
conformance rate and severity-weighted discrepancies. A passing internal test written
from the same code assumptions is not independent validation.

## Comparability rule

Any mechanic correction that can change prompts, legal actions, card values, rewards,
or survival creates a new instrument version. Classify affected historical cells and
re-baseline before combining numbers. Preserve old results with a supersession marker.
