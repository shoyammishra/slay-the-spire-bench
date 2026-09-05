"""Benchmark harness tests — uses MockLLM, no real API calls."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
from slay_bench import new_ironclad_game, start_combat
from slay_bench.enemies import Cultist, JawWorm
from slay_bench.benchmark import (
    MockLLM, TurnEvaluator, CombatEvaluator, SynergyEvaluator,
    RunEvaluator, BenchmarkHarness,
    _exhaustive_best_sequence, _simulate_play_sequence,
    _classify_archetype, _classify_archetype_confident, _draft_coherence,
    TurnScore, CombatScore, SynergyScore, RunScore, BenchmarkResult,
)
from slay_bench.prompt_builder import (
    combat_state_structured, combat_state_raw,
    deck_relic_structured, deck_relic_raw,
    card_reward_structured, card_reward_raw,
)
from slay_bench.rewards import generate_card_reward


# ── Prompt builder tests ──────────────────────────────────────────────────────

def test_structured_prompt():
    """Structured prompt serializes to valid JSON."""
    state = new_ironclad_game(1)
    enemy = Cultist(state.rng.hp_rng)
    start_combat(state, [enemy])
    text = combat_state_structured(state)
    data = json.loads(text)
    assert "player" in data
    assert "hand" in data
    assert "enemies" in data
    assert data["player"]["hp"] > 0
    print(f"[PASS] Structured prompt: {len(text)} chars, {len(data['hand'])} cards in hand")


def test_raw_prompt():
    """Raw prompt is human-readable text."""
    state = new_ironclad_game(2)
    enemy = JawWorm(state.rng.hp_rng)
    start_combat(state, [enemy])
    text = combat_state_raw(state)
    assert "COMBAT" in text
    assert "Player" in text
    assert "Hand" in text
    assert "Jaw Worm" in text
    print(f"[PASS] Raw prompt: {len(text)} chars")


def test_deck_relic_prompts():
    """Deck+relic prompts render without error."""
    state = new_ironclad_game(3)
    structured = deck_relic_structured(state)
    raw = deck_relic_raw(state)
    data = json.loads(structured)
    assert "deck" in data
    assert "relics" in data
    assert "Deck" in raw
    print(f"[PASS] Deck/relic prompts: structured={len(structured)}c raw={len(raw)}c")


def test_card_reward_prompts():
    """Card reward prompts include offer details."""
    state = new_ironclad_game(4)
    offers = generate_card_reward(state, 3)
    structured = card_reward_structured(offers, state.player.deck, state.player.relics)
    raw = card_reward_raw(offers, state.player.deck, state.player.relics)
    data = json.loads(structured)
    assert len(data["offers"]) == 3
    assert "CARD REWARD" in raw
    print(f"[PASS] Card reward prompts: {[c['name'] for c in data['offers']]}")


# ── Exhaustive search tests ───────────────────────────────────────────────────

def test_exhaustive_search():
    """Exhaustive search finds a non-negative damage sequence."""
    state = new_ironclad_game(10)
    enemy = Cultist(state.rng.hp_rng)
    start_combat(state, [enemy])
    opt_dmg, opt_seq = _exhaustive_best_sequence(state)
    assert opt_dmg >= 0
    assert isinstance(opt_seq, list)
    print(f"[PASS] Exhaustive search: opt_dmg={opt_dmg}, sequence={opt_seq}")


def test_simulate_play_sequence():
    """Simulate play sequence returns damage and legality."""
    state = new_ironclad_game(11)
    enemy = Cultist(state.rng.hp_rng)
    start_combat(state, [enemy])
    # Play nothing — 0 damage, legal
    dmg, legal = _simulate_play_sequence(state, [])
    assert dmg == 0
    assert legal
    print(f"[PASS] Simulate empty sequence: dmg={dmg}, legal={legal}")


# ── Mock LLM tests ────────────────────────────────────────────────────────────

def test_mock_llm_responses():
    """MockLLM returns scripted responses in order."""
    mock = MockLLM(['{"plays": [0], "reasoning": "test"}',
                    '{"action": "end_turn", "reasoning": "done"}'])
    r1 = mock.complete_json("sys", "user1")
    r2 = mock.complete_json("sys", "user2")
    assert r1 == {"plays": [0], "reasoning": "test"}
    assert r2 == {"action": "end_turn", "reasoning": "done"}
    assert mock.last_raw_response == '{"action": "end_turn", "reasoning": "done"}'
    assert len(mock._calls) == 2
    print(f"[PASS] MockLLM: {len(mock._calls)} calls recorded")


def test_mock_llm_parse_failure():
    """MockLLM handles bad JSON gracefully."""
    mock = MockLLM(["not json at all"])
    resp = mock.complete_json("sys", "user")
    assert "error" in resp or "raw" in resp
    print(f"[PASS] MockLLM parse failure handled: keys={list(resp.keys())}")


# ── TurnEvaluator tests ───────────────────────────────────────────────────────

def test_turn_evaluator_structured():
    """TurnEvaluator runs with structured prompt format."""
    mock = MockLLM(['{"plays": [0], "reasoning": "attack first"}'])
    evaluator = TurnEvaluator(mock, prompt_format="structured")
    state = new_ironclad_game(20)
    enemy = Cultist(state.rng.hp_rng)
    start_combat(state, [enemy])
    score = evaluator.evaluate(state)
    assert isinstance(score, TurnScore)
    assert score.optimal_damage >= 0
    assert isinstance(score.damage_ratio, float)
    assert 0.0 <= score.damage_ratio <= 1.0
    print(f"[PASS] TurnEvaluator structured: opt_dmg={score.optimal_damage}, "
          f"llm_dmg={score.llm_damage}, ratio={score.damage_ratio:.2f}")


def test_turn_evaluator_raw():
    """TurnEvaluator runs with raw prompt format."""
    mock = MockLLM(['{"plays": [], "reasoning": "skip"}'])
    evaluator = TurnEvaluator(mock, prompt_format="raw")
    state = new_ironclad_game(21)
    enemy = JawWorm(state.rng.hp_rng)
    start_combat(state, [enemy])
    score = evaluator.evaluate(state)
    assert isinstance(score, TurnScore)
    assert score.parse_ok
    print(f"[PASS] TurnEvaluator raw: parse_ok={score.parse_ok}, legal={score.legal}")


def test_turn_evaluator_bad_parse():
    """TurnEvaluator handles LLM parse failure gracefully."""
    mock = MockLLM(["definitely not json"])
    evaluator = TurnEvaluator(mock, prompt_format="structured")
    state = new_ironclad_game(22)
    enemy = Cultist(state.rng.hp_rng)
    start_combat(state, [enemy])
    score = evaluator.evaluate(state)
    assert not score.parse_ok
    assert score.llm_sequence == []
    # H3: a parse failure must NOT count as a legal (empty) play, or legal_rate
    # gets inflated by exactly the parse-failure rate.
    assert not score.legal
    print(f"[PASS] TurnEvaluator bad parse: parse_ok={score.parse_ok}, legal={score.legal}")


# ── CombatEvaluator tests ─────────────────────────────────────────────────────

def test_combat_evaluator_end_turn():
    """CombatEvaluator with all end-turn responses completes without crash."""
    mock = MockLLM(['{"action": "end_turn", "reasoning": "mock"}'])
    evaluator = CombatEvaluator(mock, max_turns=5)
    state = new_ironclad_game(30)
    enemy = Cultist(state.rng.hp_rng)
    score = evaluator.evaluate(state, [enemy])
    assert isinstance(score, CombatScore)
    assert score.turns <= 5
    print(f"[PASS] CombatEvaluator end_turn: won={score.won}, turns={score.turns}, "
          f"hp={score.hp_remaining}")


def test_combat_evaluator_play_attacks():
    """CombatEvaluator that plays card 0 each turn (likely a Strike)."""
    # Script: play card 0 on turn 1, then end turn; repeat
    responses = ['{"action": "play", "card_index": 0, "target_index": 0, "reasoning": "attack"}',
                 '{"action": "end_turn", "reasoning": "done"}'] * 20
    mock = MockLLM(responses)
    evaluator = CombatEvaluator(mock, max_turns=20)
    state = new_ironclad_game(31)
    enemy = Cultist(state.rng.hp_rng)
    score = evaluator.evaluate(state, [enemy])
    assert isinstance(score, CombatScore)
    print(f"[PASS] CombatEvaluator attacks: won={score.won}, cards_played={score.cards_played}, "
          f"parse_errors={score.parse_errors}")


def test_combat_evaluator_null_indices():
    """Model returning null/string card_index or target_index must not crash."""
    responses = ['{"action": "play", "card_index": null, "target_index": null, "reasoning": "bad"}',
                 '{"action": "play", "card_index": "0", "target_index": "0", "reasoning": "str"}',
                 '{"action": "end_turn", "reasoning": "done"}'] * 20
    mock = MockLLM(responses)
    evaluator = CombatEvaluator(mock, max_turns=20)
    state = new_ironclad_game(31)
    enemy = Cultist(state.rng.hp_rng)
    score = evaluator.evaluate(state, [enemy])  # must not raise TypeError
    assert isinstance(score, CombatScore)
    print(f"[PASS] CombatEvaluator null/str indices handled: won={score.won}, "
          f"turns={score.turns}")


def test_classify_archetype_confident():
    """Confident only when one archetype uniquely owns the most signature cards."""
    from types import SimpleNamespace
    card = lambda n: SimpleNamespace(name=n)

    # One signature (Body Slam = Block payoff), rest generic → confident Block
    deck = [card(n) for n in ("Strike", "Defend", "Bash", "Body Slam", "Hemokinesis")]
    label, conf = _classify_archetype_confident(deck, [])
    assert conf and label == "Block", (label, conf)

    # No signature card at all → ambiguous (this is the seed-244 bug: Armaments /
    # Headbutt are NOT Exhaust payoffs, so they must not fabricate an Exhaust label)
    deck = [card(n) for n in ("Strike", "Bash", "Armaments", "Headbutt", "Uppercut")]
    label, conf = _classify_archetype_confident(deck, [])
    assert not conf, (label, conf)

    # Tie: one payoff for each of two archetypes → ambiguous
    deck = [card(n) for n in ("Corruption", "Juggernaut")]  # Exhaust + Block
    label, conf = _classify_archetype_confident(deck, [])
    assert not conf, (label, conf)

    print("[PASS] _classify_archetype_confident: signature/ambiguity logic correct")


# ── SynergyEvaluator tests ────────────────────────────────────────────────────

def test_synergy_evaluator():
    """SynergyEvaluator scores archetype + card pick."""
    mock = MockLLM(['{"archetype": "Aggro", "best_card_index": 0, "worst_card_name": "Defend"}'])
    evaluator = SynergyEvaluator(mock, prompt_format="structured")
    state = new_ironclad_game(40)
    offers = generate_card_reward(state, 3)
    score = evaluator.evaluate(state, offers, expert_pick_idx=0, expert_remove_name="Defend")
    assert isinstance(score, SynergyScore)
    assert score.parse_ok
    assert score.card_pick_correct is True
    assert score.removal_correct is True
    print(f"[PASS] SynergyEvaluator: archetype_correct={score.archetype_correct}, "
          f"pick_correct={score.card_pick_correct}, remove_correct={score.removal_correct}")


def test_synergy_evaluator_raw():
    """SynergyEvaluator with raw prompt format."""
    mock = MockLLM(['{"archetype": "Block", "best_card_index": 1, "worst_card_name": "Strike"}'])
    evaluator = SynergyEvaluator(mock, prompt_format="raw")
    state = new_ironclad_game(41)
    offers = generate_card_reward(state, 3)
    score = evaluator.evaluate(state, offers)
    assert isinstance(score, SynergyScore)
    assert score.parse_ok
    print(f"[PASS] SynergyEvaluator raw: archetype={score.raw_response.get('archetype')}")


def test_synergy_eval_fixtures():
    """run_synergy_eval uses hand-crafted decks: confident labels, correct ground
    truth, and a model that answers right scores right."""
    # seed=0: 0%20=fixture 0=Strength. After rotation (target_pos=0%3=0, rot=(1-0)%3=1),
    # offer becomes [Bludgeon, Strike_R, Defend_R], expert pick_idx=0 (Bludgeon).
    mock = MockLLM(['{"archetype": "Strength", "best_card_index": 0, "worst_card_name": "Strike"}'])
    harness = BenchmarkHarness(mock, model_name="mock", prompt_format="structured")
    scores = harness.run_synergy_eval([0])  # seed 0 % 20 = fixture 0 = Strength
    s = scores[0]
    assert s.expert_archetype == "Strength", s.expert_archetype
    assert s.archetype_confident is True          # crafted decks are never ambiguous
    assert s.archetype_correct is True            # model said Strength
    assert s.card_pick_correct is True            # picked index 1
    assert s.removal_correct is True              # said Strike
    print(f"[PASS] synergy fixtures: label={s.expert_archetype}, all-correct path works")


# ── Archetype classification tests ───────────────────────────────────────────

def test_classify_archetype():
    """Archetype classifier returns one of the 4 known archetypes."""
    state = new_ironclad_game(50)
    arch = _classify_archetype(state.player.deck, state.player.relics)
    assert arch in ("Strength", "Block", "Exhaust", "Aggro")
    print(f"[PASS] Archetype classification: starter deck -> {arch}")


def test_draft_coherence():
    """Draft coherence returns a float in [0, 1]."""
    state = new_ironclad_game(51)
    arch = _classify_archetype(state.player.deck, state.player.relics)
    coh = _draft_coherence(state.player.deck, arch)
    assert 0.0 <= coh <= 1.0
    print(f"[PASS] Draft coherence: {coh:.2f} for archetype {arch}")


# ── RunEvaluator tests ────────────────────────────────────────────────────────

def test_run_evaluator():
    """RunEvaluator completes an act without crashing."""
    # Script responses: always end turn in combat, pick card 0 in rewards
    combat_resp = '{"action": "end_turn", "reasoning": "mock"}'
    card_resp = '{"pick": 0, "reasoning": "mock"}'
    mock = MockLLM([combat_resp, card_resp] * 500)
    evaluator = RunEvaluator(mock, max_combat_turns=5)
    state = new_ironclad_game(60)
    score = evaluator.evaluate(state, n_acts=1)
    assert isinstance(score, RunScore)
    assert score.floors_reached >= 0
    assert 0.0 <= score.hp_fraction <= 1.0
    assert 0.0 <= score.draft_coherence <= 1.0
    print(f"[PASS] RunEvaluator: survived={score.survived}, floors={score.floors_reached}, "
          f"hp={score.final_hp}/{score.max_hp}, coherence={score.draft_coherence:.2f}")


# ── BenchmarkHarness tests ────────────────────────────────────────────────────

def test_harness_summary():
    """BenchmarkHarness.run_all returns a valid summary dict."""
    combat_resp = '{"action": "end_turn", "reasoning": "mock"}'
    turn_resp = '{"plays": [], "reasoning": "mock"}'
    synergy_resp = '{"archetype": "Aggro", "best_card_index": 0, "worst_card_name": "Defend"}'
    card_resp = '{"pick": -1, "reasoning": "mock"}'
    mock = MockLLM([turn_resp, combat_resp, synergy_resp, card_resp] * 1000)

    harness = BenchmarkHarness(mock, model_name="mock-model", prompt_format="structured")
    result = harness.run_all(seed=42, n_turn=2, n_combat=1, n_synergy=1, n_run=1)
    assert isinstance(result, BenchmarkResult)

    summary = result.summary()
    assert summary["model"] == "mock-model"
    assert summary["turn"]["n"] == 2
    assert summary["combat"]["n"] == 1
    assert summary["synergy"]["n"] == 1
    assert summary["run"]["n"] == 1
    assert summary["elapsed_seconds"] >= 0

    print(f"[PASS] Harness summary:")
    import json
    print(json.dumps(summary, indent=2))


def test_harness_determinism():
    """Same seed, same mock responses → identical results."""
    responses = ['{"plays": [0], "reasoning": "r"}',
                 '{"action": "end_turn", "reasoning": "r"}',
                 '{"archetype": "Aggro", "best_card_index": 0, "worst_card_name": "Defend"}',
                 '{"pick": 0, "reasoning": "r"}'] * 500

    mock1 = MockLLM(responses[:])
    mock2 = MockLLM(responses[:])
    h1 = BenchmarkHarness(mock1, "m", "structured")
    h2 = BenchmarkHarness(mock2, "m", "structured")

    r1 = h1.run_all(seed=77, n_turn=1, n_combat=1, n_synergy=1, n_run=0)
    r2 = h2.run_all(seed=77, n_turn=1, n_combat=1, n_synergy=1, n_run=0)

    assert r1.turn_scores[0].optimal_damage == r2.turn_scores[0].optimal_damage
    assert r1.combat_scores[0].hp_remaining == r2.combat_scores[0].hp_remaining
    print(f"[PASS] Harness determinism: turn opt_dmg={r1.turn_scores[0].optimal_damage}, "
          f"combat hp={r1.combat_scores[0].hp_remaining}")


# ── Robustness regression tests (malformed-but-parseable LLM output) ─────────

def test_turn_evaluator_nonint_indices():
    """String/null/negative indices in "plays" must not crash the evaluator.
    Numeric strings count as valid plays; null/negatives = illegal sequence."""
    from slay_bench import new_game, start_combat
    # String indices: coerced, sequence plays fine
    mock = MockLLM(['{"plays": ["0", "1"], "reasoning": "r"}'])
    ev = TurnEvaluator(mock, "structured")
    state = new_game(80, "ironclad")
    start_combat(state, [Cultist(state.rng.hp_rng)])
    score = ev.evaluate(state)
    assert score.legal, "numeric-string indices should be playable"
    # Null + negative indices: illegal, not a crash
    mock2 = MockLLM(['{"plays": [null, -1], "reasoning": "r"}'])
    ev2 = TurnEvaluator(mock2, "structured")
    state2 = new_game(80, "ironclad")
    start_combat(state2, [Cultist(state2.rng.hp_rng)])
    score2 = ev2.evaluate(state2)
    assert not score2.legal and score2.llm_damage == 0
    print("[PASS] Turn evaluator survives string/null/negative indices")


def test_synergy_evaluator_null_fields():
    """null archetype / worst_card_name and string best_card_index must not
    crash, and a numeric-string pick is scored as the number it means."""
    from slay_bench import new_game
    from slay_bench.cards import make_card_for
    mock = MockLLM(['{"archetype": null, "best_card_index": "1", "worst_card_name": null}'])
    ev = SynergyEvaluator(mock, "structured")
    state = new_game(81, "ironclad")
    offers = [make_card_for("ironclad", n) for n in ("Anger", "Bludgeon", "Iron Wave")]
    score = ev.evaluate(state, offers, expert_pick_idx=1, expert_remove_name="Strike")
    assert score.parse_ok
    assert score.card_pick_correct is True, "string '1' should match expert pick 1"
    assert score.removal_correct is False
    print("[PASS] Synergy evaluator survives null/string answer fields")


def test_character_propagates_to_evaluators():
    """BenchmarkHarness must hand its character to ALL evaluators (Silent runs
    were getting Ironclad system prompts in turn/combat)."""
    mock = MockLLM(['{"plays": [], "reasoning": "r"}',
                    '{"action": "end_turn", "reasoning": "r"}'] * 50)
    h = BenchmarkHarness(mock, "m", "structured", character="silent")
    h.run_turn_eval([90])
    h.run_combat_eval([91])
    assert all("Silent" in sys for sys, _user in mock._calls), \
        "every system prompt must mention the Silent"
    print("[PASS] Character propagates to turn/combat evaluators")


def test_aggregation_keys_match_summary():
    """Multi-seed aggregation must use the real summary key names — a mismatch
    silently yields None means for every metric."""
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
    from run_benchmark import _aggregate_summaries
    mock = MockLLM(['{"plays": [0], "reasoning": "r"}',
                    '{"action": "end_turn", "reasoning": "r"}',
                    '{"archetype": "Aggro", "best_card_index": 0, "worst_card_name": "Strike"}',
                    '{"pick": 0, "reasoning": "r"}'] * 200)
    h = BenchmarkHarness(mock, "m", "structured")
    s1 = h.run_all(seed=42, n_turn=1, n_combat=1, n_synergy=1, n_run=0).summary()
    s2 = h.run_all(seed=43, n_turn=1, n_combat=1, n_synergy=1, n_run=0).summary()
    agg = _aggregate_summaries([s1, s2], "m", "structured", "ironclad", [42, 43])
    assert agg["turn"]["avg_damage_ratio_mean"] is not None
    assert agg["turn"]["parse_ok_rate_mean"] is not None
    assert agg["combat"]["avg_hp_ratio_mean"] is not None
    assert agg["synergy"]["parse_ok_rate_mean"] is not None
    print("[PASS] Aggregation keys match summary keys (no silent None means)")


def test_synergy_fixture_ground_truth_rules():
    """Executable fixture design rules for BOTH characters: every deck has a
    Strike (the removal target), the expert pick is on-archetype, and no other
    offer is on-archetype (no ambiguous ground truth). Catches mislabeled picks
    like the ironclad#18 Fiend-Fire-vs-Defend bug."""
    from slay_bench.benchmark import _SYNERGY_FIXTURES, _get_archetype_tables
    from slay_bench.cards_silent import SILENT_SYNERGY_FIXTURES
    from slay_bench.cards import make_card_for
    for char, fixtures in (("ironclad", _SYNERGY_FIXTURES),
                           ("silent", SILENT_SYNERGY_FIXTURES)):
        arch_t, _payoffs, _default = _get_archetype_tables(char)
        for i, (arch, deck, offers, pick) in enumerate(fixtures):
            deck_names = [make_card_for(char, n).name for n in deck]
            assert "Strike" in deck_names, f"{char}#{i} ({arch}): no Strike removal target"
            # The scoring-time expert label comes from the classifier, not the
            # fixture tag — every deck must classify CONFIDENTLY as its label.
            deck_cards = [make_card_for(char, n) for n in deck]
            label, confident = _classify_archetype_confident(deck_cards, [], char)
            assert confident and label == arch, \
                f"{char}#{i}: declared {arch} but classifier says {label} (confident={confident})"
            offer_names = [make_card_for(char, n).name for n in offers]
            assert offer_names[pick] in arch_t[arch], \
                f"{char}#{i} ({arch}): expert pick {offer_names[pick]} is off-archetype"
            for j, name in enumerate(offer_names):
                if j != pick:
                    assert name not in arch_t[arch], \
                        f"{char}#{i} ({arch}): offer[{j}]={name} also on-archetype (ambiguous)"
    print("[PASS] All 40 synergy fixtures obey the ground-truth design rules")


