"""Unit tests for Setup Constraints in Trouble Brewing."""
from __future__ import annotations

import math
import unittest

from src.engine.types import Alignment, RoleId
from src.reasoning.constraints.setup_constraints import (
    TB_COMPOSITION,
    SetupConstraintEvaluator,
)
from src.reasoning.world import RoleSlot, WorldHypothesis


class TestSetupConstraints(unittest.TestCase):
    def setUp(self) -> None:
        self.evaluator = SetupConstraintEvaluator()

    def test_tb_composition_table(self) -> None:
        """Verify official Trouble Brewing player count compositions."""
        self.assertEqual(TB_COMPOSITION[7], (5, 0, 1, 1))
        self.assertEqual(TB_COMPOSITION[8], (3, 2, 2, 1))  # 3 TF, 2 Out, 2 Min, 1 Dem
        self.assertEqual(TB_COMPOSITION[10], (7, 0, 2, 1))
        self.assertEqual(TB_COMPOSITION[12], (7, 2, 2, 1))

    def test_duplicate_roles_penalized_hard(self) -> None:
        """Duplicate unique roles should receive infinite penalty (-inf)."""
        players = [f"p{i}" for i in range(1, 8)]
        slots = {
            "p1": RoleSlot.make_known(RoleId.EMPATH),
            "p2": RoleSlot.make_known(RoleId.EMPATH),  # Duplicate Townsfolk!
            "p3": RoleSlot.make_known(RoleId.CHEF),
            "p4": RoleSlot.make_known(RoleId.INVESTIGATOR),
            "p5": RoleSlot.make_known(RoleId.WASHERWOMAN),
            "p6": RoleSlot.make_known(RoleId.POISONER),
            "p7": RoleSlot.make_known(RoleId.IMP),
        }
        alignments = {p: Alignment.GOOD for p in players[:5]}
        alignments["p6"] = Alignment.EVIL
        alignments["p7"] = Alignment.EVIL

        world = WorldHypothesis(
            world_id=1,
            demon_player="p7",
            minion_players=["p6"],
            good_players=players[:5],
            slots=slots,
            alignments=alignments,
        )

        cost = self.evaluator.evaluate(world, players)
        self.assertTrue(math.isinf(cost) and cost < 0.0)

    def test_baron_outsider_count_adjustment(self) -> None:
        """Baron adds 2 outsiders; a world with Baron and correct outsiders is legal."""
        players = [f"p{i}" for i in range(1, 8)]  # 7p base: 5 TF, 0 Out, 1 Min, 1 Dem. With Baron: 3 TF, 2 Out!
        slots = {
            "p1": RoleSlot.make_known(RoleId.BUTLER),    # Outsider 1
            "p2": RoleSlot.make_known(RoleId.SAINT),     # Outsider 2
            "p3": RoleSlot.make_known(RoleId.EMPATH),    # TF 1
            "p4": RoleSlot.make_known(RoleId.CHEF),      # TF 2
            "p5": RoleSlot.make_known(RoleId.INVESTIGATOR),  # TF 3
            "p6": RoleSlot.make_known(RoleId.BARON),     # Minion
            "p7": RoleSlot.make_known(RoleId.IMP),       # Demon
        }
        alignments = {p: Alignment.GOOD for p in players[:5]}
        alignments["p6"] = Alignment.EVIL
        alignments["p7"] = Alignment.EVIL

        world = WorldHypothesis(
            world_id=2,
            demon_player="p7",
            minion_players=["p6"],
            good_players=players[:5],
            slots=slots,
            alignments=alignments,
        )

        cost = self.evaluator.evaluate(world, players)
        self.assertFalse(math.isinf(cost))
        self.assertGreaterEqual(cost, 0.0)


if __name__ == "__main__":
    unittest.main()
