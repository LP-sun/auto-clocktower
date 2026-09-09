"""Cognitive Player agent integrating Observation, Finite Memory, Beliefs, and Policy."""
from __future__ import annotations

import random
from typing import Any

from src.belief.update import update_belief_from_event
from src.belief.world_model import WorldDiversityReport, WorldHypothesisManager
from src.cognition.observation import Observation
from src.cognition.player_state import BluffPlan, ClaimRecord, PlayerState
from src.engine.types import Alignment, CharacterType, PlayerId, RoleId
from src.player.personality import PersonalityVector, sample_personality
from src.player.policy import CognitionPolicy, DecisionTrace
from src.player.skill import SkillProfile, sample_skill_profile
from src.reasoning.evidence import (
    AtomicEvidence,
    extract_atomic_evidence_from_observation,
)
from src.reasoning.evil_reasoning import FakeWorldModel, InternalWorldModel
from src.reasoning.world import WorldReasoningTrace
from src.reasoning.world_generator import (
    WorldHypothesisManager as Phase36WorldManager,
)
from src.roles.trouble_brewing import ROLES
from src.strategies.primitives import StrategyPrimitive


class CognitivePlayer:
    """Full-cognition player agent with mathematically isolated mental state and strategic decision making."""

    def __init__(
        self,
        player_id: PlayerId,
        all_players: list[PlayerId],
        initial_role: RoleId,
        initial_alignment: Alignment,
        personality: PersonalityVector | None = None,
        skill: SkillProfile | None = None,
        seed: int | None = None,
        ablated_primitives: set[str] | None = None,
        config: Any = None,
    ) -> None:
        self.player_id = player_id
        self.all_players = list(all_players)
        self.rng = random.Random(seed)
        self.config = config
        self.personality = personality or sample_personality(self.rng, config=config)
        self.skill = skill or sample_skill_profile(self.rng, config=config)
        self.ablated_primitives = set(ablated_primitives or [])

        self.state = PlayerState.create(
            player_id=player_id,
            all_players=all_players,
            perceived_role=initial_role,
            perceived_alignment=initial_alignment,
            personality=self.personality,
            skill=self.skill,
        )
        self.policy = CognitionPolicy(self.state, rng=self.rng, ablated_primitives=self.ablated_primitives, config=config)
        self.decision_traces: list[DecisionTrace] = []
        self._processed_events_count = 0
        self._processed_deaths_count = 0
        self._processed_nominations_count = 0

        self.enable_world_model = (
            getattr(config, "enable_world_model", False)
            if config is not None
            else False
        ) or (
            isinstance(config, dict) and config.get("enable_world_model", False)
        )
        self.enable_world_reasoning = (
            getattr(config, "enable_world_reasoning", False)
            if config is not None
            else False
        ) or (
            isinstance(config, dict) and config.get("enable_world_reasoning", False)
        ) or self.enable_world_model

        self.world_model_top_k = (
            getattr(config, "world_model_top_k", 32)
            if hasattr(config, "world_model_top_k")
            else (config.get("world_model_top_k", 32) if isinstance(config, dict) else 32)
        )
        self.world_blend_weight = (
            getattr(config, "world_blend_weight", 0.4)
            if hasattr(config, "world_blend_weight")
            else (config.get("world_blend_weight", 0.4) if isinstance(config, dict) else 0.4)
        )

        # Legacy world manager
        self.world_hypothesis_manager: WorldHypothesisManager | None = None
        if self.enable_world_model and not self.enable_world_reasoning:
            self.world_hypothesis_manager = WorldHypothesisManager(
                k=self.world_model_top_k,
                temperature=1.0,
                rng=self.rng,
                config=config,
            )
        self.last_world_report: WorldDiversityReport | None = None

        # Phase 3.6 Advanced Reasoning Manager
        self.phase36_reasoning_manager: Phase36WorldManager | None = None
        if self.enable_world_reasoning:
            self.phase36_reasoning_manager = Phase36WorldManager(
                observer_id=self.player_id,
                all_players=all_players,
                k=self.world_model_top_k,
                temperature=1.0,
                epsilon_exploration=0.15,
                rng=self.rng,
                config=config,
            )

        # Dual-Model Evil Reasoning
        self.internal_evil_model: InternalWorldModel | None = None
        self.fake_evil_model: FakeWorldModel | None = None
        self.good_role_inferences: dict[PlayerId, Any] = {}
        self.current_bluff_world: Any = None

        self.atomic_evidence_history: list[AtomicEvidence] = []
        self.last_phase36_trace: WorldReasoningTrace | None = None

    def _sync_evil_reasoning_models(self, obs: Observation) -> None:
        """Initialize or update dual-model evil reasoning from legal evil knowledge."""
        if self.state.perceived_alignment != Alignment.EVIL or not obs.evil_team_knowledge:
            return
        ek = obs.evil_team_knowledge
        evil_team = [self.player_id]
        if ek.get("demon") and ek["demon"] not in evil_team:
            evil_team.append(ek["demon"])
        if ek.get("minions"):
            for m in ek["minions"]:
                if m not in evil_team:
                    evil_team.append(m)
        if ek.get("other_minions"):
            for m in ek["other_minions"]:
                if m not in evil_team:
                    evil_team.append(m)

        if not self.internal_evil_model:
            self.internal_evil_model = InternalWorldModel(self.player_id, evil_team)
        if not self.fake_evil_model:
            bluffs = ek.get("bluffs")
            self.fake_evil_model = FakeWorldModel(self.player_id, evil_team, demon_bluffs=bluffs)

        # Update genuine good role inferences
        good_players = [p for p in self.all_players if p not in evil_team]
        self.good_role_inferences = self.internal_evil_model.infer_good_roles(
            good_players=good_players,
            public_claims=self.state.public_claims,
            evidence_list=self.atomic_evidence_history,
        )
        self.current_bluff_world = self.fake_evil_model.design_bluff_world(
            observer_state=self.state,
            all_players=self.all_players,
            good_players=good_players,
        )

    def update_from_observation(self, obs: Observation, skip_world_reasoning: bool = False) -> None:
        """Ingest new observations and update beliefs and memory without information leaks."""
        # Process new private events (alpha: skill belief accuracy)
        if len(obs.private_info) > self._processed_events_count:
            for pe in obs.private_info[self._processed_events_count:]:
                update_belief_from_event(pe, self.state, alive_roster=obs.roster_alive)
            self._processed_events_count = len(obs.private_info)

        # Process new public deaths (alpha: skill belief accuracy on death evidence)
        if len(obs.deaths_public) > self._processed_deaths_count:
            for d in obs.deaths_public[self._processed_deaths_count:]:
                p_dead = d.get("player") or d.get("player_id")
                update_belief_from_event({"type": "DEATH", "target": p_dead, "data": d}, self.state)
            self._processed_deaths_count = len(obs.deaths_public)

        # Process new public nominations as social evidence (beta: personality conformity)
        if len(obs.nominations_today) > self._processed_nominations_count:
            for nom in obs.nominations_today[self._processed_nominations_count:]:
                update_belief_from_event(
                    {
                        "type": "PUBLIC_NOMINATION",
                        "target": nom.get("nominee"),
                        "data": nom,
                    },
                    self.state,
                )
            self._processed_nominations_count = len(obs.nominations_today)

        # Sync Butler master if applicable
        if obs.butler_master:
            self.state.memory.store(
                day=obs.day,
                item_type="butler_master",
                source="self",
                data={"master": obs.butler_master},
                importance=2.0,
            )

        # Ingest atomic evidence
        seen_ids = {e.evidence_id for e in self.atomic_evidence_history}
        new_evidence = extract_atomic_evidence_from_observation(
            obs=obs,
            public_claims=self.state.public_claims,
            private_claims=self.state.private_claims,
            existing_ids=seen_ids,
        )
        self.atomic_evidence_history.extend(new_evidence)

        # Sync evil dual-model if evil
        if self.state.perceived_alignment == Alignment.EVIL and (new_evidence or not self.internal_evil_model):
            self._sync_evil_reasoning_models(obs)

        # Update Phase 3.6 Reasoning if active
        if (
            not skip_world_reasoning
            and self.phase36_reasoning_manager
            and obs.day >= 2
            and self.state.perceived_alignment == Alignment.GOOD
            and (new_evidence or not self.phase36_reasoning_manager.active_worlds)
        ):
            self.update_phase36_reasoning(obs)
        elif not skip_world_reasoning and self.world_hypothesis_manager and obs.day >= 2 and (new_evidence or not self.last_world_report):
            self.update_world_model(obs)

    def update_phase36_reasoning(self, obs: Observation) -> None:
        """Run Phase 3.6 World Hypothesis generator, beam search, and marginal deduction."""
        if not self.phase36_reasoning_manager:
            return

        candidates = self.phase36_reasoning_manager.generate_candidate_worlds(
            observer_state=self.state,
            alive_roster=obs.roster_alive,
            evidence_list=self.atomic_evidence_history,
        )
        marginals, trace = self.phase36_reasoning_manager.update_and_prune(
            new_candidates=candidates,
            evidence_list=self.atomic_evidence_history,
            observer_state=self.state,
            alive_roster=obs.roster_alive,
        )
        self.last_phase36_trace = trace

        # Blend Demon marginals into belief state
        lam = self.world_blend_weight
        for p, d_prob in marginals.items():
            if p in self.state.beliefs:
                old_d = self.state.beliefs[p].demon
                new_d = (1.0 - lam) * old_d + lam * d_prob
                self.state.beliefs[p].demon = max(0.01, min(0.99, new_d))
                if self.state.beliefs[p].demon > self.state.beliefs[p].evil:
                    self.state.beliefs[p].evil = min(0.99, self.state.beliefs[p].demon + 0.05)

    def update_world_model(self, obs: Observation) -> None:
        """Legacy world hypothesis model update."""
        if not self.world_hypothesis_manager or self.state.perceived_alignment != Alignment.GOOD:
            return

        claims = {p: rec.claimed_role for p, rec in self.state.public_claims.items()}
        candidates = self.world_hypothesis_manager.generate_candidate_worlds(
            observer_id=self.player_id,
            all_players=self.all_players,
            claims=claims,
            alive_roster=obs.roster_alive,
            perceived_role=self.state.perceived_role,
            perceived_alignment=self.state.perceived_alignment,
        )
        for w in candidates:
            self.world_hypothesis_manager.score_world(w, self.state, obs.roster_alive)

        marginals, report = self.world_hypothesis_manager.update_and_marginalize(
            candidates, self.all_players
        )
        self.last_world_report = report

        lam = self.world_blend_weight
        for p, d_prob in marginals.items():
            if p in self.state.beliefs:
                old_d = self.state.beliefs[p].demon
                new_d = (1.0 - lam) * old_d + lam * d_prob
                self.state.beliefs[p].demon = max(0.01, min(0.99, new_d))
                if self.state.beliefs[p].demon > self.state.beliefs[p].evil:
                    self.state.beliefs[p].evil = min(0.99, self.state.beliefs[p].demon + 0.05)

    def decide_nomination(self, obs: Observation) -> PlayerId | None:
        """Evaluate nomination utility via cognitive policy."""
        self.update_from_observation(obs)
        nominee, trace = self.policy.score_nomination_detailed(obs)
        if trace:
            self.decision_traces.append(trace)
        return nominee

    def decide_vote(self, obs: Observation) -> bool:
        """Evaluate vote utility via cognitive policy."""
        self.update_from_observation(obs, skip_world_reasoning=True)
        vote_yes, trace = self.policy.score_vote_detailed(obs)
        if trace:
            self.decision_traces.append(trace)
        return vote_yes

    def decide_slayer_shot(self, obs: Observation) -> PlayerId | None:
        """Decide whether to fire Slayer shot based on Demon probability threshold."""
        self.update_from_observation(obs)
        if not obs.alive or obs.self_role != RoleId.SLAYER:
            return None

        alive_others = [p for p, alive in obs.roster_alive.items() if alive and p != self.player_id]
        if not alive_others:
            return None

        # Sort by demon suspicion
        candidates_by_demon = sorted(
            alive_others,
            key=lambda p: self.state.beliefs.get(p).demon if self.state.beliefs.get(p) else 0.0,
            reverse=True,
        )
        best_target = candidates_by_demon[0]
        best_demon_prob = self.state.beliefs.get(best_target).demon if self.state.beliefs.get(best_target) else 0.1

        # Slayer fires if demon suspicion exceeds risk threshold (modulated by personality)
        threshold = 0.45 - (self.personality.risk_tolerance - 0.5) * 0.2
        if best_demon_prob >= threshold or (obs.day >= 3 and self.rng.random() < 0.4):
            return best_target
        return None

    def choose_whisper_target(self, obs: Observation) -> PlayerId | None:
        """Choose a private whisper partner based on strategic primitives, world disambiguation, and cognitive state."""
        self.update_from_observation(obs)
        alive_others = [p for p, alive in obs.roster_alive.items() if alive and p != self.player_id]
        if not alive_others:
            return None

        # 1. Evil coordination primitive
        if self.state.perceived_alignment == Alignment.EVIL:
            if StrategyPrimitive.EVIL_COORDINATION.value not in self.ablated_primitives:
                if obs.evil_team_knowledge:
                    ek = obs.evil_team_knowledge
                    evil_partners = []
                    if "minions" in ek:
                        evil_partners.extend(ek["minions"])
                    if ek.get("demon"):
                        evil_partners.append(ek["demon"])
                    if "other_minions" in ek:
                        evil_partners.extend(ek["other_minions"])
                    alive_evil = [p for p in evil_partners if p in alive_others]
                    if alive_evil and self.rng.random() < 0.8:
                        return self.rng.choice(alive_evil)

        # 2. Phase 3.6 World Disambiguation Value (Good player prioritizing players that separate top worlds)
        if (
            self.state.perceived_alignment == Alignment.GOOD
            and self.phase36_reasoning_manager
            and self.phase36_reasoning_manager.active_worlds
        ):
            top_worlds = self.phase36_reasoning_manager.active_worlds[:4]
            best_disambig_p = None
            max_entropy_slots = 0
            for p in alive_others:
                distinct_assignments = {w.get_assigned_role(p) for w in top_worlds}
                if len(distinct_assignments) > max_entropy_slots:
                    max_entropy_slots = len(distinct_assignments)
                    best_disambig_p = p
            if best_disambig_p and max_entropy_slots > 1 and self.rng.random() < 0.65:
                return best_disambig_p

        # 3. Seek complementary info primitive (Townsfolk info roles)
        if self.state.perceived_alignment == Alignment.GOOD:
            if StrategyPrimitive.SEEK_COMPLEMENTARY_INFO.value not in self.ablated_primitives:
                info_roles = {
                    RoleId.WASHERWOMAN, RoleId.LIBRARIAN, RoleId.INVESTIGATOR,
                    RoleId.CHEF, RoleId.EMPATH, RoleId.FORTUNE_TELLER, RoleId.UNDERTAKER,
                }
                if self.state.perceived_role in info_roles:
                    # Prefer whispering living players who might have complementary info or neighbors
                    claimed_info = [
                        p for p in alive_others
                        if self.state.public_claims.get(p)
                        and self.state.public_claims[p].claimed_role in info_roles
                    ]
                    if claimed_info and self.rng.random() < 0.7:
                        return self.rng.choice(claimed_info)

                    # Prefer neighbors for Empath/Chef validation
                    all_p = list(obs.roster_alive.keys())
                    if self.player_id in all_p:
                        idx = all_p.index(self.player_id)
                        neighbors = [all_p[(idx - 1) % len(all_p)], all_p[(idx + 1) % len(all_p)]]
                        alive_neighbors = [n for n in neighbors if n in alive_others]
                        if alive_neighbors and self.rng.random() < 0.6:
                            return self.rng.choice(alive_neighbors)

        # Fallback: choose by highest trust or random
        trusted_alive = sorted(
            alive_others,
            key=lambda p: self.state.trust.get(p, 0.0),
            reverse=True,
        )
        if trusted_alive and self.rng.random() < 0.6:
            return trusted_alive[0]
        return self.rng.choice(alive_others)

    def decide_whisper_claim(self, partner_id: PlayerId, obs: Observation) -> RoleId | None:
        """Decide whether to disclose a claim in private whisper based on PRIVATE_CLAIM primitive."""
        if StrategyPrimitive.PRIVATE_CLAIM.value in self.ablated_primitives:
            return None

        # Evil player bluffing
        if self.state.perceived_alignment == Alignment.EVIL and self.fake_evil_model and self.fake_evil_model.active_bluff_plan:
            return self.fake_evil_model.active_bluff_plan.bluff_role

        # Disclosure guided by openness and early days
        trust = self.state.trust.get(partner_id, 0.0)
        threshold = 0.3 - (self.personality.openness - 0.5) * 0.3
        if trust >= threshold or obs.day <= 2:
            return self.state.perceived_role
        return None

    def choose_night_target(self, obs: Observation, action_type: str) -> Any:
        """Choose night target based on role-specific strategic primitives and evil inference."""
        self.update_from_observation(obs)
        all_players = list(obs.roster_alive.keys())
        alive_players = [p for p, alive in obs.roster_alive.items() if alive]
        others_alive = [p for p in alive_players if p != self.player_id]

        if action_type == "poisoner":
            # Target high-threat Good roles inferred by InternalWorldModel if available
            if self.internal_evil_model and self.good_role_inferences:
                rec = self.internal_evil_model.recommend_kill_target(others_alive, self.good_role_inferences)
                if rec and self.rng.random() < 0.8:
                    return rec

            # Fallback: Target claimed info roles
            info_targets = [
                p for p in alive_players
                if p != self.player_id
                and self.state.public_claims.get(p)
                and self.state.public_claims[p].claimed_role in (
                    RoleId.EMPATH, RoleId.FORTUNE_TELLER, RoleId.UNDERTAKER, RoleId.VIRGIN, RoleId.SLAYER
                )
            ]
            if info_targets and self.rng.random() < 0.75:
                return self.rng.choice(info_targets)
            return self.rng.choice(alive_players) if alive_players else None

        if action_type == "monk":
            # Protect high-value role: prioritize claimed Empath, FT, Undertaker
            if StrategyPrimitive.PROTECT_HIGH_VALUE_ROLE.value not in self.ablated_primitives:
                claimed_info = [
                    p for p in others_alive
                    if self.state.public_claims.get(p)
                    and self.state.public_claims[p].claimed_role in (
                        RoleId.EMPATH, RoleId.FORTUNE_TELLER, RoleId.UNDERTAKER
                    )
                ]
                if claimed_info and self.rng.random() < 0.8:
                    return self.rng.choice(claimed_info)

            # Otherwise protect highest trusted living player or random
            trusted_alive = sorted(
                others_alive,
                key=lambda p: self.state.trust.get(p, 0.0),
                reverse=True,
            )
            return trusted_alive[0] if trusted_alive else (self.rng.choice(others_alive) if others_alive else None)

        if action_type == "imp":
            # Star pass evaluation: if under heavy suspicion and living minion exists
            if self.personality.risk_tolerance > 0.6:
                my_suspicion = self.state.suspicion.get(self.player_id, 0.0)
                if my_suspicion > 0.8 and len(alive_players) >= 5 and self.rng.random() < 0.2:
                    return self.player_id  # Star pass!

            # Target high-threat Good roles recommended by InternalWorldModel (Monk, Slayer, FT, Empath)
            if self.internal_evil_model and self.good_role_inferences:
                rec = self.internal_evil_model.recommend_kill_target(others_alive, self.good_role_inferences)
                if rec and self.rng.random() < 0.85:
                    return rec

            # Fallback: Kill info role: prioritize eliminating public info roles
            if StrategyPrimitive.KILL_INFO_ROLE.value not in self.ablated_primitives:
                claimed_info = [
                    p for p in others_alive
                    if self.state.public_claims.get(p)
                    and self.state.public_claims[p].claimed_role in (
                        RoleId.EMPATH, RoleId.FORTUNE_TELLER, RoleId.UNDERTAKER, RoleId.VIRGIN, RoleId.SLAYER
                    )
                ]
                if claimed_info and self.rng.random() < 0.85:
                    return self.rng.choice(claimed_info)

            # Otherwise eliminate highest-trusted good player
            return self.rng.choice(others_alive) if others_alive else self.player_id

        if action_type == "fortune_teller":
            # Choose highest demon suspect + second candidate
            sorted_suspects = sorted(
                all_players,
                key=lambda p: self.state.beliefs.get(p).demon if self.state.beliefs.get(p) else 0.0,
                reverse=True,
            )
            target1 = sorted_suspects[0] if sorted_suspects else self.player_id
            pool = [p for p in all_players if p != target1]
            target2 = self.rng.choice(pool) if pool else target1
            return (target1, target2)

        if action_type == "butler":
            # Pick highest trusted player as master
            trusted = sorted(
                [p for p in all_players if p != self.player_id],
                key=lambda p: self.state.trust.get(p, 0.0),
                reverse=True,
            )
            return trusted[0] if trusted else self.rng.choice([p for p in all_players if p != self.player_id])

        if action_type == "ravenkeeper":
            # Inspect highest suspicion player
            sorted_suspects = sorted(
                all_players,
                key=lambda p: self.state.beliefs.get(p).evil if self.state.beliefs.get(p) else 0.0,
                reverse=True,
            )
            return sorted_suspects[0] if sorted_suspects else self.player_id

        return None
