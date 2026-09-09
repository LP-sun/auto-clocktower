"""Townsfolk role constraint evaluators for Trouble Brewing."""
from __future__ import annotations

from typing import Any

from src.cognition.player_state import PlayerState
from src.engine.types import Alignment, CharacterType, PlayerId, RoleId
from src.reasoning.evidence import AtomicEvidence, EvidenceType
from src.reasoning.role_constraints.base import BaseRoleConstraint, RoleConstraintResult
from src.reasoning.world import RoleSlot, SlotState, WorldHypothesis
from src.roles.trouble_brewing import ROLES


class ChefConstraint(BaseRoleConstraint):
    def evaluate(
        self,
        world: WorldHypothesis,
        evidence: AtomicEvidence,
        observer_state: PlayerState,
        alive_roster: dict[PlayerId, bool],
    ) -> RoleConstraintResult:
        actor = evidence.source_player if evidence.source_player != "storyteller" else (observer_state.player_id if observer_state else evidence.observer)
        actor_is_chef = (world.slots.get(actor) and world.slots[actor].matches_role(RoleId.CHEF)) or (observer_state and observer_state.player_id == actor and getattr(observer_state, "role", None) == RoleId.CHEF)
        ev_type = evidence.content.get("type")
        if ev_type not in ("INFO_CHEF", "CHEF") and not (actor_is_chef and evidence.evidence_type == EvidenceType.COUNT_INFO):
            return RoleConstraintResult(compatible=True)

        claimed_num = evidence.content.get("number")
        if claimed_num is None:
            claimed_num = evidence.content.get("pairs")
        if claimed_num is None:
            claimed_num = evidence.content.get("count", 0)

        # Count actual evil pairs in this world
        # Seating circle order from world slots or alive roster
        circle = list(world.slots.keys()) if world.slots else list(alive_roster.keys())
        n = len(circle)
        evil_players = set(world.minion_players + [world.demon_player])

        # Spy can register good, Recluse can register evil
        actual_evil_pairs = 0
        for i in range(n):
            p1 = circle[i]
            p2 = circle[(i + 1) % n]
            p1_evil = (p1 in evil_players)
            p2_evil = (p2 in evil_players)

            # Recluse registration assumption
            if world.slots.get(p1) and world.slots[p1].matches_role(RoleId.RECLUSE):
                if world.recluse_registration_assumptions.get(p1, {}).get("chef_evil", False):
                    p1_evil = True
            if world.slots.get(p2) and world.slots[p2].matches_role(RoleId.RECLUSE):
                if world.recluse_registration_assumptions.get(p2, {}).get("chef_evil", False):
                    p2_evil = True

            # Spy registration assumption
            if world.slots.get(p1) and world.slots[p1].matches_role(RoleId.SPY):
                if world.spy_registration_assumptions.get(p1, {}).get("chef_good", False):
                    p1_evil = False
            if world.slots.get(p2) and world.slots[p2].matches_role(RoleId.SPY):
                if world.spy_registration_assumptions.get(p2, {}).get("chef_good", False):
                    p2_evil = False

            if p1_evil and p2_evil:
                actual_evil_pairs += 1

        if actor == world.drunk_player:
            return RoleConstraintResult(
                compatible=True,
                score_delta=0.4,
                required_explanations=[{"type": "DRUNK_EXPLANATION", "player": actor, "evidence": evidence.evidence_id}],
                reason_codes=["CHEF_EXPLAINED_BY_DRUNK"],
                consumed_evidence_ids=[evidence.evidence_id],
            )

        if actual_evil_pairs == claimed_num:
            return RoleConstraintResult(
                compatible=True,
                score_delta=1.8,
                reason_codes=["SUPPORTS_CHEF_INFO"],
                consumed_evidence_ids=[evidence.evidence_id],
            )

        # Mismatch: check if Poisoner exists and was active
        has_poisoner = any(s.matches_role(RoleId.POISONER) for s in world.slots.values())
        if has_poisoner:
            return RoleConstraintResult(
                compatible=True,
                score_delta=-0.8,
                required_explanations=[{"type": "POISON_EXPLANATION", "night": 1, "target": actor, "evidence": evidence.evidence_id}],
                reason_codes=["CHEF_CONTRADICTED_REQUIRES_POISON"],
                consumed_evidence_ids=[evidence.evidence_id],
            )

        return RoleConstraintResult(
            compatible=False,
            score_delta=-3.5,
            reason_codes=["CHEF_INFO_CONTRADICTED_UNEXPLAINED"],
            consumed_evidence_ids=[evidence.evidence_id],
        )


