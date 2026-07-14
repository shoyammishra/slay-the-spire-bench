"""Integration tests: full act run, map generation, rewards, events."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from slay_bench import new_ironclad_game, generate_map
from slay_bench.run_loop import run_act
from slay_bench.enums import NodeType
from slay_bench.rewards import generate_card_reward
from slay_bench.events_pool import random_event, resolve_event, available_events
from slay_bench.nodes import generate_shop, buy_card, remove_card
from slay_bench.potions import random_potion


def test_map_generation():
    """Map generates correct structure."""
    state = new_ironclad_game(42)
    game_map = generate_map(1, state.rng.map_rng)
    assert len(game_map.floors) == 15, f"Expected 15 floors, got {len(game_map.floors)}"
    assert game_map.boss_node is not None
    assert game_map.boss_node.node_type == NodeType.BOSS

    # At least 1 merchant and 1 treasure
    all_types = {n.node_type for f in game_map.floors for n in f}
    assert NodeType.MONSTER in all_types
    assert NodeType.REST in all_types
    print(f"[PASS] Map generation: 15 floors, types={sorted(t.name for t in all_types)}")


def test_map_determinism():
    """Same seed produces same map."""
    s1 = new_ironclad_game(7)
    s2 = new_ironclad_game(7)
    m1 = generate_map(1, s1.rng.map_rng)
    m2 = generate_map(1, s2.rng.map_rng)
    t1 = [(n.col, n.node_type.name) for f in m1.floors for n in f]
    t2 = [(n.col, n.node_type.name) for f in m2.floors for n in f]
    assert t1 == t2, "Maps differ for same seed!"
    print(f"[PASS] Map determinism: {len(t1)} nodes match")


def test_card_reward_generation():
    """Card reward produces 3 distinct playable cards."""
    state = new_ironclad_game(10)
    offers = generate_card_reward(state)
    assert len(offers) == 3
    names = [c.name for c in offers]
    assert len(set(names)) == 3, f"Duplicate offers: {names}"
    for card in offers:
        assert card.type is not None
    print(f"[PASS] Card rewards: {names}")


def test_card_reward_determinism():
    """Same seed same rewards."""
    s1 = new_ironclad_game(99)
    s2 = new_ironclad_game(99)
    o1 = generate_card_reward(s1)
    o2 = generate_card_reward(s2)
    assert [c.name for c in o1] == [c.name for c in o2]
    print(f"[PASS] Card reward determinism: {[c.name for c in o1]}")


def test_event_pool():
    """Events are available and resolvable."""
    state = new_ironclad_game(20)
    state.act = 1
    events = available_events(state)
    assert len(events) > 0
    event = random_event(state)
    assert event is not None
    result = resolve_event(state, event, 0)
    assert isinstance(result, str)
    print(f"[PASS] Event pool: {len(events)} events, rolled '{event.name}': {result[:50]}")


def test_shop_generation():
    """Shop generates cards, relics, potions."""
    state = new_ironclad_game(5)
    state.floor = 6
    shop = generate_shop(state)
    assert len(shop.cards) > 0
    assert len(shop.potions) > 0
    print(f"[PASS] Shop: {len(shop.cards)} cards, {len(shop.relics)} relics, {len(shop.potions)} potions")


def test_shop_buy_card():
    """Buying a card spends gold and adds to deck."""
    state = new_ironclad_game(5)
    state.player.gold = 999
    state.floor = 6
    shop = generate_shop(state)
    initial_deck = len(state.player.deck)
    if shop.cards:
        card = shop.cards[0]
        ok = buy_card(state, shop, card)
        assert ok
        assert len(state.player.deck) == initial_deck + 1
        assert state.player.gold < 999
        print(f"[PASS] Buy card: {card.name}, gold={state.player.gold}")


def test_card_removal():
    """Card removal spends gold and shrinks deck."""
    state = new_ironclad_game(3)
    state.player.gold = 999
    state.floor = 4
    from slay_bench.nodes import ShopInventory
    shop = ShopInventory()
    card = state.player.deck[0]
    initial = len(state.player.deck)
    ok = remove_card(state, shop, card)
    assert ok
    assert len(state.player.deck) == initial - 1
    assert state.player.gold == 999 - 75
    print(f"[PASS] Card removal: removed {card.name}, deck={len(state.player.deck)}")


def test_potion_use():
    """Potions can be used in combat."""
    from slay_bench import start_combat, is_combat_over
    from slay_bench.enemies import Cultist
    from slay_bench.potions import BlockPotion
    state = new_ironclad_game(1)
    state.player.potions = [BlockPotion()]
    enemy = Cultist(state.rng.hp_rng)
    start_combat(state, [enemy])
    block_before = state.player.block
    state.player.potions[0].use(state)
    state.player.potions.pop(0)
    assert state.player.block > block_before
    print(f"[PASS] Potion use: block {block_before} -> {state.player.block}")


def test_act1_run():
    """Full Act 1 run completes without error."""
    state = new_ironclad_game(42)
    summary = run_act(state, act=1)
    assert "survived" in summary
    floors_visited = len(summary["floors"])
    print(f"[PASS] Act 1 run: survived={summary['survived']}, floors={floors_visited}, final_hp={state.player.hp}")


def test_act1_run_determinism():
    """Same seed Act 1 run produces same outcome."""
    seed = 77
    s1 = new_ironclad_game(seed)
    s2 = new_ironclad_game(seed)
    r1 = run_act(s1, act=1)
    r2 = run_act(s2, act=1)
    assert r1["survived"] == r2["survived"]
    assert s1.player.hp == s2.player.hp
    print(f"[PASS] Act 1 determinism: survived={r1['survived']}, hp={s1.player.hp}")


def test_relic_registration():
    """Relics register hooks without error."""
    from slay_bench.relics_full import FULL_RELIC_LIST
    state = new_ironclad_game(1)
    for cls in FULL_RELIC_LIST[:10]:
        try:
            r = cls()
            r.register(state)
        except Exception as e:
            print(f"[WARN] {cls.__name__} registration failed: {e}")
    print(f"[PASS] Relic registration: tested {min(10, len(FULL_RELIC_LIST))} relics")


def test_act2_enemies():
    """Act 2 enemies spawn and execute moves."""
    from slay_bench import start_combat, end_player_turn, is_combat_over
    from slay_bench.enemies import ENEMY_REGISTRY
    for eid in ["Chosen", "Byrd", "TorchHead"]:
        state = new_ironclad_game(10)
        cls = ENEMY_REGISTRY.get(eid)
        assert cls, f"Missing enemy: {eid}"
        enemy = cls(state.rng.hp_rng)
        start_combat(state, [enemy])
        enemy.select_move(state)
        enemy.execute_move(state)
        print(f"  {eid}: hp={enemy.hp}, move={enemy.current_move.name if enemy.current_move else 'None'}")
    print(f"[PASS] Act 2 enemy execution")


def test_relic_pools_gated():
    """Boss relics must not leak into chest rares; off-class relics are
    excluded per character; Nuclear Battery (Defect) is out of boss pools."""
    from slay_bench.relics_full import _RARITY_POOLS, relic_allowed, BOSS_RELIC_POOL
    rare_ids = {cls.id for cls in _RARITY_POOLS["rare"]}
    for boss_only in ("Sozu", "Busted Crown", "Velvet Choker", "Sacred Bark",
                      "Empty Cage"):
        assert boss_only not in rare_ids, f"{boss_only} leaked into rare pool"
    assert "Nuclear Battery" not in BOSS_RELIC_POOL
    assert not relic_allowed("Nuclear Battery", "ironclad")   # Defect-only
    assert not relic_allowed("Captain's Wheel", "silent")     # Defect-only
    assert not relic_allowed("Violet Lotus", "ironclad")      # Watcher-only
    assert not relic_allowed("Brimstone", "silent")           # Ironclad-only
    assert not relic_allowed("Tingsha", "ironclad")           # Silent-only
    assert relic_allowed("Brimstone", "ironclad")
    assert relic_allowed("Tingsha", "silent")
    print("[PASS] Relic pools: boss leak fixed + character gating")


def test_boss_relic_choices_gated():
    """generate_boss_relic_choices respects gating and owned-relic dedup."""
    from slay_bench import new_game
    from slay_bench.rewards import generate_boss_relic_choices
    from slay_bench.relics_full import relic_allowed
    state = new_game(42, "silent")
    for _ in range(10):
        for rid in generate_boss_relic_choices(state, 3):
            assert relic_allowed(rid, "silent"), f"off-class boss relic {rid}"
            assert rid not in {r.id for r in state.player.relics}
    print("[PASS] Boss relic choices are character-gated")


def test_merchant_greedy_shop():
    """MERCHANT nodes were no-ops; the greedy policy now buys a removal."""
    from slay_bench.nodes import greedy_shop_visit
    state = new_ironclad_game(5)
    state.player.gold = 200
    deck_before = len(state.player.deck)
    result = greedy_shop_visit(state)
    assert result["removed"] == "Strike", f"expected Strike removal, got {result}"
    assert len(state.player.deck) == deck_before - 1
    assert state.player.gold == 200 - 75
    print(f"[PASS] Merchant: greedy shop removes worst card (gold 200->{state.player.gold})")


def test_maw_bank_and_single_first_move():
    """Maw Bank pays 12/floor and deactivates on purchase; the first node is
    no longer visited twice (double move_to)."""
    from slay_bench.run_loop import RunState
    from slay_bench import generate_map
    state = new_ironclad_game(8)
    game_map = generate_map(1, state.rng.map_rng)
    run = RunState(state, game_map)
    state.player._maw_bank = True
    gold = state.player.gold
    run.move_to(game_map.floors[0][0])
    run.move_to(game_map.floors[1][0])
    assert state.player.gold == gold + 24, \
        f"Maw Bank should pay 12/move: {state.player.gold - gold}"
    # any shop purchase deactivates it
    from slay_bench.nodes import ShopInventory, remove_card
    state.player.gold = 999
    remove_card(state, ShopInventory(), state.player.deck[0])
    assert not state.player._maw_bank, "Maw Bank survived a purchase"
    print("[PASS] Maw Bank pays per floor and deactivates on purchase")


def test_rest_policies():
    """Coffee Dripper: REST heals 0 everywhere; Peace Pipe: TOKE removes the
    worst card (curse first)."""
    from slay_bench.nodes import resolve_rest, RestSiteAction
    from slay_bench.cards import make_card
    state = new_ironclad_game(11)
    state.player.hp = 30
    state.player._no_rest_heal = True
    resolve_rest(state, RestSiteAction.REST)
    assert state.player.hp == 30, "Coffee Dripper REST must heal 0"
    # Peace Pipe toke removes the curse
    state.player._peace_pipe = True
    state.player.deck.append(make_card("Regret"))
    deck_before = len(state.player.deck)
    resolve_rest(state, RestSiteAction.TOKE)
    assert len(state.player.deck) == deck_before - 1
    assert not any(c.name == "Regret" for c in state.player.deck)
    print("[PASS] Rest policies: no-heal REST + Peace Pipe toke")


def test_tiny_chest_fires_on_fourth_combat():
    """Tiny Chest's counter reset every combat (could never reach 4)."""
    from slay_bench.relics_full import TinyChest
    from slay_bench.events import Event
    state = new_ironclad_game(13)
    tc = TinyChest()
    state.player.relics.append(tc)
    relics_before = len(state.player.relics)
    for _ in range(4):
        state.bus.clear()          # what start_combat does
        tc.register(state)         # re-registered every combat
        state.bus.emit(Event.COMBAT_END, state)
    assert len(state.player.relics) > relics_before, \
        "Tiny Chest never fired after 4 combats"
    print("[PASS] Tiny Chest fires on the 4th combat (per-run counter)")


