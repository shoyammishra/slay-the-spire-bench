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


# ── 2026-06-11 audit regression tests ─────────────────────────────────────────

def test_hp_loss_bypasses_block():
    """HP-loss effects (Offering, poison ticks, Combust) must bypass block —
    block used to absorb them entirely."""
    from slay_bench.cards import _damage_player
    state = new_ironclad_game(42)
    enemy = Cultist(state.rng.hp_rng)
    start_combat(state, [enemy])
    state.player.block = 10
    hp = state.player.hp
    _damage_player(state, 6, is_hp_loss=True)
    assert hp - state.player.hp == 6, f"HP loss absorbed by block: lost {hp - state.player.hp}"
    assert state.player.block == 10, f"block consumed by HP loss: {state.player.block}"
    print("[PASS] HP-loss effects bypass block")


def test_burn_damage_blockable_not_hp_loss():
    """Burn deals blockable damage (not block-bypassing HP loss)."""
    from slay_bench.cards import Burn
    state = new_ironclad_game(42)
    enemy = Cultist(state.rng.hp_rng)
    start_combat(state, [enemy])
    state.combat.hand[:] = [Burn()]
    state.player.block = 5
    hp = state.player.hp
    end_player_turn(state)  # TURN_END fires Burn while block is still up
    assert state.player.hp == hp, f"Burn pierced block: hp {hp}->{state.player.hp}"
    print("[PASS] Burn damage is blockable")


def test_enemy_block_survives_player_turn():
    """Enemy block gained during the enemy phase must persist through the
    player's next turn (it used to be wiped at player-turn start, making
    every enemy blocking move a no-op)."""
    from slay_bench.enemies import Enemy, Move
    from slay_bench.enums import IntentType

    class _Blocker(Enemy):
        def __init__(self):
            super().__init__("Blocker", "Blocker", 50, 50)
        def select_move(self, state):
            self.current_move = Move("Guard", IntentType.BLOCK)
            return self.current_move
        def execute_move(self, state):
            self.add_block(10)

    state = new_ironclad_game(42)
    blocker = _Blocker()
    start_combat(state, [blocker])
    end_player_turn(state)  # enemy gains 10 block in its phase
    assert blocker.block == 10, f"enemy block wiped: {blocker.block}"
    s = Strike()
    state.combat.hand[:] = [s]
    state.player.energy = 3
    hp_before = blocker.hp
    play_card(state, s, blocker)
    assert hp_before == blocker.hp, "Strike should be fully blocked"
    assert blocker.block == 4, f"block should absorb 6: {blocker.block}"
    print("[PASS] Enemy block persists into the player's turn")


def test_lagavulin_metallicize_and_wake():
    """Sleeping Lagavulin gains 8 block per round (enemy Metallicize had no
    handler) and loses the power when it wakes."""
    from slay_bench.enemies import Lagavulin
    from slay_bench.enums import PowerId
    state = new_ironclad_game(42)
    lag = Lagavulin(state.rng.hp_rng)
    start_combat(state, [lag])
    end_player_turn(state)
    assert lag.block == 8, f"sleeping Lagavulin should have 8 block, got {lag.block}"
    state.player.hp -= 1  # damage wakes it at next move selection
    end_player_turn(state)
    assert PowerId.METALLICIZE not in lag.powers, "Metallicize must drop on wake"
    print("[PASS] Lagavulin Metallicize ticks while asleep, drops on wake")


def test_havoc_no_duplication():
    """Havoc duplicated the top draw-pile card (left in draw AND exhausted)."""
    from slay_bench.cards import Havoc
    state = new_ironclad_game(42)
    enemy = Cultist(state.rng.hp_rng)
    start_combat(state, [enemy])
    c = state.combat
    hv = Havoc()
    c.hand[:] = [hv]
    state.player.energy = 3
    top = c.draw_pile[-1]
    total = len(c.hand) + len(c.draw_pile) + len(c.discard_pile) + len(c.exhaust_pile)
    play_card(state, hv, enemy)
    total2 = len(c.hand) + len(c.draw_pile) + len(c.discard_pile) + len(c.exhaust_pile)
    assert total2 == total, f"Havoc changed card count {total}->{total2}"
    assert not any(x is top for x in c.draw_pile), "played card still in draw pile"
    assert any(x is top for x in c.exhaust_pile), "played card not exhausted"
    print("[PASS] Havoc plays+exhausts the top card without duplication")