class EmpathConstraint(BaseRoleConstraint):
    def evaluate(
        self,
        world: WorldHypothesis,
        evidence: AtomicEvidence,
        observer_state: PlayerState,
        alive_roster: dict[PlayerId, bool],
    ) -> RoleConstraintResult:
        actor = evidence.source_player if evidence.source_player != "storyteller" else (observer_state.player_id if observer_state else evidence.observer)
        actor_is_empath = (world.slots.get(actor) and world.slots[actor].matches_role(RoleId.EMPATH)) or (observer_state and observer_state.player_id == actor and getattr(observer_state, "role", None) == RoleId.EMPATH)
        ev_type = evidence.content.get("type")
        if ev_type not in ("INFO_EMPATH", "EMPATH") and not (actor_is_empath and evidence.evidence_type in (EvidenceType.COUNT_INFO, EvidenceType.NEIGHBOR_INFO)):
            return RoleConstraintResult(compatible=True)

        claimed_num = evidence.content.get("number")
        if claimed_num is None:
            claimed_num = evidence.content.get("count", 0)

        # Living neighbors at that time
        living = [p for p, a in alive_roster.items() if a]
        if actor not in living or len(living) <= 2:
            return RoleConstraintResult(compatible=True, consumed_evidence_ids=[evidence.evidence_id])

        idx = living.index(actor)
        left = living[(idx - 1) % len(living)]
        right = living[(idx + 1) % len(living)]

        evil_players = set(world.minion_players + [world.demon_player])
        left_evil = (left in evil_players)
        right_evil = (right in evil_players)

        # Registration adjustments
        if world.slots.get(left) and world.slots[left].matches_role(RoleId.RECLUSE):
            if world.recluse_registration_assumptions.get(left, {}).get("empath_evil", False):
                left_evil = True
        if world.slots.get(right) and world.slots[right].matches_role(RoleId.RECLUSE):
            if world.recluse_registration_assumptions.get(right, {}).get("empath_evil", False):
                right_evil = True

        if world.slots.get(left) and world.slots[left].matches_role(RoleId.SPY):
            if world.spy_registration_assumptions.get(left, {}).get("empath_good", False):
                left_evil = False
        if world.slots.get(right) and world.slots[right].matches_role(RoleId.SPY):
            if world.spy_registration_assumptions.get(right, {}).get("empath_good", False):
                right_evil = False

        actual_evil_count = (1 if left_evil else 0) + (1 if right_evil else 0)

        if actor == world.drunk_player:
            return RoleConstraintResult(
                compatible=True,
                score_delta=0.4,
                required_explanations=[{"type": "DRUNK_EXPLANATION", "player": actor, "evidence": evidence.evidence_id}],
                reason_codes=["EMPATH_EXPLAINED_BY_DRUNK"],
                consumed_evidence_ids=[evidence.evidence_id],
            )

        if actual_evil_count == claimed_num:
            return RoleConstraintResult(
                compatible=True,
                score_delta=1.6,
                reason_codes=["SUPPORTS_EMPATH_INFO"],
                consumed_evidence_ids=[evidence.evidence_id],
            )

        has_poisoner = any(s.matches_role(RoleId.POISONER) for s in world.slots.values())
        if has_poisoner:
            return RoleConstraintResult(
                compatible=True,
                score_delta=-0.9,
                required_explanations=[{"type": "POISON_EXPLANATION", "night": evidence.day, "target": actor, "evidence": evidence.evidence_id}],
                reason_codes=["EMPATH_CONTRADICTED_REQUIRES_POISON"],
                consumed_evidence_ids=[evidence.evidence_id],
            )

        return RoleConstraintResult(
            compatible=False,
            score_delta=-3.5,
            reason_codes=["EMPATH_INFO_CONTRADICTED_UNEXPLAINED"],
            consumed_evidence_ids=[evidence.evidence_id],
        )


