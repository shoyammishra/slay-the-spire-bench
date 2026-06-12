"""Full relic pool: ~130 relics across all rarities."""
from __future__ import annotations
from typing import TYPE_CHECKING

from .events import Event
from .relics import Relic, RELIC_REGISTRY

if TYPE_CHECKING:
    from .state import GameState


# ── Common Relics ─────────────────────────────────────────────────────────────

class BagOfMarbles(Relic):
    id = "Bag of Marbles"
    name = "Bag of Marbles"
    def register(self, state):
        from .enums import PowerId
        def on_combat_start(gs, **kw):
            for e in gs.combat.enemies:
                from .cards import _apply_power
                _apply_power(gs, e, PowerId.VULNERABLE, 1)
        state.bus.subscribe(Event.COMBAT_START, on_combat_start)


class BloodVial(Relic):
    id = "Blood Vial"
    name = "Blood Vial"
    def register(self, state):
        def on_combat_start(gs, **kw):
            from .cards import _heal_player
            _heal_player(gs, 2)
        state.bus.subscribe(Event.COMBAT_START, on_combat_start)


class CentennialPuzzle(Relic):
    id = "Centennial Puzzle"
    name = "Centennial Puzzle"
    _triggered = False
    def register(self, state):
        # Once per COMBAT (register runs at every combat start)
        self._triggered = False
        def on_damage(gs, **kw):
            if gs.combat is None:  # event HP loss between combats
                return
            if not self._triggered:
                self._triggered = True
                from .cards import _draw_cards
                _draw_cards(gs, 3)
        state.bus.subscribe(Event.DAMAGE_TAKEN, on_damage)


class CeramicFish(Relic):
    id = "Ceramic Fish"
    name = "Ceramic Fish"
    def register(self, state):
        def on_card_add(gs, **kw):
            gs.player.gold += 9
        state.bus.subscribe(Event.CARD_ADDED, on_card_add)


class DreamCatcher(Relic):
    id = "Dream Catcher"
    name = "Dream Catcher"
    def register(self, state):
        def on_rest(gs, **kw):
            from .rewards import generate_card_reward
            gs._dream_catcher_offer = generate_card_reward(gs, 1)
        state.bus.subscribe(Event.REST_SITE_ENTER, on_rest)


class HappyFlower(Relic):
    id = "Happy Flower"
    name = "Happy Flower"
    _count = 0  # persists across combats (real StS) — must not reset in register()
    def register(self, state):
        def on_turn_start(gs, **kw):
            self._count += 1
            if self._count >= 3:
                self._count = 0
                gs.player.energy += 1
        state.bus.subscribe(Event.TURN_START, on_turn_start)


class JuzuBracelet(Relic):
    id = "Juzu Bracelet"
    name = "Juzu Bracelet"
    def register(self, state):
        # No curses appear in card rewards
        state.player._juzu = True


class Lantern(Relic):
    id = "Lantern"
    name = "Lantern"
    def register(self, state):
        def on_combat_start(gs, **kw):
            # Direct energy here is WIPED by _begin_player_turn's reset;
            # ENERGIZED is consumed at TURN_START after the reset.
            from .enums import PowerId
            gs.player.powers[PowerId.ENERGIZED] = \
                gs.player.powers.get(PowerId.ENERGIZED, 0) + 1
        state.bus.subscribe(Event.COMBAT_START, on_combat_start)


class MawBank(Relic):
    id = "Maw Bank"
    name = "Maw Bank"
    def register(self, state):
        # +12 gold per floor climbed (RunState.move_to); any shop purchase
        # clears the flag (nodes.py buy_*/remove_card).
        state.player._maw_bank = True


class MealTicket(Relic):
    id = "Meal Ticket"
    name = "Meal Ticket"
    def register(self, state):
        state.player._meal_ticket = True


class Omamori(Relic):
    id = "Omamori"
    name = "Omamori"
    _charges = 2  # per RUN, not per combat — must not reset in register()
    def register(self, state):
        def on_card_add(gs, card=None, **kw):
            from .enums import CardType
            if card and card.type == CardType.CURSE and self._charges > 0:
                self._charges -= 1
                gs.player.deck.remove(card)
        state.bus.subscribe(Event.CARD_ADDED, on_card_add)


class Orichalcum(Relic):
    id = "Orichalcum"
    name = "Orichalcum"
    def register(self, state):
        def on_turn_end(gs, **kw):
            if gs.player.block == 0:
                # Relic block is flat (no Dex/Frail), so don't route through
                # _gain_block — but still emit BLOCK_GAINED so Juggernaut fires.
                gs.player.block += 6
                gs.bus.emit(Event.BLOCK_GAINED, gs, amount=6)
        state.bus.subscribe(Event.TURN_END, on_turn_end)


class PaperKrane(Relic):
    id = "Paper Krane"
    name = "Paper Krane"
    def register(self, state):
        # Weak applies 40% reduction instead of 25%
        state.player._paper_krane = True


class PaperPhrog(Relic):
    id = "Paper Phrog"
    name = "Paper Phrog"
    def register(self, state):
        # Vulnerable applies 75% bonus instead of 50%
        state.player._paper_phrog = True


