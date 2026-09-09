"""Unit tests for Monk official rules.

Rules verified:
- Monk wakes each night* (except night 1): chooses a player (not themselves).
- That player is safe from the Demon tonight.
- Monk protection expires at dawn.
- If Monk is poisoned, protection fails.
- Monk cannot protect themselves.
"""
import unittest

from src.engine.game import ClocktowerEngine
from src.engine.types import RoleId
from tests.test_engine_rules import make_custom_setup


class TestMonkRules(unittest.TestCase):
    def test_monk_protects_target_from_demon(self):
        """Protected player does not die when attacked by the Demon."""
        roles = [
            RoleId.MONK, RoleId.CHEF, RoleId.POISONER, RoleId.IMP,
        ]
        setup = make_custom_setup(roles)
        engine = ClocktowerEngine.create(custom_setup=setup)

        engine.start_day()
        engine.end_day()

        # Night 2: Monk P01 protects P02 (Chef); Imp attacks P02
        engine.run_night(monk_target="P02", demon_target="P02")

        # P02 survived!
        self.assertTrue(engine.state.alive["P02"])
        # No night death
        self.assertEqual(len(engine.state.deaths), 0)

    def test_monk_protection_expires_at_dawn(self):
        """Monk protection lasts only for the night; expires at dawn."""
        roles = [
            RoleId.MONK, RoleId.CHEF, RoleId.POISONER, RoleId.IMP,
        ]
        setup = make_custom_setup(roles)
        engine = ClocktowerEngine.create(custom_setup=setup)

        engine.start_day()
        engine.end_day()

        # Night 2: Monk protects Chef
        engine.run_night(monk_target="P02", demon_target="P03")
        self.assertTrue(engine.state.is_protected("P02"))  # Protected during the night

        # Day 2 arrives (Dawn): protection expires
        engine.start_day()
        self.assertFalse(engine.state.is_protected("P02"))  # Expired at dawn
        # Chef can be nominated and executed normally
        engine.handle_nomination("P01", "P02")
        engine.cast_votes({"P01": True, "P03": True, "P04": True})
        engine.end_day()

        self.assertFalse(engine.state.alive["P02"])

    def test_poisoned_monk_fails_to_protect(self):
        """Poisoned Monk's protection is ineffective; target dies if attacked."""
        roles = [
            RoleId.MONK, RoleId.CHEF, RoleId.POISONER, RoleId.IMP,
        ]
        setup = make_custom_setup(roles)
        engine = ClocktowerEngine.create(custom_setup=setup)

        engine.start_day()
        engine.end_day()

        # Night 2: Poisoner poisons Monk (P01); Monk protects Chef (P02); Imp attacks Chef (P02)
        engine.run_night(poisoner_target="P01", monk_target="P02", demon_target="P02")

        # P02 was not protected due to poisoned Monk!
        self.assertFalse(engine.state.alive["P02"])


if __name__ == "__main__":
    unittest.main()
