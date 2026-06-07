"""
Benchmark harness for evaluating LLM planning on the Slay the Spire simulator.

Four evaluation dimensions:
  1. Turn-level   — freeze mid-combat, query LLM for optimal card sequence
  2. Combat-level — LLM plays full fight turn-by-turn
  3. Synergy      — static deck+relic snapshot, score archetype/card picks/removals
  4. Run-level    — LLM plays a full act end-to-end

LLM interface is abstract: plug in Groq, OpenRouter, or a mock for unit tests.
"""
from __future__ import annotations

import copy
import itertools
import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .prompt_builder import (
    combat_state_structured, combat_state_raw,
    deck_relic_structured, deck_relic_raw,
    card_reward_structured, card_reward_raw,
    SYSTEM_TURN, SYSTEM_COMBAT, SYSTEM_SYNERGY, SYSTEM_RUN,
)


# ── LLM interface ─────────────────────────────────────────────────────────────

class RateLimitExhausted(RuntimeError):
    """Raised when the API rate limit persists after all retries. The harness
    catches this and returns partial results instead of losing completed work."""


class LLMInterface(ABC):
    """Abstract LLM client. Implement `complete()` for any provider."""

    @abstractmethod
    def complete(self, system: str, user: str, **kwargs) -> str:
        """Return the model's text response."""

    def complete_json(self, system: str, user: str, **kwargs) -> dict:
        """Call complete() and parse JSON from the response."""
        raw = self.complete(system, user, **kwargs)
        # Strip <think>...</think> blocks (reasoning models like qwen3)
        import re as _re
        text = _re.sub(r'<think>.*?</think>', '', raw, flags=_re.DOTALL).strip()
        # Strip markdown fences if present
        if text.startswith("```"):
            lines = text.splitlines()
            text = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        # Try to extract the first valid JSON object from the text
        import re
        for m in re.finditer(r'\{', text):
            for end in range(len(text), m.start(), -1):
                candidate = text[m.start():end]
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    continue
        return {"error": "parse_failure", "raw": raw}


class GroqLLM(LLMInterface):
    """Groq API client (llama-3.1-8b-instant or llama-4-scout-17b)."""

    def __init__(self, model: str = "llama-3.1-8b-instant", api_key: Optional[str] = None):
        self.model = model
        self._api_key = api_key
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                from groq import Groq
                import os
                key = self._api_key or os.environ.get("GROQ_API_KEY")
                # max_retries=0: disable the SDK's own retry loop so OUR backoff
                # below is the single, predictable retry path (and converts a
                # persistent 429 into RateLimitExhausted for graceful partial save).
                self._client = Groq(api_key=key, max_retries=0)
            except ImportError:
                raise RuntimeError("pip install groq")
        return self._client

    @staticmethod
    def _is_rate_limit(e) -> bool:
        """Robustly detect a 429 from the groq SDK (typed first, strings as fallback)."""
        try:
            import groq
            if isinstance(e, groq.RateLimitError):
                return True
        except ImportError:
            pass
        # APIStatusError carries .status_code; httpx errors carry .response.status_code
        status = getattr(e, "status_code", None) or getattr(
            getattr(e, "response", None), "status_code", None)
        return status == 429 or "rate" in type(e).__name__.lower() \
            or "429" in str(e) or "rate limit" in str(e).lower()

    def complete(self, system: str, user: str, **kwargs) -> str:
        import time
        client = self._get_client()
        last_err = None
        attempts = 6
        for attempt in range(attempts):
            try:
                resp = client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    temperature=kwargs.get("temperature", 0.0),
                    max_tokens=kwargs.get("max_tokens", 3000),
                )
                return resp.choices[0].message.content
            except Exception as e:  # noqa: BLE001 — retry only on rate limits
                last_err = e
                if not self._is_rate_limit(e):
                    raise
                # Cap at 30s so later attempts cover a full per-minute reset
                # (1, 2, 4, 8, 16, 30 ≈ 61s total before giving up).
                wait = min(2 ** attempt, 30)
                print(f"    [rate limit] retry {attempt+1}/{attempts} in {wait}s...", flush=True)
                time.sleep(wait)
        # Out of retries — signal exhaustion so the harness can stop gracefully.
        raise RateLimitExhausted(str(last_err))


class OpenRouterLLM(LLMInterface):
    """OpenRouter API client (any model)."""

    def __init__(self, model: str, api_key: Optional[str] = None):
        self.model = model
        self._api_key = api_key

    def complete(self, system: str, user: str, **kwargs) -> str:
        import os, time, urllib.request, urllib.error
        key = self._api_key or os.environ.get("OPENROUTER_API_KEY")
        payload = json.dumps({
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": kwargs.get("temperature", 0.0),
            "max_tokens": kwargs.get("max_tokens", 8000),
        }).encode()
        last_err = None
        for attempt in range(5):
            try:
                req = urllib.request.Request(
                    "https://openrouter.ai/api/v1/chat/completions",
                    data=payload,
                    headers={
                        "Authorization": f"Bearer {key}",
                        "Content-Type": "application/json",
                    },
                )
                with urllib.request.urlopen(req, timeout=120) as r:
                    data = json.loads(r.read())
                return data["choices"][0]["message"]["content"]
            except urllib.error.HTTPError as e:
                last_err = e
                if e.code == 429:
                    wait = 2 ** attempt
                    print(f"    [rate limit] retry {attempt+1}/5 in {wait}s...", flush=True)
                    time.sleep(wait)
                elif e.code == 402:
                    raise RuntimeError(
                        "OpenRouter returned 402 Payment Required — "
                        "add credits at openrouter.ai/credits to use this model."
                    ) from e
                else:
                    raise
            except Exception as e:
                last_err = e
                wait = 2 ** attempt
                print(f"    [network error] retry {attempt+1}/5 in {wait}s: {e}", flush=True)
                time.sleep(wait)
        raise RateLimitExhausted(str(last_err))