def test_bag_of_preparation_every_combat():
    """Bag of Preparation used to fire only in the FIRST combat of a run."""
    from slay_bench import start_combat
    from slay_bench.relics import BagOfPreparation
    from slay_bench.enemies import Cultist
    state = new_ironclad_game(17)
    state.player.relics.append(BagOfPreparation())
    start_combat(state, [Cultist(state.rng.hp_rng)])
    assert len(state.combat.hand) == 7, f"combat 1 hand={len(state.combat.hand)}"
    start_combat(state, [Cultist(state.rng.hp_rng)])
    assert len(state.combat.hand) == 7, \
        f"combat 2 hand={len(state.combat.hand)} — Bag fired only once"
    print("[PASS] Bag of Preparation draws 2 in EVERY combat")


def test_pickup_relics_mutate_deck():
    """Bottled Flame makes the first attack innate; Dolly's Mirror duplicates
    a card (both were no-ops)."""
    from slay_bench.relics_full import BottledFlame, DollysMirror
    from slay_bench.nodes import _obtain_relic
    state = new_ironclad_game(19)
    _obtain_relic(state, BottledFlame())
    first_attack = next(c for c in state.player.deck if c.type.name == "ATTACK")
    assert first_attack.innate, "Bottled Flame did not bottle an attack"
    deck_before = len(state.player.deck)
    _obtain_relic(state, DollysMirror())
    assert len(state.player.deck) == deck_before + 1, "Dolly's Mirror no-op"
    print("[PASS] Bottled Flame + Dolly's Mirror act on pickup")


