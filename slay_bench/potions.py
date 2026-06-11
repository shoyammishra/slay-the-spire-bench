"""Potion definitions."""
from __future__ import annotations
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .state import GameState
    from .enemies import Enemy


@dataclass
class Potion:
    id: str
    name: str
    requires_target: bool = False

    def use(self, state: GameState, target: Optional[Enemy] = None) -> None:
        raise NotImplementedError

    def __repr__(self) -> str:
        return self.name


class AttackPotion(Potion):
    def __init__(self): super().__init__("Attack Potion", "Attack Potion", requires_target=True)
    def use(self, state, target=None):
        from .cards import _deal_damage
        sacred = _sacred_bark(state)
        _deal_damage(state, target, 10 * sacred)


class BlockPotion(Potion):
    def __init__(self): super().__init__("Block Potion", "Block Potion")
    def use(self, state, target=None):
        from .cards import _gain_block
        _gain_block(state, 12 * _sacred_bark(state))


class StrengthPotion(Potion):
    def __init__(self): super().__init__("Strength Potion", "Strength Potion")
    def use(self, state, target=None):
        from .enums import PowerId
        state.player.powers[PowerId.STRENGTH] = state.player.powers.get(PowerId.STRENGTH, 0) + 2 * _sacred_bark(state)


class DexterityPotion(Potion):
    def __init__(self): super().__init__("Dexterity Potion", "Dexterity Potion")
    def use(self, state, target=None):
        from .enums import PowerId
        state.player.powers[PowerId.DEXTERITY] = state.player.powers.get(PowerId.DEXTERITY, 0) + 2 * _sacred_bark(state)


class EnergyPotion(Potion):
    def __init__(self): super().__init__("Energy Potion", "Energy Potion")
    def use(self, state, target=None):
        state.player.energy += 2 * _sacred_bark(state)


class ExplosivePotion(Potion):
    def __init__(self): super().__init__("Explosive Potion", "Explosive Potion")
    def use(self, state, target=None):
        from .cards import _apply_damage_to_enemy
        dmg = 10 * _sacred_bark(state)
        for e in state.combat.enemies:
            if e.hp > 0:
                _apply_damage_to_enemy(state, e, dmg)


class FirePotion(Potion):
    def __init__(self): super().__init__("Fire Potion", "Fire Potion", requires_target=True)
    def use(self, state, target=None):
        from .cards import _apply_damage_to_enemy
        _apply_damage_to_enemy(state, target, 20 * _sacred_bark(state))


class FearPotion(Potion):
    def __init__(self): super().__init__("Fear Potion", "Fear Potion")
    def use(self, state, target=None):
        from .cards import _apply_power
        from .enums import PowerId
        amt = 3 * _sacred_bark(state)
        for e in state.combat.enemies:
            if e.hp > 0:
                _apply_power(state, e, PowerId.VULNERABLE, amt)


class WeakenPotion(Potion):
    def __init__(self): super().__init__("Weaken Potion", "Weaken Potion")
    def use(self, state, target=None):
        from .cards import _apply_power
        from .enums import PowerId
        amt = 3 * _sacred_bark(state)
        for e in state.combat.enemies:
            if e.hp > 0:
                _apply_power(state, e, PowerId.WEAK, amt)


class SwiftPotion(Potion):
    def __init__(self): super().__init__("Swift Potion", "Swift Potion")
    def use(self, state, target=None):
        from .cards import _draw_cards
        _draw_cards(state, 3 * _sacred_bark(state))


class BloodPotion(Potion):
    def __init__(self): super().__init__("Blood Potion", "Blood Potion")
    def use(self, state, target=None):
        heal = int(state.player.max_hp * 0.2 * _sacred_bark(state))
        state.player.hp = min(state.player.max_hp, state.player.hp + heal)


class FruitJuice(Potion):
    def __init__(self): super().__init__("Fruit Juice", "Fruit Juice")
    def use(self, state, target=None):
        n = 5 * _sacred_bark(state)
        state.player.max_hp += n
        state.player.hp += n


class AncientPotion(Potion):
    def __init__(self): super().__init__("Ancient Potion", "Ancient Potion")
    def use(self, state, target=None):
        from .enums import PowerId
        state.player.powers[PowerId.ARTIFACT] = state.player.powers.get(PowerId.ARTIFACT, 0) + 1 * _sacred_bark(state)


