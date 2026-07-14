"""High-level run loop: traverse map, resolve nodes, manage rewards."""
from __future__ import annotations
from typing import TYPE_CHECKING, Optional, Callable, List

from .enums import NodeType
from .map_gen import MapNode, GameMap, generate_map
from .rewards import generate_card_reward, gold_reward, potion_drop
from .events import Event

if TYPE_CHECKING:
    from .state import GameState
    from .cards import Card
    from .enemies import Enemy


# ── Encounter tables ──────────────────────────────────────────────────────────

ACT1_MONSTER_ENCOUNTERS = [
    ["Cultist"],
    ["JawWorm"],
    ["RedLouse", "GreenLouse"],
    ["RedLouse", "RedLouse"],
    ["GreenLouse", "GreenLouse"],
    ["AcidSlimeS", "SpikeSlimeS"],
    ["AcidSlimeM"],
    ["SpikeSlimeM"],
    ["FungalBeast"],
]

ACT1_ELITE_ENCOUNTERS = [
    ["GremlinNob"],
    ["Lagavulin"],
    ["Sentry", "Sentry", "Sentry"],
]

ACT1_BOSS_ENCOUNTERS = [
    ["SlimeBoss"],
    ["Hexaghost"],
]

# Act 2/3 encounter pools reclassified 2026-07-14 (bug_audit_2026-07-14 M1) to the
# real-game classification with our implemented roster. Previously elites sat in
# normal pools (BookOfStabbing, GiantHead) and Act-3 encounters (Transient,
# WrithingMass) sat in Act 2. Byrd is a ×3 group (was ×2). TorchHead has no solo
# real encounter → used as a documented stand-in pair. SpireShield/SpireSpear are
# real Act-4 Heart guards → removed from the tables (kept registered, reserved).
ACT2_MONSTER_ENCOUNTERS = [
    ["Chosen"],
    ["ShellParasite"],
    ["Byrd", "Byrd", "Byrd"],
    ["Chosen", "Byrd"],
    ["ShellParasite", "Byrd"],
    ["TorchHead", "TorchHead"],  # documented stand-in pair
]

ACT2_ELITE_ENCOUNTERS = [
    ["GremlinLeader"],
    ["RedSlaver", "BlueSlaver", "Taskmaster"],
    ["BookOfStabbing"],
]

ACT2_BOSS_ENCOUNTERS = [
    ["TheCollector"],
    ["BronzeAutomaton"],
    ["TheChamp"],
]

ACT3_MONSTER_ENCOUNTERS = [
    ["Darkling", "Darkling", "Darkling"],
    ["Maw"],
    ["WrithingMass"],
    ["Transient"],
]

ACT3_ELITE_ENCOUNTERS = [
    ["GiantHead"],
    ["Nemesis"],
    ["Reptomancer"],
]

ACT3_BOSS_ENCOUNTERS = [
    ["Donu", "Deca"],
    ["AwakenedOne"],
    ["TimeEater"],
]

_ENCOUNTER_TABLE = {
    1: {
        NodeType.MONSTER: ACT1_MONSTER_ENCOUNTERS,
        NodeType.ELITE:   ACT1_ELITE_ENCOUNTERS,
        NodeType.BOSS:    ACT1_BOSS_ENCOUNTERS,
    },
    2: {
        NodeType.MONSTER: ACT2_MONSTER_ENCOUNTERS,
        NodeType.ELITE:   ACT2_ELITE_ENCOUNTERS,
        NodeType.BOSS:    ACT2_BOSS_ENCOUNTERS,
    },
    3: {
        NodeType.MONSTER: ACT3_MONSTER_ENCOUNTERS,
        NodeType.ELITE:   ACT3_ELITE_ENCOUNTERS,
        NodeType.BOSS:    ACT3_BOSS_ENCOUNTERS,
    },
}


def roll_encounter(state: GameState, node_type: NodeType) -> List[str]:
    table = _ENCOUNTER_TABLE.get(state.act, {}).get(node_type, [["Cultist"]])
    idx = state.rng.misc_rng.next_int(len(table))
    return table[idx]


def spawn_enemies(state: GameState, enemy_ids: List[str],
                  elite: bool = False, boss: bool = False) -> List[Enemy]:
    from .enemies import ENEMY_REGISTRY
    from .enemies_act2 import register_act2_act3
    register_act2_act3(ENEMY_REGISTRY)
    enemies = []
    for eid in enemy_ids:
        cls = ENEMY_REGISTRY.get(eid)
        if cls is None:
            # A silent skip here masked C1 (the "DonuAndDeca" phantom id) for
            # months: an unknown id produced an empty enemy list → instant
            # auto-"win". Fail loud instead — an unresolved id is always a bug.
            raise ValueError(f"Unknown enemy id: {eid!r}")
        e = cls(state.rng.hp_rng)
        # Room-type tags consumed by Preserved Insect / Slaver's Collar
        e._elite = elite
        e._boss = boss
        enemies.append(e)
    return enemies


