"""Combat engine: turn loop, card playing, enemy execution."""
from __future__ import annotations
from typing import TYPE_CHECKING, Optional, List

from .enums import PowerId, CardType
from .events import Event

if TYPE_CHECKING:
    from .state import GameState, CombatState
    from .cards import Card
    from .enemies import Enemy


def start_combat(state: GameState, enemies: List[Enemy]) -> None:
    """Initialize a combat encounter."""
    from .state import CombatState
    from .cards import _draw_cards
    from .powers import register_power_hooks

    # Fresh combat state. Also drop any listeners left over from prior combats:
    # relic/power hooks are re-registered below, and without clearing they would
    # stack across a run (e.g. Burning Blood healing 6, then 12, then 18 ...).
    state.bus.clear()
    # Powers are per-combat in StS: without this reset, power cards played in an
    # earlier fight (Demon Form, Inflame, Metallicize, ...) would carry over and
    # snowball across a run. Relic-granted powers re-apply via COMBAT_START hooks.
    state.player.powers = {}
    state.combat = CombatState(enemies=enemies)

    # Shuffle master deck into draw pile
    draw = [c.copy() for c in state.player.deck]
    state.rng.shuffle_rng.shuffle(draw)
    state.combat.draw_pile = draw

    # Apply innate cards
    innate = [c for c in state.combat.draw_pile if c.innate]
    for c in innate:
        state.combat.draw_pile.remove(c)
        state.combat.hand.append(c)

    # Corruption: skills cost 0
    if state.player.corruption:
        for c in state.combat.draw_pile + state.combat.hand:
            if c.type == CardType.SKILL:
                c.cost_override = 0

    # Register power event hooks (fresh for each combat)
    register_power_hooks(state)

    # Register relic hooks
    for relic in state.player.relics:
        relic.register(state)

    # Emit combat start
    state.bus.emit(Event.COMBAT_START, state)

    # Select enemy intents for turn 1
    for enemy in enemies:
        enemy.select_move(state)

    # Begin turn 1
    _begin_player_turn(state)


def _begin_player_turn(state: GameState) -> None:
    from .cards import _draw_cards, _gain_block, _add_card_to_hand
    player = state.player
    combat = state.combat
    combat.turn += 1
    combat.cards_played_this_turn = 0
    combat.attacks_played_this_turn = 0
    combat.discarded_this_turn = 0

    # Reset block (unless Barricade / Blur / Calipers)
    if not player.barricade:
        if PowerId.BLUR in player.powers:
            player.powers[PowerId.BLUR] -= 1
            if player.powers[PowerId.BLUR] <= 0:
                del player.powers[PowerId.BLUR]
        elif getattr(player, '_calipers', False):
            player.block = min(player.block, 15)
        else:
            player.block = 0

    # Queued next-turn effects (Dodge and Roll, Predator, Doppelganger)
    if PowerId.NEXT_TURN_BLOCK in player.powers:
        _gain_block(state, player.powers.pop(PowerId.NEXT_TURN_BLOCK))
    # Phantasmal Killer: double damage becomes active the turn after play
    if PowerId.PHANTASMAL in player.powers:
        stacks = player.powers.pop(PowerId.PHANTASMAL)
        player.powers[PowerId.DOUBLE_DAMAGE] = player.powers.get(PowerId.DOUBLE_DAMAGE, 0) + stacks
    # Nightmare: add the queued copies
    queued = getattr(combat, '_nightmare_card', None)
    if queued is not None:
        for _ in range(3):
            _add_card_to_hand(state, queued.copy())
        combat._nightmare_card = None
    # Clear single-turn retain marks from Well-Laid Plans
    for c in combat.hand:
        if getattr(c, '_temp_retain', False):
            c._temp_retain = False

    # Reset Entangled
    if PowerId.ENTANGLED in player.powers:
        del player.powers[PowerId.ENTANGLED]

    # Reset energy (Ice Cream: carry over)
    if getattr(player, '_ice_cream', False):
        player.energy += player.energy_per_turn
    else:
        player.energy = player.energy_per_turn

    # Enemy block resets each turn
    for e in combat.enemies:
        e.block = 0

    # Emit turn start (powers hook here: Demon Form, Metallicize, Brutality, etc.)
    state.bus.emit(Event.TURN_START, state)

    # Draw cards (default 5, No Draw prevents)
    if PowerId.NO_DRAW not in player.powers:
        _draw_cards(state, 5)
        # Queued extra draws (Predator, Doppelganger)
        if PowerId.NEXT_TURN_DRAW in player.powers:
            _draw_cards(state, player.powers.pop(PowerId.NEXT_TURN_DRAW))
    else:
        del player.powers[PowerId.NO_DRAW]
        player.powers.pop(PowerId.NEXT_TURN_DRAW, None)

    # Confused: randomize card costs
    if PowerId.CONFUSED in player.powers:
        for c in combat.hand:
            if c.cost >= 0:
                c.cost_override = state.rng.misc_rng.next_int(4)  # 0-3


