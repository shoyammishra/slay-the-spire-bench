"""Act 2 and Act 3 enemy definitions."""
from __future__ import annotations
from typing import TYPE_CHECKING

from .enemies import Enemy, Move, _enemy_attack, _enemy_apply_power
from .enums import IntentType, PowerId

if TYPE_CHECKING:
    from .state import GameState


# ── Act 2 Regular ─────────────────────────────────────────────────────────────

class Chosen(Enemy):
    def __init__(self, hp_rng):
        hp = hp_rng.next_int(14) + 95  # 95-108
        super().__init__("Chosen", "Chosen", hp, hp)
        # Real Chosen has NO Artifact — the invented stack silently ate the
        # player's first debuff (Bash Vuln, Neutralize Weak, poison openers),
        # punishing debuff archetypes, Silent most (bug_audit M5). Removed.
        self.move_history = []

    def select_move(self, state):
        last = self.move_history[-1] if self.move_history else None
        roll = state.rng.ai_rng.next_int(100)
        if roll < 40:
            self.current_move = Move("Poke", IntentType.ATTACK, damage=5, hits=2) if last != "Poke" else Move("Debilitate", IntentType.DEBUFF)
        elif roll < 70:
            self.current_move = Move("Zap", IntentType.ATTACK, damage=18) if last != "Zap" else Move("Poke", IntentType.ATTACK, damage=5, hits=2)
        else:
            self.current_move = Move("Debilitate", IntentType.DEBUFF) if last != "Debilitate" else Move("Zap", IntentType.ATTACK, damage=18)
        return self.current_move

    def execute_move(self, state):
        m = self.current_move
        self.move_history.append(m.name)
        if m.name == "Debilitate":
            from .cards import _apply_power
            _apply_power(state, state.player, PowerId.VULNERABLE, 2)
            _apply_power(state, state.player, PowerId.WEAK, 2)
        else:
            _enemy_attack(state, self, m)


class ShellParasite(Enemy):
    def __init__(self, hp_rng):
        hp = hp_rng.next_int(14) + 68  # 68-81
        super().__init__("ShellParasite", "Shell Parasite", hp, hp)
        self.move_history = []

    def select_move(self, state):
        pattern = ["Suck", "Fell", "Suck", "Stunned", "Suck"]
        idx = len(self.move_history) % len(pattern)
        name = pattern[idx]
        if name == "Suck":
            self.current_move = Move("Suck", IntentType.ATTACK_DEBUFF, damage=4, hits=3)
        elif name == "Fell":
            self.current_move = Move("Fell", IntentType.ATTACK, damage=24)
        else:
            self.current_move = Move("Stunned", IntentType.SLEEP)
        return self.current_move

    def execute_move(self, state):
        m = self.current_move
        self.move_history.append(m.name)
        if m.name == "Suck":
            _enemy_attack(state, self, m)
            from .cards import _apply_power
            _apply_power(state, state.player, PowerId.FRAIL, 1)
        elif m.name == "Fell":
            _enemy_attack(state, self, m)
        # Stunned: do nothing


class Byrd(Enemy):
    def __init__(self, hp_rng):
        hp = hp_rng.next_int(4) + 25  # 25-28
        super().__init__("Byrd", "Byrd", hp, hp)
        self.move_history = []
        self._flying = True
        self._flight_hits = 3  # grounded after 3 damaging attack hits (Flight)

    def select_move(self, state):
        pattern = ["Peck", "Peck", "Peck", "Swoop", "Peck", "Peck", "Headbutt"]
        idx = len(self.move_history) % len(pattern)
        name = pattern[idx]
        if name == "Peck":
            self.current_move = Move("Peck", IntentType.ATTACK, damage=1, hits=6)
        elif name == "Swoop":
            self.current_move = Move("Swoop", IntentType.ATTACK, damage=14)
        else:
            self.current_move = Move("Headbutt", IntentType.ATTACK, damage=3)
        return self.current_move

    def execute_move(self, state):
        self.move_history.append(self.current_move.name)
        _enemy_attack(state, self, self.current_move)

    def on_damage_taken(self, state, amount, from_attack=True):
        # Flight: each damaging ATTACK hit reduces the flight counter; at 0 the
        # Byrd is grounded (attack damage no longer halved). Non-attack damage
        # (Combust/Juggernaut) does NOT reduce Flight, matching the real game.
        # Real Byrds regain Flight later — the grounded-stays-grounded
        # simplification is fine for our short fights (Headbutt is its grounded
        # move; documented-design).
        if from_attack and self._flying:
            self._flight_hits -= 1
            if self._flight_hits <= 0:
                self._flying = False