# ── Node resolution ───────────────────────────────────────────────────────────

class RunState:
    """Tracks run-level state between nodes."""

    def __init__(self, state: GameState, game_map: GameMap):
        self.state = state
        self.game_map = game_map
        self.current_floor = 0
        self.current_col = None  # set when player picks a path
        self.history: List[MapNode] = []

    @property
    def current_node(self) -> Optional[MapNode]:
        if self.current_col is None:
            return None
        return self.game_map.get_node(self.current_floor, self.current_col)

    def available_next_nodes(self) -> List[MapNode]:
        if self.current_col is None:
            return self.game_map.floors[0] if self.game_map.floors else []
        return self.game_map.reachable_from(self.current_floor, self.current_col)

    def move_to(self, node: MapNode) -> None:
        self.current_floor = node.floor
        self.current_col = node.col
        self.history.append(node)
        self.state.floor = node.floor
        self.state.player.floor = node.floor
        # Maw Bank: +12 gold per floor climbed (until any shop purchase)
        if getattr(self.state.player, '_maw_bank', False) \
                and not getattr(self.state.player, '_no_gold', False):
            self.state.player.gold += 12


def resolve_node(run: RunState, node: MapNode,
                 card_choice_fn: Optional[Callable] = None,
                 path_choice_fn: Optional[Callable] = None) -> dict:
    """
    Resolve a single map node. Returns a result dict.
    card_choice_fn(offers: List[Card]) -> Card | None
    path_choice_fn(nodes: List[MapNode]) -> MapNode
    """
    state = run.state
    result = {"node": node, "outcome": None}

    if node.node_type in (NodeType.MONSTER, NodeType.ELITE, NodeType.BOSS):
        result.update(_resolve_combat(run, node, card_choice_fn))

    elif node.node_type == NodeType.REST:
        result.update(_resolve_rest(run, card_choice_fn))

    elif node.node_type == NodeType.MERCHANT:
        from .nodes import greedy_shop_visit
        result.update(greedy_shop_visit(state))

    elif node.node_type == NodeType.TREASURE:
        from .nodes import resolve_treasure
        resolve_treasure(state)
        result["outcome"] = "treasure"

    elif node.node_type == NodeType.EVENT:
        result.update(_resolve_event(run))

    return result


def _resolve_combat(run: RunState, node: MapNode,
                    card_choice_fn: Optional[Callable]) -> dict:
    from .combat import start_combat, play_card, end_player_turn, is_combat_over, end_combat
    state = run.state

    enemy_type = {
        NodeType.MONSTER: "normal",
        NodeType.ELITE: "elite",
        NodeType.BOSS: "boss",
    }[node.node_type]

    enemy_ids = roll_encounter(state, node.node_type)
    enemies = spawn_enemies(state, enemy_ids,
                            elite=node.node_type == NodeType.ELITE,
                            boss=node.node_type == NodeType.BOSS)
    start_combat(state, enemies)

    # Default AI: greedy card play
    result = {"outcome": None, "turns": 0}
    for _ in range(100):
        result["turns"] += 1
        outcome = is_combat_over(state)
        if outcome:
            result["outcome"] = outcome
            break

        played = True
        while played:
            played = False
            for card in list(state.combat.hand):
                target = next((e for e in state.combat.enemies if e.hp > 0), None)
                if target and card.can_play(state):
                    play_card(state, card, target)
                    played = True
                    if is_combat_over(state):
                        result["outcome"] = is_combat_over(state)
                        break
                    break

        if result["outcome"]:
            break
        end_player_turn(state)

    # 100-turn draw: score it a LOSS, symmetric with the LLM path
    # (benchmark._llm_combat returns False on timeout → run over). Previously
    # this path left outcome=None and the run CONTINUED, biasing the greedy
    # anchor against the LLM in Acts 2/3 where 500-HP GiantHead / high-HP
    # stalls are realistic. No COMBAT_END is emitted (a draw is not a win —
    # Burning Blood must not heal); clear the stale combat so between-combat
    # code keying on `state.combat is None` doesn't see a dead combat object.
    # (bug_audit_2026-07-14 M2 — acceptance verified empirically 2026-07-14:
    # greedy baseline re-run for both characters, all anchor metrics
    # [floors/progress/survival] identical; Act-1 greedy never draws in 100
    # turns. Per-sample death-overkill final_hp shifted via the Hexaghost M3
    # companion fix, not this change — see the audit doc's impl notes.)
    if result["outcome"] is None:
        result["outcome"] = "loss"
        state.combat = None

    if result["outcome"] == "win":
        end_combat(state)
        # Rewards
        gold = gold_reward(state, enemy_type)
        state.player.gold += gold
        state.bus.emit(Event.GOLD_GAINED, state, amount=gold)
        result["gold"] = gold

        if node.node_type == NodeType.BOSS:
            state.bus.emit(Event.BOSS_DEFEATED, state)

        # Elite relic drop (Black Star: an additional one)
        if node.node_type == NodeType.ELITE:
            from .nodes import _obtain_relic
            from .relics import random_relic
            from .rewards import elite_relic_rarity
            n_relics = 2 if getattr(state.player, '_black_star', False) else 1
            for _ in range(n_relics):
                _obtain_relic(state, random_relic(state, elite_relic_rarity(state)))

        # Card reward
        n_offers = 3
        if getattr(state.player, '_prayer_wheel', False):
            n_offers += 1
        if getattr(state.player, '_busted_crown', False):
            n_offers = max(1, n_offers - 2)
        offers = generate_card_reward(state, n_offers)
        result["card_offers"] = offers

        if card_choice_fn:
            chosen = card_choice_fn(offers)
            if chosen:
                state.player.deck.append(chosen)
                state.bus.emit(Event.CARD_ADDED, state, card=chosen)
                result["card_chosen"] = chosen

        # Potion drop
        if not getattr(state.player, '_no_potions', False):
            if potion_drop(state, enemy_type) and len(state.player.potions) < 3:
                from .potions import random_potion
                p = random_potion(state)
                state.player.potions.append(p)
                result["potion"] = p

    return result


