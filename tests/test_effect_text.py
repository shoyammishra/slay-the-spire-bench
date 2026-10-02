"""Fidelity tests for slay_bench/ablation/effect_text.py (engine-faithful effect text).

(a) coverage: every card / enemy / relic / power in all 1,760 controlled-H v3
    release fixtures has a spec and the appendix renders;
(b) numeric fidelity: every card spec is replayed through the REAL engine
    (``play_card`` in a canonical sandbox; targeted skills also through
    ``controlled_horizon.transition``) and every enemy AI is stepped turn by turn;
(c) renaming: bijective, deterministic per seed, no original proper name survives.

Run: python tests/test_effect_text.py   (no pytest needed; set PYTHONIOENCODING=utf-8)
"""
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from slay_bench import new_game, start_combat, make_enemy  # noqa: E402
from slay_bench.ablation import effect_text as et  # noqa: E402
from slay_bench.cards import (make_card_for, _draw_cards, _gain_block,  # noqa: E402
                              _apply_damage_to_enemy, _discard_from_hand)
from slay_bench.combat import play_card, end_player_turn, end_combat  # noqa: E402
from slay_bench.controlled_horizon import (ControlledFixture, load_fixture,  # noqa: E402
                                           legal_actions, transition, build_prompt)
from slay_bench.enemies import Enemy, Move, _enemy_attack  # noqa: E402
from slay_bench.enums import IntentType, PowerId  # noqa: E402
from slay_bench.relics import BurningBlood, RingOfTheSnake  # noqa: E402

FIXTURES = os.path.join(ROOT, "results", "controlled_h_v3_release_fixtures.json")

# Cards whose effect is only partly checkable numerically, with the reason
# (must equal the specs' ``unchecked`` field set - nothing is skipped silently).
EXPECTED_UNCHECKED = {
    "True Grit", "Alchemize", "All-Out Attack", "Sword Boomerang", "Bouncing Flask",
}


# ── sandbox ───────────────────────────────────────────────────────────────────

class Dummy(Enemy):
    """Inert test enemy with ample HP; optionally attacks for ``attack`` each turn."""

    def __init__(self, hp=999, attack=0):
        super().__init__("Dummy", "Dummy", hp, hp)
        self._attack = attack

    def select_move(self, state):
        if self._attack:
            self.current_move = Move("Hit", IntentType.ATTACK, damage=self._attack, hits=1)
        else:
            self.current_move = Move("Wait", IntentType.BUFF)
        return self.current_move

    def execute_move(self, state):
        if self._attack:
            _enemy_attack(state, self, self.current_move)


def _char(spec):
    return "ironclad" if spec.character == "ironclad" else "silent"


def _filler(char):
    return "Defend_R" if char == "ironclad" else "Defend_G"


def sandbox(char, card_id, hand_extra=(), draw_ids=None, n_enemies=1, energy=3,
            enemy_hp=999, attack=0):
    """Fresh combat: no relics, Dummy enemies, hand = [card] + extras, draw pile of
    filler Defends (top = list end), empty discard/exhaust piles."""
    s = new_game(1, char)
    s.player.relics = []
    s.player.deck = [make_card_for(char, _filler(char)) for _ in range(5)]
    start_combat(s, [Dummy(enemy_hp, attack) for _ in range(n_enemies)])
    c = s.combat
    c.hand = []
    c.discard_pile = []
    c.exhaust_pile = []
    c.draw_pile = [make_card_for(char, x)
                   for x in (draw_ids if draw_ids is not None else [_filler(char)] * 12)]
    card = make_card_for(char, card_id)
    c.hand = [card] + [make_card_for(char, x) for x in hand_extra]
    s.player.energy = energy
    return s, card


def pw(powers):
    return {(k.value if hasattr(k, "value") else str(k)): v for k, v in powers.items()}


def delta(before, after):
    keys = set(before) | set(after)
    return {k: after.get(k, 0) - before.get(k, 0) for k in keys
            if after.get(k, 0) != before.get(k, 0)}


def snapshot(s):
    c = s.combat
    return {
        "enemy_hp": [e.hp for e in c.enemies],
        "enemy_powers": [pw(e.powers) for e in c.enemies],
        "block": s.player.block, "hp": s.player.hp, "max_hp": s.player.max_hp,
        "energy": s.player.energy, "draw": len(c.draw_pile),
        "powers": pw(s.player.powers), "potions": len(s.player.potions),
    }


def play_measure(s, card, target_index=0, via_transition=False):
    """Play ``card`` (engine call or controlled-H transition) and measure deltas."""
    before = snapshot(s)
    if via_transition:
        idx = next(i for i, c in enumerate(s.combat.hand) if c is card)
        act = next(a for a in legal_actions(s)
                   if a.action == "play" and a.card_index == idx)
        s = transition(s, act)
        card = None
    else:
        if target_index is None and card.type.name == "ATTACK":
            target_index = 0
        target = None if target_index is None else s.combat.enemies[target_index]
        play_card(s, card, target)
    after = snapshot(s)
    return s, card, before, after


# ── (a) coverage over all release fixtures ────────────────────────────────────

_STATES = None


def release_states():
    global _STATES
    if _STATES is None:
        with open(FIXTURES, encoding="utf-8") as fh:
            payload = json.load(fh)
        _STATES = [load_fixture(ControlledFixture.from_dict(p)) for p in payload]
    return _STATES


def test_coverage_all_release_fixtures():
    states = release_states()
    assert len(states) == 1760, len(states)
    names, enemies, relics, powers = set(), set(), set(), set()
    for s in states:
        c = s.combat
        for card in c.hand + c.draw_pile + c.discard_pile + c.exhaust_pile:
            et.card_spec_for(card)              # raises if missing / upgraded
            names.add(card.name)
            assert et.describe_card(card)
        for e in c.enemies:
            assert type(e).__name__ in et.ENEMY_SPECS, type(e).__name__
            enemies.add(e.name)
            for p in e.powers:
                key = p.value if hasattr(p, "value") else str(p)
                assert key in et.POWER_SPECS, key
                powers.add(key)
        for p in s.player.powers:
            assert p.value in et.POWER_SPECS, p
            powers.add(p.value)
        for r in s.player.relics:
            assert r.name in et.RELIC_SPECS, r.name
            relics.add(r.name)
        text = et.effects_appendix(s)
        for card in c.hand + c.draw_pile + c.discard_pile + c.exhaust_pile:
            assert f"- {card.name}:" in text, card.name
        for e in c.enemies:
            assert f"- {e.name}:" in text
        assert set(et.proper_names_in_state(s)) <= set(et.all_proper_names())
    assert len(names) == 107, len(names)       # incl. Shiv/Dazed/Slimed
    assert enemies == {"Lagavulin", "Slime Boss", "Hexaghost", "Gremlin Nob", "Sentry"}
    assert relics == {"Burning Blood", "Ring of the Snake"}
    print(f"  coverage: {len(names)} card names, {len(enemies)} enemies, "
          f"{len(relics)} relics, {len(powers)} power keys in 1,760 fixtures")