class CenturionAndMystic(Enemy):
    """Centurion: fights alongside Mystic."""
    def __init__(self, hp_rng, is_mystic: bool = False):
        if is_mystic:
            hp = hp_rng.next_int(10) + 48  # 48-57
            super().__init__("Mystic", "Mystic", hp, hp)
        else:
            hp = hp_rng.next_int(10) + 76  # 76-85
            super().__init__("Centurion", "Centurion", hp, hp)
        self.is_mystic = is_mystic
        self.move_history = []

    def select_move(self, state):
        if self.is_mystic:
            # Mystic heals Centurion or debuffs player
            roll = state.rng.ai_rng.next_int(100)
            if roll < 40:
                self.current_move = Move("Heal", IntentType.BUFF)
            else:
                self.current_move = Move("Sanctity", IntentType.BUFF)
        else:
            pattern = ["Slash", "Slash", "Fury"]
            idx = len(self.move_history) % len(pattern)
            name = pattern[idx]
            if name == "Slash":
                self.current_move = Move("Slash", IntentType.ATTACK, damage=12)
            else:
                self.current_move = Move("Fury", IntentType.ATTACK, damage=6, hits=3)
        return self.current_move

    def execute_move(self, state):
        m = self.current_move
        self.move_history.append(m.name)
        if m.name == "Heal":
            # Heal the Centurion
            for e in state.combat.enemies:
                if e.id == "Centurion":
                    e.hp = min(e.max_hp, e.hp + 10)
        elif m.name == "Sanctity":
            self.add_block(6)
        else:
            _enemy_attack(state, self, m)


class TorchHead(Enemy):
    def __init__(self, hp_rng):
        hp = hp_rng.next_int(6) + 38  # 38-43
        super().__init__("TorchHead", "Torch Head", hp, hp)

    def select_move(self, state):
        self.current_move = Move("Flame Tackle", IntentType.ATTACK, damage=7, hits=2)
        return self.current_move

    def execute_move(self, state):
        _enemy_attack(state, self, self.current_move)
        from .cards import Burn
        state.combat.discard_pile.append(Burn())


class Transient(Enemy):
    def __init__(self, hp_rng):
        hp = hp_rng.next_int(20) + 999  # high HP; Fading escapes at end of turn 5
        super().__init__("Transient", "Transient", hp, hp)
        # Real Transient has NO Intangible (it has Fading + Shifting). The old
        # permanent Intangible + set-hp=0-on-turn-5 made the fight decision-free
        # and scored the ~150-damage HP tax as a WIN. Now legitimately blockable
        # and killable. Shifting stays unimplemented (documented-design).
        self._turns = 0

    def select_move(self, state):
        self._turns += 1
        # Attack curve: single hit 30 + 10 per prior turn (real Attack Debilitate
        # curve), not the old 10×turn-count multi-hit.
        dmg = 30 + 10 * (self._turns - 1)
        self.current_move = Move("Attack", IntentType.ATTACK, damage=dmg, hits=1)
        return self.current_move

    def execute_move(self, state):
        _enemy_attack(state, self, self.current_move)
        if self._turns >= 5:
            self.hp = 0  # Fading: flees at the end of its 5th turn (ends fight)


class BookOfStabbing(Enemy):
    def __init__(self, hp_rng):
        hp = hp_rng.next_int(16) + 160  # 160-175
        super().__init__("BookOfStabbing", "Book of Stabbing", hp, hp)
        # Multi-Stab hits = 2 + number of prior Multi-Stabs (real scaling). The
        # counter increments when Multi-Stab is USED, not on every other move.
        self._stabs = 2
        self.move_history = []

    def select_move(self, state):
        if len(self.move_history) % 3 == 2:
            self.current_move = Move("Multi-Stab", IntentType.ATTACK, damage=6, hits=self._stabs)
        else:
            # Single Stab is 21 damage in the real fight (was 6).
            self.current_move = Move("Stab", IntentType.ATTACK, damage=21, hits=1)
        return self.current_move

    def execute_move(self, state):
        self.move_history.append(self.current_move.name)
        _enemy_attack(state, self, self.current_move)
        if self.current_move.name == "Multi-Stab":
            self._stabs += 1