def test_synergy_pick_position_debias():
    """A model that ALWAYS answers index 0 must score ~chance on card-pick.
    Before the offer-rotation fix it scored 75% (Ironclad) / 100% (Silent)
    because the hand-written fixtures put the correct card first."""
    mock = MockLLM(['{"archetype": "Aggro", "best_card_index": 0, "worst_card_name": "Strike"}'])
    h = BenchmarkHarness(mock, "m", "structured")
    scores = h.run_synergy_eval(list(range(500, 520)))  # 20 samples, one fixture pass
    picks = [s.expert_pick_idx for s in scores]
    for pos in (0, 1, 2):
        assert picks.count(pos) >= 6, f"expert pick position {pos} underrepresented: {picks}"
    acc = sum(1 for s in scores if s.card_pick_correct) / len(scores)
    assert acc <= 0.4, f"always-0 strategy scored {acc:.2f} — positional bias not fixed"
    print(f"[PASS] Pick positions uniform {sorted(picks.count(p) for p in (0,1,2))}, "
          f"always-0 scores {acc:.2f}")


def test_synergy_removal_constant_strike_confounded():
    """Removal-v1 is diagnostic only: every fixture's expert target is Strike,
    so an input-ignoring constant answer reaches the 1.0 boundary."""
    import contextlib
    import io

    response = ('{"archetype":"Aggro","best_card_index":0,'
                '"worst_card_name":"Strike"}')
    for character in ("ironclad", "silent"):
        harness = BenchmarkHarness(MockLLM([response]), "m", "structured",
                                   character=character)
        with contextlib.redirect_stdout(io.StringIO()):
            scores = harness.run_synergy_eval(list(range(500, 520)))
        assert len(scores) == 20
        assert all(score.removal_correct for score in scores)
    print("[PASS] constant Strike scores 40/40; removal-v1 remains quarantined")