class FortuneTellerConstraint(BaseRoleConstraint):
    def evaluate(
        self,
        world: WorldHypothesis,
        evidence: AtomicEvidence,
        observer_state: PlayerState,
        alive_roster: dict[PlayerId, bool],
    ) -> RoleConstraintResult:
        if evidence.content.get("type") != "INFO_FORTUNE_TELLER":
            return RoleConstraintResult(compatible=True)

        targets = evidence.content.get("targets", [])
        claimed_res = evidence.content.get("result", False)
        actor = evidence.source_player if evidence.source_player != "storyteller" else observer_state.player_id

        # A reading is YES if either target is Demon OR Red Herring (or Recluse registering as Demon)
        has_demon = any(t == world.demon_player for t in targets)
        has_recluse_demon = any(
            world.slots.get(t) and world.slots[t].matches_role(RoleId.RECLUSE) and
            world.recluse_registration_assumptions.get(t, {}).get("ft_demon", False)
            for t in targets
        )
        actual_reading = (has_demon or has_recluse_demon)

        if actor == world.drunk_player:
            return RoleConstraintResult(
                compatible=True,
                score_delta=0.4,
                required_explanations=[{"type": "DRUNK_EXPLANATION", "player": actor, "evidence": evidence.evidence_id}],
                reason_codes=["FT_EXPLAINED_BY_DRUNK"],
                consumed_evidence_ids=[evidence.evidence_id],
            )

        if actual_reading == claimed_res:
            return RoleConstraintResult(
                compatible=True,
                score_delta=1.5,
                reason_codes=["SUPPORTS_FT_INFO"],
                consumed_evidence_ids=[evidence.evidence_id],
            )

        # Could it be Red Herring if result was YES but neither is Demon?
        if claimed_res and not actual_reading:
            # Plausible red herring assumption
            rh_cand = targets[0] if targets else "unknown"
            return RoleConstraintResult(
                compatible=True,
                score_delta=0.6,
                required_explanations=[{"type": "RED_HERRING_ASSUMPTION", "player": rh_cand, "evidence": evidence.evidence_id}],
                reason_codes=["FT_YES_EXPLAINED_BY_RED_HERRING"],
                consumed_evidence_ids=[evidence.evidence_id],
            )

        has_poisoner = any(s.matches_role(RoleId.POISONER) for s in world.slots.values())
        if has_poisoner:
            return RoleConstraintResult(
                compatible=True,
                score_delta=-0.8,
                required_explanations=[{"type": "POISON_EXPLANATION", "night": evidence.day, "target": actor, "evidence": evidence.evidence_id}],
                reason_codes=["FT_CONTRADICTED_REQUIRES_POISON"],
                consumed_evidence_ids=[evidence.evidence_id],
            )

        return RoleConstraintResult(
            compatible=False,
            score_delta=-3.0,
            reason_codes=["FT_INFO_CONTRADICTED_UNEXPLAINED"],
            consumed_evidence_ids=[evidence.evidence_id],
        )


class UndertakerConstraint(BaseRoleConstraint):
    def evaluate(
        self,
        world: WorldHypothesis,
        evidence: AtomicEvidence,
        observer_state: PlayerState,
        alive_roster: dict[PlayerId, bool],
    ) -> RoleConstraintResult:
        if evidence.content.get("type") != "INFO_UNDERTAKER":
            return RoleConstraintResult(compatible=True)

        target = evidence.content.get("player")
        learned_role_val = evidence.content.get("role")
        actor = evidence.source_player if evidence.source_player != "storyteller" else observer_state.player_id

        if not target or not learned_role_val:
            return RoleConstraintResult(compatible=True)

        target_slot = world.slots.get(target)

        # Check if learned role matches hypothesized true role
        matches = target_slot.matches_role(RoleId(learned_role_val)) if target_slot else False

        # Recluse/Spy registration possibility
        if not matches and target_slot:
            if target_slot.matches_role(RoleId.RECLUSE):
                matches = True
            elif target_slot.matches_role(RoleId.SPY):
                matches = True

        if actor == world.drunk_player:
            return RoleConstraintResult(
                compatible=True,
                score_delta=0.4,
                required_explanations=[{"type": "DRUNK_EXPLANATION", "player": actor, "evidence": evidence.evidence_id}],
                reason_codes=["UNDERTAKER_EXPLAINED_BY_DRUNK"],
                consumed_evidence_ids=[evidence.evidence_id],
            )

        if matches:
            return RoleConstraintResult(
                compatible=True,
                score_delta=2.0,
                reason_codes=["SUPPORTS_UNDERTAKER_INFO"],
                consumed_evidence_ids=[evidence.evidence_id],
            )

        has_poisoner = any(s.matches_role(RoleId.POISONER) for s in world.slots.values())
        if has_poisoner:
            return RoleConstraintResult(
                compatible=True,
                score_delta=-1.0,
                required_explanations=[{"type": "POISON_EXPLANATION", "night": evidence.day, "target": actor, "evidence": evidence.evidence_id}],
                reason_codes=["UNDERTAKER_CONTRADICTED_REQUIRES_POISON"],
                consumed_evidence_ids=[evidence.evidence_id],
            )

        return RoleConstraintResult(
            compatible=False,
            score_delta=-3.5,
            reason_codes=["UNDERTAKER_CONTRADICTED_UNEXPLAINED"],
            consumed_evidence_ids=[evidence.evidence_id],
        )