class WrithingMass(Enemy):
    def __init__(self, hp_rng):
        hp = hp_rng.next_int(15) + 160  # 160-174
        super().__init__("WrithingMass", "Writhing Mass", hp, hp)
        self.powers[PowerId.MALLEABLE] = 3
        self._malleable_base = 3  # _tick_enemy_powers resets Malleable to this
        self.move_history = []

    def select_move(self, state):
        roll = state.rng.ai_rng.next_int(100)
        if roll < 15:
            self.current_move = Move("Flail", IntentType.ATTACK, damage=16)
        elif roll < 35:
            # Real Wither: 10 damage + 2 Weak + 2 Vulnerable (was 12 dmg, Weak 2
            # only; the audit's Frail recollection was wiki-corrected 2026-07-14).
            self.current_move = Move("Wither", IntentType.ATTACK_DEBUFF, damage=10)
        elif roll < 60:
            self.current_move = Move("Strong Strike", IntentType.ATTACK, damage=38)
        else:
            self.current_move = Move("Implant", IntentType.DEBUFF)
        return self.current_move

    def execute_move(self, state):
        m = self.current_move
        self.move_history.append(m.name)
        if m.name == "Wither":
            # Real Wither: 10 damage + 2 Weak + 2 VULNERABLE (wiki-checked
            # 2026-07-14; the audit's L8 recollection said Frail — corrected).
            _enemy_attack(state, self, m)
            from .cards import _apply_power
            _apply_power(state, state.player, PowerId.WEAK, 2)
            _apply_power(state, state.player, PowerId.VULNERABLE, 2)
        elif m.name == "Implant":
            # Implant → NO_DRAW-1 is the documented stand-in for the real
            # Parasite curse (see documented-design register).
            from .cards import _apply_power
            _apply_power(state, state.player, PowerId.NO_DRAW, 1)
        else:
            _enemy_attack(state, self, m)


# ── Act 2 Elites ──────────────────────────────────────────────────────────────

class GremlinLeader(Enemy):
    def __init__(self, hp_rng):
        hp = hp_rng.next_int(10) + 140  # 140-149
        super().__init__("GremlinLeader", "Gremlin Leader", hp, hp)
        self.move_history = []

    def _spawn_gremlins(self, state):
        from .enemies import ENEMY_REGISTRY
        for _ in range(2):
            if len(state.combat.enemies) < 5:
                g = ENEMY_REGISTRY["JawWorm"](state.rng.hp_rng)  # stand-in for gremlin
                g.hp = 10; g.max_hp = 10
                state.combat.enemies.append(g)

    def select_move(self, state):
        pattern = ["Rally", "Encourage", "Stab", "Stab", "Encourage"]
        idx = len(self.move_history) % len(pattern)
        name = pattern[idx]
        if name == "Rally":
            self.current_move = Move("Rally!", IntentType.BUFF)
        elif name == "Encourage":
            self.current_move = Move("Encourage", IntentType.BUFF)
        else:
            self.current_move = Move("Stab", IntentType.ATTACK, damage=6, hits=3)
        return self.current_move

    def execute_move(self, state):
        m = self.current_move
        self.move_history.append(m.name)
        if m.name == "Rally!":
            self._spawn_gremlins(state)
        elif m.name == "Encourage":
            for e in state.combat.enemies:
                if e.hp > 0 and e is not self:
                    e.powers[PowerId.STRENGTH] = e.powers.get(PowerId.STRENGTH, 0) + 3
                    e.add_block(6)
        else:
            _enemy_attack(state, self, m)


class Slavers(Enemy):
    """Red Slaver + Blue Slaver as an elite encounter."""
    def __init__(self, hp_rng, is_red: bool = True):
        if is_red:
            hp = hp_rng.next_int(8) + 46  # 46-53
            super().__init__("RedSlaver", "Red Slaver", hp, hp)
        else:
            hp = hp_rng.next_int(8) + 38  # 38-45
            super().__init__("BlueSlaver", "Blue Slaver", hp, hp)
        self.is_red = is_red
        self.move_history = []

    def select_move(self, state):
        if self.is_red:
            pattern = ["Stab", "Rake", "Stab", "Entangle"]
            idx = len(self.move_history) % len(pattern)
            name = pattern[idx]
            if name == "Entangle":
                self.current_move = Move("Entangle", IntentType.DEBUFF)
            elif name == "Rake":
                self.current_move = Move("Rake", IntentType.ATTACK_DEBUFF, damage=7)
            else:
                self.current_move = Move("Stab", IntentType.ATTACK, damage=12)
        else:
            roll = state.rng.ai_rng.next_int(100)
            if roll < 40:
                self.current_move = Move("Stab", IntentType.ATTACK, damage=6)
            else:
                self.current_move = Move("Rake", IntentType.ATTACK_DEBUFF, damage=7)
        return self.current_move

    def execute_move(self, state):
        m = self.current_move
        self.move_history.append(m.name)
        if m.name == "Entangle":
            from .cards import _apply_power
            _apply_power(state, state.player, PowerId.ENTANGLED, 1)
        elif m.name == "Rake":
            _enemy_attack(state, self, m)
            from .cards import _apply_power
            _apply_power(state, state.player, PowerId.WEAK, 1)
        else:
            _enemy_attack(state, self, m)


class Taskmaster(Enemy):
    def __init__(self, hp_rng):
        hp = hp_rng.next_int(12) + 54  # 54-65
        super().__init__("Taskmaster", "Taskmaster", hp, hp)
        self.move_history = []

    def select_move(self, state):
        self.current_move = Move("Scouring Whip", IntentType.ATTACK_DEBUFF, damage=7)
        return self.current_move

    def execute_move(self, state):
        self.move_history.append("Scouring Whip")
        _enemy_attack(state, self, self.current_move)
        from .cards import Wound
        state.combat.discard_pile.append(Wound())  # was draw-pile top (M3)