class MockLLM(LLMInterface):
    """Deterministic mock for unit tests — returns scripted responses."""

    def __init__(self, responses: Optional[List[str]] = None):
        self._responses = list(responses or [])
        self._idx = 0
        self._calls: List[Tuple[str, str]] = []

    def complete(self, system: str, user: str, **kwargs) -> str:
        self._calls.append((system, user))
        if self._responses:
            resp = self._responses[self._idx % len(self._responses)]
            self._idx += 1
            return resp
        # Fallback: always end turn
        return '{"action": "end_turn", "reasoning": "mock"}'


# ── Scores ─────────────────────────────────────────────────────────────────────

@dataclass
class TurnScore:
    """Score for a single turn-level query."""
    optimal_damage: int
    llm_damage: int
    optimal_sequence: List[int]   # card indices
    llm_sequence: List[int]
    parse_ok: bool
    legal: bool                   # all plays were legal

    @property
    def damage_ratio(self) -> float:
        if self.optimal_damage == 0:
            return 1.0 if self.llm_damage == 0 else 0.0
        return min(1.0, self.llm_damage / self.optimal_damage)


@dataclass
class CombatScore:
    """Score for a single combat-level evaluation."""
    won: bool
    turns: int
    hp_remaining: int
    optimal_hp_remaining: Optional[int]   # from exhaustive solve (may be None)
    cards_played: int
    parse_errors: int

    @property
    def hp_ratio(self) -> float:
        if self.optimal_hp_remaining is None or self.optimal_hp_remaining <= 0:
            return 1.0 if self.hp_remaining > 0 else 0.0
        return max(0.0, self.hp_remaining / self.optimal_hp_remaining)


@dataclass
class SynergyScore:
    """Score for a synergy-recognition query."""
    archetype_correct: Optional[bool]          # None if not asked OR deck is ambiguous
    card_pick_correct: Optional[bool]          # picked the expert-labeled best card
    removal_correct: Optional[bool]            # removed the expert-labeled worst card
    parse_ok: bool
    expert_archetype: str = ""                 # the heuristic label (for audit)
    archetype_confident: bool = True           # False = ambiguous deck, excluded from acc
    model_archetype: str = ""                  # what the model answered (for audit)
    raw_response: dict = field(default_factory=dict)


@dataclass
class RunScore:
    """Score for a full-run evaluation."""
    survived: bool
    floors_reached: int
    final_hp: int
    max_hp: int
    gold: int
    deck_size: int
    # Sub-scores (computed post-hoc)
    draft_coherence: float = 0.0      # fraction of cards fitting dominant archetype
    route_optimality: float = 0.0     # placeholder: 1.0 if no unnecessary elites taken
    parse_errors: int = 0
    llm_calls: int = 0

    @property
    def hp_fraction(self) -> float:
        return max(0.0, self.final_hp / self.max_hp) if self.max_hp > 0 else 0.0


# ── Turn-level evaluator ──────────────────────────────────────────────────────

def _simulate_play_sequence(state_snapshot, sequence: List[int]) -> Tuple[int, bool]:
    """
    Simulate playing cards in the given index order on a deep-copied state.
    Returns (total_enemy_hp_lost, all_legal).
    """
    from .combat import play_card, is_combat_over
    import copy

    s = copy.deepcopy(state_snapshot)
    c = s.combat
    initial_enemy_hp = sum(e.hp for e in c.enemies if e.hp > 0)

    # Snapshot cards by their original index so hand-shifting doesn't corrupt lookups
    initial_hand = list(c.hand)

    for idx in sequence:
        if idx >= len(initial_hand):
            return (initial_enemy_hp - sum(e.hp for e in c.enemies if e.hp > 0), False)
        card = initial_hand[idx]
        if card not in c.hand:
            return (initial_enemy_hp - sum(e.hp for e in c.enemies if e.hp > 0), False)
        if not card.can_play(s):
            return (initial_enemy_hp - sum(e.hp for e in c.enemies if e.hp > 0), False)
        target = next((e for e in c.enemies if e.hp > 0), None)
        play_card(s, card, target)
        if is_combat_over(s):
            break

    final_enemy_hp = sum(e.hp for e in c.enemies if e.hp > 0)
    return (initial_enemy_hp - final_enemy_hp, True)


def _exhaustive_best_sequence(state_snapshot) -> Tuple[int, List[int]]:
    """
    Enumerate all permutations of playable cards (up to 6 cards to keep it tractable).
    Returns (best_damage, best_sequence).
    """
    c = state_snapshot.combat
    playable_indices = [i for i, card in enumerate(c.hand) if card.can_play(state_snapshot)]

    # Cap at 6 to avoid factorial explosion (720 permutations max)
    cap = playable_indices[:6]

    best_dmg = 0
    best_seq: List[int] = []

    for length in range(len(cap) + 1):
        for perm in itertools.permutations(cap, length):
            dmg, legal = _simulate_play_sequence(state_snapshot, list(perm))
            if legal and dmg > best_dmg:
                best_dmg = dmg
                best_seq = list(perm)

    return best_dmg, best_seq


