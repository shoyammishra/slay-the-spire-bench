"""Enemy definitions with intent patterns."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable, Optional, List
import math

from .enums import IntentType, PowerId

if TYPE_CHECKING:
    from .state import GameState


@dataclass
class Move:
    name: str
    intent: IntentType
    damage: int = 0       # per hit
    hits: int = 1
    block: int = 0
    effects: Optional[Callable] = None  # (state, enemy, target) -> None


@dataclass
class Enemy:
    id: str
    name: str
    hp: int
    max_hp: int
    block: int = 0
    powers: dict = field(default_factory=dict)
    move_index: int = 0
    move_history: list = field(default_factory=list)
    current_move: Optional[Move] = None
    # runtime flags
    alive: bool = True

    def add_block(self, amount: int) -> None:
        self.block += amount

    def select_move(self, state: GameState) -> Move:
        raise NotImplementedError

    def on_death(self, state: GameState) -> None:
        pass

    def __repr__(self) -> str:
        return f"{self.name}(hp={self.hp}/{self.max_hp}, block={self.block})"


# ── helpers ───────────────────────────────────────────────────────────────────

def effective_move_damage(enemy: Enemy, move: Move, player=None) -> int:
    """Per-hit damage of a move after the enemy's Strength and Weak.
    Single source of truth shared by combat execution AND the prompt builder,
    so the intent shown to the LLM matches the damage that actually lands
    (real StS displays the adjusted number; Vulnerable on the player is
    applied separately at damage time). Pass the player so Paper Krane
    (Weak reduces enemy damage 40% instead of 25%) is honored."""
    strength = enemy.powers.get(PowerId.STRENGTH, 0)
    per_hit = max(0, move.damage + strength)
    if PowerId.WEAK in enemy.powers:
        mult = 0.6 if (player is not None
                       and getattr(player, '_paper_krane', False)) else 0.75
        per_hit = math.floor(per_hit * mult)
    return per_hit


def _enemy_attack(state: GameState, enemy: Enemy, move: Move) -> None:
    from .cards import _damage_player
    from .events import Event
    per_hit = effective_move_damage(enemy, move, state.player)
    # Vulnerable on player handled in _damage_player
    for _ in range(move.hits):
        _damage_player(state, per_hit)
        # Flame Barrier
        fb = state.player.powers.get(PowerId.FLAME_BARRIER, 0)
        if fb > 0 and enemy.hp > 0:
            from .cards import _apply_damage_to_enemy
            _apply_damage_to_enemy(state, enemy, fb)


def _enemy_apply_power(state: GameState, enemy: Enemy, power_id: PowerId, amount: int) -> None:
    from .cards import _apply_power
    _apply_power(state, state.player, power_id, amount)


# ── Act 1 enemies ─────────────────────────────────────────────────────────────

class Cultist(Enemy):
    MOVES = [
        Move("Incantation", IntentType.BUFF),
        Move("Dark Strike", IntentType.ATTACK, damage=6, hits=1),
    ]

    def __init__(self, hp_rng):
        hp = hp_rng.next_int(9) + 48  # 48-57
        super().__init__("Cultist", "Cultist", hp, hp)
        self._first_turn = True

    def select_move(self, state):
        if self._first_turn:
            self._first_turn = False
            self.current_move = self.MOVES[0]
        else:
            self.current_move = self.MOVES[1]
        return self.current_move

    def execute_move(self, state: GameState) -> None:
        if self.current_move.name == "Incantation":
            self.powers[PowerId.RITUAL] = self.powers.get(PowerId.RITUAL, 0) + 3
        else:
            _enemy_attack(state, self, self.current_move)


class JawWorm(Enemy):
    CHOMP = Move("Chomp", IntentType.ATTACK, damage=11, hits=1)
    THRASH = Move("Thrash", IntentType.ATTACK_DEFEND, damage=7, hits=1, block=5)
    BELLOW = Move("Bellow", IntentType.ATTACK_BUFF, damage=0, hits=0, block=6)

    def __init__(self, hp_rng):
        hp = hp_rng.next_int(5) + 40  # 40-44
        super().__init__("JawWorm", "Jaw Worm", hp, hp)
        self._first_turn = True

    def select_move(self, state):
        if self._first_turn:
            self._first_turn = False
            self.current_move = self.CHOMP
            return self.current_move
        last = self.move_history[-1] if self.move_history else None
        roll = state.rng.ai_rng.next_int(100)
        if roll < 45:
            if last == "Bellow":
                m = self.THRASH if state.rng.ai_rng.next_int(2) == 0 else self.CHOMP
            else:
                m = self.BELLOW
        elif roll < 45 + 30:
            if last == "Thrash":
                m = self.BELLOW if state.rng.ai_rng.next_int(2) == 0 else self.CHOMP
            else:
                m = self.THRASH
        else:
            if self.move_history[-2:] == ["Chomp", "Chomp"]:
                m = self.BELLOW if state.rng.ai_rng.next_int(2) == 0 else self.THRASH
            else:
                m = self.CHOMP
        self.current_move = m
        return m

    def execute_move(self, state: GameState) -> None:
        m = self.current_move
        if m.name == "Bellow":
            self.powers[PowerId.STRENGTH] = self.powers.get(PowerId.STRENGTH, 0) + 3
            self.add_block(6)
        elif m.name == "Thrash":
            _enemy_attack(state, self, m)
            self.add_block(m.block)
        else:
            _enemy_attack(state, self, m)
        self.move_history.append(m.name)


class RedLouse(Enemy):
    def __init__(self, hp_rng):
        hp = hp_rng.next_int(8) + 10  # 10-17
        super().__init__("Louse_Red", "Red Louse", hp, hp)
        self.powers[PowerId.CURL_UP] = hp_rng.next_int(4) + 3  # 3-6 curl up block
        self._curl_triggered = False
        self._first = True

    def select_move(self, state):
        if self._first:
            self._first = False
            if state.rng.ai_rng.next_int(2) == 0:
                self.current_move = Move("Bite", IntentType.ATTACK, damage=5, hits=1)
            else:
                self.current_move = Move("Grow", IntentType.BUFF)
        else:
            roll = state.rng.ai_rng.next_int(100)
            if roll < 25:
                self.current_move = Move("Grow", IntentType.BUFF)
            else:
                # Base damage only — _enemy_attack adds Strength at execution
                # (baking it in here double-counted Grow stacks: 5+str dealt +str again)
                self.current_move = Move("Bite", IntentType.ATTACK, damage=5, hits=1)
        return self.current_move

    def execute_move(self, state):
        if self.current_move.name == "Grow":
            self.powers[PowerId.STRENGTH] = self.powers.get(PowerId.STRENGTH, 0) + 3
        else:
            _enemy_attack(state, self, self.current_move)

    def on_damage_taken(self, state, amount):
        if not self._curl_triggered and PowerId.CURL_UP in self.powers:
            self.add_block(self.powers[PowerId.CURL_UP])
            self._curl_triggered = True


class GreenLouse(Enemy):
    def __init__(self, hp_rng):
        hp = hp_rng.next_int(8) + 10
        super().__init__("Louse_Green", "Green Louse", hp, hp)
        self.powers[PowerId.CURL_UP] = hp_rng.next_int(4) + 3
        self._curl_triggered = False
        self._first = True

    def select_move(self, state):
        if self._first:
            self._first = False
            self.current_move = Move("Bite", IntentType.ATTACK, damage=5, hits=1)
        else:
            roll = state.rng.ai_rng.next_int(100)
            if roll < 25:
                self.current_move = Move("Spit Web", IntentType.DEBUFF)
            else:
                self.current_move = Move("Bite", IntentType.ATTACK, damage=5, hits=1)
        return self.current_move

    def execute_move(self, state):
        if self.current_move.name == "Spit Web":
            from .cards import _apply_power
            _apply_power(state, state.player, PowerId.WEAK, 2)
        else:
            _enemy_attack(state, self, self.current_move)

    def on_damage_taken(self, state, amount):
        if not self._curl_triggered and PowerId.CURL_UP in self.powers:
            self.add_block(self.powers[PowerId.CURL_UP])
            self._curl_triggered = True


class AcidSlimeS(Enemy):
    def __init__(self, hp_rng):
        hp = hp_rng.next_int(3) + 8  # 8-10
        super().__init__("AcidSlime_S", "Acid Slime (S)", hp, hp)

    def select_move(self, state):
        roll = state.rng.ai_rng.next_int(100)
        if roll < 50:
            self.current_move = Move("Tackle", IntentType.ATTACK, damage=3, hits=1)
        else:
            self.current_move = Move("Lick", IntentType.DEBUFF)
        return self.current_move

    def execute_move(self, state):
        if self.current_move.name == "Lick":
            from .cards import _apply_power
            _apply_power(state, state.player, PowerId.WEAK, 1)
        else:
            _enemy_attack(state, self, self.current_move)


class AcidSlimeM(Enemy):
    def __init__(self, hp_rng):
        hp = hp_rng.next_int(10) + 28  # 28-37
        super().__init__("AcidSlime_M", "Acid Slime (M)", hp, hp)
        self.move_history = []

    def select_move(self, state):
        last = self.move_history[-1] if self.move_history else None
        roll = state.rng.ai_rng.next_int(100)
        if roll < 40:
            if last == "Corrosive Spit":
                m = "Lick" if state.rng.ai_rng.next_int(2) == 0 else "Tackle"
                self.current_move = (Move("Lick", IntentType.DEBUFF) if m == "Lick"
                                     else Move("Tackle", IntentType.ATTACK, damage=7, hits=1))
            else:
                self.current_move = Move("Corrosive Spit", IntentType.ATTACK_DEBUFF, damage=7, hits=1)
        elif roll < 70:
            if last == "Tackle":
                m = "Lick" if state.rng.ai_rng.next_int(2) == 0 else "Corrosive Spit"
                self.current_move = (Move("Lick", IntentType.DEBUFF) if m == "Lick"
                                     else Move("Corrosive Spit", IntentType.ATTACK_DEBUFF, damage=7, hits=1))
            else:
                self.current_move = Move("Tackle", IntentType.ATTACK, damage=7, hits=1)
        else:
            if last == "Lick":
                m = "Corrosive Spit" if state.rng.ai_rng.next_int(2) == 0 else "Tackle"
                self.current_move = (Move("Corrosive Spit", IntentType.ATTACK_DEBUFF, damage=7, hits=1) if m == "Corrosive Spit"
                                     else Move("Tackle", IntentType.ATTACK, damage=7, hits=1))
            else:
                self.current_move = Move("Lick", IntentType.DEBUFF)
        return self.current_move

    def execute_move(self, state):
        m = self.current_move
        self.move_history.append(m.name)
        if m.name == "Lick":
            from .cards import _apply_power
            _apply_power(state, state.player, PowerId.WEAK, 1)
        elif m.name == "Corrosive Spit":
            _enemy_attack(state, self, m)
            from .cards import _apply_power
            _apply_power(state, state.player, PowerId.WEAK, 2)
        else:
            _enemy_attack(state, self, m)


class AcidSlimeL(Enemy):
    def __init__(self, hp_rng):
        hp = hp_rng.next_int(10) + 65  # 65-74
        super().__init__("AcidSlime_L", "Acid Slime (L)", hp, hp)
        self.move_history = []
        self._split = False

    def select_move(self, state):
        last = self.move_history[-1] if self.move_history else None
        roll = state.rng.ai_rng.next_int(100)
        if roll < 40:
            m = "Corrosive Spit" if last != "Corrosive Spit" else ("Lick" if state.rng.ai_rng.next_int(2)==0 else "Tackle")
        elif roll < 70:
            m = "Tackle" if last != "Tackle" else ("Lick" if state.rng.ai_rng.next_int(2)==0 else "Corrosive Spit")
        else:
            m = "Lick" if last != "Lick" else ("Corrosive Spit" if state.rng.ai_rng.next_int(2)==0 else "Tackle")
        if m == "Corrosive Spit":
            self.current_move = Move("Corrosive Spit", IntentType.ATTACK_DEBUFF, damage=11, hits=1)
        elif m == "Tackle":
            self.current_move = Move("Tackle", IntentType.ATTACK, damage=16, hits=1)
        else:
            self.current_move = Move("Lick", IntentType.DEBUFF)
        return self.current_move

    def execute_move(self, state):
        m = self.current_move
        self.move_history.append(m.name)
        if m.name == "Lick":
            from .cards import _apply_power
            _apply_power(state, state.player, PowerId.WEAK, 2)
        elif m.name == "Corrosive Spit":
            _enemy_attack(state, self, m)
            from .cards import _apply_power
            _apply_power(state, state.player, PowerId.WEAK, 3)
        else:
            _enemy_attack(state, self, m)

    def on_hp_threshold(self, state):
        if not self._split and self.hp <= self.max_hp // 2:
            self._split = True
            for _ in range(2):
                m = AcidSlimeM(state.rng.hp_rng)
                m.hp = m.max_hp = self.hp  # children inherit parent's current HP
                state.combat.enemies.append(m)
            self.hp = 0  # parent is replaced by its split children


class SpikeSlimeS(Enemy):
    def __init__(self, hp_rng):
        hp = hp_rng.next_int(3) + 10  # 10-12
        super().__init__("SpikeSlime_S", "Spike Slime (S)", hp, hp)

    def select_move(self, state):
        self.current_move = Move("Tackle", IntentType.ATTACK, damage=5, hits=1)
        return self.current_move

    def execute_move(self, state):
        _enemy_attack(state, self, self.current_move)


class SpikeSlimeM(Enemy):
    def __init__(self, hp_rng):
        hp = hp_rng.next_int(10) + 28  # 28-37
        super().__init__("SpikeSlime_M", "Spike Slime (M)", hp, hp)
        self.move_history = []

    def select_move(self, state):
        last = self.move_history[-1] if self.move_history else None
        roll = state.rng.ai_rng.next_int(100)
        if roll < 30:
            m = "Flame Tackle" if last != "Flame Tackle" else "Lunge"
        else:
            m = "Lunge" if last != "Lunge" else "Flame Tackle"
        if m == "Flame Tackle":
            self.current_move = Move("Flame Tackle", IntentType.ATTACK_DEBUFF, damage=8, hits=1)
        else:
            self.current_move = Move("Lunge", IntentType.ATTACK, damage=9, hits=1)
        return self.current_move

    def execute_move(self, state):
        m = self.current_move
        self.move_history.append(m.name)
        if m.name == "Flame Tackle":
            _enemy_attack(state, self, m)
            from .cards import _apply_power
            state.combat.discard_pile = getattr(state.combat, 'discard_pile', [])
            from .cards import Slimed
            state.combat.discard_pile.append(Slimed())
        else:
            _enemy_attack(state, self, m)


class SpikeSlimeL(Enemy):
    def __init__(self, hp_rng):
        hp = hp_rng.next_int(10) + 65  # 65-74
        super().__init__("SpikeSlime_L", "Spike Slime (L)", hp, hp)
        self.move_history = []
        self._split = False

    def select_move(self, state):
        last = self.move_history[-1] if self.move_history else None
        roll = state.rng.ai_rng.next_int(100)
        if roll < 30:
            m = "Flame Tackle" if last != "Flame Tackle" else "Lunge"
        else:
            m = "Lunge" if last != "Lunge" else "Flame Tackle"
        if m == "Flame Tackle":
            self.current_move = Move("Flame Tackle", IntentType.ATTACK_DEBUFF, damage=16, hits=1)
        else:
            self.current_move = Move("Lunge", IntentType.ATTACK, damage=18, hits=1)
        return self.current_move

    def execute_move(self, state):
        m = self.current_move
        self.move_history.append(m.name)
        if m.name == "Flame Tackle":
            _enemy_attack(state, self, m)
            from .cards import Slimed
            state.combat.discard_pile.append(Slimed())
            state.combat.discard_pile.append(Slimed())
        else:
            _enemy_attack(state, self, m)

    def on_hp_threshold(self, state):
        if not self._split and self.hp <= self.max_hp // 2:
            self._split = True
            for _ in range(2):
                m = SpikeSlimeM(state.rng.hp_rng)
                m.hp = m.max_hp = self.hp  # children inherit parent's current HP
                state.combat.enemies.append(m)
            self.hp = 0  # parent is replaced by its split children


class FungalBeast(Enemy):
    def __init__(self, hp_rng):
        hp = hp_rng.next_int(6) + 22  # 22-27
        super().__init__("FungalBeast", "Fungal Beast", hp, hp)
        self.powers[PowerId.SPORE_CLOUD] = 2
        self.move_history = []

    def select_move(self, state):
        last = self.move_history[-1] if self.move_history else None
        roll = state.rng.ai_rng.next_int(100)
        if roll < 60:
            m = "Bite" if last != "Bite" else "Grow"
        else:
            m = "Grow" if last != "Grow" else "Bite"
        if m == "Bite":
            self.current_move = Move("Bite", IntentType.ATTACK, damage=6, hits=1)
        else:
            self.current_move = Move("Grow", IntentType.BUFF)
        return self.current_move

    def execute_move(self, state):
        m = self.current_move
        self.move_history.append(m.name)
        if m.name == "Grow":
            self.powers[PowerId.STRENGTH] = self.powers.get(PowerId.STRENGTH, 0) + 3
        else:
            _enemy_attack(state, self, m)

    def on_death(self, state):
        from .cards import _apply_power
        _apply_power(state, state.player, PowerId.VULNERABLE, self.powers.get(PowerId.SPORE_CLOUD, 2))


# ── Act 1 Elites ──────────────────────────────────────────────────────────────

class GremlinNob(Enemy):
    def __init__(self, hp_rng):
        hp = hp_rng.next_int(11) + 82  # 82-92 (ascension may vary)
        super().__init__("GremlinNob", "Gremlin Nob", hp, hp)
        self._first = True
        self.move_history = []

    def select_move(self, state):
        if self._first:
            self._first = False
            self.current_move = Move("Bellow", IntentType.BUFF)
            return self.current_move
        last = self.move_history[-1] if self.move_history else None
        roll = state.rng.ai_rng.next_int(100)
        if roll < 33:
            m = "Rush" if last != "Rush" else "Skull Bash"
        else:
            m = "Skull Bash" if last != "Skull Bash" else "Rush"
        if m == "Rush":
            self.current_move = Move("Rush", IntentType.ATTACK, damage=14, hits=1)
        else:
            self.current_move = Move("Skull Bash", IntentType.ATTACK_DEBUFF, damage=6, hits=1)
        return self.current_move

    def execute_move(self, state):
        m = self.current_move
        self.move_history.append(m.name)
        if m.name == "Bellow":
            self.powers[PowerId.ANGER_ENEMY] = self.powers.get(PowerId.ANGER_ENEMY, 0)
            # Enrage: gain strength when player plays a skill
            self.powers["enrage"] = 2
        elif m.name == "Skull Bash":
            _enemy_attack(state, self, m)
            from .cards import _apply_power
            _apply_power(state, state.player, PowerId.VULNERABLE, 2)
        else:
            _enemy_attack(state, self, m)


class Lagavulin(Enemy):
    def __init__(self, hp_rng):
        hp = hp_rng.next_int(8) + 109  # 109-116
        super().__init__("Lagavulin", "Lagavulin", hp, hp)
        self.powers[PowerId.METALLICIZE] = 8
        self.powers[PowerId.ARTIFACT] = 0
        self._asleep = True
        self._asleep_turns = 0
        self._awoken = False
        self.move_history = []

    def select_move(self, state):
        if self._asleep:
            if self._asleep_turns >= 2 or state.player.hp < state.player.max_hp:
                self._asleep = False
                self._awoken = True
                self.current_move = Move("Attack", IntentType.ATTACK, damage=18, hits=1)
            else:
                self._asleep_turns += 1
                self.current_move = Move("Sleep", IntentType.SLEEP)
        else:
            last = self.move_history[-1] if self.move_history else None
            if last == "Siphon Soul":
                self.current_move = Move("Attack", IntentType.ATTACK, damage=18, hits=1)
            elif last == "Attack":
                self.current_move = Move("Siphon Soul", IntentType.DEBUFF)
            else:
                self.current_move = Move("Attack", IntentType.ATTACK, damage=18, hits=1)
        return self.current_move

    def execute_move(self, state):
        m = self.current_move
        self.move_history.append(m.name)
        if m.name == "Sleep":
            pass  # do nothing; has Metallicize
        elif m.name == "Siphon Soul":
            from .cards import _apply_power
            _apply_power(state, state.player, PowerId.STRENGTH, -1)
            _apply_power(state, state.player, PowerId.DEXTERITY, -1)
        else:
            _enemy_attack(state, self, m)


class Sentry(Enemy):
    """Used in groups of 3."""
    def __init__(self, hp_rng, index: int = 0):
        hp = hp_rng.next_int(7) + 38  # 38-44
        super().__init__(f"Sentry_{index}", f"Sentry", hp, hp)
        self.powers[PowerId.ARTIFACT] = 0
        # Sentries alternate based on position parity
        self._first_move = "Beam" if index % 2 == 0 else "Bolt"
        self._toggle = (index % 2 == 0)

    def select_move(self, state):
        if self._toggle:
            self.current_move = Move("Beam", IntentType.ATTACK, damage=9, hits=1)
        else:
            self.current_move = Move("Bolt", IntentType.DEBUFF)
        self._toggle = not self._toggle
        return self.current_move

    def execute_move(self, state):
        if self.current_move.name == "Bolt":
            from .cards import Dazed, _apply_power
            state.combat.draw_pile.insert(0, Dazed())
            state.combat.draw_pile.insert(0, Dazed())
        else:
            _enemy_attack(state, self, self.current_move)


# ── Act 1 Bosses ──────────────────────────────────────────────────────────────

class SlimeBoss(Enemy):
    def __init__(self, hp_rng):
        hp = hp_rng.next_int(10) + 140  # 140-149
        super().__init__("SlimeBoss", "Slime Boss", hp, hp)
        self.move_history = []
        self._split = False
        self._phase = 0

    def select_move(self, state):
        # Pattern: Goop Spray, Preparing, Slam, Preparing, Slam, repeat
        pattern = ["Goop Spray", "Preparing", "Slam", "Preparing", "Slam"]
        move_name = pattern[self._phase % len(pattern)]
        if move_name == "Goop Spray":
            self.current_move = Move("Goop Spray", IntentType.DEBUFF)
        elif move_name == "Preparing":
            self.current_move = Move("Preparing", IntentType.UNKNOWN)
        else:
            self.current_move = Move("Slam", IntentType.ATTACK, damage=35, hits=1)
        self._phase += 1
        return self.current_move

    def execute_move(self, state):
        if self.current_move.name == "Goop Spray":
            from .cards import Slimed
            for _ in range(3):
                state.combat.discard_pile.append(Slimed())
        elif self.current_move.name == "Slam":
            _enemy_attack(state, self, self.current_move)

    def on_hp_threshold(self, state):
        if not self._split and self.hp <= self.max_hp // 2:
            self._split = True
            m1 = SpikeSlimeL(state.rng.hp_rng)
            m2 = AcidSlimeL(state.rng.hp_rng)
            state.combat.enemies.append(m1)
            state.combat.enemies.append(m2)
            # SlimeBoss dies when split
            self.hp = 0


class Hexaghost(Enemy):
    def __init__(self, hp_rng):
        hp = hp_rng.next_int(10) + 250  # 250-259
        super().__init__("Hexaghost", "Hexaghost", hp, hp)
        self._phase = 0
        self._activated = False
        self._inferno_count = 0

    def select_move(self, state):
        if not self._activated:
            self._activated = True
            self.current_move = Move("Activate", IntentType.UNKNOWN)
            return self.current_move
        # 6-move cycling pattern after activation
        pattern = ["Divider", "Inferno", "Inflame", "Inferno", "Sear", "Inferno"]
        move_name = pattern[self._phase % len(pattern)]
        self._phase += 1
        if move_name == "Divider":
            self.current_move = Move("Divider", IntentType.ATTACK, damage=max(1, state.player.hp // 12), hits=6)
        elif move_name == "Inferno":
            self._inferno_count += 1
            dmg = 2 * self._inferno_count
            self.current_move = Move("Inferno", IntentType.ATTACK, damage=dmg, hits=6)
        elif move_name == "Inflame":
            self.current_move = Move("Inflame", IntentType.BUFF)
        else:  # Sear
            self.current_move = Move("Sear", IntentType.ATTACK_DEBUFF, damage=6, hits=1)
        return self.current_move

    def execute_move(self, state):
        m = self.current_move
        if m.name == "Activate":
            pass
        elif m.name in ("Divider", "Inferno"):
            _enemy_attack(state, self, m)
            if m.name == "Divider":
                from .cards import Burn
                for _ in range(6):
                    state.combat.draw_pile.insert(0, Burn())
        elif m.name == "Inflame":
            self.powers[PowerId.STRENGTH] = self.powers.get(PowerId.STRENGTH, 0) + 2
            self.add_block(12)
        else:  # Sear
            _enemy_attack(state, self, m)
            from .cards import Burn
            state.combat.draw_pile.insert(0, Burn())


# ── Enemy factory ─────────────────────────────────────────────────────────────

ENEMY_REGISTRY = {
    "Cultist": Cultist,
    "JawWorm": JawWorm,
    "RedLouse": RedLouse,
    "GreenLouse": GreenLouse,
    "AcidSlimeS": AcidSlimeS,
    "AcidSlimeM": AcidSlimeM,
    "AcidSlimeL": AcidSlimeL,
    "SpikeSlimeS": SpikeSlimeS,
    "SpikeSlimeM": SpikeSlimeM,
    "SpikeSlimeL": SpikeSlimeL,
    "FungalBeast": FungalBeast,
    "GremlinNob": GremlinNob,
    "Lagavulin": Lagavulin,
    "Sentry": Sentry,
    "SlimeBoss": SlimeBoss,
    "Hexaghost": Hexaghost,
}


def make_enemy(enemy_id: str, hp_rng, **kwargs) -> Enemy:
    cls = ENEMY_REGISTRY.get(enemy_id)
    if cls is None:
        raise ValueError(f"Unknown enemy: {enemy_id}")
    return cls(hp_rng, **kwargs)
