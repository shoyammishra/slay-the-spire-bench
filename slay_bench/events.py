"""Event bus for relic/power hooks."""
from __future__ import annotations
from enum import Enum, auto
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from .state import GameState


class Event(Enum):
    COMBAT_START = auto()
    TURN_START = auto()
    TURN_END = auto()
    CARD_PLAY = auto()
    CARD_DRAW = auto()
    CARD_EXHAUST = auto()
    CARD_DISCARD = auto()
    DAMAGE_TAKEN = auto()
    DAMAGE_DEALT = auto()
    BLOCK_GAINED = auto()
    BLOCK_LOST = auto()
    HEAL = auto()
    ENEMY_DEATH = auto()
    COMBAT_END = auto()
    REST_SITE_ENTER = auto()
    CARD_ADDED = auto()
    CARD_REMOVED = auto()
    CARD_UPGRADED = auto()
    RELIC_OBTAINED = auto()
    POTION_USED = auto()
    GOLD_GAINED = auto()
    GOLD_LOST = auto()
    DEATH_WOULD_OCCUR = auto()
    BOSS_DEFEATED = auto()
    ACT_END = auto()
    ATTACK_PLAY = auto()
    SKILL_PLAY = auto()
    STATUS_DRAW = auto()
    SHUFFLE = auto()      # discard pile reshuffled into draw pile


class EventBus:
    def __init__(self) -> None:
        self._listeners: dict[Event, list[Callable]] = {e: [] for e in Event}

    def clear(self) -> None:
        """Drop all listeners. Called at combat start so per-combat relic/power
        hooks are re-registered fresh instead of stacking across the run."""
        for e in self._listeners:
            self._listeners[e].clear()

    def subscribe(self, event: Event, callback: Callable) -> None:
        self._listeners[event].append(callback)

    def unsubscribe(self, event: Event, callback: Callable) -> None:
        if callback in self._listeners[event]:
            self._listeners[event].remove(callback)

    def emit(self, event: Event, state: GameState, **kwargs: Any) -> Any:
        results = []
        for cb in list(self._listeners[event]):
            result = cb(state, **kwargs)
            if result is not None:
                results.append(result)
        return results
