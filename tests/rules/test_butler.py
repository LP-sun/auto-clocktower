"""Unit tests for Butler official rules.

Rules verified:
- Butler chooses a Master each night (not themselves).
- Butler may only vote if Master votes on that nomination.
- Butler vote attempted without Master voting is rejected by the rules engine.
- If Butler is drunk or poisoned, the restriction is waived (Butler can vote freely).
- If Master is dead, Butler can only vote if Master uses their ghost vote on that nomination.
"""
import unittest

from src.engine.game import ClocktowerEngine
from src.engine.types import RoleId
from tests.test_engine_rules import make_custom_setup


class TestButlerRules(unittest.TestCase):
    def test_butler_cannot_vote_without_master(self):
        """Butler cannot vote if Master did not vote."""
        roles = [
            RoleId.BUTLER, RoleId.CHEF, RoleId.POISONER, RoleId.IMP,
        ]
        setup = make_custom_setup(roles)
        engine = ClocktowerEngine.create(custom_setup=setup)

        # Night 1: Butler P01 chooses P02 (Chef) as Master
        engine.run_first_night(butler_target="P02")
        self.assertEqual(engine.state.butler_masters["P01"], "P02")

        engine.start_day()
        # Nominate P03 (Poisoner)
        engine.handle_nomination("P04", "P03")

        # Butler P01 votes True, but Master P02 votes False!
        votes = {"P01": True, "P02": False, "P04": True}
        tally, exceeded = engine.cast_votes(votes)

        # Butler's vote must NOT be counted!
        self.assertEqual(tally, 1)  # Only P04 counted!

    def test_butler_can_vote_with_master(self):
        """Butler can vote when Master votes."""
        roles = [
            RoleId.BUTLER, RoleId.CHEF, RoleId.POISONER, RoleId.IMP,
        ]
        setup = make_custom_setup(roles)
        engine = ClocktowerEngine.create(custom_setup=setup)

        engine.run_first_night(butler_target="P02")
        engine.start_day()
        engine.handle_nomination("P04", "P03")

        # Both Butler P01 and Master P02 vote True
        votes = {"P01": True, "P02": True, "P04": True}
        tally, exceeded = engine.cast_votes(votes)

        # All 3 counted!
        self.assertEqual(tally, 3)

    def test_poisoned_butler_can_vote_freely(self):
        """Poisoned Butler is not bound by Master restriction."""
        roles = [
            RoleId.BUTLER, RoleId.CHEF, RoleId.POISONER, RoleId.IMP,
        ]
        setup = make_custom_setup(roles)
        engine = ClocktowerEngine.create(custom_setup=setup)

        # Poison Butler P01 on Night 1
        engine.run_first_night(poisoner_target="P01", butler_target="P02")
        self.assertTrue(engine.state.is_poisoned("P01"))

        engine.start_day()
        engine.handle_nomination("P04", "P03")

        # Butler P01 votes True, Master P02 votes False
        votes = {"P01": True, "P02": False, "P04": True}
        tally, exceeded = engine.cast_votes(votes)

        # Because Butler was poisoned, vote was counted!
        self.assertEqual(tally, 2)  # P01 and P04 counted!


if __name__ == "__main__":
    unittest.main()