def test_every_spec_card_is_constructible_and_flags_match():
    for spec in et.CARD_SPECS.values():
        card = make_card_for(_char(spec), spec.id)
        assert card.name == spec.name, spec.id
        assert card.type.name == spec.type, spec.id
        assert card.upgraded == spec.upgraded
        if spec.cost is None:
            assert card.cost == -1 and card.unplayable, spec.id
        else:
            assert card.cost == spec.cost and not card.unplayable, spec.id
        for flag in ("exhaust", "ethereal", "innate", "retain"):
            assert bool(getattr(card, flag)) == getattr(spec, flag), (spec.id, flag)
    assert {s.name for s in et.CARD_SPECS.values() if s.unchecked} == EXPECTED_UNCHECKED
    for spec in et.CARD_SPECS.values():
        if spec.unchecked:
            print(f"  partially checked: {spec.name}: {spec.unchecked}")


# ── (b) numeric fidelity: generic one-play check for EVERY card ───────────────

def _default_expectations(spec, energy):
    """Expected deltas of one play in the default sandbox, from spec fields only."""
    n_en = 2 if (spec.target in ("all", "random") or spec.all_enemy_powers) else 1
    damage = spec.damage * spec.hits * (n_en if spec.target == "all" else 1)
    block, draw = spec.block, spec.draw
    self_powers = dict(spec.self_powers)
    target_powers = dict(spec.target_powers)
    # Conditional numbers, all taken from the spec's params:
    if spec.id == "Perfected Strike":       # only Strike-family card = itself
        damage = spec.damage + spec.param("per_strike") * 1
    if spec.id == "Skewer":                 # X = 3 energy
        damage = spec.damage * energy
    if spec.id == "Escape Plan":            # filler draw is a Skill
        block += spec.param("skill_block")
    if spec.id == "Expertise":              # hand empty after the play
        draw = spec.param("hand_to")
    if spec.id == "Doppelganger":
        self_powers = {"Next Turn Draw": energy, "Energized": energy}
    if spec.id == "Bouncing Flask":         # one enemy receives every bounce
        target_powers = {"Poison": spec.param("poison") * spec.param("times")}
    if spec.id == "Malaise":
        target_powers = {"Strength": -energy, "Weak": energy}
    return n_en, damage, block, draw, self_powers, target_powers


def test_generic_one_play_fidelity_every_card():
    checked = 0
    for spec in et.CARD_SPECS.values():
        char = _char(spec)
        energy = 3
        n_en, damage, block, draw, self_powers, target_powers = \
            _default_expectations(spec, energy)
        draw_ids = [] if spec.id == "Grand Finale" else None
        s, card = sandbox(char, spec.id, n_enemies=n_en, energy=energy,
                          draw_ids=draw_ids)
        if spec.unplayable:
            assert not card.can_play(s), spec.id
            checked += 1
            continue
        assert card.can_play(s), spec.id
        paid = energy if spec.cost == -2 else max(0, card.effective_cost())
        target_index = 0 if (spec.type == "ATTACK" or spec.targeted_skill) else None
        s, card, b, a = play_measure(s, card, target_index=target_index)
        got_damage = sum(x - y for x, y in zip(b["enemy_hp"], a["enemy_hp"]))
        assert got_damage == damage, (spec.id, got_damage, damage)
        assert a["block"] - b["block"] == block, (spec.id, a["block"] - b["block"], block)
        assert b["draw"] - a["draw"] == draw, (spec.id, b["draw"] - a["draw"], draw)
        assert a["energy"] - (b["energy"] - paid) == spec.energy, \
            (spec.id, a["energy"], b["energy"], paid)
        assert b["hp"] - a["hp"] == spec.hp_loss, spec.id
        assert delta(b["powers"], a["powers"]) == self_powers, \
            (spec.id, delta(b["powers"], a["powers"]), self_powers)
        for i in range(n_en):
            expected = dict(spec.all_enemy_powers)
            if i == 0:
                for k, v in target_powers.items():
                    expected[k] = expected.get(k, 0) + v
            got = delta(b["enemy_powers"][i], a["enemy_powers"][i])
            assert got == expected, (spec.id, i, got, expected)
        c = s.combat
        n_exh = sum(1 for x in c.exhaust_pile if x is card)
        n_dis = sum(1 for x in c.discard_pile if x is card)
        if spec.exhaust:
            assert (n_exh, n_dis) == (1, 0), (spec.id, n_exh, n_dis)
        else:
            # Engine: played Powers go to the discard pile like Attacks/Skills.
            assert (n_exh, n_dis) == (0, 1), (spec.id, n_exh, n_dis)
        # Rendered text carries every non-zero numeric field.
        text = et.describe_card(card, mode="engine")
        for value in (spec.damage, spec.block, spec.draw, spec.energy, spec.hp_loss):
            if value:
                assert str(value) in text, (spec.id, value, text)
        checked += 1
    assert checked == len(et.CARD_SPECS)
    print(f"  generic one-play fidelity: {checked} card specs")


# ── (b) targeted skills through the controlled-H interface ───────────────────