def test_synergy_archetype_multi_mention_scored_false():
    """An answer naming several archetypes (or echoing the option list) must NOT
    count as correct just because the right name appears as a substring."""
    from slay_bench import new_game
    from slay_bench.cards import make_card_for
    mock = MockLLM(['{"archetype": "Strength, Block, Exhaust, Aggro", '
                    '"best_card_index": 0, "worst_card_name": "Strike"}',
                    '{"archetype": "Block", "best_card_index": 0, "worst_card_name": "Strike"}'])
    ev = SynergyEvaluator(mock, "structured")
    deck = [make_card_for("ironclad", n) for n in
            ("Barricade", "Juggernaut", "Entrench", "Impervious", "Strike_R")]
    offers = [make_card_for("ironclad", n) for n in ("Body Slam", "Anger", "Iron Wave")]
    state = new_game(82, "ironclad")
    state.player.deck = deck
    s1 = ev.evaluate(state, offers, expert_pick_idx=0, expert_remove_name="Strike")
    assert s1.archetype_correct is False, "option-list echo must not score correct"
    s2 = ev.evaluate(state, offers, expert_pick_idx=0, expert_remove_name="Strike")
    assert s2.archetype_correct is True, "a single correct name must still score"
    assert s2.model_pick == 0 and s2.model_removal == "Strike"  # audit fields persisted
    print("[PASS] Multi-archetype answers rejected; single correct name accepted")


def test_combat_hp_scored_before_combat_end_heal():
    """hp_remaining must be read BEFORE end_combat fires COMBAT_END hooks
    (Burning Blood heals +6 there; the greedy baseline never emits COMBAT_END).
    Pre-fix, an LLM playing identically to the bot scored hp_ratio ~1.10."""
    from slay_bench import new_game, start_combat as _sc
    # Dry run on a twin state (same seed → same shuffle) to find an attack index.
    dry = new_game(7, "ironclad")
    dry_enemy = Cultist(dry.rng.hp_rng)
    _sc(dry, [dry_enemy])
    from slay_bench.enums import CardType
    atk_idx = next(i for i, c in enumerate(dry.combat.hand)
                   if c.type == CardType.ATTACK)

    state = new_game(7, "ironclad")
    state.player.hp = 50  # below max so the +6 heal is observable
    enemy = Cultist(state.rng.hp_rng)
    enemy.hp = enemy.max_hp = 1  # any attack kills on turn 1
    mock = MockLLM([json.dumps({"action": "play", "card_index": atk_idx,
                                "target_index": 0})])
    ev = CombatEvaluator(mock, "structured")
    score = ev.evaluate(state, [enemy])
    assert score.won
    assert score.hp_remaining == 50, \
        f"hp scored post-heal: {score.hp_remaining} (Burning Blood leaked into the score)"
    assert score.optimal_hp_remaining == 50  # greedy also kills turn 1 untouched
    assert abs(score.hp_ratio - 1.0) < 1e-9
    assert state.player.hp == 56  # the heal still applies to the state itself
    print(f"[PASS] hp_remaining={score.hp_remaining} pre-heal, ratio={score.hp_ratio:.3f}")


def test_turn_oracle_handles_more_than_six_playable():
    """The oracle must search ALL playable cards. The old first-6 cap understated
    the optimum on Silent's 7-card opening hand (Ring of the Snake) — e.g. seed
    43 reported 6 when the true optimum was 12."""
    import itertools
    from slay_bench import new_game, start_combat as _sc
    for seed in (43, 44):
        state = new_game(seed, "silent")
        enemy = Cultist(state.rng.hp_rng)
        _sc(state, [enemy])
        playable = [i for i, c in enumerate(state.combat.hand)
                    if c.can_play(state)]
        assert len(playable) == 7, f"setup drift: expected 7 playable, got {len(playable)}"
        opt_dmg, opt_seq = _exhaustive_best_sequence(state)
        # Brute-force reference over ALL playable indices (energy 3 + one
        # 0-cost card bounds legal sequences well under length 5).
        brute = 0
        for length in range(6):
            for perm in itertools.permutations(playable, length):
                dmg, legal = _simulate_play_sequence(state, list(perm))
                if legal and dmg > brute:
                    brute = dmg
        assert opt_dmg == brute, f"seed {seed}: oracle={opt_dmg} brute-force={brute}"
        # The oracle's own sequence must reproduce its claimed damage legally.
        dmg, legal = _simulate_play_sequence(state, opt_seq)
        assert legal and dmg == opt_dmg
    print(f"[PASS] Turn oracle matches full brute force on 7-playable Silent hands")


def test_synergy_prompts_vary_across_base_seeds():
    """`--seeds` must produce real instrument variance for synergy. Pre-fix,
    fixture choice and offer rotation came from the loop index only, so every
    seed sent byte-identical prompts and multi-seed std was 0 by construction."""
    def prompts_for(base_seed):
        mock = MockLLM(['{"archetype":"Aggro","best_card_index":0,'
                        '"worst_card_name":"Strike"}'])
        h = BenchmarkHarness(mock, "m", "structured")
        import io, contextlib
        with contextlib.redirect_stdout(io.StringIO()):
            h.run_synergy_eval(list(range(base_seed + 200, base_seed + 220)))
        return [u for (_s, u) in mock._calls]

    p42, p142 = prompts_for(42), prompts_for(142)
    assert p42 == prompts_for(42), "same base seed must reproduce identical prompts"
    assert p42 != p142, "different base seeds must produce different synergy prompts"
    print("[PASS] Synergy prompts are seed-dependent (reproducible per seed, vary across seeds)")


def test_intent_shows_effective_damage():
    """Prompts must show Strength-adjusted intent damage (what actually lands),
    like the real game — Cultist's Ritual previously displayed 6 forever while
    real hits grew 9/12/15."""
    from slay_bench.enums import PowerId
    state = new_ironclad_game(20)
    enemy = Cultist(state.rng.hp_rng)
    start_combat(state, [enemy])
    enemy.powers[PowerId.STRENGTH] = 6
    enemy.current_move = enemy.MOVES[1]  # Dark Strike, base 6
    data = json.loads(combat_state_structured(state))
    assert data["enemies"][0]["intent"]["damage"] == 12, data["enemies"][0]["intent"]
    assert "(12×1 dmg)" in combat_state_raw(state)
    # Weak reduces the displayed number too (floor(12 * 0.75) = 9).
    enemy.powers[PowerId.WEAK] = 1
    data = json.loads(combat_state_structured(state))
    assert data["enemies"][0]["intent"]["damage"] == 9
    print("[PASS] Intent display is Strength/Weak-adjusted in both formats")


def test_turn_prompt_states_damage_objective():
    """The turn system prompt must state the scored objective (max damage this
    turn) — models were previously penalized for unscored defensive play."""
    from slay_bench.prompt_builder import system_prompt
    p = system_prompt("turn").lower()
    assert "maximizes total damage" in p
    assert "not scored" in p
    print("[PASS] Turn system prompt states the damage-only objective")


def test_duplicate_play_indices_are_illegal():
    """`plays: [i, i]` used to replay an already-played card through an
    identical twin (equality membership) and was scored LEGAL with full
    damage — it could even beat the oracle via hand-counting cards."""
    state = new_ironclad_game(11)
    enemy = Cultist(state.rng.hp_rng)
    start_combat(state, [enemy])
    strikes = [i for i, c in enumerate(state.combat.hand) if c.name == "Strike"]
    assert len(strikes) >= 2, "test needs two identical Strikes in the opening hand"
    i, j = strikes[0], strikes[1]
    dmg_dup, legal_dup = _simulate_play_sequence(state, [i, i])
    assert not legal_dup, "duplicate index must be scored illegal"
    dmg_ok, legal_ok = _simulate_play_sequence(state, [i, j])
    assert legal_ok and dmg_ok == 12, f"distinct twins must stay legal: {dmg_ok}/{legal_ok}"
    print("[PASS] Duplicate play indices are illegal; distinct twins legal")


# ── 2026-06-12 audit regression tests ─────────────────────────────────────────

def test_safe_int_float_strings():
    """H7: numeric float-strings parse via int(float(v)); null/garbage -> default."""
    from slay_bench.benchmark import _safe_int
    assert _safe_int("1.0") == 1
    assert _safe_int("2.9") == 2
    assert _safe_int(1.7) == 1
    assert _safe_int("3") == 3
    assert _safe_int(None, default=-1) == -1
    assert _safe_int("garbage", default=-1) == -1
    assert _safe_int("", default=0) == 0
    print("[PASS] _safe_int parses float-strings, rejects garbage")


def test_combat_negative_target_index_first_alive():
    """H2: a negative target_index must NOT Python-negative-index to the last
    enemy — it falls back to the first alive enemy like out-of-range does."""
    from slay_bench.enemies import AcidSlimeS, SpikeSlimeS
    # action play card 0 (Strike) at target -1, then end turn.
    mock = MockLLM(['{"action": "play", "card_index": 0, "target_index": -1}',
                    '{"action": "end_turn"}'] * 50)
    ev = CombatEvaluator(mock, prompt_format="structured")
    state = new_ironclad_game(73)
    e0 = AcidSlimeS(state.rng.hp_rng)
    e1 = SpikeSlimeS(state.rng.hp_rng)
    hp0_before = e0.hp
    score = ev.evaluate(state, [e0, e1])
    # The first card (a Strike) must have hit the FIRST enemy (index 0), not the
    # last. Damage was dealt to e0.
    assert e0.hp < hp0_before, f"first alive enemy should have taken damage: {e0.hp}/{hp0_before}"
    print(f"[PASS] Negative target_index hits first alive enemy ({hp0_before}->{e0.hp})")


def test_synergy_summary_exposes_n_scored_denominators():
    """H4: summary's synergy block reports card_pick_n_scored and
    removal_n_scored (denominators for the parse-fail exclusion policy)."""
    mock = MockLLM(['{"archetype": "Block", "best_card_index": 0, "worst_card_name": "Strike"}'] * 40)
    h = BenchmarkHarness(mock, "m", "structured")
    result = h.run_all(seed=42, n_turn=0, n_combat=0, n_synergy=4, n_run=0)
    syn = result.summary()["synergy"]
    assert "card_pick_n_scored" in syn and "removal_n_scored" in syn
    assert syn["card_pick_n_scored"] == 4 and syn["removal_n_scored"] == 4
    print(f"[PASS] Synergy summary exposes n_scored denominators "
          f"(pick={syn['card_pick_n_scored']}, removal={syn['removal_n_scored']})")