# ── Act 2 Bosses ──────────────────────────────────────────────────────────────

class TheCollector(Enemy):
    def __init__(self, hp_rng):
        hp = hp_rng.next_int(10) + 260  # 260-269
        super().__init__("TheCollector", "The Collector", hp, hp)
        self.move_history = []
        self._spawned = False

    def _spawn_torches(self, state):
        # Real Collector refills only DEAD torches (max 2 alive). The old
        # len(enemies) < 4 gate counted the Collector itself, letting a 3rd
        # torch spawn while 2 were alive (bug_audit L5).
        alive_torches = sum(1 for e in state.combat.enemies
                            if e.id == "TorchHead" and e.hp > 0)
        for _ in range(max(0, 2 - alive_torches)):
            torch = TorchHead(state.rng.hp_rng)
            state.combat.enemies.append(torch)

    def select_move(self, state):
        pattern = ["Spawn", "Buff", "Mega Slash", "Buff", "Mega Slash"]
        idx = len(self.move_history) % len(pattern)
        name = pattern[idx]
        if name == "Spawn":
            self.current_move = Move("Spawn!", IntentType.BUFF)
        elif name == "Buff":
            self.current_move = Move("Buff", IntentType.BUFF)
        else:
            self.current_move = Move("Mega Slash", IntentType.ATTACK, damage=18)
        return self.current_move

    def execute_move(self, state):
        m = self.current_move
        self.move_history.append(m.name)
        if m.name == "Spawn!":
            self._spawn_torches(state)
        elif m.name == "Buff":
            for e in state.combat.enemies:
                if e.hp > 0:
                    e.powers[PowerId.STRENGTH] = e.powers.get(PowerId.STRENGTH, 0) + 3
        else:
            _enemy_attack(state, self, m)


class BronzeAutomaton(Enemy):
    def __init__(self, hp_rng):
        hp = hp_rng.next_int(10) + 300  # 300-309
        super().__init__("BronzeAutomaton", "Bronze Automaton", hp, hp)
        self.move_history = []
        self.powers[PowerId.ARTIFACT] = 3
        self._spawned_orbs = False

    def select_move(self, state):
        pattern = ["Spawn", "Flail", "Flail", "Hyper Beam", "Stunned", "Stunned"]
        idx = len(self.move_history) % len(pattern)
        name = pattern[idx]
        if name == "Spawn":
            # Orbs spawn ONCE in the real fight. On repeat "Spawn" slots (moves
            # 6, 12, …) Boost instead (+3 Strength, +9 block) — the old code had
            # no cap, spawning 2 fresh orbs every 6 turns unbounded (bug_audit H2).
            if not self._spawned_orbs:
                self.current_move = Move("Spawn Orbs", IntentType.BUFF)
            else:
                self.current_move = Move("Boost", IntentType.BUFF)
        elif name == "Hyper Beam":
            self.current_move = Move("Hyper Beam", IntentType.ATTACK, damage=45)
        elif name == "Stunned":
            self.current_move = Move("Stunned", IntentType.SLEEP)
        else:
            self.current_move = Move("Flail", IntentType.ATTACK, damage=7, hits=2)
        return self.current_move

    def execute_move(self, state):
        m = self.current_move
        self.move_history.append(m.name)
        if m.name == "Spawn Orbs":
            # Spawn 2 Orb Walkers, once per combat.
            for _ in range(2):
                orb = _OrbWalker(state.rng.hp_rng)
                state.combat.enemies.append(orb)
            self._spawned_orbs = True
        elif m.name == "Boost":
            self.powers[PowerId.STRENGTH] = self.powers.get(PowerId.STRENGTH, 0) + 3
            self.add_block(9)
        elif m.name == "Hyper Beam":
            _enemy_attack(state, self, m)
        elif m.name != "Stunned":
            _enemy_attack(state, self, m)


class _OrbWalker(Enemy):
    def __init__(self, hp_rng):
        hp = hp_rng.next_int(7) + 52  # 52-58 (real Bronze Orb band; was 80-84)
        super().__init__("OrbWalker", "Orb Walker", hp, hp)

    def select_move(self, state):
        roll = state.rng.ai_rng.next_int(100)
        if roll < 50:
            self.current_move = Move("Laser", IntentType.ATTACK, damage=10)
        else:
            self.current_move = Move("Claw", IntentType.ATTACK, damage=15)
        return self.current_move

    def execute_move(self, state):
        _enemy_attack(state, self, self.current_move)