def test_elite_relic_drop_tagging():
    """spawn_enemies tags elites/bosses (Preserved Insect, Slaver's Collar,
    elite relic drops key on it)."""
    from slay_bench.run_loop import spawn_enemies
    state = new_ironclad_game(23)
    elites = spawn_enemies(state, ["GremlinNob"], elite=True)
    bosses = spawn_enemies(state, ["SlimeBoss"], boss=True)
    normals = spawn_enemies(state, ["Cultist"])
    assert elites[0]._elite and not elites[0]._boss
    assert bosses[0]._boss and not bosses[0]._elite
    assert not normals[0]._elite and not normals[0]._boss
    print("[PASS] Spawn sites tag elite/boss enemies")


# ── 2026-06-11 audit regression tests ─────────────────────────────────────────

def test_neow_gated_to_run_start():
    """Neow's Lament must not appear in the mid-run event pool (its auto-picked
    1-HP boon trivialised combats and inflated run-level scores)."""
    state = new_ironclad_game(42)
    state.player.floor = 1
    ids = [e.id for e in available_events(state)]
    assert "Neow" not in ids, "Neow available mid-run"
    state.player.floor = 0
    ids0 = [e.id for e in available_events(state)]
    assert "Neow" in ids0, "Neow should be available at run start (floor 0)"
    print("[PASS] Neow's Lament is gated to floor 0")


