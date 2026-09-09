"""Base interface and result model for Trouble Brewing role constraints."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from src.cognition.player_state import PlayerState
from src.engine.types import PlayerId
from src.reasoning.evidence import AtomicEvidence
from src.reasoning.world import WorldHypothesis


@dataclass(slots=True)
class RoleConstraintResult:
    compatible: bool
    score_delta: float = 0.0
    required_explanations: list[dict[str, Any]] = field(default_factory=list)
    reason_codes: list[str] = field(default_factory=list)
    consumed_evidence_ids: list[str] = field(default_factory=list)

    def merge(self, other: RoleConstraintResult) -> RoleConstraintResult:
        return RoleConstraintResult(
            compatible=self.compatible and other.compatible,
            score_delta=self.score_delta + other.score_delta,
            required_explanations=self.required_explanations + other.required_explanations,
            reason_codes=self.reason_codes + other.reason_codes,
            consumed_evidence_ids=list(set(self.consumed_evidence_ids + other.consumed_evidence_ids)),
        )


class BaseRoleConstraint(ABC):
    """Abstract evaluator for evaluating whether an atomic evidence item is consistent with a WorldHypothesis."""

    @abstractmethod
    def evaluate(
        self,
        world: WorldHypothesis,
        evidence: AtomicEvidence,
        observer_state: PlayerState,
        alive_roster: dict[PlayerId, bool],
    ) -> RoleConstraintResult:
        """Evaluate consistency of evidence with world. Returns RoleConstraintResult."""
        pass