def test_run_tag_stem_suffix():
    """H5: --run-tag appends `_<tag>` to the file stem; empty leaves it unchanged."""
    from run_benchmark import _tagged_stem
    assert _tagged_stem("llama_structured_seed42", "") == "llama_structured_seed42"
    assert _tagged_stem("llama_structured_seed42", "rep1") == "llama_structured_seed42_rep1"
    assert _tagged_stem("m_raw_seeds42_43", "  ") == "m_raw_seeds42_43"  # whitespace = empty
    print("[PASS] _tagged_stem suffixes only when a tag is set")


def test_local_llm_builds_openai_request():
    """--provider local posts an OpenAI-compatible chat-completions request to
    {base_url}/chat/completions and returns choices[0].message.content. No real
    network: urllib.request.urlopen is stubbed."""
    import urllib.request
    from slay_bench.benchmark import LocalLLM

    captured = {}

    class _FakeResp:
        def __init__(self, body): self._body = body
        def read(self): return self._body
        def __enter__(self): return self
        def __exit__(self, *a): return False

    def _fake_urlopen(req, timeout=None):
        captured["url"] = req.full_url
        captured["headers"] = dict(req.header_items())
        captured["body"] = json.loads(req.data.decode())
        captured["timeout"] = timeout
        return _FakeResp(json.dumps(
            {"choices": [{"message": {"content": '{"plays": [0]}'}}]}).encode())

    orig = urllib.request.urlopen
    urllib.request.urlopen = _fake_urlopen
    try:
        llm = LocalLLM(model="qwen3-32b", base_url="http://localhost:8000/v1/",
                       api_key="secret", timeout=123)
        out = llm.complete("sys", "user", temperature=0.7, max_tokens=4096)
    finally:
        urllib.request.urlopen = orig

    assert out == '{"plays": [0]}'
    # trailing slash on base_url is stripped, endpoint appended exactly once
    assert captured["url"] == "http://localhost:8000/v1/chat/completions"
    assert captured["timeout"] == 123
    assert llm.max_attempts == 5
    assert captured["body"]["model"] == "qwen3-32b"
    assert captured["body"]["temperature"] == 0.7
    assert captured["body"]["max_tokens"] == 4096
    assert captured["body"]["messages"][0] == {"role": "system", "content": "sys"}
    assert captured["body"]["messages"][1] == {"role": "user", "content": "user"}
    # api key flows into the Bearer header (header names are title-cased by urllib)
    assert captured["headers"].get("Authorization") == "Bearer secret"
    print("[PASS] LocalLLM posts an OpenAI-compatible request to the right URL")


def test_local_llm_surfaces_server_error():
    """A non-429 HTTP error from the local server is surfaced (not swallowed as a
    payment wall like OpenRouter's 402) so a misconfigured endpoint is obvious."""
    import urllib.request, urllib.error, io
    from slay_bench.benchmark import LocalLLM

    def _fake_urlopen(req, timeout=None):
        raise urllib.error.HTTPError(
            req.full_url, 400, "Bad Request", {},
            io.BytesIO(b'{"error": "model not found"}'))

    orig = urllib.request.urlopen
    urllib.request.urlopen = _fake_urlopen
    try:
        llm = LocalLLM(model="missing", base_url="http://localhost:8000/v1")
        raised = None
        try:
            llm.complete("sys", "user")
        except RuntimeError as e:
            raised = e
    finally:
        urllib.request.urlopen = orig

    assert raised is not None, "a 400 should raise RuntimeError"
    assert "HTTP 400" in str(raised) and "model not found" in str(raised)
    print("[PASS] LocalLLM surfaces a server HTTP error with the response body")


def test_build_llm_local_provider():
    """build_llm('local', ...) returns a LocalLLM with the resolved base_url,
    honouring the explicit --base-url over the default."""
    from run_benchmark import build_llm
    from slay_bench.benchmark import LocalLLM

    llm = build_llm("local", "qwen3-32b", base_url="http://gpu-box:8000/v1")
    assert isinstance(llm, LocalLLM)
    assert llm.model == "qwen3-32b"
    assert llm.base_url == "http://gpu-box:8000/v1"

    # default when neither --base-url nor $LOCAL_BASE_URL is set
    prev = os.environ.pop("LOCAL_BASE_URL", None)
    prev_timeout = os.environ.pop("LOCAL_TIMEOUT", None)
    prev_attempts = os.environ.pop("LOCAL_MAX_ATTEMPTS", None)
    try:
        d = build_llm("local", "m")
        assert d.base_url == "http://localhost:8000/v1"
        assert d.timeout == 300 and d.max_attempts == 5
        os.environ["LOCAL_TIMEOUT"] = "900"
        os.environ["LOCAL_MAX_ATTEMPTS"] = "1"
        frozen = build_llm("local", "m")
        assert frozen.timeout == 900 and frozen.max_attempts == 1
    finally:
        if prev is not None:
            os.environ["LOCAL_BASE_URL"] = prev
        if prev_timeout is not None:
            os.environ["LOCAL_TIMEOUT"] = prev_timeout
        else:
            os.environ.pop("LOCAL_TIMEOUT", None)
        if prev_attempts is not None:
            os.environ["LOCAL_MAX_ATTEMPTS"] = prev_attempts
        else:
            os.environ.pop("LOCAL_MAX_ATTEMPTS", None)
    print("[PASS] build_llm wires the local provider with the right base_url")


# ── 2026-06-12b audit regression tests ────────────────────────────────────────

def test_run_eval_keeps_partial_on_server_error():
    """H1: a non-429 server error mid-run (e.g. vLLM HTTP 400) must stop
    run-level and KEEP completed runs, not propagate and discard everything."""
    from slay_bench.benchmark import LLMInterface

    class _RaiseAfter(LLMInterface):
        """Acts like an always-end-turn model, but raises RuntimeError on the
        Nth complete() call (simulating a context-overflow HTTP 400)."""
        def __init__(self, raise_on):
            self.n = 0
            self.raise_on = raise_on
        def complete(self, system, user, **kw):
            self.n += 1
            if self.n >= self.raise_on:
                raise RuntimeError("server returned HTTP 400: prompt too long")
            return '{"action": "end_turn", "reasoning": "mock"}'

    # Measure the exact call count of a single run on a FIXED seed (all end-turn
    # → deterministic loss), so we can raise on the very next call when that same
    # seed is replayed as run 1 of a multi-run pass.
    counter = MockLLM(['{"action": "end_turn"}'])
    h0 = BenchmarkHarness(counter, "m", "structured")
    import io, contextlib
    with contextlib.redirect_stdout(io.StringIO()):
        h0.run_run_eval([901])
    calls_per_run = len(counter._calls)
    assert calls_per_run > 0

    # Replay seed 901 as run 1 (completes identically), then raise on the first
    # call of run 2 → run 1's score must survive.
    stub = _RaiseAfter(raise_on=calls_per_run + 1)
    h = BenchmarkHarness(stub, "m", "structured")
    with contextlib.redirect_stdout(io.StringIO()):
        scores = h.run_run_eval([901, 902])
    assert len(scores) == 1, f"must keep the 1 completed run, got {len(scores)}"
    print(f"[PASS] run_run_eval keeps {len(scores)} completed run(s) on a server error")


def test_run_all_keeps_partial_on_dimension_error():
    """H1: a non-429 exception from a dimension aborts the rest but keeps the
    dimensions completed so far (mirrors the RateLimitExhausted path)."""
    from slay_bench.benchmark import LLMInterface

    class _RaiseOnRun(LLMInterface):
        """Returns valid synergy/turn/combat answers, but raises once a run-level
        prompt arrives (run prompts mention 'move to' / 'pick')."""
        def complete(self, system, user, **kw):
            if "Output JSON: {\"pick\"" in user or "move to" in user:
                raise RuntimeError("server died mid-run")
            return ('{"plays": [0], "archetype": "Aggro", "best_card_index": 0, '
                    '"worst_card_name": "Strike", "action": "end_turn"}')

    h = BenchmarkHarness(_RaiseOnRun(), "m", "structured")
    import io, contextlib
    with contextlib.redirect_stdout(io.StringIO()):
        result = h.run_all(seed=42, n_turn=1, n_combat=1, n_synergy=2, n_run=2)
    # Earlier dimensions collected; run-level aborted but did not crash run_all.
    assert result.synergy_scores, "synergy results must survive a later-dimension crash"
    assert isinstance(result.elapsed_seconds, float)
    print("[PASS] run_all keeps partial results when a dimension errors")


def test_complete_json_first_object_and_fast_on_garbage():
    """H2: complete_json still returns the FIRST embedded JSON object, and the
    raw_decode fallback is fast on a long brace-only garbage dump."""
    import time as _t
    # First valid object wins, trailing junk ignored.
    mock = MockLLM(['noise {"a": 1} then {"b": 2} tail'])
    obj = mock.complete_json("s", "u")
    assert obj == {"a": 1}, obj
    # A truncated reasoning dump (50k '{' with no closing brace) must fail fast.
    mock2 = MockLLM(["{" * 50000])
    t0 = _t.time()
    res = mock2.complete_json("s", "u")
    elapsed = _t.time() - t0
    assert res.get("error") == "parse_failure", res
    assert elapsed < 3.0, f"parse-failure fallback too slow: {elapsed:.2f}s"
    print(f"[PASS] complete_json returns first object; garbage fails in {elapsed:.3f}s")


def test_act_transition_counts_llm_call_only_when_made():
    """L7: _act_transition must not count an llm_call when the boss-relic helper
    short-circuits (≤1 relic offered → no API call)."""
    from slay_bench.benchmark import RunEvaluator
    mock = MockLLM(['{"pick": 0}'])
    ev = RunEvaluator(mock, "structured")
    state = new_ironclad_game(42)
    counters = {"llm_calls": 0}
    # Monkeypatch the relic-choice helpers so no real relic logic runs and only
    # ONE relic is offered (forces the short-circuit).
    import slay_bench.benchmark as bm
    orig_gen = bm.generate_boss_relic_choices if hasattr(bm, "generate_boss_relic_choices") else None
    # generate_boss_relic_choices is imported inside _act_transition; patch the source.
    import slay_bench.rewards as rw
    orig = rw.generate_boss_relic_choices
    rw.generate_boss_relic_choices = lambda s, n=3: ["Sozu"]  # single offer
    try:
        ev._act_transition(state, counters)
    finally:
        rw.generate_boss_relic_choices = orig
    assert counters["llm_calls"] == 0, \
        f"no LLM call should be counted for a single-relic offer, got {counters['llm_calls']}"
    assert mock._calls == [], "no LLM call should have been made"
    print("[PASS] _act_transition counts no llm_call when none is made")


def test_complete_json_failure_diagnostics():
    """2026-07-12: parse-failure dicts must carry finish_reason / raw_len /
    truncated_think so truncation ("thought past max_tokens") can be
    distinguished from malformed-but-complete output."""
    # Truncated reasoning dump: <think> never closed, finish_reason=length.
    trunc = "<think>step 1... step 2... step 3"
    mock = MockLLM([trunc], finish_reasons=["length"])
    res = mock.complete_json("s", "u")
    assert res.get("error") == "parse_failure", res
    assert res["finish_reason"] == "length", res
    assert res["truncated_think"] is True, res
    assert res["raw_len"] == len(trunc), res
    # Malformed-but-complete output: closed <think>, finish_reason=stop.
    done = "<think>done</think> the answer is forty-two, no JSON here"
    mock2 = MockLLM([done], finish_reasons=["stop"])
    res2 = mock2.complete_json("s", "u")
    assert res2.get("error") == "parse_failure", res2
    assert res2["finish_reason"] == "stop", res2
    assert res2["truncated_think"] is False, res2
    print("[PASS] complete_json failure diagnostics distinguish truncation vs malformed")


