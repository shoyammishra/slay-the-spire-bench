"""Power/debuff hooks wired into the EventBus at combat start."""
from __future__ import annotations
from typing import TYPE_CHECKING

from .enums import PowerId
from .events import Event

if TYPE_CHECKING:
    from .state import GameState
    from .cards import Card
    from .enemies import Enemy


def register_power_hooks(state: GameState) -> None:
    """Subscribe all active player powers to the event bus for this combat."""
    p = state.player
    bus = state.bus

    # ── Turn Start hooks ──────────────────────────────────────────────────────

    def on_turn_start(gs: GameState, **kw):
        from .cards import _gain_block, _damage_player, _draw_cards
        player = gs.player

        # Demon Form: gain Strength
        if PowerId.DEMON_FORM in player.powers:
            player.powers[PowerId.STRENGTH] = player.powers.get(PowerId.STRENGTH, 0) + player.powers[PowerId.DEMON_FORM]

        # Metallicize: gain block
        if PowerId.METALLICIZE in player.powers:
            _gain_block(gs, player.powers[PowerId.METALLICIZE])

        # Brutality: lose 1 hp, draw 1 card
        if player.brutality:
            _damage_player(gs, 1, is_hp_loss=True)
            _draw_cards(gs, 1)

        # Berserk: if Vulnerable, gain 1 energy
        if player.berserk and PowerId.VULNERABLE in player.powers:
            player.energy += 1

        # Energized: gain 1 extra energy
        if PowerId.ENERGIZED in player.powers:
            player.energy += player.powers.pop(PowerId.ENERGIZED)

        # Noxious Fumes: poison all enemies
        if PowerId.NOXIOUS_FUMES in player.powers:
            from .cards import _apply_power
            for e in gs.combat.enemies:
                if e.hp > 0:
                    _apply_power(gs, e, PowerId.POISON,
                                 player.powers[PowerId.NOXIOUS_FUMES])

        # Infinite Blades: add a Shiv to hand
        if PowerId.INFINITE_BLADES in player.powers:
            from .cards import _add_card_to_hand
            from .cards_silent import Shiv
            for _ in range(player.powers[PowerId.INFINITE_BLADES]):
                _add_card_to_hand(gs, Shiv())

        # Tools of the Trade: draw 1, discard 1
        if PowerId.TOOLS_OF_THE_TRADE in player.powers:
            from .cards import _draw_cards, _discard_from_hand, _auto_discard_choice
            n = player.powers[PowerId.TOOLS_OF_THE_TRADE]
            _draw_cards(gs, n)
            for _ in range(n):
                pick = _auto_discard_choice(gs)
                if pick:
                    _discard_from_hand(gs, pick)

    bus.subscribe(Event.TURN_START, on_turn_start)

    # ── Turn End hooks ────────────────────────────────────────────────────────

    def on_turn_end(gs: GameState, **kw):
        from .cards import _damage_player, _apply_power
        player = gs.player

        # Combust: lose HP, deal damage to all enemies
        if PowerId.COMBUST in player.powers:
            _damage_player(gs, 1, is_hp_loss=True)
            for e in gs.combat.enemies:
                if e.hp > 0:
                    from .cards import _apply_damage_to_enemy
                    _apply_damage_to_enemy(gs, e, player.powers[PowerId.COMBUST])

        # Flex: lose temporary Strength
        if PowerId.FLEX in player.powers:
            flex_amount = player.powers.pop(PowerId.FLEX)
            player.powers[PowerId.STRENGTH] = player.powers.get(PowerId.STRENGTH, 0) - flex_amount
            if player.powers[PowerId.STRENGTH] == 0:
                del player.powers[PowerId.STRENGTH]

        # Constricted: lose HP
        if PowerId.CONSTRICTED in player.powers:
            _damage_player(gs, player.powers[PowerId.CONSTRICTED], is_hp_loss=True)

        # Poison: lose HP, reduce by 1
        if PowerId.POISON in player.powers:
            amt = player.powers[PowerId.POISON]
            _damage_player(gs, amt, is_hp_loss=True)
            player.powers[PowerId.POISON] = amt - 1
            if player.powers[PowerId.POISON] <= 0:
                del player.powers[PowerId.POISON]

        # Shackled: lose Strength (will be restored at next turn start in real game;
        #           simplified here: just note the shackle amount)
        # (Full Shackled implementation would require turn-start restoration)

        # Wraith Form: lose 1 Dexterity each turn it is active
        if PowerId.WRAITH_FORM in player.powers:
            player.powers[PowerId.DEXTERITY] = player.powers.get(PowerId.DEXTERITY, 0) - 1
            if player.powers[PowerId.DEXTERITY] == 0:
                del player.powers[PowerId.DEXTERITY]

        # Well-Laid Plans: retain up to N cards (least valuable kept simple: first N)
        if PowerId.WELL_LAID_PLANS in player.powers:
            for card in gs.combat.hand[:player.powers[PowerId.WELL_LAID_PLANS]]:
                card._temp_retain = True

        # Burn / curse cards in hand deal their end-of-turn effects
        for card in list(gs.combat.hand):
            if hasattr(card, 'end_of_turn_effect'):
                card.end_of_turn_effect(gs)

    bus.subscribe(Event.TURN_END, on_turn_end)

    # ── Card Play hooks ───────────────────────────────────────────────────────

    def on_card_play(gs: GameState, card: Card = None, **kw):
        from .enums import CardType
        player = gs.player

        # Rage: gain block on attack
        if PowerId.RAGE in player.powers and card and card.type == CardType.ATTACK:
            from .cards import _gain_block
            _gain_block(gs, player.powers[PowerId.RAGE])

        # A Thousand Cuts: damage all enemies on any card play
        if PowerId.THOUSAND_CUTS in player.powers:
            from .cards import _apply_damage_to_enemy
            for e in gs.combat.enemies:
                if e.hp > 0:
                    _apply_damage_to_enemy(gs, e, player.powers[PowerId.THOUSAND_CUTS])

        # After Image: gain block on any card play
        if PowerId.AFTER_IMAGE in player.powers:
            from .cards import _gain_block
            _gain_block(gs, player.powers[PowerId.AFTER_IMAGE])

        # Choke: choked enemies lose HP per card played
        for e in gs.combat.enemies:
            if e.hp > 0 and PowerId.CHOKED in e.powers:
                e.hp -= e.powers[PowerId.CHOKED]

        # Pain curse: while in HAND, lose 1 HP on any other card play (StS rule;
        # copies in the draw/discard piles do nothing)
        for c in gs.combat.hand:
            if c.__class__.__name__ == 'Pain':
                from .cards import _damage_player
                _damage_player(gs, 1, is_hp_loss=True)
                break

        # Hex: add Dazed on non-attack play
        if PowerId.HEX in player.powers and card and card.type != CardType.ATTACK:
            from .cards import Dazed
            gs.combat.discard_pile.append(Dazed())

        # Juggernaut handled via BLOCK_GAINED event
        # Double Tap handled in combat engine (card play duplication)

        # GremlinNob "enrage": gain strength on skill play (enemy)
        for e in gs.combat.enemies:
            if e.hp > 0 and "enrage" in e.powers and card and card.type == CardType.SKILL:
                e.powers[PowerId.STRENGTH] = e.powers.get(PowerId.STRENGTH, 0) + e.powers["enrage"]

    bus.subscribe(Event.CARD_PLAY, on_card_play)

    # ── Exhaust hooks ─────────────────────────────────────────────────────────

    def on_exhaust(gs: GameState, card: Card = None, **kw):
        player = gs.player

        # Dark Embrace: draw a card
        if PowerId.DARK_EMBRACE in player.powers:
            from .cards import _draw_cards
            _draw_cards(gs, player.powers[PowerId.DARK_EMBRACE])

        # Feel No Pain: gain block
        if PowerId.FEEL_NO_PAIN in player.powers:
            from .cards import _gain_block
            _gain_block(gs, player.powers[PowerId.FEEL_NO_PAIN])

        # Dead Branch relic handled in relics

    bus.subscribe(Event.CARD_EXHAUST, on_exhaust)

    # ── Draw hooks ────────────────────────────────────────────────────────────

    def on_draw(gs: GameState, card: Card = None, **kw):
        from .enums import CardType
        player = gs.player

        # Fire Breathing: deal damage on status draw
        if PowerId.FIRE_BREATHING in player.powers and card and card.type == CardType.STATUS:
            from .cards import _apply_damage_to_enemy
            for e in gs.combat.enemies:
                if e.hp > 0:
                    _apply_damage_to_enemy(gs, e, player.powers[PowerId.FIRE_BREATHING])

        # Evolve: draw on status draw
        if PowerId.EVOLVE in player.powers and card and card.type == CardType.STATUS:
            from .cards import _draw_cards
            _draw_cards(gs, player.powers[PowerId.EVOLVE])

        # Void card: lose 1 energy on draw
        if card and card.__class__.__name__ == 'VoidCard':
            player.energy = max(0, player.energy - 1)

    bus.subscribe(Event.CARD_DRAW, on_draw)

    # ── Block Gained hooks ────────────────────────────────────────────────────

    def on_block_gained(gs: GameState, amount: int = 0, **kw):
        player = gs.player

        # Juggernaut: deal damage to random enemy
        if PowerId.JUGGERNAUT in player.powers and amount > 0:
            alive = [e for e in gs.combat.enemies if e.hp > 0]
            if alive:
                idx = gs.rng.misc_rng.next_int(len(alive))
                from .cards import _apply_damage_to_enemy
                _apply_damage_to_enemy(gs, alive[idx], player.powers[PowerId.JUGGERNAUT])

    bus.subscribe(Event.BLOCK_GAINED, on_block_gained)

    # ── Enemy Death hooks ─────────────────────────────────────────────────────

    def on_enemy_death(gs: GameState, target: Enemy = None, **kw):
        if target and hasattr(target, 'on_death'):
            target.on_death(gs)

        # Corpse Explosion: on death, deal the enemy's max HP to all others
        if target and PowerId.CORPSE_EXPLOSION in target.powers:
            from .cards import _apply_damage_to_enemy
            for e in gs.combat.enemies:
                if e is not target and e.hp > 0:
                    _apply_damage_to_enemy(gs, e, target.max_hp)

    bus.subscribe(Event.ENEMY_DEATH, on_enemy_death)

    # ── Enemy powers: Ritual ──────────────────────────────────────────────────
    # Handled in combat engine turn-end enemy processing
