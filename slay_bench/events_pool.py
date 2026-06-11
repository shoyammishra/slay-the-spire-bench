"""Event pool: ~50 events across all acts with branching outcomes."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, List, Callable, Optional, Dict

if TYPE_CHECKING:
    from .state import GameState


@dataclass
class EventChoice:
    label: str
    effect: Callable  # (state) -> str  returns flavor text


@dataclass
class GameEvent:
    id: str
    name: str
    description: str
    acts: List[int]  # which acts this can appear in
    choices: List[EventChoice] = field(default_factory=list)
    condition: Optional[Callable] = None  # (state) -> bool; None = always available


def _register_events() -> Dict[str, GameEvent]:
    events: Dict[str, GameEvent] = {}

    def add(e: GameEvent):
        events[e.id] = e

    # ── Act 1 Events ──────────────────────────────────────────────────────────

    add(GameEvent(
        id="Neow",
        name="Neow's Lament",
        description="You encounter Neow at the start of your journey.",
        acts=[1],
        # Run-start ONLY: without the floor gate this sat in the regular event
        # pool, and the auto-picked choice 0 (1-HP enemies for 3 combats)
        # trivialised combats mid-run — inflating run-level scores.
        condition=lambda s: s.player.floor == 0,
        choices=[
            EventChoice("Enemies in your first 3 combats have 1 HP", lambda s: _neow_1hp(s)),
            EventChoice("Obtain 100 gold", lambda s: _give_gold(s, 100)),
            EventChoice("Choose a card to remove from your starting deck", lambda s: _remove_starter(s)),
            EventChoice("Obtain a random rare relic — Max HP -10", lambda s: _neow_rare_relic(s)),
        ],
    ))

    add(GameEvent(
        id="BigFish",
        name="Big Fish",
        description="A giant fish surfaces before you.",
        acts=[1],
        choices=[
            EventChoice("Banana (Heal 33% HP)", lambda s: _heal_pct(s, 0.33)),
            EventChoice("Donut (+5 Max HP)", lambda s: _max_hp(s, 5)),
            EventChoice("Box (Random relic, gain Curse: Regret)", lambda s: _big_fish_box(s)),
        ],
    ))

    add(GameEvent(
        id="TheWall",
        name="The Wall",
        description="You stand before a massive wall.",
        acts=[1],
        choices=[
            EventChoice("Punch the wall (lose 7 HP, upgrade a card)", lambda s: _wall_punch(s)),
            EventChoice("Leave", lambda s: "You walk away."),
        ],
    ))

    add(GameEvent(
        id="GoldenIdol",
        name="Golden Idol",
        description="A golden idol gleams before you.",
        acts=[1, 2, 3],
        choices=[
            EventChoice("Take it (gain 250 gold, Curse: Injury)", lambda s: _golden_idol_take(s)),
            EventChoice("Leave it", lambda s: "You leave the idol."),
        ],
    ))

    add(GameEvent(
        id="DeadAdventurer",
        name="Dead Adventurer",
        description="You find the remains of a fallen adventurer.",
        acts=[1, 2],
        choices=[
            EventChoice("Search the body (60% relic, 40% fight)", lambda s: _dead_adventurer_search(s)),
            EventChoice("Leave", lambda s: "You move on."),
        ],
    ))

    add(GameEvent(
        id="ForgottenAltar",
        name="Forgotten Altar",
        description="You discover an ancient altar.",
        acts=[1, 2],
        choices=[
            EventChoice("Offer your blood (lose 25% HP, gain random relic)", lambda s: _altar_blood(s)),
            EventChoice("Offer your gold (lose 75 gold, gain relic) ", lambda s: _altar_gold(s)),
            EventChoice("Leave", lambda s: "You leave the altar."),
        ],
    ))

    add(GameEvent(
        id="OldBeggar",
        name="Old Beggar",
        description="An old man asks for gold.",
        acts=[1, 2, 3],
        choices=[
            EventChoice("Pay 75 gold (remove a card from deck)", lambda s: _beggar_remove(s)),
            EventChoice("Leave", lambda s: "You walk past."),
        ],
    ))

    add(GameEvent(
        id="UpgradeShrine",
        name="Upgrade Shrine",
        description="A shrine that can enhance your cards.",
        acts=[1, 2, 3],
        choices=[
            EventChoice("Pray (upgrade a random card)", lambda s: _upgrade_random(s)),
        ],
    ))

    add(GameEvent(
        id="Transmogrifier",
        name="Transmogrifier",
        description="A strange machine hums before you.",
        acts=[1, 2, 3],
        choices=[
            EventChoice("Transform a card (replace with random card of same rarity)", lambda s: _transform_card(s)),
            EventChoice("Leave", lambda s: "The machine remains silent."),
        ],
    ))

    add(GameEvent(
        id="WorldOfGoop",
        name="World of Goop",
        description="You sink into a pit of goop.",
        acts=[1],
        choices=[
            EventChoice("Struggle free (lose 11 HP)", lambda s: _damage_event(s, 11)),
            EventChoice("Offer gold (lose up to 30 gold)", lambda s: _lose_gold(s, 30)),
        ],
    ))

    add(GameEvent(
        id="WeMeetAgain",
        name="We Meet Again",
        description="A merchant offers a trade.",
        acts=[1, 2, 3],
        choices=[
            EventChoice("Give a potion (receive a relic)", lambda s: _trade_potion(s)),
            EventChoice("Give gold (receive a relic)", lambda s: _trade_gold(s)),
            EventChoice("Give a card (receive a relic)", lambda s: _trade_card(s)),
            EventChoice("Leave", lambda s: "You part ways."),
        ],
    ))

    add(GameEvent(
        id="MaskedBandits",
        name="Masked Bandits",
        description="Bandits block your path.",
        acts=[1, 2, 3],
        choices=[
            EventChoice("Pay them (lose all gold)", lambda s: _pay_bandits(s)),
            EventChoice("Fight (enter combat with Bandits)", lambda s: "You draw your weapon!"),
        ],
    ))

    add(GameEvent(
        id="ShiningLight",
        name="Shining Light",
        description="A brilliant light offers power at a cost.",
        acts=[1, 2, 3],
        choices=[
            EventChoice("Enter the light (lose 30% max HP, upgrade 2 random cards)", lambda s: _shining_light(s)),
            EventChoice("Leave", lambda s: "You shield your eyes and walk away."),
        ],
    ))

    add(GameEvent(
        id="ScrapOoze",
        name="Scrap Ooze",
        description="An ooze holds a relic. Each attempt costs HP.",
        acts=[1, 2],
        choices=[
            EventChoice("Attempt to grab (10% +10% per try, cost 3/5/8/13 HP)", lambda s: _scrap_ooze(s)),
            EventChoice("Leave", lambda s: "You back away slowly."),
        ],
    ))

    add(GameEvent(
        id="NlothsGift",
        name="N'loth's Gift",
        description="N'loth appears, offering a trade.",
        acts=[2, 3],
        choices=[
            EventChoice("Trade 2 relics for a rare relic", lambda s: _nloths_trade(s)),
            EventChoice("Leave", lambda s: "N'loth frowns and vanishes."),
        ],
        condition=lambda s: len(s.player.relics) >= 3,
    ))

    add(GameEvent(
        id="Falling",
        name="Falling",
        description="You tumble down a chasm. You lose a card.",
        acts=[2],
        choices=[
            EventChoice("Brace for impact", lambda s: _falling_lose_card(s)),
        ],
    ))

    add(GameEvent(
        id="MindBloom",
        name="Mind Bloom",
        description="A strange flower presents visions.",
        acts=[3],
        choices=[
            EventChoice("I am War (fight Act 1 boss, gain gold)", lambda s: _mind_bloom_war(s)),
            EventChoice("I am Awake (+1 Max HP per 5 cards)", lambda s: _mind_bloom_awake(s)),
            EventChoice("I am Rich (gain 999 gold, Cursed!)", lambda s: _mind_bloom_rich(s)),
        ],
    ))

    add(GameEvent(
        id="CouncilOfGhosts",
        name="Council of Ghosts",
        description="Ghostly apparitions surround you.",
        acts=[3],
        choices=[
            EventChoice("Offer half your HP (gain 5 Apparitions)", lambda s: _council_ghosts(s)),
            EventChoice("Leave", lambda s: "The ghosts wail as you flee."),
        ],
    ))

    add(GameEvent(
        id="Cursed_Tome",
        name="Cursed Tome",
        description="A tome hums with dark energy.",
        acts=[2, 3],
        choices=[
            EventChoice("Read it (take 1/2/3 damage 3 turns, gain random rare)", lambda s: _cursed_tome(s)),
            EventChoice("Leave", lambda s: "You resist the temptation."),
        ],
    ))

    add(GameEvent(
        id="DrugDealer",
        name="Drug Dealer",
        description="A shady figure offers wares.",
        acts=[1, 2, 3],
        choices=[
            EventChoice("Buy (gain 2 potions, Curse: Shame)", lambda s: _drug_dealer(s)),
            EventChoice("Leave", lambda s: "You decline the offer."),
        ],
    ))

    add(GameEvent(
        id="FountainOfCurseRemoval",
        name="Fountain of Cleansing",
        description="A pure fountain cleanses curses.",
        acts=[1, 2, 3],
        choices=[
            EventChoice("Drink (remove all curses from deck)", lambda s: _cleanse_curses(s)),
        ],
    ))

    add(GameEvent(
        id="GoldenWing",
        name="Golden Wing",
        description="A golden feather glows before you.",
        acts=[1, 2, 3],
        choices=[
            EventChoice("Take feather (lose a relic, gain random rare relic)", lambda s: _golden_wing(s)),
            EventChoice("Leave", lambda s: "The feather dissolves."),
        ],
        condition=lambda s: len(s.player.relics) >= 2,
    ))

    add(GameEvent(
        id="LivingWall",
        name="Living Wall",
        description="A living wall offers power.",
        acts=[3],
        choices=[
            EventChoice("Forget (remove a card)", lambda s: _remove_random_card(s)),
            EventChoice("Grow (+3 Max HP)", lambda s: _max_hp(s, 3)),
            EventChoice("Ingrain (upgrade a card)", lambda s: _upgrade_random(s)),
        ],
    ))

    add(GameEvent(
        id="TheMoaiHead",
        name="The Moai Head",
        description="A giant stone head blocks the path.",
        acts=[2, 3],
        choices=[
            EventChoice("Offer gold (gain Max HP equal to gold spent / 3)", lambda s: _moai_head(s)),
            EventChoice("Leave", lambda s: "The head stares blankly."),
        ],
    ))

    add(GameEvent(
        id="PleadingVagrant",
        name="Pleading Vagrant",
        description="A vagrant pleads for help.",
        acts=[2, 3],
        choices=[
            EventChoice("Give 85 gold (gain a relic)", lambda s: _vagrant_relic(s)),
            EventChoice("Rob (gain 150 gold, Curse: Shame)", lambda s: _vagrant_rob(s)),
            EventChoice("Leave", lambda s: "You walk past."),
        ],
    ))

    add(GameEvent(
        id="Colosseum",
        name="The Colosseum",
        description="You are forced to fight in the Colosseum.",
        acts=[2],
        choices=[
            EventChoice("Fight first wave", lambda s: "You enter the arena!"),
        ],
    ))

    add(GameEvent(
        id="TrialOfFire",
        name="Trial of Fire",
        description="A flaming trial awaits.",
        acts=[2],
        choices=[
            EventChoice("Enter (fight Reptomancer for a rare relic)", lambda s: "You face the trial!"),
            EventChoice("Leave", lambda s: "You choose safety."),
        ],
    ))

    add(GameEvent(
        id="Duplicator",
        name="Duplicator",
        description="A machine that duplicates cards.",
        acts=[1, 2, 3],
        choices=[
            EventChoice("Duplicate a card (add a copy)", lambda s: _duplicate_card(s)),
            EventChoice("Leave", lambda s: "The machine powers down."),
        ],
    ))

    add(GameEvent(
        id="MysteriousSphere",
        name="Mysterious Sphere",
        description="A glowing orb hums with energy.",
        acts=[1, 2, 3],
        choices=[
            EventChoice("Open it (fight 2 elites, gain 2 relics)", lambda s: "You crack the sphere open!"),
            EventChoice("Leave", lambda s: "The orb fades."),
        ],
    ))

    add(GameEvent(
        id="WingedStatue",
        name="Winged Statue",
        description="A statue with outstretched wings.",
        acts=[1, 2, 3],
        choices=[
            EventChoice("Pray (remove a card from deck)", lambda s: _remove_random_card(s)),
            EventChoice("Destroy it (take 3 damage for each card removed this run)", lambda s: _winged_statue_destroy(s)),
        ],
    ))

    return events


# ── Effect helpers ─────────────────────────────────────────────────────────────

def _heal_pct(state: GameState, pct: float) -> str:
    heal = int(state.player.max_hp * pct)
    state.player.hp = min(state.player.max_hp, state.player.hp + heal)
    return f"You heal {heal} HP."

def _max_hp(state: GameState, amount: int) -> str:
    state.player.max_hp += amount
    state.player.hp += amount
    return f"+{amount} Max HP."

def _give_gold(state: GameState, amount: int) -> str:
    state.player.gold += amount
    return f"You gain {amount} gold."

def _lose_gold(state: GameState, amount: int) -> str:
    lost = min(amount, state.player.gold)
    state.player.gold -= lost
    return f"You lose {lost} gold."

def _damage_event(state: GameState, amount: int) -> str:
    from .cards import _damage_player
    _damage_player(state, amount, is_hp_loss=True)
    return f"You take {amount} damage."

def _upgrade_random(state: GameState) -> str:
    candidates = [c for c in state.player.deck if not c.upgraded]
    if not candidates:
        return "No cards to upgrade."
    idx = state.rng.event_rng.next_int(len(candidates))
    candidates[idx].upgrade()
    return f"Upgraded {candidates[idx]}."

def _remove_random_card(state: GameState) -> str:
    if not state.player.deck:
        return "No cards to remove."
    idx = state.rng.event_rng.next_int(len(state.player.deck))
    card = state.player.deck.pop(idx)
    state.player._cards_removed = getattr(state.player, '_cards_removed', 0) + 1
    return f"Removed {card}."

def _remove_starter(state: GameState) -> str:
    return _remove_random_card(state)

def _transform_card(state: GameState) -> str:
    if not state.player.deck:
        return "No cards to transform."
    from .cards import make_card_for
    from .rewards import card_pool_for
    character = getattr(state, "character", "ironclad")
    char_pool = card_pool_for(state)  # Silent must not get Ironclad cards
    idx = state.rng.event_rng.next_int(len(state.player.deck))
    old = state.player.deck[idx]
    pool_by_rarity = char_pool.get(old.rarity, list(char_pool.values())[0])
    new_name = pool_by_rarity[state.rng.event_rng.next_int(len(pool_by_rarity))]
    state.player.deck[idx] = make_card_for(character, new_name)
    return f"Transformed {old} into {state.player.deck[idx]}."

def _duplicate_card(state: GameState) -> str:
    if not state.player.deck:
        return "No cards to duplicate."
    idx = state.rng.event_rng.next_int(len(state.player.deck))
    card = state.player.deck[idx]
    state.player.deck.append(card.copy())
    return f"Duplicated {card}."

def _obtain_relic_event(state: GameState, rarity: str = "common") -> str:
    from .relics import random_relic
    from .nodes import _obtain_relic
    relic = random_relic(state, rarity)
    _obtain_relic(state, relic)
    return f"Obtained {relic}."

def _add_curse(state: GameState, curse_name: str) -> str:
    from .cards import make_card
    curse = make_card(curse_name)
    state.player.deck.append(curse)
    return f"Added {curse} to your deck."

def _neow_1hp(state: GameState) -> str:
    state._neow_1hp_combats = 3
    return "First 3 combat enemies have 1 HP."

def _neow_rare_relic(state: GameState) -> str:
    state.player.max_hp -= 10
    state.player.hp = min(state.player.hp, state.player.max_hp)
    return _obtain_relic_event(state, "rare")

def _big_fish_box(state: GameState) -> str:
    _add_curse(state, "Regret")
    return _obtain_relic_event(state, "common")

def _wall_punch(state: GameState) -> str:
    from .cards import _damage_player
    _damage_player(state, 7, is_hp_loss=True)
    return _upgrade_random(state)

def _golden_idol_take(state: GameState) -> str:
    state.player.gold += 250
    return _add_curse(state, "Injury")

def _dead_adventurer_search(state: GameState) -> str:
    roll = state.rng.event_rng.next_int(10)
    if roll < 6:
        return _obtain_relic_event(state, "common")
    return "Fight triggered! (not implemented in event-only mode)"

def _altar_blood(state: GameState) -> str:
    loss = state.player.max_hp // 4
    state.player.hp = max(1, state.player.hp - loss)
    return _obtain_relic_event(state)

def _altar_gold(state: GameState) -> str:
    if state.player.gold < 75:
        return "Not enough gold."
    state.player.gold -= 75
    return _obtain_relic_event(state)

def _beggar_remove(state: GameState) -> str:
    if state.player.gold < 75:
        return "Not enough gold."
    state.player.gold -= 75
    return _remove_random_card(state)

def _scrap_ooze(state: GameState) -> str:
    costs = [3, 5, 8, 13]
    for i, cost in enumerate(costs):
        from .cards import _damage_player
        _damage_player(state, cost, is_hp_loss=True)
        chance = 10 + i * 10
        if state.rng.event_rng.next_int(100) < chance or i == len(costs) - 1:
            return _obtain_relic_event(state)
    return "Failed to grab relic."

def _shining_light(state: GameState) -> str:
    # Lose 30% max HP, upgrade 2 random un-upgraded cards.
    loss = (state.player.max_hp * 30) // 100
    from .cards import _damage_player
    _damage_player(state, loss, is_hp_loss=True)
    upgradeable = [c for c in state.player.deck if not getattr(c, "upgraded", False)]
    upgraded = 0
    for _ in range(2):
        if not upgradeable:
            break
        idx = state.rng.event_rng.next_int(len(upgradeable))
        card = upgradeable.pop(idx)
        try:
            card.upgrade()
            upgraded += 1
        except NotImplementedError:
            pass
    return f"Lost {loss} HP, upgraded {upgraded} cards."

def _nloths_trade(state: GameState) -> str:
    if len(state.player.relics) < 3:  # matches the event's availability condition
        return "Not enough relics."
    state.player.relics.pop()
    state.player.relics.pop()
    return _obtain_relic_event(state, "rare")

def _falling_lose_card(state: GameState) -> str:
    from .enums import CardType
    # Lose one skill, power, or attack (random category)
    cat = state.rng.event_rng.next_int(3)
    target_type = [CardType.SKILL, CardType.POWER, CardType.ATTACK][cat]
    candidates = [c for c in state.player.deck if c.type == target_type]
    if candidates:
        idx = state.rng.event_rng.next_int(len(candidates))
        card = candidates[idx]
        state.player.deck.remove(card)
        return f"You lose {card}."
    return "No cards of that type to lose."

def _mind_bloom_war(state: GameState) -> str:
    # The boss fight is not implemented in event-only mode — granting the
    # 100-gold reward without the fight was a free lunch for the run loop.
    return "Fight Act 1 boss! (not implemented in event-only mode — no reward)"

def _mind_bloom_awake(state: GameState) -> str:
    gain = len(state.player.deck) // 5
    _max_hp(state, gain)
    return f"+{gain} Max HP from {len(state.player.deck)} cards."

def _mind_bloom_rich(state: GameState) -> str:
    state.player.gold += 999
    for _ in range(3):
        _add_curse(state, "Regret")
    return "You are rich! But cursed!"

def _council_ghosts(state: GameState) -> str:
    from .cards import Apparition
    loss = state.player.hp // 2
    state.player.hp = max(1, state.player.hp - loss)
    for _ in range(5):
        state.player.deck.append(Apparition())
    return f"Lost {loss} HP, gained 5 Apparitions."

def _cursed_tome(state: GameState) -> str:
    # Take cumulative damage, gain rare relic
    total = 1 + 2 + 3
    from .cards import _damage_player
    _damage_player(state, total, is_hp_loss=True)
    return _obtain_relic_event(state, "rare")

def _drug_dealer(state: GameState) -> str:
    from .potions import random_potion
    for _ in range(2):
        if len(state.player.potions) < 3:
            state.player.potions.append(random_potion(state))
    return _add_curse(state, "Shame")

def _cleanse_curses(state: GameState) -> str:
    from .enums import CardType
    before = len(state.player.deck)
    state.player.deck = [c for c in state.player.deck if c.type != CardType.CURSE]
    removed = before - len(state.player.deck)
    return f"Removed {removed} curses."

def _golden_wing(state: GameState) -> str:
    if not state.player.relics:
        return "No relics to sacrifice."
    state.player.relics.pop()
    return _obtain_relic_event(state, "rare")

def _moai_head(state: GameState) -> str:
    gain = state.player.gold // 3
    state.player.gold = 0
    _max_hp(state, gain)
    return f"Traded all gold for +{gain} Max HP."

def _vagrant_relic(state: GameState) -> str:
    if state.player.gold < 85:
        return "Not enough gold."
    state.player.gold -= 85
    return _obtain_relic_event(state)

def _vagrant_rob(state: GameState) -> str:
    state.player.gold += 150
    return _add_curse(state, "Shame")

def _winged_statue_destroy(state: GameState) -> str:
    # Damage per card removed this run (tracked on player)
    removed = getattr(state.player, '_cards_removed', 0)
    dmg = removed * 3
    from .cards import _damage_player
    _damage_player(state, dmg, is_hp_loss=True)
    return f"Took {dmg} damage."

def _trade_potion(state: GameState) -> str:
    if not state.player.potions:
        return "No potions to trade."
    state.player.potions.pop()
    return _obtain_relic_event(state)

def _trade_gold(state: GameState) -> str:
    if state.player.gold < 50:
        return "Not enough gold."
    state.player.gold -= 50
    return _obtain_relic_event(state)

def _trade_card(state: GameState) -> str:
    return _remove_random_card(state) + " " + _obtain_relic_event(state)

def _pay_bandits(state: GameState) -> str:
    lost = state.player.gold
    state.player.gold = 0
    return f"You pay {lost} gold."


# ── Event selection ───────────────────────────────────────────────────────────

EVENT_REGISTRY = _register_events()


def available_events(state: GameState) -> List[GameEvent]:
    """Return events valid for the current act."""
    return [
        e for e in EVENT_REGISTRY.values()
        if state.act in e.acts
        and (e.condition is None or e.condition(state))
    ]


def random_event(state: GameState) -> GameEvent:
    """Select a random event for the current floor. Events seen this run are
    excluded until the pool is exhausted (StS events don't repeat)."""
    seen = getattr(state, '_seen_events', set())
    available = available_events(state)
    pool = [e for e in available if e.id not in seen]
    if not pool:
        pool = available or list(EVENT_REGISTRY.values())
    idx = state.rng.event_rng.next_int(len(pool))
    event = pool[idx]
    state._seen_events = seen | {event.id}
    return event


def resolve_event(state: GameState, event: GameEvent, choice_index: int) -> str:
    """Execute the chosen option of an event."""
    if choice_index < 0 or choice_index >= len(event.choices):
        return "Invalid choice."
    choice = event.choices[choice_index]
    return choice.effect(state)
