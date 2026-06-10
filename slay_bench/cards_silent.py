"""Card definitions for the Silent.

Mechanics live in the shared engine (cards.py / combat.py / powers.py):
poison (block-bypassing tick), shivs, manual-discard triggers, dexterity,
hand limit, Burst/After Image/A Thousand Cuts/etc. power hooks.

Documented simplifications (player-choice effects use a deterministic rule so
the simulator stays choice-free below the LLM decision layer):
- "discard a card" picks via _auto_discard_choice (status/curse > Strike > Defend > first).
- Setup / Nightmare act on the first other card in hand.
- Masterful Stab has a fixed cost of 2 (real card scales with HP loss).
- Piercing Wail's Strength reduction is permanent (real card restores it next turn).
- Distraction adds a Deflect (real card adds a random 0-cost skill).
- Bullet Time zeroes current hand costs for the turn (cannot-draw clause omitted).
"""
from __future__ import annotations
from typing import Optional

from .enums import CardType, CardRarity, PowerId
from .cards import (
    Card,
    _deal_damage, _apply_damage_to_enemy, _damage_player, _gain_block,
    _apply_power, _draw_cards, _exhaust_card,
    _add_card_to_hand, _discard_from_hand, _auto_discard_choice,
)


def _alive(state):
    return [e for e in state.combat.enemies if e.hp > 0]


def _random_alive(state):
    alive = _alive(state)
    if not alive:
        return None
    return alive[state.rng.misc_rng.next_int(len(alive))]


# ── Special ───────────────────────────────────────────────────────────────────

class Shiv(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Shiv", "Shiv", CardType.ATTACK, CardRarity.SPECIAL, 0,
                         upgraded, exhaust=True)

    def play(self, state, target=None):
        dmg = (6 if self.upgraded else 4) + state.player.powers.get(PowerId.ACCURACY, 0)
        if target:
            _deal_damage(state, target, dmg)

    def upgrade(self):
        self.upgraded = True


# ── Basics ────────────────────────────────────────────────────────────────────

