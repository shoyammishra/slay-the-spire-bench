"""Slay the Spire Python Simulator."""
from .state import GameState, Player, CombatState
from .rng import SeededRNG
from .events import EventBus
from .cards import starter_deck, make_card
from .enemies import make_enemy, ENEMY_REGISTRY
from .enemies_act2 import register_act2_act3
from .relics import make_relic, BurningBlood, random_relic
from .relics_full import _update_relic_registry
from .combat import start_combat, play_card, end_player_turn, is_combat_over, end_combat
from .map_gen import generate_map
from .run_loop import run_act, RunState


# Populate full enemy and relic registries at import time
register_act2_act3(ENEMY_REGISTRY)
_update_relic_registry()


def new_ironclad_game(seed: int, starting_hp: int = 80) -> GameState:
    """Create a fresh Ironclad run."""
    rng = SeededRNG(seed)
    bus = EventBus()
    player = Player(
        hp=starting_hp,
        max_hp=starting_hp,
        deck=starter_deck(),
        relics=[BurningBlood()],
    )
    state = GameState(player=player, rng=rng, bus=bus)
    return state
