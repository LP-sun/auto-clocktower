"""Outsider role constraint evaluators for Trouble Brewing."""
from __future__ import annotations

from typing import Any

from src.cognition.player_state import PlayerState
from src.engine.types import Alignment, PlayerId, RoleId
from src.reasoning.evidence import AtomicEvidence, EvidenceType
from src.reasoning.role_constraints.base import BaseRoleConstraint, RoleConstraintResult
from src.reasoning.world import RoleSlot, SlotState, WorldHypothesis


class SaintConstraint(BaseRoleConstraint):
    def evaluate(
        self,
        world: WorldHypothesis,
        evidence: AtomicEvidence,
        observer_state: PlayerState,
        alive_roster: dict[PlayerId, bool],
    ) -> RoleConstraintResult:
        if evidence.evidence_type == EvidenceType.DEATH_INFO and evidence.content.get("reason") == "execution":
            victim = evidence.content.get("dead_player")
            v_slot = world.slots.get(victim)
            if v_slot and v_slot.matches_role(RoleId.SAINT) and victim != world.drunk_player:
                # If Saint was executed, evil should have won immediately
                # If game continued, Saint was poisoned or Drunk
                has_poisoner = any(s.matches_role(RoleId.POISONER) for s in world.slots.values())
                if has_poisoner:
                    return RoleConstraintResult(
                        compatible=True,
                        score_delta=-1.0,
                        required_explanations=[{"type": "POISON_EXPLANATION", "day": evidence.day, "target": victim}],
                        reason_codes=["SAINT_EXECUTED_REQUIRES_POISON_SURVIVAL"],
                        consumed_evidence_ids=[evidence.evidence_id],
                    )
                return RoleConstraintResult(
                    compatible=False,
                    score_delta=-4.0,
                    reason_codes=["SAINT_EXECUTED_WITHOUT_EVIL_WIN_CONTRADICTION"],
                    consumed_evidence_ids=[evidence.evidence_id],
                )
        return RoleConstraintResult(compatible=True)


class ButlerConstraint(BaseRoleConstraint):
    def evaluate(
        self,
        world: WorldHypothesis,
        evidence: AtomicEvidence,
        observer_state: PlayerState,
        alive_roster: dict[PlayerId, bool],
    ) -> RoleConstraintResult:
        # Butler master constraints on voting
        return RoleConstraintResult(compatible=True)


class RecluseConstraint(BaseRoleConstraint):
    def evaluate(
        self,
        world: WorldHypothesis,
        evidence: AtomicEvidence,
        observer_state: PlayerState,
        alive_roster: dict[PlayerId, bool],
    ) -> RoleConstraintResult:
        # Handled in caller registration evaluations
        return RoleConstraintResult(compatible=True)
