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
    try:
        d = build_llm("local", "m")
        assert d.base_url == "http://localhost:8000/v1"
    finally:
        if prev is not None:
            os.environ["LOCAL_BASE_URL"] = prev
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
