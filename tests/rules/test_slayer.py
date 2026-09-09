"""Rule tests for Slayer: ability once per game, poisoned failure, and Recluse registration."""
import unittest

from src.engine.game import ClocktowerEngine
from src.engine.types import RoleId
from tests.test_engine_rules import make_custom_setup


class MockSTPolicy:
    def __init__(self, recluse_as_demon: bool = True):
        self.recluse_as_demon = recluse_as_demon

    def decide(self, dtype, state, actor=None, suspicions=None, **kwargs):
        if self.recluse_as_demon:
            return {"role": RoleId.IMP, "alignment": "evil"}
        return {"role": RoleId.RECLUSE, "alignment": "good"}


class TestSlayerRules(unittest.TestCase):
    def test_slayer_shoots_demon_kills_demon(self):
        """Slayer shoots Demon -> Demon dies."""
        roles = [RoleId.SLAYER, RoleId.CHEF, RoleId.IMP]
        setup = make_custom_setup(roles)
        engine = ClocktowerEngine.create(custom_setup=setup)
        engine.start_day()

        hit = engine.use_slayer_ability("P01", "P03")
        self.assertTrue(hit)
        self.assertFalse(engine.state.alive["P03"])
        self.assertIn("P01", engine.state.ability_used)

    def test_slayer_shoots_non_demon_spends_ability(self):
        """Slayer shoots Chef (non-demon) -> Chef does not die, ability spent."""
        roles = [RoleId.SLAYER, RoleId.CHEF, RoleId.IMP]
        setup = make_custom_setup(roles)
        engine = ClocktowerEngine.create(custom_setup=setup)
        engine.start_day()

        hit = engine.use_slayer_ability("P01", "P02")
        self.assertFalse(hit)
        self.assertTrue(engine.state.alive["P02"])
        self.assertIn("P01", engine.state.ability_used)

    def test_poisoned_slayer_fails_on_demon(self):
        """Poisoned Slayer shoots Demon -> Demon survives, ability spent."""
        roles = [RoleId.SLAYER, RoleId.CHEF, RoleId.IMP]
        setup = make_custom_setup(roles)
        engine = ClocktowerEngine.create(custom_setup=setup)

        engine.state.add_ongoing_effect("POISON", source_player=None, target_player="P01", expires_at="permanent")

        engine.start_day()
        hit = engine.use_slayer_ability("P01", "P03")
        self.assertFalse(hit)
        self.assertTrue(engine.state.alive["P03"])
        self.assertIn("P01", engine.state.ability_used)

    def test_slayer_shoots_recluse_registered_as_demon(self):
        """Slayer shoots Recluse, ST registers Recluse as Demon -> Recluse dies."""
        roles = [RoleId.SLAYER, RoleId.RECLUSE, RoleId.IMP]
        setup = make_custom_setup(roles)
        engine = ClocktowerEngine.create(custom_setup=setup)
        engine.start_day()

        st = MockSTPolicy(recluse_as_demon=True)
        hit = engine.use_slayer_ability("P01", "P02", st_policy=st)
        self.assertTrue(hit)
        self.assertFalse(engine.state.alive["P02"])


if __name__ == "__main__":
    unittest.main()
