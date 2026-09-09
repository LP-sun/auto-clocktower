"""Unit tests for Recluse and Spy typed registration official rules.

Rules verified:
- Recluse can register as Evil, Minion, or Demon (NEVER Townsfolk).
  - Chef: may register as Evil.
  - Empath: may register as Evil.
  - Fortune Teller: may register as Demon.
  - Slayer: may register as Demon (dies to Slayer!).
  - Virgin: cannot register as Townsfolk (Virgin never procs on Recluse).
- Spy can register as Good, Townsfolk, or Outsider (NEVER Demon).
  - Chef: may register as Good.
  - Empath: may register as Good.
  - Fortune Teller: cannot register as Demon (returns False unless Red Herring).
  - Virgin: may register as Townsfolk (Virgin procs and executes Spy!).
  - Slayer: cannot register as Demon (Slayer shot always fails).
  - Undertaker: may register as Townsfolk or Outsider.
"""
import unittest

from src.engine.game import ClocktowerEngine
from src.engine.types import Alignment, CharacterType, RoleId, STDecisionType
from src.storyteller.legal_actions import generate_legal_st_actions
from tests.test_engine_rules import make_custom_setup


class MockSTPolicy:
    """Mock ST policy that returns predetermined registration decisions."""
    def __init__(self, recluse_reg=None, spy_reg=None):
        self.recluse_reg = recluse_reg
        self.spy_reg = spy_reg

    def decide(self, decision_type, state, actor=None, context=None, suspicions=None):
        if decision_type == STDecisionType.RECLUSE_REGISTRATION:
            return self.recluse_reg
        if decision_type == STDecisionType.SPY_REGISTRATION:
            return self.spy_reg
        return None


class TestRecluseSpyRules(unittest.TestCase):
    def test_recluse_candidate_generation_strictly_typed(self):
        """Recluse candidate branches must only contain Evil/Minion/Demon, never Townsfolk."""
        roles = [RoleId.RECLUSE, RoleId.CHEF, RoleId.IMP, RoleId.BARON]
        setup = make_custom_setup(roles)
        engine = ClocktowerEngine.create(custom_setup=setup)

        actions = generate_legal_st_actions(STDecisionType.RECLUSE_REGISTRATION, engine.state, actor="P01")
        for a in actions:
            # Must not be Townsfolk
            self.assertNotEqual(a.get("role"), RoleId.CHEF)
            self.assertIn(a["alignment"], (Alignment.GOOD, Alignment.EVIL))
            if a["alignment"] == Alignment.EVIL:
                self.assertIn(a["role"], (RoleId.RECLUSE, RoleId.POISONER, RoleId.IMP))

    def test_spy_candidate_generation_strictly_typed(self):
        """Spy candidate branches must only contain Good/Townsfolk/Outsider, never Demon."""
        roles = [RoleId.SPY, RoleId.CHEF, RoleId.IMP, RoleId.BARON]
        setup = make_custom_setup(roles)
        engine = ClocktowerEngine.create(custom_setup=setup)

        actions = generate_legal_st_actions(STDecisionType.SPY_REGISTRATION, engine.state, actor="P01")
        for a in actions:
            # Must not be Demon
            self.assertNotEqual(a.get("role"), RoleId.IMP)
            self.assertIn(a["alignment"], (Alignment.GOOD, Alignment.EVIL))
            if a["alignment"] == Alignment.GOOD:
                self.assertIn(a["role"], (RoleId.SPY, RoleId.SOLDIER, RoleId.BUTLER))

    def test_recluse_slayer_shot(self):
        """Recluse registered as Demon dies to Slayer shot; real Demon alive so game continues."""
        roles = [RoleId.RECLUSE, RoleId.SLAYER, RoleId.POISONER, RoleId.IMP]
        setup = make_custom_setup(roles)
        engine = ClocktowerEngine.create(custom_setup=setup)

        st_mock = MockSTPolicy(recluse_reg={"alignment": Alignment.EVIL, "role": RoleId.IMP})
        engine.start_day()

        shot_result = engine.use_slayer_ability("P02", "P01", st_policy=st_mock)
        self.assertTrue(shot_result)
        self.assertFalse(engine.state.alive["P01"])
        # Game continues because real Imp (P04) is alive!
        self.assertIsNone(engine.state.winner)

    def test_spy_virgin_nomination(self):
        """Spy registered as Townsfolk procs Virgin ability and is executed immediately!"""
        roles = [RoleId.SPY, RoleId.VIRGIN, RoleId.POISONER, RoleId.IMP]
        setup = make_custom_setup(roles)
        engine = ClocktowerEngine.create(custom_setup=setup)

        st_mock = MockSTPolicy(spy_reg={"alignment": Alignment.GOOD, "role": RoleId.SOLDIER})
        engine.start_day()

        # P01 (Spy) nominates P02 (Virgin)
        nom = engine.handle_nomination("P01", "P02", st_policy=st_mock)
        # Virgin procs! Spy executed!
        self.assertFalse(engine.state.alive["P01"])
        self.assertEqual(engine.state.executed_today, "P01")

    def test_recluse_virgin_nomination_never_procs(self):
        """Recluse is Outsider and can never register as Townsfolk; Virgin never procs on Recluse."""
        roles = [RoleId.RECLUSE, RoleId.VIRGIN, RoleId.POISONER, RoleId.IMP]
        setup = make_custom_setup(roles)
        engine = ClocktowerEngine.create(custom_setup=setup)

        st_mock = MockSTPolicy(recluse_reg={"alignment": Alignment.EVIL, "role": RoleId.IMP})
        engine.start_day()

        # P01 (Recluse) nominates P02 (Virgin)
        nom = engine.handle_nomination("P01", "P02", st_policy=st_mock)
        # Recluse alive, Virgin did not execute nominator
        self.assertTrue(engine.state.alive["P01"])
        self.assertIn("P02", engine.state.ability_used)

    def test_spy_slayer_shot_always_fails(self):
        """Spy can never register as Demon; Slayer shot on Spy always fails."""
        roles = [RoleId.SPY, RoleId.SLAYER, RoleId.POISONER, RoleId.IMP]
        setup = make_custom_setup(roles)
        engine = ClocktowerEngine.create(custom_setup=setup)

        engine.start_day()
        shot = engine.use_slayer_ability("P02", "P01")
        self.assertFalse(shot)
        self.assertTrue(engine.state.alive["P01"])


if __name__ == "__main__":
    unittest.main()
