"""Map generation matching Slay the Spire's layout rules."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Set, Tuple, TYPE_CHECKING

from .enums import NodeType

if TYPE_CHECKING:
    from .rng import StsRandom


# Act structure: (floors_of_content, boss_floor)
ACT_STRUCTURE = {
    1: (15, 16),   # floors 1-15 content, floor 16 boss
    2: (15, 31),
    3: (15, 47),   # was (14, 54): Act 3 has 15 content floors like the others;
                   # cumulative boss floor after 16+15 = 47 (bug_audit M9)
}

# Node distribution weights per act (approximate StS weights)
_NODE_WEIGHTS = [
    # (NodeType, weight)
    (NodeType.MONSTER,  45),
    (NodeType.ELITE,    12),
    (NodeType.EVENT,    22),
    (NodeType.REST,     12),
    (NodeType.MERCHANT,  5),
    (NodeType.TREASURE,  4),
]


@dataclass
class MapNode:
    floor: int
    col: int
    node_type: NodeType
    edges: List[int] = field(default_factory=list)   # cols on next floor reachable from here
    parents: List[int] = field(default_factory=list) # cols on prev floor that reach here

    def __repr__(self) -> str:
        symbol = {
            NodeType.MONSTER:  "M",
            NodeType.ELITE:    "E",
            NodeType.EVENT:    "?",
            NodeType.REST:     "R",
            NodeType.MERCHANT: "$",
            NodeType.TREASURE: "T",
            NodeType.BOSS:     "B",
        }[self.node_type]
        return f"{symbol}({self.floor},{self.col})"


@dataclass
class GameMap:
    """Full map for one act."""
    act: int
    floors: List[List[MapNode]] = field(default_factory=list)  # floors[floor_idx][col]
    boss_node: Optional[MapNode] = None

    def get_node(self, floor: int, col: int) -> Optional[MapNode]:
        if 0 <= floor < len(self.floors):
            for node in self.floors[floor]:
                if node.col == col:
                    return node
        return None

    def reachable_from(self, floor: int, col: int) -> List[MapNode]:
        node = self.get_node(floor, col)
        if not node:
            return []
        if floor + 1 < len(self.floors):
            return [n for n in self.floors[floor + 1] if n.col in node.edges]
        elif self.boss_node:
            return [self.boss_node]
        return []

    def ascii(self) -> str:
        lines = []
        for floor_nodes in reversed(self.floors):
            row = ["." ] * 7
            for node in floor_nodes:
                symbol = {
                    NodeType.MONSTER:  "M",
                    NodeType.ELITE:    "E",
                    NodeType.EVENT:    "?",
                    NodeType.REST:     "R",
                    NodeType.MERCHANT: "$",
                    NodeType.TREASURE: "T",
                    NodeType.BOSS:     "B",
                }[node.node_type]
                if 0 <= node.col < 7:
                    row[node.col] = symbol
            lines.append(" ".join(row))
        if self.boss_node:
            lines.insert(0, "    B    (Boss)")
        return "\n".join(lines)


def _roll_node_type(rng: StsRandom, floor: int, act: int,
                    prev_type: Optional[NodeType] = None) -> NodeType:
    """Roll a node type, respecting adjacency rules."""
    weights = list(_NODE_WEIGHTS)

    # No consecutive Rests
    if prev_type == NodeType.REST:
        weights = [(t, w) for t, w in weights if t != NodeType.REST]
    # No Elite before floor 5 (floor index < 4)
    if floor < 4:
        weights = [(t, w) for t, w in weights if t != NodeType.ELITE]
    # No consecutive Elites
    if prev_type == NodeType.ELITE:
        weights = [(t, w) for t, w in weights if t != NodeType.ELITE]

    total = sum(w for _, w in weights)
    roll = rng.next_int(total)
    cumulative = 0
    for node_type, w in weights:
        cumulative += w
        if roll < cumulative:
            return node_type
    return NodeType.MONSTER


def generate_map(act: int, rng: StsRandom) -> GameMap:
    """Generate a full act map."""
    num_floors, _ = ACT_STRUCTURE[act]
    num_cols = 7
    game_map = GameMap(act=act)

    # Decide the active columns for every floor up front. This is critical:
    # edges must point at the columns that actually exist on the next floor.
    # (Previously each floor's columns were re-rolled when wiring vs. when
    # building, so edges referenced non-existent nodes and paths dead-ended.)
    active_per_floor: List[List[int]] = [
        _choose_active_cols(rng, floor, num_floors) for floor in range(num_floors)
    ]

    # Generate nodes floor by floor, wiring edges to the real next-floor columns.
    for floor in range(num_floors):
        floor_nodes: List[MapNode] = []

        for col in active_per_floor[floor]:
            # Find what prev node connects here to determine adjacency constraint
            prev_type = None
            if floor > 0:
                for prev_node in game_map.floors[floor - 1]:
                    if col in prev_node.edges:
                        prev_type = prev_node.node_type
                        break

            node_type = _roll_node_type(rng, floor, act, prev_type)
            floor_nodes.append(MapNode(floor=floor, col=col, node_type=node_type))

        game_map.floors.append(floor_nodes)

        # Wire edges from the floor we just built to the real next-floor columns.
        if floor < num_floors - 1:
            _wire_edges(rng, floor_nodes, active_per_floor[floor + 1])

    # Guarantee every node has a path upward (no orphan columns / dead ends).
    _ensure_connectivity(game_map)

    # Boss node
    game_map.boss_node = MapNode(floor=num_floors, col=3, node_type=NodeType.BOSS)

    # Ensure at least 1 Merchant and 1 Treasure per act
    _ensure_node_type(game_map, NodeType.MERCHANT, rng, min_floor=2)
    _ensure_node_type(game_map, NodeType.TREASURE, rng, min_floor=1)

    return game_map


def _choose_active_cols(rng: StsRandom, floor: int, num_floors: int) -> List[int]:
    """Choose which columns are active on this floor (3-6 nodes per floor)."""
    # More nodes in middle floors, fewer near start/end
    count = 3 + rng.next_int(4)  # 3-6
    cols = sorted(rng.next_int(7) for _ in range(count * 2))
    # Deduplicate
    seen: Set[int] = set()
    result = []
    for c in cols:
        if c not in seen:
            seen.add(c)
            result.append(c)
        if len(result) >= count:
            break
    return sorted(result) if result else [3]


def _wire_edges(rng: StsRandom, current_floor: List[MapNode],
                next_cols: List[int]) -> None:
    """Connect current floor nodes to next floor columns."""
    if not next_cols:
        return
    for node in current_floor:
        # Each node connects to 1-2 of the nearest columns on the next floor.
        candidates = sorted(next_cols, key=lambda c: abs(c - node.col))
        num_edges = 1 + (1 if rng.next_int(3) == 0 else 0)
        node.edges = sorted(candidates[:num_edges])


def _ensure_connectivity(game_map: GameMap) -> None:
    """Guarantee every node reaches the next floor and every next-floor node
    has a parent, so the greedy traversal never dead-ends below the boss."""
    floors = game_map.floors
    for fi in range(len(floors) - 1):
        cur = floors[fi]
        nxt_cols = [n.col for n in floors[fi + 1]]
        if not nxt_cols:
            continue
        # Every current node must have at least one edge to a real next node.
        for node in cur:
            valid = [c for c in node.edges if c in nxt_cols]
            if not valid:
                nearest = min(nxt_cols, key=lambda c: abs(c - node.col))
                valid = [nearest]
            node.edges = sorted(valid)
        # Every next-floor node must have at least one parent.
        reached = {c for node in cur for c in node.edges}
        for child_col in nxt_cols:
            if child_col not in reached:
                parent = min(cur, key=lambda n: abs(n.col - child_col))
                parent.edges = sorted(set(parent.edges) | {child_col})
    # Recompute parents for completeness.
    for fi in range(1, len(floors)):
        prev = floors[fi - 1]
        for node in floors[fi]:
            node.parents = sorted(p.col for p in prev if node.col in p.edges)


def _ensure_node_type(game_map: GameMap, node_type: NodeType,
                      rng: StsRandom, min_floor: int = 0) -> None:
    """Replace a random Monster node with the given type if none exists."""
    has_type = any(
        n.node_type == node_type
        for floor in game_map.floors
        for n in floor
    )
    if not has_type:
        candidates = [
            (fi, ni)
            for fi, floor in enumerate(game_map.floors)
            for ni, n in enumerate(floor)
            if n.node_type == NodeType.MONSTER and fi >= min_floor
        ]
        if candidates:
            fi, ni = candidates[rng.next_int(len(candidates))]
            game_map.floors[fi][ni].node_type = node_type
