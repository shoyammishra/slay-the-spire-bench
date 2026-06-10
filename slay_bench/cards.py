"""Card definitions for Ironclad (and status/curse cards)."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional
import math

from .enums import CardType, CardRarity

if TYPE_CHECKING:
    from .state import GameState
    from .enemies import Enemy


@dataclass
class Card:
    id: str
    name: str
    type: CardType
    rarity: CardRarity
    cost: int  # -1 = unplayable, -2 = X cost
    upgraded: bool = False
    # flags
    exhaust: bool = False
    ethereal: bool = False
    innate: bool = False
    retain: bool = False
    unplayable: bool = False
    # runtime state
    cost_override: Optional[int] = None  # temporary cost change this combat

    def effective_cost(self) -> int:
        if self.cost_override is not None:
            return self.cost_override
        return self.cost

    def can_play(self, state: GameState) -> bool:
        if self.unplayable:
            return False
        from .enums import PowerId
        if PowerId.ENTANGLED in state.player.powers and self.type == CardType.ATTACK:
            return False
        cost = self.effective_cost()
        if cost == -1:
            return False
        if cost == -2:
            return True  # X cost, any energy >= 0
        return state.player.energy >= cost

    def play(self, state: GameState, target: Optional[Enemy] = None) -> None:
        raise NotImplementedError(f"{self.name}.play() not implemented")

    def upgrade(self) -> None:
        raise NotImplementedError(f"{self.name}.upgrade() not implemented")

    def __repr__(self) -> str:
        suffix = "+" if self.upgraded else ""
        return f"{self.name}{suffix}"

    def copy(self) -> Card:
        import copy
        return copy.copy(self)


# ── helpers ──────────────────────────────────────────────────────────────────

def _deal_damage(state: GameState, target: Enemy, base: int, times: int = 1) -> int:
    """Apply Strength/Weak/Vulnerable scaling, return total damage dealt."""
    from .enums import PowerId
    from .events import Event
    strength = state.player.powers.get(PowerId.STRENGTH, 0)
    dexterity = state.player.powers.get(PowerId.DEXTERITY, 0)
    per_hit = max(0, base + strength)
    if PowerId.WEAK in state.player.powers:
        per_hit = math.floor(per_hit * 0.75)
    if PowerId.VULNERABLE in target.powers:
        per_hit = math.floor(per_hit * 1.5)
    if PowerId.VIGOR in state.player.powers:
        per_hit += state.player.powers.pop(PowerId.VIGOR)
    if PowerId.DOUBLE_DAMAGE in state.player.powers:  # Phantasmal Killer
        per_hit *= 2
    # Pen Nib: the 10th attack deals double damage (one-shot flag set by the relic)
    if getattr(state.player, '_pen_nib_ready', False):
        per_hit *= 2
        state.player._pen_nib_ready = False
    envenom = state.player.powers.get(PowerId.ENVENOM, 0)
    total = 0
    for _ in range(times):
        hp_before = target.hp
        dmg = _apply_damage_to_enemy(state, target, per_hit, from_attack=True)
        total += dmg
        # Envenom: unblocked attack damage applies poison
        if envenom and target.hp < hp_before:
            _apply_power(state, target, PowerId.POISON, envenom)
        if target.hp <= 0:
            break
    return total


def _apply_damage_to_enemy(state: GameState, target: Enemy, amount: int,
                           from_attack: bool = False) -> int:
    from .enums import PowerId
    from .events import Event
    if PowerId.INTANGIBLE in target.powers:
        amount = 1
    # Thorns retaliates against ATTACK damage only (not Combust/Juggernaut/etc.)
    thorns = target.powers.get(PowerId.THORNS, 0)
    if from_attack and thorns > 0:
        _damage_player(state, thorns)
    blocked = min(target.block, amount)
    target.block -= blocked
    real_dmg = amount - blocked
    if real_dmg > 0:
        if PowerId.MALLEABLE in target.powers:
            target.powers[PowerId.MALLEABLE] += 1
            target.add_block(target.powers[PowerId.MALLEABLE])
        target.hp -= real_dmg
        state.bus.emit(Event.DAMAGE_DEALT, state, target=target, amount=real_dmg)
        # Curl Up: gain block the first time attack damage lands
        if hasattr(target, 'on_damage_taken'):
            target.on_damage_taken(state, real_dmg)
        # Split (slimes): check HP threshold while still alive
        if target.hp > 0 and hasattr(target, 'on_hp_threshold'):
            target.on_hp_threshold(state)
    return amount  # return total (blocked+unblocked) for display purposes


def _damage_player(state: GameState, amount: int, is_hp_loss: bool = False) -> int:
    """Damage the player; returns actual HP lost."""
    from .enums import PowerId
    from .events import Event
    if not is_hp_loss:
        if PowerId.INTANGIBLE in state.player.powers:
            amount = 1
        if PowerId.VULNERABLE in state.player.powers:
            amount = math.floor(amount * 1.5)
        # Tungsten Rod relic would go here
    blocked = min(state.player.block, amount)
    state.player.block -= blocked
    real_dmg = amount - blocked
    if real_dmg > 0:
        results = state.bus.emit(Event.DEATH_WOULD_OCCUR, state, amount=real_dmg)
        if any(results):  # relic prevented death
            state.player.hp = max(1, state.player.hp)
            return real_dmg
        state.player.hp -= real_dmg
        state.bus.emit(Event.DAMAGE_TAKEN, state, amount=real_dmg)
        if PowerId.RUPTURE in state.player.powers and is_hp_loss:
            state.player.powers[PowerId.STRENGTH] = (
                state.player.powers.get(PowerId.STRENGTH, 0) + state.player.powers[PowerId.RUPTURE]
            )
    return real_dmg


def _gain_block(state: GameState, amount: int) -> None:
    from .enums import PowerId
    from .events import Event
    dex = state.player.powers.get(PowerId.DEXTERITY, 0)
    if PowerId.FRAIL in state.player.powers:
        amount = math.floor((amount + dex) * 0.75)
    else:
        amount = amount + dex
    amount = max(0, amount)
    state.player.block += amount
    state.bus.emit(Event.BLOCK_GAINED, state, amount=amount)


def _apply_power(state: GameState, target, power_id, amount: int) -> None:
    """Apply a power/debuff to player or enemy, respecting Artifact."""
    from .enums import PowerId
    debuffs = {
        PowerId.WEAK, PowerId.VULNERABLE, PowerId.FRAIL, PowerId.POISON,
        PowerId.CONFUSED, PowerId.CONSTRICTED, PowerId.ENTANGLED,
        PowerId.NO_DRAW, PowerId.HEX, PowerId.SHACKLED,
    }
    if power_id in debuffs:
        artifact = target.powers.get(PowerId.ARTIFACT, 0)
        if artifact > 0:
            target.powers[PowerId.ARTIFACT] = artifact - 1
            if target.powers[PowerId.ARTIFACT] == 0:
                del target.powers[PowerId.ARTIFACT]
            return
    target.powers[power_id] = target.powers.get(power_id, 0) + amount
    # StS justApplied rule: debuffs enemies put on the player during the enemy
    # phase must survive the end-of-round tick of that same round.
    if (target is state.player and state.combat is not None
            and state.combat.enemy_phase):
        state.combat.just_applied.add(power_id)


_HAND_LIMIT = 10


def _draw_cards(state: GameState, n: int) -> None:
    from .events import Event
    for _ in range(n):
        if len(state.combat.hand) >= _HAND_LIMIT:
            break  # hand full — extra draws are lost (StS rule)
        if not state.combat.draw_pile and not state.combat.discard_pile:
            break
        if not state.combat.draw_pile:
            state.combat.draw_pile = state.combat.discard_pile[:]
            state.combat.discard_pile.clear()
            state.rng.shuffle_rng.shuffle(state.combat.draw_pile)
            state.bus.emit(Event.SHUFFLE, state)
        card = state.combat.draw_pile.pop()
        state.combat.hand.append(card)
        state.bus.emit(Event.CARD_DRAW, state, card=card)
        if hasattr(card, 'on_drawn'):
            card.on_drawn(state)  # e.g. Endless Agony copies itself
        if card.type == CardType.STATUS:
            state.bus.emit(Event.STATUS_DRAW, state, card=card)


def _exhaust_card(state: GameState, card: Card) -> None:
    from .events import Event
    if card in state.combat.hand:
        state.combat.hand.remove(card)
    state.combat.exhaust_pile.append(card)
    state.bus.emit(Event.CARD_EXHAUST, state, card=card)


def _add_card_to_hand(state: GameState, card: Card) -> None:
    """Add a generated card to hand, overflowing to the discard pile (StS rule)."""
    if len(state.combat.hand) < _HAND_LIMIT:
        state.combat.hand.append(card)
    else:
        state.combat.discard_pile.append(card)


def _discard_from_hand(state: GameState, card: Card) -> None:
    """Manually discard a card from hand (Silent mechanic). Triggers
    on-discard effects (Reflex, Tactician) and the CARD_DISCARD event."""
    from .events import Event
    if card not in state.combat.hand:
        return
    state.combat.hand.remove(card)
    state.combat.discard_pile.append(card)
    state.combat.discarded_this_turn += 1
    if hasattr(card, 'on_manual_discard'):
        card.on_manual_discard(state)
    state.bus.emit(Event.CARD_DISCARD, state, card=card)


def _auto_discard_choice(state: GameState) -> Optional[Card]:
    """Deterministic pick of the least valuable hand card to discard:
    statuses/curses first, then basic Strikes, then Defends, then the first card.
    (Stand-in for the human choice; keeps simulation deterministic.)"""
    hand = state.combat.hand
    if not hand:
        return None
    for c in hand:
        if c.type in (CardType.STATUS, CardType.CURSE):
            return c
    for name in ("Strike", "Defend"):
        for c in hand:
            if c.name == name:
                return c
    return hand[0]


# ── Status / Curse cards ──────────────────────────────────────────────────────

class Burn(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Burn", "Burn", CardType.STATUS, CardRarity.SPECIAL, -1, upgraded, unplayable=True)

    def play(self, state, target=None): pass
    def upgrade(self): pass

    def end_of_turn_effect(self, state):
        _damage_player(state, 2 if not self.upgraded else 4, is_hp_loss=True)


class Dazed(Card):
    def __init__(self):
        super().__init__("Dazed", "Dazed", CardType.STATUS, CardRarity.SPECIAL, -1, ethereal=True, unplayable=True)

    def play(self, state, target=None): pass
    def upgrade(self): pass


class Slimed(Card):
    def __init__(self):
        super().__init__("Slimed", "Slimed", CardType.STATUS, CardRarity.SPECIAL, 1, exhaust=True)

    def play(self, state, target=None):
        _exhaust_card(state, self)

    def upgrade(self): pass


class Wound(Card):
    def __init__(self):
        super().__init__("Wound", "Wound", CardType.STATUS, CardRarity.SPECIAL, -1, unplayable=True)

    def play(self, state, target=None): pass
    def upgrade(self): pass


class VoidCard(Card):
    def __init__(self):
        super().__init__("Void", "Void", CardType.STATUS, CardRarity.SPECIAL, -1, ethereal=True, unplayable=True)

    def play(self, state, target=None): pass
    def upgrade(self): pass

    def on_draw(self, state):
        state.player.energy = max(0, state.player.energy - 1)


# ── Curses ─────────────────────────────────────────────────────────────────

class CurseBase(Card):
    def play(self, state, target=None): pass
    def upgrade(self): pass


class Clumsy(CurseBase):
    def __init__(self):
        super().__init__("Clumsy", "Clumsy", CardType.CURSE, CardRarity.CURSE, -1, ethereal=True, unplayable=True)


class Decay(CurseBase):
    def __init__(self):
        super().__init__("Decay", "Decay", CardType.CURSE, CardRarity.CURSE, -1, unplayable=True)

    def end_of_turn_effect(self, state):
        _damage_player(state, 2, is_hp_loss=True)


class Doubt(CurseBase):
    def __init__(self):
        super().__init__("Doubt", "Doubt", CardType.CURSE, CardRarity.CURSE, -1, unplayable=True)

    def end_of_turn_effect(self, state):
        from .enums import PowerId
        _apply_power(state, state.player, PowerId.WEAK, 1)


class Injury(CurseBase):
    def __init__(self):
        super().__init__("Injury", "Injury", CardType.CURSE, CardRarity.CURSE, -1, unplayable=True)


class Normality(CurseBase):
    def __init__(self):
        super().__init__("Normality", "Normality", CardType.CURSE, CardRarity.CURSE, -1, unplayable=True)


class Pain(CurseBase):
    def __init__(self):
        super().__init__("Pain", "Pain", CardType.CURSE, CardRarity.CURSE, -1, unplayable=True)

    def on_card_played(self, state, card):
        _damage_player(state, 1, is_hp_loss=True)


class Parasite(CurseBase):
    def __init__(self):
        super().__init__("Parasite", "Parasite", CardType.CURSE, CardRarity.CURSE, -1, unplayable=True)


class Pride(CurseBase):
    def __init__(self):
        super().__init__("Pride", "Pride", CardType.CURSE, CardRarity.CURSE, 1, innate=True, exhaust=True)

    def play(self, state, target=None):
        state.combat.hand.append(Pride())
        _exhaust_card(state, self)


class Regret(CurseBase):
    def __init__(self):
        super().__init__("Regret", "Regret", CardType.CURSE, CardRarity.CURSE, -1, unplayable=True)

    def end_of_turn_effect(self, state):
        n = len(state.combat.hand)
        _damage_player(state, n, is_hp_loss=True)


class Shame(CurseBase):
    def __init__(self):
        super().__init__("Shame", "Shame", CardType.CURSE, CardRarity.CURSE, -1, unplayable=True)

    def end_of_turn_effect(self, state):
        from .enums import PowerId
        _apply_power(state, state.player, PowerId.FRAIL, 1)


class Writhe(CurseBase):
    def __init__(self):
        super().__init__("Writhe", "Writhe", CardType.CURSE, CardRarity.CURSE, -1, innate=True, unplayable=True)


class AscendersBane(CurseBase):
    def __init__(self):
        super().__init__("AscendersBane", "Ascender's Bane", CardType.CURSE, CardRarity.SPECIAL, -1, ethereal=True, unplayable=True)


# ── Basic cards ───────────────────────────────────────────────────────────────

class Strike(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Strike_R", "Strike", CardType.ATTACK, CardRarity.BASIC, 1, upgraded)

    def play(self, state, target=None):
        dmg = 9 if self.upgraded else 6
        _deal_damage(state, target, dmg)

    def upgrade(self):
        self.upgraded = True


class Defend(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Defend_R", "Defend", CardType.SKILL, CardRarity.BASIC, 1, upgraded)

    def play(self, state, target=None):
        _gain_block(state, 8 if self.upgraded else 5)

    def upgrade(self):
        self.upgraded = True


class Bash(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Bash", "Bash", CardType.ATTACK, CardRarity.BASIC, 2, upgraded)

    def play(self, state, target=None):
        from .enums import PowerId
        dmg = 10 if self.upgraded else 8
        vuln = 3 if self.upgraded else 2
        _deal_damage(state, target, dmg)
        if target and target.hp > 0:
            _apply_power(state, target, PowerId.VULNERABLE, vuln)

    def upgrade(self):
        self.upgraded = True


# ── Common cards ──────────────────────────────────────────────────────────────

class Anger(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Anger", "Anger", CardType.ATTACK, CardRarity.COMMON, 0, upgraded)

    def play(self, state, target=None):
        dmg = 8 if self.upgraded else 6
        _deal_damage(state, target, dmg)
        state.combat.discard_pile.append(self.copy())

    def upgrade(self):
        self.upgraded = True


class Armaments(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Armaments", "Armaments", CardType.SKILL, CardRarity.COMMON, 1, upgraded)

    def play(self, state, target=None):
        _gain_block(state, 5)
        if self.upgraded:
            for c in state.combat.hand:
                c.upgrade()
        else:
            # upgrade one card in hand of player's choice — auto pick first upgradeable
            upgradeable = [c for c in state.combat.hand if not c.upgraded]
            if upgradeable:
                upgradeable[0].upgrade()

    def upgrade(self):
        self.upgraded = True


class BodySlam(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Body Slam", "Body Slam", CardType.ATTACK, CardRarity.COMMON,
                         0 if upgraded else 1, upgraded)

    def play(self, state, target=None):
        _deal_damage(state, target, state.player.block)

    def upgrade(self):
        self.upgraded = True
        self.cost = 0


class Clash(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Clash", "Clash", CardType.ATTACK, CardRarity.COMMON, 0, upgraded)

    def can_play(self, state) -> bool:
        if not super().can_play(state):
            return False
        return all(c.type == CardType.ATTACK for c in state.combat.hand if c is not self)

    def play(self, state, target=None):
        dmg = 18 if self.upgraded else 14
        _deal_damage(state, target, dmg)

    def upgrade(self):
        self.upgraded = True


class Cleave(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Cleave", "Cleave", CardType.ATTACK, CardRarity.COMMON, 1, upgraded)

    def play(self, state, target=None):
        dmg = 11 if self.upgraded else 8
        for e in state.combat.enemies:
            if e.hp > 0:
                _deal_damage(state, e, dmg)

    def upgrade(self):
        self.upgraded = True


class Clothesline(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Clothesline", "Clothesline", CardType.ATTACK, CardRarity.COMMON, 2, upgraded)

    def play(self, state, target=None):
        from .enums import PowerId
        dmg = 14 if self.upgraded else 12
        weak = 3 if self.upgraded else 2
        _deal_damage(state, target, dmg)
        if target and target.hp > 0:
            _apply_power(state, target, PowerId.WEAK, weak)

    def upgrade(self):
        self.upgraded = True


class Flex(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Flex", "Flex", CardType.SKILL, CardRarity.COMMON, 0, upgraded)

    def play(self, state, target=None):
        from .enums import PowerId
        amount = 4 if self.upgraded else 2
        state.player.powers[PowerId.STRENGTH] = state.player.powers.get(PowerId.STRENGTH, 0) + amount
        state.player.powers[PowerId.FLEX] = state.player.powers.get(PowerId.FLEX, 0) + amount

    def upgrade(self):
        self.upgraded = True


class Havoc(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Havoc", "Havoc", CardType.SKILL, CardRarity.COMMON,
                         0 if upgraded else 1, upgraded)

    def play(self, state, target=None):
        if state.combat.draw_pile:
            card = state.combat.draw_pile[-1]
            # play the top card without paying cost, then exhaust
            card.cost_override = 0
            card.play(state, target)
            card.cost_override = None
            _exhaust_card(state, card)

    def upgrade(self):
        self.upgraded = True
        self.cost = 0


class Headbutt(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Headbutt", "Headbutt", CardType.ATTACK, CardRarity.COMMON, 1, upgraded)

    def play(self, state, target=None):
        dmg = 10 if self.upgraded else 9
        _deal_damage(state, target, dmg)
        if state.combat.discard_pile:
            # put top of discard on top of draw pile
            card = state.combat.discard_pile[-1]
            state.combat.discard_pile.pop()
            state.combat.draw_pile.append(card)

    def upgrade(self):
        self.upgraded = True


class HeavyBlade(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Heavy Blade", "Heavy Blade", CardType.ATTACK, CardRarity.COMMON, 2, upgraded)

    def play(self, state, target=None):
        from .enums import PowerId
        strength = state.player.powers.get(PowerId.STRENGTH, 0)
        multiplier = 5 if self.upgraded else 3
        _deal_damage(state, target, 14 + strength * (multiplier - 1))

    def upgrade(self):
        self.upgraded = True


class IronWave(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Iron Wave", "Iron Wave", CardType.ATTACK, CardRarity.COMMON, 1, upgraded)

    def play(self, state, target=None):
        amount = 7 if self.upgraded else 5
        _gain_block(state, amount)
        _deal_damage(state, target, amount)

    def upgrade(self):
        self.upgraded = True


class PerfectedStrike(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Perfected Strike", "Perfected Strike", CardType.ATTACK, CardRarity.COMMON, 2, upgraded)

    def play(self, state, target=None):
        bonus = 3 if self.upgraded else 2
        strike_count = sum(
            1 for c in (state.combat.draw_pile + state.combat.hand +
                        state.combat.discard_pile + state.combat.exhaust_pile)
            if "strike" in c.id.lower()
        )
        _deal_damage(state, target, 6 + strike_count * bonus)

    def upgrade(self):
        self.upgraded = True


class PommelStrike(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Pommel Strike", "Pommel Strike", CardType.ATTACK, CardRarity.COMMON, 1, upgraded)

    def play(self, state, target=None):
        dmg = 10 if self.upgraded else 9
        draw = 2 if self.upgraded else 1
        _deal_damage(state, target, dmg)
        _draw_cards(state, draw)

    def upgrade(self):
        self.upgraded = True


class ShrugItOff(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Shrug It Off", "Shrug It Off", CardType.SKILL, CardRarity.COMMON, 1, upgraded)

    def play(self, state, target=None):
        _gain_block(state, 11 if self.upgraded else 8)
        _draw_cards(state, 1)

    def upgrade(self):
        self.upgraded = True


class SwordBoomerang(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Sword Boomerang", "Sword Boomerang", CardType.ATTACK, CardRarity.COMMON, 1, upgraded)

    def play(self, state, target=None):
        times = 4 if self.upgraded else 3
        for _ in range(times):
            alive = [e for e in state.combat.enemies if e.hp > 0]
            if alive:
                t = state.rng.misc_rng.next_int(len(alive))
                _deal_damage(state, alive[t], 3)

    def upgrade(self):
        self.upgraded = True


class Thunderclap(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Thunderclap", "Thunderclap", CardType.ATTACK, CardRarity.COMMON, 1, upgraded)

    def play(self, state, target=None):
        from .enums import PowerId
        for e in state.combat.enemies:
            if e.hp > 0:
                _deal_damage(state, e, 7 if self.upgraded else 4)
                _apply_power(state, e, PowerId.VULNERABLE, 1)

    def upgrade(self):
        self.upgraded = True


class TrueGrit(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("True Grit", "True Grit", CardType.SKILL, CardRarity.COMMON, 1, upgraded)

    def play(self, state, target=None):
        _gain_block(state, 9 if self.upgraded else 7)
        if self.upgraded:
            # exhaust a card of choice — auto pick a status/curse or last
            candidates = [c for c in state.combat.hand if c is not self and c.type in (CardType.STATUS, CardType.CURSE)]
            if not candidates:
                candidates = [c for c in state.combat.hand if c is not self]
            if candidates:
                _exhaust_card(state, candidates[0])
        else:
            candidates = [c for c in state.combat.hand if c is not self]
            if candidates:
                idx = state.rng.misc_rng.next_int(len(candidates))
                _exhaust_card(state, candidates[idx])

    def upgrade(self):
        self.upgraded = True


class TwinStrike(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Twin Strike", "Twin Strike", CardType.ATTACK, CardRarity.COMMON, 1, upgraded)

    def play(self, state, target=None):
        dmg = 7 if self.upgraded else 5
        _deal_damage(state, target, dmg, times=2)

    def upgrade(self):
        self.upgraded = True


class Warcry(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Warcry", "Warcry", CardType.SKILL, CardRarity.COMMON, 0, upgraded, exhaust=True)

    def play(self, state, target=None):
        draw = 2 if self.upgraded else 1
        _draw_cards(state, draw)
        # put a card from hand on top of draw pile (auto: last drawn)
        if state.combat.hand:
            card = state.combat.hand[-1]
            state.combat.hand.remove(card)
            state.combat.draw_pile.append(card)
        _exhaust_card(state, self)

    def upgrade(self):
        self.upgraded = True


class WildStrike(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Wild Strike", "Wild Strike", CardType.ATTACK, CardRarity.COMMON, 1, upgraded)

    def play(self, state, target=None):
        dmg = 17 if self.upgraded else 12
        _deal_damage(state, target, dmg)
        state.combat.draw_pile.insert(0, Wound())

    def upgrade(self):
        self.upgraded = True


# ── Uncommon cards ────────────────────────────────────────────────────────────

class BattleTrance(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Battle Trance", "Battle Trance", CardType.SKILL, CardRarity.UNCOMMON, 0, upgraded)

    def play(self, state, target=None):
        from .enums import PowerId
        draw = 4 if self.upgraded else 3
        _draw_cards(state, draw)
        _apply_power(state, state.player, PowerId.NO_DRAW, 1)

    def upgrade(self):
        self.upgraded = True


class BloodForBlood(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Blood for Blood", "Blood for Blood", CardType.ATTACK, CardRarity.UNCOMMON, 4, upgraded, exhaust=True)

    def effective_cost(self):
        return max(0, super().effective_cost() - getattr(self, '_times_hit', 0))

    def play(self, state, target=None):
        cost = self.effective_cost()
        state.player.energy -= cost
        dmg = 22 if self.upgraded else 18
        _deal_damage(state, target, dmg)
        _exhaust_card(state, self)

    def upgrade(self):
        self.upgraded = True


class Bloodletting(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Bloodletting", "Bloodletting", CardType.SKILL, CardRarity.UNCOMMON, 0, upgraded)

    def play(self, state, target=None):
        energy_gain = 3 if self.upgraded else 2
        _damage_player(state, 3, is_hp_loss=True)
        state.player.energy += energy_gain

    def upgrade(self):
        self.upgraded = True


class BurningPact(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Burning Pact", "Burning Pact", CardType.SKILL, CardRarity.UNCOMMON, 1, upgraded)

    def play(self, state, target=None):
        # exhaust a card from hand
        candidates = [c for c in state.combat.hand if c is not self]
        if candidates:
            _exhaust_card(state, candidates[0])
        draw = 3 if self.upgraded else 2
        _draw_cards(state, draw)

    def upgrade(self):
        self.upgraded = True


class Carnage(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Carnage", "Carnage", CardType.ATTACK, CardRarity.UNCOMMON, 2, upgraded, ethereal=True)

    def play(self, state, target=None):
        dmg = 28 if self.upgraded else 20
        _deal_damage(state, target, dmg)

    def upgrade(self):
        self.upgraded = True


class Combust(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Combust", "Combust", CardType.POWER, CardRarity.UNCOMMON, 1, upgraded)

    def play(self, state, target=None):
        from .enums import PowerId
        amount = 7 if self.upgraded else 5
        state.player.powers[PowerId.COMBUST] = state.player.powers.get(PowerId.COMBUST, 0) + amount

    def upgrade(self):
        self.upgraded = True


class DarkEmbrace(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Dark Embrace", "Dark Embrace", CardType.POWER, CardRarity.UNCOMMON, 2 if not upgraded else 1, upgraded)

    def play(self, state, target=None):
        from .enums import PowerId
        state.player.powers[PowerId.DARK_EMBRACE] = state.player.powers.get(PowerId.DARK_EMBRACE, 0) + 1

    def upgrade(self):
        self.upgraded = True
        self.cost = 1


class Disarm(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Disarm", "Disarm", CardType.SKILL, CardRarity.UNCOMMON, 1, upgraded, exhaust=True)

    def play(self, state, target=None):
        from .enums import PowerId
        amount = 3 if self.upgraded else 2
        if target:
            target.powers[PowerId.STRENGTH] = target.powers.get(PowerId.STRENGTH, 0) - amount
        _exhaust_card(state, self)

    def upgrade(self):
        self.upgraded = True


class Dropkick(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Dropkick", "Dropkick", CardType.ATTACK, CardRarity.UNCOMMON, 1, upgraded)

    def play(self, state, target=None):
        from .enums import PowerId
        dmg = 8 if self.upgraded else 5
        _deal_damage(state, target, dmg)
        if target and PowerId.VULNERABLE in target.powers:
            state.player.energy += 1
            _draw_cards(state, 1)

    def upgrade(self):
        self.upgraded = True


class DualWield(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Dual Wield", "Dual Wield", CardType.SKILL, CardRarity.UNCOMMON, 1, upgraded)

    def play(self, state, target=None):
        attacks = [c for c in state.combat.hand if c.type == CardType.ATTACK and c is not self]
        if attacks:
            copies = 2 if self.upgraded else 1
            for _ in range(copies):
                state.combat.hand.append(attacks[0].copy())

    def upgrade(self):
        self.upgraded = True


class Entrench(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Entrench", "Entrench", CardType.SKILL, CardRarity.UNCOMMON,
                         1 if upgraded else 2, upgraded)

    def play(self, state, target=None):
        state.player.block *= 2

    def upgrade(self):
        self.upgraded = True
        self.cost = 1


class Evolve(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Evolve", "Evolve", CardType.POWER, CardRarity.UNCOMMON, 1, upgraded)

    def play(self, state, target=None):
        from .enums import PowerId
        amount = 2 if self.upgraded else 1
        state.player.powers[PowerId.EVOLVE] = state.player.powers.get(PowerId.EVOLVE, 0) + amount

    def upgrade(self):
        self.upgraded = True


class FeelNoPain(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Feel No Pain", "Feel No Pain", CardType.POWER, CardRarity.UNCOMMON, 1, upgraded)

    def play(self, state, target=None):
        from .enums import PowerId
        amount = 4 if self.upgraded else 3
        state.player.powers[PowerId.FEEL_NO_PAIN] = state.player.powers.get(PowerId.FEEL_NO_PAIN, 0) + amount

    def upgrade(self):
        self.upgraded = True


class FireBreathing(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Fire Breathing", "Fire Breathing", CardType.POWER, CardRarity.UNCOMMON, 1, upgraded)

    def play(self, state, target=None):
        from .enums import PowerId
        amount = 10 if self.upgraded else 6
        state.player.powers[PowerId.FIRE_BREATHING] = state.player.powers.get(PowerId.FIRE_BREATHING, 0) + amount

    def upgrade(self):
        self.upgraded = True


class FlameBarrier(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Flame Barrier", "Flame Barrier", CardType.SKILL, CardRarity.UNCOMMON, 2, upgraded)

    def play(self, state, target=None):
        from .enums import PowerId
        _gain_block(state, 12 if self.upgraded else 8)
        amount = 6 if self.upgraded else 4
        state.player.powers[PowerId.FLAME_BARRIER] = state.player.powers.get(PowerId.FLAME_BARRIER, 0) + amount

    def upgrade(self):
        self.upgraded = True


class GhostlyArmor(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Ghostly Armor", "Ghostly Armor", CardType.SKILL, CardRarity.UNCOMMON, 1, upgraded, ethereal=True)

    def play(self, state, target=None):
        _gain_block(state, 13 if self.upgraded else 10)

    def upgrade(self):
        self.upgraded = True


class Hemokinesis(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Hemokinesis", "Hemokinesis", CardType.ATTACK, CardRarity.UNCOMMON, 1, upgraded)

    def play(self, state, target=None):
        _damage_player(state, 2, is_hp_loss=True)
        dmg = 20 if self.upgraded else 15
        _deal_damage(state, target, dmg)

    def upgrade(self):
        self.upgraded = True


class InfernalBlade(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Infernal Blade", "Infernal Blade", CardType.SKILL, CardRarity.UNCOMMON,
                         0 if upgraded else 1, upgraded, exhaust=True)

    def play(self, state, target=None):
        # Add a random attack to hand (simplified: add a Strike)
        state.combat.hand.append(Strike())
        _exhaust_card(state, self)

    def upgrade(self):
        self.upgraded = True
        self.cost = 0


class Inflame(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Inflame", "Inflame", CardType.POWER, CardRarity.UNCOMMON, 1, upgraded)

    def play(self, state, target=None):
        from .enums import PowerId
        amount = 3 if self.upgraded else 2
        state.player.powers[PowerId.STRENGTH] = state.player.powers.get(PowerId.STRENGTH, 0) + amount

    def upgrade(self):
        self.upgraded = True


class Intimidate(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Intimidate", "Intimidate", CardType.SKILL, CardRarity.UNCOMMON, 0, upgraded, exhaust=True)

    def play(self, state, target=None):
        from .enums import PowerId
        weak = 2 if self.upgraded else 1
        for e in state.combat.enemies:
            if e.hp > 0:
                _apply_power(state, e, PowerId.WEAK, weak)
        _exhaust_card(state, self)

    def upgrade(self):
        self.upgraded = True


class Metallicize(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Metallicize", "Metallicize", CardType.POWER, CardRarity.UNCOMMON, 1, upgraded)

    def play(self, state, target=None):
        from .enums import PowerId
        amount = 4 if self.upgraded else 3
        state.player.powers[PowerId.METALLICIZE] = state.player.powers.get(PowerId.METALLICIZE, 0) + amount

    def upgrade(self):
        self.upgraded = True


class PowerThrough(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Power Through", "Power Through", CardType.SKILL, CardRarity.UNCOMMON, 1, upgraded)

    def play(self, state, target=None):
        _gain_block(state, 20 if self.upgraded else 15)
        state.combat.hand.append(Wound())
        state.combat.hand.append(Wound())

    def upgrade(self):
        self.upgraded = True


class Pummel(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Pummel", "Pummel", CardType.ATTACK, CardRarity.UNCOMMON, 1, upgraded, exhaust=True)

    def play(self, state, target=None):
        times = 5 if self.upgraded else 4
        _deal_damage(state, target, 2, times=times)
        _exhaust_card(state, self)

    def upgrade(self):
        self.upgraded = True


class Rage(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Rage", "Rage", CardType.SKILL, CardRarity.UNCOMMON, 0, upgraded)

    def play(self, state, target=None):
        from .enums import PowerId
        amount = 5 if self.upgraded else 3
        state.player.powers[PowerId.RAGE] = state.player.powers.get(PowerId.RAGE, 0) + amount

    def upgrade(self):
        self.upgraded = True


class Rampage(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Rampage", "Rampage", CardType.ATTACK, CardRarity.UNCOMMON, 1, upgraded)
        self._bonus = 0

    def play(self, state, target=None):
        inc = 8 if self.upgraded else 5
        self._bonus += inc
        _deal_damage(state, target, 8 + self._bonus - inc)  # base 8 + accumulated

    def upgrade(self):
        self.upgraded = True

    def copy(self):
        c = super().copy()
        c._bonus = self._bonus
        return c


class RecklessCharge(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Reckless Charge", "Reckless Charge", CardType.ATTACK, CardRarity.UNCOMMON, 0, upgraded)

    def play(self, state, target=None):
        dmg = 10 if self.upgraded else 7
        _deal_damage(state, target, dmg)
        state.combat.draw_pile.insert(0, Dazed())

    def upgrade(self):
        self.upgraded = True


class Rupture(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Rupture", "Rupture", CardType.POWER, CardRarity.UNCOMMON, 1, upgraded)

    def play(self, state, target=None):
        from .enums import PowerId
        amount = 2 if self.upgraded else 1
        state.player.powers[PowerId.RUPTURE] = state.player.powers.get(PowerId.RUPTURE, 0) + amount

    def upgrade(self):
        self.upgraded = True


class SearingBlow(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Searing Blow", "Searing Blow", CardType.ATTACK, CardRarity.UNCOMMON, 2, upgraded)
        self._upgrades = 1 if upgraded else 0

    def _damage(self):
        n = self._upgrades
        return (n * n + 7 * n + 12) // 2 + (n % 2) * 1  # formula from game

    def play(self, state, target=None):
        _deal_damage(state, target, self._damage())

    def upgrade(self):
        self._upgrades += 1
        self.upgraded = True


class SecondWind(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Second Wind", "Second Wind", CardType.SKILL, CardRarity.UNCOMMON, 1, upgraded)

    def play(self, state, target=None):
        block_per = 6 if self.upgraded else 5
        non_attacks = [c for c in state.combat.hand if c.type != CardType.ATTACK and c is not self]
        for c in non_attacks:
            _exhaust_card(state, c)
            _gain_block(state, block_per)

    def upgrade(self):
        self.upgraded = True


class SeeingRed(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Seeing Red", "Seeing Red", CardType.SKILL, CardRarity.UNCOMMON,
                         0 if upgraded else 1, upgraded, exhaust=True)

    def play(self, state, target=None):
        state.player.energy += 2
        _exhaust_card(state, self)

    def upgrade(self):
        self.upgraded = True
        self.cost = 0


class Sentinel(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Sentinel", "Sentinel", CardType.SKILL, CardRarity.UNCOMMON, 1, upgraded)

    def play(self, state, target=None):
        from .enums import PowerId
        _gain_block(state, 8 if self.upgraded else 5)
        state.player.powers[PowerId.SENTINEL] = state.player.powers.get(PowerId.SENTINEL, 0) + (3 if self.upgraded else 2)

    def upgrade(self):
        self.upgraded = True


class SeverSoul(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Sever Soul", "Sever Soul", CardType.ATTACK, CardRarity.UNCOMMON, 2, upgraded)

    def play(self, state, target=None):
        non_attacks = [c for c in state.combat.hand if c.type != CardType.ATTACK and c is not self]
        for c in non_attacks:
            _exhaust_card(state, c)
        dmg = 22 if self.upgraded else 16
        _deal_damage(state, target, dmg)

    def upgrade(self):
        self.upgraded = True


class Shockwave(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Shockwave", "Shockwave", CardType.SKILL, CardRarity.UNCOMMON, 2, upgraded, exhaust=True)

    def play(self, state, target=None):
        from .enums import PowerId
        amount = 5 if self.upgraded else 3
        for e in state.combat.enemies:
            if e.hp > 0:
                _apply_power(state, e, PowerId.WEAK, amount)
                _apply_power(state, e, PowerId.VULNERABLE, amount)
        _exhaust_card(state, self)

    def upgrade(self):
        self.upgraded = True


class SpotWeakness(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Spot Weakness", "Spot Weakness", CardType.SKILL, CardRarity.UNCOMMON, 1, upgraded)

    def play(self, state, target=None):
        from .enums import PowerId
        from .enums import IntentType
        if target and target.current_move and target.current_move.intent in (
            IntentType.ATTACK, IntentType.ATTACK_BUFF, IntentType.ATTACK_DEBUFF, IntentType.ATTACK_DEFEND
        ):
            amount = 4 if self.upgraded else 3
            state.player.powers[PowerId.STRENGTH] = state.player.powers.get(PowerId.STRENGTH, 0) + amount

    def upgrade(self):
        self.upgraded = True


class Uppercut(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Uppercut", "Uppercut", CardType.ATTACK, CardRarity.UNCOMMON, 2, upgraded)

    def play(self, state, target=None):
        from .enums import PowerId
        _deal_damage(state, target, 13)
        if target and target.hp > 0:
            amount = 2 if self.upgraded else 1
            _apply_power(state, target, PowerId.WEAK, amount)
            _apply_power(state, target, PowerId.VULNERABLE, amount)

    def upgrade(self):
        self.upgraded = True


class Whirlwind(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Whirlwind", "Whirlwind", CardType.ATTACK, CardRarity.UNCOMMON, -2, upgraded)

    def play(self, state, target=None):
        x = state.player.energy
        state.player.energy = 0
        dmg = 8 if self.upgraded else 5
        for _ in range(x):
            for e in state.combat.enemies:
                if e.hp > 0:
                    _deal_damage(state, e, dmg)

    def upgrade(self):
        self.upgraded = True


# ── Rare cards ────────────────────────────────────────────────────────────────

class Barricade(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Barricade", "Barricade", CardType.POWER, CardRarity.RARE,
                         2 if not upgraded else 1, upgraded)

    def play(self, state, target=None):
        state.player.barricade = True

    def upgrade(self):
        self.upgraded = True
        self.cost = 1


class Berserk(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Berserk", "Berserk", CardType.POWER, CardRarity.RARE, 0, upgraded)

    def play(self, state, target=None):
        from .enums import PowerId
        vuln = 1 if self.upgraded else 2
        _apply_power(state, state.player, PowerId.VULNERABLE, vuln)
        state.player.berserk = True

    def upgrade(self):
        self.upgraded = True


class Bludgeon(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Bludgeon", "Bludgeon", CardType.ATTACK, CardRarity.RARE, 3, upgraded)

    def play(self, state, target=None):
        _deal_damage(state, target, 42 if self.upgraded else 32)

    def upgrade(self):
        self.upgraded = True


class Brutality(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Brutality", "Brutality", CardType.POWER, CardRarity.RARE, 0, upgraded)

    def play(self, state, target=None):
        state.player.brutality = True
        if self.upgraded:
            state.player.innate_brutality = True

    def upgrade(self):
        self.upgraded = True


class Corruption(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Corruption", "Corruption", CardType.POWER, CardRarity.RARE,
                         3 if not upgraded else 2, upgraded)

    def play(self, state, target=None):
        state.player.corruption = True

    def upgrade(self):
        self.upgraded = True
        self.cost = 2


class DemonForm(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Demon Form", "Demon Form", CardType.POWER, CardRarity.RARE, 3, upgraded)

    def play(self, state, target=None):
        from .enums import PowerId
        amount = 3 if self.upgraded else 2
        state.player.powers[PowerId.DEMON_FORM] = state.player.powers.get(PowerId.DEMON_FORM, 0) + amount

    def upgrade(self):
        self.upgraded = True


class DoubleTap(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Double Tap", "Double Tap", CardType.SKILL, CardRarity.RARE, 1, upgraded)

    def play(self, state, target=None):
        from .enums import PowerId
        amount = 2 if self.upgraded else 1
        state.player.powers[PowerId.DOUBLE_TAP] = state.player.powers.get(PowerId.DOUBLE_TAP, 0) + amount

    def upgrade(self):
        self.upgraded = True


class Exhume(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Exhume", "Exhume", CardType.SKILL, CardRarity.RARE,
                         0 if upgraded else 1, upgraded, exhaust=True)

    def play(self, state, target=None):
        if state.combat.exhaust_pile:
            card = state.combat.exhaust_pile.pop()
            state.combat.hand.append(card)
        _exhaust_card(state, self)

    def upgrade(self):
        self.upgraded = True
        self.cost = 0


class Feed(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Feed", "Feed", CardType.ATTACK, CardRarity.RARE, 1, upgraded, exhaust=True)

    def play(self, state, target=None):
        dmg = 12 if self.upgraded else 10
        hp_gain = 4 if self.upgraded else 3
        _deal_damage(state, target, dmg)
        if target and target.hp <= 0:
            state.player.max_hp += hp_gain
            state.player.hp += hp_gain
        _exhaust_card(state, self)

    def upgrade(self):
        self.upgraded = True


class FiendFire(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Fiend Fire", "Fiend Fire", CardType.ATTACK, CardRarity.RARE, 2, upgraded, exhaust=True)

    def play(self, state, target=None):
        cards = [c for c in state.combat.hand if c is not self]
        dmg = 7 if self.upgraded else 6
        for c in cards:
            _exhaust_card(state, c)
            _deal_damage(state, target, dmg)
        _exhaust_card(state, self)

    def upgrade(self):
        self.upgraded = True


class Immolate(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Immolate", "Immolate", CardType.ATTACK, CardRarity.RARE, 2, upgraded)

    def play(self, state, target=None):
        dmg = 28 if self.upgraded else 21
        for e in state.combat.enemies:
            if e.hp > 0:
                _deal_damage(state, e, dmg)
        state.combat.discard_pile.append(Burn())

    def upgrade(self):
        self.upgraded = True


class Impervious(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Impervious", "Impervious", CardType.SKILL, CardRarity.RARE, 2, upgraded, exhaust=True)

    def play(self, state, target=None):
        _gain_block(state, 40 if self.upgraded else 30)
        _exhaust_card(state, self)

    def upgrade(self):
        self.upgraded = True


class Juggernaut(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Juggernaut", "Juggernaut", CardType.POWER, CardRarity.RARE, 2, upgraded)

    def play(self, state, target=None):
        from .enums import PowerId
        amount = 7 if self.upgraded else 5
        state.player.powers[PowerId.JUGGERNAUT] = state.player.powers.get(PowerId.JUGGERNAUT, 0) + amount

    def upgrade(self):
        self.upgraded = True


class LimitBreak(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Limit Break", "Limit Break", CardType.SKILL, CardRarity.RARE, 1, upgraded,
                         exhaust=not upgraded)

    def play(self, state, target=None):
        from .enums import PowerId
        strength = state.player.powers.get(PowerId.STRENGTH, 0)
        state.player.powers[PowerId.STRENGTH] = strength * 2
        if not self.upgraded:
            _exhaust_card(state, self)

    def upgrade(self):
        self.upgraded = True
        self.exhaust = False


class Offering(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Offering", "Offering", CardType.SKILL, CardRarity.RARE, 0, upgraded, exhaust=True)

    def play(self, state, target=None):
        draw = 5 if self.upgraded else 3
        _damage_player(state, 6, is_hp_loss=True)
        state.player.energy += 2
        _draw_cards(state, draw)
        _exhaust_card(state, self)

    def upgrade(self):
        self.upgraded = True


class Reaper(Card):
    def __init__(self, upgraded: bool = False):
        super().__init__("Reaper", "Reaper", CardType.ATTACK, CardRarity.RARE, 2, upgraded, exhaust=True)

    def play(self, state, target=None):
        dmg = 5 if self.upgraded else 4
        for e in state.combat.enemies:
            if e.hp > 0:
                dealt = _deal_damage(state, e, dmg)
                # heal for damage dealt (unblocked)
                actual = min(dmg, e.hp + min(dmg, e.block) - max(0, e.block - dmg))
                heal = max(0, dmg - max(0, e.block))
                state.player.hp = min(state.player.max_hp, state.player.hp + heal)
        _exhaust_card(state, self)

    def upgrade(self):
        self.upgraded = True


# ── Card registry ─────────────────────────────────────────────────────────────

IRONCLAD_CARD_CLASSES = {
    # Basics
    "Strike_R": Strike, "Defend_R": Defend, "Bash": Bash,
    # Curses/status
    "AscendersBane": AscendersBane, "Burn": Burn, "Dazed": Dazed,
    "Slimed": Slimed, "Wound": Wound, "Void": VoidCard,
    "Clumsy": Clumsy, "Decay": Decay, "Doubt": Doubt, "Injury": Injury,
    "Normality": Normality, "Pain": Pain, "Parasite": Parasite, "Pride": Pride,
    "Regret": Regret, "Shame": Shame, "Writhe": Writhe,
    # Commons
    "Anger": Anger, "Armaments": Armaments, "Body Slam": BodySlam,
    "Clash": Clash, "Cleave": Cleave, "Clothesline": Clothesline,
    "Flex": Flex, "Havoc": Havoc, "Headbutt": Headbutt,
    "Heavy Blade": HeavyBlade, "Iron Wave": IronWave,
    "Perfected Strike": PerfectedStrike, "Pommel Strike": PommelStrike,
    "Shrug It Off": ShrugItOff, "Sword Boomerang": SwordBoomerang,
    "Thunderclap": Thunderclap, "True Grit": TrueGrit,
    "Twin Strike": TwinStrike, "Warcry": Warcry, "Wild Strike": WildStrike,
    # Uncommons
    "Battle Trance": BattleTrance, "Blood for Blood": BloodForBlood,
    "Bloodletting": Bloodletting, "Burning Pact": BurningPact,
    "Carnage": Carnage, "Combust": Combust, "Dark Embrace": DarkEmbrace,
    "Disarm": Disarm, "Dropkick": Dropkick, "Dual Wield": DualWield,
    "Entrench": Entrench, "Evolve": Evolve, "Feel No Pain": FeelNoPain,
    "Fire Breathing": FireBreathing, "Flame Barrier": FlameBarrier,
    "Ghostly Armor": GhostlyArmor, "Hemokinesis": Hemokinesis,
    "Infernal Blade": InfernalBlade, "Inflame": Inflame, "Intimidate": Intimidate,
    "Metallicize": Metallicize, "Power Through": PowerThrough, "Pummel": Pummel,
    "Rage": Rage, "Rampage": Rampage, "Reckless Charge": RecklessCharge,
    "Rupture": Rupture, "Searing Blow": SearingBlow, "Second Wind": SecondWind,
    "Seeing Red": SeeingRed, "Sentinel": Sentinel, "Sever Soul": SeverSoul,
    "Shockwave": Shockwave, "Spot Weakness": SpotWeakness,
    "Uppercut": Uppercut, "Whirlwind": Whirlwind,
    # Rares
    "Barricade": Barricade, "Berserk": Berserk, "Bludgeon": Bludgeon,
    "Brutality": Brutality, "Corruption": Corruption, "Demon Form": DemonForm,
    "Double Tap": DoubleTap, "Exhume": Exhume, "Feed": Feed,
    "Fiend Fire": FiendFire, "Immolate": Immolate, "Impervious": Impervious,
    "Juggernaut": Juggernaut, "Limit Break": LimitBreak, "Offering": Offering,
    "Reaper": Reaper,
}


def make_card(name: str, upgraded: bool = False) -> Card:
    cls = IRONCLAD_CARD_CLASSES.get(name)
    if cls is None:
        raise ValueError(f"Unknown card: {name}")
    try:
        return cls(upgraded)
    except TypeError:
        # Curses and other fixed cards take no `upgraded` argument.
        card = cls()
        if upgraded:
            try:
                card.upgrade()
            except NotImplementedError:
                pass
        return card


def make_card_for(character: str, name: str, upgraded: bool = False) -> Card:
    """Character-aware card factory ('ironclad' | 'silent')."""
    if character == "silent":
        from .cards_silent import make_silent_card
        return make_silent_card(name, upgraded)
    return make_card(name, upgraded)


def starter_deck() -> list[Card]:
    return [
        Strike(), Strike(), Strike(), Strike(), Strike(),
        Defend(), Defend(), Defend(), Defend(),
        Bash(),
    ]
