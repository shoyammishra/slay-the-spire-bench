"""Versioned infrastructure for a controlled, same-state horizon experiment.

Unlike the legacy four-task ordering, this intervention holds the simulator state,
action vocabulary, prompt encoding, oracle, and utility fixed.  Only the number of
future decision transitions (H) changes.  No result is claimed until model calls are
run and the fixture/oracle audit in ``docs/research_audit/DECISIVE_EXPERIMENT.md`` is
complete.
"""
from __future__ import annotations

import copy
import hashlib
import json
import time
from dataclasses import asdict, dataclass, fields, is_dataclass
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .enums import CardType
from .prompt_builder import combat_state_raw, combat_state_structured, system_prompt


CONTROLLED_HORIZON_VERSION = "controlled-decision-horizon-v2"
CONTROLLED_ACTION_SCORING_VERSION = "controlled-action-scoring-v2.1"
DEFAULT_HORIZONS = (1, 2, 4, 8)


class OracleBudgetExceeded(RuntimeError):
    """Raised rather than silently treating a truncated search as exact."""


class OracleTimeBudgetExceeded(RuntimeError):
    """Raised rather than silently treating a wall-time-limited search as exact."""


@dataclass(frozen=True, order=True)
class ControlledAction:
    action: str
    card_index: int = -1
    target_index: int = -1


@dataclass
class HorizonOracleResult:
    version: str
    horizon: int
    nodes_expanded: int
    exact: bool
    best_value: float
    worst_value: float
    optimal_actions: List[ControlledAction]
    action_values: Dict[str, float]
    search_calls: int = 0
    cache_hits: int = 0


@dataclass
class HorizonModelScore:
    version: str
    fixture_id: str
    horizon: int
    chosen_action: ControlledAction
    legal: bool
    parse_ok: bool
    oracle_exact: bool
    chosen_value: Optional[float]
    optimal_value: float
    regret: Optional[float]
    normalized_quality: Optional[float]


@dataclass
class ControlledFixture:
    """Tamper-evident recipe for regenerating one frozen combat state.

    Engine states contain callbacks and class instances that are unsafe to treat as
    a long-lived JSON serialization contract.  A fixture therefore persists the
    deterministic construction recipe plus a digest of the complete regenerated
    state.  Loading fails closed if engine changes alter that state.
    """

    version: str
    fixture_id: str
    character: str
    seed: int
    enemy_ids: List[str]
    deck_names: List[str]
    player_hp: int
    prefix_actions: List[ControlledAction]
    state_digest: str

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "ControlledFixture":
        """Restore a fixture from its public JSON representation."""
        values = dict(payload)
        values["prefix_actions"] = [
            action if isinstance(action, ControlledAction)
            else ControlledAction(**action)
            for action in values.get("prefix_actions", [])
        ]
        return cls(**values)


def _canonical_value(value: Any, seen: Optional[set[int]] = None) -> Any:
    """Convert engine state to stable JSON data for fixture integrity hashing."""
    if seen is None:
        seen = set()
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Enum):
        return {"enum": f"{value.__class__.__module__}.{value.__class__.__qualname__}",
                "value": value.value}
    if callable(value):
        fn = getattr(value, "__func__", value)
        return {"callable": f"{getattr(fn, '__module__', '')}."
                            f"{getattr(fn, '__qualname__', repr(fn))}"}
    if isinstance(value, dict):
        pairs = [(_canonical_value(k, seen), _canonical_value(v, seen))
                 for k, v in value.items()]
        return {"mapping": sorted(pairs, key=lambda pair: json.dumps(
            pair[0], sort_keys=True, separators=(",", ":")))}
    if isinstance(value, (list, tuple)):
        return [_canonical_value(item, seen) for item in value]
    if isinstance(value, set):
        items = [_canonical_value(item, seen) for item in value]
        return {"set": sorted(items, key=lambda item: json.dumps(
            item, sort_keys=True, separators=(",", ":")))}

    object_id = id(value)
    if object_id in seen:
        return {"cycle": f"{value.__class__.__module__}.{value.__class__.__qualname__}"}
    seen.add(object_id)
    try:
        if is_dataclass(value):
            attrs = {field.name: getattr(value, field.name) for field in fields(value)}
            # Runtime attributes on enemies/cards are decision-relevant too.
            attrs.update({k: v for k, v in vars(value).items() if k not in attrs})
        elif hasattr(value, "__dict__"):
            attrs = dict(vars(value))
        else:
            return repr(value)
        # EventBus listeners are reconstructed by the recipe. Bound callbacks
        # otherwise create cycles and encode process-specific object identities.
        attrs.pop("bus", None)
        attrs.pop("_listeners", None)
        return {
            "class": f"{value.__class__.__module__}.{value.__class__.__qualname__}",
            "attrs": {key: _canonical_value(attrs[key], seen)
                      for key in sorted(attrs)},
        }
    finally:
        seen.remove(object_id)


