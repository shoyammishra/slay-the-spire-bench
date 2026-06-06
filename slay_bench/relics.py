"""Relic base class and core Ironclad relics."""
from __future__ import annotations
from typing import TYPE_CHECKING

from .events import Event

if TYPE_CHECKING:
    from .state import GameState
    from .cards import Card
    from .enemies import Enemy


class Relic:
    id: str
    name: str

    def register(self, state: GameState) -> None:
        """Subscribe to relevant events on the state's bus."""
        pass

    def __repr__(self) -> str:
        return self.name


# ── Starter relic ─────────────────────────────────────────────────────────────

class BurningBlood(Relic):
    id = "Burning Blood"
    name = "Burning Blood"

    def register(self, state: GameState) -> None:
        def on_combat_end(gs: GameState, **kw):
            heal = 6
            gs.player.hp = min(gs.player.max_hp, gs.player.hp + heal)
        state.bus.subscribe(Event.COMBAT_END, on_combat_end)


# ── Common relics ─────────────────────────────────────────────────────────────

class Akabeko(Relic):
    id = "Akabeko"
    name = "Akabeko"

    def register(self, state: GameState) -> None:
        from .enums import PowerId
        def on_combat_start(gs: GameState, **kw):
            gs.player.powers[PowerId.VIGOR] = gs.player.powers.get(PowerId.VIGOR, 0) + 8
        state.bus.subscribe(Event.COMBAT_START, on_combat_start)


class Anchor(Relic):
    id = "Anchor"
    name = "Anchor"

    def register(self, state: GameState) -> None:
        def on_combat_start(gs: GameState, **kw):
            gs.player.block += 10
        state.bus.subscribe(Event.COMBAT_START, on_combat_start)


class AncientTeaSet(Relic):
    id = "Ancient Tea Set"
    name = "Ancient Tea Set"
    _triggered = False

    def register(self, state: GameState) -> None:
        def on_rest(gs: GameState, **kw):
            self._triggered = True
        def on_combat_start(gs: GameState, **kw):
            if self._triggered:
                gs.player.energy += 2
                self._triggered = False
        state.bus.subscribe(Event.REST_SITE_ENTER, on_rest)
        state.bus.subscribe(Event.COMBAT_START, on_combat_start)


class ArtOfWar(Relic):
    id = "Art of War"
    name = "Art of War"

    def register(self, state: GameState) -> None:
        self._no_attacks = True

        def on_attack_play(gs: GameState, **kw):
            self._no_attacks = False
        def on_turn_end(gs: GameState, **kw):
            if self._no_attacks:
                gs.player.energy += 1
            self._no_attacks = True
        state.bus.subscribe(Event.ATTACK_PLAY, on_attack_play)
        state.bus.subscribe(Event.TURN_END, on_turn_end)


class BagOfPreparation(Relic):
    id = "Bag of Preparation"
    name = "Bag of Preparation"

    def register(self, state: GameState) -> None:
        self._first = True
        def on_combat_start(gs: GameState, **kw):
            if self._first:
                self._first = False
                from .cards import _draw_cards
                _draw_cards(gs, 2)
        state.bus.subscribe(Event.COMBAT_START, on_combat_start)


class BronzeScales(Relic):
    id = "Bronze Scales"
    name = "Bronze Scales"

    def register(self, state: GameState) -> None:
        from .enums import PowerId
        def on_combat_start(gs: GameState, **kw):
            gs.player.powers[PowerId.THORNS] = gs.player.powers.get(PowerId.THORNS, 0) + 3
        state.bus.subscribe(Event.COMBAT_START, on_combat_start)


class NunchakuRelic(Relic):
    id = "Nunchaku"
    name = "Nunchaku"

    def register(self, state: GameState) -> None:
        self._count = 0

        def on_attack(gs: GameState, card=None, **kw):
            from .enums import CardType
            if card and card.type == CardType.ATTACK:
                self._count += 1
                if self._count >= 10:
                    self._count = 0
                    gs.player.energy += 1
        state.bus.subscribe(Event.CARD_PLAY, on_attack)

    def on_combat_start(self, state):
        self._count = 0


class OddlySmoothStone(Relic):
    id = "Oddly Smooth Stone"
    name = "Oddly Smooth Stone"

    def register(self, state: GameState) -> None:
        from .enums import PowerId
        def on_combat_start(gs: GameState, **kw):
            gs.player.powers[PowerId.DEXTERITY] = gs.player.powers.get(PowerId.DEXTERITY, 0) + 1
        state.bus.subscribe(Event.COMBAT_START, on_combat_start)


class PenNib(Relic):
    id = "Pen Nib"
    name = "Pen Nib"

    def register(self, state: GameState) -> None:
        self._count = 0

        def on_attack(gs: GameState, card=None, **kw):
            from .enums import CardType
            if card and card.type == CardType.ATTACK:
                self._count += 1
                if self._count >= 10:
                    self._count = 0
                    from .enums import PowerId
                    gs.player.powers[PowerId.VIGOR] = gs.player.powers.get(PowerId.VIGOR, 0) + 999  # double next attack
        state.bus.subscribe(Event.CARD_PLAY, on_attack)


class Vajra(Relic):
    id = "Vajra"
    name = "Vajra"

    def register(self, state: GameState) -> None:
        from .enums import PowerId
        def on_combat_start(gs: GameState, **kw):
            gs.player.powers[PowerId.STRENGTH] = gs.player.powers.get(PowerId.STRENGTH, 0) + 1
        state.bus.subscribe(Event.COMBAT_START, on_combat_start)