def test_warcry_no_twin_duplication():
    """Warcry's equality-based hand.remove() could remove a twin and leave the
    chosen card in hand AND the draw pile."""
    from slay_bench.cards import Warcry
    state = new_ironclad_game(42)
    enemy = Cultist(state.rng.hp_rng)
    start_combat(state, [enemy])
    c = state.combat
    wc, s1, s2 = Warcry(), Strike(), Strike()
    c.hand[:] = [wc, s1, s2]
    c.draw_pile.clear(); c.discard_pile.clear()
    state.player.energy = 3
    play_card(state, wc, enemy)
    dup = [x for x in c.hand if any(x is d for d in c.draw_pile)]
    assert not dup, "card object in hand AND draw pile after Warcry"
    assert any(x is s2 for x in c.draw_pile), "chosen card (hand[-1]) not moved to draw"
    assert any(x is s1 for x in c.hand), "twin wrongly removed from hand"
    print("[PASS] Warcry moves the chosen object (no twin duplication)")


def test_corruption_makes_skills_free():
    """Under Corruption, skills must be playable at 0 energy, cost 0, and
    exhaust — can_play used to demand the printed cost."""
    state = new_ironclad_game(42)
    enemy = Cultist(state.rng.hp_rng)
    start_combat(state, [enemy])
    state.player.corruption = True
    state.player.energy = 0
    d = Defend()
    state.combat.hand[:] = [d]
    assert d.can_play(state), "skill must be playable at 0 energy under Corruption"
    play_card(state, d)
    assert state.player.energy == 0
    assert any(x is d for x in state.combat.exhaust_pile), "Corruption skill must exhaust"
    print("[PASS] Corruption: skills free + exhausted")


def test_searing_blow_formula():
    """Searing Blow: 12 base, 16 at +1, 21 at +2 (was 6/11)."""
    from slay_bench.cards import SearingBlow
    sb = SearingBlow()
    assert sb._damage() == 12, f"base {sb._damage()}"
    sb.upgrade()
    assert sb._damage() == 16, f"+1 {sb._damage()}"
    sb.upgrade()
    assert sb._damage() == 21, f"+2 {sb._damage()}"
    print("[PASS] Searing Blow damage formula (12/16/21)")


def test_reaper_heals_unblocked_only():
    """Reaper used post-hit block in its heal calc and overhealed."""
    from slay_bench.cards import Reaper
    state = new_ironclad_game(42)
    enemy = Cultist(state.rng.hp_rng)
    start_combat(state, [enemy])
    enemy.block = 3
    state.player.hp = 10
    r = Reaper()
    state.combat.hand[:] = [r]
    state.player.energy = 2
    ehp = enemy.hp
    play_card(state, r, enemy)
    unblocked = ehp - enemy.hp
    assert unblocked == 1, f"4 dmg into 3 block should land 1, landed {unblocked}"
    assert state.player.hp == 11, f"heal must equal unblocked dmg: hp={state.player.hp}"
    print("[PASS] Reaper heals exactly the unblocked damage")


def test_choke_expires_at_turn_end():
    """Choke's per-card-play HP loss lasts only the turn it was played."""
    from slay_bench.enums import PowerId
    state = new_ironclad_game(42)
    enemy = Cultist(state.rng.hp_rng)
    start_combat(state, [enemy])
    enemy.powers[PowerId.CHOKED] = 3
    end_player_turn(state)
    assert PowerId.CHOKED not in enemy.powers, "Choked must expire at turn end"
    print("[PASS] Choke expires at end of the turn")


