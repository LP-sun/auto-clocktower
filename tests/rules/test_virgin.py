"""Rule tests for Virgin: Townsfolk check, ability spent on non-townsfolk/drunk, and day ending."""
import unittest

from src.engine.game import ClocktowerEngine
from src.engine.types import GamePhase, RoleId
from tests.test_engine_rules import make_custom_setup


class TestVirginRules(unittest.TestCase):
    def test_virgin_nominated_by_true_townsfolk(self):
        """Nominated first time by true Townsfolk -> nominator executed immediately, day ends."""
        roles = [
            RoleId.WASHERWOMAN, RoleId.VIRGIN, RoleId.SAINT, RoleId.IMP,
        ]
        setup = make_custom_setup(roles)
        engine = ClocktowerEngine.create(custom_setup=setup)
        engine.start_day()

        # P01 (Washerwoman - Townsfolk) nominates P02 (Virgin)
        nom = engine.handle_nomination("P01", "P02")
        self.assertIsNone(nom)  # Day immediately ended
        self.assertFalse(engine.state.alive["P01"])
        self.assertIn("P02", engine.state.ability_used)
        self.assertEqual(engine.state.executed_today, "P01")

    def test_virgin_nominated_by_outsider_saint(self):
        """Nominated first time by Outsider (Saint) -> nominator NOT executed, but ability is spent!"""
        roles = [
            RoleId.WASHERWOMAN, RoleId.VIRGIN, RoleId.SAINT, RoleId.IMP,
        ]
        setup = make_custom_setup(roles)
        engine = ClocktowerEngine.create(custom_setup=setup)
        engine.start_day()

        # P03 (Saint - Outsider) nominates P02 (Virgin)
        nom = engine.handle_nomination("P03", "P02")
        self.assertIsNotNone(nom)
        self.assertTrue(engine.state.alive["P03"])  # Saint not executed!
        self.assertIn("P02", engine.state.ability_used)  # Virgin ability IS spent!

        # Second nomination on Day 2 by true Townsfolk P01 -> does NOT trigger because ability spent!
        engine.cast_votes({})  # Finish P03 nomination
        engine.end_day()
        engine.run_night({})
        engine.start_day()
        nom2 = engine.handle_nomination("P01", "P02")
        self.assertIsNotNone(nom2)
        self.assertTrue(engine.state.alive["P01"])

    def test_virgin_nominated_by_drunk_believing_townsfolk(self):
        """Drunk believing they are Townsfolk is still an Outsider -> Virgin does NOT proc!"""
        roles = [
            RoleId.DRUNK, RoleId.VIRGIN, RoleId.CHEF, RoleId.IMP,
        ]
        setup = make_custom_setup(roles, fake_drunk=RoleId.WASHERWOMAN)
        engine = ClocktowerEngine.create(custom_setup=setup)
        engine.start_day()

        # P01 is Drunk (thinks Washerwoman), nominates Virgin P02
        nom = engine.handle_nomination("P01", "P02")
        self.assertIsNotNone(nom)
        self.assertTrue(engine.state.alive["P01"])  # P01 not executed!
        self.assertIn("P02", engine.state.ability_used)

    def test_poisoned_virgin_spends_ability_without_proc(self):
        """Poisoned Virgin nominated by true Townsfolk -> ability spent, but nominator NOT executed!"""
        roles = [
            RoleId.WASHERWOMAN, RoleId.VIRGIN, RoleId.CHEF, RoleId.IMP,
        ]
        setup = make_custom_setup(roles)
        engine = ClocktowerEngine.create(custom_setup=setup)

        # Poison Virgin P02
        engine.state.add_ongoing_effect("POISON", source_player=None, target_player="P02", expires_at="permanent")

        engine.start_day()
        nom = engine.handle_nomination("P01", "P02")
        self.assertIsNotNone(nom)
        self.assertTrue(engine.state.alive["P01"])
        self.assertIn("P02", engine.state.ability_used)


if __name__ == "__main__":
    unittest.main()
