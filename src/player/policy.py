"""Utility-based decision model and Softmax stochastic sampling policy with structured DecisionTrace."""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Sequence

from src.cognition.observation import Observation
from src.cognition.player_state import PlayerState
from src.engine.types import Alignment, PlayerId, RoleId
from src.strategies.primitives import StrategyPrimitive
from src.strategies.role_policies import get_role_modifiers


@dataclass(slots=True)
class DecisionTrace:
    """Complete, transparent decision trace for model validation and dynamic taint testing."""
    action_type: str
    legal_actions: list[str]
    applicable_primitives: list[str]
    candidate_scores: dict[str, float]
    utility_components: dict[str, dict[str, float]]
    softmax_probabilities: dict[str, float]
    chosen_action: str
    collapse_warning: bool = False

    @property
    def candidate_utilities(self) -> dict[str, float]:
        return self.candidate_scores

    @property
    def candidate_probabilities(self) -> dict[str, float]:
        return self.softmax_probabilities



def softmax_eval(
    candidates: Sequence[tuple[str, float]],
    temperature: float = 1.0,
    rng: random.Random | None = None,
) -> tuple[str, dict[str, float]]:
    """Softmax evaluation returning chosen candidate and exact probability distribution."""
    if not candidates:
        raise ValueError("Cannot sample from empty candidates.")
    if len(candidates) == 1:
        return candidates[0][0], {candidates[0][0]: 1.0}

    r = rng or random.Random()
    t = max(0.1, temperature)
    max_score = max(score for _, score in candidates)

    exp_scores = [math.exp(min(20.0, max(-20.0, (score - max_score) / t))) for _, score in candidates]
    total_exp = sum(exp_scores)
    probs = [e / total_exp for e in exp_scores]
    probs_dict = {candidates[i][0]: probs[i] for i in range(len(candidates))}

    chosen = r.choices([c[0] for c in candidates], weights=probs, k=1)[0]
    return chosen, probs_dict


def softmax_sample(
    candidates: Sequence[tuple[str, float]],
    temperature: float = 1.0,
    rng: random.Random | None = None,
) -> str:
    """Softmax sampling over candidate actions with numerical stability."""
    chosen, _ = softmax_eval(candidates, temperature=temperature, rng=rng)
    return chosen