def test_combat_parse_error_split():
    """2026-07-12: CombatScore.parse_errors is additively split into
    json_parse_errors (no JSON at all) + illegal_action_errors (valid JSON,
    bad index / unplayable / unknown action); parse_errors itself keeps the
    historical conflated total so matrix aggregates stay comparable."""
    mock = MockLLM([
        "<think>never closes",                                                # json parse fail (truncated)
        '{"action": "play", "card_index": 99, "target_index": 0, "reasoning": "r"}',  # illegal index
        '{"action": "end_turn", "reasoning": "r"}',
    ], finish_reasons=["length", "stop", "stop"])
    evaluator = CombatEvaluator(mock, max_turns=3)
    state = new_ironclad_game(30)
    enemy = Cultist(state.rng.hp_rng)
    score = evaluator.evaluate(state, [enemy])
    assert score.json_parse_errors == 1, score
    assert score.illegal_action_errors == 1, score
    assert score.truncation_errors == 1, score
    assert score.parse_errors == score.json_parse_errors + score.illegal_action_errors, score
    # The split must reach the multi-seed aggregate without silent None means.
    from run_benchmark import _aggregate_summaries
    r = BenchmarkResult("m", "structured", 42)
    r.combat_scores = [score]
    agg = _aggregate_summaries([r.summary()], "m", "structured", "ironclad", [42])
    assert agg["combat"]["avg_json_parse_errors_mean"] == 1.0, agg["combat"]
    assert agg["combat"]["avg_illegal_action_errors_mean"] == 1.0, agg["combat"]
    assert agg["combat"]["avg_truncation_errors_mean"] == 1.0, agg["combat"]
    print("[PASS] combat parse_errors split: json=1 illegal=1 truncation=1, total unchanged")


def test_turn_parse_fail_truncation_diagnostics():
    """2026-07-12: turn-level JSON-parse failures record finish_reason /
    unclosed-<think> / raw length, and the summary splits truncations out."""
    mock = MockLLM(["<think>overthinking with no end"], finish_reasons=["length"])
    evaluator = TurnEvaluator(mock, prompt_format="structured")
    state = new_ironclad_game(22)
    enemy = Cultist(state.rng.hp_rng)
    start_combat(state, [enemy])
    score = evaluator.evaluate(state)
    assert not score.parse_ok
    assert score.fail_json_parse is True, score
    assert score.fail_truncated_think is True, score
    assert score.fail_finish_reason == "length", score
    assert score.fail_raw_len > 0, score
    r = BenchmarkResult("m", "structured", 42)
    r.turn_scores = [score]
    t = r.summary()["turn"]
    assert t["parse_fail_n"] == 1 and t["parse_fail_truncated"] == 1, t
    # A schema miss (valid JSON, no "plays") is NOT a JSON-parse failure.
    mock2 = MockLLM(['{"cards": [0]}'])
    score2 = TurnEvaluator(mock2, prompt_format="structured").evaluate(state)
    assert not score2.parse_ok and score2.fail_json_parse is False, score2
    print("[PASS] turn parse-fail diagnostics: truncation recorded, schema miss excluded")


def test_per_sample_diagnostics_persisted():
    """2026-07-13: per-sample parse-failure diagnostics must survive into the
    SERIALIZED result JSON. The parse probe (2026-07-13) had to be read from
    summary counters alone — per-sample fail_finish_reason/raw_len were
    computed but discarded, and raw truncated completions were unrecoverable.
    Turn + combat summary blocks now carry a 'samples' list (synergy pattern):
    sample seed, parse/legal outcome, the fail_* split, and a size-BOUNDED
    raw-completion excerpt on failure (never the full dump)."""
    # Turn: induced truncation failure (unclosed <think>, finish_reason=length).
    long_think = "<think>" + "overthinking step " * 60   # well past the 400-char bound
    mock = MockLLM([long_think], finish_reasons=["length"])
    harness = BenchmarkHarness(mock, model_name="mock", prompt_format="structured")
    result = BenchmarkResult("mock", "structured", 42)
    result.turn_scores = harness.run_turn_eval([42])

    # Combat: alternating truncation-failure / end_turn calls.
    combat_mock = MockLLM([
        "<think>never closes",
        '{"action": "end_turn", "reasoning": "r"}',
    ], finish_reasons=["length", "stop"])
    harness2 = BenchmarkHarness(combat_mock, model_name="mock", prompt_format="structured")
    result.combat_scores = harness2.run_combat_eval([142])

    # Round-trip through JSON = exactly what lands on disk.
    blob = json.loads(json.dumps(result.summary()))

    ts = blob["turn"]["samples"]
    assert len(ts) == 1, ts
    s = ts[0]
    assert s["seed"] == 42, s
    assert s["parse_ok"] is False and s["fail_json_parse"] is True, s
    assert s["fail_finish_reason"] == "length", s
    assert s["fail_truncated_think"] is True, s
    assert s["fail_raw_len"] == len(long_think), s
    assert s["fail_raw_excerpt"].startswith("<think>"), s
    assert "chars omitted" in s["fail_raw_excerpt"], s   # bounded, not a full dump
    assert len(s["fail_raw_excerpt"]) < len(long_think), s
    # Summary counters must agree with the per-sample records.
    assert blob["turn"]["parse_fail_n"] == 1 and blob["turn"]["parse_fail_truncated"] == 1

    cs = blob["combat"]["samples"]
    assert len(cs) == 1, cs
    c = cs[0]
    assert c["seed"] == 142, c
    assert c["json_parse_errors"] >= 1, c
    assert c["truncation_errors"] == c["json_parse_errors"], c   # all failures were truncations
    assert c["parse_errors"] == c["json_parse_errors"] + c["illegal_action_errors"], c

    # A successful parse persists a clean record (no excerpt, no fail flags).
    ok_mock = MockLLM(['{"plays": [], "reasoning": "pass"}'])
    ok_harness = BenchmarkHarness(ok_mock, model_name="mock", prompt_format="structured")
    r2 = BenchmarkResult("mock", "structured", 42)
    r2.turn_scores = ok_harness.run_turn_eval([7])
    s2 = json.loads(json.dumps(r2.summary()))["turn"]["samples"][0]
    assert s2["seed"] == 7 and s2["parse_ok"] is True, s2
    assert s2["fail_json_parse"] is False and s2["fail_raw_excerpt"] == "", s2

    # Old on-disk JSONs (no 'samples' key) must still aggregate cleanly.
    from run_benchmark import _aggregate_summaries
    old_style = {"turn": {"n": 20, "avg_damage_ratio": 0.5, "legal_rate": 1.0,
                          "parse_ok_rate": 1.0, "parse_fail_n": 0, "parse_fail_truncated": 0},
                 "combat": None, "synergy": None, "run": None}
    agg = _aggregate_summaries([old_style], "m", "structured", "ironclad", [42])
    assert agg["turn"]["avg_damage_ratio_mean"] == 0.5, agg["turn"]
    print("[PASS] per-sample turn/combat diagnostics persisted in serialized summary")


def test_result_provenance_and_legacy_merge_are_explicit():
    """New artifacts disclose protocol metadata and legacy partial merges."""
    import argparse
    import tempfile
    from pathlib import Path
    from run_benchmark import _attach_provenance, _merge_existing

    args = argparse.Namespace(
        provider="mock", model="mock", fmt="structured", character="ironclad",
        seeds=None, seed=42, n_turn=1, n_combat=0, n_synergy=0, n_run=0,
        temperature=0.0, acts=1, llm_routing=False)
    current = _attach_provenance(
        {"turn": {"n": 1}, "combat": None, "synergy": None, "run": None}, args)
    assert current["result_schema_version"] == "2.0"
    assert current["provenance"]["provider"] == "mock"
    assert current["provenance"]["max_tokens"] == 8000
    assert current["provenance"]["base_seeds"] == [42]
    assert current["provenance"]["requested_base_seeds"] == [42]
    assert current["provenance"]["endpoint_persisted"] is False
    assert current["dimension_sources"]["turn"]["source"] == "current_invocation"
    args.seeds = [42, 1042]
    child = _attach_provenance({"turn": None, "combat": None, "synergy": None,
                                "run": None}, args, artifact_seeds=[1042])
    assert child["provenance"]["base_seeds"] == [1042]
    assert child["provenance"]["requested_base_seeds"] == [42, 1042]

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "legacy.json"
        path.write_text(json.dumps({"turn": None, "combat": {"n": 3},
                                    "synergy": None, "run": None}))
        merged = _merge_existing(path, current)
    assert merged["dimension_sources"]["combat"]["source"] == "merged_legacy_artifact"
    assert merged["dimension_sources"]["combat"]["provenance_complete"] is False
    print("[PASS] result provenance and legacy partial-merge source are explicit")


def test_invalid_cross_task_visuals_fail_closed():
    """Cross-task scalar/radar and horizon-line outputs must not be generated."""
    import tempfile
    from pathlib import Path
    from slay_bench.visualize import horizon_collapse_curve, write_radar

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "invalid.png"
        for fn, args in (
                (write_radar, ({"model": "mock"}, out)),
                (horizon_collapse_curve, (Path(tmp), out))):
            try:
                fn(*args)
            except RuntimeError as exc:
                assert "invalid" in str(exc).lower() or "retired" in str(exc).lower()
            else:
                raise AssertionError(f"{fn.__name__} should fail closed")
        assert not out.exists()
    print("[PASS] invalid cross-task scalar visualizations fail closed")


def test_synergy_dictionary_shortcut_solves_all_fixed_fixtures():
    """A card-name lookup with no planning must expose fixed-fixture leakage."""
    from scripts.instrument_diagnostics import synergy_lookup_audit

    audit = synergy_lookup_audit()
    for character, row in audit["by_character"].items():
        assert row["fixture_position_cases"] == 60, (character, row)
        assert row["archetype_lookup_accuracy"] == 1.0, (character, row)
        assert row["unique_on_label_offer_rate"] == 1.0, (character, row)
        assert row["card_pick_lookup_accuracy"] == 1.0, (character, row)
        assert row["expert_position_counts"] == {0: 20, 1: 20, 2: 20}
    print("[PASS] non-planning dictionary lookup solves all fixed synergy cases")


def test_controlled_horizon_holds_state_and_action_contract_fixed():
    """Only H changes in the decisive experiment prompt; its oracle is exact."""
    from slay_bench import new_game, start_combat
    from slay_bench.controlled_horizon import (
        CONTROLLED_HORIZON_VERSION, build_prompt, exact_action_values, legal_actions,
        score_response, transition)
    from slay_bench.enemies import Cultist

    state = new_game(42, "ironclad")
    start_combat(state, [Cultist(state.rng.hp_rng)])
    before_hand = [c.name for c in state.combat.hand]
    h1 = exact_action_values(state, 1, node_budget=1000)
    assert h1.version == CONTROLLED_HORIZON_VERSION and h1.exact
    assert h1.search_calls == len(legal_actions(state))
    assert h1.nodes_expanded <= h1.search_calls  # equivalent duplicate cards cache
    assert [c.name for c in state.combat.hand] == before_hand  # oracle does not mutate
    assert h1.optimal_actions

    system1, prompt1 = build_prompt(state, 1)
    system2, prompt2 = build_prompt(state, 2)
    assert system1 == system2
    assert prompt1.replace("exactly 1 decision", "exactly 2 decision") == prompt2

    best = h1.optimal_actions[0]
    response = {"action": best.action, "card_index": best.card_index,
                "target_index": best.target_index}
    score = score_response(state, "smoke-42", 1, response, node_budget=1000)
    assert score.legal and score.oracle_exact and score.regret == 0
    assert score.normalized_quality == 1.0
    # Transition operates on a clone.
    transition(state, best)
    assert [c.name for c in state.combat.hand] == before_hand
    print("[PASS] controlled-horizon v2 changes only H and uses an exact oracle")


