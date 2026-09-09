"""Master Information Consistency Engine and Resource-Constrained Explanation Accounting."""
from __future__ import annotations

import math
from typing import Any

from src.cognition.player_state import PlayerState
from src.engine.types import Alignment, CharacterType, PlayerId, RoleId
from src.reasoning.constraints.death_constraints import evaluate_death_pattern_consistency
from src.reasoning.constraints.setup_constraints import check_setup_legality
from src.reasoning.evidence import AtomicEvidence, EvidenceTier, EvidenceType
from src.reasoning.role_constraints.base import BaseRoleConstraint, RoleConstraintResult
from src.reasoning.role_constraints.outsiders import SaintConstraint
from src.reasoning.role_constraints.townsfolk import (
    ChefConstraint,
    EmpathConstraint,
    FortuneTellerConstraint,
    InvestigatorConstraint,
    LibrarianConstraint,
    UndertakerConstraint,
    VirginConstraint,
    WasherwomanConstraint,
)
from src.reasoning.world import RoleSlot, SlotState, WorldHypothesis


class InformationConstraintsCoordinator:
    """Evaluates comprehensive world score across setup, info, claims, death patterns, and bounded explanations."""

    def __init__(self) -> None:
        self.role_evaluators: list[BaseRoleConstraint] = [
            ChefConstraint(),
            EmpathConstraint(),
            FortuneTellerConstraint(),
            UndertakerConstraint(),
            InvestigatorConstraint(),
            WasherwomanConstraint(),
            LibrarianConstraint(),
            VirginConstraint(),
            SaintConstraint(),
        ]

    def _validate_poison_resource_capacity(
        self,
        world: WorldHypothesis,
        alive_roster: dict[PlayerId, bool],
        living_players_by_day: dict[int, list[PlayerId]] | None = None,
    ) -> bool:
        """Enforce strict Poisoner capacity: living Poisoner, 1 target/night."""
        if not world.poison_history:
            return True

        poisoner_slots = [p for p, s in world.slots.items() if s.matches_role(RoleId.POISONER)]
        if not poisoner_slots:
            return False

        p_source = poisoner_slots[0]
        targets_by_night: dict[int, set[PlayerId]] = {}
        for action in world.poison_history:
            night = action.get("night", 1)
            target = action.get("target")
            source = action.get("source", p_source)

            if living_players_by_day and night in living_players_by_day:
                if source not in living_players_by_day[night]:
                    return False
            elif night > 1 and alive_roster and not alive_roster.get(source, True):
                return False

            if target:
                targets_by_night.setdefault(night, set()).add(target)

        for night, targets in targets_by_night.items():
            if len(targets) > 1:
                return False

        return True

    def evaluate_world(
        self,
        world: WorldHypothesis,
        evidence_list: list[AtomicEvidence],
        observer_state: PlayerState,
        alive_roster: dict[PlayerId, bool],
        living_players_by_day: dict[int, list[PlayerId]] | None = None,
        complexity_aversion: float = 1.0,
    ) -> float:
        """Evaluate full consistency score for a WorldHypothesis, updating its components."""
        # 1. Hard Setup Legality Check
        tot_players = len(world.slots) if world.slots else len(alive_roster)
        obs_id = observer_state.player_id if observer_state else None
        obs_align = observer_state.perceived_alignment if observer_state else Alignment.GOOD
        is_legal, violation_reason = check_setup_legality(
            world=world,
            total_players=tot_players,
            observer_id=obs_id,
            observer_alignment=obs_align,
        )
        if not is_legal:
            world.score_rule = -float("inf")
            world.total_score = -float("inf")
            return -float("inf")

        # 1b. Strict Poison Resource Capacity Check
        if not self._validate_poison_resource_capacity(world, alive_roster, living_players_by_day):
            world.score_rule = -float("inf")
            world.total_score = -float("inf")
            return -float("inf")
        world.score_rule = 0.0

        # 2. Information Consistency across atomic evidence
        score_info = 0.0
        explanations_gathered: list[dict[str, Any]] = []

        for ev in evidence_list:
            if ev.evidence_id in world.consumed_evidence_ids:
                continue

            for evaluator in self.role_evaluators:
                res = evaluator.evaluate(world, ev, observer_state, alive_roster)
                if not res.compatible:
                    world.score_info = -float("inf")
                    world.total_score = -float("inf")
                    return -float("inf")
                else:
                    score_info += res.score_delta
                    explanations_gathered.extend(res.required_explanations)

                for cid in res.consumed_evidence_ids:
                    world.consumed_evidence_ids.add(cid)

        # 3. Death Pattern Consistency
        living_by_day = living_players_by_day or {1: list(alive_roster.keys())}
        death_score, death_exp, _ = evaluate_death_pattern_consistency(world, evidence_list, living_by_day)
        explanations_gathered.extend(death_exp)
        world.score_death = death_score

        # 4. Public Claims Consistency
        score_claim = 0.0
        claims_dict = observer_state.public_claims if observer_state else {}
        for p, claim_rec in claims_dict.items():
            slot = world.slots.get(p)
            c_role = getattr(claim_rec, "claimed_role", None)
            if not slot or not c_role:
                continue

            is_hypo_evil = (p == world.demon_player or p in world.minion_players)

            if slot.matches_role(c_role):
                score_claim += 0.8
            elif is_hypo_evil:
                # Plausible evil bluff
                score_claim += 0.2
                explanations_gathered.append({"type": "EVIL_BLUFF", "player": p, "claimed": c_role.value})
            elif p == world.drunk_player:
                # Drunk thinks they are that role
                score_claim += 0.4
            else:
                # Unprovoked false claim by Good player
                score_claim -= 1.5

        world.score_claim = score_claim

        # 5. Social Opinion & Trust Auxiliary Prior
        score_social = 0.0
        suspicion_dict = observer_state.suspicion if observer_state else {}
        for p, s in suspicion_dict.items():
            if p == world.demon_player:
                score_social += (s - 0.5) * 1.2
            elif p in world.minion_players:
                score_social += (s - 0.5) * 0.6

        world.score_social = score_social

        # 6. Resource-Constrained Explanation & Complexity Accounting
        # Explanations must satisfy real ability limits:
        # A single living Poisoner can poison at most 1 target per night.
        poison_assumptions_by_night: dict[int, set[PlayerId]] = {}
        for exp in explanations_gathered:
            if exp.get("type") == "POISON_EXPLANATION":
                night = exp.get("night", 1)
                target = exp.get("target")
                if target:
                    poison_assumptions_by_night.setdefault(night, set()).add(target)

        for p_action in world.poison_history:
            night = p_action.get("night", 1)
            target = p_action.get("target")
            if target:
                poison_assumptions_by_night.setdefault(night, set()).add(target)

        # Check Poisoner capacity: in TB, 1 Poisoner = 1 target/night
        has_poisoner = any(s.matches_role(RoleId.POISONER) for s in world.slots.values())
        poisoner_capacity_violation = False
        if not has_poisoner and poison_assumptions_by_night:
            poisoner_capacity_violation = True
        else:
            for night, targets in poison_assumptions_by_night.items():
                if len(targets) > 1:
                    # Over-capacity: 1 Poisoner cannot poison multiple different targets on same night!
                    poisoner_capacity_violation = True
                    break

        if poisoner_capacity_violation:
            world.cost_explanation = float("inf")
            world.total_score = -float("inf")
            return -float("inf")

        # Reuse explanation: number of actual poison nights charged
        n_poison_actions = sum(1 for targets in poison_assumptions_by_night.values() if targets)
        n_drunk = 1 if world.drunk_player else 0
        n_reg = len(world.spy_registration_assumptions) + len(world.recluse_registration_assumptions)
        n_bluffs = sum(1 for e in explanations_gathered if e.get("type") == "EVIL_BLUFF")

        lambda_p = 0.8
        lambda_d = 0.6
        lambda_r = 0.5
        lambda_f = 0.3

        cost_exp = (
            lambda_p * n_poison_actions +
            lambda_d * n_drunk +
            lambda_r * n_reg +
            lambda_f * n_bluffs
        )

        total_assumptions = n_poison_actions + n_drunk + n_reg + n_bluffs
        cost_complexity = (0.35 * complexity_aversion) * (total_assumptions ** 1.5)

        world.cost_explanation = cost_exp
        world.cost_complexity = cost_complexity
        world.score_info = score_info

        total = (
            world.score_rule +
            score_info +
            score_claim +
            death_score +
            score_social -
            cost_exp -
            cost_complexity
        )
        world.total_score = total
        return total