class CognitionPolicy:
    """Evaluates utility for nomination, voting, and night actions from internal PlayerState."""

    def __init__(
        self,
        state: PlayerState,
        rng: random.Random | None = None,
        ablated_primitives: set[str] | None = None,
        config: Any = None,
    ) -> None:
        self.state = state
        self.rng = rng or random.Random()
        self.ablated_primitives = set(ablated_primitives or [])
        self.config = config
        self.modifiers = get_role_modifiers(state.perceived_role, ablated_primitives=self.ablated_primitives)
        self.last_trace: DecisionTrace | None = None

    def score_nomination_detailed(self, obs: Observation) -> tuple[PlayerId | None, DecisionTrace | None]:
        """Score all legal nominees returning chosen nominee and full DecisionTrace."""
        if not obs.alive or self.state.player_id in obs.nominated_by_today:
            return None, None

        legal_nominees = [
            p for p in obs.roster_alive.keys()
            if p not in obs.nominated_today and p != self.state.player_id
        ]
        if not legal_nominees:
            return None, None

        legal_actions = ["pass"] + sorted(legal_nominees)

        # Continuous PASS utility
        # 1. Uncertainty: if max evil probability across legal targets is low, uncertainty is high
        max_evil_suspicion = max(
            (self.state.beliefs.get(p).evil for p in legal_nominees if self.state.beliefs.get(p)),
            default=0.3
        )
        uncertainty_comp = (1.0 - max_evil_suspicion) * 1.5

        # 2. Wrong Execution Risk: parity & late-game penalty
        # At 4 alive, wrong execution means 3 alive at dusk -> 2 alive at night -> instant demon win!
        n_alive = len([p for p, alive in obs.roster_alive.items() if alive])
        if n_alive == 4:
            wrong_exec_risk = 1.2
        elif n_alive % 2 == 0:
            wrong_exec_risk = 0.5  # Even alive count: parity loss
        elif n_alive == 3:
            wrong_exec_risk = 0.2
        else:
            wrong_exec_risk = 0.1

        # Check if Mayor is believed alive/functioning
        mayor_believed_alive = False
        if obs.self_role == RoleId.MAYOR and obs.alive:
            mayor_believed_alive = True
        else:
            for p, claim in self.state.public_claims.items():
                if claim.claimed_role == RoleId.MAYOR and obs.roster_alive.get(p, False):
                    # Trusted claim or positive good belief
                    if self.state.trust.get(p, 0.0) > 0.0 or (self.state.beliefs.get(p) and self.state.beliefs[p].good > 0.4):
                        mayor_believed_alive = True
                        break

        if n_alive == 3:
            if mayor_believed_alive:
                mayor_f3_comp = 1.5  # Strategic bonus: pursuit of Mayor 3-alive victory condition
            else:
                mayor_f3_comp = -5.0  # Suicide without Mayor: no-execution yields free Demon night kill win!
        else:
            mayor_f3_comp = 0.0

        # 3. Nomination saturation: as more nominations have occurred today, incentive to pass increases
        saturation_comp = min(1.2, len(obs.nominations_today) * 0.4)

        # 4. Aggression penalty: aggressive players dislike passing
        pass_aggression_penalty = self.state.personality.aggression * 1.0

        pass_utility = uncertainty_comp + wrong_exec_risk + saturation_comp + mayor_f3_comp - pass_aggression_penalty - 0.8
        candidates: list[tuple[str, float]] = [("pass", pass_utility)]
        candidate_scores: dict[str, float] = {"pass": pass_utility}
        utility_components: dict[str, dict[str, float]] = {
            "pass": {
                "uncertainty": uncertainty_comp,
                "wrong_exec_risk": wrong_exec_risk,
                "saturation": saturation_comp,
                "mayor_f3_comp": mayor_f3_comp,
                "aggression_penalty": -pass_aggression_penalty,
                "base": -0.8,
            }
        }

        applicable_primitives: list[str] = []

        nom_evil_w = float(self.config.get("nomination_evil_weight", 2.5)) if self.config else 2.5
        nom_demon_w = float(self.config.get("nomination_demon_weight", 1.5)) if self.config else 1.5

        for target in sorted(legal_nominees):
            b = self.state.beliefs.get(target)
            evil_prob = b.evil if b else 0.3
            demon_prob = b.demon if b else 0.1

            evil_comp = evil_prob * nom_evil_w
            demon_comp = demon_prob * nom_demon_w
            if evil_prob > 0.4 and StrategyPrimitive.PUSH_EXECUTION.value not in applicable_primitives:
                applicable_primitives.append(StrategyPrimitive.PUSH_EXECUTION.value)

            # Virgin testing utility
            virgin_comp = 0.0
            claimed_role = self.state.public_claims.get(target)
            if claimed_role and claimed_role.claimed_role == RoleId.VIRGIN:
                test_bias = self.modifiers.get(StrategyPrimitive.TEST_VIRGIN, 0.0)
                virgin_comp = test_bias * 2.0
                if test_bias > 0 and StrategyPrimitive.TEST_VIRGIN.value not in applicable_primitives:
                    applicable_primitives.append(StrategyPrimitive.TEST_VIRGIN.value)

            # Aggression personality modifier
            aggression_comp = (self.state.personality.aggression - 0.5) * 1.2
            noise_comp = self.rng.gauss(0.0, 0.1)

            total_score = evil_comp + demon_comp + virgin_comp + aggression_comp + noise_comp
            candidates.append((target, total_score))
            candidate_scores[target] = total_score
            utility_components[target] = {
                "evil_contrib": evil_comp,
                "demon_contrib": demon_comp,
                "virgin_bias": virgin_comp,
                "aggression": aggression_comp,
                "noise": noise_comp,
            }

        chosen, probs_dict = softmax_eval(candidates, temperature=self.state.skill.temperature, rng=self.rng)
        has_warning = len(candidates) > 1 and max(probs_dict.values()) > 0.95 and chosen != "pass"
        trace = DecisionTrace(
            action_type="nomination",
            legal_actions=legal_actions,
            applicable_primitives=sorted(applicable_primitives),
            candidate_scores=candidate_scores,
            utility_components=utility_components,
            softmax_probabilities=probs_dict,
            chosen_action=chosen,
            collapse_warning=has_warning,
        )
        self.last_trace = trace
        return (chosen if chosen != "pass" else None), trace

    def score_nomination(self, obs: Observation) -> PlayerId | None:
        """Score all legal nominees based on suspicion, virgin testing, and role value."""
        chosen, _ = self.score_nomination_detailed(obs)
        return chosen

    def score_vote_detailed(self, obs: Observation) -> tuple[bool, DecisionTrace | None]:
        """Evaluate vote utility on active nomination returning (vote_yes, DecisionTrace)."""
        if not obs.current_nomination:
            return False, None

        nominee = obs.current_nomination["nominee"]
        is_alive = obs.alive
        has_ghost = obs.ghost_vote_available

        if not is_alive and not has_ghost:
            return False, None

        # Butler check
        if is_alive and obs.self_role == RoleId.BUTLER and obs.butler_master:
            master_vote = obs.current_nomination.get("votes", {}).get(obs.butler_master, False)
            if not master_vote:
                return False, None

        b = self.state.beliefs.get(nominee)
        evil_prob = b.evil if b else 0.3
        demon_prob = b.demon if b else 0.1
        applicable_primitives: list[str] = []

        vote_evil_w = float(self.config.get("vote_evil_weight", 3.0)) if self.config else 3.0
        vote_demon_w = float(self.config.get("vote_demon_weight", 2.0)) if self.config else 2.0
        vote_base = float(self.config.get("vote_base_bias", -1.2)) if self.config else -1.2
        n_alive = len([p for p, a in obs.roster_alive.items() if a])

        if self.state.perceived_alignment == Alignment.GOOD:
            evil_comp = evil_prob * vote_evil_w
            demon_comp = demon_prob * vote_demon_w
            base_bias = vote_base
            # Dynamic ghost vote conservation:
            # > 4 alive: heavy conservation penalty
            # == 4 alive: moderate penalty
            # <= 3 alive: 0 penalty (crucial endgame, must spend to execute)
            if not is_alive:
                if n_alive > 4:
                    ghost_cost = -2.5 * self.state.skill.voting_discipline
                elif n_alive == 4:
                    ghost_cost = -1.2 * self.state.skill.voting_discipline
                else:
                    ghost_cost = 0.0
            else:
                ghost_cost = 0.0

            current_votes = sum(1 for v in obs.current_nomination.get("votes", {}).values() if v)
            conformity_comp = (
                self.state.personality.conformity * 1.0
                if current_votes >= obs.execution_threshold
                else 0.0
            )
            utility_yes = evil_comp + demon_comp + base_bias + ghost_cost + conformity_comp
            utility_components_yes = {
                "evil_contrib": evil_comp,
                "demon_contrib": demon_comp,
                "base": base_bias,
                "ghost_cost": ghost_cost,
                "conformity": conformity_comp,
            }
            if evil_prob > 0.4:
                applicable_primitives.append(StrategyPrimitive.PUSH_EXECUTION.value)
        else:
            # Evil team voter: Nuanced utility formulation U_vote = w_s SaveDemon + w_b BluffConsistency + w_e ExposureRisk + w_bus BusValue + w_c VoteContext
            is_target_demon = (
                obs.evil_team_knowledge
                and obs.evil_team_knowledge.get("demon") == nominee
            )
            is_self = (nominee == self.state.player_id)
            current_votes = sum(1 for v in obs.current_nomination.get("votes", {}).values() if v)
            threshold = obs.execution_threshold

            if not is_alive:
                if n_alive > 4:
                    ghost_cost = -2.5 * self.state.skill.voting_discipline
                elif n_alive == 4:
                    ghost_cost = -1.0 * self.state.skill.voting_discipline
                else:
                    ghost_cost = 0.0
            else:
                ghost_cost = 0.0

            if is_self:
                utility_yes = -3.0 + ghost_cost
                utility_components_yes = {"self_preservation": -3.0, "ghost_cost": ghost_cost}
            elif is_target_demon:
                # Save Demon vs Bus / Bluff Consistency
                save_demon_base = -2.2

                if current_votes >= threshold:
                    # Demon already doomed: vote YES to save cover and build trust
                    vote_context_comp = 1.8
                    bus_comp = 1.2 * self.state.skill.skill_score

                elif current_votes >= threshold - 1 and n_alive > 4:
                    vote_context_comp = 0.8
                    bus_comp = 0.5
                else:
                    vote_context_comp = -0.5
                    bus_comp = 0.0

                claimed_rec = self.state.public_claims.get(self.state.player_id)
                if claimed_rec and claimed_rec.claimed_role in (RoleId.VIRGIN, RoleId.SLAYER, RoleId.FORTUNE_TELLER, RoleId.EMPATH):
                    bluff_consistency_comp = 1.2
                    exposure_risk_comp = 1.0
                else:
                    bluff_consistency_comp = 0.0
                    exposure_risk_comp = 0.2

                coord_noise = self.rng.gauss(0.0, 0.25 * (1.0 - self.state.skill.voting_discipline))

                utility_yes = (
                    save_demon_base +
                    vote_context_comp +
                    bus_comp +
                    bluff_consistency_comp +
                    exposure_risk_comp +
                    coord_noise +
                    ghost_cost
                )
                utility_components_yes = {
                    "save_demon": save_demon_base,
                    "vote_context": vote_context_comp,
                    "bus_value": bus_comp,
                    "bluff_consistency": bluff_consistency_comp,
                    "exposure_risk": exposure_risk_comp,
                    "noise": coord_noise,
                    "ghost_cost": ghost_cost,
                }
                applicable_primitives.append(StrategyPrimitive.EVIL_COORDINATION.value)
            else:
                is_minion_teammate = (
                    obs.evil_team_knowledge
                    and nominee in obs.evil_team_knowledge.get("minions", [])
                )
                if is_minion_teammate:
                    if obs.day >= 2 and current_votes >= threshold - 1:
                        bus_minion = 0.8 * self.state.skill.skill_score
                    else:
                        bus_minion = -0.5
                    utility_yes = 0.2 + bus_minion + ghost_cost
                    utility_components_yes = {"bus_minion": bus_minion, "base": 0.2, "ghost_cost": ghost_cost}
                else:
                    push_good = 1.2
                    if current_votes == 0 and obs.day >= 2:
                        caution = -0.3 * (1.0 - self.state.personality.aggression)
                    else:
                        caution = 0.2
                    utility_yes = push_good + caution + ghost_cost
                    utility_components_yes = {"push_good": push_good, "caution": caution, "ghost_cost": ghost_cost}
                applicable_primitives.append(StrategyPrimitive.EVIL_COORDINATION.value)

        utility_no = 0.0
        candidates = [("yes", utility_yes), ("no", utility_no)]
        chosen, probs_dict = softmax_eval(candidates, temperature=self.state.skill.temperature, rng=self.rng)
        has_warning = len(candidates) > 1 and max(probs_dict.values()) > 0.95

        trace = DecisionTrace(
            action_type="vote",
            legal_actions=["yes", "no"],
            applicable_primitives=sorted(applicable_primitives),
            candidate_scores={"yes": utility_yes, "no": utility_no},
            utility_components={"yes": utility_components_yes, "no": {"base": 0.0}},
            softmax_probabilities=probs_dict,
            chosen_action=chosen,
            collapse_warning=has_warning,
        )
        self.last_trace = trace
        return chosen == "yes", trace

    def score_vote(self, obs: Observation) -> bool:
        """Evaluate vote utility on the active nomination."""
        chosen, _ = self.score_vote_detailed(obs)
        return chosen
