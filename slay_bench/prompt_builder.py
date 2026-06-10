"""State serialization: converts GameState / CombatState to LLM prompt strings."""
from __future__ import annotations
import json
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from .state import GameState
    from .cards import Card
    from .enemies import Enemy


# ── Helpers ───────────────────────────────────────────────────────────────────

def _card_summary(card) -> dict:
    return {
        "name": card.name,
        "cost": card.cost if card.cost_override is None else card.cost_override,
        "type": card.type.name,
        "upgraded": card.upgraded,
        "exhaust": card.exhaust,
    }


def _enemy_summary(e) -> dict:
    intent = None
    if e.current_move:
        intent = {
            "name": e.current_move.name,
            "intent": e.current_move.intent.name,
        }
        if e.current_move.damage:
            intent["damage"] = e.current_move.damage
            intent["hits"] = e.current_move.hits
        if e.current_move.block:
            intent["block"] = e.current_move.block
    return {
        "name": e.name,
        "hp": e.hp,
        "max_hp": e.max_hp,
        "block": e.block,
        "powers": {k.value if hasattr(k, 'value') else str(k): v
                   for k, v in (e.powers or {}).items()},
        "intent": intent,
    }


def _player_summary(p) -> dict:
    return {
        "hp": p.hp,
        "max_hp": p.max_hp,
        "block": p.block,
        "energy": p.energy,
        "gold": p.gold,
        "floor": p.floor,
        "powers": {k.value if hasattr(k, 'value') else str(k): v
                   for k, v in (p.powers or {}).items() if v},
        "relics": [r.name for r in (p.relics or [])],
    }


# ── Structured prompt (compact JSON) ─────────────────────────────────────────

def _card_summary_with_playable(card, state: GameState) -> dict:
    d = _card_summary(card)
    d["playable"] = card.can_play(state)
    return d


def combat_state_structured(state: GameState) -> str:
    """Return a compact JSON string describing the full combat state."""
    c = state.combat
    p = state.player
    data = {
        "player": _player_summary(p),
        "enemies": [_enemy_summary(e) for e in c.enemies if e.hp > 0],
        "hand": [_card_summary_with_playable(card, state) for card in c.hand],
        "draw_pile_size": len(c.draw_pile),
        "discard_pile_size": len(c.discard_pile),
        "exhaust_pile": [card.name for card in c.exhaust_pile],
        "turn": c.turn,
        "energy": p.energy,
    }
    return json.dumps(data, indent=2)


def deck_relic_structured(state: GameState) -> str:
    """Return a compact JSON string describing deck + relics (for synergy eval)."""
    from collections import Counter
    deck_counts = Counter(c.name for c in state.player.deck)
    data = {
        "deck": dict(deck_counts),
        "relics": [r.name for r in state.player.relics],
        "floor": state.player.floor,
        "hp": state.player.hp,
        "max_hp": state.player.max_hp,
        "gold": state.player.gold,
    }
    return json.dumps(data, indent=2)


def card_reward_structured(offers: List, deck: List, relics: List) -> str:
    """Serialize card reward choice context."""
    from collections import Counter
    data = {
        "offers": [_card_summary(c) for c in offers],
        "current_deck": dict(Counter(c.name for c in deck)),
        "relics": [r.name for r in relics],
    }
    return json.dumps(data, indent=2)


# ── Raw context prompt (verbose text) ─────────────────────────────────────────

def combat_state_raw(state: GameState) -> str:
    """Return a verbose natural-language description of combat state."""
    c = state.combat
    p = state.player

    lines = [
        f"=== COMBAT — Turn {c.turn} ===",
        f"Player: {p.hp}/{p.max_hp} HP  Block: {p.block}  Energy: {p.energy}/{p.energy_per_turn}",
    ]
    if p.powers:
        active = [f"{k.value if hasattr(k,'value') else k}({v})"
                  for k, v in p.powers.items() if v]
        if active:
            lines.append(f"Player powers: {', '.join(active)}")

    lines.append("")
    lines.append("Enemies:")
    for e in c.enemies:
        if e.hp <= 0:
            continue
        intent_str = ""
        if e.current_move:
            m = e.current_move
            if m.damage:
                intent_str = f" → intends {m.name} ({m.damage}×{m.hits} dmg)"
            elif m.block:
                intent_str = f" → intends {m.name} (block {m.block})"
            else:
                intent_str = f" → intends {m.name}"
        ep = ""
        if e.powers:
            ep = "  powers: " + ", ".join(
                f"{k.value if hasattr(k,'value') else k}({v})"
                for k, v in e.powers.items() if v)
        lines.append(f"  {e.name}: {e.hp}/{e.max_hp} HP  block={e.block}{intent_str}{ep}")

    lines.append("")
    lines.append(f"Hand ({len(c.hand)} cards):")
    for i, card in enumerate(c.hand):
        cost = card.cost if card.cost_override is None else card.cost_override
        playable = "✓" if card.can_play(state) else "✗"
        lines.append(f"  [{i}] {card.name}  cost={cost}  type={card.type.name}  {playable}")

    lines.append(f"Draw pile: {len(c.draw_pile)} cards")
    lines.append(f"Discard: {len(c.discard_pile)} cards")
    if c.exhaust_pile:
        lines.append(f"Exhausted: {', '.join(cd.name for cd in c.exhaust_pile)}")

    lines.append("")
    lines.append(f"Relics: {', '.join(r.name for r in p.relics)}")
    return "\n".join(lines)