class TurnEvaluator:
    """
    Freeze a combat at the start of a turn, query the LLM for the optimal
    card sequence, and score it against exhaustive search.
    """

    def __init__(self, llm: LLMInterface, prompt_format: str = "structured"):
        self.llm = llm
        self.prompt_format = prompt_format  # "structured" | "raw"

    def evaluate(self, state) -> TurnScore:
        """Score a single turn. state must be in a valid mid-combat position."""
        import copy
        snapshot = copy.deepcopy(state)

        # Build prompt
        if self.prompt_format == "raw":
            context = combat_state_raw(state)
        else:
            context = combat_state_structured(state)

        user_prompt = (
            context + "\n\n"
            "List the indices of cards from your hand you want to play this turn, in order. "
            "Output JSON: {\"plays\": [<indices>], \"reasoning\": \"<brief>\"}"
        )

        resp = self.llm.complete_json(SYSTEM_TURN, user_prompt)

        parse_ok = "plays" in resp and "error" not in resp
        llm_sequence = resp.get("plays", []) if parse_ok else []
        if not isinstance(llm_sequence, list):
            llm_sequence = []
            parse_ok = False

        # Score LLM sequence
        llm_dmg, llm_legal = _simulate_play_sequence(snapshot, llm_sequence)

        # Optimal via exhaustive search
        opt_dmg, opt_seq = _exhaustive_best_sequence(snapshot)

        # Illegal sequence: credit partial damage but cap ratio at 0 so it
        # doesn't artificially inflate the score for a sequence that cheated.
        if not llm_legal:
            llm_dmg = 0

        return TurnScore(
            optimal_damage=opt_dmg,
            llm_damage=llm_dmg,
            optimal_sequence=opt_seq,
            llm_sequence=llm_sequence,
            parse_ok=parse_ok,
            legal=llm_legal,
        )


# ── Combat-level evaluator ─────────────────────────────────────────────────────

def _safe_int(v, default: int = 0) -> int:
    """Coerce an LLM-supplied index to an int. Models sometimes return null, a
    string, a float, or omit the field — all become `default` (0 = first option)."""
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


class CombatEvaluator:
    """LLM plays a full combat from start to finish, turn by turn."""

    def __init__(self, llm: LLMInterface, prompt_format: str = "structured",
                 max_turns: int = 50):
        self.llm = llm
        self.prompt_format = prompt_format
        self.max_turns = max_turns

    def evaluate(self, state, enemies: List) -> CombatScore:
        from .combat import start_combat, play_card, end_player_turn, is_combat_over, end_combat

        start_combat(state, enemies)
        # Greedy baseline on the identical post-start state (own RNG copy)
        optimal_hp = _greedy_combat_hp(state, self.max_turns)
        parse_errors = 0
        cards_played = 0
        turns = 0

        for _ in range(self.max_turns):
            outcome = is_combat_over(state)
            if outcome:
                break

            turns += 1
            turn_done = False

            while not turn_done:
                if self.prompt_format == "raw":
                    context = combat_state_raw(state)
                else:
                    context = combat_state_structured(state)

                user_prompt = (
                    context + "\n\n"
                    "What is your next action? "
                    "Output JSON: {\"action\": \"play\"|\"end_turn\", \"card_index\": <int>, "
                    "\"target_index\": <int>, \"reasoning\": \"<brief>\"}"
                )

                resp = self.llm.complete_json(SYSTEM_COMBAT, user_prompt)

                if "error" in resp:
                    parse_errors += 1
                    end_player_turn(state)
                    turn_done = True
                    continue

                action = resp.get("action", "end_turn")

                if action == "end_turn":
                    end_player_turn(state)
                    turn_done = True

                elif action == "play":
                    idx = _safe_int(resp.get("card_index", 0))
                    target_idx = _safe_int(resp.get("target_index", 0))
                    hand = state.combat.hand
                    if not (0 <= idx < len(hand)):
                        parse_errors += 1
                        end_player_turn(state)
                        turn_done = True
                        continue
                    card = hand[idx]
                    enemies_alive = [e for e in state.combat.enemies if e.hp > 0]
                    target = enemies_alive[target_idx] if target_idx < len(enemies_alive) else (
                        enemies_alive[0] if enemies_alive else None)
                    if card.can_play(state):
                        play_card(state, card, target)
                        cards_played += 1
                    else:
                        parse_errors += 1
                        end_player_turn(state)
                        turn_done = True
                else:
                    parse_errors += 1
                    end_player_turn(state)
                    turn_done = True

                outcome = is_combat_over(state)
                if outcome:
                    turn_done = True

        outcome = is_combat_over(state)
        won = outcome == "win"
        if won:
            end_combat(state)

        return CombatScore(
            won=won,
            turns=turns,
            hp_remaining=state.player.hp,
            optimal_hp_remaining=optimal_hp,
            cards_played=cards_played,
            parse_errors=parse_errors,
        )


# ── Synergy evaluator ─────────────────────────────────────────────────────────

# Expert archetype labels: map of key card names → archetype
_ARCHETYPES = {
    "Strength": [
        "Limit Break", "Inflame", "Demon Form", "Heavy Blade", "Whirlwind",
        "Flex", "Sword Boomerang", "Dropkick", "Thunderclap", "Uppercut",
        "Bludgeon", "Carnage", "Anger", "Hemokinesis",
    ],
    "Block": [
        "Barricade", "Entrench", "Body Slam", "Juggernaut", "Impervious",
        "Iron Wave", "Shrug It Off", "True Grit", "Ghostly Armor", "Sentinel",
        "Power Through", "Second Wind", "Warcry", "Seeing Red",
    ],
    "Exhaust": [
        "Feel No Pain", "Dark Embrace", "Corruption", "Dead Branch", "Offering",
        "Armaments", "Fiend Fire", "Immolate", "Reaper", "Brutality",
        "Evolve", "Headbutt", "Sever Soul",
    ],
    "Aggro": [
        "Perfected Strike", "Twin Strike", "Wild Strike", "Pommel Strike", "Clash",
        "Cleave", "Clothesline", "Reckless Charge", "Blood for Blood",
        "Rampage", "Searing Blow", "Havoc", "Battle Trance",
    ],
}

