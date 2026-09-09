"""Tests for Storyteller diagnostics: decision stratification, component variance, rank stability, and no-future-peeking audit."""
import unittest

from src.calibration.st_diagnostics import StorytellerDiagnostics
from src.storyteller.types import STDecisionPhase, STDecisionRecord
from src.simulation.runner import simulate_game


class TestStorytellerSensitivity(unittest.TestCase):
    def test_stratified_decisions(self):
        """Storyteller decisions are stratified by phase and decision type with valid metrics."""
        res = simulate_game(player_count=12, seed=1)
        decisions = res.to_dict().get("st_decisions", [])
        
        strat = StorytellerDiagnostics.analyze_stratified_decisions(decisions)
        self.assertGreater(len(strat), 0)
        for s in strat:
            self.assertIn("phase", s)
            self.assertIn("decision_type", s)
            self.assertGreaterEqual(s["decision_count"], 1)
            self.assertGreaterEqual(s["median_delta_u"], 0.0)
            self.assertGreaterEqual(s["all_equal_rate"], 0.0)
            self.assertLessEqual(s["all_equal_rate"], 1.0)

    def test_component_variance_and_scale(self):
        """Component variance and scale metrics are extracted for all utility terms."""
        res = simulate_game(player_count=12, seed=1)
        decisions = res.to_dict().get("st_decisions", [])
        
        scale_reports = StorytellerDiagnostics.analyze_component_variance_and_scale(decisions)
        self.assertGreaterEqual(len(scale_reports), 4)
        comp_names = {r["component"] for r in scale_reports}
        self.assertEqual(comp_names, {"fairness", "tension", "solvability", "drama"})
        for r in scale_reports:
            self.assertGreaterEqual(r["variance"], 0.0)
            self.assertLessEqual(r["min"], r["max"])

    def test_rank_stability(self):
        """Rank stability under +/-5% and +/-10% weight perturbations is bounded in [0, 1]."""
        res = simulate_game(player_count=12, seed=1)
        decisions = res.to_dict().get("st_decisions", [])
        
        stability = StorytellerDiagnostics.evaluate_rank_stability(decisions, [0.05, 0.10])
        self.assertIn("rank_stability_5pct", stability)
        self.assertIn("rank_stability_10pct", stability)
        self.assertGreaterEqual(stability["rank_stability_5pct"], 0.0)
        self.assertLessEqual(stability["rank_stability_5pct"], 1.0)

    def test_no_future_peeking_audit(self):
        """Audit passes on clean records and raises AssertionError if future keys are injected."""
        clean_decisions = [
            {"state_features": {"alive_count": 8, "tension": 0.5, "candidate_count": 3}}
        ]
        self.assertTrue(StorytellerDiagnostics.audit_no_future_peeking(clean_decisions))

        leaky_decisions = [
            {"state_features": {"alive_count": 8, "future_kill_target": "P02"}}
        ]
        with self.assertRaises(AssertionError):
            StorytellerDiagnostics.audit_no_future_peeking(leaky_decisions)


if __name__ == "__main__":
    unittest.main()
