"""Top-K Plausible World Hypothesis Modeling and Consistency Scoring for Trouble Brewing."""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Any

from src.cognition.player_state import PlayerState
from src.engine.types import Alignment, PlayerId, RoleId


@dataclass(slots=True)
class WorldHypothesis:
    world_id: int
    demon: PlayerId
    minions: list[PlayerId]
    good_players: list[PlayerId]
    role_assignments: dict[PlayerId, RoleId]
    drunk_player: PlayerId | None = None
    poison_explanations: list[dict[str, Any]] = field(default_factory=list)
    registration_assumptions: dict[PlayerId, str] = field(default_factory=dict)
    score: float = 0.0
    probability: float = 0.0

    # Detailed consistency breakdown
    info_consistency: float = 0.0
    claim_consistency: float = 0.0
    rule_consistency: float = 0.0
    social_consistency: float = 0.0
    vote_consistency: float = 0.0
    complexity_penalty: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "world_id": self.world_id,
            "demon": self.demon,
            "minions": self.minions,
            "good_players": self.good_players,
            "role_assignments": {p: r.value for p, r in self.role_assignments.items()},
            "drunk_player": self.drunk_player,
            "poison_explanations_count": len(self.poison_explanations),
            "registration_assumptions_count": len(self.registration_assumptions),
            "score": round(self.score, 4),
            "probability": round(self.probability, 4),
            "complexity_penalty": round(self.complexity_penalty, 4),
        }


@dataclass(slots=True)
class WorldDiversityReport:
    total_worlds: int
    effective_world_count: float
    top1_world_prob: float
    top3_world_mass: float
    world_entropy_proxy: float
    demon_marginals: dict[PlayerId, float]
    collapse_warning: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_worlds": self.total_worlds,
            "effective_world_count": round(self.effective_world_count, 4),
            "top1_world_prob": round(self.top1_world_prob, 4),
            "top3_world_mass": round(self.top3_world_mass, 4),
            "world_entropy_proxy": round(self.world_entropy_proxy, 4),
            "demon_marginals": {p: round(prob, 4) for p, prob in self.demon_marginals.items()},
            "collapse_warning": self.collapse_warning,
        }


