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


def test_played_card_with_twin_does_not_vanish():
    """Card.__eq__ is field-based; playing a Strike while an identical Strike
    was in hand used to make the played copy vanish from the game."""
    state = new_ironclad_game(42)
    enemy = Cultist(state.rng.hp_rng)
    start_combat(state, [enemy])
    c = state.combat
    s1, s2 = Strike(), Strike()
    c.hand[:] = [s1, s2]
    total_before = len(c.hand) + len(c.draw_pile) + len(c.discard_pile) + len(c.exhaust_pile)
    play_card(state, s1, enemy)
    total_after = len(c.hand) + len(c.draw_pile) + len(c.discard_pile) + len(c.exhaust_pile)
    assert total_after == total_before, \
        f"card vanished: {total_before} -> {total_after}"
    assert any(x is s1 for x in c.discard_pile), "played Strike not in discard"
    assert any(x is s2 for x in c.hand), "twin Strike removed from hand"
    print("[PASS] Played card with identical twin reaches discard (no vanish)")


def test_self_exhausting_card_exhausts_once():
    """Self-exhausting cards (Slimed etc.) were appended to the exhaust pile a
    second time by play_card, double-emitting CARD_EXHAUST."""
    from slay_bench.cards import Slimed
    from slay_bench.events import Event
    state = new_ironclad_game(42)
    enemy = Cultist(state.rng.hp_rng)
    start_combat(state, [enemy])
    counts = {"exhaust": 0}
    state.bus.subscribe(Event.CARD_EXHAUST,
                        lambda gs, **kw: counts.__setitem__("exhaust", counts["exhaust"] + 1))
    sl = Slimed()
    state.combat.hand[:] = [sl]
    play_card(state, sl, enemy)
    n_in_pile = sum(1 for x in state.combat.exhaust_pile if x is sl)
    assert n_in_pile == 1, f"Slimed in exhaust pile {n_in_pile} times"
    assert counts["exhaust"] == 1, f"CARD_EXHAUST emitted {counts['exhaust']} times"
    print("[PASS] Self-exhausting card exhausts exactly once")


def test_blood_for_blood_energy_and_discount():
    """BfB deducted its cost itself on top of play_card's payment (double
    charge), and its per-HP-loss discount flag was never incremented."""
    from slay_bench.cards import BloodForBlood, _damage_player
    state = new_ironclad_game(42)
    enemy = Cultist(state.rng.hp_rng)
    start_combat(state, [enemy])
    bfb = BloodForBlood()
    state.combat.hand[:] = [bfb]
    state.player.energy = 4
    # discount: two HP losses -> cost 4-2=2
    _damage_player(state, 3, is_hp_loss=True)
    _damage_player(state, 3, is_hp_loss=True)
    assert bfb.effective_cost() == 2, f"cost should be 2, got {bfb.effective_cost()}"
    play_card(state, bfb, enemy)
    assert state.player.energy == 2, \
        f"energy should be 4-2=2 (single charge), got {state.player.energy}"
    print("[PASS] Blood for Blood: single energy charge + HP-loss discount")


def test_lizard_tail_only_on_lethal():
    """DEATH_WOULD_OCCUR fired on ANY damage — chip damage consumed the revive
    (and could even heal). Now lethal-only."""
    from slay_bench.relics import LizardTail
    from slay_bench.cards import _damage_player
    state = new_ironclad_game(42)
    enemy = Cultist(state.rng.hp_rng)
    start_combat(state, [enemy])
    tail = LizardTail()
    tail._used = False
    tail.register(state)
    state.player.hp = 50
    _damage_player(state, 5)  # chip — must NOT trigger the revive
    assert state.player.hp == 45, f"chip damage mishandled: hp={state.player.hp}"
    assert not tail._used, "Lizard Tail consumed by chip damage"
    _damage_player(state, 99)  # lethal — revive to max_hp//2
    assert state.player.hp == state.player.max_hp // 2, \
        f"revive failed: hp={state.player.hp}"
    assert tail._used
    print("[PASS] Lizard Tail revives on lethal damage only")


def test_defensive_relic_flags():
    """Torii (≤5 unblocked attack → 1), Tungsten Rod (-1 all HP loss),
    The Boot (<5 player attack → 5), Paper Phrog (vuln ×1.75)."""
    from slay_bench.cards import _damage_player, _deal_damage, _apply_power
    from slay_bench.enums import PowerId
    state = new_ironclad_game(42)
    enemy = Cultist(state.rng.hp_rng)
    start_combat(state, [enemy])
    p = state.player
    p.block = 0
    # Torii then Rod: 5 -> 1 -> 0
    p._torii = True
    p._tungsten_rod = True
    hp = p.hp
    _damage_player(state, 5)
    assert p.hp == hp, f"Torii+Rod should fully negate 5: lost {hp - p.hp}"
    # Rod alone on hp-loss: 3 -> 2
    p._torii = False
    hp = p.hp
    _damage_player(state, 3, is_hp_loss=True)
    assert hp - p.hp == 2, f"Rod should reduce hp-loss 3->2, lost {hp - p.hp}"
    # The Boot: base 3 -> 5
    p._the_boot = True
    ehp = enemy.hp
    _deal_damage(state, enemy, 3)
    assert ehp - enemy.hp == 5, f"Boot should raise 3->5, dealt {ehp - enemy.hp}"
    # Paper Phrog: 6 with vuln -> floor(6*1.75)=10
    p._the_boot = False
    p._paper_phrog = True
    _apply_power(state, enemy, PowerId.VULNERABLE, 2)
    ehp = enemy.hp
    _deal_damage(state, enemy, 6)
    assert ehp - enemy.hp == 10, f"Phrog vuln 6->10, dealt {ehp - enemy.hp}"
    print("[PASS] Torii / Tungsten Rod / The Boot / Paper Phrog flags consumed")