# Signature "payoff" cards that define an archetype far more strongly than generic
# support cards. A single payoff outweighs several commons in classification — this
# fixes the bias where the over-stuffed Aggro bucket (full of generic Strike-variants
# that appear in any random draft) captured nearly every deck.
_ARCHETYPE_PAYOFFS = {
    "Strength": {"Demon Form", "Limit Break", "Inflame", "Heavy Blade", "Whirlwind"},
    "Block":    {"Barricade", "Body Slam", "Juggernaut", "Entrench", "Impervious"},
    "Exhaust":  {"Corruption", "Feel No Pain", "Dark Embrace", "Dead Branch", "Fiend Fire"},
    "Aggro":    {"Perfected Strike", "Rampage", "Blood for Blood", "Reckless Charge"},
}

_PAYOFF_WEIGHT = 3.0
_SUPPORT_WEIGHT = 1.0


def _classify_archetype(deck: List, relics: List) -> str:
    """Heuristically label the deck's dominant archetype.

    Payoff cards are weighted 3x over generic support cards so the label reflects
    what the deck is actually built around, not which bucket has the most filler
    commons. Duplicates count once (presence, not quantity)."""
    relic_names = {r.name for r in relics}
    scores: Dict[str, float] = {arch: 0.0 for arch in _ARCHETYPES}
    deck_set = {c.name for c in deck}
    for arch, keys in _ARCHETYPES.items():
        payoffs = _ARCHETYPE_PAYOFFS.get(arch, set())
        for key in keys:
            if key in deck_set:
                scores[arch] += _PAYOFF_WEIGHT if key in payoffs else _SUPPORT_WEIGHT
    # Relic bonuses
    if "Barricade" in relic_names or "Calipers" in relic_names:
        scores["Block"] += 2.0
    if "Brimstone" in relic_names:
        scores["Strength"] += 2.0
    best = max(scores, key=lambda k: scores[k])
    return best if scores[best] > 0 else "Aggro"


def _classify_archetype_confident(deck: List, relics: List) -> Tuple[str, bool]:
    """Label the deck's archetype using *signature* cards only, and report whether
    that label is trustworthy.

    The plain `_classify_archetype` always returns *something* (needed for draft
    coherence / best-pick), but for scoring "did the model identify the archetype?"
    we must not penalize the model when the deck has no real archetype. A deck is
    only confidently labeled when exactly one archetype owns the most signature
    (payoff) cards — relics count as a signature. Otherwise (no payoff at all, or a
    tie between archetypes) the deck is genuinely ambiguous and is excluded from
    archetype accuracy.

    Returns (label, confident). When not confident, `label` is the best-effort
    `_classify_archetype` value, kept only for display/audit."""
    relic_names = {r.name for r in relics}
    deck_set = {c.name for c in deck}
    sig: Dict[str, int] = {arch: 0 for arch in _ARCHETYPES}
    for arch in _ARCHETYPES:
        sig[arch] = sum(1 for c in _ARCHETYPE_PAYOFFS.get(arch, set()) if c in deck_set)
    if "Barricade" in relic_names or "Calipers" in relic_names:
        sig["Block"] += 1
    if "Brimstone" in relic_names:
        sig["Strength"] += 1

    ranked = sorted(sig.items(), key=lambda kv: kv[1], reverse=True)
    top_arch, top_n = ranked[0]
    runner_n = ranked[1][1]
    confident = top_n > 0 and top_n > runner_n
    label = top_arch if confident else _classify_archetype(deck, relics)
    return label, confident


def _draft_coherence(deck: List, archetype: str) -> float:
    """Fraction of non-basic cards that belong to the archetype."""
    keys = set(_ARCHETYPES.get(archetype, []))
    basics = {"Strike", "Defend"}
    non_basic = [c for c in deck if c.name not in basics]
    if not non_basic:
        return 0.0
    hits = sum(1 for c in non_basic if c.name in keys)
    return hits / len(non_basic)


def _expert_best_card_index(offers: List, deck: List, relics: List) -> int:
    """Heuristic 'expert' best pick: favors the dominant archetype, then rarity."""
    from .enums import CardRarity
    archetype = _classify_archetype(deck, relics)
    keys = set(_ARCHETYPES.get(archetype, []))
    rarity_w = {
        CardRarity.RARE: 2.0, CardRarity.UNCOMMON: 1.0, CardRarity.COMMON: 0.0,
        CardRarity.BASIC: -1.0, CardRarity.SPECIAL: -5.0, CardRarity.CURSE: -10.0,
    }
    best_i, best_score = 0, float("-inf")
    for i, c in enumerate(offers):
        score = rarity_w.get(c.rarity, 0.0)
        if c.name in keys:
            score += 3.0
        if getattr(c, "upgraded", False):
            score += 0.5
        if score > best_score:
            best_score, best_i = score, i
    return best_i


