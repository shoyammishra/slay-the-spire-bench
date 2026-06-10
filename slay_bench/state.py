"""Core game state dataclasses."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional, List

if TYPE_CHECKING:
    from .cards import Card
    from .enemies import Enemy
    from .relics import Relic
    from .events import EventBus
    from .rng import SeededRNG


@dataclass
class CombatState:
    enemies: List[Enemy] = field(default_factory=list)
    draw_pile: List[Card] = field(default_factory=list)
    hand: List[Card] = field(default_factory=list)
    discard_pile: List[Card] = field(default_factory=list)
    exhaust_pile: List[Card] = field(default_factory=list)
    turn: int = 0
    cards_played_this_turn: int = 0
    cards_played_this_combat: int = 0
    attacks_played_this_turn: int = 0   # Finisher
    discarded_this_turn: int = 0        # Sneaky Strike / Eviscerate
    # Debuff timing (StS "justApplied" rule): player debuffs applied by enemies
    # during the enemy phase must not tick down at the end of that same round.
    enemy_phase: bool = False
    just_applied: set = field(default_factory=set)


@dataclass
class Player:
    hp: int
    max_hp: int
    block: int = 0
    energy: int = 3
    energy_per_turn: int = 3
    gold: int = 99
    floor: int = 0
    act: int = 1
    powers: dict = field(default_factory=dict)
    relics: list = field(default_factory=list)
    potions: list = field(default_factory=list)
    deck: List[Card] = field(default_factory=list)  # master deck outside combat
    # runtime flags set by some powers/cards
    barricade: bool = False        # block doesn't reset
    berserk: bool = False          # gain 1 energy each turn player is Vulnerable
    brutality: bool = False        # lose 1 HP draw 1 card each turn
    innate_brutality: bool = False
    corruption: bool = False       # skills cost 0, exhaust
    cards_played_this_combat: int = 0


@dataclass
class GameState:
    player: Player
    rng: SeededRNG
    bus: EventBus
    combat: Optional[CombatState] = None
    # non-combat state
    floor: int = 0
    act: int = 1
    character: str = "ironclad"
    act_boss_relic_choices: list = field(default_factory=list)
