"""Rule tests for Scarlet Woman: 5-alive pre-death threshold and off-by-one verification."""
import unittest

from src.engine.game import ClocktowerEngine
from src.engine.types import Alignment, DeathReason, RoleId
from tests.test_engine_rules import make_custom_setup


class TestScarletWomanRules(unittest.TestCase):
    def test_five_alive_before_demon_death_transforms(self):
        """When Demon dies with exactly 5 alive immediately before death, Scarlet Woman transforms into Imp."""
        roles = [
            RoleId.WASHERWOMAN, RoleId.CHEF, RoleId.EMPATH,
            RoleId.SCARLET_WOMAN, RoleId.IMP,
        ]
        setup = make_custom_setup(roles)
        engine = ClocktowerEngine.create(custom_setup=setup)
        self.assertEqual(engine.state.alive_count, 5)

        # Execute Demon P05: alive count immediately before death was 5
        engine.start_day()
        engine.handle_nomination("P01", "P05")
        engine.cast_votes({"P01": True, "P02": True, "P03": True})
        engine.end_day()

        self.assertFalse(engine.state.alive["P05"])
        # Scarlet Woman P04 was promoted!
        self.assertEqual(engine.state.true_roles["P04"], RoleId.IMP)
        self.assertIsNone(engine.state.winner)  # Game continues!

    def test_four_alive_before_demon_death_does_not_transform(self):
        """When Demon dies with 4 alive immediately before death, SW does NOT transform -> Good wins!"""
        roles = [
            RoleId.WASHERWOMAN, RoleId.CHEF,
            RoleId.SCARLET_WOMAN, RoleId.IMP,
        ]
        setup = make_custom_setup(roles)
        engine = ClocktowerEngine.create(custom_setup=setup)
        self.assertEqual(engine.state.alive_count, 4)

        # Execute Demon P04
        engine.start_day()
        engine.handle_nomination("P01", "P04")
        engine.cast_votes({"P01": True, "P02": True})
        engine.end_day()

        self.assertFalse(engine.state.alive["P04"])
        # SW P03 does NOT transform
        self.assertEqual(engine.state.true_roles["P03"], RoleId.SCARLET_WOMAN)
        self.assertEqual(engine.state.winner, Alignment.GOOD)
        self.assertEqual(engine.state.end_reason, "imp_dead")

    def test_poisoned_scarlet_woman_does_not_transform(self):
        """Poisoned Scarlet Woman cannot transform even if 5 players were alive."""
        roles = [
            RoleId.WASHERWOMAN, RoleId.CHEF, RoleId.EMPATH,
            RoleId.SCARLET_WOMAN, RoleId.IMP,
        ]
        setup = make_custom_setup(roles)
        engine = ClocktowerEngine.create(custom_setup=setup)

        # Poison SW P04
        engine.state.add_ongoing_effect("POISON", source_player=None, target_player="P04", expires_at="permanent")

        # Execute Demon P05
        engine.start_day()
        engine.handle_nomination("P01", "P05")
        engine.cast_votes({"P01": True, "P02": True, "P03": True})
        engine.end_day()

        self.assertEqual(engine.state.true_roles["P04"], RoleId.SCARLET_WOMAN)
        self.assertEqual(engine.state.winner, Alignment.GOOD)


if __name__ == "__main__":
    unittest.main()
