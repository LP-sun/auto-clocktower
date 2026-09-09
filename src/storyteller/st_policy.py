"""Storyteller utility policy balancing fairness, tension, solvability, and drama."""
from __future__ import annotations

import math
import random
from typing import Any, Mapping

from src.engine.state import GameState
from src.engine.types import PlayerId, RoleId, STDecisionType
from src.storyteller.legal_actions import generate_legal_st_actions
from src.storyteller.solvability import calculate_solvability_proxy, is_in_healthy_solvability_range
from src.storyteller.tension import calculate_tension
from src.storyteller.types import STDecisionPhase, STDecisionRecord, STReasonCode


class StorytellerPolicy:
    """Mathematical Storyteller evaluating discretionary choices against game-balance objectives."""

    def __init__(self, seed: int | None = None, temperature: float = 0.5) -> None:
        self.rng = random.Random(seed)
        self.temperature = temperature
        self._next_decision_id = 1
        self.decisions_log: list[STDecisionRecord] = []

    def decide(
        self,
        decision_type: STDecisionType,
        state: GameState,
        actor: PlayerId | None = None,
        suspicions: Mapping[PlayerId, float] | None = None,
        context: str | None = None,
    ) -> Any:
        legal_actions = generate_legal_st_actions(decision_type, state, actor=actor, context=context)
        if not legal_actions:
            return None
        if len(legal_actions) == 1:
            return legal_actions[0]

        current_tension = calculate_tension(state, suspicions)
        current_solvability = calculate_solvability_proxy(state, suspicions)

        # Robust belief summary features (score-softmax approximations, not calibrated Bayesian posteriors)
        candidate_count = sum(1 for p, s in (suspicions or {}).items() if s > 0.3)
        mean_suspicion = (sum((suspicions or {}).values()) / len(suspicions)) if suspicions else 0.25

        action_scores: list[tuple[Any, float, dict[str, float], list[str]]] = []
        counterfactual_scores: dict[str, dict[str, float]] = {}

        for action in legal_actions:
            fairness = 0.5
            tension_contrib = current_tension
            solvability = 0.8 if is_in_healthy_solvability_range(current_solvability) else 0.4
            drama = 0.6
            reasons: list[str] = [STReasonCode.PRESERVE_SOLVABILITY.value]

            if decision_type == STDecisionType.DRUNK_POISON_MISINFO:
                actor_role = state.true_roles.get(actor) if actor else None
                if actor_role == RoleId.EMPATH:
                    if isinstance(action, int):
                        if action == 1:
                            solvability += 0.25
                            fairness += 0.15
                            reasons.append(STReasonCode.PLAUSIBLE_MISINFO.value)
                        elif action == 0:
                            tension_contrib += 0.20
                            solvability += 0.10
                            reasons.append(STReasonCode.AVOID_HARD_CONFIRMATION.value)
                        else:
                            drama += 0.35
                            solvability -= 0.05
                            reasons.append(STReasonCode.DRAMATIC_BALANCE.value)
                elif actor_role == RoleId.FORTUNE_TELLER:
                    if action is True:
                        solvability += 0.30
                        drama += 0.15
                        reasons.append(STReasonCode.SIMULATE_RED_HERRING.value)
                    else:
                        fairness += 0.20
                        tension_contrib += 0.25
                        reasons.append(STReasonCode.AVOID_HARD_CONFIRMATION.value)
                elif isinstance(action, int):
                    if action in (0, 1):
                        solvability += 0.25
                        reasons.append(STReasonCode.AVOID_HARD_CONFIRMATION.value)
                    elif action >= 2:
                        drama += 0.35
                        reasons.append(STReasonCode.DRAMATIC_BALANCE.value)
                else:
                    solvability += 0.15
                    drama += 0.15
                    reasons.append(STReasonCode.PLAUSIBLE_MISINFO.value)

            elif decision_type == STDecisionType.MAYOR_BOUNCE:
                if action is None:
                    # Accept Mayor death: legitimate narrative choice in late game or when preserving other players
                    if state.alive_count <= 4:
                        tension_contrib += 0.20
                        fairness += 0.20
                        solvability += 0.15
                        drama += 0.10
                        reasons.append("ACCEPT_MAYOR_DEATH")
                    else:
                        fairness += 0.25
                        tension_contrib += 0.15
                        solvability += 0.15
                        reasons.append("ACCEPT_MAYOR_DEATH")
                else:
                    target_p = action
                    t_role = state.true_roles.get(target_p)
                    if t_role == RoleId.RAVENKEEPER:
                        drama += 0.25
                        solvability += 0.20
                        tension_contrib += 0.15
                        reasons.append(STReasonCode.TRIGGER_RAVENKEEPER.value)
                    elif t_role == RoleId.SOLDIER:
                        solvability += 0.25
                        fairness += 0.20
                        drama += 0.15
                        reasons.append(STReasonCode.CONFIRM_SOLDIER.value)
                    elif t_role in (RoleId.WASHERWOMAN, RoleId.LIBRARIAN, RoleId.CHEF):
                        tension_contrib += 0.25
                        solvability += 0.20
                        drama += 0.15
                        reasons.append(STReasonCode.TARGET_SPENT_ROLE.value)
                    elif t_role in (RoleId.EMPATH, RoleId.FORTUNE_TELLER, RoleId.UNDERTAKER):
                        solvability += 0.10
                        drama += 0.20
                        tension_contrib += 0.15
                        reasons.append("HIT_ACTIVE_INFO_ROLE")
                    elif t_role in (RoleId.SAINT, RoleId.BUTLER, RoleId.RECLUSE):
                        fairness += 0.20
                        tension_contrib += 0.20
                        drama += 0.15
                        reasons.append("SAFE_OUTSIDER_NIGHT_KILL")
                    elif t_role in (RoleId.POISONER, RoleId.BARON, RoleId.SPY, RoleId.SCARLET_WOMAN):
                        drama += 0.30
                        tension_contrib += 0.25
                        fairness += 0.15
                        reasons.append("BOUNCE_TO_MINION")
                    else:
                        drama += 0.18
                        tension_contrib += 0.18
                        solvability += 0.15
                        reasons.append(STReasonCode.MAINTAIN_TENSION.value)

            elif decision_type == STDecisionType.RECLUSE_REGISTRATION:
                # If Recluse registers as evil/demon, it creates confusion/drama but lowers solvability
                if isinstance(action, dict) and action.get("alignment") != "good":
                    drama += 0.25
                    reasons.append(STReasonCode.SUPPORT_DEMON_BLUFF.value)
                else:
                    solvability += 0.2

            elif decision_type == STDecisionType.SPY_REGISTRATION:
                # If Spy registers as townsfolk, aids evil infiltration
                if isinstance(action, dict) and action.get("alignment") == "good":
                    drama += 0.25
                    reasons.append(STReasonCode.SUPPORT_DEMON_BLUFF.value)
                else:
                    fairness += 0.2

            total_utility = (
                0.25 * fairness +
                0.25 * tension_contrib +
                0.25 * solvability +
                0.25 * drama
            )

            components = {
                "fairness": fairness,
                "tension": tension_contrib,
                "solvability": solvability,
                "drama": drama,
            }
            action_scores.append((action, total_utility, components, reasons))
            counterfactual_scores[str(action)] = {
                "total_utility": total_utility,
                **components,
            }

        # Calculate choice sensitivity: delta_u = U_best - U_second
        sorted_scores = sorted([u for _, u, _, _ in action_scores], reverse=True)
        delta_u = sorted_scores[0] - sorted_scores[1] if len(sorted_scores) > 1 else 0.0

        # Softmax sampling
        max_u = sorted_scores[0]
        t = max(0.1, self.temperature)
        exp_scores = [math.exp((u - max_u) / t) for _, u, _, _ in action_scores]
        total_exp = sum(exp_scores)
        probs = [e / total_exp for e in exp_scores]

        idx = self.rng.choices(range(len(action_scores)), weights=probs, k=1)[0]
        chosen_action, _, chosen_components, chosen_reasons = action_scores[idx]

        # Determine STDecisionPhase
        if decision_type in (
            STDecisionType.SETUP_DISTRIBUTION,
            STDecisionType.DRUNK_FAKE_ROLE,
            STDecisionType.RED_HERRING_SELECTION,
            STDecisionType.IMP_BLUFFS,
        ) or (state.day == 0 and state.night_number == 0):
            dec_phase = STDecisionPhase.SETUP
        elif decision_type in (STDecisionType.RECLUSE_REGISTRATION, STDecisionType.SPY_REGISTRATION):
            dec_phase = STDecisionPhase.REGISTRATION
        elif decision_type == STDecisionType.MAYOR_BOUNCE:
            dec_phase = STDecisionPhase.DEATH_RESOLUTION
        elif state.phase.value == "day":
            dec_phase = STDecisionPhase.DAY
        else:
            dec_phase = STDecisionPhase.NIGHT

        record = STDecisionRecord(
            decision_id=self._next_decision_id,
            seed=state.seed,
            day=state.day,
            night=state.night_number,
            decision_type=decision_type,
            actor=actor,
            state_features={
                "alive_count": state.alive_count,
                "tension": current_tension,
                "entropy": current_solvability,
                "solvability_proxy": current_solvability,
                "candidate_count": candidate_count,
                "mean_suspicion": mean_suspicion,
                "execution_threshold": state.execution_threshold,
            },
            legal_actions=legal_actions,
            chosen_action=chosen_action,
            utility_components=chosen_components,
            counterfactual_scores=counterfactual_scores,
            delta_u=delta_u,
            reason_codes=chosen_reasons,
            phase=dec_phase,
        )
        self._next_decision_id += 1
        self.decisions_log.append(record)

        return chosen_action
