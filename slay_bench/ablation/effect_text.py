"""Engine-faithful effect text + deterministic neutral renaming (controlled-H v3).

Purpose
-------
Instrument for the planned "described" and "renamed+described" prompt ablations
(PTA reviewers: results may reflect pretrained card-name recognition). This module
does NOT change any prompt, runner, config or frozen file; it only provides:

* ``CARD_SPECS`` / ``ENEMY_SPECS`` / ``RELIC_SPECS`` / ``POWER_SPECS`` - structured
  specs of every card, enemy, relic and power that occurs in (or can be generated
  inside the lookahead of) the 1,760 controlled-H v3 release fixtures. Specs describe
  OUR ENGINE's behaviour, not the wiki's; deviations live in ``real_game`` notes
  (never rendered into prompts).
* ``describe_card`` / ``describe_enemy`` / ``describe_relic`` / ``describe_power`` and
  ``effects_appendix(state)`` - English text rendered FROM the structured fields
  (single source of truth; ``tests/test_effect_text.py`` replays every numeric field
  through the real engine).
* ``neutral_name_map(names, seed)`` + ``rename(text_or_payload, mapping)`` -
  deterministic, bijective neutral renaming ("Card K7", "Enemy B", ...).

Keyword policy (renaming)
-------------------------
PROPER NAMES are renamed: card names (and card ids such as ``Strike_R``), enemy
names/ids, relic names, distinctive enemy move names (Bellow, Slam, Siphon Soul, ...)
and enemy-specific power names (``enrage``). Powers whose name is a card name
(``Feel No Pain``, ``Accuracy``, ``Metallicize`` ...) are renamed through the card
name because renaming is string-level (one string -> one token).

GENERIC MECHANIC KEYWORDS are kept: Strength, Dexterity, Vulnerable, Weak, Frail,
Poison, Artifact, Intangible, Thorns, Block, energy, Exhaust, Ethereal, Innate,
Retain, Unplayable, Energized, Next Turn Block, Next Turn Draw, Double Damage, Choked,
and generic move labels (Attack, Sleep, Preparing, Activate). Justification: (1) they
are shared rules vocabulary of the whole genre, not identifiers of a particular card
or enemy, so they carry little item-recognition signal; (2) every one of them is
defined in the rendered rules glossary, so the renamed+described condition remains
self-contained; (3) renaming them would turn the ablation into "learn an unknown
rule system from scratch", confounding name recognition with rule comprehension;
(4) the prompt's JSON keys / the engine's power ids use these strings, so keeping
them avoids desynchronising the payload. Residual leak (documented): keyword mix
(e.g. Poison) still reveals the character archetype; the context names
``Slay the Spire`` / ``Ironclad`` / ``Silent`` are optional (``CONTEXT_NAMES``).

Interface modes
---------------
``mode="controlled_h"`` (default) renders what the controlled-H oracle actually
simulates: ``controlled_horizon.legal_actions`` gives every non-Attack card
``target_index=-1`` and ``transition`` then calls ``play_card(..., target=None)``, so
targeted SKILLS (Deadly Poison, Terror, Catalyst, Corpse Explosion, Malaise, Leg
Sweep's Weak, Spot Weakness) never affect an enemy. ``mode="engine"`` renders the
card's engine effect when a target IS supplied (legacy combat harness).
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

EFFECT_TEXT_VERSION = "effect-text-v1"

MODES = ("controlled_h", "engine")

# ── keyword / name policy ─────────────────────────────────────────────────────

KEPT_KEYWORDS = (
    "Strength", "Dexterity", "Vulnerable", "Weak", "Frail", "Poison", "Artifact",
    "Intangible", "Thorns", "Block", "Exhaust", "Ethereal", "Innate", "Retain",
    "Unplayable", "Energized", "Next Turn Block", "Next Turn Draw", "Double Damage",
    "Choked",
)
GENERIC_MOVE_NAMES = ("Attack", "Sleep", "Preparing", "Activate")
CONTEXT_NAMES = ("Slay the Spire", "Ironclad", "Silent")


# ── spec dataclasses ──────────────────────────────────────────────────────────

@dataclass(frozen=True)
class CardSpec:
    """Structured, engine-faithful spec of one card (base, non-upgraded).

    Numeric fields describe ONE play in a canonical sandbox (no Strength/Weak/
    Vulnerable/Dexterity, hand otherwise empty, ample draw pile of filler cards).
    Conditional numbers live in ``params`` and are used by both the renderer
    (via clause templates) and the fidelity tests.
    """
    id: str
    name: str
    character: str              # 'ironclad' | 'silent' | 'any'
    type: str                   # ATTACK | SKILL | POWER | STATUS
    cost: Optional[int]         # None = unplayable; -2 = X
    upgraded: bool = False
    damage: int = 0             # per hit, before modifiers
    hits: int = 0
    target: str = "none"        # enemy | all | random | none
    block: int = 0
    draw: int = 0
    energy: int = 0             # energy gained by the play (excluding the cost)
    hp_loss: int = 0
    self_powers: Tuple[Tuple[str, int], ...] = ()
    target_powers: Tuple[Tuple[str, int], ...] = ()     # needs a target enemy
    all_enemy_powers: Tuple[Tuple[str, int], ...] = ()
    exhaust: bool = False
    ethereal: bool = False
    innate: bool = False
    retain: bool = False
    unplayable: bool = False
    targeted_skill: bool = False   # SKILL whose enemy effect needs a target
    params: Tuple[Tuple[str, Any], ...] = ()
    clauses: Tuple[str, ...] = ()  # templated; {card:X}/{power:X}/... refs, {p:key}
    target_clauses: Tuple[str, ...] = ()  # targeted-skill clauses (need a target)
    generates: Tuple[str, ...] = ()  # card NAMES this card can add to the game
    real_game: str = ""           # deviation note (never rendered)
    unchecked: str = ""           # reason a numeric aspect cannot be checked

    def param(self, key: str, default: Any = None) -> Any:
        return dict(self.params).get(key, default)


@dataclass(frozen=True)
class MoveSpec:
    name: str
    intent: str
    damage: int = 0
    hits: int = 0
    effect: str = ""          # templated
    damage_text: str = ""     # templated override when damage is formula-based


@dataclass(frozen=True)
class EnemySpec:
    key: str                  # class name
    name: str                 # display name
    ids: Tuple[str, ...]      # engine ids seen (aliases)
    hp_min: int
    hp_max: int
    start_powers: Tuple[Tuple[str, int], ...] = ()
    moves: Tuple[MoveSpec, ...] = ()
    ai: Tuple[str, ...] = ()  # templated rule sentences
    deterministic_cycle: Tuple[str, ...] = ()   # executed-move order (tested)
    spawns: Tuple[str, ...] = ()                # enemy names created by splitting
    generates: Tuple[str, ...] = ()             # card names added to your piles
    real_game: str = ""


@dataclass(frozen=True)
class RelicSpec:
    name: str
    character: str
    text: str
    real_game: str = ""


@dataclass(frozen=True)
class PowerSpec:
    name: str                 # PowerId value / engine key as shown in prompts
    text: str                 # templated, {n} = stack amount
    proper: bool = False      # renamed (enemy-specific) vs generic keyword
    real_game: str = ""


# ── card specs ────────────────────────────────────────────────────────────────

def _C(id, name, character, type, cost, **kw) -> CardSpec:
    for key in ("self_powers", "target_powers", "all_enemy_powers", "params",
                "clauses", "target_clauses", "generates"):
        if key in kw:
            value = kw[key]
            if isinstance(value, dict):
                value = tuple(value.items())
            kw[key] = tuple(value)
    return CardSpec(id=id, name=name, character=character, type=type, cost=cost, **kw)


_AUTO_DISCARD = "discard 1 card (automatic choice, see Rules)"

_CARDS: List[CardSpec] = [
    # ── statuses (any character) ──
    _C("Dazed", "Dazed", "any", "STATUS", None, unplayable=True, ethereal=True),
    _C("Slimed", "Slimed", "any", "STATUS", 1, exhaust=True,
       clauses=("No other effect.",)),
    _C("Burn", "Burn", "any", "STATUS", None, unplayable=True,
       params={"end_turn_damage": 2},
       clauses=("At the end of your turn, if this is in your hand, you take {p:end_turn_damage} "
                "damage (Block applies; Vulnerable does not).",)),

    # ── Ironclad ──
    _C("Strike_R", "Strike", "ironclad", "ATTACK", 1, damage=6, hits=1, target="enemy"),
    _C("Defend_R", "Defend", "ironclad", "SKILL", 1, block=5),
    _C("Bash", "Bash", "ironclad", "ATTACK", 2, damage=8, hits=1, target="enemy",
       target_powers={"Vulnerable": 2},
       real_game="Vulnerable is only applied if the target survives the hit."),
    _C("Bloodletting", "Bloodletting", "ironclad", "SKILL", 0, hp_loss=3, energy=2),
    _C("Bludgeon", "Bludgeon", "ironclad", "ATTACK", 3, damage=32, hits=1, target="enemy"),
    _C("Body Slam", "Body Slam", "ironclad", "ATTACK", 1, target="enemy",
       params={"damage_equals_block": True},
       clauses=("Deal damage equal to your current Block to the target enemy.",)),
    _C("Brutality", "Brutality", "ironclad", "POWER", 0,
       params={"turn_hp_loss": 1, "turn_draw": 1},
       clauses=("For the rest of combat, at the start of each of your turns, lose "
                "{p:turn_hp_loss} HP and draw {p:turn_draw} card. Further copies add nothing.",),
       real_game="Real Brutality stacks per copy; the engine uses a single on/off flag."),
    _C("Burning Pact", "Burning Pact", "ironclad", "SKILL", 1, draw=2,
       clauses=("Before drawing, Exhaust the first other card in your hand (automatic "
                "choice; real game: your choice).",)),
    _C("Carnage", "Carnage", "ironclad", "ATTACK", 2, damage=20, hits=1, target="enemy",
       ethereal=True),
    _C("Clash", "Clash", "ironclad", "ATTACK", 0, damage=14, hits=1, target="enemy",
       clauses=("Can only be played if every other card in your hand is an Attack.",)),
    _C("Evolve", "Evolve", "ironclad", "POWER", 1, self_powers={"Evolve": 1}),
    _C("Exhume", "Exhume", "ironclad", "SKILL", 1, exhaust=True,
       clauses=("Put the most recently exhausted card (other than an {card:Exhume}) from "
                "your exhaust pile into your hand (automatic choice; real game: your choice).",)),
    _C("Feed", "Feed", "ironclad", "ATTACK", 1, damage=10, hits=1, target="enemy",
       exhaust=True, params={"kill_max_hp": 3},
       clauses=("If this kills the target, raise your max HP by {p:kill_max_hp} and heal "
                "{p:kill_max_hp} HP.",)),
    _C("Feel No Pain", "Feel No Pain", "ironclad", "POWER", 1,
       self_powers={"Feel No Pain": 3}),
    _C("Fiend Fire", "Fiend Fire", "ironclad", "ATTACK", 2, target="enemy", exhaust=True,
       params={"per_card_damage": 6},
       clauses=("Exhaust every other card in your hand; for each card exhausted, deal "
                "{p:per_card_damage} damage to the target enemy.",),
       real_game="Real Fiend Fire deals 7 per card (10 upgraded); engine 6 (7 upgraded)."),
    _C("Fire Breathing", "Fire Breathing", "ironclad", "POWER", 1,
       self_powers={"Fire Breathing": 6},
       real_game="Real Fire Breathing also triggers on Curse draws; engine Status only."),
    _C("Flame Barrier", "Flame Barrier", "ironclad", "SKILL", 2, block=8,
       self_powers={"Flame Barrier": 4},
       real_game="Real Flame Barrier: 12 Block and the retaliation ends at the start of "
                 "your next turn. Engine: 8 Block and the retaliation never expires during "
                 "combat (stacks with further copies) - suspected engine bug."),
    _C("Iron Wave", "Iron Wave", "ironclad", "ATTACK", 1, damage=5, hits=1,
       target="enemy", block=5),
    _C("Juggernaut", "Juggernaut", "ironclad", "POWER", 2, self_powers={"Juggernaut": 5}),
    _C("Limit Break", "Limit Break", "ironclad", "SKILL", 1, exhaust=True,
       clauses=("Double your Strength (no effect at 0 Strength).",)),
    _C("Metallicize", "Metallicize", "ironclad", "POWER", 1,
       self_powers={"Metallicize": 3},
       real_game="Real Metallicize grants Block at the END of your turn; engine at the "
                 "START of your next turn (first Block arrives one enemy phase later)."),
    _C("Offering", "Offering", "ironclad", "SKILL", 0, hp_loss=6, energy=2, draw=3,
       exhaust=True),
    _C("Perfected Strike", "Perfected Strike", "ironclad", "ATTACK", 2, damage=6, hits=1,
       target="enemy", params={"per_strike": 2},
       clauses=("Deals {p:per_strike} additional damage for each card you have in this "
                "combat (hand, draw, discard and exhaust piles, counting this card) that "
                "is a {card:Strike}, {card:Pommel Strike} or {card:Perfected Strike}.",),
       real_game="Engine matches the id substring 'strike' (Strike_R, Pommel Strike, "
                 "Perfected Strike); same set as the real game for these fixtures."),
    _C("Pommel Strike", "Pommel Strike", "ironclad", "ATTACK", 1, damage=9, hits=1,
       target="enemy", draw=1),
    _C("Sever Soul", "Sever Soul", "ironclad", "ATTACK", 2, damage=16, hits=1,
       target="enemy",
       clauses=("Before the damage, Exhaust every non-Attack card in your hand.",)),
    _C("Shockwave", "Shockwave", "ironclad", "SKILL", 2, exhaust=True,
       all_enemy_powers={"Weak": 3, "Vulnerable": 3}),
    _C("Shrug It Off", "Shrug It Off", "ironclad", "SKILL", 1, block=8, draw=1),
    _C("Spot Weakness", "Spot Weakness", "ironclad", "SKILL", 1, targeted_skill=True,
       params={"strength": 3},
       target_clauses=("If the target enemy intends to attack, gain {p:strength} "
                       "Strength.",)),
    _C("Sword Boomerang", "Sword Boomerang", "ironclad", "ATTACK", 1, damage=3, hits=3,
       target="random",
       unchecked="the per-enemy split of hits is random (misc RNG); total damage over "
                 "two enemies and exact damage vs one enemy are checked"),
    _C("Thunderclap", "Thunderclap", "ironclad", "ATTACK", 1, damage=4, hits=1,
       target="all", all_enemy_powers={"Vulnerable": 1}),
    _C("True Grit", "True Grit", "ironclad", "SKILL", 1, block=7,
       clauses=("Exhaust a random other card in your hand.",),
       unchecked="which card is exhausted is random (misc RNG); only Block and "
                 "'exactly one other card exhausted' are checked"),

    # ── Silent ──
    _C("Strike_G", "Strike", "silent", "ATTACK", 1, damage=6, hits=1, target="enemy"),
    _C("Defend_G", "Defend", "silent", "SKILL", 1, block=5),
    _C("Neutralize", "Neutralize", "silent", "ATTACK", 0, damage=3, hits=1,
       target="enemy", target_powers={"Weak": 1}),
    _C("Survivor", "Survivor", "silent", "SKILL", 1, block=8,
       clauses=("Then " + _AUTO_DISCARD + ".",)),
    _C("Shiv", "Shiv", "silent", "ATTACK", 0, damage=4, hits=1, target="enemy",
       exhaust=True),
    _C("A Thousand Cuts", "A Thousand Cuts", "silent", "POWER", 2,
       self_powers={"A Thousand Cuts": 1}),
    _C("Accuracy", "Accuracy", "silent", "POWER", 1, self_powers={"Accuracy": 4}),
    _C("Acrobatics", "Acrobatics", "silent", "SKILL", 1, draw=3,
       clauses=("Then " + _AUTO_DISCARD + ".",)),
    _C("Adrenaline", "Adrenaline", "silent", "SKILL", 0, energy=1, draw=2, exhaust=True),
    _C("After Image", "After Image", "silent", "POWER", 1,
       self_powers={"After Image": 1}),
    _C("Alchemize", "Alchemize", "silent", "SKILL", 1, exhaust=True,
       clauses=("Obtain a random potion (if you hold fewer than 3). Potions cannot be "
                "used in this engine, so this has no combat effect.",),
       unchecked="which potion is obtained is random (loot RNG); checked only that "
                 "exactly one potion is obtained"),
    _C("All-Out Attack", "All-Out Attack", "silent", "ATTACK", 1, damage=10, hits=1,
       target="all", clauses=("Then discard a random card from your hand.",),
       unchecked="the discarded card is random (misc RNG); checked only that exactly "
                 "one card is discarded"),
    _C("Backflip", "Backflip", "silent", "SKILL", 1, block=5, draw=2),
    _C("Backstab", "Backstab", "silent", "ATTACK", 0, damage=11, hits=1, target="enemy",
       exhaust=True, innate=True),
    _C("Bane", "Bane", "silent", "ATTACK", 1, damage=7, hits=1, target="enemy",
       params={"poison_extra_hits": 1},
       clauses=("If the target is still alive and has Poison, deal the damage again.",)),
    _C("Blade Dance", "Blade Dance", "silent", "SKILL", 1, params={"shivs": 3},
       clauses=("Add {p:shivs} copies of {card:Shiv} to your hand.",),
       generates=("Shiv",)),
    _C("Blur", "Blur", "silent", "SKILL", 1, block=5, self_powers={"Blur": 1}),
    _C("Bouncing Flask", "Bouncing Flask", "silent", "SKILL", 2,
       params={"poison": 3, "times": 3},
       clauses=("{p:times} times: apply {p:poison} Poison to a random enemy (re-chosen "
                "each time).",),
       unchecked="the per-enemy split is random (misc RNG); total Poison over two "
                 "enemies and exact Poison vs one enemy are checked"),
    _C("Bullet Time", "Bullet Time", "silent", "SKILL", 3,
       clauses=("Every card currently in your hand costs 0 for the rest of this turn.",),
       real_game="Real Bullet Time also prevents drawing this turn; engine omits that."),
    _C("Burst", "Burst", "silent", "SKILL", 1, self_powers={"Burst": 1}),
    _C("Calculated Gamble", "Calculated Gamble", "silent", "SKILL", 0, exhaust=True,
       clauses=("Discard your whole hand, then draw that many cards.",)),
    _C("Caltrops", "Caltrops", "silent", "POWER", 1, self_powers={"Thorns": 3},
       clauses=("Note: in this engine Thorns on you never triggers, so this has no "
                "combat effect.",),
       real_game="Real Caltrops deals 3 damage back to each attacker; engine never reads "
                 "the player's Thorns - suspected engine bug."),
    _C("Catalyst", "Catalyst", "silent", "SKILL", 1, exhaust=True, targeted_skill=True,
       params={"mult": 2},
       target_clauses=("Multiply the target enemy's Poison by {p:mult}.",)),
    _C("Choke", "Choke", "silent", "ATTACK", 2, damage=12, hits=1, target="enemy",
       target_powers={"Choked": 3}),
    _C("Cloak and Dagger", "Cloak and Dagger", "silent", "SKILL", 1, block=6,
       params={"shivs": 1},
       clauses=("Add {p:shivs} {card:Shiv} to your hand.",), generates=("Shiv",)),
    _C("Concentrate", "Concentrate", "silent", "SKILL", 0, energy=2,
       params={"discards": 3},
       clauses=("First discard {p:discards} cards one at a time (automatic choice, see "
                "Rules).",)),
    _C("Corpse Explosion", "Corpse Explosion", "silent", "SKILL", 2, targeted_skill=True,
       target_powers={"Poison": 6, "Corpse Explosion": 1}),
    _C("Crippling Cloud", "Crippling Cloud", "silent", "SKILL", 2, exhaust=True,
       all_enemy_powers={"Poison": 4, "Weak": 2}),
    _C("Dagger Spray", "Dagger Spray", "silent", "ATTACK", 1, damage=4, hits=2,
       target="all"),
    _C("Dagger Throw", "Dagger Throw", "silent", "ATTACK", 1, damage=9, hits=1,
       target="enemy", draw=1, clauses=("After drawing, " + _AUTO_DISCARD + ".",)),
    _C("Dash", "Dash", "silent", "ATTACK", 2, damage=10, hits=1, target="enemy", block=10),
    _C("Deadly Poison", "Deadly Poison", "silent", "SKILL", 1, targeted_skill=True,
       target_powers={"Poison": 5}),
    _C("Deflect", "Deflect", "silent", "SKILL", 0, block=4),
    _C("Die Die Die", "Die Die Die", "silent", "ATTACK", 1, damage=13, hits=1,
       target="all", exhaust=True),
    _C("Distraction", "Distraction", "silent", "SKILL", 1, exhaust=True,
       clauses=("Add a {card:Deflect} to your hand.",), generates=("Deflect",),
       real_game="Real Distraction adds a random Skill that costs 0 this turn."),
    _C("Dodge and Roll", "Dodge and Roll", "silent", "SKILL", 1, block=4,
       self_powers={"Next Turn Block": 4}),
    _C("Doppelganger", "Doppelganger", "silent", "SKILL", -2, exhaust=True,
       clauses=("Spend all your energy (X). Next turn, draw X additional cards and gain "
                "X additional energy.",)),
    _C("Endless Agony", "Endless Agony", "silent", "ATTACK", 0, damage=4, hits=1,
       target="enemy", exhaust=True,
       clauses=("Whenever you draw this card, add a copy of it to your hand.",),
       generates=("Endless Agony",)),
    _C("Envenom", "Envenom", "silent", "POWER", 2, self_powers={"Envenom": 1}),
    _C("Escape Plan", "Escape Plan", "silent", "SKILL", 0, draw=1,
       params={"skill_block": 3},
       clauses=("If the drawn card is a Skill, gain {p:skill_block} Block.",)),
    _C("Eviscerate", "Eviscerate", "silent", "ATTACK", 3, damage=7, hits=3,
       target="enemy",
       clauses=("Costs 1 less for each card you discarded this turn (minimum 0); stops "
                "hitting once the target dies.",)),
    _C("Expertise", "Expertise", "silent", "SKILL", 1, params={"hand_to": 6},
       clauses=("Draw cards until you have {p:hand_to} cards in hand.",)),
    _C("Finisher", "Finisher", "silent", "ATTACK", 1, target="enemy",
       params={"per_attack_damage": 6},
       clauses=("Deal {p:per_attack_damage} damage to the target enemy once for each "
                "Attack you already played this turn (not counting this one).",)),
    _C("Flechettes", "Flechettes", "silent", "ATTACK", 1, target="enemy",
       params={"per_skill_damage": 4},
       clauses=("Deal {p:per_skill_damage} damage to the target enemy once for each "
                "Skill in your hand.",)),
    _C("Flying Knee", "Flying Knee", "silent", "ATTACK", 1, damage=8, hits=1,
       target="enemy", self_powers={"Energized": 1}),
    _C("Footwork", "Footwork", "silent", "POWER", 1, self_powers={"Dexterity": 2}),
    _C("Glass Knife", "Glass Knife", "silent", "ATTACK", 1, damage=8, hits=2,
       target="enemy", params={"decay": 2},
       clauses=("Each play permanently lowers this copy's damage by {p:decay} for the "
                "rest of combat.",)),
    _C("Grand Finale", "Grand Finale", "silent", "ATTACK", 0, damage=50, hits=1,
       target="all",
       clauses=("Can only be played if your draw pile is empty.",)),
    _C("Heel Hook", "Heel Hook", "silent", "ATTACK", 1, damage=5, hits=1, target="enemy",
       params={"weak_energy": 1, "weak_draw": 1},
       clauses=("If the target has Weak, gain {p:weak_energy} energy and draw "
                "{p:weak_draw} card.",)),
    _C("Infinite Blades", "Infinite Blades", "silent", "POWER", 1,
       self_powers={"Infinite Blades": 1}, generates=("Shiv",)),
    _C("Leg Sweep", "Leg Sweep", "silent", "SKILL", 2, block=11, targeted_skill=True,
       target_powers={"Weak": 2}),
    _C("Malaise", "Malaise", "silent", "SKILL", -2, exhaust=True, targeted_skill=True,
       clauses=("Spend all your energy (X).",),
       target_clauses=("The target enemy loses X Strength (ignores Artifact) and gains X "
                       "Weak.",),
       real_game="Engine's Strength loss ignores Artifact (real game: Artifact blocks it)."),
    _C("Masterful Stab", "Masterful Stab", "silent", "ATTACK", 2, damage=12, hits=1,
       target="enemy",
       real_game="Real cost is 0 (+1 per HP lost this combat); engine fixed cost 2."),
    _C("Nightmare", "Nightmare", "silent", "SKILL", 3, exhaust=True, params={"copies": 3},
       clauses=("At the start of your next turn, add {p:copies} copies of the first other "
                "card in your hand (automatic choice) to your hand.",)),
    _C("Noxious Fumes", "Noxious Fumes", "silent", "POWER", 1,
       self_powers={"Noxious Fumes": 2}),
    _C("Outmaneuver", "Outmaneuver", "silent", "SKILL", 1,
       self_powers={"Energized": 2}),
    _C("Phantasmal Killer", "Phantasmal Killer", "silent", "SKILL", 1,
       self_powers={"Phantasmal Killer": 1}),
    _C("Piercing Wail", "Piercing Wail", "silent", "SKILL", 1, exhaust=True,
       all_enemy_powers={"Strength": -6},
       clauses=("This Strength loss lasts the rest of combat and ignores Artifact.",),
       real_game="Real Piercing Wail's Strength loss lasts one turn and is blocked by "
                 "Artifact; engine: permanent and ignores Artifact."),
    _C("Poisoned Stab", "Poisoned Stab", "silent", "ATTACK", 1, damage=6, hits=1,
       target="enemy", target_powers={"Poison": 3}),
    _C("Predator", "Predator", "silent", "ATTACK", 2, damage=15, hits=1, target="enemy",
       self_powers={"Next Turn Draw": 2}),
    _C("Prepared", "Prepared", "silent", "SKILL", 0, draw=1,
       clauses=("Then " + _AUTO_DISCARD + ".",)),
    _C("Quick Slash", "Quick Slash", "silent", "ATTACK", 1, damage=8, hits=1,
       target="enemy", draw=1),
    _C("Reflex", "Reflex", "silent", "SKILL", None, unplayable=True,
       params={"discard_draw": 2},
       clauses=("Whenever a card effect discards this from your hand, draw "
                "{p:discard_draw} cards.",)),
    _C("Riddle with Holes", "Riddle with Holes", "silent", "ATTACK", 2, damage=3, hits=5,
       target="enemy"),
    _C("Setup", "Setup", "silent", "SKILL", 1,
       clauses=("Put the first other card in your hand (automatic choice) on top of "
                "your draw pile; it costs 0 for the rest of combat.",),
       real_game="Real Setup: your choice, costs 0 until played."),
    _C("Skewer", "Skewer", "silent", "ATTACK", -2, damage=7, target="enemy",
       clauses=("Spend all your energy (X): deal the damage X times.",)),
    _C("Slice", "Slice", "silent", "ATTACK", 0, damage=6, hits=1, target="enemy"),
    _C("Sneaky Strike", "Sneaky Strike", "silent", "ATTACK", 2, damage=12, hits=1,
       target="enemy", params={"discard_energy": 2},
       clauses=("If you discarded a card this turn, gain {p:discard_energy} energy.",)),
    _C("Storm of Steel", "Storm of Steel", "silent", "SKILL", 1,
       clauses=("Discard your whole hand, then add one {card:Shiv} to your hand per "
                "card discarded.",), generates=("Shiv",)),
    _C("Sucker Punch", "Sucker Punch", "silent", "ATTACK", 1, damage=7, hits=1,
       target="enemy", target_powers={"Weak": 1}),
    _C("Tactician", "Tactician", "silent", "SKILL", None, unplayable=True,
       params={"discard_energy": 1},
       clauses=("Whenever a card effect discards this from your hand, gain "
                "{p:discard_energy} energy.",)),
    _C("Terror", "Terror", "silent", "SKILL", 1, exhaust=True, targeted_skill=True,
       target_powers={"Vulnerable": 99}),
    _C("Tools of the Trade", "Tools of the Trade", "silent", "POWER", 1,
       self_powers={"Tools of the Trade": 1}),
    _C("Unload", "Unload", "silent", "ATTACK", 1, damage=14, hits=1, target="enemy",
       clauses=("Then discard every non-Attack card in your hand.",)),
    _C("Well-Laid Plans", "Well-Laid Plans", "silent", "POWER", 1,
       self_powers={"Well-Laid Plans": 1},
       real_game="Real: you choose which card to Retain; engine keeps the first card(s)."),
    _C("Wraith Form", "Wraith Form", "silent", "POWER", 3,
       self_powers={"Intangible": 2, "Wraith Form": 1}),
]

CARD_SPECS: Dict[str, CardSpec] = {spec.id: spec for spec in _CARDS}
if len(CARD_SPECS) != len(_CARDS):  # pragma: no cover - authoring guard
    raise RuntimeError("duplicate card spec id")

# Cards whose enemy effect needs a target that controlled-H never supplies.
TARGETED_SKILLS = tuple(sorted(s.name for s in _CARDS if s.targeted_skill))


# ── power specs ───────────────────────────────────────────────────────────────

_POWERS: List[PowerSpec] = [
    PowerSpec("Strength", "adds {n} to the damage of each hit of the owner's attacks "
              "(negative values reduce it)."),
    PowerSpec("Dexterity", "adds {n} to every Block gain of yours (negative reduces it)."),
    PowerSpec("Vulnerable", "the owner takes 50% more damage from attacks (rounded down) "
              "for {n} more turn(s)."),
    PowerSpec("Weak", "the owner's attacks deal 25% less damage (rounded down) for {n} "
              "more turn(s)."),
    PowerSpec("Frail", "you gain 25% less Block from cards for {n} more turn(s)."),
    PowerSpec("Poison", "at the end of each round the owner loses {n} HP (ignores Block), "
              "then Poison drops by 1."),
    PowerSpec("Artifact", "negates the next {n} debuff(s) applied to the owner (Weak, "
              "Vulnerable, Frail, Poison, ...)."),
    PowerSpec("Intangible", "damage the owner takes is reduced to 1 per hit (your "
              "HP-loss effects are not reduced); lasts {n} more round(s)."),
    PowerSpec("Thorns", "on an enemy: whenever you hit it with an attack you take {n} "
              "damage. On you: no effect in this engine.",
              real_game="Player Thorns is never read by the engine (Caltrops no-op)."),
    PowerSpec("Metallicize", "on you: at the start of each of your turns gain {n} Block. "
              "On an enemy: at the end of each round it gains {n} Block.",
              real_game="Real player Metallicize triggers at end of turn."),
    PowerSpec("enrage", "whenever you play a Skill, this enemy gains {n} Strength (before "
              "the Skill resolves).", proper=True),
    PowerSpec("Choked", "for the rest of this turn, whenever you play a card, this enemy "
              "loses {n} HP (ignores Block)."),
    PowerSpec("Energized", "at the start of your next turn gain {n} additional energy."),
    PowerSpec("Next Turn Block", "at the start of your next turn gain {n} Block."),
    PowerSpec("Next Turn Draw", "at the start of your next turn draw {n} additional "
              "card(s)."),
    PowerSpec("Double Damage", "your attacks deal double damage; ends at the end of "
              "this round."),
    PowerSpec("Evolve", "whenever you draw a Status card, draw {n} card(s)."),
    PowerSpec("Feel No Pain", "whenever a card is exhausted, gain {n} Block."),
    PowerSpec("Fire Breathing", "whenever you draw a Status card, deal {n} damage to ALL "
              "enemies."),
    PowerSpec("Flame Barrier", "whenever an enemy attack hits you (each hit), deal {n} "
              "damage to that enemy. Does not expire during combat in this engine.",
              real_game="Real Flame Barrier ends at the start of your next turn."),
    PowerSpec("Juggernaut", "whenever you gain more than 0 Block, deal {n} damage to a "
              "random enemy."),
    PowerSpec("Noxious Fumes", "at the start of your turn, apply {n} Poison to ALL "
              "enemies."),
    PowerSpec("Envenom", "whenever your attack deals unblocked damage, apply {n} Poison "
              "to that enemy."),
    PowerSpec("A Thousand Cuts", "whenever you play a card, deal {n} damage to ALL "
              "enemies (before the card resolves)."),
    PowerSpec("After Image", "whenever you play a card, gain {n} Block (before the card "
              "resolves)."),
    PowerSpec("Accuracy", "each {card:Shiv} deals {n} additional damage."),
    PowerSpec("Infinite Blades", "at the start of your turn, add {n} {card:Shiv} to your "
              "hand."),
    PowerSpec("Tools of the Trade", "at the start of your turn, draw {n} card(s), then "
              "discard {n} card(s) (automatic choice, see Rules)."),
    PowerSpec("Wraith Form", "at the end of each of your turns, lose 1 Dexterity "
              "(regardless of stacks)."),
    PowerSpec("Burst", "your next {n} Skill(s) are played twice."),
    PowerSpec("Blur", "your Block is not removed at the start of your next {n} turn(s)."),
    PowerSpec("Phantasmal Killer", "at the start of your next turn, gain Double Damage "
              "for that turn."),
    PowerSpec("Well-Laid Plans", "at the end of your turn, the first {n} card(s) in your "
              "hand (automatic choice) stay in hand for the next turn."),
    PowerSpec("Corpse Explosion", "when this enemy dies, deal damage equal to its max HP "
              "to every other enemy."),
]
POWER_SPECS: Dict[str, PowerSpec] = {p.name: p for p in _POWERS}


# ── enemy specs ───────────────────────────────────────────────────────────────

_M = MoveSpec

_ENEMIES: List[EnemySpec] = [
    EnemySpec(
        key="Lagavulin", name="Lagavulin", ids=("Lagavulin",), hp_min=109, hp_max=116,
        start_powers=(("Metallicize", 8),),
        moves=(
            _M("Sleep", "SLEEP", effect="does nothing."),
            _M("Attack", "ATTACK", damage=18, hits=1),
            _M("Siphon Soul", "DEBUFF", effect="you lose 1 Strength and 1 Dexterity."),
        ),
        ai=(
            "Starts asleep with {power:Metallicize} 8 (gains 8 Block at the end of each "
            "round) and uses {move:Sleep}.",
            "When its next move is chosen (end of each round, and at combat start) it "
            "wakes if it has already used {move:Sleep} twice OR your HP is below your "
            "max HP. Damaging it does NOT wake it.",
            "On waking it loses {power:Metallicize} and its move is {move:Attack}; "
            "afterwards it strictly alternates {move:Siphon Soul} and {move:Attack}.",
        ),
        deterministic_cycle=("Sleep", "Sleep", "Attack", "Siphon Soul", "Attack",
                             "Siphon Soul"),
        real_game="Real Lagavulin wakes when it takes HP damage (or after 3 sleeping "
                  "turns) and attacks twice before each Siphon Soul; engine wakes on the "
                  "PLAYER being below max HP, sleeps 2 turns, and alternates."),
    EnemySpec(
        key="SlimeBoss", name="Slime Boss", ids=("SlimeBoss",), hp_min=140, hp_max=149,
        moves=(
            _M("Goop Spray", "DEBUFF", effect="adds 3 {card:Slimed} to your discard pile."),
            _M("Preparing", "UNKNOWN", effect="does nothing."),
            _M("Slam", "ATTACK", damage=35, hits=1),
        ),
        ai=(
            "Fixed 5-move cycle: {move:Goop Spray}, {move:Preparing}, {move:Slam}, "
            "{move:Preparing}, {move:Slam}, then repeats.",
            "Split: the moment an attack or other direct damage leaves it alive at or "
            "below half its max HP, it is removed and replaced by a "
            "{enemy:Spike Slime (L)} and an {enemy:Acid Slime (L)}, each with HP and max "
            "HP equal to its HP at that moment. New slimes take no action in the round "
            "they appear.",
            "Poison and Choked HP loss do not trigger the split (it can die to Poison "
            "without splitting).",
        ),
        deterministic_cycle=("Goop Spray", "Preparing", "Slam", "Preparing", "Slam",
                             "Goop Spray"),
        spawns=("Spike Slime (L)", "Acid Slime (L)"), generates=("Slimed",),
        real_game="Real Slime Boss cycles Goop Spray/Preparing/Slam (3 moves) and splits "
                  "as its next action; engine uses a 5-move cycle, splits instantly, and "
                  "never splits from Poison (suspected bug)."),
    EnemySpec(
        key="AcidSlimeL", name="Acid Slime (L)", ids=("AcidSlime_L",), hp_min=65,
        hp_max=74,
        moves=(
            _M("Corrosive Spit", "ATTACK_DEBUFF", damage=11, hits=1,
               effect="also adds 2 {card:Slimed} to your discard pile."),
            _M("Tackle", "ATTACK", damage=16, hits=1),
            _M("Lick", "DEBUFF", effect="applies 2 Weak to you."),
        ),
        ai=("Random each round: 40% {move:Corrosive Spit}, 30% {move:Tackle}, 30% "
            "{move:Lick}; never the same move twice in a row (a repeat roll becomes one "
            "of the other two, 50/50).",
            "Splits like the boss (at or below half HP from direct damage) into two "
            "{enemy:Acid Slime (M)} with its current HP.",),
        spawns=("Acid Slime (M)",), generates=("Slimed",)),
    EnemySpec(
        key="SpikeSlimeL", name="Spike Slime (L)", ids=("SpikeSlime_L",), hp_min=65,
        hp_max=74,
        moves=(
            _M("Flame Tackle", "ATTACK_DEBUFF", damage=16, hits=1,
               effect="also adds 2 {card:Slimed} to your discard pile."),
            _M("Lunge", "ATTACK", damage=18, hits=1),
        ),
        ai=("Random each round: 30% {move:Flame Tackle}, 70% {move:Lunge}; never the "
            "same move twice in a row.",
            "Splits like the boss into two {enemy:Spike Slime (M)} with its current HP.",),
        spawns=("Spike Slime (M)",), generates=("Slimed",),
        real_game="Real Spike Slime (L) has Lick (2 Frail) instead of an 18-damage Lunge."),
    EnemySpec(
        key="AcidSlimeM", name="Acid Slime (M)", ids=("AcidSlime_M",), hp_min=28,
        hp_max=37,
        moves=(
            _M("Corrosive Spit", "ATTACK_DEBUFF", damage=7, hits=1,
               effect="also adds 1 {card:Slimed} to your discard pile."),
            _M("Tackle", "ATTACK", damage=7, hits=1),
            _M("Lick", "DEBUFF", effect="applies 1 Weak to you."),
        ),
        ai=("Random each round: 40% {move:Corrosive Spit}, 30% {move:Tackle}, 30% "
            "{move:Lick}; never the same move twice in a row.",),
        generates=("Slimed",),
        real_game="Real Acid Slime (M) Tackle deals 10."),
    EnemySpec(
        key="SpikeSlimeM", name="Spike Slime (M)", ids=("SpikeSlime_M",), hp_min=28,
        hp_max=37,
        moves=(
            _M("Flame Tackle", "ATTACK_DEBUFF", damage=8, hits=1,
               effect="also adds 1 {card:Slimed} to your discard pile."),
            _M("Lunge", "ATTACK", damage=9, hits=1),
        ),
        ai=("Random each round: 30% {move:Flame Tackle}, 70% {move:Lunge}; never the "
            "same move twice in a row.",),
        generates=("Slimed",),
        real_game="Real Spike Slime (M) has Lick (1 Frail) instead of a 9-damage Lunge."),
    EnemySpec(
        key="Hexaghost", name="Hexaghost", ids=("Hexaghost",), hp_min=250, hp_max=259,
        moves=(
            _M("Activate", "UNKNOWN", effect="does nothing."),
            _M("Divider", "ATTACK", hits=6,
               damage_text="6 hits of (your HP when the move is chosen, divided by 12, "
                           "rounded down, plus 1) damage"),
            _M("Inferno", "ATTACK", hits=6,
               damage_text="6 hits of 2 x k damage, where k counts this combat's uses "
                           "of {move:Inferno} including this one (2, 4, 6, ...)"),
            _M("Inflame", "BUFF", effect="gains 2 Strength and 12 Block."),
            _M("Sear", "ATTACK_DEBUFF", damage=6, hits=1,
               effect="also adds 1 {card:Burn} to your discard pile."),
        ),
        ai=("First move {move:Activate}; then a fixed 6-move cycle: {move:Divider}, "
            "{move:Inferno}, {move:Inflame}, {move:Inferno}, {move:Sear}, {move:Inferno}, "
            "repeating.",),
        deterministic_cycle=("Activate", "Divider", "Inferno", "Inflame", "Inferno",
                             "Sear", "Inferno", "Divider"),
        generates=("Burn",),
        real_game="Real Hexaghost: Activate, Divider once, then Sear/Tackle/Sear/Inflame/"
                  "Tackle/Sear/Inferno (Inferno once per cycle, upgrades Burns). Engine's "
                  "escalating triple Inferno is a large deviation."),
    EnemySpec(
        key="GremlinNob", name="Gremlin Nob", ids=("GremlinNob",), hp_min=82, hp_max=92,
        moves=(
            _M("Bellow", "BUFF", effect="gains {power:enrage} 2."),
            _M("Rush", "ATTACK", damage=14, hits=1),
            _M("Skull Bash", "ATTACK_DEBUFF", damage=6, hits=1,
               effect="also applies 2 Vulnerable to you."),
        ),
        ai=("First move {move:Bellow}. Next move is random: 33% {move:Rush}, 67% "
            "{move:Skull Bash}; after that it strictly alternates {move:Rush} and "
            "{move:Skull Bash}.",),
        real_game="Real Nob: 67% Rush / 33% Skull Bash, Rush at most twice in a row (no "
                  "forced alternation)."),
    EnemySpec(
        key="Sentry", name="Sentry", ids=("Sentry_0", "Sentry_1", "Sentry_2"), hp_min=38,
        hp_max=44, start_powers=(("Artifact", 1),),
        moves=(
            _M("Beam", "ATTACK", damage=9, hits=1),
            _M("Bolt", "DEBUFF", effect="adds 2 {card:Dazed} to the BOTTOM of your draw "
                                        "pile."),
        ),
        ai=("Alternates {move:Beam} and {move:Bolt}, starting with {move:Beam}. In this "
            "engine every {enemy:Sentry} in the fight starts with {move:Beam}, so a pair acts in "
            "sync.",),
        deterministic_cycle=("Beam", "Bolt", "Beam", "Bolt", "Beam", "Bolt"),
        generates=("Dazed",),
        real_game="Real Sentries alternate out of phase and Bolt shuffles Dazed into the "
                  "draw pile; engine: both instances get index 0 (identical id "
                  "'Sentry_0', in-phase Beams) and Dazed go to the bottom."),
]
ENEMY_SPECS: Dict[str, EnemySpec] = {e.key: e for e in _ENEMIES}
_ENEMY_BY_NAME = {e.name: e for e in _ENEMIES}

# ── relic specs ───────────────────────────────────────────────────────────────

_RELICS: List[RelicSpec] = [
    RelicSpec("Burning Blood", "ironclad",
              "At the end of combat, heal 6 HP. (Combat end is never reached inside the "
              "controlled-H utility, so it has no effect there.)"),
    RelicSpec("Ring of the Snake", "silent",
              "At the start of each combat, draw 2 additional cards (already applied "
              "before any fixture state)."),
]
RELIC_SPECS: Dict[str, RelicSpec] = {r.name: r for r in _RELICS}

# ── distinctive move names (renamed) ──────────────────────────────────────────

MOVE_NAMES = tuple(sorted({m.name for e in _ENEMIES for m in e.moves
                           if m.name not in GENERIC_MOVE_NAMES}))

RULES_TEXT = (
    "Rules (engine): 3 energy per turn, unspent energy is lost; draw 5 cards per turn; "
    "hand limit 10 (extra draws are lost, extra generated cards go to the discard pile); "
    "when the draw pile is empty the discard pile is shuffled into it. Your Block is "
    "removed at the start of your turn, an enemy's at the start of the enemy phase. "
    "Attack damage per hit = base + Strength, x0.75 if the attacker is Weak, x1.5 if the "
    "defender is Vulnerable (rounded down after each step). Weak/Vulnerable on an enemy "
    "drop by 1 right after that enemy acts; your debuffs drop by 1 at the end of the "
    "round (debuffs an enemy applied that round are skipped once). Exhaust: removed to "
    "the exhaust pile for the rest of combat. Ethereal: exhausted if still in hand at "
    "the end of your turn. Innate: starts combat in hand. Played Power cards go to the "
    "discard pile and can be drawn and played again (their effects stack). Automatic "
    "discard choice: the first Status/Curse in hand, else a {card:Strike}, else a "
    "{card:Defend}, else the first card in hand.")


# ── rendering ─────────────────────────────────────────────────────────────────

_REF_RE = re.compile(r"\{(card|enemy|relic|move|power|p):([^{}]+)\}")


def _fmt(template: str, spec: Optional[CardSpec] = None, n: Optional[int] = None,
         ref=None) -> str:
    """Resolve {card:X}/{enemy:X}/{relic:X}/{move:X}/{power:X} refs, {p:key} params
    and {n}. ``ref(kind, name)`` decides how a proper-name ref is printed (tests mark
    them to prove no unmarked proper name appears in rendered text)."""
    def sub(match):
        kind, value = match.group(1), match.group(2)
        if kind == "p":
            return str(spec.param(value))
        if kind == "move" and value in GENERIC_MOVE_NAMES:
            return value          # generic labels are kept, never renamed
        return ref(kind, value) if ref else value
    text = _REF_RE.sub(sub, template)
    if n is not None:
        text = text.replace("{n}", str(n))
    return text


_TYPE_WORD = {"ATTACK": "Attack", "SKILL": "Skill", "POWER": "Power",
              "STATUS": "Status"}


BASIC_KEYWORDS = ("Strength", "Dexterity", "Vulnerable", "Weak", "Frail", "Poison",
                  "Artifact", "Intangible", "Thorns")


def _power_label(power: str, ref=None) -> str:
    return power if power in KEPT_KEYWORDS else _fmt("{power:" + power + "}", ref=ref)


def _amount_phrase(power: str, amount: int, who: str, ref=None) -> str:
    """'apply 2 Vulnerable to the target enemy' / 'gain 3 Dexterity' / power detail."""
    if power in BASIC_KEYWORDS:
        if who == "self":
            verb = "gain" if amount >= 0 else "lose"
            return f"{verb} {abs(amount)} {power}"
        place = "the target enemy" if who == "target" else "ALL enemies"
        if amount < 0:
            return f"{place} lose {-amount} {power}"
        return f"apply {amount} {power} to {place}"
    detail = _fmt(POWER_SPECS[power].text, n=amount, ref=ref).rstrip(".")
    label = _power_label(power, ref)
    if who == "self":
        return f"gain {label} {amount} ({detail})"
    place = "the target enemy" if who == "target" else "ALL enemies"
    return f"give {place} {label} {amount} ({detail})"


def _sentence(text: str) -> str:
    text = text.strip()
    return text[:1].upper() + text[1:] + ("" if text.endswith(".") else ".")


def card_effect_sentences(spec: CardSpec, mode: str = "controlled_h",
                          ref=None) -> List[str]:
    """Ordered effect sentences of ``spec`` (without the header)."""
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}")
    out: List[str] = []
    if spec.hp_loss:
        out.append(f"Lose {spec.hp_loss} HP.")
    if spec.block:
        out.append(f"Gain {spec.block} Block.")
    if spec.damage and spec.hits:
        times = "" if spec.hits == 1 else f" {spec.hits} times"
        if spec.target == "enemy":
            out.append(f"Deal {spec.damage} damage to the target enemy{times}.")
        elif spec.target == "all":
            out.append(f"Deal {spec.damage} damage to ALL enemies{times}.")
        elif spec.target == "random":
            out.append(f"Deal {spec.damage} damage to a random enemy{times} (re-chosen "
                       f"each hit).")
    elif spec.damage and spec.target == "enemy":   # X-hit attack (Skewer)
        out.append(f"Damage per hit: {spec.damage}.")
    targeted = [_amount_phrase(p, a, "target", ref) for p, a in spec.target_powers]
    if targeted and not spec.targeted_skill:
        out.append(_sentence(" and ".join(targeted)))
    for p, a in spec.all_enemy_powers:
        out.append(_sentence(_amount_phrase(p, a, "all", ref)))
    for p, a in spec.self_powers:
        out.append(_sentence(_amount_phrase(p, a, "self", ref)))
    if spec.energy:
        out.append(f"Gain {spec.energy} energy.")
    if spec.draw:
        out.append(f"Draw {spec.draw} card{'s' if spec.draw != 1 else ''}.")
    clause_text = [_sentence(_fmt(c, spec, ref=ref)) for c in spec.clauses]
    if spec.targeted_skill:
        intended = ([_sentence(t) for t in targeted]
                    + [_sentence(_fmt(c, spec, ref=ref)) for c in spec.target_clauses])
        if mode == "engine":
            out.extend(intended)
        else:
            out.append("Intended effect: " + " ".join(intended) + " BUT this interface "
                       "plays Skills without a target, so this enemy effect never "
                       "happens.")
    out.extend(clause_text)
    flags = [w for w, on in (("Exhaust", spec.exhaust), ("Ethereal", spec.ethereal),
                             ("Innate", spec.innate), ("Retain", spec.retain)) if on]
    if flags:
        out.append(". ".join(flags) + ".")
    return out


def render_card_spec(spec: CardSpec, mode: str = "controlled_h", ref=None,
                     current_damage: Optional[int] = None) -> str:
    kind = _TYPE_WORD[spec.type]
    if spec.unplayable:
        head = f"{kind}, Unplayable."
    elif spec.cost == -2:
        head = f"{kind}, cost X."
    else:
        head = f"{kind}, cost {spec.cost}."
    body = card_effect_sentences(spec, mode, ref)
    if current_damage is not None and current_damage != spec.damage:
        body.append(f"(This copy currently deals {current_damage} per hit.)")
    return " ".join([head] + body)


def card_spec_for(card) -> CardSpec:
    """Spec for an engine card object (identity of id + upgrade level)."""
    spec = CARD_SPECS.get(card.id)
    if spec is None:
        raise KeyError(f"no effect-text spec for card id {card.id!r}")
    if bool(card.upgraded) != spec.upgraded:
        raise KeyError(f"no spec for {card.id!r} upgraded={card.upgraded}: upgraded "
                       "cards never occur in the v3 release fixtures")
    return spec


def describe_card(card, mode: str = "controlled_h", ref=None) -> str:
    """Engine-faithful description of a card object (or a card id string)."""
    if isinstance(card, str):
        return render_card_spec(CARD_SPECS[card], mode, ref)
    spec = card_spec_for(card)
    current = getattr(card, "_dmg", None)  # Glass Knife per-copy decay
    return render_card_spec(spec, mode, ref, current_damage=current)


def _enemy_spec_for(enemy) -> EnemySpec:
    if isinstance(enemy, str):
        if enemy in ENEMY_SPECS:
            return ENEMY_SPECS[enemy]
        if enemy in _ENEMY_BY_NAME:
            return _ENEMY_BY_NAME[enemy]
        raise KeyError(f"no enemy spec for {enemy!r}")
    key = type(enemy).__name__
    if key not in ENEMY_SPECS:
        raise KeyError(f"no enemy spec for {key!r}")
    return ENEMY_SPECS[key]


def _render_move(move: MoveSpec, ref=None) -> str:
    label = _fmt("{move:" + move.name + "}", ref=ref) \
        if move.name not in GENERIC_MOVE_NAMES else move.name
    if move.damage_text:
        dmg = _fmt(move.damage_text, ref=ref)
    elif move.damage:
        dmg = f"{move.damage} damage" + ("" if move.hits == 1 else f" x{move.hits}")
    else:
        dmg = ""
    effect = _fmt(move.effect, ref=ref) if move.effect else ""
    if dmg and effect:
        return f"{label}: {dmg}; {effect}"
    return f"{label}: {dmg or effect}".rstrip()


def describe_enemy(enemy, ref=None) -> str:
    """Engine-faithful move set + AI rule of an enemy (object, class key or name)."""
    spec = _enemy_spec_for(enemy)
    parts = [f"HP {spec.hp_min}-{spec.hp_max}."]
    if spec.start_powers:
        parts.append("Starts with " + ", ".join(
            f"{_power_label(p, ref)} {a}"
            for p, a in spec.start_powers) + ".")
    parts.append("Moves: " + "; ".join(
        _render_move(m, ref).rstrip(".") for m in spec.moves) + ".")
    parts.extend(_fmt(rule, ref=ref) for rule in spec.ai)
    parts.append("Attack damage shown in its intent already includes its Strength and "
                 "Weak.")
    return " ".join(parts)


def describe_relic(relic, ref=None) -> str:
    name = relic if isinstance(relic, str) else relic.name
    return RELIC_SPECS[name].text


def describe_power(power: str, amount: Optional[int] = None, ref=None) -> str:
    key = power.value if hasattr(power, "value") else str(power)
    return _fmt(POWER_SPECS[key].text, n=amount if amount is not None else "N", ref=ref)


# ── appendix ──────────────────────────────────────────────────────────────────

def _all_cards(state) -> List[Any]:
    c = state.combat
    return list(c.hand) + list(c.draw_pile) + list(c.discard_pile) + list(c.exhaust_pile)


def appendix_entities(state) -> Dict[str, List[str]]:
    """Card ids / enemy keys / relic names / power keys covered by the appendix:
    everything visible in the state plus everything that can be generated from it
    (Shiv, Deflect, Slimed, Dazed, Burn, split children)."""
    card_ids: List[str] = []
    seen = set()

    def add_card_id(cid):
        if cid not in seen:
            seen.add(cid)
            card_ids.append(cid)
    for card in _all_cards(state):
        add_card_id(card.id)
    enemy_keys: List[str] = []
    queue = [type(e).__name__ for e in state.combat.enemies]
    while queue:
        key = queue.pop(0)
        if key in enemy_keys:
            continue
        enemy_keys.append(key)
        for child in ENEMY_SPECS[key].spawns:
            queue.append(_ENEMY_BY_NAME[child].key)
    by_name = {s.name: s.id for s in _CARDS
               if s.character in ("any", state.character)}
    frontier = list(card_ids)
    for key in enemy_keys:
        frontier.extend(by_name[n] for n in ENEMY_SPECS[key].generates)
    while frontier:
        cid = frontier.pop(0)
        add_card_id(cid)
        frontier.extend(by_name[n] for n in CARD_SPECS[cid].generates
                        if by_name[n] not in seen)
    powers: List[str] = []

    def add_power(p):
        p = p.value if hasattr(p, "value") else str(p)
        if p not in powers:
            powers.append(p)
    for p in state.player.powers:
        add_power(p)
    for e in state.combat.enemies:
        for p in e.powers:
            add_power(p)
    for cid in card_ids:
        spec = CARD_SPECS[cid]
        for p, _ in spec.self_powers + spec.target_powers + spec.all_enemy_powers:
            add_power(p)
    for key in enemy_keys:
        for p, _ in ENEMY_SPECS[key].start_powers:
            add_power(p)
        if key == "GremlinNob":
            add_power("enrage")
    relics = [r.name for r in state.player.relics]
    return {"cards": card_ids, "enemies": enemy_keys, "relics": relics,
            "powers": powers}


def effects_appendix(state, mode: str = "controlled_h", ref=None) -> str:
    """Text for every card/enemy/relic/power visible in (or generable from) ``state``."""
    ent = appendix_entities(state)
    name_of = lambda kind, n: _fmt("{" + kind + ":" + n + "}", ref=ref)  # noqa: E731
    lines = ["=== EFFECT REFERENCE (exact engine rules) ===", _fmt(RULES_TEXT, ref=ref),
             "", "Cards:"]
    printed = set()
    for cid in ent["cards"]:
        spec = CARD_SPECS[cid]
        if spec.name in printed:   # Strike_R / Strike_G share a display name
            continue
        printed.add(spec.name)
        lines.append(f"- {name_of('card', spec.name)}: "
                     f"{render_card_spec(spec, mode, ref)}")
    lines += ["", "Enemies:"]
    for key in ent["enemies"]:
        spec = ENEMY_SPECS[key]
        lines.append(f"- {name_of('enemy', spec.name)}: {describe_enemy(key, ref)}")
    if ent["relics"]:
        lines += ["", "Relics:"]
        for name in ent["relics"]:
            lines.append(f"- {name_of('relic', name)}: {describe_relic(name, ref)}")
    lines += ["", "Effects (stack amount N):"]
    for p in ent["powers"]:
        lines.append(f"- {_power_label(p, ref)}: {describe_power(p, None, ref)}")
    return "\n".join(lines)


# ── neutral renaming ──────────────────────────────────────────────────────────

# Engine ids that are aliases of a display name (renamed to the same token).
NAME_ALIASES: Dict[str, str] = {
    "Strike_R": "Strike", "Strike_G": "Strike",
    "Defend_R": "Defend", "Defend_G": "Defend",
}
for _e in _ENEMIES:
    for _alias in _e.ids:
        if _alias != _e.name:
            NAME_ALIASES[_alias] = _e.name
for _e in _ENEMIES:
    if _e.key != _e.name:
        NAME_ALIASES.setdefault(_e.key, _e.name)

CARD_NAMES = tuple(sorted({s.name for s in _CARDS}))
ENEMY_NAMES = tuple(sorted({e.name for e in _ENEMIES}))
RELIC_NAMES = tuple(sorted(RELIC_SPECS))
PROPER_POWER_NAMES = tuple(sorted(p.name for p in _POWERS
                                  if p.proper and p.name not in CARD_NAMES))


def name_category(name: str) -> str:
    """Category used for the neutral token prefix (card > enemy > relic > move >
    power > context)."""
    if name in CARD_NAMES:
        return "Card"
    if name in ENEMY_NAMES:
        return "Enemy"
    if name in RELIC_NAMES:
        return "Relic"
    if name in MOVE_NAMES:
        return "Move"
    if name in PROPER_POWER_NAMES:
        return "Effect"
    if name in CONTEXT_NAMES:
        return "Context"
    raise KeyError(f"{name!r} is not a known proper name")


def all_proper_names(include_context: bool = False) -> Tuple[str, ...]:
    names = set(CARD_NAMES) | set(ENEMY_NAMES) | set(RELIC_NAMES) | set(MOVE_NAMES) \
        | set(PROPER_POWER_NAMES)
    if include_context:
        names |= set(CONTEXT_NAMES)
    return tuple(sorted(names))


def proper_names_in_state(state) -> Tuple[str, ...]:
    """Every proper name the prompt or the effects appendix of ``state`` can contain:
    the names the appendix renders as refs (which covers all cards, enemies, moves,
    relics and card-named powers visible in the state) plus proper power keys."""
    seen: set = set()

    def collect(kind, name):
        seen.add(name)
        return name
    effects_appendix(state, ref=collect)
    for p in list(state.player.powers) + [p for e in state.combat.enemies
                                          for p in e.powers]:
        key = p.value if hasattr(p, "value") else str(p)
        if key in CARD_NAMES or key in PROPER_POWER_NAMES:
            seen.add(key)
    return tuple(sorted(seen))


_CODE_LETTERS = "ABCDEFGHJKLMNPQRSTUVWXYZ"   # no I/O (look like digits)
_CODE_DIGITS = "23456789"


def _h(seed: int, *parts: str) -> str:
    return hashlib.sha256(("\x1f".join((str(seed),) + parts)).encode()).hexdigest()


def neutral_name_map(names: Iterable[str], seed: int) -> Dict[str, str]:
    """Deterministic bijection proper-name -> neutral token for one seed.

    Tokens: ``Card K7`` / ``Relic Q3`` / ``Move M4`` / ``Effect E5`` / ``Context C2``
    (one shared pool of letter+digit codes, so tokens are unique across categories)
    and ``Enemy B`` (single letter). Order is a SHA-256 ranking keyed on
    (seed, name), so it is identical across processes, platforms and Python versions.
    Aliases (engine ids such as ``Strike_R``) are not keys: ``rename`` maps them to
    their display name's token. Build ONE map over the full vocabulary
    (``all_proper_names()``) per seed so a name has the same token in every fixture.
    """
    canon = sorted({NAME_ALIASES.get(n, n) for n in names})
    for n in canon:
        name_category(n)  # raises on unknown names
    codes = sorted((l + d for l in _CODE_LETTERS for d in _CODE_DIGITS),
                   key=lambda code: _h(seed, "code", code))
    letters = sorted(_CODE_LETTERS, key=lambda c: _h(seed, "enemy-letter", c))
    ranked = sorted(canon, key=lambda n: _h(seed, "name", n))
    mapping: Dict[str, str] = {}
    ci = li = 0
    for name in ranked:
        cat = name_category(name)
        if cat == "Enemy":
            if li >= len(letters):
                raise ValueError("too many enemy names for single-letter tokens")
            mapping[name] = f"Enemy {letters[li]}"
            li += 1
        else:
            if ci >= len(codes):
                raise ValueError("neutral code pool exhausted")
            mapping[name] = f"{cat} {codes[ci]}"
            ci += 1
    return mapping


def _expanded(mapping: Mapping[str, str]) -> Dict[str, str]:
    full = dict(mapping)
    for alias, canon in NAME_ALIASES.items():
        if canon in mapping and alias not in full:
            full[alias] = mapping[canon]
    return full


_PATTERN_CACHE: Dict[Tuple[Tuple[str, str], ...], Tuple[re.Pattern, Dict[str, str]]] = {}


def _pattern(mapping: Mapping[str, str]):
    key = tuple(sorted(mapping.items()))
    hit = _PATTERN_CACHE.get(key)
    if hit is None:
        full = _expanded(mapping)
        names = sorted(full, key=lambda n: (-len(n), n))
        if not names:
            hit = (None, full)
        else:
            alt = "|".join(re.escape(n) for n in names)
            hit = (re.compile(r"(?<![A-Za-z0-9_])(?:" + alt + r")(?![A-Za-z0-9_])"),
                   full)
        _PATTERN_CACHE[key] = hit
    return hit


def rename(obj: Any, mapping: Mapping[str, str]) -> Any:
    """Replace every whole-word, case-sensitive occurrence of a mapped proper name
    (or one of its engine-id aliases) in a string, or recursively in the keys and
    string values of a JSON-like payload. Single regex pass, longest name first, so
    replacements never chain and 'Pommel Strike' never becomes 'Pommel Card K7'."""
    pattern, full = _pattern(mapping)
    if pattern is None:
        return obj

    def go(x):
        if isinstance(x, str):
            return pattern.sub(lambda m: full[m.group(0)], x)
        if isinstance(x, dict):
            return {go(k): go(v) for k, v in x.items()}
        if isinstance(x, list):
            return [go(v) for v in x]
        if isinstance(x, tuple):
            return tuple(go(v) for v in x)
        return x
    return go(obj)


def release_name_map(seed: int, include_context: bool = False) -> Dict[str, str]:
    """The recommended map: full v3 vocabulary, one seed."""
    return neutral_name_map(all_proper_names(include_context), seed)