def test_controlled_horizon_fixture_recipe_is_deterministic_and_fails_on_drift():
    """Released recipes reproduce hidden state, not only visible prompt bytes."""
    from dataclasses import asdict, replace
    from slay_bench.controlled_horizon import (
        ControlledAction, ControlledFixture, create_fixture, load_fixture, state_digest)

    fixture, state = create_fixture(
        "ironclad", 42000, ("Cultist",),
        (ControlledAction("end_turn"),), "fixture-integrity-smoke")
    rebuilt = load_fixture(fixture)
    assert state_digest(state) == fixture.state_digest == state_digest(rebuilt)
    assert [card.name for card in state.combat.hand] == [
        card.name for card in rebuilt.combat.hand]
    assert [rng.seed for rng in vars(state.rng).values()] == [
        rng.seed for rng in vars(rebuilt.rng).values()]
    json_roundtrip = ControlledFixture.from_dict(json.loads(json.dumps(asdict(fixture))))
    assert state_digest(load_fixture(json_roundtrip)) == fixture.state_digest

    tampered = replace(fixture, state_digest="0" * 64)
    try:
        load_fixture(tampered)
        assert False, "digest drift must fail closed"
    except ValueError as exc:
        assert "state drift" in str(exc)
    print("[PASS] controlled-H fixture recipes are deterministic and tamper-evident")


def test_controlled_horizon_pilot_generator_is_model_blind_and_deterministic():
    from scripts.controlled_horizon_pilot import generate_fixtures

    first = generate_fixtures(2)
    second = generate_fixtures(2)
    assert len(first) == len(second) == 4
    assert [fixture.state_digest for fixture in first] == [
        fixture.state_digest for fixture in second]
    assert {fixture.character for fixture in first} == {"ironclad", "silent"}
    assert all(fixture.version == "controlled-decision-horizon-v2"
               for fixture in first)
    print("[PASS] controlled-H pilot generator is deterministic and model-blind")


def test_controlled_horizon_frozen_protocol_is_digest_locked_and_balanced():
    from collections import Counter
    from scripts.controlled_horizon_pilot import (
        generate_frozen_candidates, load_frozen_protocol)

    protocol, digest = load_frozen_protocol()
    assert digest == "78a768f7fb27ecfba3d8c2cb4bee47ce3284c427fe6ea22b2a6dd64c70c5f110"
    fixtures, attempts = generate_frozen_candidates(protocol)
    assert len(fixtures) == len(attempts) == 800
    assert all(attempt["generated"] and attempt["error"] is None
               for attempt in attempts)
    assert len({fixture.fixture_id for fixture in fixtures}) == 800
    assert len({fixture.seed for fixture in fixtures}) == 800
    assert all(len(fixture.deck_names) == 10 for fixture in fixtures)
    by_character = Counter(fixture.character for fixture in fixtures)
    assert by_character == {"ironclad": 400, "silent": 400}
    assert {attempt["target_combat_turn"] for attempt in attempts} == {1, 2, 3}
    assert {attempt["hp_fraction"] for attempt in attempts} == {1.0, 0.75, 0.5}
    assert {len(attempt["enemy_ids"]) for attempt in attempts} == {1, 2}
    print("[PASS] frozen controlled-H protocol is digest-locked and balanced")


def test_controlled_horizon_frozen_funnel_is_deterministic_and_fails_closed():
    import copy
    from scripts.controlled_horizon_pilot import (
        load_frozen_protocol, select_frozen_advancements, select_frozen_release)

    protocol, _digest = load_frozen_protocol()
    protocol = copy.deepcopy(protocol)
    protocol["candidate_generation"]["characters"] = ["ironclad", "silent"]
    protocol["screen"]["screen_insensitive_advances_per_character"] = 1
    protocol["release"].update({
        "fixtures_per_character": 2,
        "h1_h8_sensitive_per_character": 1,
        "h1_h8_insensitive_per_character": 1,
    })

    def row(character, ordinal, h4_sensitive, h8_sensitive):
        fixture_id = f"synthetic-{character}-{ordinal}"
        action_a = {"action": "end_turn", "card_index": -1, "target_index": -1}
        action_b = {"action": "play", "card_index": 0, "target_index": 0}
        def oracle(action):
            return {
                "exact": True,
                "optimal_actions": [action],
                "zero_span": False,
                "baselines": {
                    "h1_mismatched_oracle": {
                        "regret": 1 if action == action_b else 0,
                    },
                },
            }
        return {
            "fixture": {"fixture_id": fixture_id, "character": character},
            "prompt_only_h_changes": True,
            "error": None,
            "oracles": {
                "1": oracle(action_a),
                "2": oracle(action_a),
                "4": oracle(action_b if h4_sensitive else action_a),
                "8": oracle(action_b if h8_sensitive else action_a),
            },
        }

    rows = [
        row("ironclad", 0, True, True),
        row("ironclad", 1, False, False),
        row("silent", 0, True, True),
        row("silent", 1, False, False),
    ]
    first = select_frozen_advancements(rows, protocol)
    second = select_frozen_advancements(list(reversed(rows)), protocol)
    assert first["selected_fixture_ids"] == second["selected_fixture_ids"]
    assert len(first["selected_fixture_ids"]) == 4

    release = select_frozen_release(rows, protocol)
    assert release["release_gate_passed"]
    assert len(release["selected_fixture_ids"]) == 4
    failed = select_frozen_release(rows[:-1], protocol)
    assert not failed["release_gate_passed"]
    assert failed["selected_fixture_ids"] == []
    assert failed["shortfalls"]
    print("[PASS] frozen controlled-H funnel is deterministic and fails closed")


def test_controlled_horizon_silent_extension_is_digest_locked_and_next_ranked():
    import copy
    from scripts.controlled_horizon_pilot import load_frozen_protocol
    from scripts.controlled_horizon_silent_extension import (
        load_extension_protocol, select_extension_candidates)

    base, _base_digest = load_frozen_protocol()
    extension, digest = load_extension_protocol()
    assert digest == "43d9c7b37e41b1dbf3e3a066dfe0b868e063df54a35e6808dc9863aa9d617995"
    assert extension["supplementation"]["original_v2_gate_remains_failed"]
    assert extension["selection"]["fixture_count"] == 50

    base = copy.deepcopy(base)
    base["candidate_generation"]["characters"] = ["silent"]
    base["screen"]["screen_insensitive_advances_per_character"] = 1
    extension = copy.deepcopy(extension)
    extension["selection"]["fixture_count"] = 2
    extension["selection"]["offset_after_base_advanced"] = 1

    action = {"action": "end_turn", "card_index": -1, "target_index": -1}
    rows = []
    for ordinal in range(5):
        rows.append({
            "fixture": {
                "fixture_id": f"synthetic-silent-{ordinal}",
                "character": "silent",
            },
            "prompt_only_h_changes": True,
            "error": None,
            "oracles": {
                "1": {"optimal_actions": [action], "zero_span": False},
                "4": {"optimal_actions": [action], "zero_span": False},
            },
        })
    first = select_extension_candidates(rows, base, extension)
    second = select_extension_candidates(list(reversed(rows)), base, extension)
    assert first["rank_ordered_fixture_ids"] == second["rank_ordered_fixture_ids"]
    assert first["selection_count"] == 2
    assert first["available_unadvanced_pool_size"] == 4
    ranked = sorted(first["decisions"], key=lambda item: item["rank"])
    assert first["rank_ordered_fixture_ids"] == [
        item["fixture_id"] for item in ranked[:2]]
    assert sum(item["extension_selected"] for item in first["decisions"]) == 2
    print("[PASS] Silent extension is digest-locked and selects the next rank slice")


def test_controlled_horizon_combined_release_is_locked_and_control_only():
    import copy
    from scripts.controlled_horizon_combined_release import (
        load_combined_protocol, select_combined_release)
    from scripts.controlled_horizon_pilot import (
        load_frozen_protocol, select_frozen_release)

    base, _base_digest = load_frozen_protocol()
    combined, digest = load_combined_protocol()
    assert digest == "71461857bc2296e09769f8c886b0618ea3651757d438ff02bb4d8ab2380db99b"
    assert not combined["selection"]["extension_may_supply_h1_h8_sensitive"]
    assert combined["failure_policy"]["original_v2_gate_remains_failed"]

    base = copy.deepcopy(base)
    base["release"].update({
        "fixtures_per_character": 2,
        "h1_h8_sensitive_per_character": 1,
        "h1_h8_insensitive_per_character": 1,
        "minimum_sensitive_fraction": 0.2,
    })
    combined = copy.deepcopy(combined)
    combined["selection"].update({
        "fixtures_per_character": 2,
        "h1_h8_sensitive_per_character": 1,
        "h1_h8_insensitive_per_character": 1,
    })
    action_a = {"action": "end_turn", "card_index": -1, "target_index": -1}
    action_b = {"action": "play", "card_index": 0, "target_index": 0}

    def row(fixture_id, character, sensitive):
        def oracle(action, regret):
            return {
                "exact": True,
                "optimal_actions": [action],
                "zero_span": False,
                "baselines": {"h1_mismatched_oracle": {"regret": regret}},
            }
        return {
            "fixture": {"fixture_id": fixture_id, "character": character},
            "prompt_only_h_changes": True,
            "error": None,
            "oracles": {
                "1": oracle(action_a, 0),
                "2": oracle(action_a, 0),
                "4": oracle(action_a, 0),
                "8": oracle(action_b if sensitive else action_a,
                            1 if sensitive else 0),
            },
        }

    base_rows = [
        row("base-ic-sensitive", "ironclad", True),
        row("base-ic-control", "ironclad", False),
        row("base-silent-sensitive", "silent", True),
    ]
    extension_rows = [
        row("extension-silent-control", "silent", False),
        row("extension-silent-sensitive", "silent", True),
    ]
    assert not select_frozen_release(base_rows, base)["release_gate_passed"]
    release = select_combined_release(
        base_rows, extension_rows, base, combined)
    assert release["release_gate_passed"]
    assert len(release["selected_fixture_ids"]) == 4
    assert release["selected_source_counts"] == {
        "base": 3, "silent_control_extension": 1}
    assert release["allowed_extension_control_fixture_ids"] == [
        "extension-silent-control"]
    assert "extension-silent-sensitive" not in release["selected_fixture_ids"]
    print("[PASS] combined release is locked and accepts extension controls only")


