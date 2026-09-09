"""Storyteller decision types, counterfactual logging, and sensitivity metrics."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum, unique
from typing import Any

from src.engine.types import PlayerId, STDecisionType


@unique
class STReasonCode(str, Enum):
    PRESERVE_SOLVABILITY = "PRESERVE_SOLVABILITY"
    MAINTAIN_TENSION = "MAINTAIN_TENSION"
    SUPPORT_DEMON_BLUFF = "SUPPORT_DEMON_BLUFF"
    AVOID_HARD_CONFIRMATION = "AVOID_HARD_CONFIRMATION"
    REWARD_PLAYER_AGENCY = "REWARD_PLAYER_AGENCY"
    AVOID_ARBITRARY_HARM = "AVOID_ARBITRARY_HARM"
    DRAMATIC_BALANCE = "DRAMATIC_BALANCE"
    ENFORCE_ROLE_RELEVANCE = "ENFORCE_ROLE_RELEVANCE"
    TRIGGER_RAVENKEEPER = "TRIGGER_RAVENKEEPER"
    CONFIRM_SOLDIER = "CONFIRM_SOLDIER"
    TARGET_SPENT_ROLE = "TARGET_SPENT_ROLE"
    SIMULATE_RED_HERRING = "SIMULATE_RED_HERRING"
    PLAUSIBLE_MISINFO = "PLAUSIBLE_MISINFO"


@unique
class STDecisionPhase(str, Enum):
    SETUP = "SETUP"
    NIGHT = "NIGHT"
    DAY = "DAY"
    REGISTRATION = "REGISTRATION"
    DEATH_RESOLUTION = "DEATH_RESOLUTION"


@dataclass(slots=True)
class STDecisionRecord:
    decision_id: int
    seed: int
    day: int
    night: int
    decision_type: STDecisionType
    actor: PlayerId | None
    state_features: dict[str, Any]
    legal_actions: list[Any]
    chosen_action: Any
    utility_components: dict[str, float]
    counterfactual_scores: dict[str, dict[str, float]] = field(default_factory=dict)
    delta_u: float = 0.0  # U_best - U_second (Choice sensitivity)
    reason_codes: list[str] = field(default_factory=list)
    outcome_delta: dict[str, Any] | None = None
    phase: STDecisionPhase = STDecisionPhase.NIGHT

    def to_dict(self) -> dict[str, Any]:
        res = asdict(self)
        res["decision_type"] = self.decision_type.value
        res["phase"] = self.phase.value
        return res