class InvestigatorConstraint(BaseRoleConstraint):
    def evaluate(
        self,
        world: WorldHypothesis,
        evidence: AtomicEvidence,
        observer_state: PlayerState,
        alive_roster: dict[PlayerId, bool],
    ) -> RoleConstraintResult:
        actor = evidence.source_player if evidence.source_player != "storyteller" else (observer_state.player_id if observer_state else evidence.observer)
        actor_is_inv = (world.slots.get(actor) and world.slots[actor].matches_role(RoleId.INVESTIGATOR)) or (observer_state and observer_state.player_id == actor and getattr(observer_state, "role", None) == RoleId.INVESTIGATOR)
        ev_type = evidence.content.get("type")
        if ev_type not in ("INFO_INVESTIGATOR", "INVESTIGATOR") and not (actor_is_inv and evidence.evidence_type in (EvidenceType.PAIR_INFO, EvidenceType.ROLE_INFO)):
            return RoleConstraintResult(compatible=True)

        players_pair = evidence.content.get("players", [])
        minion_role = evidence.content.get("role")
        if minion_role:
            try:
                r_minion = RoleId(minion_role) if isinstance(minion_role, str) else minion_role
                if ROLES[r_minion].type != CharacterType.MINION:
                    return RoleConstraintResult(
                        compatible=False,
                        score_delta=-float("inf"),
                        reason_codes=["INVESTIGATOR_LEARNED_NON_MINION_ROLE"],
                        consumed_evidence_ids=[evidence.evidence_id],
                    )
            except Exception:
                pass

        # At least one player in pair should be a minion (or Recluse registering as minion)
        has_minion = any(p in world.minion_players for p in players_pair)
        has_recluse = any(
            world.slots.get(p) and world.slots[p].matches_role(RoleId.RECLUSE)
            for p in players_pair
        )

        if actor == world.drunk_player:
            return RoleConstraintResult(
                compatible=True,
                score_delta=0.4,
                required_explanations=[{"type": "DRUNK_EXPLANATION", "player": actor, "evidence": evidence.evidence_id}],
                reason_codes=["INVESTIGATOR_EXPLAINED_BY_DRUNK"],
                consumed_evidence_ids=[evidence.evidence_id],
            )

        if has_minion or has_recluse:
            return RoleConstraintResult(
                compatible=True,
                score_delta=1.5,
                reason_codes=["SUPPORTS_INVESTIGATOR_INFO"],
                consumed_evidence_ids=[evidence.evidence_id],
            )

        has_poisoner = any(s.matches_role(RoleId.POISONER) for s in world.slots.values())
        if has_poisoner:
            return RoleConstraintResult(
                compatible=True,
                score_delta=-0.8,
                required_explanations=[{"type": "POISON_EXPLANATION", "night": 1, "target": actor, "evidence": evidence.evidence_id}],
                reason_codes=["INVESTIGATOR_CONTRADICTED_REQUIRES_POISON"],
                consumed_evidence_ids=[evidence.evidence_id],
            )

        return RoleConstraintResult(
            compatible=False,
            score_delta=-3.0,
            reason_codes=["INVESTIGATOR_INFO_CONTRADICTED_UNEXPLAINED"],
            consumed_evidence_ids=[evidence.evidence_id],
        )