def deck_relic_raw(state: GameState) -> str:
    """Verbose text describing deck + relics for synergy evaluation."""
    from collections import Counter
    deck_counts = Counter(c.name for c in state.player.deck)
    lines = [
        f"=== DECK & RELICS (Floor {state.player.floor}) ===",
        f"HP: {state.player.hp}/{state.player.max_hp}  Gold: {state.player.gold}",
        "",
        "Deck:",
    ]
    for name, count in sorted(deck_counts.items()):
        lines.append(f"  {count}x {name}")
    lines.append("")
    lines.append("Relics:")
    for r in state.player.relics:
        lines.append(f"  {r.name}")
    return "\n".join(lines)


def card_reward_raw(offers: List, deck: List, relics: List) -> str:
    """Verbose text for card reward choice."""
    from collections import Counter
    lines = ["=== CARD REWARD ===", "Choose one card (or skip):"]
    for i, c in enumerate(offers):
        cost = c.cost if c.cost_override is None else c.cost_override
        lines.append(f"  [{i}] {c.name}  cost={cost}  type={c.type.name}"
                     + ("  (upgraded)" if c.upgraded else ""))
    lines.append("")
    deck_counts = Counter(c.name for c in deck)
    lines.append(f"Your deck ({len(deck)} cards): " +
                 ", ".join(f"{v}x{k}" for k, v in sorted(deck_counts.items())))
    lines.append(f"Relics: {', '.join(r.name for r in relics)}")
    return "\n".join(lines)


# ── System prompt templates ───────────────────────────────────────────────────

_SYSTEM_TEMPLATES = {
    "turn": """You are an expert Slay the Spire player controlling the {character}.
Your task: given the current combat state, output the optimal sequence of card plays for this turn.

Rules:
- You can only play cards you have enough energy for (energy resets each turn).
- Playing a card with "exhaust" removes it from the game (not discard).
- Cards with type ATTACK deal damage; SKILL provides utility; POWER applies a permanent effect.
- End your turn when no more beneficial plays remain.

Output format (JSON array of card indices in play order, then "end_turn"):
{{"plays": [0, 2, 1], "reasoning": "brief explanation"}}
""",
    "combat": """You are an expert Slay the Spire player controlling the {character}.
Each turn you will receive the combat state and must decide which card to play next (or end your turn).

Output format (JSON):
{{"action": "play", "card_index": 0, "target_index": 0, "reasoning": "..."}}
OR
{{"action": "end_turn", "reasoning": "..."}}
""",
    "synergy": """You are an expert Slay the Spire deckbuilder evaluating a {character} run.
Analyze the deck and relics, then answer the questions asked.
Output format: JSON object with keys matching the questions.
""",
    "run": """You are an expert Slay the Spire player making run-level decisions for the {character}.
You will be asked to make decisions at each node: which card to pick, which path to take, what to do at rest sites.
Always output valid JSON matching the requested format.
""",
}

_CHARACTER_TITLES = {"ironclad": "Ironclad", "silent": "Silent"}


def system_prompt(kind: str, character: str = "ironclad") -> str:
    """Character-aware system prompt ('turn' | 'combat' | 'synergy' | 'run')."""
    name = _CHARACTER_TITLES.get(character, character.title())
    return _SYSTEM_TEMPLATES[kind].format(character=name)


# Ironclad-formatted constants kept for backwards compatibility.
SYSTEM_TURN = system_prompt("turn")
SYSTEM_COMBAT = system_prompt("combat")
SYSTEM_SYNERGY = system_prompt("synergy")
SYSTEM_RUN = system_prompt("run")