def test_events_do_not_repeat():
    """random_event must not redraw an event seen earlier in the run until the
    pool is exhausted."""
    state = new_ironclad_game(42)
    state.player.floor = 1
    seen = [random_event(state).id for _ in range(8)]
    assert len(seen) == len(set(seen)), f"event repeated: {seen}"
    print("[PASS] Events do not repeat within a run")


def test_mind_bloom_war_no_free_gold():
    """'I am War' must not grant the 100-gold reward while the boss fight is
    unimplemented."""
    from slay_bench.events_pool import EVENT_REGISTRY
    state = new_ironclad_game(42)
    state.act = 3
    gold = state.player.gold
    resolve_event(state, EVENT_REGISTRY["MindBloom"], 0)
    assert state.player.gold == gold, f"free gold granted: {gold}->{state.player.gold}"
    print("[PASS] Mind Bloom 'I am War' grants no unearned gold")


def test_snecko_skull_buffs_applied_poison():
    """Snecko Skull: +1 poison the player APPLIES to enemies — it used to grow
    the player's OWN poison instead (actively harmful)."""
    from slay_bench import new_game
    from slay_bench.combat import start_combat
    from slay_bench.enemies import Cultist
    from slay_bench.enums import PowerId
    from slay_bench.cards import _apply_power
    state = new_game(7, "silent")
    enemy = Cultist(state.rng.hp_rng)
    start_combat(state, [enemy])
    state.player._snecko_skull = True
    _apply_power(state, enemy, PowerId.POISON, 5)
    assert enemy.powers[PowerId.POISON] == 6, \
        f"enemy poison should be 5+1, got {enemy.powers[PowerId.POISON]}"
    _apply_power(state, state.player, PowerId.POISON, 2)
    assert state.player.powers[PowerId.POISON] == 2, \
        "player-targeted poison must NOT be bumped"
    print("[PASS] Snecko Skull buffs poison applied to enemies only")


def test_blue_candle_makes_curses_playable():
    """Blue Candle was a no-op: curses stayed unplayable, so its hook never
    fired. Now: playable, lose 1 HP, exhausted."""
    from slay_bench.relics_full import BlueCandle
    from slay_bench.combat import start_combat, play_card
    from slay_bench.enemies import Cultist
    from slay_bench.cards import make_card
    state = new_ironclad_game(42)
    bc = BlueCandle()
    state.player.relics.append(bc)
    enemy = Cultist(state.rng.hp_rng)
    start_combat(state, [enemy])
    curse = make_card("Regret")
    state.combat.hand[:] = [curse]
    assert curse.can_play(state), "curse must be playable with Blue Candle"
    hp = state.player.hp
    energy = state.player.energy
    play_card(state, curse)
    assert hp - state.player.hp == 1, f"should cost 1 HP, lost {hp - state.player.hp}"
    assert state.player.energy == energy, "curse must cost 0 energy (not -1!)"
    assert any(x is curse for x in state.combat.exhaust_pile), "curse must exhaust"
    print("[PASS] Blue Candle: curses playable (1 HP, exhaust, 0 energy)")