def _archetype_draft_fn(target_archetype: str):
    """Return a card_choice_fn that drafts *toward* a target archetype.

    Prefers the archetype's payoff cards, then its support cards, then falls back
    to the highest-rarity non-curse offer. This produces a deck with a coherent,
    identifiable strategy — so 'archetype accuracy' tests real recognition instead
    of agreement on a random pile of greedy first-picks."""
    from .enums import CardRarity, CardType
    keys = set(_ARCHETYPES.get(target_archetype, []))
    payoffs = _ARCHETYPE_PAYOFFS.get(target_archetype, set())
    rarity_w = {
        CardRarity.RARE: 2.0, CardRarity.UNCOMMON: 1.0, CardRarity.COMMON: 0.0,
        CardRarity.BASIC: -1.0, CardRarity.SPECIAL: -5.0, CardRarity.CURSE: -10.0,
    }

    def pick(offers):
        best, best_score = None, float("-inf")
        for c in offers:
            if c.type == CardType.CURSE:
                continue
            score = rarity_w.get(c.rarity, 0.0)
            if c.name in payoffs:
                score += 20.0
            elif c.name in keys:
                score += 10.0
            if score > best_score:
                best_score, best = score, c
        return best

    return pick


def _expert_worst_card_name(deck: List) -> Optional[str]:
    """Heuristic 'expert' removal target: curses first, then basic Strike, then Defend."""
    from .enums import CardType
    for c in deck:
        if c.type == CardType.CURSE:
            return c.name
    for target in ("Strike", "Defend"):
        for c in deck:
            if c.name == target:
                return c.name
    return None


def _greedy_combat_hp(state_after_start, max_turns: int = 50) -> int:
    """
    Non-LLM reference: play the same combat with a simple greedy AI
    (play every playable card each turn) on a deep copy. Returns HP remaining
    (0 on loss). Used as the 'optimal' baseline for CombatScore.hp_ratio.
    """
    from .combat import play_card, end_player_turn, is_combat_over
    import copy
    s = copy.deepcopy(state_after_start)
    for _ in range(max_turns):
        if is_combat_over(s):
            break
        played = True
        while played:
            played = False
            for card in list(s.combat.hand):
                target = next((e for e in s.combat.enemies if e.hp > 0), None)
                if target and card.can_play(s):
                    play_card(s, card, target)
                    played = True
                    if is_combat_over(s):
                        break
                    break
        if is_combat_over(s):
            break
        end_player_turn(s)
    return max(0, s.player.hp)


class SynergyEvaluator:
    """
    Static evaluation: show a deck + relic snapshot, ask the LLM three questions.
    Score vs. expert labels (heuristic archetype + simulated card value).
    """

    def __init__(self, llm: LLMInterface, prompt_format: str = "structured"):
        self.llm = llm
        self.prompt_format = prompt_format

    def evaluate(self, state, card_offers: List, expert_pick_idx: Optional[int] = None,
                 expert_remove_name: Optional[str] = None) -> SynergyScore:

        expert_archetype, archetype_confident = _classify_archetype_confident(
            state.player.deck, state.player.relics)
        # Derive real expert labels when callers don't supply hand-labeled data
        if expert_pick_idx is None and card_offers:
            expert_pick_idx = _expert_best_card_index(
                card_offers, state.player.deck, state.player.relics)
        if expert_remove_name is None:
            expert_remove_name = _expert_worst_card_name(state.player.deck)

        if self.prompt_format == "raw":
            context = deck_relic_raw(state) + "\n\n" + card_reward_raw(
                card_offers, state.player.deck, state.player.relics)
        else:
            context = deck_relic_structured(state) + "\n\n" + card_reward_structured(
                card_offers, state.player.deck, state.player.relics)

        user_prompt = (
            context + "\n\n"
            "Answer three questions:\n"
            "1. What is the deck's primary archetype? (one of: Strength, Block, Exhaust, Aggro)\n"
            "2. Which offered card (by index 0,1,2) is the best addition to this deck?\n"
            "3. Which card in the current deck should be removed first (exact name)?\n\n"
            "Output JSON: {\"archetype\": \"...\", \"best_card_index\": <int>, "
            "\"worst_card_name\": \"...\"}"
        )

        resp = self.llm.complete_json(SYSTEM_SYNERGY, user_prompt)
        parse_ok = "error" not in resp

        archetype_correct = None
        card_pick_correct = None
        removal_correct = None
        model_archetype = ""

        if parse_ok:
            model_archetype = resp.get("archetype", "").strip()
            # Only score archetype ID when the deck has a real, unambiguous archetype.
            # Ambiguous decks (no signature card, or a tie) stay None → excluded from acc.
            if archetype_confident:
                # Substring match: accept "Block", "Block deck", "Defensive / Block", etc.
                # Archetype names are mutually non-overlapping, so `in` is unambiguous.
                archetype_correct = expert_archetype.lower() in model_archetype.lower()

            if expert_pick_idx is not None:
                pick = resp.get("best_card_index")
                card_pick_correct = pick == expert_pick_idx

            if expert_remove_name is not None:
                removal = resp.get("worst_card_name", "")
                removal_correct = removal.strip().lower() == expert_remove_name.lower()

        return SynergyScore(
            archetype_correct=archetype_correct,
            card_pick_correct=card_pick_correct,
            removal_correct=removal_correct,
            parse_ok=parse_ok,
            expert_archetype=expert_archetype,
            archetype_confident=archetype_confident,
            model_archetype=model_archetype,
            raw_response=resp,
        )


# ── Run-level evaluator ───────────────────────────────────────────────────────

