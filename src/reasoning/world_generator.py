"""World Hypothesis Generator, Epsilon-Exploration Beam Search, and Evolutionary Tracking."""
from __future__ import annotations

import math
import random
from typing import Any

from src.cognition.player_state import PlayerState
from src.engine.types import Alignment, CharacterType, PlayerId, RoleId
from src.reasoning.constraints.setup_constraints import TB_COMPOSITION
from src.reasoning.evidence import AtomicEvidence
from src.reasoning.information_constraints import InformationConstraintsCoordinator
from src.reasoning.world import (
    RoleSlot,
    SlotState,
    WorldHypothesis,
    WorldLineageRecord,
    WorldReasoningTrace,
)


class WorldHypothesisManager:
    """Manages generation, beam search, lineage tracking, and marginal deduction for subjective worlds."""

    def __init__(
        self,
        observer_id: PlayerId,
        all_players: list[PlayerId],
        k: int = 32,
        temperature: float = 1.0,
        epsilon_exploration: float = 0.15,
        rng: random.Random | None = None,
        config: Any = None,
    ) -> None:
        self.observer_id = observer_id
        self.all_players = all_players
        self.k = k
        self.temperature = max(0.1, temperature)
        self.epsilon_exploration = epsilon_exploration
        self.rng = rng or random.Random()
        self.config = config

        self.coordinator = InformationConstraintsCoordinator()
        self.active_worlds: list[WorldHypothesis] = []
        self.archived_worlds: list[WorldHypothesis] = []
        self.lineage_records: list[WorldLineageRecord] = []
        self.last_trace: WorldReasoningTrace | None = None
        self._next_world_id = 1

    def generate_candidate_worlds(
        self,
        observer_state: PlayerState,
        alive_roster: dict[PlayerId, bool],
        evidence_list: list[AtomicEvidence],
        demon_proposals: list[PlayerId] | None = None,
    ) -> list[WorldHypothesis]:
        """Generate stochastic, bounded candidate worlds using proposal heuristics and exploration quota."""
        n_players = len(self.all_players)
        base_tf, base_out, base_min, base_dem = TB_COMPOSITION.get(n_players, (7, 2, 2, 1))

        # 1. Propose Demon candidates with epsilon-exploration
        alive_candidates = [p for p in self.all_players if p != self.observer_id or observer_state.perceived_alignment == Alignment.EVIL]
        if not alive_candidates:
            alive_candidates = list(self.all_players)

        # Rank by local suspicion
        suspects_ranked = sorted(
            alive_candidates,
            key=lambda p: observer_state.suspicion.get(p, 0.5),
            reverse=True,
        )

        top_suspects = suspects_ranked[:max(3, len(suspects_ranked) // 2)]
        proposals: list[PlayerId] = []

        # Allocate slots: (1 - eps) to top suspects, eps to exploration
        num_demons_to_sample = min(6, len(alive_candidates))
        for _ in range(num_demons_to_sample):
            if self.rng.random() < self.epsilon_exploration:
                # Epsilon exploration quota: sample outside top suspects or uniform
                cand = self.rng.choice(alive_candidates)
            else:
                cand = self.rng.choice(top_suspects)
            if cand not in proposals:
                proposals.append(cand)

        # Include caller-provided demon proposals if specified
        if demon_proposals:
            for dp in demon_proposals:
                if dp in alive_candidates and dp not in proposals:
                    proposals.insert(0, dp)

        candidates: list[WorldHypothesis] = []

        # 2. Build partial worlds for each Demon proposal
        for d in proposals:
            # Propose Minions
            other_players = [p for p in self.all_players if p != d]
            if observer_state.perceived_alignment == Alignment.GOOD and self.observer_id in other_players:
                other_players.remove(self.observer_id)

            minion_ranked = sorted(
                other_players,
                key=lambda p: observer_state.suspicion.get(p, 0.3),
                reverse=True,
            )
            top_minion_pool = minion_ranked[:max(base_min * 2, len(minion_ranked) // 2)]

            # Generate 2-4 minion combinations per demon
            for _ in range(3):
                m_list = self.rng.sample(top_minion_pool, min(base_min, len(top_minion_pool)))
                good_pool = [p for p in self.all_players if p != d and p not in m_list]

                # Assign Partial Role Slots
                slots: dict[PlayerId, RoleSlot] = {}
                alignments: dict[PlayerId, Alignment] = {}

                # Demon
                slots[d] = RoleSlot.make_known(RoleId.IMP)
                alignments[d] = Alignment.EVIL

                # Minions
                minion_role_pool = [RoleId.POISONER, RoleId.SPY, RoleId.BARON, RoleId.SCARLET_WOMAN]
                for idx, m in enumerate(m_list):
                    alignments[m] = Alignment.EVIL
                    # If minion publicly claimed a role, they might be bluffing that role
                    c_rec = observer_state.public_claims.get(m)
                    if c_rec and self.rng.random() < 0.5:
                        slots[m] = RoleSlot.make_candidates(minion_role_pool)
                    else:
                        slots[m] = RoleSlot.make_known(minion_role_pool[idx % len(minion_role_pool)])

                # Observer own perceived role
                slots[self.observer_id] = RoleSlot.make_known(observer_state.perceived_role)
                alignments[self.observer_id] = observer_state.perceived_alignment

                # Good players
                for g in good_pool:
                    alignments[g] = Alignment.GOOD
                    if g == self.observer_id:
                        continue
                    c_rec = observer_state.public_claims.get(g)
                    if c_rec and hasattr(c_rec, "claimed_role"):
                        # Use claimed role as known or candidate
                        slots[g] = RoleSlot.make_known(c_rec.claimed_role)
                    else:
                        slots[g] = RoleSlot.make_unknown()

                # Drunk candidate assignment
                drunk_cand = self.rng.choice(good_pool) if good_pool and self.rng.random() < 0.35 else None

                world = WorldHypothesis(
                    world_id=self._next_world_id,
                    demon_player=d,
                    minion_players=m_list,
                    good_players=good_pool,
                    slots=slots,
                    alignments=alignments,
                    created_day=getattr(observer_state, "day", 1),
                    drunk_player=drunk_cand,
                )
                self._next_world_id += 1
                candidates.append(world)

        return candidates

    def update_and_prune(
        self,
        new_candidates: list[WorldHypothesis],
        evidence_list: list[AtomicEvidence],
        observer_state: PlayerState,
        alive_roster: dict[PlayerId, bool],
        living_players_by_day: dict[int, list[PlayerId]] | None = None,
    ) -> tuple[dict[PlayerId, float], WorldReasoningTrace]:
        """Rescore active and new worlds, prune uncompetitive ones, and calculate marginals."""
        # 1. Pool active worlds, archived worlds (for possible resurrection), and new candidates
        all_to_evaluate = list(self.active_worlds) + new_candidates
        # Try resurrecting up to 4 archived worlds
        if self.archived_worlds:
            sample_archived = self.rng.sample(self.archived_worlds, min(4, len(self.archived_worlds)))
            all_to_evaluate.extend(sample_archived)

        # 2. Score every world
        valid_scored: list[WorldHypothesis] = []
        for w in all_to_evaluate:
            score = self.coordinator.evaluate_world(
                world=w,
                evidence_list=evidence_list,
                observer_state=observer_state,
                alive_roster=alive_roster,
                living_players_by_day=living_players_by_day,
            )
            if not math.isinf(score) and score > -999.0:
                valid_scored.append(w)
            else:
                self.lineage_records.append(
                    WorldLineageRecord(
                        world_id=w.world_id,
                        parent_world_id=w.parent_world_id,
                        created_day=w.created_day,
                        removed_day=getattr(observer_state, "day", 1),
                        removal_reason="RULE_CONTRADICTION",
                    )
                )

        if not valid_scored:
            # Fallback: keep top previous or uniform
            uniform = 1.0 / len(self.all_players) if self.all_players else 0.0
            marginals = {p: uniform for p in self.all_players}
            trace = WorldReasoningTrace(
                player_id=self.observer_id,
                day=getattr(observer_state, "day", 1),
                phase="day",
                input_evidence_count=len(evidence_list),
                candidate_world_count=len(all_to_evaluate),
                pruned_world_count=len(all_to_evaluate),
                top_worlds=[],
                demon_marginals=marginals,
                minion_marginals={p: 0.0 for p in self.all_players},
                effective_world_count=1.0,
                top1_world_mass=1.0,
                world_entropy=0.0,
                collapse_warning=False,
                underconstrained_warning=True,
            )
            self.last_trace = trace
            return marginals, trace

        # 3. Sort descending by score and keep Top K
        valid_scored.sort(key=lambda w: w.total_score, reverse=True)
        top_k = valid_scored[:self.k]
        pruned = valid_scored[self.k:]

        # Archive pruned worlds for possible future resurrection
        self.archived_worlds = (self.archived_worlds + pruned)[-64:]
        for pw in pruned:
            self.lineage_records.append(
                WorldLineageRecord(
                    world_id=pw.world_id,
                    parent_world_id=pw.parent_world_id,
                    created_day=pw.created_day,
                    removed_day=getattr(observer_state, "day", 1),
                    removal_reason="SEARCH_CAPACITY",
                )
            )

        # 4. Softmax normalization: HEURISTIC WORLD DISTRIBUTION
        max_s = top_k[0].total_score
        t = self.temperature
        exp_scores = [math.exp(min(20.0, max(-20.0, (w.total_score - max_s) / t))) for w in top_k]
        sum_exp = sum(exp_scores)
        probs = [e / sum_exp for e in exp_scores]

        for w, p in zip(top_k, probs):
            w.probability = p

        self.active_worlds = top_k

        # 5. Deduce Demon and Minion marginals: P(Demon = j) = sum_{W: D(W)=j} P(W)
        demon_marginals: dict[PlayerId, float] = {p: 0.0 for p in self.all_players}
        minion_marginals: dict[PlayerId, float] = {p: 0.0 for p in self.all_players}

        for w in top_k:
            if w.demon_player in demon_marginals:
                demon_marginals[w.demon_player] += w.probability
            for m in w.minion_players:
                if m in minion_marginals:
                    minion_marginals[m] += w.probability

        # 6. Diagnostics
        entropy = -sum(p * math.log(max(1e-9, p)) for p in probs)
        eff_count = math.exp(entropy)
        top1_mass = probs[0] if probs else 0.0
        collapse_warn = (top1_mass > 0.95 and eff_count < 1.5)
        underconstrained_warn = (len([p for p, a in alive_roster.items() if a]) <= 4 and eff_count > (self.k * 0.75))

        trace = WorldReasoningTrace(
            player_id=self.observer_id,
            day=getattr(observer_state, "day", 1),
            phase="day",
            input_evidence_count=len(evidence_list),
            candidate_world_count=len(all_to_evaluate),
            pruned_world_count=len(pruned),
            top_worlds=[w.to_dict() for w in top_k[:5]],
            demon_marginals=demon_marginals,
            minion_marginals=minion_marginals,
            effective_world_count=eff_count,
            top1_world_mass=top1_mass,
            world_entropy=entropy,
            collapse_warning=collapse_warn,
            underconstrained_warning=underconstrained_warn,
        )
        self.last_trace = trace
        return demon_marginals, trace

    def assume_condition(
        self,
        demon: PlayerId | None = None,
        minion: PlayerId | None = None,
    ) -> list[WorldHypothesis]:
        """Query conditioned plausible worlds (e.g. 'If P7 is Demon, what else must be true?')."""
        return [
            w for w in self.active_worlds
            if w.condition(demon=demon, minion=minion)
        ]