def play_card(state: GameState, card: Card, target: Optional[Enemy] = None) -> None:
    """Play a card from hand. Validates legality, pays cost, triggers hooks."""
    combat = state.combat
    player = state.player

    if card not in combat.hand:
        raise ValueError(f"Card {card} not in hand")
    if not card.can_play(state):
        raise ValueError(f"Cannot play {card}: insufficient energy or restriction")

    # Pay energy (X costs spend all energy)
    if card.cost == -2:
        pass  # handled inside card.play()
    else:
        cost = card.effective_cost()
        if player.corruption and card.type == CardType.SKILL:
            cost = 0
        player.energy -= cost
        player.energy = max(0, player.energy)

    # Remove from hand before play (some cards add to hand)
    combat.hand.remove(card)

    # Emit play event
    state.bus.emit(Event.CARD_PLAY, state, card=card)
    if card.type == CardType.ATTACK:
        state.bus.emit(Event.ATTACK_PLAY, state, card=card)
    elif card.type == CardType.SKILL:
        state.bus.emit(Event.SKILL_PLAY, state, card=card)

    # Track play counts
    combat.cards_played_this_turn += 1
    combat.cards_played_this_combat += 1
    player.cards_played_this_combat += 1
    if card.type == CardType.ATTACK:
        combat.attacks_played_this_turn += 1

    # Double Tap: each stack doubles one attack (1 stack consumed per attack)
    double_tap_count = 0
    if PowerId.DOUBLE_TAP in player.powers and card.type == CardType.ATTACK:
        double_tap_count = 1
        player.powers[PowerId.DOUBLE_TAP] -= 1
        if player.powers[PowerId.DOUBLE_TAP] <= 0:
            del player.powers[PowerId.DOUBLE_TAP]

    # Burst: next skill(s) played twice (decrements one stack per skill)
    burst_replay = 0
    if PowerId.BURST in player.powers and card.type == CardType.SKILL:
        burst_replay = 1
        player.powers[PowerId.BURST] -= 1
        if player.powers[PowerId.BURST] <= 0:
            del player.powers[PowerId.BURST]

    # Execute card effect
    card.play(state, target)

    # Double Tap / Burst replay
    for _ in range(double_tap_count + burst_replay):
        card.play(state, target)

    # Exhaust logic
    should_exhaust = card.exhaust
    if player.corruption and card.type == CardType.SKILL:
        should_exhaust = True
    if should_exhaust:
        from .cards import _exhaust_card
        if card not in combat.hand:  # may have been removed by effect
            combat.exhaust_pile.append(card)
            state.bus.emit(Event.CARD_EXHAUST, state, card=card)
    elif card not in combat.hand:  # wasn't re-added during play
        combat.discard_pile.append(card)
        state.bus.emit(Event.CARD_DISCARD, state, card=card)

    # Check enemy deaths
    _check_enemy_deaths(state)


def end_player_turn(state: GameState) -> None:
    """End player turn, discard hand, execute enemy moves, begin next player turn."""
    from .cards import _draw_cards
    combat = state.combat
    player = state.player

    # Emit turn end (Combust, Flex, Constricted, Burn cards, etc.)
    state.bus.emit(Event.TURN_END, state)

    # Discard hand (ethereal cards exhaust instead; Runic Pyramid keeps the hand)
    runic_pyramid = getattr(player, '_runic_pyramid', False)
    for card in list(combat.hand):
        if card.ethereal:
            from .cards import _exhaust_card
            combat.hand.remove(card)
            combat.exhaust_pile.append(card)
            state.bus.emit(Event.CARD_EXHAUST, state, card=card)
        elif runic_pyramid or getattr(card, 'retain', False) \
                or getattr(card, '_temp_retain', False):
            pass  # stay in hand
        else:
            combat.hand.remove(card)
            combat.discard_pile.append(card)

    # Bullet Time: restore costs zeroed for this turn only
    for card in combat.hand + combat.discard_pile + combat.draw_pile:
        if getattr(card, '_bullet_time', False):
            card._bullet_time = False
            card.cost_override = None

    # Enemy turns. Player debuffs (Vulnerable, Intangible, ...) must still be
    # active here — they tick at the end of the ROUND, below. Debuffs the
    # enemies apply during this phase are flagged just_applied so they don't
    # tick the same round (StS rule).
    combat.enemy_phase = True
    try:
        for enemy in combat.enemies:
            if enemy.hp > 0:
                _execute_enemy_turn(state, enemy)
                _check_enemy_deaths(state)
            if player.hp <= 0:
                return  # player died
    finally:
        combat.enemy_phase = False

    # Enemy powers tick (Ritual, Regenerate, Poison)
    for enemy in combat.enemies:
        if enemy.hp > 0:
            _tick_enemy_powers(state, enemy)
    _check_enemy_deaths(state)  # poison can kill

    # End of round: reduce player debuff durations (after enemies acted, so
    # Wraith Form / Incense Burner Intangible and enemy-applied Vulnerable
    # actually cover the enemy attacks of this round)
    _tick_player_debuffs(state)

    # Select next enemy moves
    for enemy in combat.enemies:
        if enemy.hp > 0:
            enemy.select_move(state)

    # Begin next player turn
    _begin_player_turn(state)