class RunEvaluator:
    """
    LLM plays a full act from start to boss.
    Scores: survival, HP fraction, draft coherence, route optimality.
    """

    def __init__(self, llm: LLMInterface, prompt_format: str = "structured",
                 max_combat_turns: int = 50):
        self.llm = llm
        self.prompt_format = prompt_format
        self.max_combat_turns = max_combat_turns

    def _llm_card_choice(self, state, offers: List):
        """LLM picks a card from reward offers."""
        if not offers:
            return None
        if self.prompt_format == "raw":
            context = card_reward_raw(offers, state.player.deck, state.player.relics)
        else:
            context = card_reward_structured(offers, state.player.deck, state.player.relics)

        user_prompt = (
            context + "\n\n"
            "Which card do you pick? (0-indexed, or -1 to skip)\n"
            "Output JSON: {\"pick\": <int>, \"reasoning\": \"...\"}"
        )
        resp = self.llm.complete_json(SYSTEM_RUN, user_prompt)
        idx = resp.get("pick", -1)
        if isinstance(idx, int) and 0 <= idx < len(offers):
            return offers[idx]
        return None

    def _llm_combat(self, state) -> Tuple[bool, int]:
        """Run a full combat with LLM decisions. Returns (won, turns)."""
        from .combat import play_card, end_player_turn, is_combat_over, end_combat
        parse_errors = 0
        turns = 0

        for _ in range(self.max_combat_turns):
            outcome = is_combat_over(state)
            if outcome:
                won = outcome == "win"
                if won:
                    end_combat(state)
                return won, turns

            turns += 1
            turn_done = False

            while not turn_done:
                if self.prompt_format == "raw":
                    context = combat_state_raw(state)
                else:
                    context = combat_state_structured(state)

                user_prompt = (
                    context + "\n\n"
                    "Next action? JSON: {\"action\": \"play\"|\"end_turn\", "
                    "\"card_index\": <int>, \"target_index\": <int>, \"reasoning\": \"...\"}"
                )
                resp = self.llm.complete_json(SYSTEM_COMBAT, user_prompt)

                if "error" in resp or resp.get("action") == "end_turn":
                    if "error" in resp:
                        parse_errors += 1
                    end_player_turn(state)
                    turn_done = True
                elif resp.get("action") == "play":
                    idx = _safe_int(resp.get("card_index", 0))
                    tidx = _safe_int(resp.get("target_index", 0))
                    hand = state.combat.hand
                    if 0 <= idx < len(hand) and hand[idx].can_play(state):
                        enemies_alive = [e for e in state.combat.enemies if e.hp > 0]
                        target = enemies_alive[tidx] if tidx < len(enemies_alive) else (
                            enemies_alive[0] if enemies_alive else None)
                        play_card(state, hand[idx], target)
                    else:
                        parse_errors += 1
                        end_player_turn(state)
                        turn_done = True
                else:
                    parse_errors += 1
                    end_player_turn(state)
                    turn_done = True

                if is_combat_over(state):
                    turn_done = True

        # timeout — clean up stale combat state
        from .combat import end_combat
        if state.combat is not None:
            end_combat(state)
        return False, turns

    def evaluate(self, state, act: int = 1) -> RunScore:
        from .map_gen import generate_map
        from .run_loop import RunState, roll_encounter, spawn_enemies
        from .rewards import generate_card_reward, gold_reward, potion_drop
        from .events import Event
        from .nodes import resolve_rest, RestSiteAction, resolve_treasure
        from .events_pool import random_event, resolve_event
        from .enums import NodeType
        from .combat import start_combat

        game_map = generate_map(act, state.rng.map_rng)
        run = RunState(state, game_map)
        state.act = act

        parse_errors = 0
        llm_calls = 0
        floors_visited = 0
        elite_nodes_taken = 0

        def process_node(node):
            nonlocal parse_errors, llm_calls, floors_visited, elite_nodes_taken
            floors_visited += 1
            ntype = node.node_type

            if ntype in (NodeType.MONSTER, NodeType.ELITE, NodeType.BOSS):
                if ntype == NodeType.ELITE:
                    elite_nodes_taken += 1
                enemy_type = {
                    NodeType.MONSTER: "normal",
                    NodeType.ELITE: "elite",
                    NodeType.BOSS: "boss",
                }[ntype]
                enemy_ids = roll_encounter(state, ntype)
                enemies = spawn_enemies(state, enemy_ids)
                start_combat(state, enemies)
                won, turns = self._llm_combat(state)
                if won:
                    gold = gold_reward(state, enemy_type)
                    state.player.gold += gold
                    state.bus.emit(Event.GOLD_GAINED, state, amount=gold)
                    if ntype == NodeType.BOSS:
                        state.bus.emit(Event.BOSS_DEFEATED, state)
                    offers = generate_card_reward(state)
                    chosen = self._llm_card_choice(state, offers)
                    llm_calls += 1
                    if chosen:
                        state.player.deck.append(chosen)
                        state.bus.emit(Event.CARD_ADDED, state, card=chosen)
                    if potion_drop(state, enemy_type) and len(state.player.potions) < 3:
                        from .potions import random_potion
                        state.player.potions.append(random_potion(state))
                    return won
                return False

            elif ntype == NodeType.REST:
                resolve_rest(state, RestSiteAction.REST)

            elif ntype == NodeType.TREASURE:
                resolve_treasure(state)

            elif ntype == NodeType.EVENT:
                event = random_event(state)
                resolve_event(state, event, 0)

            return True

        # Traverse floors (greedy: pick first available node each floor)
        current_nodes = game_map.floors[0] if game_map.floors else []
        if not current_nodes:
            return RunScore(survived=False, floors_reached=0,
                            final_hp=state.player.hp, max_hp=state.player.max_hp,
                            gold=state.player.gold, deck_size=len(state.player.deck))

        current_node = current_nodes[0]
        run.move_to(current_node)
        visited = set()
        queue = [current_node]

        while queue:
            node = queue.pop(0)
            if id(node) in visited:
                continue
            visited.add(id(node))
            run.move_to(node)

            ok = process_node(node)
            if not ok or state.player.hp <= 0:
                archetype = _classify_archetype(state.player.deck, state.player.relics)
                return RunScore(
                    survived=False,
                    floors_reached=floors_visited,
                    final_hp=state.player.hp,
                    max_hp=state.player.max_hp,
                    gold=state.player.gold,
                    deck_size=len(state.player.deck),
                    draft_coherence=_draft_coherence(state.player.deck, archetype),
                    parse_errors=parse_errors,
                    llm_calls=llm_calls,
                )

            # Exclude the boss; it is fought once in the dedicated block below
            next_nodes = [n for n in run.available_next_nodes()
                          if n is not game_map.boss_node]
            if next_nodes:
                queue.append(next_nodes[0])

        # Boss
        survived = False
        if game_map.boss_node:
            run.move_to(game_map.boss_node)
            ok = process_node(game_map.boss_node)
            if ok and state.player.hp > 0:
                state.bus.emit(Event.ACT_END, state)
                survived = True

        archetype = _classify_archetype(state.player.deck, state.player.relics)
        return RunScore(
            survived=survived,
            floors_reached=floors_visited,
            final_hp=state.player.hp,
            max_hp=state.player.max_hp,
            gold=state.player.gold,
            deck_size=len(state.player.deck),
            draft_coherence=_draft_coherence(state.player.deck, archetype),
            parse_errors=parse_errors,
            llm_calls=llm_calls,
        )