def test_controlled_horizon_model_pilot_is_locked_balanced_and_model_blind():
    import copy
    import hashlib
    from scripts.controlled_horizon_model_pilot import (
        load_pilot_protocol, select_pilot_fixtures, validate_serving_stack)

    protocol, digest = load_pilot_protocol()
    assert digest == "465bab1dc23dddf5c5566c91943efaebc44ac3ab316ffb2003f15e01046a104f"
    assert protocol["inference"]["expected_query_count"] == 120
    assert protocol["decision_policy"]["confirmatory_matrix_reuses_pilot_responses"] is False
    assert protocol["pilot_gate"]["observed_effect_sign_used_for_go_no_go"] is False
    expected_stack = protocol["inference"]["serving_stack"]
    validate_serving_stack(protocol, {
        "vllm": expected_stack["vllm_version"],
        "transformers": expected_stack["transformers_version"],
    })
    try:
        validate_serving_stack(protocol, {
            "vllm": "wrong", "transformers": expected_stack["transformers_version"]})
        raise AssertionError("mismatched serving stack was accepted")
    except ValueError as exc:
        assert "vllm" in str(exc)

    protocol = copy.deepcopy(protocol)
    dispositions = []
    for character in ("ironclad", "silent"):
        for sensitive, count in ((True, 4), (False, 11)):
            for ordinal in range(count):
                dispositions.append({
                    "fixture_id": f"synthetic-{character}-{sensitive}-{ordinal}",
                    "character": character,
                    "h1_h8_sensitive": sensitive,
                    "released": True,
                })
    ids = sorted(item["fixture_id"] for item in dispositions)
    protocol["pilot_sample"]["selected_fixture_ids_sha256"] = hashlib.sha256(
        ("\n".join(ids) + "\n").encode("utf-8")).hexdigest()
    release = {
        "release_gate_passed": True,
        "selection": {"dispositions": dispositions},
    }
    first = select_pilot_fixtures(release, protocol)
    release["selection"]["dispositions"].reverse()
    second = select_pilot_fixtures(release, protocol)
    assert first == second
    assert len(first["selected_fixture_ids"]) == 30
    for character in ("ironclad", "silent"):
        character_rows = [item for item in first["decisions"]
                          if item["character"] == character]
        for position in range(4):
            counts = {
                horizon: sum(item["horizon_query_order"][position] == horizon
                             for item in character_rows)
                for horizon in (1, 2, 4, 8)
            }
            assert max(counts.values()) - min(counts.values()) <= 1
    print("[PASS] controlled-H model pilot is locked, balanced, and model-blind")


def test_controlled_horizon_pilot_scores_only_frozen_oracle_values():
    from scripts.controlled_horizon_model_pilot import score_precomputed_oracle

    oracle_row = {"oracles": {"8": {
        "exact": True,
        "best_value": 10.0,
        "worst_value": 0.0,
        "action_values": {"end_turn:-1:-1": 0.0, "play:0:0": 10.0},
    }}}
    scored = score_precomputed_oracle(
        oracle_row, 8,
        {"action": "play", "card_index": "0", "target_index": 0})
    assert scored["parse_ok"] and scored["schema_ok"] and scored["legal"]
    assert scored["normalized_quality"] == 1.0 and scored["regret"] == 0.0
    invalid = score_precomputed_oracle(
        oracle_row, 8,
        {"action": "play", "card_index": True, "target_index": 0})
    assert invalid["parse_ok"] and not invalid["schema_ok"] and not invalid["legal"]
    assert invalid["normalized_quality"] is None
    print("[PASS] model pilot scores against frozen values and rejects bad schema")


def test_controlled_horizon_pilot_normalizes_only_non_targeted_card_targets():
    from scripts.controlled_horizon_model_pilot import score_precomputed_oracle

    oracle_row = {"oracles": {"2": {
        "exact": True,
        "best_value": 10.0,
        "worst_value": 0.0,
        "action_values": {
            "end_turn:-1:-1": 0.0,
            "play:0:-1": 7.0,
            "play:1:0": 10.0,
            "play:1:1": 2.0,
        },
    }}}
    skill = score_precomputed_oracle(
        oracle_row, 2,
        {"action": "play", "card_index": 0, "target_index": 0})
    assert skill["legal"] and skill["chosen_action"]["target_index"] == 0
    assert skill["scored_action"]["target_index"] == -1
    assert skill["action_normalization"] == "ignored_target_for_non_targeted_card"
    wrong_enemy = score_precomputed_oracle(
        oracle_row, 2,
        {"action": "play", "card_index": 1, "target_index": 2})
    assert not wrong_enemy["legal"]
    assert wrong_enemy["scored_action"]["target_index"] == 2
    assert wrong_enemy["action_normalization"] is None
    print("[PASS] pilot normalizes only irrelevant non-targeted-card targets")


def test_controlled_horizon_checkpoint_rescore_preserves_original_score():
    import copy
    from scripts.controlled_horizon_model_pilot import (
        load_pilot_protocol, rescore_checkpoint)

    protocol, digest = load_pilot_protocol()
    fixture_id = "synthetic-rescore"
    response = {"action": "play", "card_index": 0, "target_index": 0}
    original_score = {
        "chosen_action": response,
        "parse_ok": True,
        "schema_ok": True,
        "legal": False,
        "chosen_value": None,
        "optimal_value": 10.0,
        "worst_value": 0.0,
        "regret": None,
        "normalized_quality": None,
        "oracle_exact": True,
    }
    report = {
        "protocol_digest": digest,
        "provider": protocol["inference"]["provider"],
        "completed_queries": 1,
        "rows": [{
            "fixture_id": fixture_id,
            "horizon": 1,
            "character": "ironclad",
            "response_parsed": response,
            "score": copy.deepcopy(original_score),
            "diagnostics": {"truncated": False},
        }],
    }
    oracle_rows = {fixture_id: {"oracles": {"1": {
        "exact": True,
        "best_value": 10.0,
        "worst_value": 0.0,
        "action_values": {"play:0:-1": 10.0},
    }}}}
    corrected = rescore_checkpoint(report, protocol, digest, oracle_rows)
    row = corrected["rows"][0]
    assert row["score_before_action_normalization"] == original_score
    assert row["score"]["legal"] and row["score"]["normalized_quality"] == 1.0
    assert corrected["scoring_correction"]["model_inference_performed"] is False
    assert corrected["scoring_correction"]["legality_changes"] == 1
    again = rescore_checkpoint(corrected, protocol, digest, oracle_rows)
    assert again["rows"][0]["score_before_action_normalization"] == original_score
    print("[PASS] checkpoint rescore is explicit, lossless, and idempotent")


def test_controlled_horizon_pilot_query_budget_checkpoints_and_resumes():
    import copy
    import hashlib
    from pathlib import Path
    from tempfile import TemporaryDirectory
    from scripts.controlled_horizon_model_pilot import (
        load_pilot_protocol, run_pilot)
    from slay_bench.benchmark import MockLLM
    from slay_bench.controlled_horizon import create_fixture

    protocol, _digest = load_pilot_protocol()
    protocol = copy.deepcopy(protocol)
    dispositions = []
    fixtures = {}
    oracle_rows = {}
    for char_index, character in enumerate(("ironclad", "silent")):
        for sensitive, count in ((True, 4), (False, 11)):
            for ordinal in range(count):
                fixture_id = f"budget-{character}-{sensitive}-{ordinal}"
                dispositions.append({
                    "fixture_id": fixture_id,
                    "character": character,
                    "h1_h8_sensitive": sensitive,
                    "released": True,
                })
                fixture, _state = create_fixture(
                    character, 70000 + char_index * 100 + len(fixtures),
                    ("Cultist",))
                fixture.fixture_id = fixture_id
                fixtures[fixture_id] = fixture
                oracle_rows[fixture_id] = {"oracles": {
                    str(horizon): {
                        "exact": True,
                        "best_value": 1.0,
                        "worst_value": 0.0,
                        "action_values": {"end_turn:-1:-1": 1.0},
                    }
                    for horizon in protocol["inference"]["horizons"]
                }}
    ids = sorted(item["fixture_id"] for item in dispositions)
    protocol["pilot_sample"]["selected_fixture_ids_sha256"] = hashlib.sha256(
        ("\n".join(ids) + "\n").encode("utf-8")).hexdigest()
    release = {
        "release_gate_passed": True,
        "selection": {"dispositions": dispositions},
    }
    llm = MockLLM([
        '{"action":"end_turn","card_index":-1,"target_index":-1}'
    ])
    with TemporaryDirectory() as directory:
        output = Path(directory) / "pilot.json"
        first = run_pilot(
            protocol, "test-protocol-digest", llm, "mock", release,
            fixtures, oracle_rows, output, max_new_queries=1)
        assert first["completed_queries"] == 1 and not first["complete"]
        assert first["action_scoring_version"] == "controlled-action-scoring-v2.1"
        second = run_pilot(
            protocol, "test-protocol-digest", llm, "mock", release,
            fixtures, oracle_rows, output, max_new_queries=1)
        assert second["completed_queries"] == 2 and not second["complete"]
        assert len({(row["fixture_id"], row["horizon"])
                    for row in second["rows"]}) == 2
    print("[PASS] controlled-H query budget checkpoints once and resumes")


def test_controlled_horizon_memoized_oracle_matches_full_tree():
    from slay_bench.controlled_horizon import create_fixture, exact_action_values

    _fixture, state = create_fixture("ironclad", 42000, ("Cultist",))
    full = exact_action_values(state, 4, node_budget=5000, memoize=False)
    memo = exact_action_values(state, 4, node_budget=5000, memoize=True)
    assert memo.action_values == full.action_values
    assert memo.optimal_actions == full.optimal_actions
    assert memo.nodes_expanded <= full.nodes_expanded
    assert memo.cache_hits > 0
    print("[PASS] controlled-H memoized oracle matches the full search tree")


def test_controlled_horizon_oracle_wall_time_fails_closed():
    from slay_bench.controlled_horizon import (
        OracleTimeBudgetExceeded, create_fixture, exact_action_values)

    _fixture, state = create_fixture("silent", 52000, ("Cultist",))
    try:
        exact_action_values(state, 8, wall_time_budget_s=1e-12)
        assert False, "wall-time truncation must not return an exact oracle"
    except OracleTimeBudgetExceeded as exc:
        assert "exceeded" in str(exc) and "H=8" in str(exc)
    print("[PASS] controlled-H wall-time limit fails closed")


def test_controlled_horizon_checkpoint_write_is_atomic():
    from tempfile import TemporaryDirectory
    from pathlib import Path
    from scripts.controlled_horizon_pilot import _atomic_write_json

    with TemporaryDirectory() as directory:
        target = Path(directory) / "audit.json"
        _atomic_write_json(target, {"rows": [{"fixture_id": "one"}]})
        assert json.loads(target.read_text(encoding="utf-8"))["rows"][0][
            "fixture_id"] == "one"
        assert not target.with_name(target.name + ".tmp").exists()
    print("[PASS] controlled-H checkpoint JSON uses atomic replacement")


def test_controlled_horizon_prompt_exposes_oracle_relevant_draw_order():
    """No identical model prompt may receive a different hidden-state oracle label."""
    import copy
    from slay_bench.controlled_horizon import (
        build_prompt, create_fixture, exact_action_values)

    deck = [
        "Strike_R", "Defend_R", "Bash", "Evolve", "Intimidate",
        "Seeing Red", "Battle Trance", "Double Tap", "Immolate",
        "Reckless Charge", "Bludgeon", "Impervious", "Offering",
        "Demon Form", "Cleave",
    ]
    _fixture, first = create_fixture(
        "ironclad", 424242, ("Cultist",), deck_names=deck)
    second = copy.deepcopy(first)
    second.combat.draw_pile[0], second.combat.draw_pile[6] = (
        second.combat.draw_pile[6], second.combat.draw_pile[0])
    # The ordinary game-facing prompt aliases these states.
    assert combat_state_structured(first) == combat_state_structured(second)
    assert combat_state_raw(first) == combat_state_raw(second)
    # Their oracle labels differ, so controlled-H must disambiguate them.
    one = exact_action_values(first, 2)
    two = exact_action_values(second, 2)
    assert one.optimal_actions != two.optimal_actions
    assert build_prompt(first, 2, "structured") != build_prompt(
        second, 2, "structured")
    assert build_prompt(first, 2, "raw") != build_prompt(second, 2, "raw")
    print("[PASS] controlled-H v2 exposes oracle-relevant hidden continuation state")


