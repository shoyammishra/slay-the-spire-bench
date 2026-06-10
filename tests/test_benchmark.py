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
    print(f"[PASS] TurnEvaluator bad parse: parse_ok={score.parse_ok}")


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
    # Fixture 0 is the Strength deck; best pick idx 1, removal = Strike.
    mock = MockLLM(['{"archetype": "Strength", "best_card_index": 1, "worst_card_name": "Strike"}'])
    harness = BenchmarkHarness(mock, model_name="mock", prompt_format="structured")
    scores = harness.run_synergy_eval([42])  # one sample -> fixture 0
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