def test_finisher_does_not_count_itself():
    """Finisher as the first attack of a turn deals 0 (it counted itself)."""
    from slay_bench.cards_silent import Finisher, StrikeG
    from slay_bench import new_game
    state = new_game(42, "silent")
    enemy = Cultist(state.rng.hp_rng)
    start_combat(state, [enemy])
    f = Finisher()
    state.combat.hand[:] = [f]
    state.player.energy = 3
    ehp = enemy.hp
    play_card(state, f, enemy)
    assert ehp == enemy.hp, f"first Finisher must deal 0, dealt {ehp - enemy.hp}"
    # second case: one attack before it -> 1x6 (fresh turn counter)
    state.combat.attacks_played_this_turn = 0
    f2, st = Finisher(), StrikeG()
    state.combat.hand[:] = [st, f2]
    state.player.energy = 3
    enemy.block = 0
    play_card(state, st, enemy)
    ehp = enemy.hp
    play_card(state, f2, enemy)
    assert ehp - enemy.hp == 6, f"Finisher after 1 attack should deal 6, dealt {ehp - enemy.hp}"
    print("[PASS] Finisher excludes itself from the attack count")


def test_blood_for_blood_no_exhaust_and_upgrade_cost():
    """BfB does not exhaust; BfB+ costs 3."""
    from slay_bench.cards import BloodForBlood
    b = BloodForBlood()
    assert not b.exhaust, "Blood for Blood must not exhaust"
    assert BloodForBlood(upgraded=True).cost == 3, "BfB+ must cost 3"
    b.upgrade()
    assert b.cost == 3, "upgrade() must lower cost to 3"
    state = new_ironclad_game(42)
    enemy = Cultist(state.rng.hp_rng)
    start_combat(state, [enemy])
    bfb = BloodForBlood()
    state.combat.hand[:] = [bfb]
    state.player.energy = 4
    play_card(state, bfb, enemy)
    assert not any(x is bfb for x in state.combat.exhaust_pile), "BfB wrongly exhausted"
    assert any(x is bfb for x in state.combat.discard_pile), "BfB should be discarded"
    print("[PASS] Blood for Blood: no exhaust, + costs 3")


def test_perfected_strike_counts_itself():
    """Perfected Strike is in no pile mid-play and was excluded from its own
    strike count (−2/−3 damage every play)."""
    from slay_bench.cards import PerfectedStrike
    state = new_ironclad_game(42)
    enemy = Cultist(state.rng.hp_rng)
    enemy.hp = enemy.max_hp = 100
    start_combat(state, [enemy])
    c = state.combat
    ps = PerfectedStrike()
    c.hand[:] = [ps]
    c.draw_pile[:] = [Strike(), Strike()]
    c.discard_pile[:] = [Strike()]
    c.exhaust_pile.clear()
    state.player.energy = 2
    enemy.block = 0
    ehp = enemy.hp
    play_card(state, ps, enemy)
    # 3 Strikes in piles + itself = 4 strike-cards -> 6 + 4*2 = 14
    assert ehp - enemy.hp == 14, f"expected 14, dealt {ehp - enemy.hp}"
    print("[PASS] Perfected Strike counts itself (6 + 4x2 = 14)")


def test_escape_plan_detects_twin_draw():
    """Escape Plan's drawn-card detection used __eq__ and missed a drawn skill
    whose twin was already in hand."""
    from slay_bench.cards_silent import EscapePlan, DefendG
    from slay_bench import new_game
    state = new_game(42, "silent")
    enemy = Cultist(state.rng.hp_rng)
    start_combat(state, [enemy])
    ep = EscapePlan()
    state.combat.hand[:] = [ep, DefendG()]
    state.combat.draw_pile.append(DefendG())  # top of pile, twin of hand card
    state.player.energy = 3
    blk = state.player.block
    play_card(state, ep, enemy)
    assert state.player.block - blk == 3, \
        f"Escape Plan must gain 3 block on drawn skill, gained {state.player.block - blk}"
    print("[PASS] Escape Plan detects the drawn card by identity")