class TheChamp(Enemy):
    def __init__(self, hp_rng):
        hp = hp_rng.next_int(10) + 420  # 420-429
        super().__init__("TheChamp", "The Champ", hp, hp)
        self.move_history = []
        self._phase2 = False

    def select_move(self, state):
        if not self._phase2 and self.hp <= self.max_hp * 0.5:
            self._phase2 = True
            self.current_move = Move("Heavy Slash", IntentType.ATTACK, damage=16)
            return self.current_move

        if not self._phase2:
            pattern = ["Gloat", "Execute", "Execute", "Flex", "Smash"]
            idx = len(self.move_history) % len(pattern)
            name = pattern[idx]
        else:
            pattern = ["Defensive", "Execute", "Heavy Slash", "Taunt"]
            idx = len(self.move_history) % len(pattern)
            name = pattern[idx]

        if name == "Execute":
            self.current_move = Move("Execute", IntentType.ATTACK, damage=10, hits=2)
        elif name == "Heavy Slash":
            self.current_move = Move("Heavy Slash", IntentType.ATTACK, damage=16)
        elif name == "Smash":
            self.current_move = Move("Smash", IntentType.ATTACK, damage=22)
        elif name == "Flex":
            self.current_move = Move("Flex", IntentType.BUFF)
        elif name == "Gloat":
            self.current_move = Move("Gloat", IntentType.BUFF)
        elif name == "Defensive":
            self.current_move = Move("Defensive Stance", IntentType.BLOCK, block=15)
        else:
            self.current_move = Move("Taunt", IntentType.DEBUFF)
        return self.current_move

    def execute_move(self, state):
        m = self.current_move
        self.move_history.append(m.name)
        if m.intent == IntentType.ATTACK:
            _enemy_attack(state, self, m)
        elif m.name in ("Flex", "Gloat"):
            self.powers[PowerId.STRENGTH] = self.powers.get(PowerId.STRENGTH, 0) + 4
        elif m.name == "Defensive Stance":
            self.add_block(m.block)
        elif m.name == "Taunt":
            from .cards import _apply_power
            _apply_power(state, state.player, PowerId.WEAK, 2)
            _apply_power(state, state.player, PowerId.VULNERABLE, 2)


# ── Act 3 enemies ─────────────────────────────────────────────────────────────

class Darkling(Enemy):
    def __init__(self, hp_rng):
        hp = hp_rng.next_int(6) + 48  # 48-53
        super().__init__("Darkling", "Darkling", hp, hp)
        self.move_history = []
        self._reborn = False

    def select_move(self, state):
        roll = state.rng.ai_rng.next_int(100)
        if roll < 50:
            self.current_move = Move("Chomp", IntentType.ATTACK, damage=9)
        else:
            self.current_move = Move("Nip", IntentType.ATTACK_DEBUFF, damage=7)
        return self.current_move

    def execute_move(self, state):
        m = self.current_move
        self.move_history.append(m.name)
        if m.name == "Nip":
            _enemy_attack(state, self, m)
            from .cards import _apply_power
            _apply_power(state, state.player, PowerId.FRAIL, 1)
        else:
            _enemy_attack(state, self, m)

    def on_death(self, state):
        if not self._reborn:
            self._reborn = True
            self.hp = self.max_hp // 2
            self.alive = True
            self.powers[PowerId.STRENGTH] = self.powers.get(PowerId.STRENGTH, 0) + 2


class GiantHead(Enemy):
    def __init__(self, hp_rng):
        hp = hp_rng.next_int(10) + 500  # 500-509
        super().__init__("GiantHead", "Giant Head", hp, hp)
        self._slow_count = 0
        self.move_history = []

    def select_move(self, state):
        if len(self.move_history) < 3:
            # Real Count is a 13-damage attack (was a no-damage +1 Str buff).
            self.current_move = Move("Count", IntentType.ATTACK, damage=13)
        else:
            self._slow_count += 1
            # It Is Time: 30, +5 per use, capped at 40 (was 13 + 2/use).
            dmg = min(40, 30 + 5 * (self._slow_count - 1))
            self.current_move = Move("It Is Time", IntentType.ATTACK, damage=dmg)
        return self.current_move

    def execute_move(self, state):
        m = self.current_move
        self.move_history.append(m.name)
        _enemy_attack(state, self, m)


class Maw(Enemy):
    def __init__(self, hp_rng):
        hp = hp_rng.next_int(10) + 300  # 300-309
        super().__init__("Maw", "Maw", hp, hp)
        self.move_history = []

    def select_move(self, state):
        # Roar is turn-1 ONLY (real fight). After that, cycle Drool/Nom/Nom.
        if not self.move_history:
            self.current_move = Move("Roar", IntentType.DEBUFF)
            return self.current_move
        cycle = ["Drool", "Nom", "Nom"]
        name = cycle[(len(self.move_history) - 1) % len(cycle)]
        if name == "Drool":
            self.current_move = Move("Drool", IntentType.BUFF)
        else:
            self.current_move = Move("Nom", IntentType.ATTACK, damage=25)
        return self.current_move

    def execute_move(self, state):
        m = self.current_move
        self.move_history.append(m.name)
        if m.name == "Roar":
            from .cards import _apply_power
            _apply_power(state, state.player, PowerId.VULNERABLE, 3)
            _apply_power(state, state.player, PowerId.WEAK, 3)
        elif m.name == "Drool":
            # Real Drool: Maw gains +5 Strength (was an invented CONFUSED that
            # punished the LLM's cost model — not this fight's mechanic; M7).
            self.powers[PowerId.STRENGTH] = self.powers.get(PowerId.STRENGTH, 0) + 5
        else:
            _enemy_attack(state, self, m)


