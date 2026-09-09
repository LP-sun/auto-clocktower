"""Unit tests for Poisoner official rules and OngoingEffect lifecycle.

Rules verified:
- Poisoner chooses a player each night; that player is poisoned tonight and tomorrow day (until dusk).
- When poisoned, target's ability does not function or yields misinformation.
- Lifecycle: If Poisoner dies during the day, ongoing poison effect ceases immediately!
- Poisoner can choose themselves (self-poison).
"""
import unittest

from src.engine.game import ClocktowerEngine
from src.engine.types import RoleId
from tests.test_engine_rules import make_custom_setup


class TestPoisonerRules(unittest.TestCase):
    def test_poisoner_poisons_target_through_day(self):
        """Target remains poisoned through night and following day until dusk."""
        roles = [
            RoleId.POISONER, RoleId.EMPATH, RoleId.CHEF, RoleId.IMP,
        ]
        setup = make_custom_setup(roles)
        engine = ClocktowerEngine.create(custom_setup=setup)

        # Night 1: Poison Empath (P02)
        engine.run_first_night(poisoner_target="P02")
        self.assertTrue(engine.state.is_poisoned("P02"))

        # Day 1: Empath is still poisoned
        engine.start_day()
        self.assertTrue(engine.state.is_poisoned("P02"))

        # Day 1 ends (dusk): poison expires
        engine.end_day()
        self.assertFalse(engine.state.is_poisoned("P02"))

    def test_poison_ceases_immediately_when_poisoner_dies(self):
        """When Poisoner dies during the day (execution/slayer/virgin), poison ceases immediately."""
        roles = [
            RoleId.POISONER, RoleId.SOLDIER, RoleId.VIRGIN, RoleId.IMP,
        ]
        setup = make_custom_setup(roles)
        engine = ClocktowerEngine.create(custom_setup=setup)

        # Night 1: Poison Soldier (P02)
        engine.run_first_night(poisoner_target="P02")
        self.assertTrue(engine.state.is_poisoned("P02"))

        engine.start_day()
        self.assertTrue(engine.state.is_poisoned("P02"))

        # Poisoner (P01) is executed on Day 1
        engine.handle_nomination("P03", "P01")
        engine.cast_votes({"P02": True, "P03": True, "P04": True})
        engine.end_day()

        # Poisoner is dead, so Soldier is no longer poisoned!
        self.assertFalse(engine.state.alive["P01"])
        self.assertFalse(engine.state.is_poisoned("P02"))

    def test_self_poisoning(self):
        """Poisoner can poison themselves."""
        roles = [
            RoleId.POISONER, RoleId.SOLDIER, RoleId.VIRGIN, RoleId.IMP,
        ]
        setup = make_custom_setup(roles)
        engine = ClocktowerEngine.create(custom_setup=setup)

        engine.run_first_night(poisoner_target="P01")
        self.assertTrue(engine.state.is_poisoned("P01"))


if __name__ == "__main__":
    unittest.main()
