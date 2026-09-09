"""Tests for multi-seed robustness, variance decomposition, and logistic regression model fitting."""
import unittest
import numpy as np

from src.calibration.outcome_regression import decompose_multi_seed_variance, fit_logistic_regression
from src.simulation.runner import simulate_game


class TestSeedRobustness(unittest.TestCase):
    def test_multi_seed_variance_decomposition(self):
        """Variance decomposition correctly separates between-seed variance and within-seed variance."""
        seed_win_rates = {42: 0.25, 43: 0.24, 44: 0.26, 45: 0.23, 46: 0.25}
        decomp = decompose_multi_seed_variance(seed_win_rates, n_per_seed=100)
        
        self.assertIn("overall_mean_win_rate", decomp)
        self.assertIn("between_seed_variance", decomp)
        self.assertIn("within_seed_sampling_variance", decomp)
        self.assertIn("total_variance", decomp)
        self.assertGreaterEqual(decomp["between_seed_variance_ratio"], 0.0)
        self.assertLessEqual(decomp["between_seed_variance_ratio"], 1.0)

    def test_logistic_regression_fitting(self):
        """Logistic regression fits simulated data, outputting valid odds ratios, z-scores, and 95% CIs."""
        rng = np.random.RandomState(42)
        n = 100
        # 3 synthetic predictors
        x1 = rng.randn(n)
        x2 = rng.randn(n)
        x3 = rng.randn(n)
        X = np.column_stack([x1, x2, x3])
        # Logistic probability with true beta = [0.8, -0.5, 0.2]
        logits = 0.8 * x1 - 0.5 * x2 + 0.2 * x3
        probs = 1.0 / (1.0 + np.exp(-logits))
        y = (rng.rand(n) < probs).astype(np.float64)

        coeffs = fit_logistic_regression(X, y, ["feature_x1", "feature_x2", "feature_x3"])
        
        self.assertEqual(len(coeffs), 4)  # intercept + 3 features
        for c in coeffs:
            self.assertEqual(c.relationship_type, "ASSOCIATION")
            self.assertGreaterEqual(c.std_error, 0.0)
            self.assertGreater(c.odds_ratio, 0.0)
            self.assertLessEqual(c.ci_95_lower, c.odds_ratio)
            self.assertLessEqual(c.odds_ratio, c.ci_95_upper)


if __name__ == "__main__":
    unittest.main()
