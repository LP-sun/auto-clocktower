"""Tests for GoodLossDecomposition, fine-grained failure modes, information lifecycle, and 4-quadrant diagnosis."""
import unittest

from src.calibration.failure_modes import AssociatedFailureMode, GoodLossDecomposition
from src.simulation.runner import simulate_game


class TestFailureClassification(unittest.TestCase):
    def test_saint_execution_failure_attribution(self):
        """Saint execution directly triggers EXECUTION_SELECTION_FAILURE."""
        mock_game = {
            "end_reason": "saint_executed",
            "events": [{"type": "EXECUTION", "actor": "P04", "day": 2}],
            "alignments": {"P04": "good"},
            "true_roles": {"P04": "saint"},
            "apparent_roles": {"P04": "saint"},
            "alive_players": ["P01", "P02", "P03"],
        }
        failures = GoodLossDecomposition.classify_failures(mock_game)
        self.assertIn(AssociatedFailureMode.EXECUTION_SELECTION_FAILURE, failures)

    def test_demon_vote_threshold_failure(self):
        """Demon nomination receiving votes strictly below threshold triggers VOTE_THRESHOLD_FAILURE."""
        mock_game = {
            "end_reason": "demon_in_final_two",
            "events": [
                {"type": "NOMINATION", "day": 2, "actor": "P01", "target": "P03"},
                {
                    "type": "VOTE_RESULT",
                    "day": 2,
                    "data": {"nominee": "P03", "votes": 4, "threshold": 6},
                },
            ],
            "alignments": {"P01": "good", "P02": "good", "P03": "evil"},
            "true_roles": {"P01": "washerwoman", "P02": "librarian", "P03": "imp"},
            "apparent_roles": {"P01": "washerwoman", "P02": "librarian", "P03": "imp"},
            "alive_players": ["P01", "P03"],
        }
        failures = GoodLossDecomposition.classify_failures(mock_game)
        self.assertIn(AssociatedFailureMode.VOTE_THRESHOLD_FAILURE, failures)

    def test_information_lifecycle_rates(self):
        """Information lifecycle tracks conversion probabilities within [0, 1]."""
        res = simulate_game(player_count=12, seed=42)
        lifecycle = GoodLossDecomposition.compute_information_lifecycle(res.to_dict())
        
        self.assertIn("p_shared_given_gen", lifecycle)
        self.assertIn("p_trusted_given_shared", lifecycle)
        self.assertIn("p_used_given_trusted", lifecycle)
        self.assertGreaterEqual(lifecycle["p_shared_given_gen"], 0.0)
        self.assertLessEqual(lifecycle["p_shared_given_gen"], 1.0)

    def test_four_quadrant_diagnosis(self):
        """4-Quadrant analysis outputs bounded inference & coordination scores and valid quadrant."""
        res = simulate_game(player_count=12, seed=42)
        inf_q, coord_q, quad = GoodLossDecomposition.compute_quadrant_diagnosis(res.to_dict())
        
        self.assertGreaterEqual(inf_q, 0.0)
        self.assertLessEqual(inf_q, 1.0)
        self.assertGreaterEqual(coord_q, 0.0)
        self.assertLessEqual(coord_q, 1.0)
        self.assertIn(quad, {
            "Q1_OPTIMAL_PLAY",
            "Q2_COORDINATION_FAILURE",
            "Q3_INFERENCE_FAILURE",
            "Q4_TOTAL_COLLAPSE",
        })


if __name__ == "__main__":
    unittest.main()
