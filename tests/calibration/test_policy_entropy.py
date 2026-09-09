"""Tests for primitive 6-class taxonomy, co-activation matrix, dominance detection, and conditional policy entropy."""
import unittest

from src.calibration.primitives import PrimitiveInteractionAnalyzer
from src.strategies.primitives import PRIMITIVE_TAXONOMY, PrimitiveType, StrategyPrimitive, get_primitive_type
from src.simulation.runner import simulate_game


class TestPolicyEntropy(unittest.TestCase):
    def test_primitive_six_class_taxonomy(self):
        """All StrategyPrimitives are mapped to exactly one of the 6 canonical PrimitiveTypes."""
        for prim in StrategyPrimitive:
            ptype = get_primitive_type(prim)
            self.assertIsInstance(ptype, PrimitiveType)
            self.assertIn(ptype, {
                PrimitiveType.ELIGIBILITY,
                PrimitiveType.ACTION_GATE,
                PrimitiveType.PREFERENCE,
                PrimitiveType.UTILITY_MODIFIER,
                PrimitiveType.BELIEF_UPDATE,
                PrimitiveType.TARGET_SELECTOR,
            })

        # Check action gates
        self.assertEqual(get_primitive_type(StrategyPrimitive.PRIVATE_CLAIM), PrimitiveType.ACTION_GATE)
        self.assertEqual(get_primitive_type(StrategyPrimitive.PUBLIC_CLAIM), PrimitiveType.ACTION_GATE)

    def test_primitive_coactivation_matrix(self):
        """Co-activation matrix counts co-occurring applicable primitives in decision traces."""
        traces = [
            {"applicable_primitives": ["PUSH_EXECUTION", "TEST_VIRGIN"]},
            {"applicable_primitives": ["PUSH_EXECUTION", "TEST_VIRGIN", "EVIL_COORDINATION"]},
        ]
        coact = PrimitiveInteractionAnalyzer.compute_coactivation_matrix(traces)
        self.assertGreaterEqual(coact.get(("PUSH_EXECUTION", "TEST_VIRGIN"), 0), 2)

    def test_primitive_dominance_detection(self):
        """Dominance detection identifies primitives that constitute >=80% of candidate utility."""
        traces = [
            {
                "utility_components": {
                    "P01": {"evil_contrib": 4.5, "noise": 0.1},  # evil_contrib is 4.5 / 4.6 = 97.8% (>80%)
                    "P02": {"evil_contrib": 3.8, "noise": 0.2},
                }
            }
        ]
        dom_reports = PrimitiveInteractionAnalyzer.detect_primitive_dominance(traces, dominance_threshold=0.80)
        evil_rep = next((r for r in dom_reports if r["component"] == "evil_contrib"), None)
        self.assertIsNotNone(evil_rep)
        self.assertGreaterEqual(evil_rep["dominance_ratio"], 0.80)

    def test_conditional_policy_entropy(self):
        """Conditional entropies for action, chat target, and claim type are computed and non-negative."""
        games = [simulate_game(player_count=12, seed=42 + i).to_dict() for i in range(3)]
        entropies = PrimitiveInteractionAnalyzer.compute_conditional_entropies(games)
        
        self.assertIn("h_action_given_role_day", entropies)
        self.assertIn("h_chattarget_given_role_day", entropies)
        self.assertIn("h_claimtype_given_role_day", entropies)
        self.assertGreaterEqual(entropies["h_action_given_role_day"], 0.0)


if __name__ == "__main__":
    unittest.main()
