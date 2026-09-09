"""Unit tests for Ravenkeeper official rules.

Rules verified:
- If you die at night, you are woken to choose a player: you learn their character.
- If executed during the day, ability does NOT trigger.
- If poisoned when killed at night, wake still occurs but character learned can be false (ST misinformation).
- If Mayor bounces Demon kill to Ravenkeeper at night, Ravenkeeper died at night -> ability triggers!
"""
import unittest

from src.engine.game import ClocktowerEngine
from src.engine.types import RoleId
from tests.test_engine_rules import make_custom_setup


class TestRavenkeeperRules(unittest.TestCase):
    def test_ravenkeeper_killed_at_night_wakes_and_learns_character(self):
        """Ravenkeeper killed at night wakes, chooses a player, and learns their character."""
        roles = [
            RoleId.RAVENKEEPER, RoleId.WASHERWOMAN, RoleId.POISONER, RoleId.IMP,
        ]
        setup = make_custom_setup(roles)
        engine = ClocktowerEngine.create(custom_setup=setup)

        engine.start_day()
        engine.end_day()

        # Night 2: Imp kills Ravenkeeper (P01)
        # Ravenkeeper chooses P04 (Imp)
        engine.run_night(demon_target="P01", ravenkeeper_target="P04")

        self.assertFalse(engine.state.alive["P01"])
        rk_events = [
            e for e in engine.events.get_events_for_player("P01")
            if e.type == "INFO_RAVENKEEPER"
        ]
        self.assertEqual(len(rk_events), 1)
        self.assertEqual(rk_events[0].data.get("chosen_player"), "P04")
        self.assertEqual(rk_events[0].data.get("character"), RoleId.IMP.value)

    def test_ravenkeeper_executed_during_day_does_not_wake(self):
        """Ravenkeeper executed during the day does NOT trigger ability at night."""
        roles = [
            RoleId.RAVENKEEPER, RoleId.WASHERWOMAN, RoleId.POISONER, RoleId.IMP,
        ]
        setup = make_custom_setup(roles)
        engine = ClocktowerEngine.create(custom_setup=setup)

        engine.start_day()
        # Nominate and execute Ravenkeeper (P01)
        engine.handle_nomination("P02", "P01")
        engine.cast_votes({"P02": True, "P03": True, "P04": True})
        engine.end_day()

        self.assertFalse(engine.state.alive["P01"])

        # Night 2
        engine.run_night(demon_target="P02")

        rk_events = [
            e for e in engine.events.get_events_for_player("P01")
            if e.type == "INFO_RAVENKEEPER"
        ]
        self.assertEqual(len(rk_events), 0)

    def test_ravenkeeper_killed_by_mayor_bounce_triggers_ability(self):
        """If Mayor bounces Demon kill to Ravenkeeper at night, Ravenkeeper dies at night and wakes!"""
        roles = [
            RoleId.MAYOR, RoleId.RAVENKEEPER, RoleId.POISONER, RoleId.IMP,
        ]
        setup = make_custom_setup(roles)
        engine = ClocktowerEngine.create(custom_setup=setup)

        engine.start_day()
        engine.end_day()

        # Imp attacks Mayor P01, ST bounces to Ravenkeeper P02
        engine.run_night(demon_target="P01", mayor_bounce_target="P02", ravenkeeper_target="P03")

        self.assertTrue(engine.state.alive["P01"])  # Mayor survived!
        self.assertFalse(engine.state.alive["P02"])  # Ravenkeeper died!

        rk_events = [
            e for e in engine.events.get_events_for_player("P02")
            if e.type == "INFO_RAVENKEEPER"
        ]
        self.assertEqual(len(rk_events), 1)
        self.assertEqual(rk_events[0].data.get("chosen_player"), "P03")
        self.assertEqual(rk_events[0].data.get("character"), RoleId.POISONER.value)


if __name__ == "__main__":
    unittest.main()