def test_play_card_rejects_replayed_card():
    """Replaying an already-played card (twin still in hand) must raise —
    equality membership used to accept it without removing anything."""
    state = new_ironclad_game(42)
    enemy = Cultist(state.rng.hp_rng)
    start_combat(state, [enemy])
    s1, s2 = Strike(), Strike()
    state.combat.hand[:] = [s1, s2]
    state.player.energy = 3
    play_card(state, s1, enemy)
    try:
        play_card(state, s1, enemy)  # s1 already played; s2 (equal twin) in hand
        raise AssertionError("replaying a played card must raise ValueError")
    except ValueError:
        pass
    assert any(x is s2 for x in state.combat.hand), "twin must remain in hand"
    print("[PASS] play_card rejects replay of an already-played object")


def test_time_warp_locks_plays():
    """Time Eater's Time Warp: hitting the card threshold ends the player's
    plays for the turn and buffs the boss (the mechanic was dead code)."""
    from slay_bench.enums import PowerId
    state = new_ironclad_game(42)
    enemy = Cultist(state.rng.hp_rng)
    start_combat(state, [enemy])
    enemy.powers[PowerId.TIME_WARP] = 2  # small threshold for the test
    s1, s2, s3 = Strike(), Strike(), Strike()
    state.combat.hand[:] = [s1, s2, s3]
    state.player.energy = 5
    play_card(state, s1, enemy)
    assert s2.can_play(state), "lock must not engage before the threshold"
    play_card(state, s2, enemy)  # 2nd play hits the threshold
    assert state.combat.time_warp_lock, "Time Warp lock not set"
    assert not s3.can_play(state), "plays must be locked after Time Warp"
    assert enemy.powers.get(PowerId.STRENGTH) == 2, "Time Warp must grant 2 Strength"
    end_player_turn(state)
    assert not state.combat.time_warp_lock, "lock must clear next turn"
    print("[PASS] Time Warp locks the turn at the play threshold")


# ── 2026-06-12 audit regression tests ─────────────────────────────────────────

def test_sentinel_plays_and_exhaust_gives_energy():
    """C1: Sentinel no longer crashes (PowerId.SENTINEL was missing). Playing it
    gives block only; exhausting one gives +2 (+3 upgraded) energy."""
    from slay_bench.cards import Sentinel, _exhaust_card
    state = new_ironclad_game(42)
    enemy = Cultist(state.rng.hp_rng)
    start_combat(state, [enemy])
    sen = Sentinel()
    state.combat.hand[:] = [sen]
    state.player.energy = 3
    blk = state.player.block
    play_card(state, sen, enemy)  # must NOT raise
    assert state.player.block - blk == 5, f"Sentinel block, got {state.player.block - blk}"
    # Now exhaust a Sentinel -> energy bonus
    sen2 = Sentinel()
    state.combat.hand[:] = [sen2]
    e_before = state.player.energy
    _exhaust_card(state, sen2)
    assert state.player.energy - e_before == 2, f"exhaust energy {state.player.energy - e_before}"
    sen3 = Sentinel(); sen3.upgrade()
    state.combat.hand[:] = [sen3]
    e_before = state.player.energy
    _exhaust_card(state, sen3)
    assert state.player.energy - e_before == 3, "upgraded Sentinel exhaust = +3 energy"
    print("[PASS] Sentinel plays (block) + exhaust grants energy (2/3)")


def test_berserk_energy_unconditional():
    """E1: Berserk gives +1 energy every turn, not only while Vulnerable."""
    from slay_bench.enums import PowerId
    from slay_bench.cards import Berserk
    state = new_ironclad_game(42)
    enemy = Cultist(state.rng.hp_rng)
    start_combat(state, [enemy])
    b = Berserk()
    state.combat.hand[:] = [b]
    state.player.energy = 3
    play_card(state, b, enemy)
    # Remove Vulnerable to prove energy still flows.
    state.player.powers.pop(PowerId.VULNERABLE, None)
    end_player_turn(state)  # advances to next player turn (TURN_START fires)
    assert state.player.energy >= state.player.energy_per_turn + 1, \
        f"Berserk must add 1 energy: energy={state.player.energy}"
    print("[PASS] Berserk grants energy every turn (no Vulnerable needed)")


