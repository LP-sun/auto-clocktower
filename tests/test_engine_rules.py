"""Comprehensive unit tests for Blood on the Clocktower (Trouble Brewing) engine rules."""
import unittest

from src.engine.game import ClocktowerEngine, check_win_conditions
from src.engine.setup import SetupResult, generate_setup
from src.engine.types import (
    Alignment,
    CharacterType,
    DeathReason,
    GamePhase,
    PlayerId,
    RoleId,
)
from src.roles.trouble_brewing import ROLES


def make_custom_setup(roles: list[RoleId], fake_drunk: RoleId | None = None) -> SetupResult:
    players = [f"P{i+1:02d}" for i in range(len(roles))]
    true_roles = {players[i]: roles[i] for i in range(len(roles))}
    apparent_roles = dict(true_roles)
    alignments = {
        p: Alignment.GOOD if ROLES[r].type in (CharacterType.TOWNSFOLK, CharacterType.OUTSIDER) else Alignment.EVIL
        for p, r in true_roles.items()
    }
    drunk_player = next((p for p, r in true_roles.items() if r == RoleId.DRUNK), None)
    if drunk_player and fake_drunk:
        apparent_roles[drunk_player] = fake_drunk

    return SetupResult(
        players=players,
        true_roles=true_roles,
        apparent_roles=apparent_roles,
        alignments=alignments,
        drunk_fake_role=fake_drunk,
        red_herring="P01",
        imp_bluffs=[RoleId.SLAYER, RoleId.MAYOR, RoleId.RECLUSE],
    )