class PowerPotion(Potion):
    def __init__(self): super().__init__("Power Potion", "Power Potion")
    def use(self, state, target=None):
        # Play a random power card
        from .rewards import _IRONCLAD_POOL
        from .enums import CardRarity
        from .cards import make_card
        powers_in_pool = [n for n in _IRONCLAD_POOL[CardRarity.UNCOMMON] + _IRONCLAD_POOL[CardRarity.RARE]
                          if make_card(n).type.name == "POWER"]
        if powers_in_pool:
            idx = state.rng.misc_rng.next_int(len(powers_in_pool))
            card = make_card(powers_in_pool[idx])
            card.cost_override = 0
            card.play(state, target)


class SkillPotion(Potion):
    def __init__(self): super().__init__("Skill Potion", "Skill Potion")
    def use(self, state, target=None):
        from .rewards import _IRONCLAD_POOL
        from .enums import CardRarity
        from .cards import make_card, CardType
        skills = [n for n in _IRONCLAD_POOL[CardRarity.COMMON] + _IRONCLAD_POOL[CardRarity.UNCOMMON]
                  if make_card(n).type == CardType.SKILL]
        if skills:
            idx = state.rng.misc_rng.next_int(len(skills))
            card = make_card(skills[idx])
            card.cost_override = 0
            state.combat.hand.append(card)


class ColorlessPotion(Potion):
    def __init__(self): super().__init__("Colorless Potion", "Colorless Potion")
    def use(self, state, target=None):
        # Add random colorless card to hand at 0 cost
        from .cards import make_card
        colorless = ["Bite", "Flash of Steel", "Mind Blast", "Swift Strike"]
        idx = state.rng.misc_rng.next_int(len(colorless))
        card = make_card(colorless[idx]) if colorless[idx] in __import__('slay_bench.cards', fromlist=['IRONCLAD_CARD_CLASSES']).IRONCLAD_CARD_CLASSES else None
        if card:
            card.cost_override = 0
            state.combat.hand.append(card)


class DuplicationPotion(Potion):
    def __init__(self): super().__init__("Duplication Potion", "Duplication Potion")
    def use(self, state, target=None):
        # Next card played this turn plays twice
        from .enums import PowerId
        state.player.powers[PowerId.DOUBLE_TAP] = state.player.powers.get(PowerId.DOUBLE_TAP, 0) + 1 * _sacred_bark(state)


class GamblersBrew(Potion):
    def __init__(self): super().__init__("Gambler's Brew", "Gambler's Brew")
    def use(self, state, target=None):
        # Discard any number of cards, draw that many. Route through
        # _discard_from_hand so discard triggers (Reflex/Tactician/Tingsha,
        # discarded_this_turn) fire like a real discard.
        from .cards import _draw_cards, _discard_from_hand
        n = len(state.combat.hand)
        for c in list(state.combat.hand):
            _discard_from_hand(state, c)
        _draw_cards(state, n)


class RegenPotion(Potion):
    def __init__(self): super().__init__("Regen Potion", "Regen Potion")
    def use(self, state, target=None):
        from .enums import PowerId
        state.player.powers[PowerId.REGENERATE] = state.player.powers.get(PowerId.REGENERATE, 0) + 5 * _sacred_bark(state)


class FairyInABottle(Potion):
    """Triggers automatically on death, cannot be used manually."""
    def __init__(self): super().__init__("Fairy in a Bottle", "Fairy in a Bottle")
    _triggered = False

    def register(self, state: GameState) -> None:
        from .events import Event
        def on_death(gs, **kw):
            if not self._triggered:
                self._triggered = True
                heal = int(gs.player.max_hp * 0.3 * _sacred_bark(gs))
                gs.player.hp = max(1, heal)
                gs.player.potions.remove(self)
                return True
        state.bus.subscribe(Event.DEATH_WOULD_OCCUR, on_death)

    def use(self, state, target=None):
        pass  # Cannot use manually


def _sacred_bark(state: GameState) -> int:
    """Returns 2 if Sacred Bark relic is held, else 1."""
    return 2 if any(r.id == "Sacred Bark" for r in state.player.relics) else 1


POTION_POOL = [
    AttackPotion, BlockPotion, StrengthPotion, DexterityPotion,
    EnergyPotion, ExplosivePotion, FirePotion, FearPotion,
    WeakenPotion, SwiftPotion, BloodPotion, FruitJuice,
    AncientPotion, PowerPotion, SkillPotion, DuplicationPotion,
    GamblersBrew, RegenPotion, FairyInABottle,
]

POTION_REGISTRY = {cls().id: cls for cls in POTION_POOL}


def random_potion(state: GameState) -> Potion:
    idx = state.rng.potion_rng.next_int(len(POTION_POOL))
    return POTION_POOL[idx]()