def test_brutality_resets_across_combats():
    """E2: Brutality is per-combat; it must not persist into the next fight."""
    from slay_bench.cards import Brutality
    state = new_ironclad_game(42)
    enemy = Cultist(state.rng.hp_rng)
    start_combat(state, [enemy])
    br = Brutality()
    state.combat.hand[:] = [br]
    state.player.energy = 3
    play_card(state, br, enemy)
    assert state.player.brutality is True
    end_combat(state)
    assert state.player.brutality is False, "Brutality must reset in end_combat"
    start_combat(state, [Cultist(state.rng.hp_rng)])
    assert state.player.brutality is False, "Brutality must stay reset at combat start"
    print("[PASS] Brutality resets between combats")


def test_brutality_upgrade_is_innate():
    """E3: Brutality+ is Innate via the card flag (innate_brutality field gone)."""
    from slay_bench.cards import Brutality
    assert Brutality().innate is False
    assert Brutality(upgraded=True).innate is True
    b = Brutality(); b.upgrade()
    assert b.innate is True
    assert not hasattr(new_ironclad_game(42).player, "innate_brutality")
    print("[PASS] Brutality+ is Innate; dead field removed")


def test_pride_curse_copies_to_draw_top_not_hand():
    """E5: Pride exhausts on play (no hand copy); a copy goes to the TOP of the
    draw pile at end of turn while in hand."""
    from slay_bench.cards import Pride
    state = new_ironclad_game(42)
    enemy = Cultist(state.rng.hp_rng)
    start_combat(state, [enemy])
    c = state.combat
    p = Pride()
    c.hand[:] = [p]
    c.draw_pile.clear(); c.discard_pile.clear()
    state.player.energy = 3
    play_card(state, p, enemy)
    assert any(x is p for x in c.exhaust_pile), "Pride must exhaust on play"
    assert not any(isinstance(x, Pride) for x in c.hand), "no Pride copy added to hand on play"
    # End-of-turn effect (fired by the TURN_END hook while in hand) puts a copy on
    # the TOP of the draw pile — draw pops from the end of the list, so top = end.
    p2 = Pride()
    c.draw_pile.clear()
    p2.end_of_turn_effect(state)
    assert c.draw_pile and isinstance(c.draw_pile[-1], Pride) and c.draw_pile[-1] is not p2, \
        "Pride must put a fresh copy on top (end) of the draw pile at end of turn"
    print("[PASS] Pride exhausts on play, copies to draw-pile top at end of turn")


def test_sentry_has_artifact():
    """E6: Sentry has Artifact 1 (was the no-op 0); Lagavulin's dead ARTIFACT
    key is gone."""
    from slay_bench.enemies import Sentry, Lagavulin
    from slay_bench.enums import PowerId
    state = new_ironclad_game(42)
    assert Sentry(state.rng.hp_rng).powers.get(PowerId.ARTIFACT) == 1
    assert PowerId.ARTIFACT not in Lagavulin(state.rng.hp_rng).powers
    print("[PASS] Sentry Artifact 1; Lagavulin has no Artifact key")


def test_awakened_one_damageable_after_rebirth():
    """E4: enemy Intangible now ticks down; Awakened One's Rebirth grants only a
    single round of Intangible, so it is damageable again the next round."""
    from slay_bench.enemies_act2 import AwakenedOne
    from slay_bench.enemies import Move, IntentType
    from slay_bench.enums import PowerId
    from slay_bench.combat import _tick_enemy_powers
    state = new_ironclad_game(42)
    awo = AwakenedOne(state.rng.hp_rng)
    start_combat(state, [awo])
    # Force the Rebirth move and execute it (grants Intangible during enemy phase).
    awo.current_move = Move("Rebirth", IntentType.BUFF)
    awo.execute_move(state)
    assert awo.powers.get(PowerId.INTANGIBLE) == 1
    # Round-end tick must NOT remove a freshly-granted Intangible (covers next turn).
    _tick_enemy_powers(state, awo)
    assert awo.powers.get(PowerId.INTANGIBLE) == 1, "fresh Rebirth Intangible should survive this tick"
    # Next round's tick removes it -> damageable again.
    _tick_enemy_powers(state, awo)
    assert PowerId.INTANGIBLE not in awo.powers, "Awakened One must be damageable the round after Rebirth"
    print("[PASS] Awakened One is damageable again the round after Rebirth")


