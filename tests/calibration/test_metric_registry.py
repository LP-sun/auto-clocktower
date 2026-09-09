"""Tests for BehaviorMetricRegistry, metric extraction, and Bootstrap confidence intervals."""
import unittest

from src.calibration.metrics import (
    BehaviorMetricDefinition,
    BehaviorMetricRegistry,
    compute_bootstrap_ci,
    extract_game_behavior_metrics,
)
from src.simulation.runner import simulate_game


class TestMetricRegistry(unittest.TestCase):
    def test_registry_registration_and_retrieval(self):
        """Metrics are correctly registered and retrievable by name."""
        all_metrics = BehaviorMetricRegistry.all_metrics()
        self.assertGreaterEqual(len(all_metrics), 10)
        
        chat_m = BehaviorMetricRegistry.get("private_chats_per_player_day")
        self.assertIsNotNone(chat_m)
        self.assertEqual(chat_m.scope, "chat")
        self.assertIn("pop_activity_mu", chat_m.related_parameters)

    def test_bootstrap_ci_bounds(self):
        """Bootstrap CI calculates mean and valid 95% confidence intervals."""
        data = [0.1, 0.2, 0.25, 0.3, 0.35, 0.4, 0.5]
        mean, low, high = compute_bootstrap_ci(data, n_bootstraps=200, ci=0.95, seed=42)
        self.assertLessEqual(low, mean)
        self.assertLessEqual(mean, high)
        self.assertAlmostEqual(mean, sum(data)/len(data), places=2)

    def test_extract_game_behavior_metrics(self):
        """Extract behavior metrics produces all registered canonical keys from a simulated game."""
        res = simulate_game(player_count=12, seed=42)
        metrics = extract_game_behavior_metrics(res.to_dict())
        
        expected_keys = [
            "private_chats_per_player_day",
            "good_good_chat_ratio",
            "evil_evil_chat_ratio",
            "claim_disclosure_rate",
            "nomination_friendly_fire_rate",
            "execution_friendly_fire_rate",
            "vote_consistency",
            "vote_participation_rate",
            "night_kill_value_percentile",
            "monk_protection_quality",
            "trust_error_rate",
        ]
        for k in expected_keys:
            self.assertIn(k, metrics)
            self.assertIsInstance(metrics[k], (int, float))


if __name__ == "__main__":
    unittest.main()