class WorldHypothesisManager:
    """Manages generation, scoring, and marginalization of Top-K plausible joint role worlds."""

    def __init__(
        self,
        k: int = 32,
        temperature: float = 1.0,
        rng: random.Random | None = None,
        config: Any = None,
    ) -> None:
        self.k = k
        self.temperature = max(0.1, temperature)
        self.rng = rng or random.Random()
        self.config = config
        self.worlds: list[WorldHypothesis] = []
        self._next_world_id = 1

    def generate_candidate_worlds(
        self,
        observer_id: PlayerId,
        all_players: list[PlayerId],
        claims: dict[PlayerId, RoleId],
        alive_roster: dict[PlayerId, bool],
        perceived_role: RoleId,
        perceived_alignment: Alignment,
        demon_candidates: list[PlayerId] | None = None,
    ) -> list[WorldHypothesis]:
        """Generate a beam of plausible candidate worlds adhering to Trouble Brewing compositions."""
        candidates: list[WorldHypothesis] = []
        n_players = len(all_players)

        # Expected evil count for Trouble Brewing
        if n_players >= 10:
            n_minions = 2
        elif n_players >= 7:
            n_minions = 1
        else:
            n_minions = 0

        # Self constraint: observer knows their own perceived role and alignment
        others = [p for p in all_players if p != observer_id]
        demon_pool = demon_candidates if demon_candidates else others

        # Sample combinations of (Demon, Minions, Drunk)
        for _ in range(self.k * 3):
            d = self.rng.choice(demon_pool)
            possible_minions = [p for p in others if p != d]
            if len(possible_minions) >= n_minions:
                m_list = self.rng.sample(possible_minions, n_minions)
            else:
                m_list = possible_minions

            good_pool = [p for p in all_players if p != d and p not in m_list]

            # Assign roles consistent with public claims where possible
            role_assigns: dict[PlayerId, RoleId] = {}
            for p in all_players:
                if p == observer_id:
                    role_assigns[p] = perceived_role
                elif p == d:
                    role_assigns[p] = RoleId.IMP
                elif p in m_list:
                    role_assigns[p] = claims.get(p, RoleId.POISONER)
                else:
                    role_assigns[p] = claims.get(p, RoleId.WASHERWOMAN)

            # Assign potential drunk among living or dead good
            drunk_cand = self.rng.choice(good_pool) if good_pool and self.rng.random() < 0.4 else None

            world = WorldHypothesis(
                world_id=self._next_world_id,
                demon=d,
                minions=m_list,
                good_players=good_pool,
                role_assignments=role_assigns,
                drunk_player=drunk_cand,
            )
            self._next_world_id += 1
            candidates.append(world)

        return candidates

    def score_world(
        self,
        world: WorldHypothesis,
        state: PlayerState,
        alive_roster: dict[PlayerId, bool],
        evidence_events: list[dict[str, Any]] | None = None,
    ) -> float:
        """Evaluate world score using hard rule constraints, consistency terms, and complexity penalties."""
        ev_list = evidence_events or []
        # 1. Hard Rule Consistency Check
        # Rule check: Demon cannot be in good_players, Demon must be unique
        if world.demon in world.good_players or world.demon in world.minions:
            world.score = -float("inf")
            world.rule_consistency = -float("inf")
            return -float("inf")

        if state.player_id == world.demon and state.perceived_alignment == Alignment.GOOD:
            world.score = -float("inf")
            world.rule_consistency = -float("inf")
            return -float("inf")

        rule_score = 0.0

        # 2. Claim Consistency
        claim_score = 0.0
        for p, claimed_rec in state.public_claims.items():
            true_r = world.role_assignments.get(p)
            if true_r == claimed_rec.claimed_role:
                claim_score += 0.8
            elif p in world.minions or p == world.demon:
                # Evil bluffing is expected and consistent
                claim_score += 0.5
            elif p == world.drunk_player:
                # Drunk thinks they are their claimed role
                claim_score += 0.6
            else:
                # Unprovoked false claim by good player
                claim_score -= 1.0

        # 3. Information Consistency
        info_score = 0.0
        poison_count = 0
        drunk_assumptions = 1 if world.drunk_player else 0
        registration_assumptions = len(world.registration_assumptions)

        for ev in ev_list:
            etype = ev.get("type", "")
            data = ev.get("data", {})
            actor = ev.get("actor")

            if etype == "INFO_EMPATH":
                num = data.get("number", 0)
                # Count living evil neighbors in this world
                alive_list = [p for p, a in alive_roster.items() if a]
                if actor and actor in alive_list and len(alive_list) > 2:
                    idx = alive_list.index(actor)
                    left = alive_list[(idx - 1) % len(alive_list)]
                    right = alive_list[(idx + 1) % len(alive_list)]
                    left_evil = (left == world.demon or left in world.minions)
                    right_evil = (right == world.demon or right in world.minions)
                    actual_evil = (1 if left_evil else 0) + (1 if right_evil else 0)

                    if actor == world.drunk_player:
                        info_score += 0.2  # Explained by Drunk
                    elif actual_evil == num:
                        info_score += 1.5  # Exact match
                    else:
                        # Contradiction: requires poison explanation
                        poison_count += 1
                        info_score -= 1.0

            elif etype == "INFO_FORTUNE_TELLER":
                targets = data.get("targets", [])
                res = data.get("result", False)
                has_demon = any(t == world.demon for t in targets)
                if has_demon == res:
                    info_score += 1.2
                elif actor == world.drunk_player:
                    info_score += 0.2
                else:
                    poison_count += 1
                    info_score -= 0.8

            elif etype == "INFO_INVESTIGATOR":
                pair = data.get("players", [])
                has_minion = any(p in world.minions for p in pair)
                if has_minion:
                    info_score += 1.0
                else:
                    poison_count += 1
                    info_score -= 0.8

        # 4. Social and Vote Consistency
        social_score = 0.0
        # If majority good players suspect world.demon, higher social consistency
        for p, s in state.suspicion.items():
            if p == world.demon:
                social_score += (s - 0.5) * 1.5
            elif p in world.minions:
                social_score += (s - 0.5) * 0.8

        # 5. Complexity Penalty (Poison/Drunk cannot explain everything for free)
        lambda_p = 0.6
        lambda_d = 0.5
        lambda_r = 0.4
        complexity_penalty = lambda_p * poison_count + lambda_d * drunk_assumptions + lambda_r * registration_assumptions

        total_score = rule_score + info_score + claim_score + social_score - complexity_penalty

        world.info_consistency = info_score
        world.claim_consistency = claim_score
        world.rule_consistency = rule_score
        world.social_consistency = social_score
        world.complexity_penalty = complexity_penalty
        world.score = total_score
        return total_score

    def update_and_marginalize(
        self,
        candidate_worlds: list[WorldHypothesis],
        all_players: list[PlayerId],
    ) -> tuple[dict[PlayerId, float], WorldDiversityReport]:
        """Rank candidate worlds via Softmax and compute Demon marginal probabilities."""
        valid_worlds = [w for w in candidate_worlds if not math.isinf(w.score) and w.score > -999.0]
        if not valid_worlds:
            # Fallback uniform
            uniform_prob = 1.0 / len(all_players) if all_players else 0.0
            return {p: uniform_prob for p in all_players}, WorldDiversityReport(
                total_worlds=0,
                effective_world_count=0.0,
                top1_world_prob=0.0,
                top3_world_mass=0.0,
                world_entropy_proxy=0.0,
                demon_marginals={p: uniform_prob for p in all_players},
                collapse_warning=False,
            )

        # Sort descending by score and keep Top K
        valid_worlds.sort(key=lambda w: w.score, reverse=True)
        top_k_worlds = valid_worlds[:self.k]

        # Softmax normalization: HEURISTIC WORLD POSTERIOR
        max_s = top_k_worlds[0].score
        exp_scores = [math.exp(min(20.0, max(-20.0, (w.score - max_s) / self.temperature))) for w in top_k_worlds]
        sum_exp = sum(exp_scores)
        probs = [e / sum_exp for e in exp_scores]

        for w, p in zip(top_k_worlds, probs):
            w.probability = p

        self.worlds = top_k_worlds

        # Derive Demon Marginals: P(D = j) = sum_{w: D(w) = j} P(w)
        marginals: dict[PlayerId, float] = {p: 0.0 for p in all_players}
        for w in top_k_worlds:
            if w.demon in marginals:
                marginals[w.demon] += w.probability

        # World diversity diagnostics
        entropy = -sum(p * math.log(max(1e-9, p)) for p in probs)
        eff_count = math.exp(entropy)
        top1_p = probs[0] if probs else 0.0
        top3_mass = sum(probs[:3])

        collapse_warning = (top1_p > 0.95 and eff_count < 1.5)

        report = WorldDiversityReport(
            total_worlds=len(top_k_worlds),
            effective_world_count=eff_count,
            top1_world_prob=top1_p,
            top3_world_mass=top3_mass,
            world_entropy_proxy=entropy,
            demon_marginals=marginals,
            collapse_warning=collapse_warning,
        )

        return marginals, report
