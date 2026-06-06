"""Seeded RNG matching Slay the Spire's Java Random implementation."""
from __future__ import annotations


class StsRandom:
    """Linear congruential RNG matching Java's java.util.Random used by StS."""

    MULTIPLIER = 0x5DEECE66D
    ADDEND = 0xB
    MASK = (1 << 48) - 1

    def __init__(self, seed: int) -> None:
        self.seed = (seed ^ self.MULTIPLIER) & self.MASK

    def _next(self, bits: int) -> int:
        self.seed = (self.seed * self.MULTIPLIER + self.ADDEND) & self.MASK
        return self.seed >> (48 - bits)

    def next_int(self, bound: int | None = None) -> int:
        if bound is None:
            return self._next(32)
        if bound <= 0:
            raise ValueError("bound must be positive")
        if bound & (bound - 1) == 0:
            return (bound * self._next(31)) >> 31
        while True:
            bits = self._next(31)
            val = bits % bound
            if bits - val + (bound - 1) >= 0:
                return val

    def next_float(self) -> float:
        return self._next(24) / (1 << 24)

    def next_bool(self) -> bool:
        return self._next(1) == 1

    def shuffle(self, lst: list) -> None:
        for i in range(len(lst) - 1, 0, -1):
            j = self.next_int(i + 1)
            lst[i], lst[j] = lst[j], lst[i]


class SeededRNG:
    """Separate RNG streams per use, all derived from a single seed."""

    def __init__(self, seed: int) -> None:
        base = StsRandom(seed)
        self.map_rng = StsRandom(base.next_int())
        self.shuffle_rng = StsRandom(base.next_int())
        self.card_rng = StsRandom(base.next_int())
        self.loot_rng = StsRandom(base.next_int())
        self.event_rng = StsRandom(base.next_int())
        self.potion_rng = StsRandom(base.next_int())
        self.misc_rng = StsRandom(base.next_int())
        self.ai_rng = StsRandom(base.next_int())
        self.hp_rng = StsRandom(base.next_int())
