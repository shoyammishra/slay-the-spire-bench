"""Card reward and draft system."""
from __future__ import annotations
from typing import TYPE_CHECKING, List

from .enums import CardRarity

if TYPE_CHECKING:
    from .state import GameState
    from .cards import Card


# Rarity weights per act (base, without relic modifiers)
_RARITY_WEIGHTS = {
    CardRarity.COMMON:   (60, 50, 40),   # act 1/2/3
    CardRarity.UNCOMMON: (37, 40, 40),
    CardRarity.RARE:     (3,  10, 20),
}

# All Ironclad card names by rarity (used for random selection)
_IRONCLAD_POOL = {
    CardRarity.COMMON: [
        "Anger", "Armaments", "Body Slam", "Clash", "Cleave", "Clothesline",
        "Flex", "Havoc", "Headbutt", "Heavy Blade", "Iron Wave",
        "Perfected Strike", "Pommel Strike", "Shrug It Off", "Sword Boomerang",
        "Thunderclap", "True Grit", "Twin Strike", "Warcry", "Wild Strike",
    ],
    CardRarity.UNCOMMON: [
        "Battle Trance", "Blood for Blood", "Bloodletting", "Burning Pact",
        "Carnage", "Combust", "Dark Embrace", "Disarm", "Dropkick", "Dual Wield",
        "Entrench", "Evolve", "Feel No Pain", "Fire Breathing", "Flame Barrier",
        "Ghostly Armor", "Hemokinesis", "Infernal Blade", "Inflame", "Intimidate",
        "Metallicize", "Power Through", "Pummel", "Rage", "Rampage",
        "Reckless Charge", "Rupture", "Searing Blow", "Second Wind", "Seeing Red",
        "Sentinel", "Sever Soul", "Shockwave", "Spot Weakness", "Uppercut",
        "Whirlwind",
    ],
    CardRarity.RARE: [
        "Barricade", "Berserk", "Bludgeon", "Brutality", "Corruption",
        "Demon Form", "Double Tap", "Exhume", "Feed", "Fiend Fire",
        "Immolate", "Impervious", "Juggernaut", "Limit Break", "Offering",
        "Reaper",
    ],
}


def card_pool_for(state: GameState) -> dict:
    """Rarity → card-name pool for the state's character."""
    if getattr(state, "character", "ironclad") == "silent":
        from .cards_silent import SILENT_POOL
        return SILENT_POOL
    return _IRONCLAD_POOL


def _roll_rarity(state: GameState) -> CardRarity:
    act = min(state.act, 3) - 1
    common_w = _RARITY_WEIGHTS[CardRarity.COMMON][act]
    uncommon_w = _RARITY_WEIGHTS[CardRarity.UNCOMMON][act]
    rare_w = _RARITY_WEIGHTS[CardRarity.RARE][act]

    # Question Card relic: +1 rare chance
    # Busted Crown relic: -2 choices shown (handled elsewhere)
    roll = state.rng.card_rng.next_int(common_w + uncommon_w + rare_w)
    if roll < rare_w:
        return CardRarity.RARE
    elif roll < rare_w + uncommon_w:
        return CardRarity.UNCOMMON
    return CardRarity.COMMON


def generate_card_reward(state: GameState, count: int = 3) -> List[Card]:
    """Generate a card reward offer (3 cards, no duplicates)."""
    from .cards import make_card_for
    character = getattr(state, "character", "ironclad")
    char_pool = card_pool_for(state)
    offers: List[Card] = []
    seen_names = set()

    attempts = 0
    while len(offers) < count and attempts < 50:
        attempts += 1
        rarity = _roll_rarity(state)
        pool = char_pool[rarity]
        idx = state.rng.card_rng.next_int(len(pool))
        name = pool[idx]
        if name in seen_names:
            continue
        seen_names.add(name)

        # Rare cards: 25% chance to be upgraded (Prayer Wheel doubles this)
        upgraded = False
        if rarity == CardRarity.RARE and state.rng.card_rng.next_int(100) < 25:
            upgraded = True

        card = make_card_for(character, name, upgraded)
        # Eggs: a matching owned egg upgrades the offered card (real StS effect
        # is "whenever you ADD a card of this type"; applied at reward-generation
        # time like the rare-upgrade roll above). Upgrade IN PLACE (card.upgrade()
        # consumes no RNG) so the existing card_rng call order is unchanged.
        if not card.upgraded:
            from .enums import CardType
            p = state.player
            if ((card.type == CardType.POWER and getattr(p, '_frozen_egg', False)) or
                    (card.type == CardType.ATTACK and getattr(p, '_molten_egg', False)) or
                    (card.type == CardType.SKILL and getattr(p, '_toxic_egg', False))):
                card.upgrade()
        offers.append(card)

    return offers


BOSS_RELIC_POOL: List[str] = []  # populated by relics_full._update_relic_registry()


def generate_boss_relic_choices(state: GameState, count: int = 3) -> List[str]:
    """Return 3 boss relic IDs to choose from (character-gated, deduped)."""
    try:
        from .relics_full import relic_allowed
    except ImportError:
        relic_allowed = lambda rid, ch: True
    character = getattr(state, "character", "ironclad")
    owned = {r.id for r in state.player.relics}
    pool = [r for r in BOSS_RELIC_POOL
            if relic_allowed(r, character) and r not in owned]
    state.rng.loot_rng.shuffle(pool)
    return pool[:count]


def elite_relic_rarity(state: GameState) -> str:
    """Rarity of an elite's relic drop (real-StS odds: 50/33/17)."""
    roll = state.rng.loot_rng.next_int(100)
    if roll < 50:
        return "common"
    if roll < 83:
        return "uncommon"
    return "rare"


def gold_reward(state: GameState, enemy_type: str = "normal") -> int:
    """Roll gold drop for an enemy encounter."""
    base = {"normal": (10, 20), "elite": (25, 35), "boss": (95, 105)}
    lo, hi = base.get(enemy_type, (10, 20))
    gold = lo + state.rng.loot_rng.next_int(hi - lo + 1)
    # Ectoplasm: no gold (roll first so the RNG stream stays seed-stable)
    if getattr(state.player, "_no_gold", False):
        return 0
    # Golden Idol: +25%
    return gold


def potion_drop(state: GameState, enemy_type: str = "normal") -> bool:
    """Should a potion drop? Returns True/False."""
    # Base 40% for normal, 50% for elite
    chance = 40 if enemy_type == "normal" else 50
    dropped = state.rng.potion_rng.next_int(100) < chance
    # Sozu: no potions (roll first so the RNG stream stays seed-stable)
    if getattr(state.player, "_no_potions", False):
        return False
    # White Beast Statue: potions always drop (after the roll, same reason)
    if getattr(state.player, "_potion_always", False):
        return True
    return dropped
