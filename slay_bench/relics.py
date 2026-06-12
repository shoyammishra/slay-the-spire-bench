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

    def on_pickup(self, state: GameState) -> None:
        """One-time effects applied when the relic is obtained (max HP, energy
        per turn, deck changes, ...). Must NOT go in register(): register() is
        re-run at the start of every combat, so any non-idempotent mutation
        there would stack across a run."""
        pass

    def register(self, state: GameState) -> None:
        """Subscribe to relevant events on the state's bus. Called at the start
        of every combat (the bus is cleared first), so this must only contain
        subscriptions and idempotent flag sets."""
        pass

    def __repr__(self) -> str:
        return self.name


# ── Starter relic ─────────────────────────────────────────────────────────────

class BurningBlood(Relic):
    id = "Burning Blood"
    name = "Burning Blood"

    def register(self, state: GameState) -> None:
        def on_combat_end(gs: GameState, **kw):
            from .cards import _heal_player
            _heal_player(gs, 6)
        state.bus.subscribe(Event.COMBAT_END, on_combat_end)


class RingOfTheSnake(Relic):
    """Silent starter relic: draw 2 additional cards at the start of combat."""
    id = "Ring of the Snake"
    name = "Ring of the Snake"

    def register(self, state: GameState) -> None:
        def on_combat_start(gs: GameState, **kw):
            from .cards import _draw_cards
            _draw_cards(gs, 2)
        state.bus.subscribe(Event.COMBAT_START, on_combat_start)


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
            # Flat relic block (no Dex/Frail), but emit BLOCK_GAINED so
            # Juggernaut and friends fire (E9 / L1 consistency).
            gs.player.block += 10
            gs.bus.emit(Event.BLOCK_GAINED, gs, amount=10)
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
                self._triggered = False
                # Direct energy here would be WIPED by _begin_player_turn's
                # energy reset; ENERGIZED is consumed at TURN_START after it.
                from .enums import PowerId
                gs.player.powers[PowerId.ENERGIZED] = \
                    gs.player.powers.get(PowerId.ENERGIZED, 0) + 2
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
                # Energy added at TURN_END is wiped by the next turn's energy
                # reset — queue ENERGIZED (consumed at TURN_START after it).
                from .enums import PowerId
                gs.player.powers[PowerId.ENERGIZED] = \
                    gs.player.powers.get(PowerId.ENERGIZED, 0) + 1
            self._no_attacks = True
        state.bus.subscribe(Event.ATTACK_PLAY, on_attack_play)
        state.bus.subscribe(Event.TURN_END, on_turn_end)


class BagOfPreparation(Relic):
    id = "Bag of Preparation"
    name = "Bag of Preparation"

    def register(self, state: GameState) -> None:
        # Real StS: draws 2 extra at the start of EVERY combat (no once-only flag).
        def on_combat_start(gs: GameState, **kw):
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
    _count = 0  # persists across combats (real StS) — must not reset in register()

    def register(self, state: GameState) -> None:
        def on_attack(gs: GameState, card=None, **kw):
            from .enums import CardType
            if card and card.type == CardType.ATTACK:
                self._count += 1
                if self._count >= 10:
                    self._count = 0
                    gs.player.energy += 1
        state.bus.subscribe(Event.CARD_PLAY, on_attack)


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
    _count = 0  # persists across combats (real StS) — must not reset in register()

    def register(self, state: GameState) -> None:
        def on_attack(gs: GameState, card=None, **kw):
            from .enums import CardType
            if card and card.type == CardType.ATTACK:
                self._count += 1
                if self._count >= 10:
                    self._count = 0
                    # One-shot flag consumed by _deal_damage: this (10th) attack
                    # deals double damage. CARD_PLAY fires before card.play(),
                    # so the flag is up before the damage is rolled.
                    gs.player._pen_nib_ready = True
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
                from .cards import _heal_player
                _heal_player(gs, 12)
        state.bus.subscribe(Event.COMBAT_END, on_combat_end)