def state_digest(state) -> str:
    """SHA-256 of all decision-relevant state, including hidden piles and RNG."""
    payload = json.dumps(_canonical_value(state), sort_keys=True,
                         separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def create_fixture(character: str, seed: int, enemy_ids: Iterable[str],
                   prefix_actions: Iterable[ControlledAction] = (),
                   fixture_id: Optional[str] = None,
                   deck_names: Optional[Iterable[str]] = None,
                   player_hp: Optional[int] = None) -> Tuple[ControlledFixture, Any]:
    """Build a fixture recipe and its frozen state without model involvement."""
    from . import new_game, start_combat
    from .cards import make_card_for
    from .combat import is_combat_over
    from .enemies import make_enemy

    enemy_ids = list(enemy_ids)
    state = new_game(seed, character)
    if deck_names is not None:
        state.player.deck = [make_card_for(character, name) for name in deck_names]
    deck_names = [card.id for card in state.player.deck]
    if player_hp is not None:
        if not 1 <= player_hp <= state.player.max_hp:
            raise ValueError("fixture player_hp must be within [1, max_hp]")
        state.player.hp = player_hp
    initial_player_hp = state.player.hp
    enemies = [make_enemy(enemy_id, state.rng.hp_rng) for enemy_id in enemy_ids]
    start_combat(state, enemies)
    actions = [
        action if isinstance(action, ControlledAction)
        else ControlledAction(**action)
        for action in prefix_actions
    ]
    for action in actions:
        if is_combat_over(state):
            raise ValueError("fixture prefix reaches a terminal combat early")
        state = transition(state, action)
    if is_combat_over(state):
        raise ValueError("fixture state is terminal")
    if fixture_id is None:
        encounter = "-".join(enemy_ids).lower()
        fixture_id = f"{character}-{seed}-{encounter}-{len(actions)}"
    fixture = ControlledFixture(
        version=CONTROLLED_HORIZON_VERSION,
        fixture_id=fixture_id,
        character=character,
        seed=seed,
        enemy_ids=enemy_ids,
        deck_names=deck_names,
        player_hp=initial_player_hp,
        prefix_actions=actions,
        state_digest=state_digest(state),
    )
    return fixture, state


def load_fixture(fixture: ControlledFixture):
    """Regenerate a fixture and reject version or state drift."""
    if fixture.version != CONTROLLED_HORIZON_VERSION:
        raise ValueError(f"unsupported fixture version {fixture.version!r}")
    rebuilt, state = create_fixture(
        fixture.character, fixture.seed, fixture.enemy_ids,
        fixture.prefix_actions, fixture.fixture_id,
        fixture.deck_names, fixture.player_hp)
    if rebuilt.state_digest != fixture.state_digest:
        raise ValueError(
            f"fixture {fixture.fixture_id} state drift: "
            f"expected {fixture.state_digest}, got {rebuilt.state_digest}")
    return state


def _action_key(action: ControlledAction) -> str:
    return f"{action.action}:{action.card_index}:{action.target_index}"


def canonicalize_action_for_values(
        action: ControlledAction,
        action_values: Dict[str, float]) -> Tuple[ControlledAction, Optional[str]]:
    """Map a response action onto the frozen semantic action vocabulary.

    Combat execution ignores ``target_index`` for skills and powers.  The exact
    oracle represents those non-targeted plays with ``-1``, while the combat prompt
    historically illustrated every play with target ``0`` and did not document the
    sentinel.  Accept that irrelevant field only when the frozen action vocabulary
    proves that the selected card is non-targeted.  Targeted attacks retain exact
    target checking, including in multi-enemy states.
    """
    if _action_key(action) in action_values:
        return action, None
    if action.action == "play":
        non_targeted = ControlledAction("play", action.card_index, -1)
        if _action_key(non_targeted) in action_values:
            return non_targeted, "ignored_target_for_non_targeted_card"
    return action, None


def legal_actions(state) -> List[ControlledAction]:
    """Enumerate the next-action vocabulary used at every H."""
    if state.combat is None:
        return []
    actions = [ControlledAction("end_turn")]
    living = [i for i, enemy in enumerate(state.combat.enemies) if enemy.hp > 0]
    for card_index, card in enumerate(state.combat.hand):
        if not card.can_play(state):
            continue
        if card.type == CardType.ATTACK:
            actions.extend(ControlledAction("play", card_index, target_index)
                           for target_index in living)
        else:
            actions.append(ControlledAction("play", card_index, -1))
    return sorted(set(actions))


def transition(state, action: ControlledAction):
    """Apply one decision transition on a deep copy; the input is untouched."""
    from .combat import end_player_turn, is_combat_over, play_card

    nxt = copy.deepcopy(state)
    if is_combat_over(nxt):
        return nxt
    if action.action == "end_turn":
        end_player_turn(nxt)
        return nxt
    if action.action != "play":
        raise ValueError(f"unknown action {action.action!r}")
    actions = legal_actions(nxt)
    if action not in actions:
        raise ValueError(f"illegal action {action}")
    card = nxt.combat.hand[action.card_index]
    target = (None if action.target_index < 0
              else nxt.combat.enemies[action.target_index])
    play_card(nxt, card, target)
    return nxt


def terminal_utility(state, initial_player_hp: int, initial_enemy_hp: int) -> float:
    """Fixed utility at every H: damage dealt minus HP lost, with terminal bonuses."""
    from .combat import is_combat_over

    enemy_hp = sum(max(0, enemy.hp) for enemy in state.combat.enemies)
    value = (initial_enemy_hp - enemy_hp) - (initial_player_hp - max(0, state.player.hp))
    outcome = is_combat_over(state)
    if outcome == "win":
        value += 1000.0
    elif outcome == "loss":
        value -= 1000.0
    return float(value)


def exact_action_values(state, horizon: int,
                        node_budget: int = 2_000_000,
                        memoize: bool = True,
                        wall_time_budget_s: Optional[float] = None) -> HorizonOracleResult:
    """Exhaustively value every first action for exactly ``horizon`` transitions.

    Search truncation is never reported as an oracle: exceeding ``node_budget``
    raises ``OracleBudgetExceeded`` and invalidates that fixture/H cell.
    """
    from .combat import is_combat_over

    if horizon < 1:
        raise ValueError("horizon must be >= 1")
    if wall_time_budget_s is not None and wall_time_budget_s <= 0:
        raise ValueError("wall_time_budget_s must be positive")
    initial_player_hp = state.player.hp
    initial_enemy_hp = sum(max(0, enemy.hp) for enemy in state.combat.enemies)
    nodes = 0
    calls = 0
    cache_hits = 0
    cache: Dict[Tuple[int, str], float] = {}
    started = time.perf_counter()

    def value(node, depth: int) -> float:
        nonlocal nodes, calls, cache_hits
        calls += 1
        # Checking every 128 visits keeps the limit tight without making the
        # timer call a material part of the oracle's inner-loop cost.
        if (wall_time_budget_s is not None and calls % 128 == 1
                and time.perf_counter() - started > wall_time_budget_s):
            raise OracleTimeBudgetExceeded(
                f"controlled-horizon oracle exceeded {wall_time_budget_s:g}s "
                f"at H={horizon}")
        key = (depth, state_digest(node)) if memoize else None
        if key is not None and key in cache:
            cache_hits += 1
            return cache[key]
        nodes += 1
        if nodes > node_budget:
            raise OracleBudgetExceeded(
                f"controlled-horizon oracle exceeded {node_budget} nodes at H={horizon}")
        if depth == 0 or is_combat_over(node):
            result = terminal_utility(node, initial_player_hp, initial_enemy_hp)
        else:
            result = max(value(transition(node, action), depth - 1)
                         for action in legal_actions(node))
        if key is not None:
            cache[key] = result
        return result

    action_values = {
        _action_key(action): value(transition(state, action), horizon - 1)
        for action in legal_actions(state)
    }
    if not action_values:
        raise ValueError("fixture has no legal actions")
    best = max(action_values.values())
    worst = min(action_values.values())
    optimal = [action for action in legal_actions(state)
               if action_values[_action_key(action)] == best]
    return HorizonOracleResult(
        version=CONTROLLED_HORIZON_VERSION,
        horizon=horizon,
        nodes_expanded=nodes,
        exact=True,
        best_value=best,
        worst_value=worst,
        optimal_actions=optimal,
        action_values=action_values,
        search_calls=calls,
        cache_hits=cache_hits,
    )


def _continuation_card(card) -> dict:
    return {
        "id": card.id,
        "name": card.name,
        "cost": card.cost,
        "cost_override": card.cost_override,
        "upgraded": card.upgraded,
        "exhaust": card.exhaust,
        "ethereal": card.ethereal,
        "retain": card.retain,
    }


def oracle_visible_continuation_state(state) -> dict:
    """Expose deterministic continuation data that the exact oracle can use.

    The ordinary combat prompt intentionally hides draw order without Frozen Eye.
    That is unsuitable for a causal lookahead test: otherwise two identical prompts
    can receive different oracle labels. Controlled-H therefore adds this fixed
    full-observability appendix at every H.
    """
    combat = state.combat
    primitive = (bool, int, float, str, type(None))
    return {
        "draw_pile_next_first": [
            _continuation_card(card) for card in reversed(combat.draw_pile)],
        "discard_pile_stored_order": [
            _continuation_card(card) for card in combat.discard_pile],
        "exhaust_pile_stored_order": [
            _continuation_card(card) for card in combat.exhaust_pile],
        "combat_counters": {
            "turn": combat.turn,
            "cards_played_this_turn": combat.cards_played_this_turn,
            "cards_played_this_combat": combat.cards_played_this_combat,
            "attacks_played_this_turn": combat.attacks_played_this_turn,
            "discarded_this_turn": combat.discarded_this_turn,
            "time_warp_lock": combat.time_warp_lock,
        },
        "enemy_runtime": [
            {
                "id": enemy.id,
                "move_index": enemy.move_index,
                "move_history": list(enemy.move_history),
                "private_flags": {
                    key: value for key, value in sorted(vars(enemy).items())
                    if key.startswith("_") and isinstance(value, primitive)
                },
            }
            for enemy in combat.enemies
        ],
        "player_runtime_flags": {
            key: value for key, value in sorted(vars(state.player).items())
            if key.startswith("_") and isinstance(value, primitive)
        },
        "rng_stream_states": {
            name: stream.seed for name, stream in sorted(vars(state.rng).items())
        },
        "rng_algorithm": "java.util.Random-compatible 48-bit LCG",
    }


def build_prompt(state, horizon: int, prompt_format: str = "structured") -> Tuple[str, str]:
    if horizon < 1:
        raise ValueError("horizon must be >= 1")
    if prompt_format == "structured":
        context = combat_state_structured(state)
    elif prompt_format == "raw":
        context = combat_state_raw(state)
    else:
        raise ValueError("prompt_format must be structured or raw")
    continuation = json.dumps(
        oracle_visible_continuation_state(state), indent=2, sort_keys=True)
    system = system_prompt("combat", getattr(state, "character", "ironclad"))
    user = (
        context + "\n\n"
        "=== CONTROLLED-H FULL-OBSERVABILITY APPENDIX ===\n"
        "The exact oracle and the model receive the same deterministic continuation "
        "state. Draw-pile order is next-card first.\n"
        + continuation + "\n\n"
        f"Choose the next action that maximizes the stated utility after exactly {horizon} "
        "decision transitions. Utility is enemy HP lost minus player HP lost, plus "
        "1000 for a win and minus 1000 for a loss.\n"
        "Output JSON: {\"action\": \"play\"|\"end_turn\", \"card_index\": <int>, "
        "\"target_index\": <int>, \"reasoning\": \"<brief>\"}"
    )
    return system, user


def score_response(state, fixture_id: str, horizon: int, response: dict,
                   node_budget: int = 2_000_000) -> HorizonModelScore:
    oracle = exact_action_values(state, horizon, node_budget=node_budget)
    parse_ok = "error" not in response
    try:
        chosen = ControlledAction(
            str(response.get("action", "end_turn")),
            int(response.get("card_index", -1)),
            int(response.get("target_index", -1)),
        )
    except (TypeError, ValueError):
        chosen = ControlledAction("invalid")
    chosen, _normalization = canonicalize_action_for_values(
        chosen, oracle.action_values)
    key = _action_key(chosen)
    chosen_value = oracle.action_values.get(key)
    legal = chosen_value is not None
    regret = None if chosen_value is None else oracle.best_value - chosen_value
    span = oracle.best_value - oracle.worst_value
    quality = None
    if chosen_value is not None:
        quality = 1.0 if span == 0 else (chosen_value - oracle.worst_value) / span
    return HorizonModelScore(
        version=CONTROLLED_HORIZON_VERSION,
        fixture_id=fixture_id,
        horizon=horizon,
        chosen_action=chosen,
        legal=legal,
        parse_ok=parse_ok,
        oracle_exact=oracle.exact,
        chosen_value=chosen_value,
        optimal_value=oracle.best_value,
        regret=regret,
        normalized_quality=quality,
    )


def evaluate_fixture(llm, state, fixture_id: str,
                     horizons: Iterable[int] = DEFAULT_HORIZONS,
                     prompt_format: str = "structured", temperature: float = 0.0,
                     node_budget: int = 2_000_000) -> List[dict]:
    """Run one fixed state across H values; caller owns inference authorization."""
    rows = []
    for horizon in horizons:
        system, user = build_prompt(state, horizon, prompt_format)
        response = llm.complete_json(system, user, temperature=temperature)
        rows.append(asdict(score_response(
            state, fixture_id, horizon, response, node_budget=node_budget)))
    return rows