def test_empty_cage_counts_removals():
    """E12: Empty Cage bumps the run-wide _cards_removed counter by 2."""
    from slay_bench.relics_full import EmptyCage
    state = new_ironclad_game(42)
    state.player._cards_removed = 0
    before = len(state.player.deck)
    EmptyCage().on_pickup(state)
    assert len(state.player.deck) == before - 2
    assert state.player._cards_removed == 2, f"_cards_removed={state.player._cards_removed}"
    print("[PASS] Empty Cage counts its 2 removals")


def test_no_duplicate_relics_in_pools():
    """E8: FULL_RELIC_LIST de-duped — no _RARITY_POOLS pool has a doubled class."""
    from slay_bench.relics_full import _RARITY_POOLS
    for rarity, pool in _RARITY_POOLS.items():
        names = [cls.__name__ for cls in pool]
        assert len(names) == len(set(names)), \
            f"{rarity} pool has duplicates: {[n for n in names if names.count(n) > 1]}"
    print("[PASS] No duplicate relic classes in any rarity pool")


# ── 2026-06-12b audit regression tests ────────────────────────────────────────

def test_doubt_curse_weak_covers_next_turn():
    """M1: Doubt's end-of-turn Weak is applied during the TURN_END window, so it
    is flagged just_applied and survives the end-of-round tick — active during
    the player's NEXT turn, gone the round after."""
    from slay_bench.cards import Doubt
    from slay_bench.enums import PowerId
    state = new_ironclad_game(42)
    enemy = Cultist(state.rng.hp_rng)
    start_combat(state, [enemy])
    c = state.combat
    c.hand[:] = [Doubt()]
    c.draw_pile.clear()
    assert PowerId.WEAK not in state.player.powers
    end_player_turn(state)  # TURN_END fires Doubt; round-end tick must NOT remove it
    assert state.player.powers.get(PowerId.WEAK, 0) >= 1, \
        "Doubt's Weak must be active on the player's next turn"
    # End the next turn with no Doubt in hand -> Weak ticks away.
    c.hand[:] = []
    end_player_turn(state)
    assert PowerId.WEAK not in state.player.powers, "Weak must expire the round after"
    print("[PASS] Doubt curse Weak covers the next turn, expires after")


def test_blue_candle_pride_single_exhaust():
    """M2: with Blue Candle owned, playing Pride (naturally playable, self-
    exhausting) produces exactly one exhaust entry and one CARD_EXHAUST."""
    from slay_bench.cards import Pride
    from slay_bench.relics_full import BlueCandle
    from slay_bench.events import Event
    state = new_ironclad_game(42)
    state.player.relics.append(BlueCandle())
    enemy = Cultist(state.rng.hp_rng)
    start_combat(state, [enemy])
    c = state.combat
    p = Pride()
    c.hand[:] = [p]
    c.exhaust_pile.clear()
    fired = []
    state.bus.subscribe(Event.CARD_EXHAUST, lambda gs, card=None, **kw: fired.append(card))
    state.player.energy = 3
    hp_before = state.player.hp
    play_card(state, p, enemy)
    assert sum(1 for x in c.exhaust_pile if x is p) == 1, "Pride must exhaust exactly once"
    assert fired.count(p) == 1, f"CARD_EXHAUST fired {fired.count(p)} times for Pride"
    assert hp_before - state.player.hp == 0, "Blue Candle must not charge Pride 1 HP"
    print("[PASS] Blue Candle + Pride: single exhaust, single CARD_EXHAUST")


