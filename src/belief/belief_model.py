"""Probabilistic belief state modeling: B_ij = (P(Good), P(Minion), P(Demon))."""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from src.engine.types import PlayerId


@dataclass(slots=True)
class BeliefVector:
    good: float = 0.7
    minion: float = 0.2
    demon: float = 0.1

    def __post_init__(self) -> None:
        self.normalize()

    def normalize(self) -> None:
        total = self.good + self.minion + self.demon
        if total <= 0:
            self.good, self.minion, self.demon = 1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0
        else:
            self.good /= total
            self.minion /= total
            self.demon /= total

    @property
    def evil(self) -> float:
        return self.minion + self.demon


@dataclass(slots=True)
class ScoreBelief:
    """Score-based belief approximation before softmax transformation."""
    good_score: float = 0.0
    minion_score: float = 0.0
    demon_score: float = 0.0

    def to_belief(self, temperature: float = 1.0) -> BeliefVector:
        t = max(0.1, temperature)
        eg = math.exp(min(20.0, max(-20.0, self.good_score / t)))
        em = math.exp(min(20.0, max(-20.0, self.minion_score / t)))
        ed = math.exp(min(20.0, max(-20.0, self.demon_score / t)))
        s = eg + em + ed
        return BeliefVector(good=eg / s, minion=em / s, demon=ed / s)