def test_turn_oracle_persists_exactness_and_fails_closed_on_budget():
    """A bound hit is visible and never serialized as an exact optimum."""
    from slay_bench import new_game, start_combat
    from slay_bench.benchmark import _exhaustive_best_sequence
    from slay_bench.enemies import Cultist

    state = new_game(42, "ironclad")
    start_combat(state, [Cultist(state.rng.hp_rng)])
    _dmg, _seq, full = _exhaustive_best_sequence(state, return_audit=True)
    assert full["exact"] and 0 < full["nodes_expanded"] < full["node_budget"]
    _dmg, _seq, bounded = _exhaustive_best_sequence(
        state, node_budget=1, return_audit=True)
    assert bounded == {"nodes_expanded": 1, "node_budget": 1, "exact": False}

    score = TurnEvaluator(MockLLM(['{"plays": []}'])).evaluate(state)
    sample = BenchmarkResult("m", "structured", 42, turn_scores=[score]).summary()["turn"]
    assert sample["oracle_inexact_n"] == 0
    assert sample["samples"][0]["oracle_exact"] is True
    assert sample["samples"][0]["oracle_nodes_expanded"] > 0
    print("[PASS] turn oracle exactness and node budget are persisted per sample")


def test_compute_free_turn_oracle_audit_reports_bounds():
    from scripts.instrument_diagnostics import turn_oracle_audit

    audit = turn_oracle_audit(base_seeds=(42,), n_per_base=2)
    for row in audit["by_character"].values():
        assert row["states"] == 2
        assert row["exact_states"] + row["bound_hits"] == 2
        assert row["max_nodes_expanded"] <= row["node_budget"]
    print("[PASS] compute-free turn oracle audit reports exactness by character")


def test_controlled_h_expansion_freeze_and_source_hashes():
    from pathlib import Path
    from tempfile import TemporaryDirectory
    import copy, hashlib
    from scripts.controlled_horizon_expansion import load_protocol, load_sources, FROZEN_DIGEST
    p, digest = load_protocol()
    assert digest == FROZEN_DIGEST
    assert p['release']['fixtures_per_character'] == 252
    assert not p['primary_planning_scope']['model_execution_authorized']
    with TemporaryDirectory() as directory:
        root = Path(directory)
        changed = copy.deepcopy(p)
        changed['release']['fixtures_per_character'] = 100
        path = root/'protocol.json'
        path.write_text(json.dumps(changed), encoding='utf-8')
        try:
            load_protocol(path)
            assert False, 'mutated freeze accepted'
        except ValueError:
            pass
        source = root/'source.json'
        source.write_text('{}', encoding='utf-8')
        spec = {'sources':{'test':{'filename':'source.json','sha256':hashlib.sha256(source.read_bytes()).hexdigest()}}}
        assert load_sources(spec,root) == {'test':{}}
        source.write_text('{"changed":true}',encoding='utf-8')
        try:
            load_sources(spec,root)
            assert False, 'modified source accepted'
        except ValueError:
            pass
    print('[PASS] expansion freeze and sources fail closed on mutation')


def test_controlled_h_expansion_resume_preserves_failures_and_rejects_tampering():
    import copy
    from dataclasses import asdict
    from pathlib import Path
    from tempfile import TemporaryDirectory
    from slay_bench.controlled_horizon import create_fixture
    from scripts.controlled_horizon_expansion import run_stage, load_protocol
    p,digest=load_protocol()
    fixtures=[create_fixture('ironclad',seed,('Cultist',),fixture_id=f'expansion-test-{seed}')[0]
              for seed in (9100,10100)]
    calls=[]
    def fake(f,h,n,w):
        calls.append(f.fixture_id)
        return {'fixture':asdict(f),'error':{'type':'OracleTimeBudgetExceeded'},'oracles':{}}
    with TemporaryDirectory() as directory:
        path=Path(directory)/'checkpoint.json'
        first=run_stage(p,digest,'screen',fixtures,p['screen'],path,{'bound':1},1,fake)
        assert not first['complete'] and len(calls)==1
        second=run_stage(p,digest,'screen',fixtures,p['screen'],path,{'bound':1},1,fake)
        assert second['complete'] and len(calls)==2
        run_stage(p,digest,'screen',fixtures,p['screen'],path,{'bound':1},1,fake)
        assert len(calls)==2, 'budget failures were retried'
        variants=[]
        duplicate=copy.deepcopy(second); duplicate['rows'][1]=duplicate['rows'][0]; variants.append(duplicate)
        wrong_recipe=copy.deepcopy(second); wrong_recipe['rows'][0]['fixture']['seed']+=1; variants.append(wrong_recipe)
        wrong_count=copy.deepcopy(second); wrong_count['completed_fixture_rows']=1; variants.append(wrong_count)
        wrong_binding=copy.deepcopy(second); wrong_binding['binding']={'bound':2}; variants.append(wrong_binding)
        for tampered in variants:
            path.write_text(json.dumps(tampered),encoding='utf-8')
            try:
                run_stage(p,digest,'screen',fixtures,p['screen'],path,{'bound':1},1,fake)
                assert False, 'tampered checkpoint accepted'
            except ValueError:
                pass
        assert len(calls)==2
    print('[PASS] expansion resume retains failed dispositions and rejects checkpoint drift')


def test_controlled_h_expansion_release_excludes_pilot_and_fails_closed():
    import copy
    from scripts.controlled_horizon_expansion import load_protocol, select_release
    p,_=load_protocol()
    p=copy.deepcopy(p)
    p['release'].update(fixtures_per_character=2,h1_h8_sensitive_per_character=1,h1_h8_insensitive_per_character=1)
    a={'action':'end_turn','card_index':-1,'target_index':-1}
    b={'action':'play','card_index':0,'target_index':0}
    rows=[]
    for char in ('ironclad','silent'):
        for sensitive in (False,True):
            fid=f'{char}-{sensitive}'
            rows.append({'fixture':{'fixture_id':fid,'character':char,'state_digest':fid},
                'error':None,'prompt_only_h_changes':True,
                'oracles':{str(h):{'exact':True,'zero_span':False,
                    'optimal_actions':[b if h==8 and sensitive else a],
                    'baselines':{'h1_mismatched_oracle':{'regret':1 if sensitive else 0}}}
                    for h in (1,2,4,8)}})
    passed,payload=select_release(p,rows[:2],rows[2:],set())
    assert passed['release_gate_passed'] and len(payload)==4
    reordered,reverse=select_release(p,list(reversed(rows)),[],set())
    assert payload==reverse
    failed,payload=select_release(p,rows[:-1],[],set())
    assert not failed['release_gate_passed'] and payload==[]
    zero=copy.deepcopy(rows); zero[0]['oracles']['8']['zero_span']=True
    assert not select_release(p,zero,[],set())[0]['release_gate_passed']
    for reused,new,excluded in ((rows,[],{rows[0]['fixture']['fixture_id']}),(rows,[rows[0]],set())):
        try:
            select_release(p,reused,new,excluded)
            assert False, 'pilot/duplicate fixture accepted'
        except ValueError:
            pass
    print('[PASS] expansion release rejects leakage, zero spans, and quota shortfalls')


if __name__ == "__main__":
    tests = [
        test_structured_prompt,
        test_raw_prompt,
        test_deck_relic_prompts,
        test_card_reward_prompts,
        test_exhaustive_search,
        test_simulate_play_sequence,
        test_mock_llm_responses,
        test_mock_llm_parse_failure,
        test_turn_evaluator_structured,
        test_turn_evaluator_raw,
        test_turn_evaluator_bad_parse,
        test_combat_evaluator_end_turn,
        test_combat_evaluator_play_attacks,
        test_synergy_evaluator,
        test_synergy_evaluator_raw,
        test_classify_archetype,
        test_draft_coherence,
        test_run_evaluator,
        test_harness_summary,
        test_harness_determinism,
        test_turn_evaluator_nonint_indices,
        test_synergy_evaluator_null_fields,
        test_character_propagates_to_evaluators,
        test_aggregation_keys_match_summary,
        test_synergy_fixture_ground_truth_rules,
        test_synergy_pick_position_debias,
        test_synergy_removal_constant_strike_confounded,
        test_synergy_archetype_multi_mention_scored_false,
        test_combat_hp_scored_before_combat_end_heal,
        test_turn_oracle_handles_more_than_six_playable,
        test_synergy_prompts_vary_across_base_seeds,
        test_intent_shows_effective_damage,
        test_turn_prompt_states_damage_objective,
        # 2026-06-11 audit
        test_duplicate_play_indices_are_illegal,
        # 2026-06-12 audit
        test_safe_int_float_strings,
        test_combat_negative_target_index_first_alive,
        test_synergy_summary_exposes_n_scored_denominators,
        test_run_tag_stem_suffix,
        # 2026-06-12 GPU prep — local provider adapter
        test_local_llm_builds_openai_request,
        test_local_llm_surfaces_server_error,
        test_build_llm_local_provider,
        # 2026-06-12b audit
        test_run_eval_keeps_partial_on_server_error,
        test_run_all_keeps_partial_on_dimension_error,
        test_complete_json_first_object_and_fast_on_garbage,
        test_act_transition_counts_llm_call_only_when_made,
        # 2026-07-12 parse-failure diagnostics
        test_complete_json_failure_diagnostics,
        test_combat_parse_error_split,
        test_turn_parse_fail_truncation_diagnostics,
        # 2026-07-13 per-sample diagnostics persistence
        test_per_sample_diagnostics_persisted,
        # 2026-08-30 adversarial research audit
        test_result_provenance_and_legacy_merge_are_explicit,
        test_invalid_cross_task_visuals_fail_closed,
        test_synergy_dictionary_shortcut_solves_all_fixed_fixtures,
        test_controlled_horizon_holds_state_and_action_contract_fixed,
        test_controlled_horizon_fixture_recipe_is_deterministic_and_fails_on_drift,
        test_controlled_horizon_pilot_generator_is_model_blind_and_deterministic,
        test_controlled_horizon_frozen_protocol_is_digest_locked_and_balanced,
        test_controlled_horizon_frozen_funnel_is_deterministic_and_fails_closed,
        test_controlled_horizon_silent_extension_is_digest_locked_and_next_ranked,
        test_controlled_horizon_combined_release_is_locked_and_control_only,
        test_controlled_horizon_model_pilot_is_locked_balanced_and_model_blind,
        test_controlled_horizon_pilot_scores_only_frozen_oracle_values,
        test_controlled_horizon_pilot_normalizes_only_non_targeted_card_targets,
        test_controlled_horizon_checkpoint_rescore_preserves_original_score,
        test_controlled_horizon_pilot_query_budget_checkpoints_and_resumes,
        test_controlled_horizon_memoized_oracle_matches_full_tree,
        test_controlled_horizon_oracle_wall_time_fails_closed,
        test_controlled_horizon_checkpoint_write_is_atomic,
        test_controlled_horizon_prompt_exposes_oracle_relevant_draw_order,
        test_turn_oracle_persists_exactness_and_fails_closed_on_budget,
        test_compute_free_turn_oracle_audit_reports_bounds,
        test_controlled_h_expansion_freeze_and_source_hashes,
        test_controlled_h_expansion_resume_preserves_failures_and_rejects_tampering,
        test_controlled_h_expansion_release_excludes_pilot_and_fails_closed,
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
    print(f"\n{'='*60}")
    print(f"Results: {passed} passed, {failed} failed")
