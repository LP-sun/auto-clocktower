"""Demon role constraint evaluators for Trouble Brewing."""
from __future__ import annotations

from typing import Any

from src.cognition.player_state import PlayerState
from src.engine.types import PlayerId, RoleId
from src.reasoning.evidence import AtomicEvidence
from src.reasoning.role_constraints.base import BaseRoleConstraint, RoleConstraintResult
from src.reasoning.world import WorldHypothesis


class ImpConstraint(BaseRoleConstraint):
    def evaluate(
        self,
        world: WorldHypothesis,
        evidence: AtomicEvidence,
        observer_state: PlayerState,
        alive_roster: dict[PlayerId, bool],
    ) -> RoleConstraintResult:
        return RoleConstraintResult(compatible=True)
