"""Atomic Evidence Layer with Provenance, Strict Tier Separation, and Deduplication."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, unique
from typing import Any

from src.cognition.observation import Observation
from src.engine.types import GamePhase, PlayerId, RoleId


@unique
class EvidenceTier(str, Enum):
    FACT = "FACT"                      # Ground-truth event observed directly (e.g. ST token received, execution witnessed)
    CLAIM = "CLAIM"                    # What a player claims they saw or are (private whisper or public claim)
    INTERPRETATION = "INTERPRETATION"  # Subjective inference derived from facts/claims (never written back as ground truth)


@unique
class EvidenceType(str, Enum):
    ROLE_INFO = "ROLE_INFO"
    ALIGNMENT_INFO = "ALIGNMENT_INFO"
    PAIR_INFO = "PAIR_INFO"
    NEIGHBOR_INFO = "NEIGHBOR_INFO"
    COUNT_INFO = "COUNT_INFO"
    EXECUTION_INFO = "EXECUTION_INFO"
    DEATH_INFO = "DEATH_INFO"
    CLAIM = "CLAIM"
    PRIVATE_CLAIM = "PRIVATE_CLAIM"
    PUBLIC_CLAIM = "PUBLIC_CLAIM"
    VOTE_OBSERVATION = "VOTE_OBSERVATION"
    NOMINATION_OBSERVATION = "NOMINATION_OBSERVATION"
    ABILITY_RESULT = "ABILITY_RESULT"
    REGISTRATION_POSSIBILITY = "REGISTRATION_POSSIBILITY"
    POISON_POSSIBILITY = "POISON_POSSIBILITY"
    DRUNK_POSSIBILITY = "DRUNK_POSSIBILITY"
    SOCIAL_OPINION = "SOCIAL_OPINION"


@unique
class EvidenceStrength(str, Enum):
    HARD = "HARD"       # Public execution, direct virgin trigger, ST direct info token
    STRONG = "STRONG"   # Undertaker confirmation, repeated FT readings
    MEDIUM = "MEDIUM"   # Single-night Empath, Investigator pair
    SOFT = "SOFT"       # General public behavior, early claim changes
    SOCIAL = "SOCIAL"   # Vague hunches, trust affinities


@dataclass(slots=True)
class AtomicEvidence:
    evidence_id: str
    observer: PlayerId
    source_player: PlayerId | str
    source_type: str                   # "storyteller", "self", "public_event", "whisper"
    day: int
    phase: GamePhase
    visibility: str                    # "private", "public", "whisper"
    tier: EvidenceTier
    evidence_type: EvidenceType
    strength: EvidenceStrength
    content: dict[str, Any]
    confidence: float = 1.0            # [0.0, 1.0]
    memory_strength: float = 1.0       # Decays over days if retrieved from memory

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "observer": self.observer,
            "source_player": self.source_player,
            "source_type": self.source_type,
            "day": self.day,
            "phase": self.phase.value if hasattr(self.phase, "value") else str(self.phase),
            "visibility": self.visibility,
            "tier": self.tier.value,
            "evidence_type": self.evidence_type.value,
            "strength": self.strength.value,
            "content": self.content,
            "confidence": round(self.confidence, 4),
            "memory_strength": round(self.memory_strength, 4),
        }


def extract_atomic_evidence_from_observation(
    obs: Observation,
    public_claims: dict[PlayerId, Any] | None = None,
    private_claims: dict[PlayerId, Any] | None = None,
    existing_ids: set[str] | None = None,
) -> list[AtomicEvidence]:
    """Ingest observation and claims into a list of deduplicated AtomicEvidence items."""
    evidence_list: list[AtomicEvidence] = []
    seen_ids: set[str] = set(existing_ids or [])

    # 1. Direct private info from Storyteller (Tier: FACT of having received this token)
    for idx, p_info in enumerate(obs.private_info):
        itype = p_info.get("type", "UNKNOWN")
        ev_id = f"ev_{obs.observer}_d{obs.day}_priv_{itype}_{idx}"
        if ev_id in seen_ids:
            continue
        seen_ids.add(ev_id)

        # Map type to EvidenceType
        if itype == "INFO_EMPATH":
            etype = EvidenceType.NEIGHBOR_INFO
        elif itype == "INFO_CHEF":
            etype = EvidenceType.COUNT_INFO
        elif itype in ("INFO_FORTUNE_TELLER", "INFO_INVESTIGATOR", "INFO_WASHERWOMAN", "INFO_LIBRARIAN"):
            etype = EvidenceType.PAIR_INFO
        elif itype in ("INFO_UNDERTAKER", "INFO_RAVENKEEPER"):
            etype = EvidenceType.ROLE_INFO
        else:
            etype = EvidenceType.ABILITY_RESULT

        evidence_list.append(
            AtomicEvidence(
                evidence_id=ev_id,
                observer=obs.observer,
                source_player="storyteller",
                source_type="storyteller",
                day=p_info.get("day", obs.day),
                phase=obs.phase,
                visibility="private",
                tier=EvidenceTier.FACT,
                evidence_type=etype,
                strength=EvidenceStrength.HARD,
                content={"type": itype, **p_info.get("data", {})},
                confidence=1.0,
                memory_strength=1.0,
            )
        )

    # 2. Public deaths (Tier: FACT)
    for idx, d in enumerate(obs.deaths_public):
        target = d.get("player") or d.get("player_id", "unknown")
        ev_id = f"ev_{obs.observer}_d{obs.day}_death_{target}_{idx}"
        if ev_id not in seen_ids:
            seen_ids.add(ev_id)
            evidence_list.append(
                AtomicEvidence(
                    evidence_id=ev_id,
                    observer=obs.observer,
                    source_player="town_square",
                    source_type="public_event",
                    day=obs.day,
                    phase=obs.phase,
                    visibility="public",
                    tier=EvidenceTier.FACT,
                    evidence_type=EvidenceType.DEATH_INFO,
                    strength=EvidenceStrength.HARD,
                    content={"dead_player": target, **d},
                    confidence=1.0,
                )
            )

    # 3. Public Nominations and Votes (Tier: FACT of nomination/vote having happened)
    for idx, nom in enumerate(obs.nominations_today):
        nominator = nom.get("nominator")
        nominee = nom.get("nominee")
        ev_id = f"ev_{obs.observer}_d{obs.day}_nom_{nominator}_{nominee}_{idx}"
        if ev_id not in seen_ids:
            seen_ids.add(ev_id)
            evidence_list.append(
                AtomicEvidence(
                    evidence_id=ev_id,
                    observer=obs.observer,
                    source_player=nominator,
                    source_type="public_event",
                    day=obs.day,
                    phase=obs.phase,
                    visibility="public",
                    tier=EvidenceTier.FACT,
                    evidence_type=EvidenceType.NOMINATION_OBSERVATION,
                    strength=EvidenceStrength.MEDIUM,
                    content=nom,
                    confidence=1.0,
                )
            )

    # 4. Public Claims (Tier: CLAIM)
    if public_claims:
        for p, claim_rec in public_claims.items():
            c_role = getattr(claim_rec, "claimed_role", claim_rec)
            r_val = c_role.value if hasattr(c_role, "value") else str(c_role)
            ev_id = f"ev_{obs.observer}_pubclaim_{p}_{r_val}"
            if ev_id not in seen_ids:
                seen_ids.add(ev_id)
                evidence_list.append(
                    AtomicEvidence(
                        evidence_id=ev_id,
                        observer=obs.observer,
                        source_player=p,
                        source_type="player_speech",
                        day=getattr(claim_rec, "day", obs.day),
                        phase=obs.phase,
                        visibility="public",
                        tier=EvidenceTier.CLAIM,
                        evidence_type=EvidenceType.PUBLIC_CLAIM,
                        strength=EvidenceStrength.MEDIUM,
                        content={"player": p, "claimed_role": r_val},
                        confidence=0.8,
                    )
                )

    # 5. Private Whisper Claims (Tier: CLAIM)
    if private_claims:
        for p, claim_rec in private_claims.items():
            c_role = getattr(claim_rec, "claimed_role", claim_rec)
            r_val = c_role.value if hasattr(c_role, "value") else str(c_role)
            ev_id = f"ev_{obs.observer}_privclaim_{p}_{r_val}"
            if ev_id not in seen_ids:
                seen_ids.add(ev_id)
                evidence_list.append(
                    AtomicEvidence(
                        evidence_id=ev_id,
                        observer=obs.observer,
                        source_player=p,
                        source_type="whisper",
                        day=getattr(claim_rec, "day", obs.day),
                        phase=obs.phase,
                        visibility="whisper",
                        tier=EvidenceTier.CLAIM,
                        evidence_type=EvidenceType.PRIVATE_CLAIM,
                        strength=EvidenceStrength.SOFT,
                        content={"player": p, "claimed_role": r_val},
                        confidence=0.6,
                    )
                )

    return evidence_list
