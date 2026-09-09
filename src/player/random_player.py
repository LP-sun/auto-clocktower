"""Minimal random legal-action player for Milestone 2 baseline and stress testing."""
from __future__ import annotations

import random
from typing import Any

from src.cognition.observation import Observation
from src.engine.types import ActionType, PlayerId, RoleId


class RandomPlayer:
    """A compliant player policy that samples uniformly from strictly legal actions."""

    def __init__(self, player_id: PlayerId, seed: int | None = None) -> None:
        self.player_id = player_id
        self.rng = random.Random(seed)

    def choose_night_target(self, obs: Observation, action_type: str) -> Any:
        """Pick legal targets for night actions based on role constraints."""
        all_players = list(obs.roster_alive.keys())
        alive_players = [p for p, alive in obs.roster_alive.items() if alive]
        others_alive = [p for p in alive_players if p != self.player_id]

        if action_type == "poisoner":
            # Poisoner can pick any alive player
            return self.rng.choice(alive_players) if alive_players else None

        if action_type == "monk":
            # Monk picks other alive player
            return self.rng.choice(others_alive) if others_alive else None

        if action_type == "imp":
            # Imp picks any alive player (picking self triggers star pass)
            return self.rng.choice(alive_players) if alive_players else None

        if action_type == "fortune_teller":
            # Fortune Teller picks 2 players
            return tuple(self.rng.sample(all_players, 2)) if len(all_players) >= 2 else None

        if action_type == "butler":
            # Butler picks other player (alive or dead)
            pool = [p for p in all_players if p != self.player_id]
            return self.rng.choice(pool) if pool else None

        if action_type == "ravenkeeper":
            # Ravenkeeper picks any player
            return self.rng.choice(all_players) if all_players else None

        return None

    def decide_slayer_shot(self, obs: Observation) -> PlayerId | None:
        """Decide whether to use Slayer ability and pick target."""
        if not obs.alive or obs.self_role != RoleId.SLAYER:
            return None
        # Probabilistic decision to shoot
        if self.rng.random() < 0.2:
            others_alive = [p for p, alive in obs.roster_alive.items() if alive and p != self.player_id]
            if others_alive:
                return self.rng.choice(others_alive)
        return None

    def decide_nomination(self, obs: Observation) -> PlayerId | None:
        """Decide whether to nominate and pick legal target."""
        if not obs.alive or self.player_id in obs.nominated_by_today:
            return None

        # Legal nominees: players not yet nominated today
        legal_nominees = [
            p for p in obs.roster_alive.keys()
            if p not in obs.nominated_today
        ]
        if not legal_nominees:
            return None

        # Stochastic choice: 50% chance to nominate if candidates exist
        if self.rng.random() < 0.5:
            return self.rng.choice(legal_nominees)
        return None

    def decide_vote(self, obs: Observation) -> bool:
        """Decide whether to vote Yes on the active nomination."""
        if not obs.current_nomination:
            return False

        # Can vote check
        if not obs.alive and not obs.ghost_vote_available:
            return False

        # Butler constraint check
        if obs.alive and obs.self_role == RoleId.BUTLER and obs.butler_master:
            master_vote = obs.current_nomination.get("votes", {}).get(obs.butler_master, False)
            if not master_vote:
                return False

        # 50% chance to vote Yes
        return self.rng.random() < 0.5
