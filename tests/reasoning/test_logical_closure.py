"""Unit tests for Logical Closure and Conditioned Deduction (Amendment 8)."""
from __future__ import annotations

import os
import unittest

from src.engine.types import Alignment, RoleId
from src.reasoning.logical_closure import LogicalClosureEngine
from src.reasoning.world import RoleSlot, WorldHypothesis


class TestLogicalClosure(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = LogicalClosureEngine()

    def test_conditional_query_deduces_forced_assignments(self) -> None:
        """Querying assume Demon=p7 across candidate worlds should force common slots and identify minions."""
        players = [f"p{i}" for i in range(1, 8)]

        # World 1: Demon=p7, Minion=p6, p1=Empath, p2=Chef, p3=Virgin
        w1 = WorldHypothesis(
            world_id=1,
            demon_player="p7",
            minion_players=["p6"],
            good_players=players[:5],
            slots={
                "p1": RoleSlot.make_known(RoleId.EMPATH),
                "p2": RoleSlot.make_known(RoleId.CHEF),
                "p3": RoleSlot.make_known(RoleId.VIRGIN),
                "p4": RoleSlot.make_known(RoleId.INVESTIGATOR),
                "p5": RoleSlot.make_known(RoleId.WASHERWOMAN),
                "p6": RoleSlot.make_known(RoleId.POISONER),
                "p7": RoleSlot.make_known(RoleId.IMP),
            },
            alignments={p: Alignment.GOOD for p in players[:5]},
            claim_truth_assignment={"p1": True, "p2": True, "p6": False},
            drunk_player="p2",
        )
        w1.alignments["p6"] = Alignment.EVIL
        w1.alignments["p7"] = Alignment.EVIL
        w1.probability = 0.6

        # World 2: Demon=p7, Minion=p6, p1=Empath, p2=Chef, p3=Slayer
        w2 = WorldHypothesis(
            world_id=2,
            demon_player="p7",
            minion_players=["p6"],
            good_players=players[:5],
            slots={
                "p1": RoleSlot.make_known(RoleId.EMPATH),
                "p2": RoleSlot.make_known(RoleId.CHEF),
                "p3": RoleSlot.make_known(RoleId.SLAYER),  # Differs from w1
                "p4": RoleSlot.make_known(RoleId.INVESTIGATOR),
                "p5": RoleSlot.make_known(RoleId.WASHERWOMAN),
                "p6": RoleSlot.make_known(RoleId.BARON),
                "p7": RoleSlot.make_known(RoleId.IMP),
            },
            alignments={p: Alignment.GOOD for p in players[:5]},
            claim_truth_assignment={"p1": True, "p2": True, "p6": False},
            drunk_player="p2",
        )
        w2.alignments["p6"] = Alignment.EVIL
        w2.alignments["p7"] = Alignment.EVIL
        w2.probability = 0.4

        # World 3: Demon=p5 (Alternative hypothesis)
        w3 = WorldHypothesis(
            world_id=3,
            demon_player="p5",
            minion_players=["p4"],
            good_players=["p1", "p2", "p3", "p6", "p7"],
            slots={
                "p1": RoleSlot.make_known(RoleId.BUTLER),
                "p5": RoleSlot.make_known(RoleId.IMP),
            },
            alignments={"p5": Alignment.EVIL, "p4": Alignment.EVIL},
            claim_truth_assignment={"p5": False},
        )
        w3.probability = 0.0

        all_worlds = [w1, w2, w3]

        # Query: assume Demon=p7
        result = self.engine.compute_closure(
            worlds=all_worlds,
            demon_player="p7",
            all_players=players,
        )

        self.assertFalse(result.is_refuted)
        self.assertEqual(result.consistent_world_count, 2)
        # Forced assignments: p1 (EMPATH), p2 (CHEF), p4 (INVESTIGATOR), p5 (WASHERWOMAN), p7 (IMP)
        self.assertEqual(result.forced_assignments["p1"], RoleId.EMPATH)
        self.assertEqual(result.forced_assignments["p2"], RoleId.CHEF)
        self.assertEqual(result.forced_assignments["p7"], RoleId.IMP)
        # p3 is not forced because w1 has VIRGIN and w2 has SLAYER
        self.assertNotIn("p3", result.forced_assignments)

        # Minion candidate p6 has 100% conditional probability
        minion_dict = dict(result.likely_minions)
        self.assertAlmostEqual(minion_dict.get("p6", 0.0), 1.0)

        # Required explanations: Drunk=p2
        self.assertTrue(any("Drunk=p2" in exp for exp in result.required_explanations))

        # Eliminated claims: p6
        eliminated_players = [c["player"] for c in result.eliminated_claims]
        self.assertIn("p6", eliminated_players)

    def test_refuted_condition_returns_refutation(self) -> None:
        """Querying an impossible condition yields is_refuted = True."""
        players = [f"p{i}" for i in range(1, 8)]
        w1 = WorldHypothesis(
            world_id=1,
            demon_player="p7",
            minion_players=["p6"],
            good_players=players[:5],
            slots={"p7": RoleSlot.make_known(RoleId.IMP)},
            alignments={"p7": Alignment.EVIL},
        )

        result = self.engine.compute_closure(
            worlds=[w1],
            demon_player="p1",  # No world has Demon=p1
            all_players=players,
        )
        self.assertTrue(result.is_refuted)
        self.assertEqual(result.consistent_world_count, 0)

    def test_export_diagnostics_csv(self) -> None:
        """Verify export to CSV creates a valid file."""
        csv_path = "output/test_logical_closure_diagnostics.csv"
        os.makedirs("output", exist_ok=True)
        self.engine.export_diagnostics_csv(csv_path)
        self.assertTrue(os.path.exists(csv_path))
        if os.path.exists(csv_path):
            os.remove(csv_path)


if __name__ == "__main__":
    unittest.main()