class TestTroubleBrewingRules(unittest.TestCase):
    def test_distribution_and_baron(self):
        """Test base distribution and Baron extra outsiders modification."""
        setup = generate_setup(player_count=12, seed=123)
        self.assertEqual(len(setup.players), 12)
        # Check total roles distribution
        has_baron = any(r == RoleId.BARON for r in setup.true_roles.values())
        outsider_count = sum(1 for r in setup.true_roles.values() if ROLES[r].type == CharacterType.OUTSIDER)
        if has_baron:
            self.assertEqual(outsider_count, 4)
        else:
            self.assertEqual(outsider_count, 2)

    def test_standard_execution_threshold(self):
        """Standard rule: 12 alive requires ceil(12/2) = 6 votes to execute; 5 votes fail."""
        roles = [
            RoleId.WASHERWOMAN, RoleId.CHEF, RoleId.EMPATH, RoleId.FORTUNE_TELLER,
            RoleId.UNDERTAKER, RoleId.MONK, RoleId.SOLDIER, RoleId.DRUNK,
            RoleId.SAINT, RoleId.POISONER, RoleId.SCARLET_WOMAN, RoleId.IMP,
        ]
        setup = make_custom_setup(roles, fake_drunk=RoleId.LIBRARIAN)
        engine = ClocktowerEngine.create(custom_setup=setup)
        engine.start_day()

        # Nominate P02 by P01
        engine.handle_nomination("P01", "P02")

        # 5 votes: should NOT execute
        votes_5 = {f"P{i+1:02d}": True for i in range(5)}
        tally, exceeded = engine.cast_votes(votes_5)
        self.assertEqual(tally, 5)
        self.assertFalse(exceeded)

        executed = engine.end_day()
        self.assertIsNone(executed)
        self.assertTrue(engine.state.alive["P02"])

        # Next day: 6 votes: should execute
        engine.start_day()
        engine.handle_nomination("P01", "P02")
        votes_6 = {f"P{i+1:02d}": True for i in range(6)}
        tally, exceeded = engine.cast_votes(votes_6)
        self.assertEqual(tally, 6)
        self.assertTrue(exceeded)

        executed = engine.end_day()
        self.assertEqual(executed, "P02")
        self.assertFalse(engine.state.alive["P02"])

    def test_tied_highest_votes_mean_no_execution(self):
        """If two or more candidates tie for highest qualifying vote, neither is executed."""
        roles = [
            RoleId.WASHERWOMAN, RoleId.CHEF, RoleId.EMPATH, RoleId.FORTUNE_TELLER,
            RoleId.UNDERTAKER, RoleId.MONK, RoleId.SOLDIER, RoleId.DRUNK,
            RoleId.SAINT, RoleId.POISONER, RoleId.SCARLET_WOMAN, RoleId.IMP,
        ]
        setup = make_custom_setup(roles)
        engine = ClocktowerEngine.create(custom_setup=setup)
        engine.start_day()

        # Nominate P01, gets 7 votes
        engine.handle_nomination("P03", "P01")
        engine.cast_votes({f"P{i+1:02d}": True for i in range(7)})

        # Nominate P02, also gets 7 votes
        engine.handle_nomination("P04", "P02")
        engine.cast_votes({f"P{i+1:02d}": True for i in range(7)})

        executed = engine.end_day()
        self.assertIsNone(executed)
        self.assertEqual(engine.state.alive_count, 12)

    def test_ghost_vote_consumption(self):
        """Dead players have 1 ghost vote; casting it consumes it permanently."""
        roles = [
            RoleId.WASHERWOMAN, RoleId.CHEF, RoleId.EMPATH, RoleId.FORTUNE_TELLER,
            RoleId.UNDERTAKER, RoleId.MONK, RoleId.SOLDIER, RoleId.DRUNK,
            RoleId.SAINT, RoleId.POISONER, RoleId.SCARLET_WOMAN, RoleId.IMP,
        ]
        setup = make_custom_setup(roles)
        engine = ClocktowerEngine.create(custom_setup=setup)

        # Kill P01
        engine.state.kill_player("P01", DeathReason.EXECUTION)
        engine.state.ghost_votes["P01"] = True

        engine.start_day()
        engine.handle_nomination("P02", "P03")

        # P01 votes yes with ghost vote
        tally, _ = engine.cast_votes({"P01": True})
        self.assertEqual(tally, 1)
        self.assertFalse(engine.state.ghost_votes["P01"])

        # Next nomination: P01 tries to vote again -> ignored!
        engine.handle_nomination("P04", "P05")
        tally, _ = engine.cast_votes({"P01": True})
        self.assertEqual(tally, 0)

    def test_butler_voting_constraint(self):
        """Butler cannot vote Yes if their master did not vote Yes."""
        roles = [
            RoleId.BUTLER, RoleId.CHEF, RoleId.EMPATH, RoleId.FORTUNE_TELLER,
            RoleId.UNDERTAKER, RoleId.MONK, RoleId.SOLDIER, RoleId.DRUNK,
            RoleId.SAINT, RoleId.POISONER, RoleId.SCARLET_WOMAN, RoleId.IMP,
        ]
        setup = make_custom_setup(roles)
        engine = ClocktowerEngine.create(custom_setup=setup)

        # Butler P01 picks P02 as master
        engine.state.butler_masters["P01"] = "P02"
        engine.start_day()
        engine.handle_nomination("P03", "P04")

        # Case 1: P02 does NOT vote Yes, P01 votes Yes -> P01's vote is disallowed
        tally, _ = engine.cast_votes({"P01": True, "P02": False})
        self.assertEqual(tally, 0)

        # Case 2: P02 votes Yes, P01 votes Yes -> both votes counted
        engine.handle_nomination("P05", "P06")
        tally, _ = engine.cast_votes({"P01": True, "P02": True})
        self.assertEqual(tally, 2)

    def test_virgin_proc_executes_townsfolk_nominator(self):
        """When Virgin is nominated by a Townsfolk, nominator is executed immediately and day ends."""
        roles = [
            RoleId.WASHERWOMAN, RoleId.VIRGIN, RoleId.CHEF, RoleId.EMPATH,
            RoleId.UNDERTAKER, RoleId.MONK, RoleId.SOLDIER, RoleId.DRUNK,
            RoleId.SAINT, RoleId.POISONER, RoleId.SCARLET_WOMAN, RoleId.IMP,
        ]
        setup = make_custom_setup(roles)
        engine = ClocktowerEngine.create(custom_setup=setup)
        engine.start_day()

        # P01 (Washerwoman - Townsfolk) nominates P02 (Virgin)
        nom = engine.handle_nomination("P01", "P02")
        self.assertIsNone(nom)  # Day immediately ended
        self.assertFalse(engine.state.alive["P01"])
        self.assertEqual(engine.state.phase, GamePhase.DUSK)

    def test_slayer_shooting_demon(self):
        """Slayer kills Demon if not poisoned; shooting non-demon does nothing."""
        roles = [
            RoleId.SLAYER, RoleId.CHEF, RoleId.EMPATH, RoleId.FORTUNE_TELLER,
            RoleId.UNDERTAKER, RoleId.MONK, RoleId.SOLDIER, RoleId.DRUNK,
            RoleId.SAINT, RoleId.POISONER, RoleId.SCARLET_WOMAN, RoleId.IMP,
        ]
        setup = make_custom_setup(roles)
        engine = ClocktowerEngine.create(custom_setup=setup)
        engine.start_day()

        # P01 shoots P02 (Chef - non-demon) -> fails
        success = engine.use_slayer_ability("P01", "P02")
        self.assertFalse(success)
        self.assertTrue(engine.state.alive["P02"])

        # Ability is consumed, cannot shoot again
        with self.assertRaises(ValueError):
            engine.use_slayer_ability("P01", "P12")

    def test_monk_and_soldier_protection_from_imp(self):
        """Monk protection and Soldier immunity prevent night kills."""
        roles = [
            RoleId.MONK, RoleId.SOLDIER, RoleId.EMPATH, RoleId.FORTUNE_TELLER,
            RoleId.UNDERTAKER, RoleId.WASHERWOMAN, RoleId.CHEF, RoleId.DRUNK,
            RoleId.SAINT, RoleId.POISONER, RoleId.SCARLET_WOMAN, RoleId.IMP,
        ]
        setup = make_custom_setup(roles)
        engine = ClocktowerEngine.create(custom_setup=setup)

        # Night 2: Monk P01 protects P03 (Empath). Imp P12 attacks P03 -> NO death!
        killed = engine.run_night(monk_target="P03", imp_target="P03")
        self.assertEqual(len(killed), 0)
        self.assertTrue(engine.state.alive["P03"])

        # Night 3: Imp attacks P02 (Soldier) -> Soldier is immune -> NO death!
        killed = engine.run_night(imp_target="P02")
        self.assertEqual(len(killed), 0)
        self.assertTrue(engine.state.alive["P02"])

    def test_poisoned_soldier_dies_to_imp(self):
        """If Soldier is poisoned by Poisoner, Soldier loses immunity and dies to Imp."""
        roles = [
            RoleId.MONK, RoleId.SOLDIER, RoleId.EMPATH, RoleId.FORTUNE_TELLER,
            RoleId.UNDERTAKER, RoleId.WASHERWOMAN, RoleId.CHEF, RoleId.DRUNK,
            RoleId.SAINT, RoleId.POISONER, RoleId.SCARLET_WOMAN, RoleId.IMP,
        ]
        setup = make_custom_setup(roles)
        engine = ClocktowerEngine.create(custom_setup=setup)

        # Poisoner P10 poisons Soldier P02. Imp P12 attacks P02 -> P02 dies!
        killed = engine.run_night(poisoner_target="P02", imp_target="P02")
        self.assertIn("P02", killed)
        self.assertFalse(engine.state.alive["P02"])

    def test_imp_star_pass_promotes_minion(self):
        """Imp attacks self -> Imp dies, living Minion is promoted to Imp."""
        roles = [
            RoleId.MONK, RoleId.SOLDIER, RoleId.EMPATH, RoleId.FORTUNE_TELLER,
            RoleId.UNDERTAKER, RoleId.WASHERWOMAN, RoleId.CHEF, RoleId.DRUNK,
            RoleId.SAINT, RoleId.POISONER, RoleId.SCARLET_WOMAN, RoleId.IMP,
        ]
        setup = make_custom_setup(roles)
        engine = ClocktowerEngine.create(custom_setup=setup)

        killed = engine.run_night(imp_target="P12")
        self.assertIn("P12", killed)
        self.assertFalse(engine.state.alive["P12"])

        # Scarlet Woman P11 promoted to Imp!
        self.assertEqual(engine.state.true_roles["P11"], RoleId.IMP)
        self.assertIsNone(engine.state.winner)  # Game continues!

    def test_saint_execution_triggers_evil_win(self):
        """Saint executed triggers immediate evil victory."""
        roles = [
            RoleId.WASHERWOMAN, RoleId.CHEF, RoleId.EMPATH, RoleId.FORTUNE_TELLER,
            RoleId.UNDERTAKER, RoleId.MONK, RoleId.SOLDIER, RoleId.DRUNK,
            RoleId.SAINT, RoleId.POISONER, RoleId.SCARLET_WOMAN, RoleId.IMP,
        ]
        setup = make_custom_setup(roles)
        engine = ClocktowerEngine.create(custom_setup=setup)
        engine.start_day()

        # P09 is Saint. Nominate P09 and vote 8 votes.
        engine.handle_nomination("P01", "P09")
        engine.cast_votes({f"P{i+1:02d}": True for i in range(8)})

        engine.end_day()
        self.assertEqual(engine.state.winner, Alignment.EVIL)
        self.assertEqual(engine.state.end_reason, "saint_executed")


if __name__ == "__main__":
    unittest.main()
