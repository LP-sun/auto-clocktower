"""Dual-Model Evil Reasoning Engine for Trouble Brewing.

Explicitly separates:
1. InternalWorldModel: Genuine Good-role inference, high-value target identification (Monk/Slayer/FT vs RK/Soldier), and kill/starpass planning.
2. FakeWorldModel: Construction of sustainable public bluff worlds, role claims for evil team, and framing targets for the town.

Maintains a strict cognitive firewall: FakeWorldModel objectives never pollute InternalWorldModel beliefs.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.cognition.player_state import PlayerState
from src.engine.types import Alignment, CharacterType, PlayerId, RoleId
from src.reasoning.evidence import AtomicEvidence
from src.reasoning.world import RoleSlot, SlotState, WorldHypothesis


@dataclass(slots=True)
class GoodRoleInference:
    player_id: PlayerId
    role_probabilities: dict[RoleId, float]
    kill_priority_score: float
    is_protected_risk: bool
    is_ravenkeeper_risk: bool
    is_soldier_risk: bool
    is_mayor_risk: bool


@dataclass(slots=True)
class FakeWorldBluffPlan:
    evil_player: PlayerId
    bluff_role: RoleId
    bluff_claims: list[dict[str, Any]]
    framed_good_players: list[PlayerId]
    plausibility_score: float


class InternalWorldModel:
    """Infers true roles of Good players for night kill and starpass decisions.

    Completely isolated from public fake-world bluff fabrication.
    """

    def __init__(self, evil_player_id: PlayerId, evil_team: list[PlayerId]) -> None:
        self.evil_player_id = evil_player_id
        self.evil_team = set(evil_team)

    def infer_good_roles(
        self,
        good_players: list[PlayerId],
        public_claims: dict[PlayerId, Any],
        evidence_list: list[AtomicEvidence],
    ) -> dict[PlayerId, GoodRoleInference]:
        """Infer real Good roles and rank night kill priorities."""
        inferences: dict[PlayerId, GoodRoleInference] = {}

        for p in good_players:
            claim_rec = public_claims.get(p)
            claimed_role = getattr(claim_rec, "claimed_role", None) if claim_rec else None

            # Base role probabilities
            probs: dict[RoleId, float] = {}
            if claimed_role and isinstance(claimed_role, RoleId):
                # High prior that good player tells the truth about their role
                probs[claimed_role] = 0.75
                remaining = 0.25 / 10.0
                for r in RoleId:
                    if r != claimed_role and r not in (RoleId.IMP, RoleId.BARON, RoleId.POISONER, RoleId.SCARLET_WOMAN, RoleId.SPY):
                        probs[r] = remaining
            else:
                # Uniform over town/outsider
                valid_roles = [r for r in RoleId if r not in (RoleId.IMP, RoleId.BARON, RoleId.POISONER, RoleId.SCARLET_WOMAN, RoleId.SPY)]
                u = 1.0 / len(valid_roles)
                probs = {r: u for r in valid_roles}

            # Threat calculation
            # High priority targets: Monk (protects), Slayer (can kill demon), Fortune Teller (investigates demon), Empath (adjacent evil ping)
            # Dangerous targets to kill: Ravenkeeper (punishes night kill!), Soldier (immune), Mayor (bounces)
            monk_p = probs.get(RoleId.MONK, 0.0)
            slayer_p = probs.get(RoleId.SLAYER, 0.0)
            ft_p = probs.get(RoleId.FORTUNE_TELLER, 0.0)
            empath_p = probs.get(RoleId.EMPATH, 0.0)
            rk_p = probs.get(RoleId.RAVENKEEPER, 0.0)
            soldier_p = probs.get(RoleId.SOLDIER, 0.0)
            mayor_p = probs.get(RoleId.MAYOR, 0.0)

            # Positive threat weights
            pos_threat = (monk_p * 3.5) + (slayer_p * 3.0) + (ft_p * 2.5) + (empath_p * 2.0)
            # Penalty for risky kills
            neg_risk = (rk_p * 5.0) + (soldier_p * 2.0) + (mayor_p * 1.5)

            kill_score = pos_threat - neg_risk

            inferences[p] = GoodRoleInference(
                player_id=p,
                role_probabilities=probs,
                kill_priority_score=kill_score,
                is_protected_risk=monk_p > 0.3,
                is_ravenkeeper_risk=rk_p > 0.3,
                is_soldier_risk=soldier_p > 0.3,
                is_mayor_risk=mayor_p > 0.3,
            )

        return inferences

    def recommend_kill_target(
        self,
        alive_good_players: list[PlayerId],
        inferences: dict[PlayerId, GoodRoleInference],
    ) -> PlayerId | None:
        """Select best night kill target among living good players."""
        if not alive_good_players:
            return None
        ranked = sorted(
            alive_good_players,
            key=lambda p: inferences.get(p, GoodRoleInference(p, {}, 0.0, False, False, False, False)).kill_priority_score,
            reverse=True,
        )
        return ranked[0]


class FakeWorldModel:
    """Constructs sustainable public bluff worlds for deception.

    Operates strictly outward-facing; does not modify InternalWorldModel knowledge.
    """

    def __init__(
        self,
        evil_player_id: PlayerId,
        evil_team: list[PlayerId],
        demon_bluffs: list[RoleId] | None = None,
    ) -> None:
        self.evil_player_id = evil_player_id
        self.evil_team = set(evil_team)
        self.demon_bluffs = list(demon_bluffs or [RoleId.CHEF, RoleId.INVESTIGATOR, RoleId.SOLDIER])
        self.active_bluff_plan: FakeWorldBluffPlan | None = None

    def design_bluff_world(
        self,
        observer_state: PlayerState,
        all_players: list[PlayerId],
        good_players: list[PlayerId],
    ) -> WorldHypothesis:
        """Generate a complete plausible fake world that evil can publicly assert."""
        # Pick a bluff role for self
        bluff = self.demon_bluffs[0] if self.demon_bluffs else RoleId.SOLDIER

        # Pick a plausible Good scapegoat to frame as Demon
        # Select living good player with highest suspicion in town
        scapegoat = good_players[0] if good_players else (all_players[0] if all_players else self.evil_player_id)
        for g in good_players:
            if observer_state.suspicion.get(g, 0.0) > observer_state.suspicion.get(scapegoat, 0.0):
                scapegoat = g

        slots: dict[PlayerId, RoleSlot] = {}
        alignments: dict[PlayerId, Alignment] = {}

        # Frame scapegoat as Demon
        slots[scapegoat] = RoleSlot.make_known(RoleId.IMP)
        alignments[scapegoat] = Alignment.EVIL

        # Frame evil teammates as good or innocent
        for ep in self.evil_team:
            if ep == self.evil_player_id:
                slots[ep] = RoleSlot.make_known(bluff)
                alignments[ep] = Alignment.GOOD
            else:
                slots[ep] = RoleSlot.make_unknown()
                alignments[ep] = Alignment.GOOD

        # Assign slots for others based on their claims
        for p in all_players:
            if p not in slots:
                c_rec = observer_state.public_claims.get(p)
                if c_rec and hasattr(c_rec, "claimed_role") and c_rec.claimed_role:
                    slots[p] = RoleSlot.make_known(c_rec.claimed_role)
                else:
                    slots[p] = RoleSlot.make_unknown()
                alignments[p] = Alignment.GOOD

        current_day = getattr(observer_state, "day", 1)
        fake_world = WorldHypothesis(
            world_id=999999,
            demon_player=scapegoat,
            minion_players=[],
            good_players=[p for p in all_players if p != scapegoat],
            slots=slots,
            alignments=alignments,
            created_day=current_day,
        )

        self.active_bluff_plan = FakeWorldBluffPlan(
            evil_player=self.evil_player_id,
            bluff_role=bluff,
            bluff_claims=[],
            framed_good_players=[scapegoat],
            plausibility_score=0.85,
        )

        return fake_world
