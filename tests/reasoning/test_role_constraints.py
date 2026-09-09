"""Unit tests for Role Constraints across Trouble Brewing characters."""
from __future__ import annotations

import unittest

from src.engine.types import Alignment, RoleId
from src.reasoning.role_constraints.demon import ImpConstraintEvaluator
from src.reasoning.role_constraints.minions import (
    BaronConstraintEvaluator,
    PoisonerConstraintEvaluator,
    ScarletWomanConstraintEvaluator,
    SpyConstraintEvaluator,
)
from src.reasoning.role_constraints.outsiders import (
    ButlerConstraintEvaluator,
    RecluseConstraintEvaluator,
    SaintConstraintEvaluator,
)
from src.reasoning.role_constraints.townsfolk import (
    ChefConstraintEvaluator,
    EmpathConstraintEvaluator,
    FortuneTellerConstraintEvaluator,
    InvestigatorConstraintEvaluator,
    LibrarianConstraintEvaluator,
    UndertakerConstraintEvaluator,
    VirginConstraintEvaluator,
    WasherwomanConstraintEvaluator,
)
from src.reasoning.world import RoleSlot, WorldHypothesis


class TestRoleConstraints(unittest.TestCase):
    def setUp(self) -> None:
        self.players = [f"p{i}" for i in range(1, 8)]

    def _build_test_world(self, demon="p7", minion="p6") -> WorldHypothesis:
        slots = {
            "p1": RoleSlot.make_known(RoleId.EMPATH),
            "p2": RoleSlot.make_known(RoleId.CHEF),
            "p3": RoleSlot.make_known(RoleId.FORTUNE_TELLER),
            "p4": RoleSlot.make_known(RoleId.INVESTIGATOR),
            "p5": RoleSlot.make_known(RoleId.WASHERWOMAN),
            "p6": RoleSlot.make_known(RoleId.POISONER),
            "p7": RoleSlot.make_known(RoleId.IMP),
        }
        alignments = {p: Alignment.GOOD for p in self.players[:5]}
        alignments["p6"] = Alignment.EVIL
        alignments["p7"] = Alignment.EVIL
        return WorldHypothesis(
            world_id=1,
            demon_player=demon,
            minion_players=[minion],
            good_players=self.players[:5],
            slots=slots,
            alignments=alignments,
        )

    def test_chef_pairs_evaluation(self) -> None:
        """Chef evaluator correctly detects pairs of evil players."""
        evaluator = ChefConstraintEvaluator()
        world = self._build_test_world()
        # p6 and p7 are adjacent in [p1..p7] circle (indices 5 and 6)
        pairs = evaluator.count_evil_pairs(world, self.players)
        self.assertEqual(pairs, 1)

    def test_empath_neighbors_evaluation(self) -> None:
        """Empath evaluator checks adjacent alive neighbors."""
        evaluator = EmpathConstraintEvaluator()
        world = self._build_test_world()
        alive_roster = {p: True for p in self.players}
        # p1's neighbors in 7p circle: p7 (Imp - Evil) and p2 (Chef - Good)
        count = evaluator.count_evil_neighbors("p1", world, self.players, alive_roster)
        self.assertEqual(count, 1)

    def test_fortune_teller_evaluation(self) -> None:
        """Fortune Teller returns YES if target is Demon or Red Herring."""
        evaluator = FortuneTellerConstraintEvaluator()
        world = self._build_test_world()
        # Target p7 is Demon -> YES
        self.assertTrue(evaluator.eval_ping("p3", ("p7", "p2"), world, red_herring="p4"))
        # Target p4 is Red Herring -> YES
        self.assertTrue(evaluator.eval_ping("p3", ("p4", "p2"), world, red_herring="p4"))
        # Targets p1 and p2 (both good, neither RH) -> NO
        self.assertFalse(evaluator.eval_ping("p3", ("p1", "p2"), world, red_herring="p4"))

    def test_undertaker_evaluation(self) -> None:
        """Undertaker learns the role of the player executed yesterday."""
        evaluator = UndertakerConstraintEvaluator()
        world = self._build_test_world()
        # If p6 was executed, Undertaker should see Poisoner
        seen_role = evaluator.get_executed_role("p6", world)
        self.assertEqual(seen_role, RoleId.POISONER)

    def test_investigator_evaluation(self) -> None:
        """Investigator sees one Minion and one decoy."""
        evaluator = InvestigatorConstraintEvaluator()
        world = self._build_test_world()
        # p6 is Poisoner (Minion) -> valid candidate pair (p6, p2)
        valid = evaluator.is_valid_investigator_reading("p6", ("p6", "p2"), RoleId.POISONER, world)
        self.assertTrue(valid)
        # Pair with no minion -> invalid
        invalid = evaluator.is_valid_investigator_reading("p1", ("p1", "p2"), RoleId.POISONER, world)
        self.assertFalse(invalid)

    def test_recluse_spy_registrations(self) -> None:
        """Recluse can register as Evil/Minion/Demon; Spy can register as Good/Townsfolk."""
        recluse_eval = RecluseConstraintEvaluator()
        spy_eval = SpyConstraintEvaluator()

        self.assertTrue(recluse_eval.can_register_as(Alignment.EVIL))
        self.assertFalse(recluse_eval.can_register_as(Alignment.GOOD))

        self.assertTrue(spy_eval.can_register_as(Alignment.GOOD))
        self.assertFalse(spy_eval.can_register_as(Alignment.EVIL))


if __name__ == "__main__":
    unittest.main()