# ── Uncommon relics ───────────────────────────────────────────────────────────

class IceCream(Relic):
    id = "Ice Cream"
    name = "Ice Cream"

    def register(self, state: GameState) -> None:
        # Energy carries over between turns — handled in combat engine
        state.player._ice_cream = True


class MeatOnTheBone(Relic):
    id = "Meat on the Bone"
    name = "Meat on the Bone"

    def register(self, state: GameState) -> None:
        def on_combat_end(gs: GameState, **kw):
            if gs.player.hp <= gs.player.max_hp // 2:
                gs.player.hp = min(gs.player.max_hp, gs.player.hp + 12)
        state.bus.subscribe(Event.COMBAT_END, on_combat_end)


class Shuriken(Relic):
    id = "Shuriken"
    name = "Shuriken"

    def register(self, state: GameState) -> None:
        self._count = 0
        from .enums import PowerId

        def on_attack(gs: GameState, card=None, **kw):
            from .enums import CardType
            if card and card.type == CardType.ATTACK:
                self._count += 1
                if self._count >= 3:
                    self._count = 0
                    gs.player.powers[PowerId.STRENGTH] = gs.player.powers.get(PowerId.STRENGTH, 0) + 1
        state.bus.subscribe(Event.CARD_PLAY, on_attack)


class Sundial(Relic):
    id = "Sundial"
    name = "Sundial"

    def register(self, state: GameState) -> None:
        self._count = 0

        def on_shuffle(gs: GameState, **kw):
            self._count += 1
            if self._count >= 3:
                self._count = 0
                gs.player.energy += 2
        state.bus.subscribe(Event.CARD_DRAW, on_shuffle)  # approximate


# ── Rare relics ───────────────────────────────────────────────────────────────

class DeadBranch(Relic):
    id = "Dead Branch"
    name = "Dead Branch"

    def register(self, state: GameState) -> None:
        def on_exhaust(gs: GameState, card=None, **kw):
            # Add a random card to hand
            import random
            from .cards import IRONCLAD_CARD_CLASSES, make_card
            name = gs.rng.misc_rng.next_int(len(IRONCLAD_CARD_CLASSES))
            card_name = list(IRONCLAD_CARD_CLASSES.keys())[name]
            gs.combat.hand.append(make_card(card_name))
        state.bus.subscribe(Event.CARD_EXHAUST, on_exhaust)


class LizardTail(Relic):
    id = "Lizard Tail"
    name = "Lizard Tail"
    _used = False

    def register(self, state: GameState) -> None:
        def on_death(gs: GameState, **kw):
            if not self._used:
                self._used = True
                gs.player.hp = max(1, gs.player.max_hp // 2)
                return True  # prevent death
        state.bus.subscribe(Event.DEATH_WOULD_OCCUR, on_death)


class MarkOfPain(Relic):
    id = "Mark of Pain"
    name = "Mark of Pain"

    def register(self, state: GameState) -> None:
        from .enums import PowerId
        state.player.energy_per_turn += 1

        def on_combat_start(gs: GameState, **kw):
            from .cards import Wound
            gs.combat.draw_pile.append(Wound())
            gs.combat.draw_pile.append(Wound())
        state.bus.subscribe(Event.COMBAT_START, on_combat_start)


class RunicDome(Relic):
    id = "Runic Dome"
    name = "Runic Dome"
    # Hides enemy intents — no mechanical effect in simulator, just metadata
    def register(self, state: GameState) -> None:
        pass


class SneckoEye(Relic):
    id = "Snecko Eye"
    name = "Snecko Eye"

    def register(self, state: GameState) -> None:
        from .enums import PowerId
        def on_combat_start(gs: GameState, **kw):
            from .cards import _draw_cards
            _draw_cards(gs, 2)
            gs.player.powers[PowerId.CONFUSED] = 1
        state.bus.subscribe(Event.COMBAT_START, on_combat_start)


# ── Boss relics ───────────────────────────────────────────────────────────────

class BlackBlood(Relic):
    id = "Black Blood"
    name = "Black Blood"

    def register(self, state: GameState) -> None:
        def on_combat_end(gs: GameState, **kw):
            gs.player.hp = min(gs.player.max_hp, gs.player.hp + 12)
        state.bus.subscribe(Event.COMBAT_END, on_combat_end)


# ── Registry ──────────────────────────────────────────────────────────────────

RELIC_REGISTRY = {
    r.id: r for r in [
        BurningBlood, Akabeko, Anchor, AncientTeaSet, ArtOfWar,
        BagOfPreparation, BronzeScales, NunchakuRelic, OddlySmoothStone,
        PenNib, Vajra, IceCream, MeatOnTheBone, Shuriken, Sundial,
        DeadBranch, LizardTail, MarkOfPain, RunicDome, SneckoEye,
        BlackBlood,
    ]
}


def make_relic(relic_id: str) -> Relic:
    cls = RELIC_REGISTRY.get(relic_id)
    if cls is None:
        raise ValueError(f"Unknown relic: {relic_id}")
    return cls()


def random_relic(state: GameState, rarity: str = "common") -> Relic:
    """Return a random relic of the given rarity, using loot_rng."""
    try:
        from .relics_full import _RARITY_POOLS
        pool = _RARITY_POOLS.get(rarity, _RARITY_POOLS["common"])
    except ImportError:
        pool = list(RELIC_REGISTRY.values())
    if not pool:
        pool = list(RELIC_REGISTRY.values())
    idx = state.rng.loot_rng.next_int(len(pool))
    return pool[idx]()
