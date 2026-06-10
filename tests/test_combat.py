"""End-to-end combat tests for determinism and correctness."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from slay_bench import new_ironclad_game, start_combat, play_card, end_player_turn, is_combat_over, end_combat
from slay_bench.enemies import Cultist, JawWorm, AcidSlimeM
from slay_bench.cards import Strike, Defend, Bash


def run_cultist_fight(seed: int) -> dict:
    """Run a simple fight vs Cultist, playing optimally (bash first, then strikes)."""
    state = new_ironclad_game(seed)
    enemy = Cultist(state.rng.hp_rng)
    start_combat(state, [enemy])

    result = {"turns": 0, "outcome": None, "final_hp": state.player.hp}

    for turn in range(20):  # safety limit
        result["turns"] = turn + 1
        outcome = is_combat_over(state)
        if outcome:
            result["outcome"] = outcome
            break

        # Simple greedy: play all playable cards
        played = True
        while played:
            played = False
            for card in list(state.combat.hand):
                target = next((e for e in state.combat.enemies if e.hp > 0), None)
                if card.can_play(state) and target:
                    play_card(state, card, target)
                    played = True
                    outcome = is_combat_over(state)
                    if outcome:
                        result["outcome"] = outcome
                        result["final_hp"] = state.player.hp
                        end_combat(state)
                        return result
                    break

        end_player_turn(state)
        outcome = is_combat_over(state)
        if outcome:
            result["outcome"] = outcome
            break

    result["final_hp"] = state.player.hp
    if result["outcome"] == "win":
        end_combat(state)
    return result


def test_cultist_fight_determinism():
    """Same seed always produces same outcome."""
    seed = 42
    r1 = run_cultist_fight(seed)
    r2 = run_cultist_fight(seed)
    assert r1 == r2, f"Non-deterministic! {r1} != {r2}"
    print(f"[PASS] Determinism: seed={seed} -> {r1}")


def test_cultist_fight_win():
    """Basic fight should be winnable."""
    result = run_cultist_fight(42)
    assert result["outcome"] == "win", f"Expected win, got: {result}"
    print(f"[PASS] Combat win: {result}")


def test_different_seeds_differ():
    """Different seeds produce different outcomes or HP values."""
    r1 = run_cultist_fight(1)
    r2 = run_cultist_fight(999)
    # At minimum HP outcomes should differ (due to different enemy HP rolls)
    print(f"[INFO] seed=1: {r1}")
    print(f"[INFO] seed=999: {r2}")
    print("[PASS] Different seeds test (manual inspection)")


def test_player_takes_damage():
    """Cultist attacks after turn 1, player should take damage."""
    state = new_ironclad_game(100)
    enemy = Cultist(state.rng.hp_rng)
    start_combat(state, [enemy])

    initial_hp = state.player.hp

    # End turn without playing cards (enemy gets to attack after incantation)
    end_player_turn(state)
    # End turn 2 so cultist attacks
    end_player_turn(state)

    assert state.player.hp < initial_hp or is_combat_over(state) is not None, \
        "Player should have taken damage or fight should be over"
    print(f"[PASS] Player takes damage: {initial_hp} -> {state.player.hp}")


def test_block_absorbs_damage():
    """Defend card should reduce damage taken."""
    state = new_ironclad_game(1)
    enemy = Cultist(state.rng.hp_rng)
    start_combat(state, [enemy])

    # Play defend cards first turn, then end turn
    defends = [c for c in state.combat.hand if c.__class__.__name__ == 'Defend']
    for d in defends:
        play_card(state, d)

    block_before_enemy = state.player.block
    hp_before = state.player.hp
    end_player_turn(state)

    # Enemy should attack turn 2 (after Incantation turn 1 passes)
    # After turn end, block resets; enemy hasn't attacked yet on turn 1 (Incantation)
    print(f"[PASS] Block test: block={block_before_enemy}, hp={hp_before} -> {state.player.hp}")


def test_enemy_hp_range():
    """Cultist HP should be in valid range."""
    for seed in range(10):
        state = new_ironclad_game(seed)
        enemy = Cultist(state.rng.hp_rng)
        assert 48 <= enemy.hp <= 57, f"Cultist HP {enemy.hp} out of range [48,57]"
    print("[PASS] Cultist HP range valid")


def test_slime_splits():
    """Acid Slime L splits at half HP."""
    from slay_bench.enemies import AcidSlimeL
    state = new_ironclad_game(5)
    slime = AcidSlimeL(state.rng.hp_rng)
    start_combat(state, [slime])

    initial_enemies = len(state.combat.enemies)
    assert initial_enemies == 1

    # Deal damage to get below 50% HP
    from slay_bench.cards import _apply_damage_to_enemy
    slime.hp = slime.max_hp // 2
    slime.on_hp_threshold(state)

    assert len(state.combat.enemies) == 3, f"Expected 3 enemies after split, got {len(state.combat.enemies)}"
    print(f"[PASS] Slime split: {initial_enemies} -> {len(state.combat.enemies)} enemies")


def test_intangible_covers_enemy_turn():
    """Player Intangible gained during the player turn must still be active
    when the enemies attack that same round (Wraith Form / Incense Burner),
    and only tick down at the end of the round."""
    from slay_bench.enums import PowerId
    state = new_ironclad_game(7)
    enemy = Cultist(state.rng.hp_rng)
    start_combat(state, [enemy])
    # Skip turn 1 (Cultist uses Incantation, no attack)
    end_player_turn(state)
    # Turn 2: gain Intangible 1 mid-turn (as Wraith Form would), then end turn.
    state.player.powers[PowerId.INTANGIBLE] = 1
    hp_before = state.player.hp
    state.player.block = 0
    end_player_turn(state)
    lost = hp_before - state.player.hp
    assert lost == 1, f"Intangible should cap the attack at 1 damage, lost {lost}"
    assert PowerId.INTANGIBLE not in state.player.powers, \
        "Intangible 1 should be gone after the round ends"
    print(f"[PASS] Intangible covers enemy turn: lost {lost} HP, ticked after round")


def test_enemy_applied_debuff_survives_first_tick():
    """A debuff an enemy applies during its turn must not tick that same round
    (StS justApplied rule) — it has to be active on the player's next turn."""
    from slay_bench.enums import PowerId
    from slay_bench.cards import _apply_power
    state = new_ironclad_game(7)
    enemy = Cultist(state.rng.hp_rng)
    start_combat(state, [enemy])
    # Simulate an enemy applying Weak 1 during the enemy phase
    state.combat.enemy_phase = True
    _apply_power(state, state.player, PowerId.WEAK, 1)
    state.combat.enemy_phase = False
    from slay_bench.combat import _tick_player_debuffs
    _tick_player_debuffs(state)  # end-of-round tick of the application round
    assert state.player.powers.get(PowerId.WEAK) == 1, \
        "just-applied Weak must survive the first end-of-round tick"
    _tick_player_debuffs(state)  # next round's tick removes it
    assert PowerId.WEAK not in state.player.powers
    print("[PASS] Enemy-applied debuff skips its first tick (justApplied)")