class StrikeG(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Strike_G", "Strike", CardType.ATTACK, CardRarity.BASIC, 1, upgraded)

    def play(self, state, target=None):
        _deal_damage(state, target, 9 if self.upgraded else 6)

    def upgrade(self):
        self.upgraded = True


class DefendG(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Defend_G", "Defend", CardType.SKILL, CardRarity.BASIC, 1, upgraded)

    def play(self, state, target=None):
        _gain_block(state, 8 if self.upgraded else 5)

    def upgrade(self):
        self.upgraded = True


class Neutralize(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Neutralize", "Neutralize", CardType.ATTACK, CardRarity.BASIC, 0, upgraded)

    def play(self, state, target=None):
        _deal_damage(state, target, 4 if self.upgraded else 3)
        if target:
            _apply_power(state, target, PowerId.WEAK, 2 if self.upgraded else 1)

    def upgrade(self):
        self.upgraded = True


class Survivor(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Survivor", "Survivor", CardType.SKILL, CardRarity.BASIC, 1, upgraded)

    def play(self, state, target=None):
        _gain_block(state, 11 if self.upgraded else 8)
        pick = _auto_discard_choice(state)
        if pick:
            _discard_from_hand(state, pick)

    def upgrade(self):
        self.upgraded = True


# ── Commons ───────────────────────────────────────────────────────────────────

class Acrobatics(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Acrobatics", "Acrobatics", CardType.SKILL, CardRarity.COMMON, 1, upgraded)

    def play(self, state, target=None):
        _draw_cards(state, 4 if self.upgraded else 3)
        pick = _auto_discard_choice(state)
        if pick:
            _discard_from_hand(state, pick)

    def upgrade(self):
        self.upgraded = True


class Backflip(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Backflip", "Backflip", CardType.SKILL, CardRarity.COMMON, 1, upgraded)

    def play(self, state, target=None):
        _gain_block(state, 8 if self.upgraded else 5)
        _draw_cards(state, 2)

    def upgrade(self):
        self.upgraded = True


class Bane(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Bane", "Bane", CardType.ATTACK, CardRarity.COMMON, 1, upgraded)

    def play(self, state, target=None):
        dmg = 10 if self.upgraded else 7
        _deal_damage(state, target, dmg)
        if target and target.hp > 0 and PowerId.POISON in target.powers:
            _deal_damage(state, target, dmg)

    def upgrade(self):
        self.upgraded = True


class BladeDance(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Blade Dance", "Blade Dance", CardType.SKILL, CardRarity.COMMON, 1, upgraded)

    def play(self, state, target=None):
        for _ in range(4 if self.upgraded else 3):
            _add_card_to_hand(state, Shiv())

    def upgrade(self):
        self.upgraded = True


class CloakAndDagger(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Cloak and Dagger", "Cloak and Dagger", CardType.SKILL, CardRarity.COMMON, 1, upgraded)

    def play(self, state, target=None):
        _gain_block(state, 6)
        for _ in range(2 if self.upgraded else 1):
            _add_card_to_hand(state, Shiv())

    def upgrade(self):
        self.upgraded = True


class DaggerSpray(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Dagger Spray", "Dagger Spray", CardType.ATTACK, CardRarity.COMMON, 1, upgraded)

    def play(self, state, target=None):
        dmg = 6 if self.upgraded else 4
        for _ in range(2):
            for e in _alive(state):
                _deal_damage(state, e, dmg)

    def upgrade(self):
        self.upgraded = True


class DaggerThrow(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Dagger Throw", "Dagger Throw", CardType.ATTACK, CardRarity.COMMON, 1, upgraded)

    def play(self, state, target=None):
        _deal_damage(state, target, 12 if self.upgraded else 9)
        _draw_cards(state, 1)
        pick = _auto_discard_choice(state)
        if pick:
            _discard_from_hand(state, pick)

    def upgrade(self):
        self.upgraded = True


class DeadlyPoison(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Deadly Poison", "Deadly Poison", CardType.SKILL, CardRarity.COMMON, 1, upgraded)

    def play(self, state, target=None):
        if target:
            _apply_power(state, target, PowerId.POISON, 7 if self.upgraded else 5)

    def upgrade(self):
        self.upgraded = True


class Deflect(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Deflect", "Deflect", CardType.SKILL, CardRarity.COMMON, 0, upgraded)

    def play(self, state, target=None):
        _gain_block(state, 7 if self.upgraded else 4)

    def upgrade(self):
        self.upgraded = True


class DodgeAndRoll(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Dodge and Roll", "Dodge and Roll", CardType.SKILL, CardRarity.COMMON, 1, upgraded)

    def play(self, state, target=None):
        amt = 6 if self.upgraded else 4
        _gain_block(state, amt)
        p = state.player.powers
        p[PowerId.NEXT_TURN_BLOCK] = p.get(PowerId.NEXT_TURN_BLOCK, 0) + amt

    def upgrade(self):
        self.upgraded = True


class FlyingKnee(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Flying Knee", "Flying Knee", CardType.ATTACK, CardRarity.COMMON, 1, upgraded)

    def play(self, state, target=None):
        _deal_damage(state, target, 11 if self.upgraded else 8)
        p = state.player.powers
        p[PowerId.ENERGIZED] = p.get(PowerId.ENERGIZED, 0) + 1

    def upgrade(self):
        self.upgraded = True


class Outmaneuver(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Outmaneuver", "Outmaneuver", CardType.SKILL, CardRarity.COMMON, 1, upgraded)

    def play(self, state, target=None):
        p = state.player.powers
        p[PowerId.ENERGIZED] = p.get(PowerId.ENERGIZED, 0) + (3 if self.upgraded else 2)

    def upgrade(self):
        self.upgraded = True


class PiercingWail(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Piercing Wail", "Piercing Wail", CardType.SKILL, CardRarity.COMMON, 1,
                         upgraded, exhaust=True)

    def play(self, state, target=None):
        amt = 8 if self.upgraded else 6
        for e in _alive(state):
            e.powers[PowerId.STRENGTH] = e.powers.get(PowerId.STRENGTH, 0) - amt
        _exhaust_card(state, self)

    def upgrade(self):
        self.upgraded = True


class PoisonedStab(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Poisoned Stab", "Poisoned Stab", CardType.ATTACK, CardRarity.COMMON, 1, upgraded)

    def play(self, state, target=None):
        _deal_damage(state, target, 8 if self.upgraded else 6)
        if target and target.hp > 0:
            _apply_power(state, target, PowerId.POISON, 4 if self.upgraded else 3)

    def upgrade(self):
        self.upgraded = True


class Prepared(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Prepared", "Prepared", CardType.SKILL, CardRarity.COMMON, 0, upgraded)

    def play(self, state, target=None):
        n = 2 if self.upgraded else 1
        _draw_cards(state, n)
        for _ in range(n):
            pick = _auto_discard_choice(state)
            if pick:
                _discard_from_hand(state, pick)

    def upgrade(self):
        self.upgraded = True


class QuickSlash(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Quick Slash", "Quick Slash", CardType.ATTACK, CardRarity.COMMON, 1, upgraded)

    def play(self, state, target=None):
        _deal_damage(state, target, 12 if self.upgraded else 8)
        _draw_cards(state, 1)

    def upgrade(self):
        self.upgraded = True


class Slice(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Slice", "Slice", CardType.ATTACK, CardRarity.COMMON, 0, upgraded)

    def play(self, state, target=None):
        _deal_damage(state, target, 9 if self.upgraded else 6)

    def upgrade(self):
        self.upgraded = True


class SneakyStrike(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Sneaky Strike", "Sneaky Strike", CardType.ATTACK, CardRarity.COMMON, 2, upgraded)

    def play(self, state, target=None):
        _deal_damage(state, target, 16 if self.upgraded else 12)
        if state.combat.discarded_this_turn > 0:
            state.player.energy += 2

    def upgrade(self):
        self.upgraded = True


class SuckerPunch(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Sucker Punch", "Sucker Punch", CardType.ATTACK, CardRarity.COMMON, 1, upgraded)

    def play(self, state, target=None):
        _deal_damage(state, target, 9 if self.upgraded else 7)
        if target and target.hp > 0:
            _apply_power(state, target, PowerId.WEAK, 2 if self.upgraded else 1)

    def upgrade(self):
        self.upgraded = True


# ── Uncommons ─────────────────────────────────────────────────────────────────

class Accuracy(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Accuracy", "Accuracy", CardType.POWER, CardRarity.UNCOMMON, 1, upgraded)

    def play(self, state, target=None):
        p = state.player.powers
        p[PowerId.ACCURACY] = p.get(PowerId.ACCURACY, 0) + (6 if self.upgraded else 4)

    def upgrade(self):
        self.upgraded = True


class AllOutAttack(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("All-Out Attack", "All-Out Attack", CardType.ATTACK, CardRarity.UNCOMMON, 1, upgraded)

    def play(self, state, target=None):
        dmg = 14 if self.upgraded else 10
        for e in _alive(state):
            _deal_damage(state, e, dmg)
        # discard 1 random card
        hand = state.combat.hand
        if hand:
            idx = state.rng.misc_rng.next_int(len(hand))
            _discard_from_hand(state, hand[idx])

    def upgrade(self):
        self.upgraded = True


class Backstab(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Backstab", "Backstab", CardType.ATTACK, CardRarity.UNCOMMON, 0,
                         upgraded, exhaust=True, innate=True)

    def play(self, state, target=None):
        _deal_damage(state, target, 15 if self.upgraded else 11)
        _exhaust_card(state, self)

    def upgrade(self):
        self.upgraded = True


class Blur(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Blur", "Blur", CardType.SKILL, CardRarity.UNCOMMON, 1, upgraded)

    def play(self, state, target=None):
        _gain_block(state, 8 if self.upgraded else 5)
        p = state.player.powers
        p[PowerId.BLUR] = p.get(PowerId.BLUR, 0) + 1

    def upgrade(self):
        self.upgraded = True


class BouncingFlask(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Bouncing Flask", "Bouncing Flask", CardType.SKILL, CardRarity.UNCOMMON, 2, upgraded)

    def play(self, state, target=None):
        for _ in range(4 if self.upgraded else 3):
            e = _random_alive(state)
            if e:
                _apply_power(state, e, PowerId.POISON, 3)

    def upgrade(self):
        self.upgraded = True


class CalculatedGamble(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Calculated Gamble", "Calculated Gamble", CardType.SKILL, CardRarity.UNCOMMON, 0,
                         upgraded, exhaust=not upgraded)

    def play(self, state, target=None):
        n = len(state.combat.hand)
        for card in list(state.combat.hand):
            _discard_from_hand(state, card)
        _draw_cards(state, n)
        if self.exhaust:
            _exhaust_card(state, self)

    def upgrade(self):
        self.upgraded = True
        self.exhaust = False


class Caltrops(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Caltrops", "Caltrops", CardType.POWER, CardRarity.UNCOMMON, 1, upgraded)

    def play(self, state, target=None):
        p = state.player.powers
        p[PowerId.THORNS] = p.get(PowerId.THORNS, 0) + (5 if self.upgraded else 3)

    def upgrade(self):
        self.upgraded = True


class Catalyst(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Catalyst", "Catalyst", CardType.SKILL, CardRarity.UNCOMMON, 1,
                         upgraded, exhaust=True)

    def play(self, state, target=None):
        if target and PowerId.POISON in target.powers:
            mult = 3 if self.upgraded else 2
            target.powers[PowerId.POISON] *= mult
        _exhaust_card(state, self)

    def upgrade(self):
        self.upgraded = True


class Choke(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Choke", "Choke", CardType.ATTACK, CardRarity.UNCOMMON, 2, upgraded)

    def play(self, state, target=None):
        _deal_damage(state, target, 12)
        if target and target.hp > 0:
            _apply_power(state, target, PowerId.CHOKED, 5 if self.upgraded else 3)

    def upgrade(self):
        self.upgraded = True


class Concentrate(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Concentrate", "Concentrate", CardType.SKILL, CardRarity.UNCOMMON, 0, upgraded)

    def play(self, state, target=None):
        for _ in range(2 if self.upgraded else 3):
            pick = _auto_discard_choice(state)
            if pick:
                _discard_from_hand(state, pick)
        state.player.energy += 2

    def upgrade(self):
        self.upgraded = True


class CripplingCloud(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Crippling Cloud", "Crippling Cloud", CardType.SKILL, CardRarity.UNCOMMON, 2,
                         upgraded, exhaust=True)

    def play(self, state, target=None):
        for e in _alive(state):
            _apply_power(state, e, PowerId.POISON, 7 if self.upgraded else 4)
            _apply_power(state, e, PowerId.WEAK, 2)
        _exhaust_card(state, self)

    def upgrade(self):
        self.upgraded = True


class Dash(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Dash", "Dash", CardType.ATTACK, CardRarity.UNCOMMON, 2, upgraded)

    def play(self, state, target=None):
        amt = 13 if self.upgraded else 10
        _gain_block(state, amt)
        _deal_damage(state, target, amt)

    def upgrade(self):
        self.upgraded = True


class Distraction(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Distraction", "Distraction", CardType.SKILL, CardRarity.UNCOMMON,
                         0 if upgraded else 1, upgraded, exhaust=True)

    def play(self, state, target=None):
        _add_card_to_hand(state, Deflect())  # simplification: random 0-cost skill
        _exhaust_card(state, self)

    def upgrade(self):
        self.upgraded = True
        self.cost = 0


class EndlessAgony(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Endless Agony", "Endless Agony", CardType.ATTACK, CardRarity.UNCOMMON, 0,
                         upgraded, exhaust=True)

    def play(self, state, target=None):
        _deal_damage(state, target, 6 if self.upgraded else 4)
        _exhaust_card(state, self)

    def on_drawn(self, state):
        _add_card_to_hand(state, self.copy())

    def upgrade(self):
        self.upgraded = True


class EscapePlan(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Escape Plan", "Escape Plan", CardType.SKILL, CardRarity.UNCOMMON, 0, upgraded)

    def play(self, state, target=None):
        before = list(state.combat.hand)
        _draw_cards(state, 1)
        drawn = [c for c in state.combat.hand if c not in before]
        if drawn and drawn[0].type == CardType.SKILL:
            _gain_block(state, 5 if self.upgraded else 3)

    def upgrade(self):
        self.upgraded = True


class Eviscerate(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Eviscerate", "Eviscerate", CardType.ATTACK, CardRarity.UNCOMMON, 3, upgraded)

    def effective_cost(self) -> int:
        if self.cost_override is not None:
            return self.cost_override
        return max(0, self.cost)

    def can_play(self, state) -> bool:
        # Cost falls by 1 per card discarded this turn
        self.cost_override = None
        if state.combat is not None:
            self.cost_override = max(0, 3 - state.combat.discarded_this_turn)
        return super().can_play(state)

    def play(self, state, target=None):
        dmg = 9 if self.upgraded else 7
        for _ in range(3):
            if target and target.hp > 0:
                _deal_damage(state, target, dmg)

    def upgrade(self):
        self.upgraded = True


class Expertise(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Expertise", "Expertise", CardType.SKILL, CardRarity.UNCOMMON, 1, upgraded)

    def play(self, state, target=None):
        limit = 7 if self.upgraded else 6
        n = limit - len(state.combat.hand)
        if n > 0:
            _draw_cards(state, n)

    def upgrade(self):
        self.upgraded = True


class Finisher(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Finisher", "Finisher", CardType.ATTACK, CardRarity.UNCOMMON, 1, upgraded)

    def play(self, state, target=None):
        dmg = 8 if self.upgraded else 6
        for _ in range(state.combat.attacks_played_this_turn):
            if target and target.hp > 0:
                _deal_damage(state, target, dmg)

    def upgrade(self):
        self.upgraded = True


class Flechettes(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Flechettes", "Flechettes", CardType.ATTACK, CardRarity.UNCOMMON, 1, upgraded)

    def play(self, state, target=None):
        dmg = 6 if self.upgraded else 4
        skills = sum(1 for c in state.combat.hand if c.type == CardType.SKILL)
        for _ in range(skills):
            if target and target.hp > 0:
                _deal_damage(state, target, dmg)

    def upgrade(self):
        self.upgraded = True


class Footwork(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Footwork", "Footwork", CardType.POWER, CardRarity.UNCOMMON, 1, upgraded)

    def play(self, state, target=None):
        p = state.player.powers
        p[PowerId.DEXTERITY] = p.get(PowerId.DEXTERITY, 0) + (3 if self.upgraded else 2)

    def upgrade(self):
        self.upgraded = True


class HeelHook(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Heel Hook", "Heel Hook", CardType.ATTACK, CardRarity.UNCOMMON, 1, upgraded)

    def play(self, state, target=None):
        _deal_damage(state, target, 8 if self.upgraded else 5)
        if target and PowerId.WEAK in target.powers:
            state.player.energy += 1
            _draw_cards(state, 1)

    def upgrade(self):
        self.upgraded = True


class InfiniteBlades(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Infinite Blades", "Infinite Blades", CardType.POWER, CardRarity.UNCOMMON, 1,
                         upgraded, innate=upgraded)

    def play(self, state, target=None):
        p = state.player.powers
        p[PowerId.INFINITE_BLADES] = p.get(PowerId.INFINITE_BLADES, 0) + 1

    def upgrade(self):
        self.upgraded = True
        self.innate = True


class LegSweep(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Leg Sweep", "Leg Sweep", CardType.SKILL, CardRarity.UNCOMMON, 2, upgraded)

    def play(self, state, target=None):
        _gain_block(state, 14 if self.upgraded else 11)
        if target:
            _apply_power(state, target, PowerId.WEAK, 3 if self.upgraded else 2)

    def upgrade(self):
        self.upgraded = True


class MasterfulStab(Card):
    def __init__(self, upgraded: bool = False):
        # Simplification: fixed cost 2 (real card: 0, +1 per HP-loss this combat)
        super().__init__("Masterful Stab", "Masterful Stab", CardType.ATTACK, CardRarity.UNCOMMON, 2, upgraded)

    def play(self, state, target=None):
        _deal_damage(state, target, 16 if self.upgraded else 12)

    def upgrade(self):
        self.upgraded = True


class NoxiousFumes(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Noxious Fumes", "Noxious Fumes", CardType.POWER, CardRarity.UNCOMMON, 1, upgraded)

    def play(self, state, target=None):
        p = state.player.powers
        p[PowerId.NOXIOUS_FUMES] = p.get(PowerId.NOXIOUS_FUMES, 0) + (3 if self.upgraded else 2)

    def upgrade(self):
        self.upgraded = True


class Predator(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Predator", "Predator", CardType.ATTACK, CardRarity.UNCOMMON, 2, upgraded)

    def play(self, state, target=None):
        _deal_damage(state, target, 20 if self.upgraded else 15)
        p = state.player.powers
        p[PowerId.NEXT_TURN_DRAW] = p.get(PowerId.NEXT_TURN_DRAW, 0) + 2

    def upgrade(self):
        self.upgraded = True


class Reflex(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Reflex", "Reflex", CardType.SKILL, CardRarity.UNCOMMON, -1,
                         upgraded, unplayable=True)

    def play(self, state, target=None):
        pass

    def on_manual_discard(self, state):
        _draw_cards(state, 3 if self.upgraded else 2)

    def upgrade(self):
        self.upgraded = True


class RiddleWithHoles(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Riddle with Holes", "Riddle with Holes", CardType.ATTACK, CardRarity.UNCOMMON, 2, upgraded)

    def play(self, state, target=None):
        dmg = 4 if self.upgraded else 3
        for _ in range(5):
            if target and target.hp > 0:
                _deal_damage(state, target, dmg)

    def upgrade(self):
        self.upgraded = True


class Setup(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Setup", "Setup", CardType.SKILL, CardRarity.UNCOMMON,
                         0 if upgraded else 1, upgraded)

    def play(self, state, target=None):
        # Simplification: first other card in hand goes on top of the draw pile, costs 0
        others = [c for c in state.combat.hand if c is not self]
        if others:
            card = others[0]
            state.combat.hand.remove(card)
            card.cost_override = 0
            state.combat.draw_pile.append(card)  # draw pops from the end = top

    def upgrade(self):
        self.upgraded = True
        self.cost = 0


class Skewer(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Skewer", "Skewer", CardType.ATTACK, CardRarity.UNCOMMON, -2, upgraded)

    def play(self, state, target=None):
        x = state.player.energy
        state.player.energy = 0
        dmg = 10 if self.upgraded else 7
        for _ in range(x):
            if target and target.hp > 0:
                _deal_damage(state, target, dmg)

    def upgrade(self):
        self.upgraded = True


class Tactician(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Tactician", "Tactician", CardType.SKILL, CardRarity.UNCOMMON, -1,
                         upgraded, unplayable=True)

    def play(self, state, target=None):
        pass

    def on_manual_discard(self, state):
        state.player.energy += 2 if self.upgraded else 1

    def upgrade(self):
        self.upgraded = True


class Terror(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Terror", "Terror", CardType.SKILL, CardRarity.UNCOMMON,
                         0 if upgraded else 1, upgraded, exhaust=True)

    def play(self, state, target=None):
        if target:
            _apply_power(state, target, PowerId.VULNERABLE, 99)
        _exhaust_card(state, self)

    def upgrade(self):
        self.upgraded = True
        self.cost = 0


class WellLaidPlans(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Well-Laid Plans", "Well-Laid Plans", CardType.POWER, CardRarity.UNCOMMON, 1, upgraded)

    def play(self, state, target=None):
        p = state.player.powers
        p[PowerId.WELL_LAID_PLANS] = p.get(PowerId.WELL_LAID_PLANS, 0) + (2 if self.upgraded else 1)

    def upgrade(self):
        self.upgraded = True


# ── Rares ─────────────────────────────────────────────────────────────────────

class AThousandCuts(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("A Thousand Cuts", "A Thousand Cuts", CardType.POWER, CardRarity.RARE, 2, upgraded)

    def play(self, state, target=None):
        p = state.player.powers
        p[PowerId.THOUSAND_CUTS] = p.get(PowerId.THOUSAND_CUTS, 0) + (2 if self.upgraded else 1)

    def upgrade(self):
        self.upgraded = True


class Adrenaline(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Adrenaline", "Adrenaline", CardType.SKILL, CardRarity.RARE, 0,
                         upgraded, exhaust=True)

    def play(self, state, target=None):
        state.player.energy += 2 if self.upgraded else 1
        _draw_cards(state, 2)
        _exhaust_card(state, self)

    def upgrade(self):
        self.upgraded = True


class AfterImage(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("After Image", "After Image", CardType.POWER, CardRarity.RARE, 1,
                         upgraded, innate=upgraded)

    def play(self, state, target=None):
        p = state.player.powers
        p[PowerId.AFTER_IMAGE] = p.get(PowerId.AFTER_IMAGE, 0) + 1

    def upgrade(self):
        self.upgraded = True
        self.innate = True


class Alchemize(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Alchemize", "Alchemize", CardType.SKILL, CardRarity.RARE,
                         0 if upgraded else 1, upgraded, exhaust=True)

    def play(self, state, target=None):
        if len(state.player.potions) < 3:
            from .potions import random_potion
            state.player.potions.append(random_potion(state))
        _exhaust_card(state, self)

    def upgrade(self):
        self.upgraded = True
        self.cost = 0


class BulletTime(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Bullet Time", "Bullet Time", CardType.SKILL, CardRarity.RARE,
                         2 if upgraded else 3, upgraded)

    def play(self, state, target=None):
        for card in state.combat.hand:
            if card.cost >= 0:
                card.cost_override = 0
                card._bullet_time = True  # restored at end of turn

    def upgrade(self):
        self.upgraded = True
        self.cost = 2


class Burst(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Burst", "Burst", CardType.SKILL, CardRarity.RARE, 1, upgraded)

    def play(self, state, target=None):
        p = state.player.powers
        p[PowerId.BURST] = p.get(PowerId.BURST, 0) + (2 if self.upgraded else 1)

    def upgrade(self):
        self.upgraded = True


class CorpseExplosion(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Corpse Explosion", "Corpse Explosion", CardType.SKILL, CardRarity.RARE, 2, upgraded)

    def play(self, state, target=None):
        if target:
            _apply_power(state, target, PowerId.POISON, 9 if self.upgraded else 6)
            target.powers[PowerId.CORPSE_EXPLOSION] = 1

    def upgrade(self):
        self.upgraded = True


class DieDieDie(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Die Die Die", "Die Die Die", CardType.ATTACK, CardRarity.RARE, 1,
                         upgraded, exhaust=True)

    def play(self, state, target=None):
        dmg = 17 if self.upgraded else 13
        for e in _alive(state):
            _deal_damage(state, e, dmg)
        _exhaust_card(state, self)

    def upgrade(self):
        self.upgraded = True


class Doppelganger(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Doppelganger", "Doppelganger", CardType.SKILL, CardRarity.RARE, -2,
                         upgraded, exhaust=True)

    def play(self, state, target=None):
        x = state.player.energy + (1 if self.upgraded else 0)
        state.player.energy = 0
        p = state.player.powers
        p[PowerId.NEXT_TURN_DRAW] = p.get(PowerId.NEXT_TURN_DRAW, 0) + x
        p[PowerId.ENERGIZED] = p.get(PowerId.ENERGIZED, 0) + x
        _exhaust_card(state, self)

    def upgrade(self):
        self.upgraded = True


class Envenom(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Envenom", "Envenom", CardType.POWER, CardRarity.RARE,
                         1 if upgraded else 2, upgraded)

    def play(self, state, target=None):
        p = state.player.powers
        p[PowerId.ENVENOM] = p.get(PowerId.ENVENOM, 0) + 1

    def upgrade(self):
        self.upgraded = True
        self.cost = 1


class GlassKnife(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Glass Knife", "Glass Knife", CardType.ATTACK, CardRarity.RARE, 1, upgraded)
        self._dmg = 12 if upgraded else 8

    def play(self, state, target=None):
        for _ in range(2):
            if target and target.hp > 0:
                _deal_damage(state, target, max(0, self._dmg))
        self._dmg -= 2  # per-copy decay; combat copies reset next combat

    def upgrade(self):
        self.upgraded = True
        self._dmg = 12


class GrandFinale(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Grand Finale", "Grand Finale", CardType.ATTACK, CardRarity.RARE, 0, upgraded)

    def can_play(self, state) -> bool:
        if state.combat is None or state.combat.draw_pile:
            return False
        return super().can_play(state)

    def play(self, state, target=None):
        dmg = 60 if self.upgraded else 50
        for e in _alive(state):
            _deal_damage(state, e, dmg)

    def upgrade(self):
        self.upgraded = True


class Malaise(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Malaise", "Malaise", CardType.SKILL, CardRarity.RARE, -2,
                         upgraded, exhaust=True)

    def play(self, state, target=None):
        x = state.player.energy + (1 if self.upgraded else 0)
        state.player.energy = 0
        if target:
            target.powers[PowerId.STRENGTH] = target.powers.get(PowerId.STRENGTH, 0) - x
            _apply_power(state, target, PowerId.WEAK, x)
        _exhaust_card(state, self)

    def upgrade(self):
        self.upgraded = True


class Nightmare(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Nightmare", "Nightmare", CardType.SKILL, CardRarity.RARE,
                         2 if upgraded else 3, upgraded, exhaust=True)

    def play(self, state, target=None):
        # Simplification: copies the first other card in hand
        others = [c for c in state.combat.hand if c is not self]
        if others:
            state.combat._nightmare_card = others[0].copy()  # added next turn x3
        _exhaust_card(state, self)

    def upgrade(self):
        self.upgraded = True
        self.cost = 2


class PhantasmalKiller(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Phantasmal Killer", "Phantasmal Killer", CardType.SKILL, CardRarity.RARE,
                         0 if upgraded else 1, upgraded)

    def play(self, state, target=None):
        p = state.player.powers
        p[PowerId.PHANTASMAL] = p.get(PowerId.PHANTASMAL, 0) + 1

    def upgrade(self):
        self.upgraded = True
        self.cost = 0


class StormOfSteel(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Storm of Steel", "Storm of Steel", CardType.SKILL, CardRarity.RARE, 1, upgraded)

    def play(self, state, target=None):
        n = len(state.combat.hand)
        for card in list(state.combat.hand):
            _discard_from_hand(state, card)
        for _ in range(n):
            shiv = Shiv(upgraded=self.upgraded)
            _add_card_to_hand(state, shiv)

    def upgrade(self):
        self.upgraded = True


class ToolsOfTheTrade(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Tools of the Trade", "Tools of the Trade", CardType.POWER, CardRarity.RARE,
                         0 if upgraded else 1, upgraded)

    def play(self, state, target=None):
        p = state.player.powers
        p[PowerId.TOOLS_OF_THE_TRADE] = p.get(PowerId.TOOLS_OF_THE_TRADE, 0) + 1

    def upgrade(self):
        self.upgraded = True
        self.cost = 0


class Unload(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Unload", "Unload", CardType.ATTACK, CardRarity.RARE, 1, upgraded)

    def play(self, state, target=None):
        _deal_damage(state, target, 18 if self.upgraded else 14)
        for card in list(state.combat.hand):
            if card.type != CardType.ATTACK:
                _discard_from_hand(state, card)

    def upgrade(self):
        self.upgraded = True


class WraithForm(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Wraith Form", "Wraith Form", CardType.POWER, CardRarity.RARE, 3, upgraded)

    def play(self, state, target=None):
        p = state.player.powers
        p[PowerId.INTANGIBLE] = p.get(PowerId.INTANGIBLE, 0) + (3 if self.upgraded else 2)
        p[PowerId.WRAITH_FORM] = p.get(PowerId.WRAITH_FORM, 0) + 1

    def upgrade(self):
        self.upgraded = True


# ── Registry & pools ──────────────────────────────────────────────────────────

SILENT_CARD_CLASSES = {
    # Basics & special
    "Strike_G": StrikeG, "Defend_G": DefendG, "Neutralize": Neutralize,
    "Survivor": Survivor, "Shiv": Shiv,
    # Commons
    "Acrobatics": Acrobatics, "Backflip": Backflip, "Bane": Bane,
    "Blade Dance": BladeDance, "Cloak and Dagger": CloakAndDagger,
    "Dagger Spray": DaggerSpray, "Dagger Throw": DaggerThrow,
    "Deadly Poison": DeadlyPoison, "Deflect": Deflect,
    "Dodge and Roll": DodgeAndRoll, "Flying Knee": FlyingKnee,
    "Outmaneuver": Outmaneuver, "Piercing Wail": PiercingWail,
    "Poisoned Stab": PoisonedStab, "Prepared": Prepared,
    "Quick Slash": QuickSlash, "Slice": Slice, "Sneaky Strike": SneakyStrike,
    "Sucker Punch": SuckerPunch,
    # Uncommons
    "Accuracy": Accuracy, "All-Out Attack": AllOutAttack, "Backstab": Backstab,
    "Blur": Blur, "Bouncing Flask": BouncingFlask,
    "Calculated Gamble": CalculatedGamble, "Caltrops": Caltrops,
    "Catalyst": Catalyst, "Choke": Choke, "Concentrate": Concentrate,
    "Crippling Cloud": CripplingCloud, "Dash": Dash, "Distraction": Distraction,
    "Endless Agony": EndlessAgony, "Escape Plan": EscapePlan,
    "Eviscerate": Eviscerate, "Expertise": Expertise, "Finisher": Finisher,
    "Flechettes": Flechettes, "Footwork": Footwork, "Heel Hook": HeelHook,
    "Infinite Blades": InfiniteBlades, "Leg Sweep": LegSweep,
    "Masterful Stab": MasterfulStab, "Noxious Fumes": NoxiousFumes,
    "Predator": Predator, "Reflex": Reflex, "Riddle with Holes": RiddleWithHoles,
    "Setup": Setup, "Skewer": Skewer, "Tactician": Tactician, "Terror": Terror,
    "Well-Laid Plans": WellLaidPlans,
    # Rares
    "A Thousand Cuts": AThousandCuts, "Adrenaline": Adrenaline,
    "After Image": AfterImage, "Alchemize": Alchemize, "Bullet Time": BulletTime,
    "Burst": Burst, "Corpse Explosion": CorpseExplosion, "Die Die Die": DieDieDie,
    "Doppelganger": Doppelganger, "Envenom": Envenom, "Glass Knife": GlassKnife,
    "Grand Finale": GrandFinale, "Malaise": Malaise, "Nightmare": Nightmare,
    "Phantasmal Killer": PhantasmalKiller, "Storm of Steel": StormOfSteel,
    "Tools of the Trade": ToolsOfTheTrade, "Unload": Unload,
    "Wraith Form": WraithForm,
}


def make_silent_card(name: str, upgraded: bool = False) -> Card:
    cls = SILENT_CARD_CLASSES.get(name)
    if cls is None:
        # Status/curse cards are shared with the Ironclad module
        from .cards import make_card
        return make_card(name, upgraded)
    return cls(upgraded)


def silent_starter_deck() -> list:
    return [
        StrikeG(), StrikeG(), StrikeG(), StrikeG(), StrikeG(),
        DefendG(), DefendG(), DefendG(), DefendG(), DefendG(),
        Survivor(), Neutralize(),
    ]


# Reward pool by rarity (mirrors rewards._IRONCLAD_POOL)
SILENT_POOL = {
    CardRarity.COMMON: [
        "Acrobatics", "Backflip", "Bane", "Blade Dance", "Cloak and Dagger",
        "Dagger Spray", "Dagger Throw", "Deadly Poison", "Deflect",
        "Dodge and Roll", "Flying Knee", "Outmaneuver", "Piercing Wail",
        "Poisoned Stab", "Prepared", "Quick Slash", "Slice", "Sneaky Strike",
        "Sucker Punch",
    ],
    CardRarity.UNCOMMON: [
        "Accuracy", "All-Out Attack", "Backstab", "Blur", "Bouncing Flask",
        "Calculated Gamble", "Caltrops", "Catalyst", "Choke", "Concentrate",
        "Crippling Cloud", "Dash", "Distraction", "Endless Agony", "Escape Plan",
        "Eviscerate", "Expertise", "Finisher", "Flechettes", "Footwork",
        "Heel Hook", "Infinite Blades", "Leg Sweep", "Masterful Stab",
        "Noxious Fumes", "Predator", "Reflex", "Riddle with Holes", "Setup",
        "Skewer", "Tactician", "Terror", "Well-Laid Plans",
    ],
    CardRarity.RARE: [
        "A Thousand Cuts", "Adrenaline", "After Image", "Alchemize",
        "Bullet Time", "Burst", "Corpse Explosion", "Die Die Die",
        "Doppelganger", "Envenom", "Glass Knife", "Grand Finale", "Malaise",
        "Nightmare", "Phantasmal Killer", "Storm of Steel",
        "Tools of the Trade", "Unload", "Wraith Form",
    ],
}


# ── Synergy archetypes (mirror benchmark._ARCHETYPES / _ARCHETYPE_PAYOFFS) ────

SILENT_ARCHETYPES = {
    "Poison": [
        "Deadly Poison", "Poisoned Stab", "Bane", "Bouncing Flask",
        "Crippling Cloud", "Catalyst", "Noxious Fumes", "Envenom",
        "Corpse Explosion",
    ],
    "Shiv": [
        "Blade Dance", "Cloak and Dagger", "Dagger Spray", "Storm of Steel",
        "Accuracy", "Infinite Blades", "A Thousand Cuts", "After Image",
        "Finisher",
    ],
    "Discard": [
        "Acrobatics", "Dagger Throw", "Prepared", "Survivor", "Reflex",
        "Tactician", "Sneaky Strike", "Eviscerate", "Concentrate", "Unload",
        "All-Out Attack", "Calculated Gamble",
    ],
    "Block": [
        "Backflip", "Deflect", "Dodge and Roll", "Blur", "Leg Sweep",
        "Footwork", "Caltrops", "Dash", "Wraith Form", "Escape Plan",
    ],
}

# Signature payoffs — must be disjoint across archetypes for confident labels.
SILENT_ARCHETYPE_PAYOFFS = {
    "Poison": {"Catalyst", "Noxious Fumes", "Envenom", "Corpse Explosion"},
    "Shiv": {"Accuracy", "Infinite Blades", "Storm of Steel", "A Thousand Cuts"},
    "Discard": {"Reflex", "Tactician", "Eviscerate", "Sneaky Strike"},
    "Block": {"Footwork", "Wraith Form", "Blur", "Leg Sweep"},
}


# Hand-crafted synergy fixtures: (archetype, deck_names, offer_names, expert_pick_idx).
# Same design rules as the Ironclad set: 4-5 signature cards so the archetype is
# unmistakable, a basic Strike as the removal target, an on-archetype best pick.
# Interleaved Poison/Shiv/Discard/Block so any n that is a multiple of 4 is balanced.
SILENT_SYNERGY_FIXTURES = [
    ("Poison",
     ["Noxious Fumes", "Catalyst", "Envenom", "Deadly Poison", "Poisoned Stab",
      "Strike_G", "Strike_G", "Strike_G", "Defend_G"],
     ["Bouncing Flask", "Slice", "Defend_G"], 0),
    ("Shiv",
     ["Accuracy", "Infinite Blades", "Blade Dance", "Cloak and Dagger", "A Thousand Cuts",
      "Strike_G", "Strike_G", "Defend_G", "Defend_G"],
     ["Storm of Steel", "Defend_G", "Slice"], 0),
    ("Discard",
     ["Reflex", "Tactician", "Eviscerate", "Sneaky Strike", "Acrobatics",
      "Strike_G", "Strike_G", "Defend_G", "Defend_G"],
     ["Dagger Throw", "Slice", "Defend_G"], 0),
    ("Block",
     ["Footwork", "Blur", "Leg Sweep", "Backflip", "Dodge and Roll",
      "Defend_G", "Defend_G", "Strike_G", "Strike_G"],
     ["Wraith Form", "Slice", "Strike_G"], 0),
    ("Poison",
     ["Catalyst", "Corpse Explosion", "Noxious Fumes", "Bouncing Flask", "Bane",
      "Strike_G", "Strike_G", "Defend_G", "Defend_G"],
     ["Deadly Poison", "Backflip", "Strike_G"], 0),
    ("Shiv",
     ["Infinite Blades", "Storm of Steel", "Accuracy", "Dagger Spray", "Blade Dance",
      "Strike_G", "Strike_G", "Defend_G"],
     ["Cloak and Dagger", "Defend_G", "Quick Slash"], 0),
    ("Discard",
     ["Tactician", "Sneaky Strike", "Reflex", "Prepared", "Dagger Throw",
      "Strike_G", "Strike_G", "Strike_G", "Defend_G"],
     ["Eviscerate", "Deflect", "Strike_G"], 0),
    ("Block",
     ["Wraith Form", "Footwork", "Leg Sweep", "Deflect", "Backflip",
      "Defend_G", "Defend_G", "Defend_G", "Strike_G"],
     ["Blur", "Quick Slash", "Strike_G"], 0),
    ("Poison",
     ["Envenom", "Noxious Fumes", "Crippling Cloud", "Deadly Poison", "Poisoned Stab",
      "Strike_G", "Strike_G", "Defend_G", "Defend_G"],
     ["Catalyst", "Backflip", "Defend_G"], 0),
    ("Shiv",
     ["A Thousand Cuts", "Accuracy", "Blade Dance", "Cloak and Dagger", "Dagger Spray",
      "Strike_G", "Defend_G", "Defend_G"],
     ["Infinite Blades", "Deflect", "Strike_G"], 0),
    ("Discard",
     ["Eviscerate", "Reflex", "Tactician", "All-Out Attack", "Acrobatics",
      "Strike_G", "Strike_G", "Defend_G", "Defend_G"],
     ["Sneaky Strike", "Backflip", "Defend_G"], 0),
    ("Block",
     ["Blur", "Footwork", "Dodge and Roll", "Dash", "Escape Plan",
      "Defend_G", "Defend_G", "Strike_G", "Strike_G"],
     ["Leg Sweep", "Slice", "Strike_G"], 0),
    ("Poison",
     ["Corpse Explosion", "Catalyst", "Bouncing Flask", "Bane", "Crippling Cloud",
      "Strike_G", "Strike_G", "Strike_G", "Defend_G"],
     ["Noxious Fumes", "Quick Slash", "Defend_G"], 0),
    ("Shiv",
     ["Storm of Steel", "A Thousand Cuts", "Infinite Blades", "Dagger Spray", "Finisher",
      "Strike_G", "Strike_G", "Defend_G"],
     ["Accuracy", "Defend_G", "Sucker Punch"], 0),
    ("Discard",
     ["Sneaky Strike", "Eviscerate", "Tactician", "Calculated Gamble", "Prepared",
      "Strike_G", "Strike_G", "Defend_G", "Defend_G"],
     ["Reflex", "Slice", "Defend_G"], 0),
    ("Block",
     ["Leg Sweep", "Wraith Form", "Blur", "Backflip", "Deflect",
      "Defend_G", "Defend_G", "Strike_G", "Strike_G"],
     ["Footwork", "Sucker Punch", "Strike_G"], 0),
    ("Poison",
     ["Noxious Fumes", "Envenom", "Catalyst", "Poisoned Stab", "Bouncing Flask",
      "Strike_G", "Strike_G", "Defend_G", "Defend_G"],
     ["Crippling Cloud", "Quick Slash", "Strike_G"], 0),
    ("Shiv",
     ["Accuracy", "Infinite Blades", "A Thousand Cuts", "Blade Dance", "Cloak and Dagger",
      "Strike_G", "Defend_G", "Defend_G"],
     ["Dagger Spray", "Deflect", "Strike_G"], 0),
    ("Discard",
     ["Reflex", "Sneaky Strike", "Eviscerate", "Unload", "Dagger Throw",
      "Strike_G", "Strike_G", "Defend_G", "Defend_G"],
     ["Tactician", "Slice", "Defend_G"], 0),
    ("Block",
     ["Footwork", "Blur", "Wraith Form", "Escape Plan", "Dash",
      "Defend_G", "Defend_G", "Defend_G", "Strike_G"],
     ["Dodge and Roll", "Sucker Punch", "Strike_G"], 0),
]