class Nemesis(Enemy):
    """Elite: 3 intangible ethereal turns before becoming vulnerable."""
    def __init__(self, hp_rng):
        hp = hp_rng.next_int(10) + 185  # 185-194
        super().__init__("Nemesis", "Nemesis", hp, hp)
        self.powers[PowerId.INTANGIBLE] = 1
        self._phase = 0
        self.move_history = []

    def select_move(self, state):
        if self._phase < 3:
            self._phase += 1
            # Stay Intangible through player turns 1-3 (documented 3-turn
            # simplification), droppable from turn 4. Enemy INTANGIBLE ticks down
            # each round (_tick_enemy_powers) and select_move runs AFTER that
            # tick, so re-apply it on phases 1,2,3 — this keeps the turn-3 attack
            # capped at 1. It is popped when phase 4 is selected (else branch).
            self.powers[PowerId.INTANGIBLE] = 1
            self.current_move = Move("Scythe", IntentType.ATTACK, damage=45)
        else:
            self.powers.pop(PowerId.INTANGIBLE, None)
            pattern = ["Debuff", "Scythe", "Scythe"]
            idx = (self._phase - 3) % len(pattern)
            self._phase += 1
            if pattern[idx] == "Debuff":
                self.current_move = Move("Debuff", IntentType.DEBUFF)
            else:
                self.current_move = Move("Scythe", IntentType.ATTACK, damage=45)
        return self.current_move

    def execute_move(self, state):
        m = self.current_move
        self.move_history.append(m.name)
        if m.name == "Debuff":
            from .cards import Burn
            for _ in range(3):
                state.combat.discard_pile.append(Burn())  # was draw-pile top (M3)
        else:
            _enemy_attack(state, self, m)


class Reptomancer(Enemy):
    """Elite: spawns Dagger enemies each turn."""
    def __init__(self, hp_rng):
        hp = hp_rng.next_int(10) + 180  # 180-189
        super().__init__("Reptomancer", "Reptomancer", hp, hp)
        self.move_history = []

    def _spawn_dagger(self, state):
        dagger = _SnakeDagger(state.rng.hp_rng)
        state.combat.enemies.append(dagger)

    def select_move(self, state):
        pattern = ["Summon", "Slash", "Slash", "Summon", "Big Slash"]
        idx = len(self.move_history) % len(pattern)
        name = pattern[idx]
        if name == "Summon":
            # Real Reptomancer caps at 4 daggers alive; a Summon slot with 4+
            # already out fizzles to Slash (bug_audit L7).
            alive_daggers = sum(1 for e in state.combat.enemies
                                if e.id == "SnakeDagger" and e.hp > 0)
            if alive_daggers >= 4:
                self.current_move = Move("Slash", IntentType.ATTACK, damage=15)
            else:
                self.current_move = Move("Summon", IntentType.BUFF)
        elif name == "Big Slash":
            self.current_move = Move("Big Slash", IntentType.ATTACK, damage=30)
        else:
            self.current_move = Move("Slash", IntentType.ATTACK, damage=15)
        return self.current_move

    def execute_move(self, state):
        m = self.current_move
        self.move_history.append(m.name)
        if m.name == "Summon":
            self._spawn_dagger(state)
        else:
            _enemy_attack(state, self, m)


class _SnakeDagger(Enemy):
    def __init__(self, hp_rng):
        hp = hp_rng.next_int(4) + 20  # 20-23
        super().__init__("SnakeDagger", "Snake Dagger", hp, hp)

    def select_move(self, state):
        self.current_move = Move("Stab", IntentType.ATTACK, damage=9)
        return self.current_move

    def execute_move(self, state):
        _enemy_attack(state, self, self.current_move)


class SpireShield(Enemy):
    def __init__(self, hp_rng):
        hp = hp_rng.next_int(10) + 140  # 140-149
        super().__init__("SpireShield", "Spire Shield", hp, hp)
        self.move_history = []

    def select_move(self, state):
        pattern = ["Bash", "Fortify", "Smash"]
        idx = len(self.move_history) % len(pattern)
        name = pattern[idx]
        if name == "Bash":
            self.current_move = Move("Bash", IntentType.ATTACK, damage=14)
        elif name == "Fortify":
            self.current_move = Move("Fortify", IntentType.BLOCK)
        else:
            self.current_move = Move("Smash", IntentType.ATTACK, damage=34)
        return self.current_move

    def execute_move(self, state):
        m = self.current_move
        self.move_history.append(m.name)
        if m.name == "Fortify":
            self.add_block(30)
        elif m.name == "Bash":
            _enemy_attack(state, self, m)
            from .cards import _apply_power
            _apply_power(state, state.player, PowerId.VULNERABLE, 2)
        else:
            _enemy_attack(state, self, m)


