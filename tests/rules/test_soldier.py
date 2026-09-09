"""Unit tests for Soldier official rules.

Rules verified:
- Soldier is safe from the Demon at night: Demon attack does not kill Soldier.
- Soldier is NOT safe from execution: dying by execution kills the Soldier.
- If Soldier is poisoned or drunk, they are NOT safe from the Demon.
"""
import unittest

from src.engine.game import ClocktowerEngine
from src.engine.types import RoleId
from tests.test_engine_rules import make_custom_setup


class TestSoldierRules(unittest.TestCase):
    def test_soldier_safe_from_demon_at_night(self):
        """Demon attacks Soldier -> Soldier does not die."""
        roles = [
            RoleId.SOLDIER, RoleId.CHEF, RoleId.POISONER, RoleId.IMP,
        ]
        setup = make_custom_setup(roles)
        engine = ClocktowerEngine.create(custom_setup=setup)

        engine.start_day()
        engine.end_day()

        # Night 2: Imp attacks Soldier (P01)
        engine.run_night(demon_target="P01")

        self.assertTrue(engine.state.alive["P01"])
        self.assertEqual(len(engine.state.deaths), 0)

    def test_soldier_vulnerable_to_execution(self):
        """Soldier is not immune to execution during the day."""
        roles = [
            RoleId.SOLDIER, RoleId.CHEF, RoleId.POISONER, RoleId.IMP,
        ]
        setup = make_custom_setup(roles)
        engine = ClocktowerEngine.create(custom_setup=setup)

        engine.start_day()
        # Nominate and execute Soldier P01
        engine.handle_nomination("P02", "P01")
        engine.cast_votes({"P02": True, "P03": True, "P04": True})
        engine.end_day()

        self.assertFalse(engine.state.alive["P01"])

    def test_poisoned_soldier_killed_by_demon(self):
        """Poisoned Soldier loses ability and dies when attacked by the Demon."""
        roles = [
            RoleId.SOLDIER, RoleId.CHEF, RoleId.POISONER, RoleId.IMP,
        ]
        setup = make_custom_setup(roles)
        engine = ClocktowerEngine.create(custom_setup=setup)

        engine.start_day()
        engine.end_day()

        # Night 2: Poisoner poisons Soldier (P01); Imp attacks Soldier (P01)
        engine.run_night(poisoner_target="P01", demon_target="P01")

        self.assertFalse(engine.state.alive["P01"])


if __name__ == "__main__":
    unittest.main()