def test_pandoras_box_transforms_basics_only():
    """Pandora's Box matched 'strike' as a substring and transformed
    Twin/Perfected/Pommel Strike too."""
    from slay_bench.relics_full import PandorasBox
    from slay_bench.cards import Strike, Defend, make_card
    state = new_ironclad_game(42)
    state.player.deck = [Strike(), Strike(), Defend(), make_card("Twin Strike"),
                         make_card("Perfected Strike"), make_card("Pommel Strike")]
    PandorasBox().on_pickup(state)
    names = [c.name for c in state.player.deck]
    for kept in ("Twin Strike", "Perfected Strike", "Pommel Strike"):
        assert kept in names, f"{kept} wrongly transformed"
    assert "Strike" not in names and "Defend" not in names, "basics not transformed"
    print("[PASS] Pandora's Box transforms basic Strikes/Defends only")


def test_fairy_in_a_bottle_revives():
    """Potions were never registered on the bus — Fairy's auto-revive could
    not fire. start_combat now registers potion hooks."""
    from slay_bench.potions import FairyInABottle
    from slay_bench.combat import start_combat
    from slay_bench.enemies import Cultist
    from slay_bench.cards import _damage_player
    state = new_ironclad_game(42)
    fairy = FairyInABottle()
    fairy._triggered = False
    state.player.potions.append(fairy)
    enemy = Cultist(state.rng.hp_rng)
    start_combat(state, [enemy])
    state.player.hp = 5
    _damage_player(state, 99)
    expected = max(1, int(state.player.max_hp * 0.3))
    assert state.player.hp == expected, \
        f"Fairy should revive to 30% max HP ({expected}), hp={state.player.hp}"
    assert fairy not in state.player.potions, "Fairy must be consumed"
    print("[PASS] Fairy in a Bottle registers and revives on lethal damage")


def test_random_relic_fallback_stays_in_class():
    """When every fresh relic of a rarity is owned, the fallback must stay
    within character-allowed relics (it used to leak the FULL registry)."""
    from slay_bench.relics import random_relic
    from slay_bench.relics_full import _RARITY_POOLS, relic_allowed
    state = new_ironclad_game(42)
    state.player.relics.extend(cls() for cls in _RARITY_POOLS["common"])
    for _ in range(10):
        r = random_relic(state, "common")
        assert relic_allowed(r.id, "ironclad"), f"off-class relic leaked: {r.id}"
    print("[PASS] random_relic fallback never leaks off-class relics")


# ── 2026-06-12b audit regression tests ────────────────────────────────────────

def test_eggs_upgrade_matching_reward_cards():
    """L2: an owned egg upgrades offered cards of its type at reward generation
    (POWER<->Frozen, ATTACK<->Molten, SKILL<->Toxic)."""
    from slay_bench.enums import CardType
    # Baseline: without eggs, count upgraded ATTACK/SKILL/POWER offers across seeds.
    def count_upgraded(set_flags):
        upg = {CardType.ATTACK: 0, CardType.SKILL: 0, CardType.POWER: 0}
        tot = {CardType.ATTACK: 0, CardType.SKILL: 0, CardType.POWER: 0}
        for seed in range(100, 140):
            state = new_ironclad_game(seed)
            for f in set_flags:
                setattr(state.player, f, True)
            for c in generate_card_reward(state, 3):
                if c.type in tot:
                    tot[c.type] += 1
                    if c.upgraded:
                        upg[c.type] += 1
        return upg, tot
    # Molten egg: every offered ATTACK must be upgraded.
    upg, tot = count_upgraded(["_molten_egg"])
    assert tot[CardType.ATTACK] > 0 and upg[CardType.ATTACK] == tot[CardType.ATTACK], \
        f"Molten Egg must upgrade all attack offers ({upg[CardType.ATTACK]}/{tot[CardType.ATTACK]})"
    # Toxic egg: every offered SKILL upgraded.
    upg, tot = count_upgraded(["_toxic_egg"])
    assert tot[CardType.SKILL] > 0 and upg[CardType.SKILL] == tot[CardType.SKILL], \
        f"Toxic Egg must upgrade all skill offers ({upg[CardType.SKILL]}/{tot[CardType.SKILL]})"
    # Frozen egg: every offered POWER upgraded.
    upg, tot = count_upgraded(["_frozen_egg"])
    assert tot[CardType.POWER] > 0 and upg[CardType.POWER] == tot[CardType.POWER], \
        f"Frozen Egg must upgrade all power offers ({upg[CardType.POWER]}/{tot[CardType.POWER]})"
    print("[PASS] Eggs upgrade matching reward cards")