def test_targeted_skills_have_no_enemy_effect_in_controlled_h():
    assert set(et.TARGETED_SKILLS) == {
        "Catalyst", "Corpse Explosion", "Deadly Poison", "Leg Sweep", "Malaise",
        "Spot Weakness", "Terror"}
    for name in et.TARGETED_SKILLS:
        spec = next(sp for sp in et.CARD_SPECS.values() if sp.name == name)
        s, card = sandbox(_char(spec), spec.id, attack=5)
        s.combat.enemies[0].powers[PowerId.POISON] = 4   # gives Catalyst something
        acts = [x for x in legal_actions(s) if x.action == "play"]
        assert acts and all(x.target_index == -1 for x in acts), name
        s2, _, b, a = play_measure(s, card, via_transition=True)
        assert delta(b["enemy_powers"][0], a["enemy_powers"][0]) == {}, name
        assert delta(b["powers"], a["powers"]) == {}, name   # Spot Weakness: no Str
        assert a["block"] - b["block"] == spec.block, name   # Leg Sweep keeps Block
        text = et.describe_card(card)
        assert "never happens" in text, text
        assert "never happens" not in et.describe_card(card, mode="engine")
    # Malaise still spends all energy under controlled-H.
    s, card = sandbox("silent", "Malaise", energy=3)
    s2, _, b, a = play_measure(s, card, via_transition=True)
    assert a["energy"] == 0


# ── (b) conditional / delayed effects: explicit scenarios ─────────────────────

def _spec(name):
    return next(sp for sp in et.CARD_SPECS.values() if sp.name == name)


def _hp_loss_of(s, b):
    return sum(x - y for x, y in zip(b, [e.hp for e in s.combat.enemies]))


def test_ironclad_conditional_scenarios():
    sp = _spec("Body Slam")
    s, card = sandbox("ironclad", "Body Slam")
    s.player.block = 7
    b = [e.hp for e in s.combat.enemies]
    play_card(s, card, s.combat.enemies[0])
    assert _hp_loss_of(s, b) == 7 and sp.param("damage_equals_block")

    sp = _spec("Brutality")
    s, card = sandbox("ironclad", "Brutality")
    play_card(s, card)
    assert s.player.brutality
    hp, n_draw = s.player.hp, len(s.combat.draw_pile)
    end_player_turn(s)
    assert hp - s.player.hp == sp.param("turn_hp_loss")
    assert len(s.combat.hand) == 5 + sp.param("turn_draw")

    s, card = sandbox("ironclad", "Burning Pact", hand_extra=("Strike_R", "Bash"))
    strike = s.combat.hand[1]
    play_card(s, card)
    assert any(x is strike for x in s.combat.exhaust_pile)
    assert len(s.combat.exhaust_pile) == 1

    s, card = sandbox("ironclad", "Clash", hand_extra=("Defend_R",))
    assert not card.can_play(s)
    s, card = sandbox("ironclad", "Clash", hand_extra=("Strike_R",))
    assert card.can_play(s)

    s, card = sandbox("ironclad", "Exhume")
    bash = make_card_for("ironclad", "Bash")
    other = make_card_for("ironclad", "Exhume")
    s.combat.exhaust_pile = [bash, other]
    play_card(s, card)
    assert any(x is bash for x in s.combat.hand)
    assert any(x is other for x in s.combat.exhaust_pile)

    sp = _spec("Feed")
    s, card = sandbox("ironclad", "Feed", enemy_hp=5)
    hp, mx = s.player.hp, s.player.max_hp
    play_card(s, card, s.combat.enemies[0])
    assert s.player.max_hp - mx == sp.param("kill_max_hp")
    assert s.player.hp - hp == sp.param("kill_max_hp")

    sp = _spec("Fiend Fire")
    s, card = sandbox("ironclad", "Fiend Fire",
                      hand_extra=("Strike_R", "Defend_R", "Bash"))
    b = [e.hp for e in s.combat.enemies]
    play_card(s, card, s.combat.enemies[0])
    assert _hp_loss_of(s, b) == 3 * sp.param("per_card_damage")
    assert len(s.combat.exhaust_pile) == 4 and not s.combat.hand

    for name, attr in (("Evolve", "draw"), ("Fire Breathing", "damage")):
        sp = _spec(name)
        s, card = sandbox("ironclad", sp.id, n_enemies=2)
        play_card(s, card)
        amount = dict(sp.self_powers)[name]
        s.combat.draw_pile.append(make_card_for("ironclad", "Dazed"))
        b = [e.hp for e in s.combat.enemies]
        n_hand = len(s.combat.hand)
        _draw_cards(s, 1)
        if attr == "draw":
            assert len(s.combat.hand) - n_hand == 1 + amount
        else:
            assert _hp_loss_of(s, b) == 2 * amount

    sp = _spec("Feel No Pain")
    s, card = sandbox("ironclad", "Feel No Pain", hand_extra=("Slimed",))
    play_card(s, card)
    blk = s.player.block
    play_card(s, s.combat.hand[0])          # Slimed exhausts itself
    assert s.player.block - blk == dict(sp.self_powers)["Feel No Pain"]

    sp = _spec("Flame Barrier")
    s, card = sandbox("ironclad", "Flame Barrier", attack=3)
    play_card(s, card)
    for _ in range(2):    # retaliation never expires in this engine
        hp = s.combat.enemies[0].hp
        end_player_turn(s)
        assert hp - s.combat.enemies[0].hp == dict(sp.self_powers)["Flame Barrier"]

    sp = _spec("Juggernaut")
    s, card = sandbox("ironclad", "Juggernaut", hand_extra=("Defend_R",))
    play_card(s, card)
    hp = s.combat.enemies[0].hp
    play_card(s, s.combat.hand[0])
    assert hp - s.combat.enemies[0].hp == dict(sp.self_powers)["Juggernaut"]

    s, card = sandbox("ironclad", "Limit Break")
    s.player.powers[PowerId.STRENGTH] = 3
    play_card(s, card)
    assert s.player.powers[PowerId.STRENGTH] == 6

    sp = _spec("Metallicize")
    s, card = sandbox("ironclad", "Metallicize", attack=10)
    play_card(s, card)
    hp = s.player.hp
    end_player_turn(s)
    assert hp - s.player.hp == 10           # no Block in the first enemy phase
    assert s.player.block == dict(sp.self_powers)["Metallicize"]  # start of next turn

    sp = _spec("Perfected Strike")
    s, card = sandbox("ironclad", "Perfected Strike",
                      draw_ids=["Defend_R"] * 4 + ["Strike_R", "Strike_R", "Pommel Strike"])
    b = [e.hp for e in s.combat.enemies]
    play_card(s, card, s.combat.enemies[0])
    assert _hp_loss_of(s, b) == sp.damage + 4 * sp.param("per_strike")

    s, card = sandbox("ironclad", "Sever Soul", hand_extra=("Defend_R", "Strike_R"))
    defend, strike = s.combat.hand[1], s.combat.hand[2]
    play_card(s, card, s.combat.enemies[0])
    assert any(x is defend for x in s.combat.exhaust_pile)
    assert any(x is strike for x in s.combat.hand)

    sp = _spec("Spot Weakness")
    s, card = sandbox("ironclad", "Spot Weakness", attack=5)
    play_card(s, card, s.combat.enemies[0])
    assert s.player.powers.get(PowerId.STRENGTH) == sp.param("strength")

    s, card = sandbox("ironclad", "True Grit", hand_extra=("Strike_R", "Bash"))
    play_card(s, card)
    assert s.player.block == 7 and len(s.combat.exhaust_pile) == 1
    assert len(s.combat.hand) == 1


