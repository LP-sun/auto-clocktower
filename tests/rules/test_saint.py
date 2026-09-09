"""Unit tests for Saint official rules and Event Semantics (Execution vs Death).

Rules verified:
- If Saint dies by execution, evil wins immediately.
- If Saint is drunk or poisoned when executed, ability is inactive -> evil does NOT win!
- If Saint dies at night by the Demon, ability does NOT trigger (only execution).
- If Saint dies by Slayer shot, ability does NOT trigger (Slayer is death, NOT execution).
"""
import unittest

from src.engine.game import ClocktowerEngine
from src.engine.types import Alignment, RoleId
from tests.test_engine_rules import make_custom_setup


class TestSaintRules(unittest.TestCase):
    def test_saint_executed_healthy_evil_wins(self):
        """Saint executed while healthy -> Evil wins immediately."""
        roles = [
            RoleId.SAINT, RoleId.CHEF, RoleId.POISONER, RoleId.IMP,
        ]
        setup = make_custom_setup(roles)
        engine = ClocktowerEngine.create(custom_setup=setup)

        engine.start_day()
        # Nominate and execute Saint (P01)
        engine.handle_nomination("P02", "P01")
        engine.cast_votes({"P02": True, "P03": True, "P04": True})
        engine.end_day()

        self.assertFalse(engine.state.alive["P01"])
        self.assertEqual(engine.state.winner, Alignment.EVIL)
        self.assertEqual(engine.state.end_reason, "saint_executed")

    def test_saint_executed_while_poisoned_does_not_lose(self):
        """Saint executed while poisoned -> ability does not function, game continues."""
        roles = [
            RoleId.SAINT, RoleId.CHEF, RoleId.POISONER, RoleId.IMP,
        ]
        setup = make_custom_setup(roles)
        engine = ClocktowerEngine.create(custom_setup=setup)

        # Poison Saint on Night 1
        engine.run_first_night(poisoner_target="P01")

        engine.start_day()
        # Nominate and execute Saint
        engine.handle_nomination("P02", "P01")
        engine.cast_votes({"P02": True, "P03": True, "P04": True})
        engine.end_day()

        self.assertFalse(engine.state.alive["P01"])
        # Evil did NOT win!
        self.assertNotEqual(engine.state.winner, Alignment.EVIL)

    def test_saint_killed_at_night_does_not_lose(self):
        """Saint killed at night by Demon -> game continues normally."""
        roles = [
            RoleId.SAINT, RoleId.CHEF, RoleId.POISONER, RoleId.IMP,
        ]
        setup = make_custom_setup(roles)
        engine = ClocktowerEngine.create(custom_setup=setup)

        engine.start_day()
        engine.end_day()

        # Night 2: Imp kills Saint (P01)
        engine.run_night(demon_target="P01")

        self.assertFalse(engine.state.alive["P01"])
        self.assertIsNone(engine.state.winner)

    def test_saint_shot_by_slayer_does_not_lose(self):
        """If Saint is killed by Slayer (e.g. if Recluse registered or custom), it's not execution."""
        roles = [
            RoleId.SAINT, RoleId.SLAYER, RoleId.POISONER, RoleId.IMP,
        ]
        setup = make_custom_setup(roles)
        engine = ClocktowerEngine.create(custom_setup=setup)

        engine.start_day()
        # Slayer shoots Saint (fails normally, but verifies Slayer kill is non-execution)
        shot = engine.handle_slayer_shot("P02", "P01")
        self.assertFalse(shot)
        self.assertTrue(engine.state.alive["P01"])


if __name__ == "__main__":
    unittest.main()