class WasherwomanConstraint(BaseRoleConstraint):
    def evaluate(
        self,
        world: WorldHypothesis,
        evidence: AtomicEvidence,
        observer_state: PlayerState,
        alive_roster: dict[PlayerId, bool],
    ) -> RoleConstraintResult:
        actor = evidence.source_player if evidence.source_player != "storyteller" else (observer_state.player_id if observer_state else evidence.observer)
        actor_is_ww = (world.slots.get(actor) and world.slots[actor].matches_role(RoleId.WASHERWOMAN)) or (observer_state and observer_state.player_id == actor and getattr(observer_state, "role", None) == RoleId.WASHERWOMAN)
        ev_type = evidence.content.get("type")
        if ev_type not in ("INFO_WASHERWOMAN", "WASHERWOMAN") and not (actor_is_ww and evidence.evidence_type in (EvidenceType.PAIR_INFO, EvidenceType.ROLE_INFO)):
            return RoleConstraintResult(compatible=True)

        pair = evidence.content.get("players", [])
        shown_role_val = evidence.content.get("role")
        if not shown_role_val:
            return RoleConstraintResult(compatible=True)

        try:
            r = RoleId(shown_role_val) if isinstance(shown_role_val, str) else shown_role_val
            if ROLES[r].type != CharacterType.TOWNSFOLK:
                return RoleConstraintResult(
                    compatible=False,
                    score_delta=-float("inf"),
                    reason_codes=["WASHERWOMAN_LEARNED_NON_TOWNSFOLK_ROLE"],
                    consumed_evidence_ids=[evidence.evidence_id],
                )
        except Exception:
            pass
        matches = any(
            world.slots.get(p) and world.slots[p].matches_role(r)
            for p in pair
        )
        # Spy registering as Townsfolk
        has_spy = any(
            world.slots.get(p) and world.slots[p].matches_role(RoleId.SPY)
            for p in pair
        )

        if actor == world.drunk_player:
            return RoleConstraintResult(
                compatible=True,
                score_delta=0.4,
                required_explanations=[{"type": "DRUNK_EXPLANATION", "player": actor, "evidence": evidence.evidence_id}],
                reason_codes=["WASHERWOMAN_EXPLAINED_BY_DRUNK"],
                consumed_evidence_ids=[evidence.evidence_id],
            )

        if matches or has_spy:
            return RoleConstraintResult(
                compatible=True,
                score_delta=1.5,
                reason_codes=["SUPPORTS_WASHERWOMAN_INFO"],
                consumed_evidence_ids=[evidence.evidence_id],
            )

        has_poisoner = any(s.matches_role(RoleId.POISONER) for s in world.slots.values())
        if has_poisoner:
            return RoleConstraintResult(
                compatible=True,
                score_delta=-0.8,
                required_explanations=[{"type": "POISON_EXPLANATION", "night": 1, "target": actor, "evidence": evidence.evidence_id}],
                reason_codes=["WASHERWOMAN_CONTRADICTED_REQUIRES_POISON"],
                consumed_evidence_ids=[evidence.evidence_id],
            )

        return RoleConstraintResult(
            compatible=False,
            score_delta=-3.0,
            reason_codes=["WASHERWOMAN_INFO_CONTRADICTED_UNEXPLAINED"],
            consumed_evidence_ids=[evidence.evidence_id],
        )