class PreservedInsect(Relic):
    id = "Preserved Insect"
    name = "Preserved Insect"
    def register(self, state):
        def on_combat_start(gs, **kw):
            # Elites only (spawn sites tag _elite) — the old max_hp>100 proxy
            # also hit bosses.
            for e in gs.combat.enemies:
                if getattr(e, '_elite', False):
                    e.hp = int(e.hp * 0.75)
        state.bus.subscribe(Event.COMBAT_START, on_combat_start)


class RegalPillow(Relic):
    id = "Regal Pillow"
    name = "Regal Pillow"
    def register(self, state):
        # Extra 15 HP when resting — handled in resolve_rest
        pass


class SmilingMask(Relic):
    id = "Smiling Mask"
    name = "Smiling Mask"
    def register(self, state):
        state.player._smiling_mask = True  # card removal always costs 50


class SneckoSkull(Relic):
    id = "Snecko Skull"
    name = "Snecko Skull"
    def register(self, state):
        # +1 whenever the player applies Poison to an enemy — consumed in
        # _apply_power. (The old TURN_END hook grew the PLAYER's own poison.)
        state.player._snecko_skull = True


class Strawberry(Relic):
    id = "Strawberry"
    name = "Strawberry"
    def on_pickup(self, state):
        state.player.max_hp += 7
        state.player.hp += 7


class TinyChest(Relic):
    id = "Tiny Chest"
    name = "Tiny Chest"
    _count = 0  # per RUN — resetting in register() meant it could NEVER reach 4
    def register(self, state):
        def on_combat_end(gs, **kw):
            self._count += 1
            if self._count >= 4:
                self._count = 0
                from .nodes import resolve_treasure
                resolve_treasure(gs)
        state.bus.subscribe(Event.COMBAT_END, on_combat_end)


# ── Uncommon Relics ───────────────────────────────────────────────────────────

class BlueCandle(Relic):
    id = "Blue Candle"
    name = "Blue Candle"
    def register(self, state):
        # Makes curses playable (checked in Card.can_play — without this flag
        # the CARD_PLAY hook below could never fire and the relic was a no-op)
        state.player._blue_candle = True
        def on_card_play(gs, card=None, **kw):
            from .enums import CardType
            if card and card.type == CardType.CURSE:
                from .cards import _exhaust_card, _damage_player
                _damage_player(gs, 1, is_hp_loss=True)
                _exhaust_card(gs, card)
        state.bus.subscribe(Event.CARD_PLAY, on_card_play)


class BottledFlame(Relic):
    id = "Bottled Flame"
    name = "Bottled Flame"
    def on_pickup(self, state):
        # Bottle the first attack in the master deck: innate is honored at
        # start_combat (deck copies keep the flag).
        from .enums import CardType
        for c in state.player.deck:
            if c.type == CardType.ATTACK:
                c.innate = True
                break


class DarkstonePeriapt(Relic):
    id = "Darkstone Periapt"
    name = "Darkstone Periapt"
    def register(self, state):
        def on_card_add(gs, card=None, **kw):
            from .enums import CardType
            if card and card.type == CardType.CURSE:
                gs.player.max_hp += 6
                gs.player.hp += 6
        state.bus.subscribe(Event.CARD_ADDED, on_card_add)


