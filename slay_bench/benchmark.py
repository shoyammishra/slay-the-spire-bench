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
import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .prompt_builder import (
    combat_state_structured, combat_state_raw,
    deck_relic_structured, deck_relic_raw,
    card_reward_structured, card_reward_raw,
    system_prompt,
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
        self._call_kwargs: List[dict] = []

    def complete(self, system: str, user: str, **kwargs) -> str:
        self._calls.append((system, user))
        self._call_kwargs.append(dict(kwargs))
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
    expert_pick_idx: Optional[int] = None      # ground-truth pick position (post-rotation)
    model_pick: Optional[int] = None           # the model's actual pick (for audit)
    model_removal: str = ""                    # the model's actual removal answer (for audit)
    raw_response: dict = field(default_factory=dict)


@dataclass
class RunScore:
    """Score for a full-run evaluation (one or more acts)."""
    survived: bool                    # beat the final boss of the last requested act
    floors_reached: int               # nodes visited across ALL acts (bosses included)
    final_hp: int
    max_hp: int
    gold: int
    deck_size: int
    # Multi-act bookkeeping
    n_acts: int = 1                   # acts requested
    acts_completed: int = 0           # act bosses defeated
    total_floors: int = 16            # node count of the full requested route (progress denominator)
    # Sub-scores (computed post-hoc)
    draft_coherence: float = 0.0      # fraction of cards fitting dominant archetype
    route_optimality: float = 0.0     # placeholder: 1.0 if no unnecessary elites taken
    parse_errors: int = 0
    llm_calls: int = 0

    @property
    def hp_fraction(self) -> float:
        return max(0.0, self.final_hp / self.max_hp) if self.max_hp > 0 else 0.0

    @property
    def progress(self) -> float:
        return min(1.0, self.floors_reached / self.total_floors) if self.total_floors > 0 else 0.0


# ── Turn-level evaluator ──────────────────────────────────────────────────────

def _safe_int(v, default: int = 0) -> int:
    """Coerce an LLM-supplied index to an int. Models sometimes return null, a
    string, a float, or omit the field. Plain ints/floats and integer strings
    parse directly; numeric float-strings ("1.0") fall back through int(float(v)).
    Null/garbage become `default` (0 = first option)."""
    try:
        return int(v)
    except (TypeError, ValueError):
        try:
            return int(float(v))
        except (TypeError, ValueError):
            return default


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

    used: set = set()
    for raw_idx in sequence:
        # LLMs return strings/null/floats; negative ints would silently index
        # from the end. Anything that isn't a valid hand index = illegal play.
        # Repeated indices are illegal too: with an identical twin in hand,
        # equality-based membership let `[2, 2]` replay an already-played card
        # (scored legal — and hand-counting cards could even beat the oracle).
        idx = _safe_int(raw_idx, default=-1)
        if idx < 0 or idx >= len(initial_hand) or idx in used:
            return (initial_enemy_hp - sum(e.hp for e in c.enemies if e.hp > 0), False)
        used.add(idx)
        card = initial_hand[idx]
        if not any(h is card for h in c.hand):  # identity, not __eq__
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
    Exhaustive search for the damage-maximizing play sequence.
    Returns (best_damage, best_sequence) with indices into the initial hand.

    DFS over play prefixes (illegal prefixes prune their whole subtree) instead
    of blind permutation enumeration. This removes the old first-6-playable cap,
    which silently understated the optimum whenever more than 6 cards were
    playable — Silent's 7-card opening hand (Ring of the Snake) hit it on most
    seeds, so damage_ratio denominators were wrong. Identical cards (same
    name/upgrade/cost) are expanded only once per node, so duplicate-heavy
    starter hands stay cheap. Energy limits keep legal sequences short; a
    deterministic node budget bounds pathological all-zero-cost hands.
    """
    from .combat import play_card, is_combat_over
    import copy

    base = copy.deepcopy(state_snapshot)
    initial_hp = sum(e.hp for e in base.combat.enemies if e.hp > 0)
    hand0 = list(base.combat.hand)

    best = {"dmg": 0, "seq": []}
    budget = [20000]

    def dfs(s, hand_map, seq):
        dmg = initial_hp - sum(e.hp for e in s.combat.enemies if e.hp > 0)
        if dmg > best["dmg"]:
            best["dmg"], best["seq"] = dmg, list(seq)
        if is_combat_over(s) or budget[0] <= 0:
            return
        tried = set()
        for i, card in enumerate(hand_map):
            if i in seq or card is None:
                continue
            key = (card.name, card.upgraded, card.effective_cost())
            if key in tried:
                continue
            # Identity membership: equality let the oracle "play" a card that a
            # side effect (auto-discard/exhaust) had removed, as long as an
            # identical twin remained — overstating the legal optimum.
            if not any(h is card for h in s.combat.hand) or not card.can_play(s):
                continue
            tried.add(key)
            budget[0] -= 1
            # Copy state and hand_map together so the index→card identity
            # mapping survives into the child state.
            s2, hm2 = copy.deepcopy((s, hand_map))
            target = next((e for e in s2.combat.enemies if e.hp > 0), None)
            play_card(s2, hm2[i], target)
            dfs(s2, hm2, seq + [i])

    dfs(base, hand0, [])
    return best["dmg"], best["seq"]


class TurnEvaluator:
    """
    Freeze a combat at the start of a turn, query the LLM for the optimal
    card sequence, and score it against exhaustive search.
    """

    def __init__(self, llm: LLMInterface, prompt_format: str = "structured",
                 temperature: float = 0.0, character: str = "ironclad"):
        self.llm = llm
        self.prompt_format = prompt_format  # "structured" | "raw"
        self.temperature = temperature
        self.character = character
        self.system = system_prompt("turn", character)

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

        resp = self.llm.complete_json(self.system, user_prompt,
                                      temperature=self.temperature)

        parse_ok = "plays" in resp and "error" not in resp
        llm_sequence = resp.get("plays", []) if parse_ok else []
        if not isinstance(llm_sequence, list):
            llm_sequence = []
            parse_ok = False

        # Score LLM sequence
        llm_dmg, llm_legal = _simulate_play_sequence(snapshot, llm_sequence)

        # A parse failure is NOT a legal (empty) play — an empty sequence trivially
        # simulates as legal, which would inflate legal_rate by the parse-fail rate.
        if not parse_ok:
            llm_legal = False

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

class CombatEvaluator:
    """LLM plays a full combat from start to finish, turn by turn."""

    def __init__(self, llm: LLMInterface, prompt_format: str = "structured",
                 max_turns: int = 50, temperature: float = 0.0,
                 character: str = "ironclad"):
        self.llm = llm
        self.prompt_format = prompt_format
        self.max_turns = max_turns
        self.temperature = temperature
        self.character = character
        self.system = system_prompt("combat", character)

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

                resp = self.llm.complete_json(self.system, user_prompt,
                                              temperature=self.temperature)

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
                    target = enemies_alive[target_idx] if 0 <= target_idx < len(enemies_alive) else (
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
        # Score HP at the moment combat ends, BEFORE end_combat fires COMBAT_END
        # hooks (Burning Blood heals +6 there). The greedy baseline never emits
        # COMBAT_END, so reading post-heal HP inflated hp_ratio for every
        # Ironclad win: an LLM playing identically to the bot scored ~1.10.
        hp_at_end = state.player.hp
        if won:
            end_combat(state)

        return CombatScore(
            won=won,
            turns=turns,
            hp_remaining=hp_at_end,
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
        "Feel No Pain", "Dark Embrace", "Corruption", "Offering",
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
    "Exhaust":  {"Corruption", "Feel No Pain", "Dark Embrace", "Fiend Fire"},
    "Aggro":    {"Perfected Strike", "Rampage", "Blood for Blood", "Reckless Charge"},
}

_PAYOFF_WEIGHT = 3.0
_SUPPORT_WEIGHT = 1.0


def _get_archetype_tables(character: str = "ironclad") -> Tuple[Dict, Dict, str]:
    """Return (archetypes, payoffs, default_label) for a character."""
    if character == "silent":
        from .cards_silent import SILENT_ARCHETYPES, SILENT_ARCHETYPE_PAYOFFS
        return SILENT_ARCHETYPES, SILENT_ARCHETYPE_PAYOFFS, "Shiv"
    return _ARCHETYPES, _ARCHETYPE_PAYOFFS, "Aggro"


def _relic_archetype_hints(relics: List) -> Dict[str, float]:
    """Archetype score bonuses implied by relics (keys may be absent for a character)."""
    relic_names = {r.name for r in relics}
    hints: Dict[str, float] = {}
    if "Barricade" in relic_names or "Calipers" in relic_names:
        hints["Block"] = hints.get("Block", 0) + 2.0
    if "Brimstone" in relic_names:
        hints["Strength"] = hints.get("Strength", 0) + 2.0
    if "Snecko Skull" in relic_names:
        hints["Poison"] = hints.get("Poison", 0) + 2.0
    if "Dead Branch" in relic_names:  # relic, not a card — signals Exhaust payoff
        hints["Exhaust"] = hints.get("Exhaust", 0) + 2.0
    return hints


def _classify_archetype(deck: List, relics: List, character: str = "ironclad") -> str:
    """Heuristically label the deck's dominant archetype.

    Payoff cards are weighted 3x over generic support cards so the label reflects
    what the deck is actually built around, not which bucket has the most filler
    commons. Duplicates count once (presence, not quantity)."""
    archetypes, payoff_table, default = _get_archetype_tables(character)
    scores: Dict[str, float] = {arch: 0.0 for arch in archetypes}
    deck_set = {c.name for c in deck}
    for arch, keys in archetypes.items():
        payoffs = payoff_table.get(arch, set())
        for key in keys:
            if key in deck_set:
                scores[arch] += _PAYOFF_WEIGHT if key in payoffs else _SUPPORT_WEIGHT
    for arch, bonus in _relic_archetype_hints(relics).items():
        if arch in scores:
            scores[arch] += bonus
    best = max(scores, key=lambda k: scores[k])
    return best if scores[best] > 0 else default


def _classify_archetype_confident(deck: List, relics: List,
                                  character: str = "ironclad") -> Tuple[str, bool]:
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
    archetypes, payoff_table, _default = _get_archetype_tables(character)
    deck_set = {c.name for c in deck}
    sig: Dict[str, int] = {arch: 0 for arch in archetypes}
    for arch in archetypes:
        sig[arch] = sum(1 for c in payoff_table.get(arch, set()) if c in deck_set)
    for arch, bonus in _relic_archetype_hints(relics).items():
        if arch in sig:
            sig[arch] += 1

    ranked = sorted(sig.items(), key=lambda kv: kv[1], reverse=True)
    top_arch, top_n = ranked[0]
    runner_n = ranked[1][1]
    confident = top_n > 0 and top_n > runner_n
    label = top_arch if confident else _classify_archetype(deck, relics, character)
    return label, confident


def _draft_coherence(deck: List, archetype: str, character: str = "ironclad") -> float:
    """Fraction of non-basic cards that belong to the archetype."""
    archetypes, _payoffs, _default = _get_archetype_tables(character)
    keys = set(archetypes.get(archetype, []))
    basics = {"Strike", "Defend"}
    non_basic = [c for c in deck if c.name not in basics]
    if not non_basic:
        return 0.0
    hits = sum(1 for c in non_basic if c.name in keys)
    return hits / len(non_basic)


def _expert_best_card_index(offers: List, deck: List, relics: List,
                            character: str = "ironclad") -> int:
    """Heuristic 'expert' best pick: favors the dominant archetype, then rarity."""
    from .enums import CardRarity
    archetypes, _payoffs, _default = _get_archetype_tables(character)
    archetype = _classify_archetype(deck, relics, character)
    keys = set(archetypes.get(archetype, []))
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


# Hand-crafted, unambiguous archetype decks for the synergy dimension.
# RNG-drafted Act-1 decks rarely have a clear archetype (most come out ambiguous,
# and even "confident" labels off a single signature card are debatable). Fixed
# decks give the synergy test clean, deterministic ground truth: each deck has 4-5
# signature payoff cards so its archetype is unmistakable, a basic Strike as the
# expert removal target, and a 3-card offer whose on-archetype card is the expert
# best pick. (archetype, deck_card_names, offer_card_names, expert_pick_idx).
# Card keys: "Strike_R"/"Defend_R" are the registry keys; their .name is Strike/Defend.
_SYNERGY_FIXTURES = [
    ("Strength",
     ["Demon Form", "Limit Break", "Inflame", "Heavy Blade", "Flex", "Twin Strike",
      "Strike_R", "Strike_R", "Strike_R", "Defend_R"],
     ["Defend_R", "Bludgeon", "Strike_R"], 1),          # Bludgeon = Strength payoff
    ("Block",
     ["Barricade", "Body Slam", "Juggernaut", "Entrench", "Impervious", "Iron Wave",
      "Defend_R", "Defend_R", "Defend_R", "Strike_R"],
     ["Shrug It Off", "Anger", "Strike_R"], 0),          # Shrug It Off = Block
    ("Exhaust",
     ["Corruption", "Feel No Pain", "Dark Embrace", "Fiend Fire", "Evolve", "Dual Wield",
      "Strike_R", "Strike_R", "Defend_R"],
     ["Strike_R", "Defend_R", "Sever Soul"], 2),         # Sever Soul = Exhaust
    ("Aggro",
     # Cleave (not Perfected Strike): with Perfected Strike in deck, "remove
     # Strike" as removal ground truth is debatable — Strikes feed it.
     ["Cleave", "Rampage", "Blood for Blood", "Reckless Charge", "Pommel Strike",
      "Anger", "Strike_R", "Strike_R", "Defend_R", "Bash"],
     ["Twin Strike", "Defend_R", "Iron Wave"], 0),       # Twin Strike = Aggro strike-payoff
    ("Strength",
     ["Demon Form", "Inflame", "Heavy Blade", "Whirlwind", "Flex",
      "Strike_R", "Strike_R", "Strike_R", "Defend_R", "Defend_R"],
     ["Carnage", "Defend_R", "Shrug It Off"], 0),        # Carnage = Strength payoff
    ("Block",
     ["Barricade", "Juggernaut", "Entrench", "Impervious", "Ghostly Armor", "Shrug It Off",
      "Defend_R", "Defend_R", "Strike_R", "Strike_R"],
     ["Anger", "Second Wind", "Strike_R"], 1),           # Second Wind = Block
    ("Exhaust",
     ["Corruption", "Feel No Pain", "Dark Embrace", "Sever Soul", "Evolve",
      "Strike_R", "Strike_R", "Strike_R", "Defend_R"],
     ["Defend_R", "Strike_R", "Fiend Fire"], 2),         # Fiend Fire = Exhaust
    ("Aggro",
     # Wild Strike replaces Perfected Strike (see fixture 4's note)
     ["Wild Strike", "Rampage", "Blood for Blood", "Pommel Strike", "Clothesline",
      "Anger", "Strike_R", "Strike_R", "Defend_R", "Bash"],
     ["Reckless Charge", "Defend_R", "Iron Wave"], 0),   # Reckless Charge = Aggro payoff
    # ── Fixtures 9-20: paper-grade expansion to 5 decks per archetype. ──────────
    # Appended after the original 8 so historical n=8 runs remain reproducible
    # (any n that is a multiple of 4 stays archetype-balanced).
    ("Strength",
     ["Limit Break", "Inflame", "Whirlwind", "Spot Weakness", "Flex", "Twin Strike",
      "Strike_R", "Strike_R", "Defend_R", "Defend_R"],
     ["Heavy Blade", "Shrug It Off", "Defend_R"], 0),    # Heavy Blade = Strength payoff
    ("Block",
     ["Barricade", "Entrench", "Body Slam", "Iron Wave", "True Grit",
      "Defend_R", "Defend_R", "Strike_R", "Strike_R", "Bash"],
     ["Impervious", "Twin Strike", "Strike_R"], 0),      # Impervious = Block payoff
    ("Exhaust",
     ["Feel No Pain", "Corruption", "Fiend Fire", "Burning Pact", "True Grit",
      "Strike_R", "Strike_R", "Defend_R", "Defend_R"],
     ["Dark Embrace", "Twin Strike", "Defend_R"], 0),    # Dark Embrace = Exhaust payoff
    ("Aggro",
     # Cleave replaces Perfected Strike (see fixture 4's note)
     ["Rampage", "Reckless Charge", "Cleave", "Twin Strike", "Pommel Strike",
      "Anger", "Strike_R", "Strike_R", "Defend_R", "Bash"],
     ["Blood for Blood", "Defend_R", "Shrug It Off"], 0),  # Blood for Blood = Aggro payoff
    ("Strength",
     ["Demon Form", "Heavy Blade", "Limit Break", "Sword Boomerang", "Flex",
      "Strike_R", "Strike_R", "Strike_R", "Defend_R", "Defend_R"],
     ["Inflame", "Iron Wave", "Defend_R"], 0),           # Inflame = Strength payoff
    ("Block",
     ["Juggernaut", "Barricade", "Impervious", "Shrug It Off", "Ghostly Armor",
      "Defend_R", "Defend_R", "Defend_R", "Strike_R"],
     ["Entrench", "Carnage", "Strike_R"], 0),            # Entrench = Block payoff
    ("Exhaust",
     ["Dark Embrace", "Feel No Pain", "Fiend Fire", "Second Wind", "Burning Pact",
      "Strike_R", "Strike_R", "Defend_R", "Defend_R"],
     ["Corruption", "Anger", "Strike_R"], 0),            # Corruption = Exhaust payoff
    ("Aggro",
     # Twin Strike (not Perfected Strike): the removal target here is "Strike",
     # and Strikes feed Perfected Strike — picking it then keeping Strikes is
     # logically consistent yet would score wrong on removal. Twin Strike is the
     # same Aggro strike-payoff pattern as fixtures 4 and 20 without that clash.
     ["Blood for Blood", "Rampage", "Reckless Charge", "Wild Strike", "Clash",
      "Strike_R", "Strike_R", "Defend_R", "Defend_R", "Bash"],
     ["Twin Strike", "Iron Wave", "Defend_R"], 0),  # Twin Strike = Aggro strike-payoff
    ("Strength",
     ["Inflame", "Whirlwind", "Heavy Blade", "Demon Form", "Uppercut",
      "Strike_R", "Strike_R", "Defend_R", "Defend_R", "Bash"],
     ["Limit Break", "Shrug It Off", "Defend_R"], 0),    # Limit Break = Strength payoff (Anger removed: it's Strength-listed too → ambiguous)
    ("Block",
     ["Body Slam", "Entrench", "Juggernaut", "Metallicize", "Sentinel",
      "Defend_R", "Defend_R", "Strike_R", "Strike_R", "Bash"],
     ["Barricade", "Pommel Strike", "Strike_R"], 0),     # Barricade = Block payoff
    ("Exhaust",
     ["Corruption", "Dark Embrace", "Feel No Pain", "Sever Soul", "True Grit",
      "Strike_R", "Strike_R", "Strike_R", "Defend_R"],
     ["Fiend Fire", "Iron Wave", "Defend_R"], 0),        # Fiend Fire = Exhaust payoff (was mislabeled 2=Defend)
    ("Aggro",
     # Clash replaces Perfected Strike (see fixture 4's note)
     ["Clash", "Blood for Blood", "Rampage", "Pommel Strike", "Sword Boomerang",
      "Anger", "Strike_R", "Strike_R", "Strike_R", "Defend_R"],
     ["Twin Strike", "Second Wind", "Defend_R"], 0),     # Twin Strike = Aggro strike-payoff
]

# Per-character fixture sets. The Silent set lives in cards_silent.py to keep
# all Silent content in one module.
def _silent_fixtures():
    from .cards_silent import SILENT_SYNERGY_FIXTURES
    return SILENT_SYNERGY_FIXTURES


class _LazyFixtures:
    """Defers the cards_silent import until the fixtures are actually used."""
    def __init__(self, loader):
        self._loader = loader
        self._data = None

    def _load(self):
        if self._data is None:
            self._data = self._loader()
        return self._data

    def __getitem__(self, i):
        return self._load()[i]

    def __len__(self):
        return len(self._load())

    def __iter__(self):
        return iter(self._load())


_SYNERGY_FIXTURES_BY_CHAR = {
    "ironclad": _SYNERGY_FIXTURES,
    "silent": _LazyFixtures(_silent_fixtures),
}


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

    def __init__(self, llm: LLMInterface, prompt_format: str = "structured",
                 temperature: float = 0.0, character: str = "ironclad"):
        self.llm = llm
        self.prompt_format = prompt_format
        self.temperature = temperature
        self.character = character
        self.system = system_prompt("synergy", character)

    def evaluate(self, state, card_offers: List, expert_pick_idx: Optional[int] = None,
                 expert_remove_name: Optional[str] = None) -> SynergyScore:

        expert_archetype, archetype_confident = _classify_archetype_confident(
            state.player.deck, state.player.relics, self.character)
        # Derive real expert labels when callers don't supply hand-labeled data
        if expert_pick_idx is None and card_offers:
            expert_pick_idx = _expert_best_card_index(
                card_offers, state.player.deck, state.player.relics, self.character)
        if expert_remove_name is None:
            expert_remove_name = _expert_worst_card_name(state.player.deck)

        if self.prompt_format == "raw":
            context = deck_relic_raw(state) + "\n\n" + card_reward_raw(
                card_offers, state.player.deck, state.player.relics)
        else:
            context = deck_relic_structured(state) + "\n\n" + card_reward_structured(
                card_offers, state.player.deck, state.player.relics)

        archetypes, _p, _d = _get_archetype_tables(self.character)
        arch_options = ", ".join(archetypes.keys())
        user_prompt = (
            context + "\n\n"
            "Answer three questions:\n"
            f"1. What is the deck's primary archetype? (one of: {arch_options})\n"
            "2. Which offered card (by index 0,1,2) is the best addition to this deck?\n"
            "3. Which card in the current deck should be removed first (exact name)?\n\n"
            "Output JSON: {\"archetype\": \"...\", \"best_card_index\": <int>, "
            "\"worst_card_name\": \"...\"}"
        )

        resp = self.llm.complete_json(self.system, user_prompt,
                                      temperature=self.temperature)
        parse_ok = "error" not in resp

        archetype_correct = None
        card_pick_correct = None
        removal_correct = None
        model_archetype = ""
        model_pick = None
        model_removal = ""

        if parse_ok:
            # Models sometimes return null / non-string values for any field —
            # coerce defensively instead of crashing the whole sample.
            model_archetype = str(resp.get("archetype") or "").strip()
            # Only score archetype ID when the deck has a real, unambiguous archetype.
            # Ambiguous decks (no signature card, or a tie) stay None → excluded from acc.
            if archetype_confident:
                # Correct iff the answer names EXACTLY ONE archetype and it's the
                # expert's. Plain substring matching would score multi-archetype
                # answers ("Aggro or Exhaust", an echo of the option list) as
                # correct whenever the right name appeared anywhere.
                mentioned = [a for a in archetypes
                             if a.lower() in model_archetype.lower()]
                archetype_correct = (len(mentioned) == 1 and
                                     mentioned[0].lower() == expert_archetype.lower())

            if expert_pick_idx is not None:
                # Accept "1" (string) as 1 — the answer is right, just mistyped
                model_pick = _safe_int(resp.get("best_card_index"), default=-1)
                card_pick_correct = model_pick == expert_pick_idx

            if expert_remove_name is not None:
                model_removal = str(resp.get("worst_card_name") or "").strip()
                removal_correct = model_removal.lower() == expert_remove_name.lower()

        return SynergyScore(
            archetype_correct=archetype_correct,
            card_pick_correct=card_pick_correct,
            removal_correct=removal_correct,
            parse_ok=parse_ok,
            expert_archetype=expert_archetype,
            archetype_confident=archetype_confident,
            model_archetype=model_archetype,
            expert_pick_idx=expert_pick_idx,
            model_pick=model_pick,
            model_removal=model_removal,
            raw_response=resp,
        )


# ── Run-level evaluator ───────────────────────────────────────────────────────

class RunEvaluator:
    """
    LLM plays a full run (one or more acts) from start to final boss.
    Scores: survival, HP fraction, draft coherence, route optimality.

    With llm_routing=True the LLM also chooses the map path and rest-site
    action (otherwise: greedy first node / always rest). The boss relic at
    each act transition is always an LLM choice (cheap: once per act).
    """

    def __init__(self, llm: LLMInterface, prompt_format: str = "structured",
                 max_combat_turns: int = 50, temperature: float = 0.0,
                 llm_routing: bool = False, character: str = "ironclad"):
        self.llm = llm
        self.prompt_format = prompt_format
        self.max_combat_turns = max_combat_turns
        self.temperature = temperature
        self.llm_routing = llm_routing
        self.character = character
        self.system_run = system_prompt("run", character)
        self.system_combat = system_prompt("combat", character)

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
        resp = self.llm.complete_json(self.system_run, user_prompt,
                                      temperature=self.temperature)
        idx = _safe_int(resp.get("pick", -1), default=-1)
        if 0 <= idx < len(offers):
            return offers[idx]
        return None

    def _llm_path_choice(self, state, options: List) -> int:
        """LLM picks the next map node from `options`. Returns an index
        (falls back to 0 on any parse problem)."""
        if len(options) <= 1:
            return 0
        opts = [{"index": i, "type": n.node_type.name} for i, n in enumerate(options)]
        user_prompt = (
            f"You are on floor {state.floor} of act {state.act}. "
            f"HP: {state.player.hp}/{state.player.max_hp}. Gold: {state.player.gold}.\n"
            f"Reachable next nodes: {json.dumps(opts)}\n"
            "(MONSTER=normal fight, ELITE=hard fight w/ relic reward, REST=heal or "
            "upgrade, EVENT=random event, MERCHANT=shop, TREASURE=free relic)\n"
            "Which node do you move to?\n"
            "Output JSON: {\"choice\": <index>, \"reasoning\": \"...\"}"
        )
        resp = self.llm.complete_json(self.system_run, user_prompt,
                                      temperature=self.temperature)
        idx = _safe_int(resp.get("choice", 0))
        return idx if 0 <= idx < len(options) else 0

    def _llm_rest_choice(self, state) -> str:
        """LLM chooses rest-site action: 'rest' (heal 30%) or 'smith' (upgrade)."""
        user_prompt = (
            f"You are at a rest site on floor {state.floor} of act {state.act}. "
            f"HP: {state.player.hp}/{state.player.max_hp}.\n"
            f"Deck: {[repr(c) for c in state.player.deck]}\n"
            "Options: \"rest\" (heal 30% max HP) or \"smith\" (upgrade a card).\n"
            "Output JSON: {\"action\": \"rest\"|\"smith\", \"card_name\": \"<name if smith>\", "
            "\"reasoning\": \"...\"}"
        )
        resp = self.llm.complete_json(self.system_run, user_prompt,
                                      temperature=self.temperature)
        action = str(resp.get("action", "rest")).strip().lower()
        return action if action in ("rest", "smith") else "rest"

    def _llm_boss_relic_choice(self, state, relic_ids: List[str]) -> int:
        """LLM picks one of the offered boss relics. Falls back to 0."""
        if len(relic_ids) <= 1:
            return 0
        user_prompt = (
            f"You defeated the act {state.act} boss. "
            f"HP: {state.player.hp}/{state.player.max_hp}.\n"
            f"Deck: {[repr(c) for c in state.player.deck]}\n"
            f"Relics: {[r.name for r in state.player.relics]}\n"
            f"Choose one boss relic (0-indexed): {json.dumps(relic_ids)}\n"
            "Output JSON: {\"pick\": <int>, \"reasoning\": \"...\"}"
        )
        resp = self.llm.complete_json(self.system_run, user_prompt,
                                      temperature=self.temperature)
        idx = _safe_int(resp.get("pick", 0))
        return idx if 0 <= idx < len(relic_ids) else 0

    def _llm_combat(self, state, counters: Optional[dict] = None) -> Tuple[bool, int]:
        """Run a full combat with LLM decisions. Returns (won, turns).
        Parse errors and LLM calls are accumulated into `counters` if given."""
        from .combat import play_card, end_player_turn, is_combat_over, end_combat
        counters = counters if counters is not None else {}
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
                resp = self.llm.complete_json(self.system_combat, user_prompt,
                                              temperature=self.temperature)
                counters["llm_calls"] = counters.get("llm_calls", 0) + 1

                if "error" in resp or resp.get("action") == "end_turn":
                    if "error" in resp:
                        counters["parse_errors"] = counters.get("parse_errors", 0) + 1
                    end_player_turn(state)
                    turn_done = True
                elif resp.get("action") == "play":
                    idx = _safe_int(resp.get("card_index", 0))
                    tidx = _safe_int(resp.get("target_index", 0))
                    hand = state.combat.hand
                    if 0 <= idx < len(hand) and hand[idx].can_play(state):
                        enemies_alive = [e for e in state.combat.enemies if e.hp > 0]
                        target = enemies_alive[tidx] if 0 <= tidx < len(enemies_alive) else (
                            enemies_alive[0] if enemies_alive else None)
                        play_card(state, hand[idx], target)
                    else:
                        counters["parse_errors"] = counters.get("parse_errors", 0) + 1
                        end_player_turn(state)
                        turn_done = True
                else:
                    counters["parse_errors"] = counters.get("parse_errors", 0) + 1
                    end_player_turn(state)
                    turn_done = True

                if is_combat_over(state):
                    turn_done = True

        # timeout — clean up stale combat state
        from .combat import end_combat
        if state.combat is not None:
            end_combat(state)
        return False, turns

    def _act_transition(self, state, counters: Optional[dict] = None) -> None:
        """Between-act bookkeeping after an act boss dies: full heal (base-game
        behaviour at Ascension 0) and an LLM-chosen boss relic."""
        from .rewards import generate_boss_relic_choices
        from .relics import make_relic
        from .nodes import _obtain_relic

        state.player.hp = state.player.max_hp

        relic_ids = generate_boss_relic_choices(state, 3)
        relic_ids = [r for r in relic_ids if r != "Black Blood"]  # Ironclad-keyed swap relic; keep simple
        if relic_ids:
            try:
                if counters is not None:
                    counters["llm_calls"] = counters.get("llm_calls", 0) + 1
                pick = self._llm_boss_relic_choice(state, relic_ids)
            except RateLimitExhausted:
                raise
            except Exception:
                pick = 0
            try:
                _obtain_relic(state, make_relic(relic_ids[pick]))
            except ValueError:
                pass  # relic id in pool but not implemented — skip gracefully

    def _play_act(self, state, act: int, counters: dict) -> bool:
        """Play a single act start-to-boss. Returns True if the boss died."""
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

        def process_node(node):
            counters["floors"] += 1
            ntype = node.node_type

            if ntype in (NodeType.MONSTER, NodeType.ELITE, NodeType.BOSS):
                if ntype == NodeType.ELITE:
                    counters["elites"] += 1
                enemy_type = {
                    NodeType.MONSTER: "normal",
                    NodeType.ELITE: "elite",
                    NodeType.BOSS: "boss",
                }[ntype]
                enemy_ids = roll_encounter(state, ntype)
                enemies = spawn_enemies(state, enemy_ids,
                                        elite=ntype == NodeType.ELITE,
                                        boss=ntype == NodeType.BOSS)
                start_combat(state, enemies)
                won, turns = self._llm_combat(state, counters)
                if won:
                    gold = gold_reward(state, enemy_type)
                    state.player.gold += gold
                    state.bus.emit(Event.GOLD_GAINED, state, amount=gold)
                    if ntype == NodeType.BOSS:
                        state.bus.emit(Event.BOSS_DEFEATED, state)
                    # Elite relic drop (Black Star: an additional one)
                    if ntype == NodeType.ELITE:
                        from .nodes import _obtain_relic
                        from .relics import random_relic
                        from .rewards import elite_relic_rarity
                        n_relics = 2 if getattr(state.player, '_black_star', False) else 1
                        for _ in range(n_relics):
                            _obtain_relic(state, random_relic(
                                state, elite_relic_rarity(state)))
                    # Same offer count as run_loop (Prayer Wheel / Busted Crown)
                    n_offers = 3
                    if getattr(state.player, '_prayer_wheel', False):
                        n_offers += 1
                    if getattr(state.player, '_busted_crown', False):
                        n_offers = max(1, n_offers - 2)
                    offers = generate_card_reward(state, n_offers)
                    chosen = None
                    if offers:  # no offers → no LLM call to count
                        counters["llm_calls"] += 1
                        chosen = self._llm_card_choice(state, offers)
                    if chosen:
                        state.player.deck.append(chosen)
                        state.bus.emit(Event.CARD_ADDED, state, card=chosen)
                    if potion_drop(state, enemy_type) and len(state.player.potions) < 3:
                        from .potions import random_potion
                        state.player.potions.append(random_potion(state))
                    return won
                return False

            elif ntype == NodeType.REST:
                from .enums import CardType
                p = state.player
                no_heal = getattr(p, '_no_rest_heal', False)
                no_smith = getattr(p, '_no_smith', False)
                action = RestSiteAction.REST
                card = None
                # Peace Pipe: removing a curse beats resting/smithing
                if getattr(p, '_peace_pipe', False) and \
                        any(c.type == CardType.CURSE for c in p.deck):
                    action = RestSiteAction.TOKE
                elif no_heal and not no_smith:
                    action = RestSiteAction.SMITH
                elif self.llm_routing and not no_smith:
                    counters["llm_calls"] += 1
                    if self._llm_rest_choice(state) == "smith":
                        action = RestSiteAction.SMITH
                if action == RestSiteAction.SMITH:
                    # Curses/statuses can't be upgraded (CurseBase.upgrade is a
                    # no-op) — picking one wasted the smith every rest.
                    candidates = [c for c in p.deck if not c.upgraded
                                  and c.type not in (CardType.CURSE, CardType.STATUS)]
                    card = candidates[0] if candidates else None
                resolve_rest(state, action, card)
                # Dream Catcher: a card reward when you rest
                offer = getattr(state, '_dream_catcher_offer', None)
                if action == RestSiteAction.REST and offer:
                    counters["llm_calls"] += 1
                    chosen = self._llm_card_choice(state, offer)
                    if chosen:
                        p.deck.append(chosen)
                        state.bus.emit(Event.CARD_ADDED, state, card=chosen)
                state._dream_catcher_offer = None

            elif ntype == NodeType.MERCHANT:
                from .nodes import greedy_shop_visit
                greedy_shop_visit(state)

            elif ntype == NodeType.TREASURE:
                resolve_treasure(state)

            elif ntype == NodeType.EVENT:
                event = random_event(state)
                resolve_event(state, event, 0)

            return True

        current_nodes = game_map.floors[0] if game_map.floors else []
        if not current_nodes:
            return False

        # NOTE: no move_to here — the loop pops this node and calls move_to;
        # the pre-loop call double-counted the first floor (Maw Bank ×2).
        current_node = current_nodes[0]
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
                return False

            # Exclude the boss; it is fought once in the dedicated block below
            next_nodes = [n for n in run.available_next_nodes()
                          if n is not game_map.boss_node]
            if next_nodes:
                pick = 0
                if self.llm_routing and len(next_nodes) > 1:
                    counters["llm_calls"] += 1
                    pick = self._llm_path_choice(state, next_nodes)
                queue.append(next_nodes[pick])

        # Boss
        if game_map.boss_node:
            run.move_to(game_map.boss_node)
            ok = process_node(game_map.boss_node)
            if ok and state.player.hp > 0:
                state.bus.emit(Event.ACT_END, state)
                return True
        return False

    def evaluate(self, state, n_acts: int = 1) -> RunScore:
        """Play acts 1..n_acts back-to-back (full heal + boss relic between acts)."""
        from .map_gen import ACT_STRUCTURE

        n_acts = max(1, min(n_acts, 3))
        # One node visited per floor plus the act boss, for every act played.
        total_floors = sum(ACT_STRUCTURE[a][0] + 1 for a in range(1, n_acts + 1))

        counters = {"floors": 0, "elites": 0, "llm_calls": 0, "parse_errors": 0}
        acts_completed = 0
        for act in range(1, n_acts + 1):
            beat_boss = self._play_act(state, act, counters)
            if not beat_boss:
                break
            acts_completed += 1
            if act < n_acts:
                self._act_transition(state, counters)

        archetype = _classify_archetype(state.player.deck, state.player.relics,
                                        self.character)
        return RunScore(
            survived=acts_completed == n_acts,
            floors_reached=counters["floors"],
            final_hp=state.player.hp,
            max_hp=state.player.max_hp,
            gold=state.player.gold,
            deck_size=len(state.player.deck),
            n_acts=n_acts,
            acts_completed=acts_completed,
            total_floors=total_floors,
            draft_coherence=_draft_coherence(state.player.deck, archetype, self.character),
            parse_errors=counters["parse_errors"],
            llm_calls=counters["llm_calls"],
        )


# ── Master harness ─────────────────────────────────────────────────────────────

@dataclass
class BenchmarkResult:
    model_name: str
    prompt_format: str
    seed: int
    character: str = "ironclad"
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
            "card_pick_n_scored": sum(1 for s in self.synergy_scores
                                      if s.card_pick_correct is not None),
            "removal_acc": avg([float(s.removal_correct)
                                for s in self.synergy_scores
                                if s.removal_correct is not None]),
            "removal_n_scored": sum(1 for s in self.synergy_scores
                                    if s.removal_correct is not None),
            "parse_ok_rate": avg([float(s.parse_ok) for s in self.synergy_scores]),
            "samples": [
                {
                    "expert_archetype": s.expert_archetype,
                    "model_archetype": s.model_archetype,
                    "confident": s.archetype_confident,
                    "archetype_correct": s.archetype_correct,
                    "expert_pick_idx": s.expert_pick_idx,
                    "model_pick": s.model_pick,
                    "card_pick_correct": s.card_pick_correct,
                    "model_removal": s.model_removal,
                    "removal_correct": s.removal_correct,
                }
                for s in self.synergy_scores
            ],
        } if self.synergy_scores else None

        survivors = [s for s in self.run_scores if s.survived]
        run = {
            "n": len(self.run_scores),
            "n_acts": self.run_scores[0].n_acts if self.run_scores else None,
            "survival_rate": avg([float(s.survived) for s in self.run_scores]),
            "avg_acts_completed": avg([s.acts_completed for s in self.run_scores]),
            # HP fraction only meaningful for survivors; 0 on death misleads
            "avg_hp_fraction": avg([s.hp_fraction for s in survivors]) if survivors else 0.0,
            "avg_draft_coherence": avg([s.draft_coherence for s in self.run_scores]),
            "avg_floors_reached": avg([s.floors_reached for s in self.run_scores]),
            # Progress fraction: nodes visited ÷ full requested route (partial credit)
            "avg_progress": avg([s.progress for s in self.run_scores]),
        } if self.run_scores else None

        return {
            "model": self.model_name,
            "prompt_format": self.prompt_format,
            "seed": self.seed,
            "character": self.character,
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
                 prompt_format: str = "structured", character: str = "ironclad",
                 temperature: float = 0.0, n_acts: int = 1,
                 llm_routing: bool = False):
        self.llm = llm
        self.model_name = model_name
        self.prompt_format = prompt_format
        self.character = character
        self.temperature = temperature
        self.n_acts = n_acts
        self.llm_routing = llm_routing

    def run_turn_eval(self, seeds: List[int]) -> List[TurnScore]:
        """Evaluate turn-level planning on mid-combat snapshots."""
        from slay_bench import new_game, start_combat
        from slay_bench.enemies import Cultist, JawWorm

        evaluator = TurnEvaluator(self.llm, self.prompt_format,
                                  temperature=self.temperature,
                                  character=self.character)
        scores = []
        for i, seed in enumerate(seeds):
            print(f"  [turn {i+1}/{len(seeds)}] seed={seed}", flush=True)
            state = new_game(seed, self.character)
            enemy = Cultist(state.rng.hp_rng)
            start_combat(state, [enemy])
            score = evaluator.evaluate(state)
            scores.append(score)
            print(f"    dmg_ratio={score.damage_ratio:.2f}  parse_ok={score.parse_ok}  legal={score.legal}", flush=True)
        return scores

    def run_combat_eval(self, seeds: List[int]) -> List[CombatScore]:
        """Evaluate full-combat play."""
        from slay_bench import new_game
        from slay_bench.enemies import Cultist, JawWorm

        evaluator = CombatEvaluator(self.llm, self.prompt_format,
                                    temperature=self.temperature,
                                    character=self.character)
        scores = []
        enemy_types = [Cultist, JawWorm]
        for i, seed in enumerate(seeds):
            enemy_cls = enemy_types[i % len(enemy_types)]
            print(f"  [combat {i+1}/{len(seeds)}] seed={seed}  enemy={enemy_cls.__name__}", flush=True)
            state = new_game(seed, self.character)
            enemy = enemy_cls(state.rng.hp_rng)
            score = evaluator.evaluate(state, [enemy])
            scores.append(score)
            print(f"    won={score.won}  hp_ratio={score.hp_ratio:.2f}  turns={score.turns}", flush=True)
        return scores

    def run_synergy_eval(self, seeds: List[int]) -> List[SynergyScore]:
        """Evaluate synergy recognition on hand-crafted, unambiguous archetype decks.

        RNG-drafted Act-1 decks rarely have a clear archetype, so we use fixed
        fixtures (`_SYNERGY_FIXTURES`) for clean, deterministic ground truth.
        Fixture choice AND offer rotation are derived from each sample's SEED
        (not the loop index): consecutive seeds still cover every fixture once
        per len(fixtures) samples with uniform pick positions, but different
        base seeds produce genuinely different fixture↔rotation pairings, so
        multi-seed runs (`--seeds`) measure real instrument variance instead of
        sending byte-identical prompts and reporting a fake std of 0."""
        from slay_bench import new_game
        from slay_bench.cards import make_card_for

        fixtures = _SYNERGY_FIXTURES_BY_CHAR.get(self.character, _SYNERGY_FIXTURES)
        evaluator = SynergyEvaluator(self.llm, self.prompt_format,
                                     temperature=self.temperature,
                                     character=self.character)
        scores = []
        for i, seed in enumerate(seeds):
            archetype, deck_names, offer_names, pick_idx = fixtures[seed % len(fixtures)]
            # De-bias offer position: the hand-written fixtures put the expert pick
            # at index 0 in 35/40 cases, so a model that always answered 0 scored
            # 75-100% on card-pick. Rotate each offer list so the correct index
            # cycles 0,1,2 across samples — uniform by construction, deterministic,
            # and invisible to the (stateless) model. Keyed on the seed so that
            # different --seeds runs see different rotations (real variance).
            target_pos = seed % len(offer_names)
            rot = (pick_idx - target_pos) % len(offer_names)
            offer_names = list(offer_names[rot:]) + list(offer_names[:rot])
            pick_idx = target_pos
            print(f"  [synergy {i+1}/{len(seeds)}] deck={archetype}", flush=True)
            state = new_game(seed, self.character)
            state.player.deck = [make_card_for(self.character, n) for n in deck_names]
            offers = [make_card_for(self.character, n) for n in offer_names]
            # Ground truth is supplied explicitly: best pick = the on-archetype offer,
            # removal = a basic Strike (meta-correct: basics dilute draw quality).
            score = evaluator.evaluate(state, offers,
                                       expert_pick_idx=pick_idx,
                                       expert_remove_name="Strike")
            scores.append(score)
            print(f"    expert_label={score.expert_archetype}  model_said='{score.model_archetype}'  "
                  f"archetype_ok={score.archetype_correct}  card_pick_ok={score.card_pick_correct}  "
                  f"removal_ok={score.removal_correct}", flush=True)
        return scores

    def run_run_eval(self, seeds: List[int]) -> List[RunScore]:
        """Evaluate full run-level play (acts 1..n_acts)."""
        from slay_bench import new_game

        evaluator = RunEvaluator(self.llm, self.prompt_format,
                                 temperature=self.temperature,
                                 llm_routing=self.llm_routing,
                                 character=self.character)
        scores = []
        for i, seed in enumerate(seeds):
            print(f"  [run {i+1}/{len(seeds)}] seed={seed}  acts=1-{self.n_acts}", flush=True)
            state = new_game(seed, self.character)
            try:
                score = evaluator.evaluate(state, n_acts=self.n_acts)
            except RateLimitExhausted as e:
                print(f"    [rate limit] stopping run-level after {len(scores)} "
                      f"completed run(s); keeping partial results. ({e})", flush=True)
                break
            scores.append(score)
            print(f"    survived={score.survived}  acts={score.acts_completed}/{score.n_acts}  "
                  f"floors={score.floors_reached}/{score.total_floors}  "
                  f"hp={score.final_hp}/{score.max_hp}  parse_errors={score.parse_errors}", flush=True)
        return scores

    def run_all(self, seed: int = 42, n_turn: int = 5, n_combat: int = 3,
                n_synergy: int = 3, n_run: int = 1) -> BenchmarkResult:
        """Run all 4 dimensions. Uses seed, seed+1, ... for each."""
        t0 = time.time()
        result = BenchmarkResult(
            model_name=self.model_name,
            prompt_format=self.prompt_format,
            seed=seed,
            character=self.character,
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