def test_status_and_relic_scenarios():
    s, card = sandbox("ironclad", "Dazed")
    end_player_turn(s)
    assert any(x is card for x in s.combat.exhaust_pile)   # Ethereal
    sp = _spec("Burn")
    s, card = sandbox("ironclad", "Burn")
    hp = s.player.hp
    end_player_turn(s)
    assert hp - s.player.hp == sp.param("end_turn_damage")
    # Ring of the Snake: 5 + 2 cards at combat start.
    s = new_game(3, "silent")
    start_combat(s, [Dummy()])
    assert len(s.combat.hand) == 7
    assert any(isinstance(r, RingOfTheSnake) for r in s.player.relics)
    # Burning Blood heals 6 only at end_combat (not reached in controlled-H).
    s = new_game(3, "ironclad")
    start_combat(s, [Dummy()])
    s.player.hp = 50
    end_combat(s)
    assert s.player.hp == 56
    assert any(isinstance(r, BurningBlood) for r in s.player.relics)


def test_silent_conditional_scenarios():
    s, card = sandbox("silent", "Accuracy", hand_extra=("Shiv",))
    play_card(s, card)
    hp = s.combat.enemies[0].hp
    play_card(s, s.combat.hand[0], s.combat.enemies[0])
    assert hp - s.combat.enemies[0].hp == _spec("Shiv").damage + 4

    for name, kind in (("After Image", "block"), ("A Thousand Cuts", "damage")):
        s, card = sandbox("silent", name, hand_extra=("Slice",))
        play_card(s, card, None)
        blk, hp = s.player.block, s.combat.enemies[0].hp
        play_card(s, s.combat.hand[0], s.combat.enemies[0])
        if kind == "block":
            assert s.player.block - blk == 1
        else:
            assert hp - s.combat.enemies[0].hp == _spec("Slice").damage + 1

    s, card = sandbox("silent", "Alchemize")
    play_card(s, card)
    assert len(s.player.potions) == 1

    s, card = sandbox("silent", "All-Out Attack", hand_extra=("Strike_G", "Defend_G"))
    play_card(s, card, s.combat.enemies[0])
    assert s.combat.discarded_this_turn == 1

    s, card = sandbox("silent", "Bane")
    s.combat.enemies[0].powers[PowerId.POISON] = 5
    hp = s.combat.enemies[0].hp
    play_card(s, card, s.combat.enemies[0])
    assert hp - s.combat.enemies[0].hp == _spec("Bane").damage * 2

    for name in ("Blade Dance", "Cloak and Dagger"):
        s, card = sandbox("silent", name)
        play_card(s, card)
        assert [c.name for c in s.combat.hand] == ["Shiv"] * _spec(name).param("shivs")

    s, card = sandbox("silent", "Blur")
    play_card(s, card)
    end_player_turn(s)
    assert s.player.block == 5

    s, card = sandbox("silent", "Bouncing Flask", n_enemies=2)
    play_card(s, card)
    total = sum(e.powers.get(PowerId.POISON, 0) for e in s.combat.enemies)
    sp = _spec("Bouncing Flask")
    assert total == sp.param("poison") * sp.param("times")
    s, card = sandbox("silent", "Bouncing Flask")
    play_card(s, card)
    assert s.combat.enemies[0].powers[PowerId.POISON] == 9

    s, card = sandbox("silent", "Bullet Time", hand_extra=("Dash",), energy=3)
    dash = s.combat.hand[1]
    play_card(s, card)
    assert s.player.energy == 0 and dash.can_play(s)
    end_player_turn(s)
    assert dash.cost_override is None

    s, card = sandbox("silent", "Burst", hand_extra=("Deflect",))
    play_card(s, card)
    play_card(s, s.combat.hand[0])
    assert s.player.block == 2 * _spec("Deflect").block

    s, card = sandbox("silent", "Calculated Gamble",
                      hand_extra=("Strike_G", "Strike_G", "Slice"))
    play_card(s, card)
    assert s.combat.discarded_this_turn == 3 and len(s.combat.hand) == 3

    s, card = sandbox("silent", "Caltrops", attack=6)
    play_card(s, card)
    hp = s.combat.enemies[0].hp
    end_player_turn(s)
    assert s.combat.enemies[0].hp == hp          # player Thorns never triggers

    s, card = sandbox("silent", "Catalyst")
    s.combat.enemies[0].powers[PowerId.POISON] = 5
    play_card(s, card, s.combat.enemies[0])
    assert s.combat.enemies[0].powers[PowerId.POISON] == 5 * _spec("Catalyst").param("mult")

    s, card = sandbox("silent", "Choke", hand_extra=("Deflect",))
    play_card(s, card, s.combat.enemies[0])
    hp = s.combat.enemies[0].hp
    play_card(s, s.combat.hand[0])
    assert hp - s.combat.enemies[0].hp == 3
    end_player_turn(s)
    assert PowerId.CHOKED not in s.combat.enemies[0].powers

    s, card = sandbox("silent", "Concentrate",
                      hand_extra=("Strike_G", "Strike_G", "Defend_G", "Slice"))
    play_card(s, card)
    assert s.combat.discarded_this_turn == _spec("Concentrate").param("discards")
    assert s.player.energy == 5

    s, card = sandbox("silent", "Corpse Explosion", n_enemies=2)
    play_card(s, card, s.combat.enemies[0])
    e0, e1 = s.combat.enemies
    hp1 = e1.hp
    _apply_damage_to_enemy(s, e0, 5000)
    from slay_bench.combat import _check_enemy_deaths
    _check_enemy_deaths(s)
    assert hp1 - e1.hp == e0.max_hp

    s, card = sandbox("silent", "Dagger Throw")
    play_card(s, card, s.combat.enemies[0])
    assert s.combat.discarded_this_turn == 1

    s, card = sandbox("silent", "Distraction")
    play_card(s, card)
    assert [c.name for c in s.combat.hand] == ["Deflect"]

    s, card = sandbox("silent", "Dodge and Roll")
    play_card(s, card)
    end_player_turn(s)
    assert s.player.block == 4

    s, card = sandbox("silent", "Doppelganger", energy=2)
    play_card(s, card)
    end_player_turn(s)
    assert s.player.energy == 3 + 2 and len(s.combat.hand) == 5 + 2

    s, card = sandbox("silent", "Endless Agony")
    s.combat.hand = []
    s.combat.draw_pile.append(card)
    _draw_cards(s, 1)
    assert [c.name for c in s.combat.hand] == ["Endless Agony", "Endless Agony"]

    s, card = sandbox("silent", "Envenom", hand_extra=("Slice",))
    play_card(s, card)
    play_card(s, s.combat.hand[0], s.combat.enemies[0])
    assert s.combat.enemies[0].powers[PowerId.POISON] == 1

    s, card = sandbox("silent", "Escape Plan", draw_ids=["Strike_G"] * 3)
    play_card(s, card)
    assert s.player.block == 0
    s, card = sandbox("silent", "Escape Plan", draw_ids=["Defend_G"] * 3)
    play_card(s, card)
    assert s.player.block == _spec("Escape Plan").param("skill_block")

    s, card = sandbox("silent", "Eviscerate", hand_extra=("Strike_G",))
    _discard_from_hand(s, s.combat.hand[1])
    assert card.can_play(s) and card.effective_cost() == 2

    s, card = sandbox("silent", "Expertise", hand_extra=("Slice", "Slice"))
    play_card(s, card)
    assert len(s.combat.hand) == _spec("Expertise").param("hand_to")

    sp = _spec("Finisher")
    s, card = sandbox("silent", "Finisher", hand_extra=("Slice", "Slice"))
    play_card(s, s.combat.hand[1], s.combat.enemies[0])
    play_card(s, s.combat.hand[1], s.combat.enemies[0])
    hp = s.combat.enemies[0].hp
    play_card(s, card, s.combat.enemies[0])
    assert hp - s.combat.enemies[0].hp == 2 * sp.param("per_attack_damage")

    sp = _spec("Flechettes")
    s, card = sandbox("silent", "Flechettes", hand_extra=("Defend_G", "Deflect", "Slice"))
    hp = s.combat.enemies[0].hp
    play_card(s, card, s.combat.enemies[0])
    assert hp - s.combat.enemies[0].hp == 2 * sp.param("per_skill_damage")

    sp = _spec("Glass Knife")
    s, card = sandbox("silent", "Glass Knife", energy=5)
    play_card(s, card, s.combat.enemies[0])
    s.combat.discard_pile = [x for x in s.combat.discard_pile if x is not card]
    s.combat.hand.append(card)
    hp = s.combat.enemies[0].hp
    play_card(s, card, s.combat.enemies[0])
    assert hp - s.combat.enemies[0].hp == 2 * (sp.damage - sp.param("decay"))
    assert "currently deals 4" in et.describe_card(card)

    s, card = sandbox("silent", "Grand Finale")
    assert not card.can_play(s)                 # draw pile not empty

    sp = _spec("Heel Hook")
    s, card = sandbox("silent", "Heel Hook")
    s.combat.enemies[0].powers[PowerId.WEAK] = 1
    e0, n_draw = s.player.energy, len(s.combat.draw_pile)
    play_card(s, card, s.combat.enemies[0])
    assert s.player.energy == e0 - 1 + sp.param("weak_energy")
    assert n_draw - len(s.combat.draw_pile) == sp.param("weak_draw")

    s, card = sandbox("silent", "Infinite Blades")
    play_card(s, card)
    end_player_turn(s)
    assert sum(1 for c in s.combat.hand if c.name == "Shiv") == 1

    s, card = sandbox("silent", "Nightmare", hand_extra=("Slice",))
    play_card(s, card)
    end_player_turn(s)
    assert sum(1 for c in s.combat.hand if c.name == "Slice") == 3

    s, card = sandbox("silent", "Noxious Fumes", n_enemies=2)
    play_card(s, card)
    end_player_turn(s)
    assert all(e.powers.get(PowerId.POISON) == 2 for e in s.combat.enemies)

    s, card = sandbox("silent", "Outmaneuver")
    play_card(s, card)
    end_player_turn(s)
    assert s.player.energy == 5

    s, card = sandbox("silent", "Phantasmal Killer", draw_ids=["Slice"] * 8)
    play_card(s, card)
    end_player_turn(s)
    slice_card = s.combat.hand[0]
    hp = s.combat.enemies[0].hp
    play_card(s, slice_card, s.combat.enemies[0])
    assert hp - s.combat.enemies[0].hp == 2 * _spec("Slice").damage

    s, card = sandbox("silent", "Predator")
    play_card(s, card, s.combat.enemies[0])
    end_player_turn(s)
    assert len(s.combat.hand) == 7

    s, card = sandbox("silent", "Prepared")
    play_card(s, card)
    assert s.combat.discarded_this_turn == 1

    for name, check in (("Reflex", "draw"), ("Tactician", "energy")):
        sp = _spec(name)
        s, card = sandbox("silent", "Survivor", hand_extra=(name,))
        e0, n_draw = s.player.energy, len(s.combat.draw_pile)
        play_card(s, card)
        if check == "draw":
            assert n_draw - len(s.combat.draw_pile) == sp.param("discard_draw")
        else:
            assert s.player.energy == e0 - 1 + sp.param("discard_energy")

    s, card = sandbox("silent", "Setup", hand_extra=("Dash",))
    dash = s.combat.hand[1]
    play_card(s, card)
    assert s.combat.draw_pile[-1] is dash and dash.effective_cost() == 0

    s, card = sandbox("silent", "Sneaky Strike", hand_extra=("Strike_G",))
    _discard_from_hand(s, s.combat.hand[1])
    play_card(s, card, s.combat.enemies[0])
    assert s.player.energy == 3 - 2 + _spec("Sneaky Strike").param("discard_energy")

    s, card = sandbox("silent", "Storm of Steel", hand_extra=("Strike_G",) * 3)
    play_card(s, card)
    assert [c.name for c in s.combat.hand] == ["Shiv"] * 3

    s, card = sandbox("silent", "Survivor", hand_extra=("Slice", "Strike_G"))
    strike = s.combat.hand[2]
    play_card(s, card)
    assert any(x is strike for x in s.combat.discard_pile)

    s, card = sandbox("silent", "Tools of the Trade")
    play_card(s, card)
    end_player_turn(s)
    assert len(s.combat.hand) == 5 and s.combat.discarded_this_turn == 1

    s, card = sandbox("silent", "Unload", hand_extra=("Defend_G", "Slice"))
    defend, slc = s.combat.hand[1], s.combat.hand[2]
    play_card(s, card, s.combat.enemies[0])
    assert any(x is defend for x in s.combat.discard_pile)
    assert any(x is slc for x in s.combat.hand)

    s, card = sandbox("silent", "Well-Laid Plans", hand_extra=("Slice", "Dash"))
    slc = s.combat.hand[1]
    play_card(s, card)
    end_player_turn(s)
    assert any(x is slc for x in s.combat.hand)

    s, card = sandbox("silent", "Wraith Form", attack=9)
    play_card(s, card)
    hp = s.player.hp
    end_player_turn(s)
    assert hp - s.player.hp == 1                 # Intangible
    assert s.player.powers.get(PowerId.DEXTERITY) == -1