class Shuriken(Relic):
    id = "Shuriken"
    name = "Shuriken"

    def register(self, state: GameState) -> None:
        self._count = 0
        from .enums import PowerId

        def on_turn_start(gs: GameState, **kw):
            # Real StS: "3 Attacks in a SINGLE turn" — counter resets per turn.
            self._count = 0
        state.bus.subscribe(Event.TURN_START, on_turn_start)

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
    _count = 0  # persists across combats (real StS) — must not reset in register()

    def register(self, state: GameState) -> None:
        def on_shuffle(gs: GameState, **kw):
            self._count += 1
            if self._count >= 3:
                self._count = 0
                gs.player.energy += 2
        state.bus.subscribe(Event.SHUFFLE, on_shuffle)


# ── Rare relics ───────────────────────────────────────────────────────────────

class DeadBranch(Relic):
    id = "Dead Branch"
    name = "Dead Branch"

    def register(self, state: GameState) -> None:
        def on_exhaust(gs: GameState, card=None, **kw):
            # Add a random character CARD (attack/skill/power) to hand. Real Dead
            # Branch never adds curses or statuses — the unfiltered class registry
            # included Burn/Wound/Void/Pride/every curse, actively poisoning the
            # exhaust deck it is meant to reward.
            from .cards import IRONCLAD_CARD_CLASSES, make_card_for, _add_card_to_hand
            from .enums import CardType, CardRarity
            character = getattr(gs, "character", "ironclad")
            if character == "silent":
                from .cards_silent import SILENT_CARD_CLASSES as classes
            else:
                classes = IRONCLAD_CARD_CLASSES
            candidates = []
            for name in classes.keys():
                c = make_card_for(character, name)
                if (c.type in (CardType.ATTACK, CardType.SKILL, CardType.POWER)
                        and c.rarity != CardRarity.BASIC):
                    candidates.append(name)
            if not candidates:
                return
            idx = gs.rng.misc_rng.next_int(len(candidates))
            _add_card_to_hand(gs, make_card_for(character, candidates[idx]))
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

    def on_pickup(self, state: GameState) -> None:
        state.player.energy_per_turn += 1

    def register(self, state: GameState) -> None:
        def on_combat_start(gs: GameState, **kw):
            from .cards import Wound
            # Shuffle each Wound into the draw pile (real StS). append() put both
            # on TOP (draw pops the end), so the first two draws of EVERY combat
            # were Wounds.
            for _ in range(2):
                pile = gs.combat.draw_pile
                idx = gs.rng.shuffle_rng.next_int(len(pile) + 1)
                pile.insert(idx, Wound())
        state.bus.subscribe(Event.COMBAT_START, on_combat_start)


class RunicDome(Relic):
    id = "Runic Dome"
    name = "Runic Dome"

    def on_pickup(self, state: GameState) -> None:
        state.player.energy_per_turn += 1

    def register(self, state: GameState) -> None:
        # Downside: enemy intents hidden — prompt_builder omits them when set.
        # (The greedy bot never reads prompts, so the cost falls on the LLM,
        # matching the real trade-off.)
        state.player._runic_dome = True


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
            from .cards import _heal_player
            _heal_player(gs, 12)
        state.bus.subscribe(Event.COMBAT_END, on_combat_end)


# ── Registry ──────────────────────────────────────────────────────────────────

RELIC_REGISTRY = {
    r.id: r for r in [
        BurningBlood, RingOfTheSnake, Akabeko, Anchor, AncientTeaSet, ArtOfWar,
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
    """Return a random relic of the given rarity, using loot_rng.
    Off-class relics are filtered out and already-owned relics deduped."""
    try:
        from .relics_full import _RARITY_POOLS, relic_allowed
        pool = _RARITY_POOLS.get(rarity, _RARITY_POOLS["common"])
        character = getattr(state, "character", "ironclad")
        owned = {r.id for r in state.player.relics}
        allowed = [cls for cls in pool if relic_allowed(cls.id, character)]
        fresh = [cls for cls in allowed if cls.id not in owned]
        # Staged fallback: never fall back to the FULL registry (which leaks
        # off-class relics) just because every fresh relic is owned.
        pool = fresh or allowed or pool
    except ImportError:
        pool = list(RELIC_REGISTRY.values())
    if not pool:
        pool = list(RELIC_REGISTRY.values())
    idx = state.rng.loot_rng.next_int(len(pool))
    return pool[idx]()