class LibrarianConstraint(BaseRoleConstraint):
    def evaluate(
        self,
        world: WorldHypothesis,
        evidence: AtomicEvidence,
        observer_state: PlayerState,
        alive_roster: dict[PlayerId, bool],
    ) -> RoleConstraintResult:
        if evidence.content.get("type") != "INFO_LIBRARIAN":
            return RoleConstraintResult(compatible=True)

        pair = evidence.content.get("players", [])
        shown_role_val = evidence.content.get("role")
        actor = evidence.source_player if evidence.source_player != "storyteller" else observer_state.player_id

        if not shown_role_val:
            # 0 Outsiders shown
            has_outsider = any(
                p == world.drunk_player or (world.slots.get(p) and world.slots[p].role in (RoleId.BUTLER, RoleId.SAINT, RoleId.RECLUSE))
                for p in world.slots
            )
            if not has_outsider:
                return RoleConstraintResult(compatible=True, score_delta=1.5, reason_codes=["SUPPORTS_LIBRARIAN_ZERO_OUTSIDERS"])
            return RoleConstraintResult(compatible=False, score_delta=-2.5, reason_codes=["LIBRARIAN_ZERO_CONTRADICTED"])

        r = RoleId(shown_role_val)
        matches = any(
            world.slots.get(p) and world.slots[p].matches_role(r)
            for p in pair
        )
        if r == RoleId.DRUNK and world.drunk_player in pair:
            matches = True

        # Spy registering as Outsider
        has_spy = any(
            world.slots.get(p) and world.slots[p].matches_role(RoleId.SPY)
            for p in pair
        )

        if actor == world.drunk_player:
            return RoleConstraintResult(
                compatible=True,
                score_delta=0.4,
                required_explanations=[{"type": "DRUNK_EXPLANATION", "player": actor, "evidence": evidence.evidence_id}],
                reason_codes=["LIBRARIAN_EXPLAINED_BY_DRUNK"],
                consumed_evidence_ids=[evidence.evidence_id],
            )

        if matches or has_spy:
            return RoleConstraintResult(
                compatible=True,
                score_delta=1.5,
                reason_codes=["SUPPORTS_LIBRARIAN_INFO"],
                consumed_evidence_ids=[evidence.evidence_id],
            )

        has_poisoner = any(s.matches_role(RoleId.POISONER) for s in world.slots.values())
        if has_poisoner:
            return RoleConstraintResult(
                compatible=True,
                score_delta=-0.8,
                required_explanations=[{"type": "POISON_EXPLANATION", "night": 1, "target": actor, "evidence": evidence.evidence_id}],
                reason_codes=["LIBRARIAN_CONTRADICTED_REQUIRES_POISON"],
                consumed_evidence_ids=[evidence.evidence_id],
            )

        return RoleConstraintResult(
            compatible=False,
            score_delta=-3.0,
            reason_codes=["LIBRARIAN_INFO_CONTRADICTED_UNEXPLAINED"],
            consumed_evidence_ids=[evidence.evidence_id],
        )


class VirginConstraint(BaseRoleConstraint):
    def evaluate(
        self,
        world: WorldHypothesis,
        evidence: AtomicEvidence,
        observer_state: PlayerState,
        alive_roster: dict[PlayerId, bool],
    ) -> RoleConstraintResult:
        is_virgin_event = (
            evidence.content.get("type") == "VIRGIN_PROC"
            or evidence.content.get("reason") == "virgin"
        )
        if not is_virgin_event:
            return RoleConstraintResult(compatible=True)

        nominator = evidence.content.get("nominator") or evidence.content.get("executed")
        virgin_player = evidence.content.get("virgin")

        if not nominator or not virgin_player:
            return RoleConstraintResult(compatible=True)

        # Nominator MUST register as Townsfolk and Virgin must be Townsfolk
        nom_slot = world.slots.get(nominator)
        virgin_slot = world.slots.get(virgin_player)

        virgin_ok = virgin_slot and virgin_slot.matches_role(RoleId.VIRGIN) and virgin_player != world.drunk_player
        nom_is_tf = nom_slot and nom_slot.role and (nom_slot.role in (
            RoleId.WASHERWOMAN, RoleId.LIBRARIAN, RoleId.INVESTIGATOR, RoleId.CHEF,
            RoleId.EMPATH, RoleId.FORTUNE_TELLER, RoleId.UNDERTAKER, RoleId.MONK,
            RoleId.RAVENKEEPER, RoleId.SLAYER, RoleId.SOLDIER, RoleId.MAYOR
        ))
        # Spy registering as Townsfolk
        nom_is_spy = nom_slot and nom_slot.matches_role(RoleId.SPY)

        if virgin_ok and (nom_is_tf or nom_is_spy):
            return RoleConstraintResult(
                compatible=True,
                score_delta=2.5,
                reason_codes=["VIRGIN_PROC_CONFIRMS_TOWNSFOLK"],
                consumed_evidence_ids=[evidence.evidence_id],
            )

        return RoleConstraintResult(
            compatible=False,
            score_delta=-4.0,
            reason_codes=["VIRGIN_PROC_CONTRADICTION"],
            consumed_evidence_ids=[evidence.evidence_id],
        )