def test_suspected_engine_bugs_are_real():
    """Pins the behaviours reported as suspected bugs (documented, NOT fixed)."""
    # Burst + a self-exhausting Skill puts the same object in the exhaust pile twice.
    s, card = sandbox("silent", "Burst", hand_extra=("Adrenaline",))
    adr = s.combat.hand[1]
    play_card(s, card)
    play_card(s, adr)
    assert sum(1 for x in s.combat.exhaust_pile if x is adr) == 2
    # Poison below half HP does not split the Slime Boss.
    s, _ = sandbox("silent", "Slice")
    boss = make_enemy("SlimeBoss", s.rng.hp_rng)
    s.combat.enemies = [boss]
    boss.select_move(s)
    boss.hp = boss.max_hp // 2 + 3
    boss.powers[PowerId.POISON] = 10
    end_player_turn(s)
    assert len(s.combat.enemies) == 1 and boss.hp <= boss.max_hp // 2 and not boss._split
    # Both Sentries of the pair share id Sentry_0 and start with Beam.
    s = new_game(1, "silent")
    sentries = [make_enemy("Sentry", s.rng.hp_rng) for _ in range(2)]
    assert [e.id for e in sentries] == ["Sentry_0", "Sentry_0"]


# ── (b) enemy AI stepping ─────────────────────────────────────────────────────

