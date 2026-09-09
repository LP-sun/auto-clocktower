"""Unit tests verifying strict perceptual isolation and information boundaries."""
import unittest

from src.cognition.observation import observe
from src.engine.game import ClocktowerEngine
from src.engine.setup import SetupResult
from src.engine.types import Alignment, CharacterType, RoleId
from src.roles.trouble_brewing import ROLES


class TestInformationIsolation(unittest.TestCase):
    def test_drunk_perceives_fake_townsfolk(self):
        """Drunk must observe their fake townsfolk role and Good alignment, never 'drunk'."""
        roles = [
            RoleId.WASHERWOMAN, RoleId.CHEF, RoleId.EMPATH, RoleId.FORTUNE_TELLER,
            RoleId.UNDERTAKER, RoleId.MONK, RoleId.SOLDIER, RoleId.DRUNK,
            RoleId.SAINT, RoleId.POISONER, RoleId.SCARLET_WOMAN, RoleId.IMP,
        ]
        players = [f"P{i+1:02d}" for i in range(12)]
        true_roles = {players[i]: roles[i] for i in range(12)}
        apparent_roles = dict(true_roles)
        apparent_roles["P08"] = RoleId.INVESTIGATOR  # Drunk thinks they are Investigator

        alignments = {
            p: Alignment.GOOD if ROLES[r].type in (CharacterType.TOWNSFOLK, CharacterType.OUTSIDER) else Alignment.EVIL
            for p, r in true_roles.items()
        }

        setup = SetupResult(
            players=players,
            true_roles=true_roles,
            apparent_roles=apparent_roles,
            alignments=alignments,
            drunk_fake_role=RoleId.INVESTIGATOR,
            red_herring="P01",
            imp_bluffs=[RoleId.SLAYER, RoleId.MAYOR, RoleId.RECLUSE],
        )

        engine = ClocktowerEngine.create(custom_setup=setup)
        obs_drunk = observe(engine.state, "P08")

        self.assertEqual(obs_drunk.self_role, RoleId.INVESTIGATOR)
        self.assertNotEqual(obs_drunk.self_role, RoleId.DRUNK)
        self.assertEqual(obs_drunk.self_alignment, Alignment.GOOD)

    def test_good_player_cannot_see_evil_team_or_grimoire(self):
        """Good players must not have access to evil team info or hidden roles of others."""
        roles = [
            RoleId.WASHERWOMAN, RoleId.CHEF, RoleId.EMPATH, RoleId.FORTUNE_TELLER,
            RoleId.UNDERTAKER, RoleId.MONK, RoleId.SOLDIER, RoleId.DRUNK,
            RoleId.SAINT, RoleId.POISONER, RoleId.SCARLET_WOMAN, RoleId.IMP,
        ]
        players = [f"P{i+1:02d}" for i in range(12)]
        true_roles = {players[i]: roles[i] for i in range(12)}
        apparent_roles = dict(true_roles)
        alignments = {
            p: Alignment.GOOD if ROLES[r].type in (CharacterType.TOWNSFOLK, CharacterType.OUTSIDER) else Alignment.EVIL
            for p, r in true_roles.items()
        }

        setup = SetupResult(
            players=players,
            true_roles=true_roles,
            apparent_roles=apparent_roles,
            alignments=alignments,
            drunk_fake_role=RoleId.LIBRARIAN,
            red_herring="P01",
            imp_bluffs=[RoleId.SLAYER, RoleId.MAYOR, RoleId.RECLUSE],
        )

        engine = ClocktowerEngine.create(custom_setup=setup)
        engine.run_first_night(poisoner_target="P01")

        # P01 (Washerwoman)
        obs = observe(engine.state, "P01")
        self.assertIsNone(obs.evil_team_knowledge)
        # Verify obs dict has no leak of true_roles or poisoned status
        obs_dict = obs.to_dict()
        self.assertNotIn("true_roles", obs_dict)
        self.assertNotIn("poisoned", obs_dict)
        self.assertNotIn("drunk", obs_dict)
        self.assertNotIn("red_herring", obs_dict)

        # Poisoner P10 has evil knowledge
        obs_evil = observe(engine.state, "P10")
        self.assertIsNotNone(obs_evil.evil_team_knowledge)
        self.assertEqual(obs_evil.evil_team_knowledge["demon"], "P12")

    def test_private_info_routing_isolation(self):
        """Private night info sent to P02 must NOT appear in P03's observation."""
        roles = [
            RoleId.WASHERWOMAN, RoleId.CHEF, RoleId.EMPATH, RoleId.FORTUNE_TELLER,
            RoleId.UNDERTAKER, RoleId.MONK, RoleId.SOLDIER, RoleId.DRUNK,
            RoleId.SAINT, RoleId.POISONER, RoleId.SCARLET_WOMAN, RoleId.IMP,
        ]
        players = [f"P{i+1:02d}" for i in range(12)]
        true_roles = {players[i]: roles[i] for i in range(12)}
        apparent_roles = dict(true_roles)
        alignments = {
            p: Alignment.GOOD if ROLES[r].type in (CharacterType.TOWNSFOLK, CharacterType.OUTSIDER) else Alignment.EVIL
            for p, r in true_roles.items()
        }

        setup = SetupResult(
            players=players,
            true_roles=true_roles,
            apparent_roles=apparent_roles,
            alignments=alignments,
            drunk_fake_role=RoleId.LIBRARIAN,
            red_herring="P01",
            imp_bluffs=[RoleId.SLAYER, RoleId.MAYOR, RoleId.RECLUSE],
        )

        engine = ClocktowerEngine.create(custom_setup=setup)
        engine.run_first_night()

        obs_chef = observe(engine.state, "P02")
        obs_empath = observe(engine.state, "P03")

        # Chef should have INFO_CHEF in private_info
        chef_info = [x for x in obs_chef.private_info if x["type"] == "INFO_CHEF"]
        self.assertEqual(len(chef_info), 1)

        # Empath must NOT have INFO_CHEF
        chef_info_in_empath = [x for x in obs_empath.private_info if x["type"] == "INFO_CHEF"]
        self.assertEqual(len(chef_info_in_empath), 0)


if __name__ == "__main__":
    unittest.main()
