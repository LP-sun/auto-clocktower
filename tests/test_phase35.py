"""Unit tests verifying Phase 3.5 Mechanism Corrections and Diagnostics."""
import unittest

from src.belief.belief_model import BeliefVector, ScoreBelief
from src.belief.update import update_belief_from_event
from src.calibration.alignment import compute_alignment_and_quadrants
from src.calibration.friendly_fire import FriendlyFireCause, analyze_friendly_fire
from src.calibration.human_benchmark import compute_human_structure_benchmark
from src.calibration.parameters import ReducedPersonality6D, get_6d_calibration_parameters
from src.cognition.observation import Observation
from src.cognition.player_state import PlayerState
from src.engine.types import Alignment, GamePhase, PlayerId, RoleId, SkillLevel
from src.player.personality import PersonalityVector
from src.player.policy import CognitionPolicy
from src.player.skill import SkillProfile
from src.simulation.runner import SimulationResult
from src.storyteller.st_policy import StorytellerPolicy



class TestPhase35Mechanisms(unittest.TestCase):
    def setUp(self) -> None:
        self.players = [f"p{i}" for i in range(12)]
        self.personality = PersonalityVector(
            activity=0.6,
            openness=0.6,
            aggression=0.6,
            risk_tolerance=0.5,
            deception_tendency=0.2,
            trust_propensity=0.5,
            conformity=0.8,
            stubbornness=0.5,
            confidence=0.7,
            social_initiative=0.6,
        )

        self.skill = SkillProfile(
            level=SkillLevel.EXPERT,
            skill_score=0.85,
            belief_accuracy=0.90,
            temperature=0.8,
            memory_retention=1.5,
            voting_discipline=0.85,
            bluff_consistency=0.85,
        )


    def test_continuous_pass_utility(self) -> None:
        """Verify nomination policy produces continuous PASS utility without hard thresholds."""
        state = PlayerState.create(
            player_id="p0",
            all_players=self.players,
            perceived_role=RoleId.EMPATH,
            perceived_alignment=Alignment.GOOD,
            personality=self.personality,
            skill=self.skill,
        )
        policy = CognitionPolicy(state)

        # Build mock observation with 4 alive players
        roster_alive = {p: (i < 4) for i, p in enumerate(self.players)}
        obs = Observation(
            observer="p0",
            day=3,
            phase=GamePhase.NOMINATION,
            night_number=3,
            self_role=RoleId.EMPATH,
            self_alignment=Alignment.GOOD,
            alive=True,
            ghost_vote_available=False,
            roster_alive=roster_alive,
            deaths_public=[],
            execution_threshold=3,
            nominated_by_today=[],
            nominated_today=[],
            nominations_today=[],
            current_nomination=None,
        )

        chosen, trace = policy.score_nomination_detailed(obs)
        self.assertIsNotNone(trace)
        pass_key = "pass" if "pass" in trace.candidate_utilities else "PASS"
        self.assertIn(pass_key, trace.candidate_utilities)
        pass_util = trace.candidate_utilities[pass_key]
        # PASS utility must be a continuous finite number
        self.assertIsInstance(pass_util, float)
        self.assertGreater(pass_util, -10.0)
        self.assertLess(pass_util, 10.0)


        # Probabilities across all candidates including PASS should sum to ~1.0
        prob_sum = sum(trace.candidate_probabilities.values())
        self.assertAlmostEqual(prob_sum, 1.0, places=4)

    def test_evil_voting_busing(self) -> None:
        """Verify minion can vote on Demon under continuous exposure risk and busing utility."""
        minion_state = PlayerState.create(
            player_id="p1",
            all_players=self.players,
            perceived_role=RoleId.POISONER,
            perceived_alignment=Alignment.EVIL,
            personality=self.personality,
            skill=self.skill,
        )
        policy = CognitionPolicy(minion_state)

        roster_alive = {p: (i < 6) for i, p in enumerate(self.players)}
        # Demon p0 nominated, already has 4 votes meeting threshold
        obs = Observation(
            observer="p1",
            day=2,
            phase=GamePhase.VOTING,
            night_number=2,
            self_role=RoleId.POISONER,
            self_alignment=Alignment.EVIL,
            alive=True,
            ghost_vote_available=False,
            roster_alive=roster_alive,
            deaths_public=[],
            execution_threshold=4,
            nominated_by_today=["p2"],
            nominated_today=["p0"],
            nominations_today=[],
            current_nomination={
                "nominator": "p2",
                "nominee": "p0",
                "day": 2,
                "votes": {"p2": True, "p3": True, "p4": True, "p5": True},
            },
            evil_team_knowledge={"demon": "p0", "minions": ["p1"]},
        )

        vote_yes, trace = policy.score_vote_detailed(obs)
        self.assertIsNotNone(trace)
        util_yes = trace.candidate_utilities.get("YES", 0.0)
        # Utility should not be hardcoded -4.0, but calculated continuously
        self.assertNotEqual(util_yes, -4.0)

    def test_decoupled_social_conformity(self) -> None:
        """Verify private evidence is modulated by belief_accuracy and social events by conformity."""
        state = PlayerState.create(
            player_id="p0",
            all_players=self.players,
            perceived_role=RoleId.SLAYER,
            perceived_alignment=Alignment.GOOD,
            personality=PersonalityVector(
                activity=0.5,
                openness=0.5,
                aggression=0.5,
                risk_tolerance=0.5,
                deception_tendency=0.2,
                trust_propensity=0.5,
                conformity=0.9,  # High conformity
                stubbornness=0.5,
                confidence=0.5,
                social_initiative=0.5,
            ),
            skill=SkillProfile(
                level=SkillLevel.BEGINNER,
                skill_score=0.2,
                belief_accuracy=0.2,  # Low private accuracy
                temperature=1.8,
                memory_retention=0.6,
                voting_discipline=0.4,
                bluff_consistency=0.4,
            ),
        )

        # Private event
        init_demon_score = state.score_beliefs["p1"].demon_score
        update_belief_from_event(
            {"type": "INFO_FORTUNE_TELLER", "data": {"targets": ["p1"], "result": True}},
            state,
        )
        private_diff = state.score_beliefs["p1"].demon_score - init_demon_score
        # Modulated by 0.2
        self.assertAlmostEqual(private_diff, 1.0 * 0.2, places=4)

        # Social event
        curr_demon_score = state.score_beliefs["p2"].demon_score
        update_belief_from_event(
            {"type": "PUBLIC_NOMINATION", "target": "p2", "data": {"nominee": "p2"}},
            state,
        )
        social_diff = state.score_beliefs["p2"].demon_score - curr_demon_score
        # Modulated by conformity (0.9 * 0.25 = 0.225)
        self.assertAlmostEqual(social_diff, 0.25 * 0.9, places=4)

    def test_mayor_bounce_action_discrimination(self) -> None:
        """Verify Storyteller Mayor bounce differentiates candidates rather than assigning all equal."""
        from src.engine.state import GameState
        from src.engine.types import STDecisionType

        st_policy = StorytellerPolicy(seed=42)
        # Create minimal GameState
        roles = {
            "p0": RoleId.MAYOR,
            "p1": RoleId.RAVENKEEPER,
            "p2": RoleId.SOLDIER,
            "p3": RoleId.SLAYER,
            "p4": RoleId.CHEF,
            "p5": RoleId.IMP,
            "p6": RoleId.POISONER,
            "p7": RoleId.WASHERWOMAN,
            "p8": RoleId.LIBRARIAN,
            "p9": RoleId.INVESTIGATOR,
            "p10": RoleId.EMPATH,
            "p11": RoleId.VIRGIN,
        }
        alignments = {p: (Alignment.EVIL if p in ["p5", "p6"] else Alignment.GOOD) for p in self.players}
        state = GameState(
            seed=42,
            player_count=12,
            players=self.players,
            true_roles=roles,
            apparent_roles=roles,
            alignments=alignments,
            alive={p: True for p in self.players},
            ghost_votes={p: True for p in self.players},
            day=2,
            night_number=2,
        )

        decision = st_policy.decide(STDecisionType.MAYOR_BOUNCE, state, actor="p0")
        self.assertIsNotNone(decision)
        last_rec = st_policy.decisions_log[-1]
        scores = [v.get("total_utility", v.get("total", 0.0)) for v in last_rec.counterfactual_scores.values()]
        self.assertGreater(len(scores), 1)

        # Scores should not all be equal across Ravenkeeper, Soldier, Slayer, Imp, etc.
        self.assertFalse(all(s == scores[0] for s in scores))


    def test_human_structure_benchmark(self) -> None:
        """Verify HumanStructureBenchmark correctly computes survival funnel, hazard rates, and death tempo."""
        results = [
            SimulationResult.create_mock(
                seed=42,
                winner=Alignment.GOOD,
                end_reason="DEMON_EXECUTED",
                total_days=4,
                player_count=12,
                alive_players=["p0", "p1", "p2", "p3"],
                day_start_alives={1: 12, 2: 10, 3: 7, 4: 4},
                alive_trajectory=[12, 11, 10, 8, 7, 5, 4],
                cycle_deaths={1: 2, 2: 3, 3: 3},
                reached_4_alive_day=True,
                reached_3_alive_day=False,
                ever_had_4_alive_state=True,
                ever_had_3_alive_state=False,
                early_end_category="NORMAL_END",
            ),
            SimulationResult.create_mock(
                seed=43,
                winner=Alignment.EVIL,
                end_reason="SAINT_EXECUTED",
                total_days=2,
                player_count=12,
                alive_players=["p0", "p1"],
                day_start_alives={1: 12, 2: 10},
                alive_trajectory=[12, 10, 2],
                cycle_deaths={1: 2, 2: 8},
                reached_4_alive_day=False,
                reached_3_alive_day=False,
                ever_had_4_alive_state=False,
                ever_had_3_alive_state=False,
                early_end_category="RULE_SPECIAL_END",
            ),
        ]

        bench = compute_human_structure_benchmark(results)
        self.assertEqual(bench.total_games, 2)
        self.assertEqual(bench.reached_4_alive_day_rate_all, 0.5)
        # Non-special: only g1 is non-special -> 1.0
        self.assertEqual(bench.reached_4_alive_day_rate_non_special, 1.0)
        # Survival funnel captures all states 12..2
        self.assertEqual(len(bench.survival_funnel.alive_counts), 11)
        self.assertEqual(bench.survival_funnel.alive_counts[12], 2)
        # Death tempo computed
        self.assertGreater(bench.death_tempo.total_cycles_observed, 0)
        self.assertGreater(bench.death_tempo.mean_deaths_per_cycle, 0)

    def test_alignment_and_quadrant_diagnosis(self) -> None:
        """Verify alignment module computes inference quality, coordination quality, and Q1-Q4 quadrants."""
        results = [
            SimulationResult.create_mock(
                seed=42,
                winner=Alignment.GOOD,
                end_reason="DEMON_EXECUTED",
                total_days=4,
                alive_players=["p0", "p1", "p2", "p3"],
            ),
            SimulationResult.create_mock(
                seed=43,
                winner=Alignment.EVIL,
                end_reason="EVIL_PARITY",
                total_days=3,
                alive_players=["p0", "p1"],
            ),
        ]

        metrics = compute_alignment_and_quadrants(results)
        self.assertGreaterEqual(metrics.mean_coordination_quality, 0.0)
        self.assertLessEqual(metrics.mean_coordination_quality, 1.0)
        q_sum = (
            metrics.q1_high_i_high_c_rate
            + metrics.q2_high_i_low_c_rate
            + metrics.q3_low_i_high_c_rate
            + metrics.q4_low_i_low_c_rate
        )
        self.assertAlmostEqual(q_sum, 1.0, places=4)

    def test_friendly_fire_analysis(self) -> None:
        """Verify friendly fire analysis classifies into 9 causes and tactical vs mistaken."""
        results = [
            SimulationResult.create_mock(
                seed=42,
                winner=Alignment.EVIL,
                end_reason="SAINT_EXECUTED",
                total_days=2,
                alive_players=["p0", "p1"],
            ),
        ]
        ff = analyze_friendly_fire(results)
        self.assertIn(FriendlyFireCause.SAINT_NOMINATION_EXECUTION.value, ff.cause_counts)
        self.assertGreater(ff.cause_counts[FriendlyFireCause.SAINT_NOMINATION_EXECUTION.value], 0)
        self.assertGreater(ff.mistaken_rate, 0.0)


    def test_reduced_6d_personality(self) -> None:
        """Verify ReducedPersonality6D projects correctly to 10D parameters."""
        p6d = ReducedPersonality6D(
            assertiveness=0.75,
            skepticism=0.60,
            conformity=0.40,
            expressiveness=0.80,
            patience=0.65,
            evil_loyalty=0.85,
        )
        p10d = p6d.to_10d_mapping()
        self.assertEqual(p10d["aggression"], 0.75)
        self.assertEqual(p10d["risk_tolerance"], 0.75)
        self.assertEqual(p10d["conformity"], 0.40)
        self.assertAlmostEqual(p10d["trust_propensity"], 0.40, places=4)
        self.assertAlmostEqual(p10d["deception_tendency"], 0.85, places=4)
        self.assertEqual(p10d["stubbornness"], 0.50)


        params_6d = get_6d_calibration_parameters()
        self.assertEqual(len(params_6d), 6)


if __name__ == "__main__":
    unittest.main()