def enemy_sandbox(enemy_ids, seed=7, char="ironclad", hp=5000):
    s = new_game(seed, char)
    s.player.relics = []
    s.player.max_hp = s.player.hp = hp
    s.player.deck = [make_card_for(char, _filler(char)) for _ in range(10)]
    enemies = [make_enemy(e, s.rng.hp_rng) for e in enemy_ids]
    start_combat(s, enemies)
    return s, enemies


def step_moves(s, enemy, n):
    seq = []
    for _ in range(n):
        seq.append(enemy.current_move.name)
        end_player_turn(s)
    return seq


def _move(spec, name):
    return next(m for m in spec.moves if m.name == name)


def test_enemy_hp_ranges_and_start_powers():
    for key, spec in et.ENEMY_SPECS.items():
        hps = set()
        for seed in range(60):
            s = new_game(seed, "ironclad")
            e = make_enemy(key, s.rng.hp_rng)
            hps.add(e.hp)
            assert e.name == spec.name and e.id in spec.ids, (key, e.id)
            assert pw(e.powers) == dict(spec.start_powers), (key, e.powers)
        assert min(hps) >= spec.hp_min and max(hps) <= spec.hp_max, (key, hps)


def test_lagavulin_ai():
    spec = et.ENEMY_SPECS["Lagavulin"]
    s, (lag,) = enemy_sandbox(["Lagavulin"])
    hp0 = s.player.hp
    seq = []
    for i in range(6):
        seq.append(lag.current_move.name)
        if lag.current_move.name == "Attack":
            assert lag.current_move.damage == _move(spec, "Attack").damage
        hp = s.player.hp
        end_player_turn(s)
        if seq[-1] == "Attack":
            assert hp - s.player.hp == _move(spec, "Attack").damage
        if i == 0:
            assert lag.block == 8                  # Metallicize at end of round
    assert tuple(seq) == spec.deterministic_cycle, seq
    assert s.player.powers.get(PowerId.STRENGTH) == -2   # two Siphon Souls
    assert s.player.powers.get(PowerId.DEXTERITY) == -2
    assert PowerId.METALLICIZE not in lag.powers
    # Wakes immediately if the player starts below max HP.
    s = new_game(7, "ironclad")
    s.player.relics = []
    s.player.hp = s.player.max_hp - 1
    lag = make_enemy("Lagavulin", s.rng.hp_rng)
    start_combat(s, [lag])
    assert lag.current_move.name == "Attack"
    # Damaging it does NOT wake it.
    s, (lag,) = enemy_sandbox(["Lagavulin"])
    _apply_damage_to_enemy(s, lag, 40, from_attack=True)
    end_player_turn(s)
    assert lag.current_move.name == "Sleep"


