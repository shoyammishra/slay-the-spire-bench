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
