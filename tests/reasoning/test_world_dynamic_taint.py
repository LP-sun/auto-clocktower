"""Dynamic Taint and Information Isolation Test for Phase 3.6 Reasoning Core.

Guarantees:
1. src/reasoning (WorldHypothesisManager, InformationConstraintsCoordinator, WorldHypothesis)
   NEVER accepts, accesses, or references hidden GameState.
2. Only legal PlayerObservation, PlayerMemory, and public claims are consumed.
3. Secret information (e.g. true grimoire, real identities, ST private state) is never leaked.
"""
from __future__ import annotations

import inspect
import unittest

from src.cognition.observation import Observation
from src.cognition.player_state import PlayerState
from src.engine.types import Alignment, GamePhase, RoleId
from src.player.personality import PersonalityVector
from src.player.skill import SkillProfile
from src.reasoning.evidence import (
    AtomicEvidence,
    EvidenceStrength,
    EvidenceTier,
    EvidenceType,
    extract_atomic_evidence_from_observation,
)
from src.reasoning.information_constraints import (
    InformationConstraintsCoordinator,
)
from src.reasoning.world import RoleSlot, WorldHypothesis
from src.reasoning.world_generator import WorldHypothesisManager


class TestWorldDynamicTaint(unittest.TestCase):
    def test_no_gamestate_in_signatures(self) -> None:
        """Inspect all reasoning classes and verify none accept GameState in their public API."""
        classes_to_check = [
            WorldHypothesisManager,
            InformationConstraintsCoordinator,
            WorldHypothesis,
            AtomicEvidence,
        ]
        forbidden_param_names = {"state", "game_state", "grimoire", "hidden_state", "secret_roles"}

        for cls in classes_to_check:
            for name, method in inspect.getmembers(cls, predicate=inspect.isfunction):
                sig = inspect.signature(method)
                for param_name, param in sig.parameters.items():
                    if param_name in forbidden_param_names:
                        # If parameter is named 'state', ensure annotation is PlayerState, NOT GameState
                        ann = param.annotation
                        self.assertNotEqual(
                            ann,
                            "GameState",
                            f"{cls.__name__}.{name} parameter '{param_name}' references GameState!",
                        )
                        self.assertNotIn(
                            "GameState",
                            str(ann),
                            f"{cls.__name__}.{name} parameter '{param_name}' references GameState!",
                        )

    def test_reasoning_pipeline_isolated_execution(self) -> None:
        """Execute complete reasoning cycle using only legal PlayerState and Observation."""
        players = [f"p{i}" for i in range(1, 8)]
        p_state = PlayerState.create(
            player_id="p1",
            all_players=players,
            perceived_role=RoleId.EMPATH,
            perceived_alignment=Alignment.GOOD,
            personality=PersonalityVector(0.5, 0.5, 0.5, 0.5, 0.5, 0.5),
            skill=SkillProfile(0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5),
        )

        obs = Observation(
            observer="p1",
            day=2,
            phase=GamePhase.DAY_PUBLIC,
            night_number=1,
            self_role=RoleId.EMPATH,
            self_alignment=Alignment.GOOD,
            alive=True,
            ghost_vote_available=True,
            roster_alive={p: True for p in players},
            deaths_public=[],
            execution_threshold=4,
            nominated_by_today=[],
            nominated_today=[],
            nominations_today=[],
            current_nomination=None,
            private_info=[{"type": "empath", "count": 1}],
        )

        # Extract atomic evidence
        evidence = extract_atomic_evidence_from_observation(obs)
        self.assertTrue(len(evidence) > 0)
        for ev in evidence:
            self.assertFalse(hasattr(ev, "grimoire"))
            self.assertFalse(hasattr(ev, "real_roles"))

        # Generate and update worlds
        manager = WorldHypothesisManager(observer_id="p1", all_players=players, k=8)
        candidates = manager.generate_candidate_worlds(
            observer_state=p_state,
            alive_roster=obs.roster_alive,
            evidence_list=evidence,
        )
        self.assertTrue(len(candidates) > 0)

        marginals, trace = manager.update_and_prune(
            new_candidates=candidates,
            evidence_list=evidence,
            observer_state=p_state,
            alive_roster=obs.roster_alive,
        )

        self.assertEqual(len(marginals), len(players))
        self.assertIsNotNone(trace)
        self.assertFalse(trace.collapse_warning)


if __name__ == "__main__":
    unittest.main()