class SpireSpear(Enemy):
    def __init__(self, hp_rng):
        hp = hp_rng.next_int(10) + 160  # 160-169
        super().__init__("SpireSpear", "Spire Spear", hp, hp)
        self.move_history = []

    def select_move(self, state):
        pattern = ["Burn Strike", "Piercer", "Burn Strike", "Skewer"]
        idx = len(self.move_history) % len(pattern)
        name = pattern[idx]
        if name == "Burn Strike":
            self.current_move = Move("Burn Strike", IntentType.ATTACK_DEBUFF, damage=10, hits=2)
        elif name == "Piercer":
            self.current_move = Move("Piercer", IntentType.ATTACK, damage=12, hits=3)
        else:
            self.current_move = Move("Skewer", IntentType.ATTACK, damage=30)
        return self.current_move

    def execute_move(self, state):
        m = self.current_move
        self.move_history.append(m.name)
        if m.name == "Burn Strike":
            _enemy_attack(state, self, m)
            from .cards import Burn
            state.combat.discard_pile.append(Burn())  # was draw-pile top (M3)
            state.combat.discard_pile.append(Burn())
        else:
            _enemy_attack(state, self, m)


# ── Act 3 Bosses ──────────────────────────────────────────────────────────────

class DonuAndDeca(Enemy):
    """Donu fights alongside Deca."""
    def __init__(self, hp_rng, is_deca: bool = False):
        if is_deca:
            hp = hp_rng.next_int(10) + 250  # 250-259
            super().__init__("Deca", "Deca", hp, hp)
        else:
            hp = hp_rng.next_int(10) + 250
            super().__init__("Donu", "Donu", hp, hp)
        self.is_deca = is_deca
        self.move_history = []

    def select_move(self, state):
        if self.is_deca:
            pattern = ["Square of Protection", "Beam", "Beam", "Square of Protection"]
            idx = len(self.move_history) % len(pattern)
            name = pattern[idx]
            if name == "Square of Protection":
                self.current_move = Move("Square of Protection", IntentType.BUFF)
            else:
                # Both Donu and Deca Beam 10×2 in the real fight (was 10×3 Deca,
                # 10×1 Donu). Deca's Beam also adds 2 Dazed to the discard (M8).
                self.current_move = Move("Beam", IntentType.ATTACK, damage=10, hits=2)
        else:
            pattern = ["Circle of Power", "Beam", "Beam"]
            idx = len(self.move_history) % len(pattern)
            name = pattern[idx]
            if name == "Circle of Power":
                self.current_move = Move("Circle of Power", IntentType.BUFF)
            else:
                self.current_move = Move("Beam", IntentType.ATTACK, damage=10, hits=2)
        return self.current_move

    def execute_move(self, state):
        m = self.current_move
        self.move_history.append(m.name)
        if m.name == "Square of Protection":
            for e in state.combat.enemies:
                if e.hp > 0:
                    e.add_block(16)
        elif m.name == "Circle of Power":
            for e in state.combat.enemies:
                if e.hp > 0:
                    e.powers[PowerId.STRENGTH] = e.powers.get(PowerId.STRENGTH, 0) + 3
        else:
            _enemy_attack(state, self, m)
            if self.is_deca:
                from .cards import Dazed
                state.combat.discard_pile.append(Dazed())
                state.combat.discard_pile.append(Dazed())