class EternalFeather(Relic):
    id = "Eternal Feather"
    name = "Eternal Feather"
    def register(self, state):
        def on_rest(gs, **kw):
            gain = (len(gs.player.deck) // 5) * 3
            gs.player.hp = min(gs.player.max_hp, gs.player.hp + gain)
        state.bus.subscribe(Event.REST_SITE_ENTER, on_rest)


class FrozenEgg(Relic):
    id = "Frozen Egg"
    name = "Frozen Egg"
    def register(self, state):
        # Upgraded versions of all cards appear in card rewards
        state.player._frozen_egg = True


class GamblingChip(Relic):
    id = "Gambling Chip"
    name = "Gambling Chip"
    def register(self, state):
        # Mulligan of the opening hand happens in _begin_player_turn (the hand
        # doesn't exist yet at COMBAT_START): basic Strikes/Defends are
        # discarded and replaced, once per combat.
        state.player._gambling_chip = True


class Ginger(Relic):
    id = "Ginger"
    name = "Ginger"
    def register(self, state):
        from .enums import PowerId
        def on_apply_weak(gs, **kw):
            pass  # Weak cannot be applied to player
        # Implemented at point of _apply_power
        state.player._immune_weak = True


class GoldenBell(Relic):
    id = "Golden Bell"
    name = "Golden Bell"
    def register(self, state):
        def on_combat_end(gs, **kw):
            gs.player.gold += 25
        state.bus.subscribe(Event.COMBAT_END, on_combat_end)


class GremlinHorn(Relic):
    id = "Gremlin Horn"
    name = "Gremlin Horn"
    def register(self, state):
        def on_enemy_death(gs, target=None, **kw):
            gs.player.energy += 1
            from .cards import _draw_cards
            _draw_cards(gs, 1)
        state.bus.subscribe(Event.ENEMY_DEATH, on_enemy_death)


class HandDrill(Relic):
    id = "Hand Drill"
    name = "Hand Drill"
    def register(self, state):
        from .enums import PowerId
        def on_exhaust(gs, card=None, **kw):
            for e in gs.combat.enemies:
                if e.hp > 0:
                    from .cards import _apply_power
                    _apply_power(gs, e, PowerId.VULNERABLE, 2)
        state.bus.subscribe(Event.CARD_EXHAUST, on_exhaust)


class IncensesBurner(Relic):
    id = "Incense Burner"
    name = "Incense Burner"
    _count = 0  # persists across combats (real StS) — must not reset in register()
    def register(self, state):
        def on_turn_start(gs, **kw):
            self._count += 1
            if self._count >= 6:
                self._count = 0
                from .enums import PowerId
                gs.player.powers[PowerId.INTANGIBLE] = gs.player.powers.get(PowerId.INTANGIBLE, 0) + 1
        state.bus.subscribe(Event.TURN_START, on_turn_start)


class LetterOpener(Relic):
    id = "Letter Opener"
    name = "Letter Opener"
    def register(self, state):
        self._count = 0
        def on_turn_start(gs, **kw):
            # Real StS: "3 Skills in a SINGLE turn" — counter resets per turn.
            self._count = 0
        state.bus.subscribe(Event.TURN_START, on_turn_start)
        def on_skill_play(gs, card=None, **kw):
            self._count += 1
            if self._count >= 3:
                self._count = 0
                for e in gs.combat.enemies:
                    if e.hp > 0:
                        from .cards import _apply_damage_to_enemy
                        _apply_damage_to_enemy(gs, e, 5)
        state.bus.subscribe(Event.SKILL_PLAY, on_skill_play)


class MercuryHourglass(Relic):
    id = "Mercury Hourglass"
    name = "Mercury Hourglass"
    def register(self, state):
        def on_turn_start(gs, **kw):
            for e in gs.combat.enemies:
                if e.hp > 0:
                    from .cards import _apply_damage_to_enemy
                    _apply_damage_to_enemy(gs, e, 3)
        state.bus.subscribe(Event.TURN_START, on_turn_start)


class MoltenEgg(Relic):
    id = "Molten Egg"
    name = "Molten Egg"
    def register(self, state):
        state.player._molten_egg = True  # attacks in reward upgraded


class MummifiedHand(Relic):
    id = "Mummified Hand"
    name = "Mummified Hand"
    def register(self, state):
        def on_power_play(gs, card=None, **kw):
            # Real StS: whenever a Power is played, ONE random card in hand
            # costs 0 (not -1 to everything).
            from .enums import CardType
            if card and card.type == CardType.POWER:
                candidates = [c for c in gs.combat.hand if c.effective_cost() > 0]
                if candidates:
                    pick = candidates[gs.rng.misc_rng.next_int(len(candidates))]
                    pick.cost_override = 0
        state.bus.subscribe(Event.CARD_PLAY, on_power_play)


class OrangelPellets(Relic):
    id = "Orange Pellets"
    name = "Orange Pellets"
    def register(self, state):
        self._attack = False; self._skill = False; self._power = False
        from .enums import CardType
        def on_turn_start(gs, **kw):
            # Real StS: Attack+Skill+Power in a SINGLE turn — reset per turn.
            self._attack = self._skill = self._power = False
        state.bus.subscribe(Event.TURN_START, on_turn_start)
        def on_card_play(gs, card=None, **kw):
            if card:
                if card.type == CardType.ATTACK: self._attack = True
                elif card.type == CardType.SKILL: self._skill = True
                elif card.type == CardType.POWER: self._power = True
            if self._attack and self._skill and self._power:
                self._attack = self._skill = self._power = False
                for p in list(gs.player.powers.keys()):
                    from .enums import PowerId
                    if p in {PowerId.WEAK, PowerId.VULNERABLE, PowerId.FRAIL}:
                        del gs.player.powers[p]
        state.bus.subscribe(Event.CARD_PLAY, on_card_play)


class Pantograph(Relic):
    id = "Pantograph"
    name = "Pantograph"
    def register(self, state):
        def on_boss_defeated(gs, **kw):
            gs.player.hp = min(gs.player.max_hp, gs.player.hp + 25)
        state.bus.subscribe(Event.BOSS_DEFEATED, on_boss_defeated)


class Pear(Relic):
    id = "Pear"
    name = "Pear"
    def on_pickup(self, state):
        state.player.max_hp += 10
        state.player.hp += 10


class StrikeDummy(Relic):
    id = "Strike Dummy"
    name = "Strike Dummy"
    def register(self, state):
        state.player._strike_dummy = True  # Strikes deal +3 damage


class TeardropLocket(Relic):
    id = "Teardrop Locket"
    name = "Teardrop Locket"
    def register(self, state):
        def on_combat_start(gs, **kw):
            gs.player.powers["Calm"] = 1
        state.bus.subscribe(Event.COMBAT_START, on_combat_start)


class ToxicEgg(Relic):
    id = "Toxic Egg"
    name = "Toxic Egg"
    def register(self, state):
        state.player._toxic_egg = True  # skills in reward upgraded


class WhiteBeastStatue(Relic):
    id = "White Beast Statue"
    name = "White Beast Statue"
    def register(self, state):
        state.player._potion_always = True  # always drop potions


# ── Rare Relics ───────────────────────────────────────────────────────────────

class Astrolabe(Relic):
    id = "Astrolabe"
    name = "Astrolabe"
    def on_pickup(self, state):
        # Transform 3 cards in starting deck, upgrade them
        from .cards import make_card_for
        from .rewards import card_pool_for
        from .enums import CardRarity
        character = getattr(state, "character", "ironclad")
        pool = card_pool_for(state)[CardRarity.UNCOMMON]
        for _ in range(3):
            if state.player.deck:
                idx = state.rng.misc_rng.next_int(len(state.player.deck))
                name = pool[state.rng.misc_rng.next_int(len(pool))]
                state.player.deck[idx] = make_card_for(character, name, upgraded=True)


class BlackStar(Relic):
    id = "Black Star"
    name = "Black Star"
    def on_pickup(self, state):
        # Elites drop an additional relic — read at the elite-win drop sites.
        state.player._black_star = True


class BustedCrown(Relic):
    id = "Busted Crown"
    name = "Busted Crown"
    def on_pickup(self, state):
        state.player.energy_per_turn += 1
        state.player._busted_crown = True  # only 2 card reward choices


class Calipers(Relic):
    id = "Calipers"
    name = "Calipers"
    def register(self, state):
        state.player._calipers = True  # retain up to 15 block between turns

    # Applied in _begin_player_turn: if _calipers, retain min(block, 15)


class CaptainsWheel(Relic):
    id = "Captain's Wheel"
    name = "Captain's Wheel"
    def register(self, state):
        def on_turn_start(gs, **kw):
            if gs.combat and gs.combat.turn == 3:
                gs.player.block += 18  # flat relic block (no Dex/Frail)
                gs.bus.emit(Event.BLOCK_GAINED, gs, amount=18)
        state.bus.subscribe(Event.TURN_START, on_turn_start)


class CloakClasp(Relic):
    id = "Cloak Clasp"
    name = "Cloak Clasp"
    def register(self, state):
        def on_turn_end(gs, **kw):
            amt = len(gs.combat.hand)
            if amt:
                gs.player.block += amt  # flat relic block (no Dex/Frail)
                gs.bus.emit(Event.BLOCK_GAINED, gs, amount=amt)
        state.bus.subscribe(Event.TURN_END, on_turn_end)


class CrystalBall(Relic):
    id = "Crystal Ball"
    name = "Crystal Ball"
    def register(self, state):
        # Player can look at top 3 cards of draw pile at end of turn
        state.player._crystal_ball = True


class DuVuDoll(Relic):
    id = "Du-Vu Doll"
    name = "Du-Vu Doll"
    def register(self, state):
        from .enums import CardType
        curses = sum(1 for c in state.player.deck if c.type == CardType.CURSE)
        from .enums import PowerId
        def on_combat_start(gs, **kw):
            from .enums import CardType, PowerId
            n = sum(1 for c in gs.player.deck if c.type == CardType.CURSE)
            gs.player.powers[PowerId.STRENGTH] = gs.player.powers.get(PowerId.STRENGTH, 0) + n
        state.bus.subscribe(Event.COMBAT_START, on_combat_start)


class EmptyCage(Relic):
    id = "Empty Cage"
    name = "Empty Cage"
    def on_pickup(self, state):
        # Remove 2 cards from deck on obtain
        for _ in range(2):
            if state.player.deck:
                idx = state.rng.misc_rng.next_int(len(state.player.deck))
                state.player.deck.pop(idx)
                # Count toward the run-wide removal counter (Winged Statue etc.)
                state.player._cards_removed = \
                    getattr(state.player, '_cards_removed', 0) + 1


class FossilizedHelix(Relic):
    id = "Fossilized Helix"
    name = "Fossilized Helix"
    def register(self, state):
        def on_combat_start(gs, **kw):
            # Consumed in _damage_player: the first HP loss each combat → 0.
            gs.player._helix_ready = True
        state.bus.subscribe(Event.COMBAT_START, on_combat_start)


class HoveringKite(Relic):
    id = "Hovering Kite"
    name = "Hovering Kite"
    def register(self, state):
        self._used = False
        def on_turn_start(gs, **kw):
            self._used = False
        def on_discard(gs, card=None, **kw):
            if not self._used:
                self._used = True
                gs.player.energy += 1
        state.bus.subscribe(Event.TURN_START, on_turn_start)
        state.bus.subscribe(Event.CARD_DISCARD, on_discard)


class LeesWaffle(Relic):
    id = "Lee's Waffle"
    name = "Lee's Waffle"
    def on_pickup(self, state):
        state.player.max_hp += 7
        state.player.hp = state.player.max_hp


class MagicFlower(Relic):
    id = "Magic Flower"
    name = "Magic Flower"
    def register(self, state):
        state.player._magic_flower = True  # heals 50% more


class Mango(Relic):
    id = "Mango"
    name = "Mango"
    def on_pickup(self, state):
        state.player.max_hp += 14
        state.player.hp += 14


class OldCoin(Relic):
    id = "Old Coin"
    name = "Old Coin"
    def on_pickup(self, state):
        state.player.gold += 300


class PeacePipe(Relic):
    id = "Peace Pipe"
    name = "Peace Pipe"
    def register(self, state):
        state.player._peace_pipe = True  # can remove card at rest


class Pocketwatch(Relic):
    id = "Pocketwatch"
    name = "Pocketwatch"
    def register(self, state):
        def on_turn_end(gs, **kw):
            # Draw 3 additional cards NEXT turn (drawing now would be pointless:
            # the hand is discarded right after TURN_END)
            if gs.combat and gs.combat.cards_played_this_turn <= 3:
                from .enums import PowerId
                gs.player.powers[PowerId.NEXT_TURN_DRAW] = \
                    gs.player.powers.get(PowerId.NEXT_TURN_DRAW, 0) + 3
        state.bus.subscribe(Event.TURN_END, on_turn_end)


class PrayerWheel(Relic):
    id = "Prayer Wheel"
    name = "Prayer Wheel"
    def register(self, state):
        state.player._prayer_wheel = True  # extra card in combat rewards


class RunicCube(Relic):
    id = "Runic Cube"
    name = "Runic Cube"
    def register(self, state):
        def on_damage(gs, **kw):
            if gs.combat is None:  # event HP loss between combats
                return
            from .cards import _draw_cards
            _draw_cards(gs, 1)
        state.bus.subscribe(Event.DAMAGE_TAKEN, on_damage)


class SacredBark(Relic):
    id = "Sacred Bark"
    name = "Sacred Bark"
    def register(self, state):
        pass  # effect checked via _sacred_bark() in potions.py


class SelfFormingClay(Relic):
    id = "Self-Forming Clay"
    name = "Self-Forming Clay"
    def register(self, state):
        def on_damage(gs, **kw):
            # Real StS: block NEXT turn, not immediately (immediate block would
            # soak later hits in the same enemy phase).
            from .enums import PowerId
            gs.player.powers[PowerId.NEXT_TURN_BLOCK] = \
                gs.player.powers.get(PowerId.NEXT_TURN_BLOCK, 0) + 3
        state.bus.subscribe(Event.DAMAGE_TAKEN, on_damage)


class SlaverCollar(Relic):
    id = "Slaver's Collar"
    name = "Slaver's Collar"
    def register(self, state):
        def on_turn_start(gs, **kw):
            # +1 energy per turn during elite/boss combats (spawn sites tag
            # enemies). TURN_START fires after the energy reset, so this sticks.
            enemies = gs.combat.enemies if gs.combat else []
            if any(getattr(e, '_elite', False) or getattr(e, '_boss', False)
                   for e in enemies):
                gs.player.energy += 1
        state.bus.subscribe(Event.TURN_START, on_turn_start)


class Sozu(Relic):
    id = "Sozu"
    name = "Sozu"
    def on_pickup(self, state):
        state.player.energy_per_turn += 1
        state.player._no_potions = True


class TheAbacus(Relic):
    id = "The Abacus"
    name = "The Abacus"
    def register(self, state):
        def on_shuffle(gs, **kw):
            gs.player.block += 6
        state.bus.subscribe(Event.SHUFFLE, on_shuffle)


class TheBoot(Relic):
    id = "The Boot"
    name = "The Boot"
    def register(self, state):
        state.player._the_boot = True  # attacks that deal <5 deal 5 instead


class TinghSha(Relic):
    id = "Tingsha"
    name = "Tingsha"
    def register(self, state):
        def on_discard(gs, card=None, **kw):
            for e in gs.combat.enemies:
                if e.hp > 0:
                    from .cards import _apply_damage_to_enemy
                    _apply_damage_to_enemy(gs, e, 3)
        state.bus.subscribe(Event.CARD_DISCARD, on_discard)


class Torii(Relic):
    id = "Torii"
    name = "Torii"
    def register(self, state):
        state.player._torii = True  # attacks that deal <=5 deal 1 instead


class ToughBandages(Relic):
    id = "Tough Bandages"
    name = "Tough Bandages"
    def register(self, state):
        def on_discard(gs, card=None, **kw):
            gs.player.block += 3
        state.bus.subscribe(Event.CARD_DISCARD, on_discard)


class ToyOrnithopter(Relic):
    id = "Toy Ornithopter"
    name = "Toy Ornithopter"
    def register(self, state):
        def on_potion_use(gs, **kw):
            gs.player.hp = min(gs.player.max_hp, gs.player.hp + 5)
        state.bus.subscribe(Event.POTION_USED, on_potion_use)


class TungstenRod(Relic):
    id = "Tungsten Rod"
    name = "Tungsten Rod"
    def register(self, state):
        state.player._tungsten_rod = True  # all HP loss reduced by 1


class Turnip(Relic):
    id = "Turnip"
    name = "Turnip"
    def register(self, state):
        state.player._immune_frail = True


class UnceasingTop(Relic):
    id = "Unceasing Top"
    name = "Unceasing Top"
    def register(self, state):
        def on_empty_hand(gs, **kw):
            if not gs.combat.hand:
                from .cards import _draw_cards
                _draw_cards(gs, 1)
        state.bus.subscribe(Event.CARD_PLAY, on_empty_hand)


class VelvetChoker(Relic):
    id = "Velvet Choker"
    name = "Velvet Choker"
    def on_pickup(self, state):
        state.player.energy_per_turn += 1
        state.player._velvet_choker = True  # can only play 6 cards per turn


# ── Shop Relics ───────────────────────────────────────────────────────────────

class Cauldron(Relic):
    id = "Cauldron"
    name = "Cauldron"
    def on_pickup(self, state):
        from .potions import random_potion
        for _ in range(5):
            if len(state.player.potions) < 3:
                state.player.potions.append(random_potion(state))


class ChemicalX(Relic):
    id = "Chemical X"
    name = "Chemical X"
    def register(self, state):
        state.player._chemical_x = True  # X-cost cards do +2


class ClockworkSouvenir(Relic):
    id = "Clockwork Souvenir"
    name = "Clockwork Souvenir"
    def register(self, state):
        from .enums import PowerId
        def on_combat_start(gs, **kw):
            gs.player.powers[PowerId.ARTIFACT] = gs.player.powers.get(PowerId.ARTIFACT, 0) + 1
        state.bus.subscribe(Event.COMBAT_START, on_combat_start)


class DollysMirror(Relic):
    id = "Dolly's Mirror"
    name = "Dolly's Mirror"
    def on_pickup(self, state):
        # Real effect: duplicate a card. Deterministic stand-in: copy the first
        # non-basic, non-curse deck card (fallback: first card).
        from .enums import CardType
        deck = state.player.deck
        if not deck:
            return
        basics = {"Strike", "Defend"}
        pick = next((c for c in deck
                     if c.name not in basics and c.type != CardType.CURSE),
                    deck[0])
        deck.append(pick.copy())


class FrozenEye(Relic):
    id = "Frozen Eye"
    name = "Frozen Eye"
    def register(self, state):
        state.player._frozen_eye = True  # can see draw pile order


class MembershipCard(Relic):
    id = "Membership Card"
    name = "Membership Card"
    def register(self, state):
        pass  # 50% discount — applied in generate_shop


class TinyHouse(Relic):
    id = "Tiny House"
    name = "Tiny House"
    def on_pickup(self, state):
        state.player.gold += 50
        state.player.max_hp += 5
        state.player.hp += 5
        state.player.energy_per_turn += 1
        from .rewards import generate_card_reward
        reward = generate_card_reward(state, 1)
        if reward:
            state.player.deck.append(reward[0])
        from .potions import random_potion
        if len(state.player.potions) < 3:
            state.player.potions.append(random_potion(state))


# ── Boss Relics ───────────────────────────────────────────────────────────────

class Brimstone(Relic):
    id = "Brimstone"
    name = "Brimstone"
    def register(self, state):
        from .enums import PowerId
        def on_turn_start(gs, **kw):
            gs.player.powers[PowerId.STRENGTH] = gs.player.powers.get(PowerId.STRENGTH, 0) + 2
            for e in gs.combat.enemies:
                if e.hp > 0:
                    e.powers[PowerId.STRENGTH] = e.powers.get(PowerId.STRENGTH, 0) + 1
        state.bus.subscribe(Event.TURN_START, on_turn_start)


class CallingBell(Relic):
    id = "Calling Bell"
    name = "Calling Bell"
    def on_pickup(self, state):
        # Obtain 3 random relics (common/uncommon/rare), add Curse: Injury
        from .nodes import _obtain_relic
        from .relics import random_relic
        for rarity in ("common", "uncommon", "rare"):
            _obtain_relic(state, random_relic(state, rarity))
        from .cards import make_card
        state.player.deck.append(make_card("Injury"))


class CoffeeDripper(Relic):
    id = "Coffee Dripper"
    name = "Coffee Dripper"
    def on_pickup(self, state):
        state.player.energy_per_turn += 1
        state.player._no_rest_heal = True


class CursedKey(Relic):
    id = "Cursed Key"
    name = "Cursed Key"
    def on_pickup(self, state):
        state.player.energy_per_turn += 1

    def register(self, state):
        def on_treasure(gs, source=None, **kw):
            # Real Cursed Key: curse only when opening CHESTS — not on boss
            # relics, shop relics, or its own pickup.
            if source == "chest":
                from .cards import make_card
                gs.player.deck.append(make_card("Regret"))
        state.bus.subscribe(Event.RELIC_OBTAINED, on_treasure)


class Ectoplasm(Relic):
    id = "Ectoplasm"
    name = "Ectoplasm"
    def on_pickup(self, state):
        state.player.energy_per_turn += 1
        state.player._no_gold = True


class FusionHammer(Relic):
    id = "Fusion Hammer"
    name = "Fusion Hammer"
    def on_pickup(self, state):
        state.player.energy_per_turn += 1
        state.player._no_smith = True


class HolyWater(Relic):
    id = "Holy Water"
    name = "Holy Water"
    def on_pickup(self, state):
        from .potions import random_potion
        for _ in range(3):
            if len(state.player.potions) < 3:
                state.player.potions.append(random_potion(state))


class Inserter(Relic):
    # Defect-only relic (orb slots); kept out of the Ironclad/Silent pools.
    # Approximated as transient energy — must NOT touch energy_per_turn, which
    # is a permanent stat and would ramp without bound across a run.
    id = "Inserter"
    name = "Inserter"
    def register(self, state):
        self._count = 0
        def on_turn_start(gs, **kw):
            self._count += 1
            if self._count >= 2:
                self._count = 0
                gs.player.energy += 1
        state.bus.subscribe(Event.TURN_START, on_turn_start)


class NuclearBattery(Relic):
    id = "Nuclear Battery"
    name = "Nuclear Battery"
    def on_pickup(self, state):
        state.player.energy_per_turn += 1
        state.player._nuclear_battery = True


class PandorasBox(Relic):
    id = "Pandora's Box"
    name = "Pandora's Box"
    def on_pickup(self, state):
        from .cards import make_card_for
        from .rewards import card_pool_for
        from .enums import CardRarity
        character = getattr(state, "character", "ironclad")
        char_pool = card_pool_for(state)
        deck = state.player.deck
        # BASIC Strikes/Defends only — the old substring match on the id also
        # transformed Twin/Perfected/Pommel/Wild/Sneaky Strike etc.
        strikes = [c for c in deck if c.id in ("Strike_R", "Strike_G")]
        defends = [c for c in deck if c.id in ("Defend_R", "Defend_G")]
        for c in strikes + defends:
            deck.remove(c)
        for _ in range(len(strikes)):
            pool = char_pool[CardRarity.RARE]
            name = pool[state.rng.misc_rng.next_int(len(pool))]
            deck.append(make_card_for(character, name))
        for _ in range(len(defends)):
            pool = char_pool[CardRarity.UNCOMMON]
            name = pool[state.rng.misc_rng.next_int(len(pool))]
            deck.append(make_card_for(character, name))


class PhilosophersStone(Relic):
    id = "Philosopher's Stone"
    name = "Philosopher's Stone"
    def on_pickup(self, state):
        state.player.energy_per_turn += 1

    def register(self, state):
        from .enums import PowerId
        def on_combat_start(gs, **kw):
            for e in gs.combat.enemies:
                e.powers[PowerId.STRENGTH] = e.powers.get(PowerId.STRENGTH, 0) + 1
        state.bus.subscribe(Event.COMBAT_START, on_combat_start)


class RunicPyramid(Relic):
    id = "Runic Pyramid"
    name = "Runic Pyramid"
    def register(self, state):
        state.player._runic_pyramid = True  # hand not discarded at end of turn


class VioletLotus(Relic):
    id = "Violet Lotus"
    name = "Violet Lotus"
    def register(self, state):
        def on_zero_cost(gs, card=None, **kw):
            if card and card.effective_cost() == 0:
                gs.player.energy += 1
        state.bus.subscribe(Event.CARD_PLAY, on_zero_cost)


# ── Register everything ───────────────────────────────────────────────────────

FULL_RELIC_LIST = [
    # Common
    BagOfMarbles, BloodVial, CentennialPuzzle, CeramicFish, DreamCatcher,
    HappyFlower, JuzuBracelet, Lantern, MawBank, MealTicket, Omamori,
    Orichalcum, PaperKrane, PaperPhrog, PreservedInsect, RegalPillow,
    SmilingMask, SneckoSkull, Strawberry, TinyChest,
    # Uncommon
    BlueCandle, BottledFlame, DarkstonePeriapt, EternalFeather, FrozenEgg,
    GamblingChip, Ginger, GoldenBell, GremlinHorn, HandDrill, IncensesBurner,
    LetterOpener, MercuryHourglass, MoltenEgg, MummifiedHand, OrangelPellets,
    Pantograph, Pear, StrikeDummy, TeardropLocket, ToxicEgg, WhiteBeastStatue,
    # Rare
    Astrolabe, BlackStar, BustedCrown, Calipers, CaptainsWheel, CloakClasp,
    CrystalBall, DuVuDoll, EmptyCage, FossilizedHelix, HoveringKite,
    LeesWaffle, MagicFlower, Mango, OldCoin, PeacePipe, Pocketwatch,
    PrayerWheel, RunicCube, SacredBark, SelfFormingClay, SlaverCollar,
    Sozu, TheAbacus, TheBoot, TinghSha, Torii, ToughBandages,
    ToyOrnithopter, TungstenRod, Turnip, UnceasingTop, VelvetChoker,
    # Shop (HandDrill already listed under Uncommon; it is in both pool sets so
    # one FULL_RELIC_LIST entry suffices for both — do not relist it here)
    Cauldron, ChemicalX, ClockworkSouvenir, DollysMirror, FrozenEye,
    MembershipCard, TinyHouse,
    # Boss (BustedCrown/EmptyCage/SacredBark/Sozu/VelvetChoker already listed
    # under Rare; pool membership is by class name, so one entry covers both)
    Brimstone, CallingBell, CoffeeDripper, CursedKey,
    Ectoplasm, FusionHammer, HolyWater, Inserter, NuclearBattery,
    PandorasBox, PhilosophersStone, RunicPyramid, VioletLotus,
]

BOSS_RELIC_POOL = [
    "Black Blood", "Mark of Pain", "Runic Dome", "Brimstone", "Busted Crown",
    "Calling Bell", "Coffee Dripper", "Cursed Key", "Ectoplasm", "Empty Cage",
    "Fusion Hammer", "Holy Water", "Pandora's Box",
    "Philosopher's Stone", "Runic Pyramid", "Sacred Bark", "Slaver's Collar",
    "Snecko Eye", "Sozu", "Velvet Choker",
]
# Nuclear Battery removed: Defect-only (orbs), same precedent as Inserter.


# ── Character gating ─────────────────────────────────────────────────────────
# Off-class relics must not reach Ironclad/Silent pools (mirrors card_pool_for).
# Keys are relic IDs.

_DEFECT_ONLY = {"Inserter", "Nuclear Battery", "Captain's Wheel"}
_WATCHER_ONLY = {"Teardrop Locket", "Cloak Clasp", "Violet Lotus", "Holy Water"}
_IRONCLAD_ONLY = {"Paper Phrog", "Brimstone", "Black Blood", "Mark of Pain",
                  "Magic Flower", "Self-Forming Clay"}
_SILENT_ONLY = {"Paper Krane", "Snecko Skull", "Tough Bandages", "Tingsha",
                "Hovering Kite", "Ring of the Snake"}


def relic_allowed(relic_id: str, character: str) -> bool:
    """Can this relic appear for this character? (Defect/Watcher relics never.)"""
    if relic_id in _DEFECT_ONLY or relic_id in _WATCHER_ONLY:
        return False
    if character == "silent" and relic_id in _IRONCLAD_ONLY:
        return False
    if character != "silent" and relic_id in _SILENT_ONLY:
        return False
    return True

_RARITY_POOLS = {
    "common": [r for r in FULL_RELIC_LIST if r.__name__ in {
        "BagOfMarbles", "BloodVial", "CentennialPuzzle", "CeramicFish",
        "DreamCatcher", "HappyFlower", "JuzuBracelet", "Lantern", "MawBank",
        "MealTicket", "Omamori", "Orichalcum", "PaperKrane", "PaperPhrog",
        "PreservedInsect", "RegalPillow", "SmilingMask", "SneckoSkull",
        "Strawberry", "TinyChest",
    }],
    "uncommon": [r for r in FULL_RELIC_LIST if r.__name__ in {
        "BlueCandle", "BottledFlame", "DarkstonePeriapt", "EternalFeather",
        "FrozenEgg", "GamblingChip", "Ginger", "GoldenBell", "GremlinHorn",
        "HandDrill", "IncensesBurner", "LetterOpener", "MercuryHourglass",
        "MoltenEgg", "MummifiedHand", "OrangelPellets", "Pantograph", "Pear",
        "StrikeDummy", "TeardropLocket", "ToxicEgg", "WhiteBeastStatue",
    }],
    # NOTE: boss relics (Sozu, Busted Crown, Velvet Choker, Sacred Bark,
    # Empty Cage) must NOT leak into treasure-chest rares — boss pool only.
    "rare": [r for r in FULL_RELIC_LIST if r.__name__ in {
        "Astrolabe", "BlackStar", "Calipers", "CaptainsWheel",
        "CloakClasp", "CrystalBall", "DuVuDoll", "FossilizedHelix",
        "HoveringKite", "LeesWaffle", "MagicFlower", "Mango", "OldCoin",
        "PeacePipe", "Pocketwatch", "PrayerWheel", "RunicCube",
        "SelfFormingClay", "SlaverCollar", "TheAbacus", "TheBoot",
        "TinghSha", "Torii", "ToughBandages", "ToyOrnithopter", "TungstenRod",
        "Turnip", "UnceasingTop",
    }],
    "shop": [r for r in FULL_RELIC_LIST if r.__name__ in {
        "Cauldron", "ChemicalX", "ClockworkSouvenir", "DollysMirror",
        "FrozenEye", "HandDrill", "MembershipCard", "TinyHouse",
    }],
    "boss": [r for r in FULL_RELIC_LIST if r.__name__ in {
        "Brimstone", "BustedCrown", "CallingBell", "CoffeeDripper",
        "CursedKey", "Ectoplasm", "EmptyCage", "FusionHammer", "HolyWater",
        "PandorasBox", "PhilosophersStone",
        "RunicPyramid", "SacredBark", "Sozu", "VelvetChoker", "VioletLotus",
    }],
}


def _update_relic_registry():
    for cls in FULL_RELIC_LIST:
        RELIC_REGISTRY[cls.id] = cls
    # Also add BOSS_RELIC_POOL to rewards module
    import slay_bench.rewards as rw
    rw.BOSS_RELIC_POOL = BOSS_RELIC_POOL


_update_relic_registry()