# ── Master harness ─────────────────────────────────────────────────────────────

@dataclass
class BenchmarkResult:
    model_name: str
    prompt_format: str
    seed: int
    turn_scores: List[TurnScore] = field(default_factory=list)
    combat_scores: List[CombatScore] = field(default_factory=list)
    synergy_scores: List[SynergyScore] = field(default_factory=list)
    run_scores: List[RunScore] = field(default_factory=list)
    elapsed_seconds: float = 0.0

    def summary(self) -> dict:
        def avg(lst):
            return sum(lst) / len(lst) if lst else None

        turn = {
            "n": len(self.turn_scores),
            "avg_damage_ratio": avg([s.damage_ratio for s in self.turn_scores]),
            "parse_ok_rate": avg([float(s.parse_ok) for s in self.turn_scores]),
            "legal_rate": avg([float(s.legal) for s in self.turn_scores]),
        } if self.turn_scores else None

        combat = {
            "n": len(self.combat_scores),
            "win_rate": avg([float(s.won) for s in self.combat_scores]),
            "avg_hp_ratio": avg([s.hp_ratio for s in self.combat_scores]),
            "avg_parse_errors": avg([s.parse_errors for s in self.combat_scores]),
        } if self.combat_scores else None

        synergy = {
            "n": len(self.synergy_scores),
            "archetype_acc": avg([float(s.archetype_correct)
                                  for s in self.synergy_scores
                                  if s.archetype_correct is not None]),
            "archetype_n_scored": sum(1 for s in self.synergy_scores
                                      if s.archetype_correct is not None),
            "archetype_n_ambiguous": sum(1 for s in self.synergy_scores
                                         if s.parse_ok and not s.archetype_confident),
            "card_pick_acc": avg([float(s.card_pick_correct)
                                  for s in self.synergy_scores
                                  if s.card_pick_correct is not None]),
            "removal_acc": avg([float(s.removal_correct)
                                for s in self.synergy_scores
                                if s.removal_correct is not None]),
            "parse_ok_rate": avg([float(s.parse_ok) for s in self.synergy_scores]),
            "samples": [
                {
                    "expert_archetype": s.expert_archetype,
                    "model_archetype": s.model_archetype,
                    "confident": s.archetype_confident,
                    "archetype_correct": s.archetype_correct,
                    "card_pick_correct": s.card_pick_correct,
                    "removal_correct": s.removal_correct,
                }
                for s in self.synergy_scores
            ],
        } if self.synergy_scores else None

        ACT1_FLOORS = 15
        survivors = [s for s in self.run_scores if s.survived]
        run = {
            "n": len(self.run_scores),
            "survival_rate": avg([float(s.survived) for s in self.run_scores]),
            # HP fraction only meaningful for survivors; 0 on death misleads
            "avg_hp_fraction": avg([s.hp_fraction for s in survivors]) if survivors else 0.0,
            "avg_draft_coherence": avg([s.draft_coherence for s in self.run_scores]),
            "avg_floors_reached": avg([s.floors_reached for s in self.run_scores]),
            # Progress fraction: floors reached ÷ total act floors (rewards partial credit)
            "avg_progress": avg([min(1.0, s.floors_reached / ACT1_FLOORS) for s in self.run_scores]),
        } if self.run_scores else None

        return {
            "model": self.model_name,
            "prompt_format": self.prompt_format,
            "seed": self.seed,
            "elapsed_seconds": round(self.elapsed_seconds, 2),
            "turn": turn,
            "combat": combat,
            "synergy": synergy,
            "run": run,
        }