def _resolve_rest(run: RunState, card_choice_fn: Optional[Callable] = None) -> dict:
    from .nodes import resolve_rest, RestSiteAction
    from .enums import CardType
    state = run.state
    p = state.player
    no_heal = getattr(p, '_no_rest_heal', False)
    no_smith = getattr(p, '_no_smith', False)

    # Peace Pipe: removing a curse beats resting/smithing
    if getattr(p, '_peace_pipe', False) and \
            any(c.type == CardType.CURSE for c in p.deck):
        resolve_rest(state, RestSiteAction.TOKE)
        return {"outcome": "toke"}

    # Coffee Dripper makes REST useless → SMITH, unless Fusion Hammer forbids it
    if no_heal and not no_smith:
        # Curses/statuses can't be upgraded — picking one wasted the smith
        candidates = [c for c in p.deck if not c.upgraded
                      and c.type not in (CardType.CURSE, CardType.STATUS)]
        card = candidates[0] if candidates else None
        resolve_rest(state, RestSiteAction.SMITH, card)
        return {"outcome": "smith", "upgraded": card}

    resolve_rest(state, RestSiteAction.REST)
    result = {"outcome": "rest"}
    # Dream Catcher: a card reward when you rest
    offer = getattr(state, '_dream_catcher_offer', None)
    if offer and card_choice_fn:
        chosen = card_choice_fn(offer)
        if chosen:
            p.deck.append(chosen)
            state.bus.emit(Event.CARD_ADDED, state, card=chosen)
            result["card_chosen"] = chosen
    state._dream_catcher_offer = None
    return result


def _resolve_event(run: RunState) -> dict:
    from .events_pool import random_event, resolve_event
    state = run.state
    event = random_event(state)
    # Auto-pick first choice
    text = resolve_event(state, event, 0)
    return {"outcome": "event", "event": event.name, "result": text}


# ── Full act run ──────────────────────────────────────────────────────────────

def run_act(state: GameState, act: int,
            card_choice_fn: Optional[Callable] = None) -> dict:
    """Run a full act from start to boss. Returns summary."""
    game_map = generate_map(act, state.rng.map_rng)
    run = RunState(state, game_map)
    state.act = act

    summary = {"act": act, "floors": [], "survived": False}

    # Traverse all floors
    all_nodes = [n for floor in game_map.floors for n in floor]

    # Pick first node (leftmost). NOTE: no move_to here — the loop below pops
    # this same node and calls move_to; the pre-loop call double-counted the
    # first floor (and would have paid Maw Bank twice).
    current_nodes = game_map.floors[0] if game_map.floors else []
    current_node = current_nodes[0] if current_nodes else None

    visited: set = set()
    queue = [current_node] if current_node is not None else []

    while queue:
        node = queue.pop(0)
        if id(node) in visited:
            continue
        visited.add(id(node))
        run.move_to(node)

        result = resolve_node(run, node, card_choice_fn)
        summary["floors"].append(result)

        if result.get("outcome") == "loss" or state.player.hp <= 0:
            summary["survived"] = False
            return summary

        # Pick next node (greedy: first available); exclude the boss, which is
        # fought once in the dedicated block below
        next_nodes = [n for n in run.available_next_nodes()
                      if n is not game_map.boss_node]
        if next_nodes:
            queue.append(next_nodes[0])

    # Boss
    if game_map.boss_node:
        run.move_to(game_map.boss_node)
        result = resolve_node(run, game_map.boss_node, card_choice_fn)
        summary["floors"].append(result)
        if result.get("outcome") == "win":
            state.bus.emit(Event.ACT_END, state)
            summary["survived"] = True
        else:
            summary["survived"] = False

    return summary
