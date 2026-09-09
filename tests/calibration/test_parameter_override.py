"""Tests for parameter registry, domain-aware sweep generation, and identifiability Jacobian analysis."""
import unittest
import numpy as np

from src.calibration.parameters import (
    CalibrationConfig,
    CalibrationParameter,
    CalibrationRegistry,
    ParameterDomain,
    TransformType,
    compute_identifiability_analysis,
)
from src.simulation.runner import simulate_game


class TestParameterOverride(unittest.TestCase):
    def test_registry_parameter_metadata(self):
        """All registered parameters have valid domains, bounds, and transform types."""
        params = CalibrationRegistry.all_parameters()
        self.assertGreaterEqual(len(params), 10)

        for p in params:
            self.assertIsInstance(p.domain, ParameterDomain)
            self.assertIsInstance(p.transform, TransformType)
            low, high = p.bounds
            self.assertLess(low, high)
            self.assertGreaterEqual(p.default, low)
            self.assertLessEqual(p.default, high)

    def test_domain_aware_sweep_generation(self):
        """Sweep values respect domain bounds and transform types."""
        # Logit parameter in [0.1, 0.9]
        param_logit = CalibrationRegistry.get("pop_activity_mu")
        self.assertIsNotNone(param_logit)
        vals_logit = param_logit.generate_sweep_values()
        self.assertEqual(len(vals_logit), 5)
        for v in vals_logit:
            self.assertGreaterEqual(v, 0.1)
            self.assertLessEqual(v, 0.9)

        # Multiplicative positive parameter
        param_mult = CalibrationRegistry.get("vote_evil_weight")
        self.assertIsNotNone(param_mult)
        vals_mult = param_mult.generate_sweep_values()
        self.assertEqual(len(vals_mult), 5)
        self.assertAlmostEqual(vals_mult[2], param_mult.default, places=3)
        self.assertLess(vals_mult[0], vals_mult[4])

    def test_config_override_simulation(self):
        """Passing CalibrationConfig overrides parameter during simulation non-invasively."""
        cfg = CalibrationConfig(overrides={"pop_activity_mu": 0.85, "vote_evil_weight": 5.0})
        res = simulate_game(player_count=12, seed=42, config=cfg)
        self.assertIsNotNone(res.winner)
        self.assertGreater(res.event_count, 10)

    def test_identifiability_analysis(self):
        """Sensitivity Jacobian, condition number, and collinearity pairs are correctly computed."""
        param_names = ["pop_activity_mu", "pop_social_initiative_mu", "vote_evil_weight"]
        metric_names = ["private_chats_per_player_day", "vote_consistency"]
        base_metrics = {"private_chats_per_player_day": 0.35, "vote_consistency": 0.55}
        
        perturbed_metrics = {
            "pop_activity_mu": {"private_chats_per_player_day": 0.42, "vote_consistency": 0.55},
            "pop_social_initiative_mu": {"private_chats_per_player_day": 0.41, "vote_consistency": 0.55},
            "vote_evil_weight": {"private_chats_per_player_day": 0.35, "vote_consistency": 0.68},
        }
        delta_thetas = {"pop_activity_mu": 0.2, "pop_social_initiative_mu": 0.2, "vote_evil_weight": 0.2}

        report = compute_identifiability_analysis(
            param_names=param_names,
            metric_names=metric_names,
            base_metrics=base_metrics,
            perturbed_metrics=perturbed_metrics,
            delta_thetas=delta_thetas,
        )

        self.assertEqual(report.jacobian.shape, (2, 3))
        self.assertGreater(report.condition_number, 1.0)
        self.assertGreaterEqual(report.effective_rank, 1)
        self.assertEqual(report.correlation_matrix.shape, (3, 3))
        # Activity and social initiative affect the same metric in same direction -> high collinearity detected
        self.assertGreaterEqual(len(report.collinear_pairs), 1)


if __name__ == "__main__":
    unittest.main()