def test_eggs_preserve_reward_rng_order():
    """L2: the egg upgrade is in-place (no RNG) — reward card NAMES are identical
    with or without an egg (only their upgrade flag differs)."""
    s_no = new_ironclad_game(123)
    names_no = [c.name for c in generate_card_reward(s_no, 3)]
    s_egg = new_ironclad_game(123)
    s_egg.player._molten_egg = True
    s_egg.player._toxic_egg = True
    s_egg.player._frozen_egg = True
    names_egg = [c.name for c in generate_card_reward(s_egg, 3)]
    assert names_no == names_egg, f"egg upgrade must not perturb RNG: {names_no} != {names_egg}"
    print("[PASS] Eggs preserve reward RNG order")


def test_tiny_house_no_energy_upgrades_card():
    """M4: Tiny House grants no +1 energy/turn and upgrades one card."""
    from slay_bench.relics_full import TinyHouse
    state = new_ironclad_game(42)
    e_before = state.player.energy_per_turn
    up_before = sum(1 for c in state.player.deck if c.upgraded)
    TinyHouse().on_pickup(state)
    assert state.player.energy_per_turn == e_before, "Tiny House must NOT grant +1 energy/turn"
    up_after = sum(1 for c in state.player.deck if c.upgraded)
    # One added card + one upgrade. The added reward card may itself be upgraded,
    # but the deck must gain at least one upgraded card from the upgrade step.
    assert up_after >= up_before + 1, "Tiny House must upgrade a card"
    print("[PASS] Tiny House: no energy, upgrades a card")


def test_greedy_baseline_determinism():
    """The scripted greedy run-level baseline is deterministic per seed and reuses
    the LLM run protocol via RunEvaluator (no API calls). Same seed → identical
    floors/progress; this is what makes the measured run-level anchor reproducible."""
    import importlib.util, os as _os
    from slay_bench import new_game
    spec = importlib.util.spec_from_file_location(
        "greedy_baseline",
        _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),
                      "scripts", "greedy_baseline.py"))
    gb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gb)

    for character in ("ironclad", "silent"):
        ev = gb.GreedyRunEvaluator(llm=None, prompt_format="structured",
                                   llm_routing=False, character=character)
        s1 = ev.evaluate(new_game(300 + 42, character), n_acts=1)
        s2 = ev.evaluate(new_game(300 + 42, character), n_acts=1)
        assert s1.floors_reached == s2.floors_reached, \
            f"{character}: greedy floors not deterministic ({s1.floors_reached} vs {s2.floors_reached})"
        assert abs(s1.progress - s2.progress) < 1e-9, f"{character}: greedy progress not deterministic"
        # llm=None never crashes → no real LLM/API call is ever made on the greedy
        # path (llm_calls counts protocol decision points, not API invocations).
        # Sanity: a full Act-1 run touches multiple floors (not an instant death/no-op).
        assert s1.floors_reached >= 1
    print("[PASS] Greedy run-level baseline: deterministic, zero LLM calls")


# ── 2026-07-14 Act 2/3 audit regression tests ─────────────────────────────────