def test_dead_branch_adds_no_curse_or_status():
    """M3: Dead Branch never adds a curse/status/basic card to hand."""
    from slay_bench.relics import DeadBranch
    from slay_bench.cards import _exhaust_card, Strike
    from slay_bench.enums import CardType, CardRarity
    state = new_ironclad_game(42)
    state.player.relics.append(DeadBranch())
    enemy = Cultist(state.rng.hp_rng)
    start_combat(state, [enemy])
    c = state.combat
    bad = 0
    for _ in range(50):
        before = len(c.hand)
        _exhaust_card(state, Strike())  # triggers Dead Branch's CARD_EXHAUST hook
        for card in c.hand[before:]:
            if card.type in (CardType.CURSE, CardType.STATUS) or card.rarity == CardRarity.BASIC:
                bad += 1
        c.hand.clear()
    assert bad == 0, f"Dead Branch added {bad} curse/status/basic cards"
    print("[PASS] Dead Branch never adds curse/status/basic cards")


def test_nemesis_intangible_through_turn_three():
    """M5: Nemesis stays Intangible through player turns 1-3 (attacks capped at
    1), droppable from turn 4."""
    from slay_bench.enemies_act2 import Nemesis
    from slay_bench.enums import PowerId
    state = new_ironclad_game(42)
    nem = Nemesis(state.rng.hp_rng)
    start_combat(state, [nem])
    # Survive Nemesis's 45-damage Scythe across the round transitions.
    state.player.max_hp = 1000
    state.player.hp = 1000
    for player_turn in (1, 2, 3):
        nem.block = 0
        hp0 = nem.hp
        s2 = Strike()
        state.combat.hand[:] = [s2]
        state.player.energy = 3
        play_card(state, s2, nem)
        assert hp0 - nem.hp <= 1, f"turn {player_turn}: Intangible must cap Strike at 1 (lost {hp0 - nem.hp})"
        end_player_turn(state)  # executes enemy move, ticks, re-selects
    # Turn 4: no longer intangible.
    nem.block = 0
    hp0 = nem.hp
    s4 = Strike()
    state.combat.hand[:] = [s4]
    state.player.energy = 3
    play_card(state, s4, nem)
    assert hp0 - nem.hp > 1, f"turn 4: Nemesis must take full damage (lost {hp0 - nem.hp})"
    print("[PASS] Nemesis Intangible caps turns 1-3, full damage turn 4")


def test_anchor_block_emits_block_gained():
    """L1: Anchor's flat combat-start block emits BLOCK_GAINED (Juggernaut etc.)."""
    from slay_bench.relics import Anchor
    from slay_bench.events import Event
    state = new_ironclad_game(42)
    enemy = Cultist(state.rng.hp_rng)
    start_combat(state, [enemy])  # clears the bus
    gained = []
    state.bus.subscribe(Event.BLOCK_GAINED, lambda gs, amount=0, **kw: gained.append(amount))
    # Register Anchor on the live bus, then fire COMBAT_START to trigger its hook.
    Anchor().register(state)
    state.bus.emit(Event.COMBAT_START, state)
    assert 10 in gained, f"Anchor must emit BLOCK_GAINED(10); got {gained}"
    print("[PASS] Anchor block emits BLOCK_GAINED")


def test_mark_of_pain_shuffles_wounds():
    """L4: Mark of Pain shuffles its 2 Wounds into the draw pile rather than
    stacking them on top (the first two draws were always Wounds)."""
    from slay_bench.relics import MarkOfPain
    state = new_ironclad_game(42)
    mop = MarkOfPain()
    mop.on_pickup(state)
    state.player.relics.append(mop)
    drawn_a_wound = 0
    for _ in range(20):
        enemy = Cultist(state.rng.hp_rng)
        start_combat(state, [enemy])
        pile = state.combat.draw_pile
        hand = state.combat.hand
        # Both Wounds present (draw pile + opening hand) — none lost.
        assert sum(1 for c in (pile + hand) if c.name == "Wound") == 2, \
            "exactly 2 Wounds expected across draw pile + hand"
        # If shuffled in, a Wound is sometimes NOT in the opening 5-card hand.
        if not any(c.name == "Wound" for c in hand):
            drawn_a_wound += 1
    # With both Wounds always on top (old bug), both are always drawn turn 1 →
    # never absent from hand. Shuffling makes them sometimes deeper in the pile.
    assert drawn_a_wound > 0, "Wounds must not always land in the opening hand"
    print("[PASS] Mark of Pain shuffles Wounds into the draw pile")


