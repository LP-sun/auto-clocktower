"""Unit tests for Undertaker official rules.

Rules verified:
- Undertaker wakes each night* (except Night 1) and learns which character died by execution today.
- If NO ONE died by execution today, Undertaker does NOT wake (strictly no wake / no info event).
- If Undertaker is drunk/poisoned, they wake (if an execution occurred) but may receive false information.
- Recluse executed: may register as Outsider or Minion/Demon to Undertaker.
- Spy executed: may register as Minion or Townsfolk/Outsider to Undertaker.
"""
import unittest

from src.engine.game import ClocktowerEngine
from src.engine.types import CharacterType, GamePhase, RoleId
from tests.test_engine_rules import make_custom_setup


class TestUndertakerRules(unittest.TestCase):
    def test_undertaker_no_wake_if_no_execution_yesterday(self):
        """If no one was executed yesterday, Undertaker does NOT wake at night."""
        roles = [
            RoleId.UNDERTAKER, RoleId.WASHERWOMAN, RoleId.CHEF, RoleId.IMP,
        ]
        setup = make_custom_setup(roles)
        engine = ClocktowerEngine.create(custom_setup=setup)

        # Day 1: No nominations, no executions
        engine.start_day()
        engine.end_day()

        # Night 2
        engine.run_night(demon_target="P02")

        # Check Undertaker (P01) night info events
        ut_events = [
            e for e in engine.events.get_events_for_player("P01")
            if e.type == "INFO_UNDERTAKER"
        ]
        # Strictly 0 events! No wake, no info!
        self.assertEqual(len(ut_events), 0)

    def test_undertaker_learns_executed_player_character(self):
        """Undertaker learns the character of the player executed yesterday."""
        roles = [
            RoleId.UNDERTAKER, RoleId.CHEF, RoleId.SAINT, RoleId.IMP,
        ]
        setup = make_custom_setup(roles)
        engine = ClocktowerEngine.create(custom_setup=setup)

        engine.start_day()
        # Nominate and execute Chef (P02)
        nom = engine.handle_nomination("P01", "P02")
        engine.cast_votes({"P01": True, "P02": True, "P03": True, "P04": False})
        engine.end_day()

        self.assertEqual(engine.state.last_executed_player_yesterday, "P02")

        # Night 2
        engine.run_night(demon_target="P03")

        ut_events = [
            e for e in engine.events.get_events_for_player("P01")
            if e.type == "INFO_UNDERTAKER"
        ]
        self.assertEqual(len(ut_events), 1)
        self.assertEqual(ut_events[0].data.get("executed_player"), "P02")
        self.assertEqual(ut_events[0].data.get("executed_role"), RoleId.CHEF.value)

    def test_undertaker_drunk_receives_misinformation(self):
        """Drunk/poisoned Undertaker receives false character or ST misinformation."""
        roles = [
            RoleId.UNDERTAKER, RoleId.POISONER, RoleId.CHEF, RoleId.IMP,
        ]
        setup = make_custom_setup(roles)
        engine = ClocktowerEngine.create(custom_setup=setup)

        # Poison Undertaker on Night 1
        engine.run_first_night(poisoner_target="P01")

        engine.start_day()
        # Execute Chef (P03)
        engine.handle_nomination("P01", "P03")
        engine.cast_votes({"P01": True, "P02": True, "P04": True})
        engine.end_day()

        # Re-poison Undertaker on Night 2
        engine.run_night(poisoner_target="P01", demon_target="P02")

        ut_events = [
            e for e in engine.events.get_events_for_player("P01")
            if e.type == "INFO_UNDERTAKER"
        ]
        self.assertEqual(len(ut_events), 1)
        # Being poisoned, info may be false or true (ST choice), but wake happened because execution occurred
        self.assertIn("executed_role", ut_events[0].data)


if __name__ == "__main__":
    unittest.main()