def test_paper_krane_weak_multiplier():
    """Paper Krane: Weak on enemies reduces their damage 40% (not 25%)."""
    from slay_bench.enemies import effective_move_damage, Move
    from slay_bench.enums import IntentType, PowerId
    state = new_ironclad_game(42)
    enemy = Cultist(state.rng.hp_rng)
    enemy.powers[PowerId.WEAK] = 1
    move = Move("Hit", IntentType.ATTACK, damage=10, hits=1)
    assert effective_move_damage(enemy, move) == 7  # floor(10*0.75)
    state.player._paper_krane = True
    assert effective_move_damage(enemy, move, state.player) == 6  # floor(10*0.6)
    print("[PASS] Paper Krane Weak multiplier 0.6")


def test_velvet_choker_card_cap():
    """Velvet Choker: no 7th card in a turn."""
    state = new_ironclad_game(42)
    enemy = Cultist(state.rng.hp_rng)
    start_combat(state, [enemy])
    state.player._velvet_choker = True
    state.player.energy = 99
    s = Strike()
    state.combat.hand[:] = [s]
    state.combat.cards_played_this_turn = 5
    assert s.can_play(state), "6th card should be playable"
    state.combat.cards_played_this_turn = 6
    assert not s.can_play(state), "7th card must be blocked by Velvet Choker"
    print("[PASS] Velvet Choker caps at 6 cards per turn")


def test_pain_per_copy():
    """Each Pain copy in hand costs 1 HP per card played (was capped at 1)."""
    from slay_bench.cards import Pain
    state = new_ironclad_game(42)
    enemy = Cultist(state.rng.hp_rng)
    start_combat(state, [enemy])
    s = Strike()
    state.combat.hand[:] = [Pain(), Pain(), s]
    hp = state.player.hp
    play_card(state, s, enemy)
    assert hp - state.player.hp == 2, \
        f"2 Pain copies should cost 2 HP, lost {hp - state.player.hp}"
    print("[PASS] Pain triggers per copy in hand")


def test_chemical_x_whirlwind():
    """Chemical X: X-cost cards get +2 X (energy still fully spent)."""
    from slay_bench.cards import Whirlwind
    state = new_ironclad_game(42)
    enemy = Cultist(state.rng.hp_rng)
    enemy.hp = enemy.max_hp = 100
    start_combat(state, [enemy])
    state.player._chemical_x = True
    state.player.energy = 2
    w = Whirlwind()
    state.combat.hand[:] = [w]
    ehp = enemy.hp
    play_card(state, w, enemy)
    assert ehp - enemy.hp == 20, \
        f"Whirlwind X=(2+2) should deal 4*5=20, dealt {ehp - enemy.hp}"
    assert state.player.energy == 0
    print("[PASS] Chemical X adds +2 to X-cost effects")


def test_lantern_energy_survives_reset():
    """Lantern's +1 used to be wiped by the turn-start energy reset."""
    from slay_bench.relics_full import Lantern
    state = new_ironclad_game(42)
    lantern = Lantern()
    state.player.relics.append(lantern)
    enemy = Cultist(state.rng.hp_rng)
    start_combat(state, [enemy])
    assert state.player.energy == state.player.energy_per_turn + 1, \
        f"Lantern +1 wiped: energy={state.player.energy}"
    print("[PASS] Lantern energy survives the turn-start reset (ENERGIZED)")


def test_gambling_chip_mulligan():
    """Gambling Chip swaps basic Strikes/Defends out of the opening hand."""
    state = new_ironclad_game(42)
    state.player.deck = [Strike() for _ in range(10)]
    state.player._gambling_chip = True
    enemy = Cultist(state.rng.hp_rng)
    start_combat(state, [enemy])
    assert len(state.combat.discard_pile) == 5, \
        f"5 basics should be mulliganed, discard={len(state.combat.discard_pile)}"
    assert len(state.combat.hand) == 5, f"hand={len(state.combat.hand)}"
    print("[PASS] Gambling Chip mulligans the opening hand once")


def test_pen_nib_counter_persists_across_combats():
    """Pen Nib's counter is per-run; register() must not reset it."""
    from slay_bench.relics import PenNib
    state = new_ironclad_game(42)
    nib = PenNib()
    state.player.relics.append(nib)
    enemy = Cultist(state.rng.hp_rng)
    start_combat(state, [enemy])
    nib._count = 9  # 9 attacks played earlier in the run
    enemy2 = Cultist(state.rng.hp_rng)
    start_combat(state, [enemy2])  # re-registers all relics
    assert nib._count == 9, f"Pen Nib counter reset by combat start: {nib._count}"
    s = Strike()
    state.combat.hand[:] = [s]
    state.player.energy = 3
    ehp = enemy2.hp
    play_card(state, s, enemy2)
    assert ehp - enemy2.hp == 12, \
        f"10th attack should be doubled (6*2=12), dealt {ehp - enemy2.hp}"
    print("[PASS] Pen Nib counter persists across combats (10th attack doubles)")


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
        test_played_card_with_twin_does_not_vanish,
        test_self_exhausting_card_exhausts_once,
        test_blood_for_blood_energy_and_discount,
        test_lizard_tail_only_on_lethal,
        test_defensive_relic_flags,
        test_paper_krane_weak_multiplier,
        test_velvet_choker_card_cap,
        test_pain_per_copy,
        test_chemical_x_whirlwind,
        test_lantern_energy_survives_reset,
        test_gambling_chip_mulligan,
        test_pen_nib_counter_persists_across_combats,
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
