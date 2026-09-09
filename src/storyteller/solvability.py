"""Solvability proxy and world hypothesis entropy models for Storyteller balancing."""
from __future__ import annotations

import math
from typing import Mapping

from src.engine.state import GameState
from src.engine.types import PlayerId


def calculate_solvability_proxy(
    state: GameState,
    suspicions: Mapping[PlayerId, float] | None = None,
) -> float:
    """Calculate the solvability proxy (Shannon entropy over demon candidate suspicion distribution)."""
    alive = state.alive_players
    if not alive:
        return 0.0

    if suspicions:
        weights = [max(0.01, suspicions.get(p, 0.2)) for p in alive]
    else:
        weights = [1.0] * len(alive)

    total_w = sum(weights)
    probs = [w / total_w for w in weights]

    entropy = -sum(p * math.log2(p) for p in probs if p > 0)
    return entropy


def is_in_healthy_solvability_range(entropy: float) -> bool:
    """Return True if solvability proxy falls in the healthy gameplay corridor (1.0 < H < 3.5)."""
    return 1.0 <= entropy <= 3.5