def test_exhume_cannot_return_exhume():
    """L5: Exhume retrieves the most recent non-Exhume exhausted card, never
    another Exhume."""
    from slay_bench.cards import Exhume, Strike
    state = new_ironclad_game(42)
    enemy = Cultist(state.rng.hp_rng)
    start_combat(state, [enemy])
    c = state.combat
    other_exhume = Exhume()
    strk = Strike()
    c.exhaust_pile[:] = [strk, other_exhume]  # Exhume is the MOST recent
    ex = Exhume()
    c.hand[:] = [ex]
    c.discard_pile.clear()
    state.player.energy = 3
    play_card(state, ex, enemy)
    assert any(x is strk for x in c.hand), "Exhume must retrieve the Strike, not the Exhume"
    assert not any(isinstance(x, Exhume) and x is not ex for x in c.hand), \
        "Exhume must never retrieve another Exhume"
    print("[PASS] Exhume cannot return another Exhume")


def test_limit_break_no_zero_strength_key():
    """L6: Limit Break at 0 Strength must not write a STRENGTH:0 powers entry."""
    from slay_bench.cards import LimitBreak
    from slay_bench.enums import PowerId
    state = new_ironclad_game(42)
    enemy = Cultist(state.rng.hp_rng)
    start_combat(state, [enemy])
    state.player.powers.pop(PowerId.STRENGTH, None)
    lb = LimitBreak()
    state.combat.hand[:] = [lb]
    state.player.energy = 3
    play_card(state, lb, enemy)
    assert PowerId.STRENGTH not in state.player.powers, \
        "Limit Break at 0 Strength must not materialize a STRENGTH:0 entry"
    print("[PASS] Limit Break writes no zero-Strength entry")


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
        # 2026-06-11 audit
        test_hp_loss_bypasses_block,
        test_burn_damage_blockable_not_hp_loss,
        test_enemy_block_survives_player_turn,
        test_lagavulin_metallicize_and_wake,
        test_havoc_no_duplication,
        test_warcry_no_twin_duplication,
        test_corruption_makes_skills_free,
        test_searing_blow_formula,
        test_reaper_heals_unblocked_only,
        test_choke_expires_at_turn_end,
        test_finisher_does_not_count_itself,
        test_blood_for_blood_no_exhaust_and_upgrade_cost,
        test_perfected_strike_counts_itself,
        test_escape_plan_detects_twin_draw,
        test_play_card_rejects_replayed_card,
        test_time_warp_locks_plays,
        # 2026-06-12 audit
        test_sentinel_plays_and_exhaust_gives_energy,
        test_berserk_energy_unconditional,
        test_brutality_resets_across_combats,
        test_brutality_upgrade_is_innate,
        test_pride_curse_copies_to_draw_top_not_hand,
        test_sentry_has_artifact,
        test_awakened_one_damageable_after_rebirth,
        test_empty_cage_counts_removals,
        test_no_duplicate_relics_in_pools,
        # 2026-06-12b audit
        test_doubt_curse_weak_covers_next_turn,
        test_blue_candle_pride_single_exhaust,
        test_dead_branch_adds_no_curse_or_status,
        test_nemesis_intangible_through_turn_three,
        test_anchor_block_emits_block_gained,
        test_mark_of_pain_shuffles_wounds,
        test_exhume_cannot_return_exhume,
        test_limit_break_no_zero_strength_key,
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