class BenchmarkHarness:
    """
    Orchestrates all 4 evaluation dimensions for a single (model, prompt_format) pair.

    Usage:
        llm = GroqLLM("llama-3.1-8b-instant")
        harness = BenchmarkHarness(llm, model_name="llama-3.1-8b", prompt_format="structured")
        result = harness.run_all(seed=42, n_turn=5, n_combat=3, n_synergy=3, n_run=1)
        print(json.dumps(result.summary(), indent=2))
    """

    def __init__(self, llm: LLMInterface, model_name: str = "unknown",
                 prompt_format: str = "structured"):
        self.llm = llm
        self.model_name = model_name
        self.prompt_format = prompt_format

    def run_turn_eval(self, seeds: List[int]) -> List[TurnScore]:
        """Evaluate turn-level planning on mid-combat snapshots."""
        from slay_bench import new_ironclad_game, start_combat
        from slay_bench.enemies import Cultist, JawWorm

        evaluator = TurnEvaluator(self.llm, self.prompt_format)
        scores = []
        for i, seed in enumerate(seeds):
            print(f"  [turn {i+1}/{len(seeds)}] seed={seed}", flush=True)
            state = new_ironclad_game(seed)
            enemy = Cultist(state.rng.hp_rng)
            start_combat(state, [enemy])
            score = evaluator.evaluate(state)
            scores.append(score)
            print(f"    dmg_ratio={score.damage_ratio:.2f}  parse_ok={score.parse_ok}  legal={score.legal}", flush=True)
        return scores

    def run_combat_eval(self, seeds: List[int]) -> List[CombatScore]:
        """Evaluate full-combat play."""
        from slay_bench import new_ironclad_game
        from slay_bench.enemies import Cultist, JawWorm

        evaluator = CombatEvaluator(self.llm, self.prompt_format)
        scores = []
        enemy_types = [Cultist, JawWorm]
        for i, seed in enumerate(seeds):
            enemy_cls = enemy_types[i % len(enemy_types)]
            print(f"  [combat {i+1}/{len(seeds)}] seed={seed}  enemy={enemy_cls.__name__}", flush=True)
            state = new_ironclad_game(seed)
            enemy = enemy_cls(state.rng.hp_rng)
            score = evaluator.evaluate(state, [enemy])
            scores.append(score)
            print(f"    won={score.won}  hp_ratio={score.hp_ratio:.2f}  turns={score.turns}", flush=True)
        return scores

    def run_synergy_eval(self, seeds: List[int]) -> List[SynergyScore]:
        """Evaluate synergy recognition at a mid-run snapshot."""
        from slay_bench import new_ironclad_game
        from slay_bench.rewards import generate_card_reward
        from slay_bench.run_loop import run_act
        from .enums import CardType
        import copy

        # Cycle target archetypes so every sample drafts toward a coherent,
        # identifiable strategy (and all four archetypes get tested over a run).
        targets = list(_ARCHETYPES)  # ["Strength", "Block", "Exhaust", "Aggro"]

        evaluator = SynergyEvaluator(self.llm, self.prompt_format)
        scores = []
        for i, seed in enumerate(seeds):
            target = targets[i % len(targets)]
            print(f"  [synergy {i+1}/{len(seeds)}] seed={seed}  drafting->{target}", flush=True)
            state = new_ironclad_game(seed)
            run_act(state, act=1, card_choice_fn=_archetype_draft_fn(target))
            offers = generate_card_reward(state, 3)
            score = evaluator.evaluate(state, offers)
            scores.append(score)
            tag = score.expert_archetype if score.archetype_confident else f"{score.expert_archetype}?(ambiguous)"
            print(f"    expert_label={tag}  model_said='{score.model_archetype}'  archetype_ok={score.archetype_correct}  "
                  f"card_pick_ok={score.card_pick_correct}  removal_ok={score.removal_correct}", flush=True)
        return scores

    def run_run_eval(self, seeds: List[int]) -> List[RunScore]:
        """Evaluate full run-level play."""
        from slay_bench import new_ironclad_game

        evaluator = RunEvaluator(self.llm, self.prompt_format)
        scores = []
        for i, seed in enumerate(seeds):
            print(f"  [run {i+1}/{len(seeds)}] seed={seed}", flush=True)
            state = new_ironclad_game(seed)
            try:
                score = evaluator.evaluate(state, act=1)
            except RateLimitExhausted as e:
                print(f"    [rate limit] stopping run-level after {len(scores)} "
                      f"completed run(s); keeping partial results. ({e})", flush=True)
                break
            scores.append(score)
            print(f"    survived={score.survived}  floors={score.floors_reached}  hp={score.final_hp}/{score.max_hp}  parse_errors={score.parse_errors}", flush=True)
        return scores

    def run_all(self, seed: int = 42, n_turn: int = 5, n_combat: int = 3,
                n_synergy: int = 3, n_run: int = 1) -> BenchmarkResult:
        """Run all 4 dimensions. Uses seed, seed+1, ... for each."""
        t0 = time.time()
        result = BenchmarkResult(
            model_name=self.model_name,
            prompt_format=self.prompt_format,
            seed=seed,
        )

        turn_seeds = list(range(seed, seed + n_turn))
        combat_seeds = list(range(seed + 100, seed + 100 + n_combat))
        synergy_seeds = list(range(seed + 200, seed + 200 + n_synergy))
        run_seeds = list(range(seed + 300, seed + 300 + n_run))

        try:
            print("── Turn-level ──────────────────────────", flush=True)
            result.turn_scores = self.run_turn_eval(turn_seeds)
            print("── Combat-level ────────────────────────", flush=True)
            result.combat_scores = self.run_combat_eval(combat_seeds)
            print("── Synergy ─────────────────────────────", flush=True)
            result.synergy_scores = self.run_synergy_eval(synergy_seeds)
            print("── Run-level ───────────────────────────", flush=True)
            result.run_scores = self.run_run_eval(run_seeds)
        except RateLimitExhausted as e:
            print(f"\n[rate limit] aborting remaining dimensions; saving partial "
                  f"results collected so far. ({e})", flush=True)
        result.elapsed_seconds = time.time() - t0

        return result
