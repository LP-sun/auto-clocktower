"""Tension and dramatic stakes modeling for the Storyteller."""
from __future__ import annotations

from typing import Mapping

from src.engine.state import GameState
from src.engine.types import Alignment, PlayerId, RoleId


def calculate_tension(
    state: GameState,
    suspicions: Mapping[PlayerId, float] | None = None,
) -> float:
    """Calculate dramatic tension on [0.0, 1.0] from alive counts and demon vulnerability."""
    alive = state.alive_players
    if len(alive) <= 2:
        return 1.0  # Final two is maximum tension!

    # Alive count factor: fewer living players = higher tension
    # For 12 players: 12 alive -> 0.1, 3 alive -> 0.9
    count_factor = max(0.0, min(1.0, 1.0 - (len(alive) - 2) / 10.0))

    # Demon pressure factor
    demon = next((p for p in alive if state.true_roles[p] == RoleId.IMP), None)
    demon_pressure = 0.5
    if demon and suspicions:
        # Check demon rank in suspicion
        sorted_suspects = sorted(alive, key=lambda p: suspicions.get(p, 0.0), reverse=True)
        if demon in sorted_suspects:
            rank = sorted_suspects.index(demon)
            # Rank 0 (top suspect) -> 1.0, lower rank -> lower pressure
            demon_pressure = max(0.1, 1.0 - (rank / len(sorted_suspects)))

    tension = 0.5 * count_factor + 0.5 * demon_pressure
    return max(0.0, min(1.0, tension))