def _tick_player_debuffs(state: GameState) -> None:
    """Reduce turn-based stacks at end of round. Debuffs that enemies applied
    during this round's enemy phase (just_applied) skip their first tick."""
    player = state.player
    combat = state.combat
    tick_down = {PowerId.WEAK, PowerId.VULNERABLE, PowerId.FRAIL,
                 PowerId.INTANGIBLE, PowerId.DOUBLE_DAMAGE}
    for power in tick_down:
        if power in player.powers and power not in combat.just_applied:
            player.powers[power] -= 1
            if player.powers[power] <= 0:
                del player.powers[power]
    combat.just_applied.clear()


def _execute_enemy_turn(state: GameState, enemy: Enemy) -> None:
    """Execute the enemy's chosen move."""
    if not enemy.current_move:
        return
    enemy.execute_move(state)
    # Flame Barrier already handled inside _damage_player via _apply_damage_to_enemy

    # Tick enemy debuffs
    tick_down = {PowerId.WEAK, PowerId.VULNERABLE}
    for power in tick_down:
        if power in enemy.powers:
            enemy.powers[power] -= 1
            if enemy.powers[power] <= 0:
                del enemy.powers[power]

    # Thorns on player attack is handled in _apply_damage_to_enemy
    # Strength from Ritual handled in _tick_enemy_powers


def _tick_enemy_powers(state: GameState, enemy: Enemy) -> None:
    """End-of-round enemy power ticks."""
    # Ritual: gain Strength
    if PowerId.RITUAL in enemy.powers:
        enemy.powers[PowerId.STRENGTH] = enemy.powers.get(PowerId.STRENGTH, 0) + enemy.powers[PowerId.RITUAL]

    # Regenerate
    if PowerId.REGENERATE in enemy.powers:
        enemy.hp = min(enemy.max_hp, enemy.hp + enemy.powers[PowerId.REGENERATE])

    # Malleable: increases each time blocked — reset stacking here if needed
    # Poison on enemies: direct HP loss, ignores block (StS rule)
    if PowerId.POISON in enemy.powers:
        from .events import Event
        amt = enemy.powers[PowerId.POISON]
        if PowerId.INTANGIBLE in enemy.powers:
            amt = 1
        enemy.hp -= amt
        state.bus.emit(Event.DAMAGE_DEALT, state, target=enemy, amount=amt)
        enemy.powers[PowerId.POISON] -= 1
        if enemy.powers[PowerId.POISON] <= 0:
            del enemy.powers[PowerId.POISON]


def _check_enemy_deaths(state: GameState) -> None:
    """Mark dead enemies and emit death events."""
    for enemy in state.combat.enemies:
        if enemy.hp <= 0 and enemy.alive:
            enemy.alive = False
            enemy.hp = 0
            state.bus.emit(Event.ENEMY_DEATH, state, target=enemy)


def is_combat_over(state: GameState) -> str | None:
    """Returns 'win', 'loss', or None if ongoing."""
    if state.player.hp <= 0:
        return "loss"
    if all(e.hp <= 0 for e in state.combat.enemies):
        return "win"
    return None


def end_combat(state: GameState) -> None:
    """Finalize combat: emit COMBAT_END, clear combat state."""
    from .enums import PowerId
    state.bus.emit(Event.COMBAT_END, state)

    # Remove combat-only powers
    combat_only = {
        PowerId.FLEX, PowerId.VIGOR, PowerId.DOUBLE_TAP,
        PowerId.ENERGIZED, PowerId.RAGE, PowerId.ENTANGLED,
        PowerId.FLAME_BARRIER,
    }
    for p in combat_only:
        state.player.powers.pop(p, None)

    # Reset flags
    state.player.block = 0
    state.player.barricade = False
    state.player.berserk = False
    state.player.corruption = False

    # Clear combat state
    state.combat = None
