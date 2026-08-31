"""Versioned infrastructure for a controlled, same-state horizon experiment.

Unlike the legacy four-task ordering, this intervention holds the simulator state,
action vocabulary, prompt encoding, oracle, and utility fixed.  Only the number of
future decision transitions (H) changes.  No result is claimed until model calls are
run and the fixture/oracle audit in ``docs/research_audit/DECISIVE_EXPERIMENT.md`` is
complete.
"""
from __future__ import annotations

import copy
from dataclasses import asdict, dataclass
from typing import Dict, Iterable, List, Optional, Tuple

from .enums import CardType
from .prompt_builder import combat_state_raw, combat_state_structured, system_prompt


CONTROLLED_HORIZON_VERSION = "controlled-decision-horizon-v1"
DEFAULT_HORIZONS = (1, 2, 4, 8)


class OracleBudgetExceeded(RuntimeError):
    """Raised rather than silently treating a truncated search as exact."""


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


def _action_key(action: ControlledAction) -> str:
    return f"{action.action}:{action.card_index}:{action.target_index}"


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
                        node_budget: int = 2_000_000) -> HorizonOracleResult:
    """Exhaustively value every first action for exactly ``horizon`` transitions.

    Search truncation is never reported as an oracle: exceeding ``node_budget``
    raises ``OracleBudgetExceeded`` and invalidates that fixture/H cell.
    """
    from .combat import is_combat_over

    if horizon < 1:
        raise ValueError("horizon must be >= 1")
    initial_player_hp = state.player.hp
    initial_enemy_hp = sum(max(0, enemy.hp) for enemy in state.combat.enemies)
    nodes = 0

    def value(node, depth: int) -> float:
        nonlocal nodes
        nodes += 1
        if nodes > node_budget:
            raise OracleBudgetExceeded(
                f"controlled-horizon oracle exceeded {node_budget} nodes at H={horizon}")
        if depth == 0 or is_combat_over(node):
            return terminal_utility(node, initial_player_hp, initial_enemy_hp)
        return max(value(transition(node, action), depth - 1)
                   for action in legal_actions(node))

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
    )


def build_prompt(state, horizon: int, prompt_format: str = "structured") -> Tuple[str, str]:
    if horizon < 1:
        raise ValueError("horizon must be >= 1")
    if prompt_format == "structured":
        context = combat_state_structured(state)
    elif prompt_format == "raw":
        context = combat_state_raw(state)
    else:
        raise ValueError("prompt_format must be structured or raw")
    system = system_prompt("combat", getattr(state, "character", "ironclad"))
    user = (
        context + "\n\n"
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