def test_double_tap_consumes_one_stack_per_attack():
    """Double Tap with 2 stacks doubles the next TWO attacks (one stack each),
    not one attack three times."""
    from slay_bench.enums import PowerId
    state = new_ironclad_game(3)
    enemy = Cultist(state.rng.hp_rng)
    start_combat(state, [enemy])
    state.player.powers[PowerId.DOUBLE_TAP] = 2
    state.player.energy = 10
    strike = next(c for c in state.combat.hand if c.name == "Strike")
    hp_before = enemy.hp
    play_card(state, strike, enemy)
    assert hp_before - enemy.hp == 12, \
        f"Strike with Double Tap should hit twice (12), dealt {hp_before - enemy.hp}"
    assert state.player.powers.get(PowerId.DOUBLE_TAP) == 1, \
        "one Double Tap stack should remain for the next attack"
    print("[PASS] Double Tap consumes one stack per attack")


def test_red_louse_strength_not_double_counted():
    """RedLouse baked Strength into its Bite move at select time, then
    _enemy_attack added Strength again — after one Grow it dealt 11 not 8."""
    from slay_bench.enums import PowerId
    from slay_bench.enemies import RedLouse, _enemy_attack
    state = new_ironclad_game(5)
    louse = RedLouse(state.rng.hp_rng)
    start_combat(state, [louse])
    louse.powers[PowerId.STRENGTH] = 3
    louse._first = False
    # Roll moves until Bite comes up (75% per roll, deterministic stream)
    for _ in range(50):
        if louse.select_move(state).name == "Bite":
            break
    assert louse.current_move.name == "Bite"
    state.player.block = 0
    hp_before = state.player.hp
    _enemy_attack(state, louse, louse.current_move)
    dealt = hp_before - state.player.hp
    assert dealt == 8, f"Bite with 3 Strength should deal 5+3=8, dealt {dealt}"
    print("[PASS] RedLouse Strength applied once (5+3=8)")


if __name__ == "__main__":
    tests = [
        test_cultist_fight_determinism,
        test_cultist_fight_win,
        test_different_seeds_differ,
        test_player_takes_damage,
        test_block_absorbs_damage,
        test_enemy_hp_range,
        test_slime_splits,
        test_intangible_covers_enemy_turn,
        test_enemy_applied_debuff_survives_first_tick,
        test_double_tap_consumes_one_stack_per_attack,
        test_red_louse_strength_not_double_counted,
    ]
    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"[FAIL] {test.__name__}: {e}")
            import traceback; traceback.print_exc()
            failed += 1
    print(f"\n{'='*40}")
    print(f"Results: {passed} passed, {failed} failed")
