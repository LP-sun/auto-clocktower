"""Adversarial Dynamic Taint Tests.

Verifies the mathematical boundary: True Game State vs. Player Observation vs. Player Cognition.

Requirement 6:
Dynamic taint test compares not just chosen_action, but the ENTIRE cognitive pipeline:
- legal_actions
- applicable_primitives
- candidate_scores
- utility_components
- softmax_probabilities
- chosen_action

When Observation, Cognition, and RNG are identical, two diametrically different
ground-truth universes MUST yield bit-for-bit identical decision traces.
"""
import copy
import random
import unittest

from src.cognition.observation import observe
from src.cognition.player_state import PlayerState
from src.engine.game import ClocktowerEngine
from src.engine.types import Alignment, RoleId, SkillLevel
from src.player.personality import sample_personality
from src.player.policy import CognitionPolicy, DecisionTrace
from src.player.skill import sample_skill
from tests.test_engine_rules import make_custom_setup


class TestDynamicTaint(unittest.TestCase):
    def test_deep_chain_taint_nomination_different_ground_truth(self):
        """Two worlds with different Demons/Minions but identical P01 Observation yield bit-for-bit identical traces."""
        # World A: Demon is P04 (Imp), Minion is P03 (Poisoner), P02 is Empath
        setup_a = make_custom_setup([RoleId.CHEF, RoleId.EMPATH, RoleId.POISONER, RoleId.IMP])
        engine_a = ClocktowerEngine.create(custom_setup=setup_a)
        engine_a.run_first_night()
        engine_a.start_day()

        # World B: Demon is P02 (Imp), Minion is P04 (Baron), P03 is Empath
        setup_b = make_custom_setup([RoleId.CHEF, RoleId.IMP, RoleId.EMPATH, RoleId.BARON])
        engine_b = ClocktowerEngine.create(custom_setup=setup_b)
        engine_b.run_first_night()
        engine_b.start_day()

        # Generate Observations for P01 in both worlds
        obs_a = observe(engine_a.state, "P01")
        obs_b = observe(engine_b.state, "P01")
        obs_b.private_info = copy.deepcopy(obs_a.private_info)

        # Build identical Cognition state for P01
        personality = sample_personality(seed=101)
        skill = sample_skill(level=SkillLevel.EXPERIENCED, seed=101)

        state_a = PlayerState.create(
            player_id="P01",
            all_players=["P01", "P02", "P03", "P04"],
            perceived_role=RoleId.CHEF,
            perceived_alignment=Alignment.GOOD,
            personality=personality,
            skill=skill,
        )
        state_b = PlayerState.create(
            player_id="P01",
            all_players=["P01", "P02", "P03", "P04"],
            perceived_role=RoleId.CHEF,
            perceived_alignment=Alignment.GOOD,
            personality=copy.deepcopy(personality),
            skill=copy.deepcopy(skill),
        )

        policy_a = CognitionPolicy(state_a, rng=random.Random(999))
        policy_b = CognitionPolicy(state_b, rng=random.Random(999))

        nom_a, trace_a = policy_a.score_nomination_detailed(obs_a)
        nom_b, trace_b = policy_b.score_nomination_detailed(obs_b)

        self.assertIsNotNone(trace_a)
        self.assertIsNotNone(trace_b)

        # 1. Legal actions must be identical
        self.assertEqual(trace_a.legal_actions, trace_b.legal_actions)

        # 2. Applicable primitives must be identical
        self.assertEqual(trace_a.applicable_primitives, trace_b.applicable_primitives)

        # 3. Candidate scores must be identical
        self.assertEqual(trace_a.candidate_scores, trace_b.candidate_scores)

        # 4. Utility components must be identical
        self.assertEqual(trace_a.utility_components, trace_b.utility_components)

        # 5. Softmax probabilities must be identical
        self.assertEqual(trace_a.softmax_probabilities, trace_b.softmax_probabilities)

        # 6. Chosen action must be identical
        self.assertEqual(trace_a.chosen_action, trace_b.chosen_action)
        self.assertEqual(nom_a, nom_b)

    def test_deep_chain_taint_voting_different_ground_truth(self):
        """Voting decision traces are bit-for-bit identical across different secret worlds."""
        # World A: P02 is Empath (Good)
        setup_a = make_custom_setup([RoleId.CHEF, RoleId.EMPATH, RoleId.POISONER, RoleId.IMP])
        engine_a = ClocktowerEngine.create(custom_setup=setup_a)
        engine_a.run_first_night()
        engine_a.start_day()
        engine_a.handle_nomination("P01", "P02")

        # World B: P02 is Imp (Evil Demon!)
        setup_b = make_custom_setup([RoleId.CHEF, RoleId.IMP, RoleId.EMPATH, RoleId.BARON])
        engine_b = ClocktowerEngine.create(custom_setup=setup_b)
        engine_b.run_first_night()
        engine_b.start_day()
        engine_b.handle_nomination("P01", "P02")

        obs_a = observe(engine_a.state, "P01")
        obs_b = observe(engine_b.state, "P01")
        obs_b.private_info = copy.deepcopy(obs_a.private_info)

        personality = sample_personality(seed=202)
        skill = sample_skill(level=SkillLevel.INTERMEDIATE, seed=202)

        state_a = PlayerState.create(
            player_id="P01",
            all_players=["P01", "P02", "P03", "P04"],
            perceived_role=RoleId.CHEF,
            perceived_alignment=Alignment.GOOD,
            personality=personality,
            skill=skill,
        )
        state_b = PlayerState.create(
            player_id="P01",
            all_players=["P01", "P02", "P03", "P04"],
            perceived_role=RoleId.CHEF,
            perceived_alignment=Alignment.GOOD,
            personality=copy.deepcopy(personality),
            skill=copy.deepcopy(skill),
        )

        policy_a = CognitionPolicy(state_a, rng=random.Random(888))
        policy_b = CognitionPolicy(state_b, rng=random.Random(888))

        vote_a, trace_a = policy_a.score_vote_detailed(obs_a)
        vote_b, trace_b = policy_b.score_vote_detailed(obs_b)

        self.assertIsNotNone(trace_a)
        self.assertIsNotNone(trace_b)

        # Deep verification across all 6 layers
        self.assertEqual(trace_a.legal_actions, trace_b.legal_actions)
        self.assertEqual(trace_a.applicable_primitives, trace_b.applicable_primitives)
        self.assertEqual(trace_a.candidate_scores, trace_b.candidate_scores)
        self.assertEqual(trace_a.utility_components, trace_b.utility_components)
        self.assertEqual(trace_a.softmax_probabilities, trace_b.softmax_probabilities)
        self.assertEqual(trace_a.chosen_action, trace_b.chosen_action)
        self.assertEqual(vote_a, vote_b)

    def test_drunk_player_isolation_no_taint(self):
        """Drunk believing Washerwoman has exact same decision trace as true Washerwoman given same obs."""
        # World A: True Washerwoman
        setup_a = make_custom_setup([RoleId.WASHERWOMAN, RoleId.CHEF, RoleId.POISONER, RoleId.IMP])
        engine_a = ClocktowerEngine.create(custom_setup=setup_a)
        engine_a.run_first_night()
        engine_a.start_day()

        # World B: True Drunk (fake role Washerwoman)
        setup_b = make_custom_setup([RoleId.DRUNK, RoleId.CHEF, RoleId.POISONER, RoleId.IMP], fake_drunk=RoleId.WASHERWOMAN)
        engine_b = ClocktowerEngine.create(custom_setup=setup_b)
        engine_b.run_first_night()
        engine_b.start_day()

        obs_a = observe(engine_a.state, "P01")
        obs_b = observe(engine_b.state, "P01")
        obs_b.private_info = copy.deepcopy(obs_a.private_info)

        personality = sample_personality(seed=303)
        skill = sample_skill(level=SkillLevel.EXPERIENCED, seed=303)

        state_a = PlayerState.create(
            player_id="P01",
            all_players=["P01", "P02", "P03", "P04"],
            perceived_role=RoleId.WASHERWOMAN,
            perceived_alignment=Alignment.GOOD,
            personality=personality,
            skill=skill,
        )
        state_b = PlayerState.create(
            player_id="P01",
            all_players=["P01", "P02", "P03", "P04"],
            perceived_role=RoleId.WASHERWOMAN,
            perceived_alignment=Alignment.GOOD,
            personality=copy.deepcopy(personality),
            skill=copy.deepcopy(skill),
        )

        policy_a = CognitionPolicy(state_a, rng=random.Random(777))
        policy_b = CognitionPolicy(state_b, rng=random.Random(777))

        nom_a, trace_a = policy_a.score_nomination_detailed(obs_a)
        nom_b, trace_b = policy_b.score_nomination_detailed(obs_b)

        self.assertEqual(trace_a.legal_actions, trace_b.legal_actions)
        self.assertEqual(trace_a.applicable_primitives, trace_b.applicable_primitives)
        self.assertEqual(trace_a.candidate_scores, trace_b.candidate_scores)
        self.assertEqual(trace_a.utility_components, trace_b.utility_components)
        self.assertEqual(trace_a.softmax_probabilities, trace_b.softmax_probabilities)
        self.assertEqual(trace_a.chosen_action, trace_b.chosen_action)


if __name__ == "__main__":
    unittest.main()
