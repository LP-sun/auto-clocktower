"""World Hypothesis Representation, Partial Role Slots, Lineage Tracking, and Conditioned Queries."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, unique
from typing import Any

from src.engine.types import Alignment, PlayerId, RoleId


@unique
class SlotState(str, Enum):
    KNOWN = "KNOWN"                  # Explicit single role assigned
    CANDIDATE_SET = "CANDIDATE_SET"  # Narrowed subset of potential roles
    UNKNOWN = "UNKNOWN"              # Completely open/unconstrained role slot


@dataclass(slots=True)
class RoleSlot:
    state: SlotState = SlotState.UNKNOWN
    role: RoleId | None = None
    candidates: frozenset[RoleId] = field(default_factory=frozenset)

    @classmethod
    def make_known(cls, role: RoleId) -> RoleSlot:
        return cls(state=SlotState.KNOWN, role=role, candidates=frozenset({role}))

    @classmethod
    def make_candidates(cls, candidates: set[RoleId] | list[RoleId] | frozenset[RoleId]) -> RoleSlot:
        c_set = frozenset(candidates)
        if len(c_set) == 1:
            r = next(iter(c_set))
            return cls(state=SlotState.KNOWN, role=r, candidates=c_set)
        return cls(state=SlotState.CANDIDATE_SET, role=None, candidates=c_set)

    @classmethod
    def make_unknown(cls) -> RoleSlot:
        return cls(state=SlotState.UNKNOWN, role=None, candidates=frozenset())

    def matches_role(self, r: RoleId) -> bool:
        if self.state == SlotState.UNKNOWN:
            return True
        if self.state == SlotState.KNOWN:
            return self.role == r
        return r in self.candidates

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state.value,
            "role": self.role.value if self.role else None,
            "candidates": [c.value for c in sorted(self.candidates, key=lambda x: x.value)],
        }


@dataclass(slots=True)
class WorldHypothesis:
    world_id: int
    demon_player: PlayerId
    minion_players: list[PlayerId]
    good_players: list[PlayerId]
    slots: dict[PlayerId, RoleSlot]
    alignments: dict[PlayerId, Alignment]

    parent_world_id: int | None = None
    created_day: int = 1
    drunk_player: PlayerId | None = None
    poison_history: list[dict[str, Any]] = field(default_factory=list)  # [{"night": int, "source": PlayerId, "target": PlayerId}]
    spy_registration_assumptions: dict[PlayerId, dict[str, Any]] = field(default_factory=dict)
    recluse_registration_assumptions: dict[PlayerId, dict[str, Any]] = field(default_factory=dict)
    claim_truth_assignment: dict[PlayerId, bool] = field(default_factory=dict)
    consumed_evidence_ids: set[str] = field(default_factory=set)

    # Score components
    score_rule: float = 0.0
    score_info: float = 0.0
    score_claim: float = 0.0
    score_social: float = 0.0
    score_vote: float = 0.0
    score_death: float = 0.0
    cost_explanation: float = 0.0
    cost_complexity: float = 0.0
    total_score: float = 0.0
    probability: float = 0.0

    def get_assigned_role(self, p: PlayerId) -> RoleId | None:
        slot = self.slots.get(p)
        return slot.role if slot and slot.state == SlotState.KNOWN else None

    def condition(
        self,
        demon: PlayerId | None = None,
        minion: PlayerId | None = None,
        role_assignments: dict[PlayerId, RoleId] | None = None,
    ) -> bool:
        """Check if this world satisfies specific conditional query constraints."""
        if demon and self.demon_player != demon:
            return False
        if minion and minion not in self.minion_players:
            return False
        if role_assignments:
            for p, r in role_assignments.items():
                slot = self.slots.get(p)
                if not slot or not slot.matches_role(r):
                    return False
        return True

    def to_dict(self) -> dict[str, Any]:
        return {
            "world_id": self.world_id,
            "parent_world_id": self.parent_world_id,
            "created_day": self.created_day,
            "demon": self.demon_player,
            "minions": self.minion_players,
            "good_players": self.good_players,
            "drunk_player": self.drunk_player,
            "slots": {p: s.to_dict() for p, s in self.slots.items()},
            "poison_history": self.poison_history,
            "spy_assumptions": self.spy_registration_assumptions,
            "recluse_assumptions": self.recluse_registration_assumptions,
            "consumed_evidence_count": len(self.consumed_evidence_ids),
            "score_rule": round(self.score_rule, 4),
            "score_info": round(self.score_info, 4),
            "score_claim": round(self.score_claim, 4),
            "score_death": round(self.score_death, 4),
            "cost_explanation": round(self.cost_explanation, 4),
            "cost_complexity": round(self.cost_complexity, 4),
            "total_score": round(self.total_score, 4),
            "probability": round(self.probability, 4),
        }


@dataclass(slots=True)
class WorldLineageRecord:
    world_id: int
    parent_world_id: int | None
    created_day: int
    removed_day: int | None = None
    removal_reason: str | None = None  # RULE_CONTRADICTION, INFO_CONTRADICTION, CLAIM_CONTRADICTION, TOO_COMPLEX, LOW_SCORE, MEMORY_LOSS, SEARCH_CAPACITY

    def to_dict(self) -> dict[str, Any]:
        return {
            "world_id": self.world_id,
            "parent_world_id": self.parent_world_id,
            "created_day": self.created_day,
            "removed_day": self.removed_day,
            "removal_reason": self.removal_reason,
        }


@dataclass(slots=True)
class WorldReasoningTrace:
    player_id: PlayerId
    day: int
    phase: str
    input_evidence_count: int
    candidate_world_count: int
    pruned_world_count: int
    top_worlds: list[dict[str, Any]]
    demon_marginals: dict[PlayerId, float]
    minion_marginals: dict[PlayerId, float]
    effective_world_count: float
    top1_world_mass: float
    world_entropy: float
    collapse_warning: bool
    underconstrained_warning: bool
    chosen_action: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "player_id": self.player_id,
            "day": self.day,
            "phase": self.phase,
            "input_evidence_count": self.input_evidence_count,
            "candidate_world_count": self.candidate_world_count,
            "pruned_world_count": self.pruned_world_count,
            "top_worlds": self.top_worlds,
            "demon_marginals": {p: round(prob, 4) for p, prob in self.demon_marginals.items()},
            "minion_marginals": {p: round(prob, 4) for p, prob in self.minion_marginals.items()},
            "effective_world_count": round(self.effective_world_count, 4),
            "top1_world_mass": round(self.top1_world_mass, 4),
            "world_entropy": round(self.world_entropy, 4),
            "collapse_warning": self.collapse_warning,
            "underconstrained_warning": self.underconstrained_warning,
            "chosen_action": self.chosen_action,
        }