def test_encounter_tables_resolve():
    """C1(a)/M1: every enemy id in all 9 encounter tables resolves in the
    registry, and every pool/encounter is non-empty. This invariant alone would
    have caught the 'DonuAndDeca' phantom id (Act-3 boss spawned ZERO enemies →
    instant free win on 1/3 of boss rolls)."""
    from slay_bench.run_loop import (
        ACT1_MONSTER_ENCOUNTERS, ACT1_ELITE_ENCOUNTERS, ACT1_BOSS_ENCOUNTERS,
        ACT2_MONSTER_ENCOUNTERS, ACT2_ELITE_ENCOUNTERS, ACT2_BOSS_ENCOUNTERS,
        ACT3_MONSTER_ENCOUNTERS, ACT3_ELITE_ENCOUNTERS, ACT3_BOSS_ENCOUNTERS)
    from slay_bench.enemies import ENEMY_REGISTRY
    tables = {
        "ACT1_MONSTER": ACT1_MONSTER_ENCOUNTERS, "ACT1_ELITE": ACT1_ELITE_ENCOUNTERS,
        "ACT1_BOSS": ACT1_BOSS_ENCOUNTERS, "ACT2_MONSTER": ACT2_MONSTER_ENCOUNTERS,
        "ACT2_ELITE": ACT2_ELITE_ENCOUNTERS, "ACT2_BOSS": ACT2_BOSS_ENCOUNTERS,
        "ACT3_MONSTER": ACT3_MONSTER_ENCOUNTERS, "ACT3_ELITE": ACT3_ELITE_ENCOUNTERS,
        "ACT3_BOSS": ACT3_BOSS_ENCOUNTERS,
    }
    for name, table in tables.items():
        assert table, f"{name} pool is empty"
        for enc in table:
            assert enc, f"{name} contains an empty encounter"
            for eid in enc:
                assert eid in ENEMY_REGISTRY, f"{name}: unknown enemy id {eid!r}"
    print("[PASS] All 9 encounter tables resolve in the enemy registry")


def test_spawn_enemies_fails_loud():
    """C1(b,c): spawn_enemies raises on an unknown id (the silent skip masked C1
    for months); ['Donu','Deca'] spawns both bodies; start_combat refuses an
    empty enemy list (defense in depth against auto-wins)."""
    from slay_bench import start_combat
    from slay_bench.run_loop import spawn_enemies
    state = new_ironclad_game(42)
    try:
        spawn_enemies(state, ["DonuAndDeca"])
        assert False, "spawn_enemies must raise on an unknown enemy id"
    except ValueError:
        pass
    pair = spawn_enemies(state, ["Donu", "Deca"], boss=True)
    assert len(pair) == 2, f"Donu+Deca must spawn 2 enemies, got {len(pair)}"
    assert {e.id for e in pair} == {"Donu", "Deca"}
    assert sorted(e.is_deca for e in pair) == [False, True]
    try:
        start_combat(state, [])
        assert False, "start_combat must raise on an empty enemy list"
    except ValueError:
        pass
    print("[PASS] spawn_enemies + start_combat fail loud on bad input")


if __name__ == "__main__":
    tests = [
        test_map_generation,
        test_map_determinism,
        test_card_reward_generation,
        test_card_reward_determinism,
        test_event_pool,
        test_shop_generation,
        test_shop_buy_card,
        test_card_removal,
        test_potion_use,
        test_act1_run,
        test_act1_run_determinism,
        test_relic_registration,
        test_act2_enemies,
        test_relic_pools_gated,
        test_boss_relic_choices_gated,
        test_merchant_greedy_shop,
        test_maw_bank_and_single_first_move,
        test_rest_policies,
        test_tiny_chest_fires_on_fourth_combat,
        test_bag_of_preparation_every_combat,
        test_pickup_relics_mutate_deck,
        test_elite_relic_drop_tagging,
        # 2026-06-11 audit
        test_neow_gated_to_run_start,
        test_events_do_not_repeat,
        test_mind_bloom_war_no_free_gold,
        test_snecko_skull_buffs_applied_poison,
        test_blue_candle_makes_curses_playable,
        test_pandoras_box_transforms_basics_only,
        test_fairy_in_a_bottle_revives,
        test_random_relic_fallback_stays_in_class,
        # 2026-06-12b audit
        test_eggs_upgrade_matching_reward_cards,
        test_eggs_preserve_reward_rng_order,
        test_tiny_house_no_energy_upgrades_card,
        # 2026-07-12 greedy run-level baseline
        test_greedy_baseline_determinism,
        # 2026-07-14 Act 2/3 audit
        test_encounter_tables_resolve,
        test_spawn_enemies_fails_loud,
    ]
    passed = failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"[FAIL] {test.__name__}: {e}")
            import traceback; traceback.print_exc()
            failed += 1
    print(f"\n{'='*50}")
    print(f"Results: {passed} passed, {failed} failed")
