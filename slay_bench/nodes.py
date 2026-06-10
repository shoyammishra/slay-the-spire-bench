"""Node resolution: rest, shop, treasure, event handlers."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, List, Optional, Dict, Any, Callable

if TYPE_CHECKING:
    from .state import GameState
    from .cards import Card
    from .relics import Relic
    from .potions import Potion


# ── Rest site ─────────────────────────────────────────────────────────────────

class RestSiteAction:
    REST = "rest"
    SMITH = "smith"
    LIFT = "lift"
    DIG = "dig"
    RECALL = "recall"
    TOKE = "toke"


def resolve_rest(state: GameState, action: str, card_to_upgrade: Optional[Card] = None) -> None:
    from .events import Event
    state.bus.emit(Event.REST_SITE_ENTER, state)

    if action == RestSiteAction.REST:
        # Coffee Dripper: resting no longer heals (enforced here so EVERY
        # caller honors it, not just the harness paths)
        if getattr(state.player, '_no_rest_heal', False):
            heal = 0
        else:
            heal = int(state.player.max_hp * 0.30)
            # Regal Pillow: +15 heal when resting
            if any(r.id == "Regal Pillow" for r in state.player.relics):
                heal += 15
        state.player.hp = min(state.player.max_hp, state.player.hp + heal)

    elif action == RestSiteAction.SMITH:
        # Fusion Hammer: smithing is disabled
        if getattr(state.player, '_no_smith', False):
            pass
        elif card_to_upgrade and card_to_upgrade in state.player.deck:
            card_to_upgrade.upgrade()
            state.bus.emit(Event.CARD_UPGRADED, state, card=card_to_upgrade)

    elif action == RestSiteAction.LIFT:
        # Girya relic required — adds Strength for next combat
        pass

    elif action == RestSiteAction.DIG:
        # Shovel relic required — find a relic
        from .relics import random_relic
        relic = random_relic(state, "common")
        _obtain_relic(state, relic)

    elif action == RestSiteAction.TOKE:
        # Peace Pipe relic required — remove the worst card
        # (curse → basic Strike → basic Defend; nothing if none of those)
        if getattr(state.player, '_peace_pipe', False):
            from .enums import CardType
            deck = state.player.deck
            target = next((c for c in deck if c.type == CardType.CURSE), None)
            if target is None:
                target = next((c for c in deck if c.name == "Strike"), None) \
                    or next((c for c in deck if c.name == "Defend"), None)
            if target is not None:
                deck.remove(target)
                state.player._cards_removed = \
                    getattr(state.player, '_cards_removed', 0) + 1
                state.bus.emit(Event.CARD_REMOVED, state, card=target)


# ── Shop ──────────────────────────────────────────────────────────────────────

@dataclass
class ShopInventory:
    cards: List[Card] = field(default_factory=list)
    relics: List[Relic] = field(default_factory=list)
    potions: List[Potion] = field(default_factory=list)
    card_prices: Dict[str, int] = field(default_factory=dict)   # card id -> gold
    relic_prices: Dict[str, int] = field(default_factory=dict)
    potion_prices: Dict[str, int] = field(default_factory=dict)
    removal_cost: int = 75
    removal_used: int = 0


def generate_shop(state: GameState) -> ShopInventory:
    """Generate a shop inventory with 5 cards, 2 potions, 1-2 relics."""
    from .rewards import generate_card_reward, card_pool_for
    from .enums import CardRarity
    from .relics import random_relic
    from .potions import random_potion, POTION_POOL
    from .cards import make_card_for

    character = getattr(state, "character", "ironclad")
    char_pool = card_pool_for(state)
    shop = ShopInventory()

    # 5 cards: 2 common, 2 uncommon, 1 rare (base weights)
    _rarity_counts = [
        (CardRarity.COMMON, 2),
        (CardRarity.UNCOMMON, 2),
        (CardRarity.RARE, 1),
    ]
    seen = set()
    for rarity, count in _rarity_counts:
        pool = char_pool[rarity]
        added = 0
        attempts = 0
        while added < count and attempts < 30:
            attempts += 1
            idx = state.rng.card_rng.next_int(len(pool))
            name = pool[idx]
            if name not in seen:
                seen.add(name)
                card = make_card_for(character, name)
                shop.cards.append(card)
                shop.card_prices[id(card)] = _card_price(rarity, state.floor)
                added += 1

    # 2 potions
    for _ in range(2):
        p = random_potion(state)
        shop.potions.append(p)
        shop.potion_prices[id(p)] = _potion_price(state)

    # 1-2 shop relics
    relic_count = 1 + (1 if state.rng.misc_rng.next_int(2) == 0 else 0)
    for _ in range(relic_count):
        r = random_relic(state, "shop")
        shop.relics.append(r)
        shop.relic_prices[id(r)] = _relic_price(r)

    # Membership Card relic: 50% discount
    if any(r.id == "Membership Card" for r in state.player.relics):
        shop.card_prices = {k: v // 2 for k, v in shop.card_prices.items()}
        shop.relic_prices = {k: v // 2 for k, v in shop.relic_prices.items()}

    return shop


def _card_price(rarity: CardRarity, floor: int) -> int:
    from .enums import CardRarity as CR
    base = {CR.COMMON: 45, CR.UNCOMMON: 68, CR.RARE: 135}[rarity]
    # Slight floor scaling
    return base + (floor // 5) * 5


def _potion_price(state: GameState) -> int:
    return 48 + state.rng.misc_rng.next_int(20)


def _relic_price(relic: Relic) -> int:
    # Very rough; real game uses per-relic prices
    return 143 + 0  # placeholder


def buy_card(state: GameState, shop: ShopInventory, card: Card) -> bool:
    price = shop.card_prices.get(id(card), 9999)
    if state.player.gold < price:
        return False
    state.player.gold -= price
    state.player._maw_bank = False  # Maw Bank deactivates on any purchase
    shop.cards.remove(card)
    state.player.deck.append(card)
    from .events import Event
    state.bus.emit(Event.CARD_ADDED, state, card=card)
    return True


def buy_relic(state: GameState, shop: ShopInventory, relic: Relic) -> bool:
    price = shop.relic_prices.get(id(relic), 9999)
    if state.player.gold < price:
        return False
    state.player.gold -= price
    state.player._maw_bank = False  # Maw Bank deactivates on any purchase
    shop.relics.remove(relic)
    _obtain_relic(state, relic)
    return True


def buy_potion(state: GameState, shop: ShopInventory, potion: Potion) -> bool:
    price = shop.potion_prices.get(id(potion), 9999)
    if state.player.gold < price:
        return False
    if len(state.player.potions) >= 3:
        return False
    state.player.gold -= price
    state.player._maw_bank = False  # Maw Bank deactivates on any purchase
    shop.potions.remove(potion)
    state.player.potions.append(potion)
    return True


def remove_card(state: GameState, shop: ShopInventory, card: Card) -> bool:
    """Pay to remove a card from deck."""
    # Smiling Mask: card removal always costs 50
    if getattr(state.player, '_smiling_mask', False):
        cost = 50
    else:
        cost = shop.removal_cost + shop.removal_used * 25
    if state.player.gold < cost:
        return False
    if card not in state.player.deck:
        return False
    state.player.gold -= cost
    state.player._maw_bank = False  # Maw Bank deactivates on any purchase
    shop.removal_used += 1
    state.player.deck.remove(card)
    state.player._cards_removed = getattr(state.player, '_cards_removed', 0) + 1
    from .events import Event
    state.bus.emit(Event.CARD_REMOVED, state, card=card)
    return True


def greedy_shop_visit(state: GameState) -> dict:
    """Deterministic shop policy shared by both run loops (the previous
    MERCHANT no-op made shop floors free passes and gold useless):
    Meal Ticket heal, then pay to remove the worst card (curse → basic
    Strike → basic Defend) if gold allows. Conservatively buys nothing else."""
    from .enums import CardType
    result = {"outcome": "shop", "removed": None}
    # Meal Ticket: heal 15 HP whenever you enter a shop
    if getattr(state.player, '_meal_ticket', False):
        state.player.hp = min(state.player.max_hp, state.player.hp + 15)
    shop = generate_shop(state)  # consumes RNG like a real shop visit
    deck = state.player.deck
    target = next((c for c in deck if c.type == CardType.CURSE), None)
    if target is None:
        target = next((c for c in deck if c.name == "Strike"), None) \
            or next((c for c in deck if c.name == "Defend"), None)
    if target is not None and remove_card(state, shop, target):
        result["removed"] = target.name
    return result


# ── Treasure ──────────────────────────────────────────────────────────────────

def resolve_treasure(state: GameState, take_gold: bool = True) -> None:
    """Open a chest. Small/Large chest with relic."""
    from .relics import random_relic
    # Roll chest size (33% large, 67% small)
    large = state.rng.misc_rng.next_int(3) == 0
    rarity = "rare" if large else "common"
    relic = random_relic(state, rarity)
    _obtain_relic(state, relic, source="chest")
    if take_gold:
        gold = (55 + state.rng.loot_rng.next_int(26)) if large else (25 + state.rng.loot_rng.next_int(26))
        state.player.gold += gold
        from .events import Event
        state.bus.emit(Event.GOLD_GAINED, state, amount=gold)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _obtain_relic(state: GameState, relic: Relic, source: Optional[str] = None) -> None:
    state.player.relics.append(relic)
    # One-time pickup effects (max HP, energy/turn, deck changes) happen exactly
    # once here; register() is re-run at the start of every combat and must only
    # contain subscriptions/idempotent flags.
    relic.on_pickup(state)
    relic.register(state)
    from .events import Event
    # source tags where the relic came from ("chest", None) — Cursed Key keys on it
    state.bus.emit(Event.RELIC_OBTAINED, state, relic=relic, source=source)
