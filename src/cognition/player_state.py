"""PlayerState dataclass representing an individual player's full internal cognition."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.belief.belief_model import BeliefVector, ScoreBelief
from src.cognition.memory import FiniteMemoryManager
from src.engine.types import Alignment, PlayerId, RoleId
from src.player.personality import PersonalityVector, sample_personality
from src.player.skill import SkillProfile, sample_skill_profile


@dataclass(slots=True)
class ClaimRecord:
    player_id: PlayerId
    claimed_role: RoleId
    day: int
    is_public: bool = True
    confidence: float = 1.0


@dataclass(slots=True)
class BluffPlan:
    claimed_role: RoleId
    claim_started_day: int
    public_commitments: list[str] = field(default_factory=list)
    fake_night_history: list[dict[str, Any]] = field(default_factory=list)
    desired_world: str | None = None


@dataclass(slots=True)
class PlayerState:
    player_id: PlayerId
    personality: PersonalityVector
    skill: SkillProfile
    memory: FiniteMemoryManager

    # Subjective Perceived Identity
    perceived_role: RoleId
    perceived_alignment: Alignment

    # Beliefs over each player j: B_ij
    score_beliefs: dict[PlayerId, ScoreBelief] = field(default_factory=dict)
    beliefs: dict[PlayerId, BeliefVector] = field(default_factory=dict)

    # Social graph node states
    trust: dict[PlayerId, float] = field(default_factory=dict)        # [-1.0, 1.0]
    suspicion: dict[PlayerId, float] = field(default_factory=dict)    # [0.0, 1.0]

    # Claims tracking
    public_claims: dict[PlayerId, ClaimRecord] = field(default_factory=dict)
    private_claims: dict[PlayerId, ClaimRecord] = field(default_factory=dict)

    # Evil bluff / good fake claim plan
    bluff_plan: BluffPlan | None = None

    @classmethod
    def create(
        cls,
        player_id: PlayerId,
        all_players: list[PlayerId],
        perceived_role: RoleId,
        perceived_alignment: Alignment,
        personality: PersonalityVector | None = None,
        skill: SkillProfile | None = None,
    ) -> PlayerState:
        p = personality or sample_personality()
        s = skill or sample_skill_profile()
        mem = FiniteMemoryManager(skill_factor=s.memory_retention)

        score_beliefs: dict[PlayerId, ScoreBelief] = {}
        beliefs: dict[PlayerId, BeliefVector] = {}
        trust: dict[PlayerId, float] = {}
        suspicion: dict[PlayerId, float] = {}

        for other in all_players:
            if other == player_id:
                # Self belief is known
                if perceived_alignment == Alignment.GOOD:
                    sb = ScoreBelief(good_score=10.0, minion_score=-10.0, demon_score=-10.0)
                else:
                    sb = ScoreBelief(good_score=-10.0, minion_score=5.0, demon_score=5.0)
            else:
                sb = ScoreBelief(good_score=0.5, minion_score=-0.2, demon_score=-0.5)

            score_beliefs[other] = sb
            beliefs[other] = sb.to_belief(temperature=s.temperature)
            trust[other] = 0.0
            suspicion[other] = 0.25

        return cls(
            player_id=player_id,
            personality=p,
            skill=s,
            memory=mem,
            perceived_role=perceived_role,
            perceived_alignment=perceived_alignment,
            score_beliefs=score_beliefs,
            beliefs=beliefs,
            trust=trust,
            suspicion=suspicion,
        )

    def refresh_beliefs(self) -> None:
        """Update probability belief vectors from scores using skill temperature."""
        for p, sb in self.score_beliefs.items():
            self.beliefs[p] = sb.to_belief(temperature=self.skill.temperature)
            # Suspicion aligns with probability of being evil (Minion + Demon)
            self.suspicion[p] = self.beliefs[p].evil