class AwakenedOne(Enemy):
    def __init__(self, hp_rng):
        hp = hp_rng.next_int(10) + 300  # 300-309
        super().__init__("AwakenedOne", "Awakened One", hp, hp)
        self.move_history = []
        self._phase2 = False
        self._reborn = False
        # Regenerate 10: real Awakened One heals 10/turn (the engine already
        # ticks enemy REGENERATE in _tick_enemy_powers). Kept across both phases
        # per the audit's default (bug_audit L9); see impl notes for the wiki
        # ambiguity on whether phase 2 retains it.
        self.powers[PowerId.REGENERATE] = 10

    def select_move(self, state):
        if not self._phase2:
            pattern = ["Slash", "Soul Strike", "Slash", "Rebirth", "Dark Echo"]
            idx = len(self.move_history) % len(pattern)
            name = pattern[idx]
        else:
            pattern = ["Slash", "Dark Echo", "Sludge", "Slash"]
            idx = len(self.move_history) % len(pattern)
            name = pattern[idx]

        if name == "Slash":
            self.current_move = Move("Slash", IntentType.ATTACK, damage=20)
        elif name == "Soul Strike":
            self.current_move = Move("Soul Strike", IntentType.ATTACK, damage=6, hits=4)
        elif name == "Rebirth":
            self.current_move = Move("Rebirth", IntentType.BUFF)
        elif name == "Dark Echo":
            self.current_move = Move("Dark Echo", IntentType.DEBUFF)
        else:
            self.current_move = Move("Sludge", IntentType.ATTACK_DEBUFF, damage=18)
        return self.current_move

    def execute_move(self, state):
        m = self.current_move
        self.move_history.append(m.name)
        if m.name in ("Slash", "Soul Strike"):
            _enemy_attack(state, self, m)
        elif m.name == "Rebirth":
            # 1 round of Intangible. Granted during the enemy phase, so mark it
            # "fresh" to skip this round's end-of-round tick (it then covers the
            # player's next turn, after which it ticks away).
            self.powers[PowerId.INTANGIBLE] = 1
            self._intangible_fresh = True
        elif m.name == "Dark Echo":
            from .cards import _apply_power
            _apply_power(state, state.player, PowerId.VULNERABLE, 2)
        elif m.name == "Sludge":
            _enemy_attack(state, self, m)
            from .cards import Slimed
            # Real Sludge shuffles a Slimed INTO the draw pile at a random
            # position (was guaranteed next draw via insert(0); M3).
            draw = state.combat.draw_pile
            pos = state.rng.misc_rng.next_int(len(draw) + 1)
            draw.insert(pos, Slimed())

    def on_death(self, state):
        if not self._reborn:
            self._reborn = True
            self.alive = True
            self.hp = self.max_hp // 2
            self._phase2 = True
            self.powers[PowerId.STRENGTH] = self.powers.get(PowerId.STRENGTH, 0) + 2
            self.powers[PowerId.ARTIFACT] = 1


class TimeEater(Enemy):
    def __init__(self, hp_rng):
        hp = hp_rng.next_int(10) + 456  # 456-465
        super().__init__("TimeEater", "Time Eater", hp, hp)
        self.move_history = []
        self.powers[PowerId.TIME_WARP] = 12

    def select_move(self, state):
        pattern = ["Ripple", "Reverberate", "Head Slam", "Reverberate"]
        idx = len(self.move_history) % len(pattern)
        name = pattern[idx]
        if name == "Ripple":
            self.current_move = Move("Ripple", IntentType.BUFF)
        elif name == "Reverberate":
            # Real Reverberate is 7×3 (was 18×1). The half-HP Haste (heal to 50%,
            # shed debuffs) stays unimplemented (documented-design; L10).
            self.current_move = Move("Reverberate", IntentType.ATTACK, damage=7, hits=3)
        else:
            self.current_move = Move("Head Slam", IntentType.ATTACK_DEBUFF, damage=26)
        return self.current_move

    def execute_move(self, state):
        m = self.current_move
        self.move_history.append(m.name)
        if m.name == "Ripple":
            self.add_block(20)
            self.powers[PowerId.STRENGTH] = self.powers.get(PowerId.STRENGTH, 0) + 2
        elif m.name == "Head Slam":
            _enemy_attack(state, self, m)
            from .cards import _apply_power
            _apply_power(state, state.player, PowerId.VULNERABLE, 2)
        else:
            _enemy_attack(state, self, m)

    # Time Warp (every 12th card play ends the player's turn + the boss gains
    # 2 Strength) is enforced by the engine: play_card checks TIME_WARP and
    # sets combat.time_warp_lock. (The old check_time_warp here was dead code.)


# ── Register additions ────────────────────────────────────────────────────────

def register_act2_act3(registry: dict) -> None:
    additions = {
        "Chosen": Chosen,
        "ShellParasite": ShellParasite,
        "Byrd": Byrd,
        "TorchHead": TorchHead,
        "Transient": Transient,
        "BookOfStabbing": BookOfStabbing,
        "WrithingMass": WrithingMass,
        "GremlinLeader": GremlinLeader,
        "RedSlaver": lambda r: Slavers(r, is_red=True),
        "BlueSlaver": lambda r: Slavers(r, is_red=False),
        "Taskmaster": Taskmaster,
        "TheCollector": TheCollector,
        "BronzeAutomaton": BronzeAutomaton,
        "TheChamp": TheChamp,
        "Darkling": Darkling,
        "GiantHead": GiantHead,
        "Maw": Maw,
        "Nemesis": Nemesis,
        "Reptomancer": Reptomancer,
        "SpireShield": SpireShield,
        "SpireSpear": SpireSpear,
        "Donu": lambda r: DonuAndDeca(r, is_deca=False),
        "Deca": lambda r: DonuAndDeca(r, is_deca=True),
        "AwakenedOne": AwakenedOne,
        "TimeEater": TimeEater,
    }
    registry.update(additions)