def test_slime_boss_ai_and_split():
    spec = et.ENEMY_SPECS["SlimeBoss"]
    s, (boss,) = enemy_sandbox(["SlimeBoss"])
    n_dis = len(s.combat.discard_pile)
    seq = []
    for i in range(6):
        seq.append(boss.current_move.name)
        hp = s.player.hp
        n_slimed = sum(1 for c in s.combat.discard_pile + s.combat.draw_pile
                       + s.combat.hand + s.combat.exhaust_pile if c.name == "Slimed")
        end_player_turn(s)
        if seq[-1] == "Slam":
            assert hp - s.player.hp == _move(spec, "Slam").damage
        if seq[-1] == "Goop Spray":
            after = sum(1 for c in s.combat.discard_pile + s.combat.draw_pile
                        + s.combat.hand + s.combat.exhaust_pile if c.name == "Slimed")
            assert after - n_slimed == 3
    assert tuple(seq) == spec.deterministic_cycle, seq
    # Split on direct damage at/below half max HP.
    s, (boss,) = enemy_sandbox(["SlimeBoss"])
    _apply_damage_to_enemy(s, boss, boss.hp - boss.max_hp // 2, from_attack=True)
    remaining = boss.max_hp // 2
    kids = s.combat.enemies[1:]
    assert boss.hp == 0 and [type(k).__name__ for k in kids] == ["SpikeSlimeL", "AcidSlimeL"]
    assert [et.ENEMY_SPECS[type(k).__name__].name for k in kids] == list(spec.spawns)
    assert all(k.hp == k.max_hp == remaining for k in kids)
    assert all(k.current_move is None for k in kids)   # no action this round
    end_player_turn(s)
    assert all(k.current_move is not None for k in kids)


def _check_random_slime(key, rounds=40, seeds=range(4)):
    spec = et.ENEMY_SPECS[key]
    names = {m.name for m in spec.moves}
    seen = set()
    for seed in seeds:
        s, (e,) = enemy_sandbox([key], seed=seed, hp=100000)
        e.max_hp = e.hp = 10 ** 6          # never split during the AI check
        prev = None
        for _ in range(rounds):
            m = e.current_move
            assert m.name in names, (key, m.name)
            sm = _move(spec, m.name)
            assert (m.damage, m.hits if m.damage else 0) == (sm.damage, sm.hits), key
            assert m.name != prev, (key, "repeat", m.name)
            prev = m.name
            seen.add(m.name)
            end_player_turn(s)
    assert seen == names, (key, seen)


def test_slime_children_ai_and_split():
    for key in ("AcidSlimeL", "SpikeSlimeL", "AcidSlimeM", "SpikeSlimeM"):
        _check_random_slime(key)
    for key, child in (("AcidSlimeL", "AcidSlimeM"), ("SpikeSlimeL", "SpikeSlimeM")):
        s, (e,) = enemy_sandbox([key])
        _apply_damage_to_enemy(s, e, e.hp - e.max_hp // 2, from_attack=True)
        kids = s.combat.enemies[1:]
        assert e.hp == 0 and [type(k).__name__ for k in kids] == [child, child]
        assert et.ENEMY_SPECS[key].spawns == (et.ENEMY_SPECS[child].name,)


def test_hexaghost_ai():
    spec = et.ENEMY_SPECS["Hexaghost"]
    s, (hexa,) = enemy_sandbox(["Hexaghost"])
    seq, inferno_k = [], 0
    for _ in range(8):
        m = hexa.current_move
        seq.append(m.name)
        if m.name == "Divider":
            assert m.hits == 6 and m.damage == s.player.hp // 12 + 1
        if m.name == "Inferno":
            inferno_k += 1
            assert m.hits == 6 and m.damage == 2 * inferno_k
        if m.name == "Sear":
            assert (m.damage, m.hits) == (_move(spec, "Sear").damage, 1)
        str0 = hexa.powers.get(PowerId.STRENGTH, 0)
        end_player_turn(s)
        if seq[-1] == "Inflame":
            assert hexa.powers.get(PowerId.STRENGTH, 0) - str0 == 2
            assert hexa.block == 12
        if seq[-1] == "Sear":
            assert any(c.name == "Burn" for c in
                       s.combat.discard_pile + s.combat.hand + s.combat.draw_pile)
    assert tuple(seq) == spec.deterministic_cycle, seq


def test_gremlin_nob_ai():
    spec = et.ENEMY_SPECS["GremlinNob"]
    firsts = set()
    for seed in range(12):
        s, (nob,) = enemy_sandbox(["GremlinNob"], seed=seed)
        seq = step_moves(s, nob, 7)
        assert seq[0] == "Bellow", seq
        assert nob.powers.get("enrage") == 2
        firsts.add(seq[1])
        for a, b in zip(seq[1:], seq[2:]):
            assert {a, b} == {"Rush", "Skull Bash"}, seq
    assert firsts == {"Rush", "Skull Bash"}
    s, (nob,) = enemy_sandbox(["GremlinNob"])
    end_player_turn(s)                      # Bellow executes
    s.combat.hand.append(make_card_for("ironclad", "Defend_R"))
    s.player.energy = 3
    play_card(s, s.combat.hand[-1])
    assert nob.powers.get(PowerId.STRENGTH) == 2
    for name in ("Rush", "Skull Bash"):
        assert _move(spec, name).damage in (14, 6)


def test_sentry_pair_ai():
    spec = et.ENEMY_SPECS["Sentry"]
    s, (a, b) = enemy_sandbox(["Sentry", "Sentry"])
    seq_a, seq_b = [], []
    for _ in range(6):
        seq_a.append(a.current_move.name)
        seq_b.append(b.current_move.name)
        if a.current_move.name == "Beam":
            assert a.current_move.damage == _move(spec, "Beam").damage
        end_player_turn(s)
    assert tuple(seq_a) == tuple(seq_b) == spec.deterministic_cycle
    s, (a, b) = enemy_sandbox(["Sentry", "Sentry"])
    end_player_turn(s)                      # both Beam
    s.combat.draw_pile = [make_card_for("ironclad", "Strike_R")]
    s.combat.discard_pile = []
    end_player_turn(s)                      # both Bolt: 4 Dazed to the bottom
    # The 5-card draw took Strike + 4 Dazed from the 5-card pile.
    assert sum(1 for c in s.combat.hand if c.name == "Dazed") == 4
    s, (a, b) = enemy_sandbox(["Sentry", "Sentry"])
    from slay_bench.cards import _apply_power
    _apply_power(s, a, PowerId.WEAK, 1)
    assert PowerId.WEAK not in a.powers and PowerId.ARTIFACT not in a.powers


def test_enemy_move_names_and_intents_match_engine():
    """Every spec move name occurs in the engine's executed vocabulary and every
    engine move observed is in the spec (checked over many seeds)."""
    observed = {}
    for key in et.ENEMY_SPECS:
        for seed in range(3):
            s, (e,) = enemy_sandbox([key], seed=seed, hp=100000)
            e.max_hp = e.hp = 10 ** 6
            for _ in range(12):
                m = e.current_move
                observed.setdefault(key, set()).add((m.name, m.intent.name))
                end_player_turn(s)
    for key, spec in et.ENEMY_SPECS.items():
        spec_moves = {(m.name, m.intent) for m in spec.moves}
        assert observed[key] == spec_moves, (key, observed[key] ^ spec_moves)


# ── (c) renaming ──────────────────────────────────────────────────────────────

def _word_re(names):
    names = sorted(set(names), key=lambda n: -len(n))
    return re.compile(r"(?<![A-Za-z0-9_])(?:" + "|".join(re.escape(n) for n in names)
                      + r")(?![A-Za-z0-9_])")


ALL_ORIGINAL = set(et.all_proper_names(include_context=True)) | set(et.NAME_ALIASES)


def test_name_map_bijective_and_deterministic():
    names = et.all_proper_names(include_context=True)
    m = et.neutral_name_map(names, seed=11)
    assert set(m) == set(names)
    assert len(set(m.values())) == len(m)                    # injective
    inv = {v: k for k, v in m.items()}
    assert all(inv[m[k]] == k for k in m)                    # inverse
    assert m == et.neutral_name_map(reversed(names), seed=11)  # order-free
    assert m != et.neutral_name_map(names, seed=12)
    for k, v in m.items():
        cat = et.name_category(k)
        assert v.startswith(cat + " "), (k, v)
        assert not _word_re(ALL_ORIGINAL).search(v), v        # tokens leak nothing
    assert m["Pommel Strike"] != m["Strike"]
    # Same map in a fresh interpreter (no hash-seed / process dependence).
    code = ("import sys,json; sys.path.insert(0, %r); from slay_bench.ablation import "
            "effect_text as et; print(json.dumps(et.neutral_name_map("
            "et.all_proper_names(True), 11), sort_keys=True))" % ROOT)
    env = dict(os.environ, PYTHONHASHSEED="12345")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                         env=env, check=True).stdout
    assert json.loads(out) == m
    # Aliases follow their display name.
    assert et.rename("Strike_R Strike_G Sentry_0 SlimeBoss", m) == \
        f"{m['Strike']} {m['Strike']} {m['Sentry']} {m['Slime Boss']}"


def test_cross_references_renamed_consistently():
    m = et.release_name_map(5)
    blade = et.rename("Blade Dance: " + et.describe_card("Blade Dance"), m)
    assert m["Shiv"] in blade and m["Blade Dance"] in blade
    ps = et.rename(et.describe_card("Perfected Strike"), m)
    for n in ("Strike", "Pommel Strike", "Perfected Strike"):
        assert m[n] in ps, n
    payload = {"enrage": 2, "list": ["Strike_R", {"name": "Gremlin Nob"}],
               "_first_move": "Beam"}
    out = et.rename(payload, m)
    assert out == {m["enrage"]: 2, "list": [m["Strike"], {"name": m["Gremlin Nob"]}],
                   "_first_move": m["Beam"]}


def _marked(kind, name):
    return "\x02" + name + "\x03"


def test_rendered_text_mentions_names_only_through_refs():
    """No proper name appears in rendered text except via an explicit {kind:Name}
    ref - so renaming can never corrupt ordinary words."""
    texts = [et.render_card_spec(sp, mode, ref=_marked)
             for sp in et.CARD_SPECS.values() for mode in et.MODES]
    texts += [et.describe_enemy(k, ref=_marked) for k in et.ENEMY_SPECS]
    texts += [et.describe_power(p, 3, ref=_marked) for p in et.POWER_SPECS]
    texts += [et.describe_relic(r) for r in et.RELIC_SPECS]
    texts += [et._fmt(et.RULES_TEXT, ref=_marked)]
    pattern = _word_re(ALL_ORIGINAL - set(et.KEPT_KEYWORDS))
    for t in texts:
        bare = re.sub("\x02[^\x03]*\x03", "", t)
        hit = pattern.search(bare)
        assert hit is None, (hit.group(0) if hit else None, t)


def test_no_original_name_survives_in_renamed_prompts():
    states = release_states()
    m = et.release_name_map(2026, include_context=True)
    pattern = _word_re(ALL_ORIGINAL)
    for i, s in enumerate(states):
        system, user = build_prompt(s, 8, "structured" if i % 2 else "raw")
        text = "\n".join([system, user, et.effects_appendix(s)])
        renamed = et.rename(text, m)
        hit = pattern.search(renamed)
        assert hit is None, (i, hit.group(0), renamed[max(0, hit.start() - 80):
                                                     hit.end() + 80])
        assert set(et.proper_names_in_state(s)) <= set(m)
    print(f"  renamed {len(states)} prompts+appendices: no proper name survives")


def test_appendix_token_lengths():
    lens = sorted(len(et.effects_appendix(s)) / 4 for s in release_states())
    med = lens[len(lens) // 2]
    print(f"  effects_appendix ~tokens (len/4): median {med:.0f}, max {lens[-1]:.0f}, "
          f"min {lens[0]:.0f}")
    assert lens[-1] < 4000


if __name__ == "__main__":
    tests = [
        test_coverage_all_release_fixtures,
        test_every_spec_card_is_constructible_and_flags_match,
        test_generic_one_play_fidelity_every_card,
        test_targeted_skills_have_no_enemy_effect_in_controlled_h,
        test_ironclad_conditional_scenarios,
        test_status_and_relic_scenarios,
        test_silent_conditional_scenarios,
        test_suspected_engine_bugs_are_real,
        test_enemy_hp_ranges_and_start_powers,
        test_lagavulin_ai,
        test_slime_boss_ai_and_split,
        test_slime_children_ai_and_split,
        test_hexaghost_ai,
        test_gremlin_nob_ai,
        test_sentry_pair_ai,
        test_enemy_move_names_and_intents_match_engine,
        test_name_map_bijective_and_deterministic,
        test_cross_references_renamed_consistently,
        test_rendered_text_mentions_names_only_through_refs,
        test_no_original_name_survives_in_renamed_prompts,
        test_appendix_token_lengths,
    ]
    passed = failed = 0
    for test in tests:
        try:
            test()
            passed += 1
            print(f"[PASS] {test.__name__}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"[FAIL] {test.__name__}: {exc!r}")
            import traceback
            traceback.print_exc()
    print(f"\n{'=' * 40}\nResults: {passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
