"""Minion role constraint evaluators for Trouble Brewing."""
from __future__ import annotations

from typing import Any

from src.cognition.player_state import PlayerState
from src.engine.types import PlayerId, RoleId
from src.reasoning.evidence import AtomicEvidence
from src.reasoning.role_constraints.base import BaseRoleConstraint, RoleConstraintResult
from src.reasoning.world import WorldHypothesis


class PoisonerConstraint(BaseRoleConstraint):
    def evaluate(
        self,
        world: WorldHypothesis,
        evidence: AtomicEvidence,
        observer_state: PlayerState,
        alive_roster: dict[PlayerId, bool],
    ) -> RoleConstraintResult:
        # Resource check: if world assumes Poisoner exists, must be alive to poison
        return RoleConstraintResult(compatible=True)


class ScarletWomanConstraint(BaseRoleConstraint):
    def evaluate(
        self,
        world: WorldHypothesis,
        evidence: AtomicEvidence,
        observer_state: PlayerState,
        alive_roster: dict[PlayerId, bool],
    ) -> RoleConstraintResult:
        return RoleConstraintResult(compatible=True)


class BaronConstraint(BaseRoleConstraint):
    def evaluate(
        self,
        world: WorldHypothesis,
        evidence: AtomicEvidence,
        observer_state: PlayerState,
        alive_roster: dict[PlayerId, bool],
    ) -> RoleConstraintResult:
        return RoleConstraintResult(compatible=True)


class SpyConstraint(BaseRoleConstraint):
    def evaluate(
        self,
        world: WorldHypothesis,
        evidence: AtomicEvidence,
        observer_state: PlayerState,
        alive_roster: dict[PlayerId, bool],
    ) -> RoleConstraintResult:
        return RoleConstraintResult(compatible=True)
