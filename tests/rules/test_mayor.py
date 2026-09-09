"""Rule tests for Mayor: 3-alive victory conditions and night bounce interactions."""
import unittest

from src.engine.game import ClocktowerEngine
from src.engine.types import Alignment, DeathReason, RoleId
from tests.test_engine_rules import make_custom_setup


class TestMayorRules(unittest.TestCase):
    def test_mayor_three_alive_no_execution_wins(self):
        """Exactly 3 alive, no execution, Mayor functioning -> Good wins!"""
        roles = [RoleId.MAYOR, RoleId.CHEF, RoleId.IMP]
        setup = make_custom_setup(roles)
        engine = ClocktowerEngine.create(custom_setup=setup)
        engine.start_day()

        # Day ends with no execution
        executed = engine.end_day()
        self.assertIsNone(executed)
        self.assertEqual(engine.state.winner, Alignment.GOOD)
        self.assertEqual(engine.state.end_reason, "mayor_three_alive")

    def test_mayor_three_alive_with_execution_does_not_win(self):
        """Exactly 3 alive, but execution occurs today -> Mayor win condition does NOT trigger today."""
        roles = [RoleId.MAYOR, RoleId.CHEF, RoleId.IMP]
        setup = make_custom_setup(roles)
        engine = ClocktowerEngine.create(custom_setup=setup)
        engine.start_day()

        # Nominate Chef P02 and execute
        engine.handle_nomination("P01", "P02")
        engine.cast_votes({"P01": True, "P03": True})  # 2 votes >= ceil(3/2) = 2
        executed = engine.end_day()

        self.assertEqual(executed, "P02")
        # Chef died, alive count is now 2 (Mayor + Imp), which triggers evil win (final two with demon)!
        self.assertEqual(engine.state.winner, Alignment.EVIL)
        self.assertEqual(engine.state.end_reason, "demon_in_final_two")

    def test_mayor_dead_does_not_win(self):
        """Dead Mayor cannot trigger 3-alive victory."""
        roles = [RoleId.MAYOR, RoleId.CHEF, RoleId.WASHERWOMAN, RoleId.IMP]
        setup = make_custom_setup(roles)
        engine = ClocktowerEngine.create(custom_setup=setup)

        # Kill Mayor P01
        engine.state.kill_player("P01", DeathReason.DEMON_KILL)
        # 3 alive: P02, P03, P04
        self.assertEqual(engine.state.alive_count, 3)

        engine.start_day()
        executed = engine.end_day()
        self.assertIsNone(executed)
        self.assertIsNone(engine.state.winner)  # Game continues!

    def test_mayor_drunk_or_poisoned_does_not_win(self):
        """Drunk or poisoned Mayor cannot trigger 3-alive victory."""
        roles = [RoleId.MAYOR, RoleId.CHEF, RoleId.IMP]
        setup = make_custom_setup(roles)
        engine = ClocktowerEngine.create(custom_setup=setup)

        # Poison Mayor P01
        engine.state.add_ongoing_effect("POISON", source_player=None, target_player="P01", expires_at="permanent")

        engine.start_day()
        executed = engine.end_day()
        self.assertIsNone(executed)
        self.assertIsNone(engine.state.winner)

    def test_mayor_bounce_at_night_kills_other_player(self):
        """Imp attacks Mayor, Mayor bounce targets Chef P02 -> Chef dies instead of Mayor."""
        roles = [RoleId.MAYOR, RoleId.CHEF, RoleId.IMP]
        setup = make_custom_setup(roles)
        engine = ClocktowerEngine.create(custom_setup=setup)

        killed = engine.run_night(imp_target="P01", mayor_bounce_target="P02")
        self.assertIn("P02", killed)
        self.assertNotIn("P01", killed)
        self.assertTrue(engine.state.alive["P01"])
        self.assertFalse(engine.state.alive["P02"])

    def test_mayor_bounce_to_soldier_or_monk_protected_causes_no_death(self):
        """Mayor bounce to Soldier P02 -> Soldier immune -> NO death!"""
        roles = [RoleId.MAYOR, RoleId.SOLDIER, RoleId.IMP]
        setup = make_custom_setup(roles)
        engine = ClocktowerEngine.create(custom_setup=setup)

        killed = engine.run_night(imp_target="P01", mayor_bounce_target="P02")
        self.assertEqual(len(killed), 0)
        self.assertTrue(engine.state.alive["P01"])
        self.assertTrue(engine.state.alive["P02"])


if __name__ == "__main__":
    unittest.main()
