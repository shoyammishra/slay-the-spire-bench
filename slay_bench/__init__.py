"""Slay the Spire Python Simulator."""
from typing import Optional

from .state import GameState, Player, CombatState
from .rng import SeededRNG
from .events import EventBus
from .cards import starter_deck, make_card, make_card_for
from .enemies import make_enemy, ENEMY_REGISTRY
from .enemies_act2 import register_act2_act3
from .relics import make_relic, BurningBlood, RingOfTheSnake, random_relic
from .relics_full import _update_relic_registry
from .combat import start_combat, play_card, end_player_turn, is_combat_over, end_combat
from .map_gen import generate_map
from .run_loop import run_act, RunState


# Populate full enemy and relic registries at import time
register_act2_act3(ENEMY_REGISTRY)
_update_relic_registry()

CHARACTERS = ("ironclad", "silent")


def new_game(seed: int, character: str = "ironclad",
             starting_hp: Optional[int] = None) -> GameState:
    """Create a fresh run for any supported character."""
    if character not in CHARACTERS:
        raise ValueError(f"Unknown character: {character} (choose from {CHARACTERS})")
    rng = SeededRNG(seed)
    bus = EventBus()
    if character == "silent":
        from .cards_silent import silent_starter_deck
        hp = starting_hp if starting_hp is not None else 70
        player = Player(hp=hp, max_hp=hp, deck=silent_starter_deck(),
                        relics=[RingOfTheSnake()])
    else:
        hp = starting_hp if starting_hp is not None else 80
        player = Player(hp=hp, max_hp=hp, deck=starter_deck(),
                        relics=[BurningBlood()])
    state = GameState(player=player, rng=rng, bus=bus, character=character)
    for relic in player.relics:
        relic.on_pickup(state)
    return state


def new_ironclad_game(seed: int, starting_hp: int = 80) -> GameState:
    """Create a fresh Ironclad run (kept for backwards compatibility)."""
    return new_game(seed, "ironclad", starting_hp)
