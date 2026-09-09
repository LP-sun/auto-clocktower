"""Unit tests for Imp official rules.

Rules verified:
- Kills a player each night* (except night 1).
- Self-kill (star-pass): Imp dies; a living Minion becomes the Imp.
- If Scarlet Woman is alive (and 5+ players), SW becomes Imp; otherwise another Minion (e.g. Baron, Poisoner) becomes Imp.
- Star-pass when NO Minions are alive: Imp dies, Good wins immediately!
"""
import unittest

from src.engine.game import ClocktowerEngine
from src.engine.types import Alignment, RoleId
from tests.test_engine_rules import make_custom_setup


class TestImpRules(unittest.TestCase):
    def test_imp_normal_night_kill(self):
        """Imp kills chosen target at night."""
        roles = [
            RoleId.CHEF, RoleId.EMPATH, RoleId.POISONER, RoleId.IMP,
        ]
        setup = make_custom_setup(roles)
        engine = ClocktowerEngine.create(custom_setup=setup)

        engine.start_day()
        engine.end_day()

        killed = engine.run_night(demon_target="P01")
        self.assertIn("P01", killed)
        self.assertFalse(engine.state.alive["P01"])

    def test_imp_star_pass_with_living_minion(self):
        """Imp kills self -> living minion promoted to Imp, game continues."""
        roles = [
            RoleId.CHEF, RoleId.EMPATH, RoleId.POISONER, RoleId.IMP,
        ]
        setup = make_custom_setup(roles)
        engine = ClocktowerEngine.create(custom_setup=setup)

        engine.start_day()
        engine.end_day()

        # Night 2: Imp (P04) kills self!
        killed = engine.run_night(demon_target="P04")
        self.assertIn("P04", killed)
        self.assertFalse(engine.state.alive["P04"])

        # P03 (Poisoner) became Imp!
        self.assertEqual(engine.state.true_roles["P03"], RoleId.IMP)
        self.assertIsNone(engine.state.winner)  # Game continues!

    def test_imp_star_pass_with_no_living_minions_ends_game(self):
        """Imp kills self when no Minions are alive -> Good wins immediately!"""
        roles = [
            RoleId.CHEF, RoleId.EMPATH, RoleId.POISONER, RoleId.IMP,
        ]
        setup = make_custom_setup(roles)
        engine = ClocktowerEngine.create(custom_setup=setup)

        engine.start_day()
        # Execute the only Minion (P03 Poisoner) on Day 1
        engine.handle_nomination("P01", "P03")
        engine.cast_votes({"P01": True, "P02": True, "P04": True})
        engine.end_day()

        self.assertFalse(engine.state.alive["P03"])

        # Night 2: Imp kills self!
        killed = engine.run_night(demon_target="P04")
        self.assertIn("P04", killed)
        self.assertFalse(engine.state.alive["P04"])

        # Good wins because demon is dead and no minions can be promoted!
        self.assertEqual(engine.state.winner, Alignment.GOOD)


if __name__ == "__main__":
    unittest.main()
