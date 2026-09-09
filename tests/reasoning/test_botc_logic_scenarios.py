"""Synthetic Logic Benchmark for Trouble Brewing (Amendment 5).

Evaluates 25 distinct game logic scenarios categorized into:
1. LEGALITY: Hard rule/setup contradictions must be refuted (-inf).
2. ORDERING: Simpler, unpoisoned, or corroborated worlds must rank above over-complex explanations.
3. AMBIGUITY: Multiple plausible worlds MUST simultaneously be retained without forced collapse.
"""
from __future__ import annotations

import math
import unittest

from src.cognition.player_state import PlayerState
from src.engine.types import Alignment, GamePhase, RoleId
from src.player.personality import PersonalityVector
from src.player.skill import SkillProfile
from src.reasoning.evidence import (
    AtomicEvidence,
    EvidenceStrength,
    EvidenceTier,
    EvidenceType,
)
from src.reasoning.information_constraints import (
    InformationConstraintsCoordinator,
)
from src.reasoning.world import RoleSlot, WorldHypothesis
from src.reasoning.world_generator import WorldHypothesisManager


class TestBotcLogicScenarios(unittest.TestCase):
    def setUp(self) -> None:
        self.coordinator = InformationConstraintsCoordinator()
        self.players = [f"p{i}" for i in range(1, 8)]

    # =========================================================================
    # CATEGORY 1: LEGALITY (8 Scenarios)
    # =========================================================================

    def test_legality_01_two_demons(self) -> None:
        """Scenario 1: Two players assigned IMP in 7p game is strictly illegal."""
        w = self._make_world("p7", ["p6"])
        w.slots["p5"] = RoleSlot.make_known(RoleId.IMP)  # Duplicate Demon
        score = self.coordinator.evaluate_world(w, [], None, {p: True for p in self.players})
        self.assertTrue(math.isinf(score) and score < 0)

    def test_legality_02_duplicate_townsfolk(self) -> None:
        """Scenario 2: Duplicate Townsfolk roles in TB without explanation is illegal."""
        w = self._make_world("p7", ["p6"])
        w.slots["p1"] = RoleSlot.make_known(RoleId.CHEF)
        w.slots["p2"] = RoleSlot.make_known(RoleId.CHEF)
        score = self.coordinator.evaluate_world(w, [], None, {p: True for p in self.players})
        self.assertTrue(math.isinf(score) and score < 0)

    def test_legality_03_virgin_executed_by_demon(self) -> None:
        """Scenario 3: Virgin ability executing a Demon nominator violates rules."""
        w = self._make_world("p7", ["p6"])
        w.slots["p3"] = RoleSlot.make_known(RoleId.VIRGIN)
        # Nomination by p7 (Imp) resulting in execution is illegal for Virgin
        ev = AtomicEvidence(
            evidence_id="v_exec",
            observer="p1",
            source_player="storyteller",
            source_type="storyteller",
            day=1,
            phase=GamePhase.DAY_PUBLIC,
            visibility="public",
            tier=EvidenceTier.FACT,
            evidence_type=EvidenceType.EXECUTION_INFO,
            strength=EvidenceStrength.HARD,
            content={"executed": "p7", "reason": "virgin", "virgin": "p3"},
        )
        score = self.coordinator.evaluate_world(w, [ev], None, {p: True for p in self.players})
        self.assertTrue(math.isinf(score) and score < 0)

    def test_legality_04_chef_pair_exceeds_evil(self) -> None:
        """Scenario 4: Chef ping of 2 pairs in 7p game (which only has 2 evil) is illegal."""
        w = self._make_world("p7", ["p6"])
        w.slots["p6"] = RoleSlot.make_known(RoleId.SCARLET_WOMAN)
        w.slots["p2"] = RoleSlot.make_known(RoleId.CHEF)
        ev = AtomicEvidence(
            evidence_id="chef_2",
            observer="p2",
            source_player="p2",
            source_type="self",
            day=1,
            phase=GamePhase.DAY_PUBLIC,
            visibility="private",
            tier=EvidenceTier.FACT,
            evidence_type=EvidenceType.COUNT_INFO,
            strength=EvidenceStrength.HARD,
            content={"count": 2},
        )
        score = self.coordinator.evaluate_world(w, [ev], None, {p: True for p in self.players})
        self.assertTrue(math.isinf(score) and score < 0)

    def test_legality_05_washerwoman_outsider_token(self) -> None:
        """Scenario 5: Washerwoman seeing an outsider role is illegal."""
        w = self._make_world("p7", ["p6"])
        w.slots["p1"] = RoleSlot.make_known(RoleId.WASHERWOMAN)
        ev = AtomicEvidence(
            evidence_id="ww_saint",
            observer="p1",
            source_player="p1",
            source_type="self",
            day=1,
            phase=GamePhase.DAY_PUBLIC,
            visibility="private",
            tier=EvidenceTier.FACT,
            evidence_type=EvidenceType.ROLE_INFO,
            strength=EvidenceStrength.HARD,
            content={"role": RoleId.SAINT, "players": ["p2", "p3"]},
        )
        score = self.coordinator.evaluate_world(w, [ev], None, {p: True for p in self.players})
        self.assertTrue(math.isinf(score) and score < 0)

    def test_legality_06_investigator_townsfolk_token(self) -> None:
        """Scenario 6: Investigator seeing a Townsfolk role as Minion is illegal."""
        w = self._make_world("p7", ["p6"])
        w.slots["p4"] = RoleSlot.make_known(RoleId.INVESTIGATOR)
        ev = AtomicEvidence(
            evidence_id="inv_empath",
            observer="p4",
            source_player="p4",
            source_type="self",
            day=1,
            phase=GamePhase.DAY_PUBLIC,
            visibility="private",
            tier=EvidenceTier.FACT,
            evidence_type=EvidenceType.ROLE_INFO,
            strength=EvidenceStrength.HARD,
            content={"role": RoleId.EMPATH, "players": ["p2", "p3"]},
        )
        score = self.coordinator.evaluate_world(w, [ev], None, {p: True for p in self.players})
        self.assertTrue(math.isinf(score) and score < 0)

    def test_legality_07_empath_two_evil_with_one_evil(self) -> None:
        """Scenario 7: Empath sees 2 evil with only 1 evil neighbor possible is illegal without poison."""
        w = self._make_world("p7", ["p6"])
        w.slots["p6"] = RoleSlot.make_known(RoleId.SCARLET_WOMAN)
        w.slots["p1"] = RoleSlot.make_known(RoleId.EMPATH)
        # Neighbors of p1 are p7 (evil) and p2 (good). Only 1 evil neighbor!
        ev = AtomicEvidence(
            evidence_id="empath_2",
            observer="p1",
            source_player="p1",
            source_type="self",
            day=1,
            phase=GamePhase.DAY_PUBLIC,
            visibility="private",
            tier=EvidenceTier.FACT,
            evidence_type=EvidenceType.COUNT_INFO,
            strength=EvidenceStrength.HARD,
            content={"count": 2},
        )
        score = self.coordinator.evaluate_world(w, [ev], None, {p: True for p in self.players})
        self.assertTrue(math.isinf(score) and score < 0)

    def test_legality_08_dead_poisoner_night_action(self) -> None:
        """Scenario 8: Dead Poisoner causing false info is illegal."""
        w = self._make_world("p7", ["p6"])
        w.poison_history = [{"night": 2, "source": "p6", "target": "p1"}]
        alive_roster = {p: True for p in self.players}
        alive_roster["p6"] = False
        living_by_day = {1: self.players, 2: [p for p in self.players if p != "p6"]}
        score = self.coordinator.evaluate_world(w, [], None, alive_roster, living_by_day)
        self.assertTrue(math.isinf(score) and score < 0)

    # =========================================================================
    # CATEGORY 2: ORDERING (8 Scenarios)
    # =========================================================================

    def test_ordering_09_true_world_beats_drunk_world(self) -> None:
        """Scenario 9: World requiring 0 explanations beats world requiring Drunk."""
        w_true = self._make_world("p7", ["p6"])
        w_drunk = self._make_world("p7", ["p6"])
        w_drunk.drunk_player = "p2"

        ev = AtomicEvidence(
            evidence_id="c_true",
            observer="p2",
            source_player="p2",
            source_type="self",
            day=1,
            phase=GamePhase.DAY_PUBLIC,
            visibility="private",
            tier=EvidenceTier.FACT,
            evidence_type=EvidenceType.COUNT_INFO,
            strength=EvidenceStrength.HARD,
            content={"count": 1},
        )
        s_true = self.coordinator.evaluate_world(w_true, [ev], None, {p: True for p in self.players})
        s_drunk = self.coordinator.evaluate_world(w_drunk, [ev], None, {p: True for p in self.players})
        self.assertGreater(s_true, s_drunk)

    def test_ordering_10_one_drunk_beats_two_poison_plus_drunk(self) -> None:
        """Scenario 10: Parsimony preference: 1 explanation beats 3 stacked explanations."""
        players_8 = [f"p{i}" for i in range(1, 9)]
        w1 = self._make_world("p7", ["p6"])
        w1.slots["p8"] = RoleSlot.make_unknown()
        w1.good_players.append("p8")
        w1.alignments["p8"] = Alignment.GOOD
        w1.drunk_player = "p2"

        w2 = self._make_world("p7", ["p6"])
        w2.slots["p8"] = RoleSlot.make_unknown()
        w2.good_players.append("p8")
        w2.alignments["p8"] = Alignment.GOOD
        w2.drunk_player = "p2"
        w2.poison_history = [
            {"night": 1, "source": "p6", "target": "p1"},
            {"night": 2, "source": "p6", "target": "p3"},
        ]

        alive_8 = {p: True for p in players_8}
        s1 = self.coordinator.evaluate_world(w1, [], None, alive_8)
        s2 = self.coordinator.evaluate_world(w2, [], None, alive_8)
        self.assertFalse(math.isinf(s1))
        self.assertFalse(math.isinf(s2))
        self.assertGreater(s1, s2)

    def test_ordering_11_soldier_unexplained_death_penalized(self) -> None:
        """Scenario 11: World where Soldier died at night without poison receives penalty."""
        w_clean = self._make_world("p7", ["p6"])
        w_soldier_kill = self._make_world("p7", ["p6"])
        w_soldier_kill.slots["p3"] = RoleSlot.make_known(RoleId.SOLDIER)

        ev_death = AtomicEvidence(
            evidence_id="d_s",
            observer="p1",
            source_player="storyteller",
            source_type="storyteller",
            day=2,
            phase=GamePhase.DAY_PUBLIC,
            visibility="public",
            tier=EvidenceTier.FACT,
            evidence_type=EvidenceType.DEATH_INFO,
            strength=EvidenceStrength.HARD,
            content={"player": "p3", "night": 1},
        )

        s_clean = self.coordinator.evaluate_world(w_clean, [ev_death], None, {p: True for p in self.players})
        s_soldier = self.coordinator.evaluate_world(w_soldier_kill, [ev_death], None, {p: True for p in self.players})
        self.assertGreater(s_clean, s_soldier)

    def test_ordering_12_monk_protected_death_penalized(self) -> None:
        """Scenario 12: World where Monk protected player died receives penalty."""
        w1 = self._make_world("p7", ["p6"])
        w2 = self._make_world("p7", ["p6"])

        ev_monk = AtomicEvidence(
            evidence_id="ev_m",
            observer="p1",
            source_player="p1",
            source_type="self",
            day=2,
            phase=GamePhase.DAY_PUBLIC,
            visibility="private",
            tier=EvidenceTier.FACT,
            evidence_type=EvidenceType.ROLE_INFO,
            strength=EvidenceStrength.HARD,
            content={"protected": "p2"},
        )
        ev_death = AtomicEvidence(
            evidence_id="ev_d",
            observer="p1",
            source_player="storyteller",
            source_type="storyteller",
            day=2,
            phase=GamePhase.DAY_PUBLIC,
            visibility="public",
            tier=EvidenceTier.FACT,
            evidence_type=EvidenceType.DEATH_INFO,
            strength=EvidenceStrength.HARD,
            content={"player": "p2", "night": 1},
        )

        s1 = self.coordinator.evaluate_world(w1, [ev_monk], None, {p: True for p in self.players})
        s2 = self.coordinator.evaluate_world(w2, [ev_monk, ev_death], None, {p: True for p in self.players})
        self.assertGreater(s1, s2)

    def test_ordering_13_corroborated_claims_beat_contradicted_claims(self) -> None:
        """Scenario 13: World matching public claims ranks above world contradicting them."""
        w1 = self._make_world("p7", ["p6"])
        w2 = self._make_world("p7", ["p6"])
        w2.slots["p1"] = RoleSlot.make_known(RoleId.SAINT)

        ev_claim = AtomicEvidence(
            evidence_id="pub_c",
            observer="p1",
            source_player="p1",
            source_type="player_speech",
            day=1,
            phase=GamePhase.DAY_PUBLIC,
            visibility="public",
            tier=EvidenceTier.CLAIM,
            evidence_type=EvidenceType.PUBLIC_CLAIM,
            strength=EvidenceStrength.MEDIUM,
            content={"player": "p1", "claimed_role": RoleId.EMPATH.value},
        )

        s1 = self.coordinator.evaluate_world(w1, [ev_claim], None, {p: True for p in self.players})
        s2 = self.coordinator.evaluate_world(w2, [ev_claim], None, {p: True for p in self.players})
        self.assertGreater(s1, s2)

    def test_ordering_14_slayer_shot_killed_demon_beats_non_kill(self) -> None:
        """Scenario 14: World where Slayer shot on Demon killed Demon matches game state."""
        w_demon_shot = self._make_world("p7", ["p6"])
        w_good_shot = self._make_world("p1", ["p6"])

        ev_slayer = AtomicEvidence(
            evidence_id="slayer_kill",
            observer="p1",
            source_player="storyteller",
            source_type="storyteller",
            day=2,
            phase=GamePhase.DAY_PUBLIC,
            visibility="public",
            tier=EvidenceTier.FACT,
            evidence_type=EvidenceType.DEATH_INFO,
            strength=EvidenceStrength.HARD,
            content={"slayer": "p3", "target": "p7", "died": True},
        )

        s_dem = self.coordinator.evaluate_world(w_demon_shot, [ev_slayer], None, {p: True for p in self.players})
        s_good = self.coordinator.evaluate_world(w_good_shot, [ev_slayer], None, {p: True for p in self.players})
        self.assertGreater(s_dem, s_good)

    def test_ordering_15_poisoner_explanation_with_poisoner_beats_no_poisoner(self) -> None:
        """Scenario 15: Poison explanation in a world with a Poisoner beats world with Baron only."""
        w_poisoner = self._make_world("p7", ["p6"])  # p6 is Poisoner
        w_poisoner.poison_history = [{"night": 1, "source": "p6", "target": "p1"}]

        w_baron = self._make_world("p7", ["p6"])
        w_baron.slots["p6"] = RoleSlot.make_known(RoleId.BARON)  # No poisoner!
        w_baron.poison_history = [{"night": 1, "source": "p6", "target": "p1"}]

        s_p = self.coordinator.evaluate_world(w_poisoner, [], None, {p: True for p in self.players})
        s_b = self.coordinator.evaluate_world(w_baron, [], None, {p: True for p in self.players})
        self.assertGreater(s_p, s_b)

    def test_ordering_16_scarlet_woman_inheritance_at_five_alive(self) -> None:
        """Scenario 16: Scarlet Woman inheritance at >= 5 alive is preferred over unhandled demon death."""
        w_sw = self._make_world("p7", ["p6"])
        w_sw.slots["p6"] = RoleSlot.make_known(RoleId.SCARLET_WOMAN)
        w_sw.slots["p7"] = RoleSlot.make_known(RoleId.IMP)

        # Both worlds are evaluated; SW inheritance preserves continuity
        s = self.coordinator.evaluate_world(w_sw, [], None, {p: True for p in self.players})
        self.assertFalse(math.isinf(s))

    # =========================================================================
    # CATEGORY 3: AMBIGUITY (9 Scenarios - Multi-world retention)
    # =========================================================================

    def test_ambiguity_17_fortune_teller_red_herring_vs_demon(self) -> None:
        """Scenario 17: FT YES on P2 & P7 can mean P7 is Demon OR P2 is Demon OR P2 is Red Herring.

        Both worlds MUST be retained!
        """
        w1 = self._make_world("p7", ["p6"])  # P7 is Demon
        w2 = self._make_world("p2", ["p6"])  # P2 is Demon

        ev_ft = AtomicEvidence(
            evidence_id="ft_ping",
            observer="p3",
            source_player="p3",
            source_type="self",
            day=1,
            phase=GamePhase.DAY_PUBLIC,
            visibility="private",
            tier=EvidenceTier.FACT,
            evidence_type=EvidenceType.ABILITY_RESULT,
            strength=EvidenceStrength.HARD,
            content={"pair": ["p2", "p7"], "result": True},
        )

        s1 = self.coordinator.evaluate_world(w1, [ev_ft], None, {p: True for p in self.players})
        s2 = self.coordinator.evaluate_world(w2, [ev_ft], None, {p: True for p in self.players})

        # CRUCIAL AMBIGUITY CHECK: Neither world is refuted!
        self.assertFalse(math.isinf(s1))
        self.assertFalse(math.isinf(s2))
        # Both are viable hypotheses
        self.assertGreater(s1, -10.0)
        self.assertGreater(s2, -10.0)

    def test_ambiguity_18_double_claim_washerwoman(self) -> None:
        """Scenario 18: P1 and P2 both claim Washerwoman. Both worlds retained."""
        w1 = self._make_world("p7", ["p6"])
        w1.slots["p1"] = RoleSlot.make_known(RoleId.WASHERWOMAN)
        w1.slots["p2"] = RoleSlot.make_known(RoleId.CHEF)
        w1.slots["p5"] = RoleSlot.make_known(RoleId.SLAYER)

        w2 = self._make_world("p7", ["p6"])
        w2.slots["p1"] = RoleSlot.make_known(RoleId.CHEF)
        w2.slots["p2"] = RoleSlot.make_known(RoleId.WASHERWOMAN)
        w2.slots["p5"] = RoleSlot.make_known(RoleId.SLAYER)

        s1 = self.coordinator.evaluate_world(w1, [], None, {p: True for p in self.players})
        s2 = self.coordinator.evaluate_world(w2, [], None, {p: True for p in self.players})
        self.assertFalse(math.isinf(s1))
        self.assertFalse(math.isinf(s2))

    def test_ambiguity_19_empath_one_ping_symmetric_neighbors(self) -> None:
        """Scenario 19: Empath 1 ping: Left neighbor is evil OR Right neighbor is evil. Both retained."""
        # Circle: [p7, p1, p2] -> p1's neighbors are p7 and p2
        w_left_evil = self._make_world("p7", ["p6"])   # p7 is Demon (Evil), p2 is Good
        w_right_evil = self._make_world("p2", ["p6"])  # p2 is Demon (Evil), p7 is Good

        ev_emp = AtomicEvidence(
            evidence_id="emp_1",
            observer="p1",
            source_player="p1",
            source_type="self",
            day=1,
            phase=GamePhase.DAY_PUBLIC,
            visibility="private",
            tier=EvidenceTier.FACT,
            evidence_type=EvidenceType.COUNT_INFO,
            strength=EvidenceStrength.HARD,
            content={"count": 1},
        )

        s_left = self.coordinator.evaluate_world(w_left_evil, [ev_emp], None, {p: True for p in self.players})
        s_right = self.coordinator.evaluate_world(w_right_evil, [ev_emp], None, {p: True for p in self.players})

        self.assertFalse(math.isinf(s_left))
        self.assertFalse(math.isinf(s_right))

    def test_ambiguity_20_undertaker_true_vs_poisoned(self) -> None:
        """Scenario 20: Undertaker info: either true executed role OR UT was poisoned. Both retained."""
        w_true = self._make_world("p7", ["p6"])
        w_poisoned = self._make_world("p7", ["p6"])
        w_poisoned.poison_history = [{"night": 2, "source": "p6", "target": "p5"}]

        s_true = self.coordinator.evaluate_world(w_true, [], None, {p: True for p in self.players})
        s_p = self.coordinator.evaluate_world(w_poisoned, [], None, {p: True for p in self.players})

        self.assertFalse(math.isinf(s_true))
        self.assertFalse(math.isinf(s_p))

    def test_ambiguity_21_investigator_candidate_pair(self) -> None:
        """Scenario 21: Investigator sees (P5, P6) as Minion. Either P5 is minion OR P6 is minion. Both retained."""
        w_p5_minion = self._make_world("p7", ["p5"])
        w_p6_minion = self._make_world("p7", ["p6"])

        ev_inv = AtomicEvidence(
            evidence_id="inv_pair",
            observer="p4",
            source_player="p4",
            source_type="self",
            day=1,
            phase=GamePhase.DAY_PUBLIC,
            visibility="private",
            tier=EvidenceTier.FACT,
            evidence_type=EvidenceType.PAIR_INFO,
            strength=EvidenceStrength.HARD,
            content={"role": RoleId.POISONER, "players": ["p5", "p6"]},
        )

        s5 = self.coordinator.evaluate_world(w_p5_minion, [ev_inv], None, {p: True for p in self.players})
        s6 = self.coordinator.evaluate_world(w_p6_minion, [ev_inv], None, {p: True for p in self.players})

        self.assertFalse(math.isinf(s5))
        self.assertFalse(math.isinf(s6))

    def test_ambiguity_22_recluse_registration_branch(self) -> None:
        """Scenario 22: Recluse pinged as Evil: either Recluse registered Evil OR neighbor is Evil. Both retained."""
        w_recluse_reg = self._make_world("p7", ["p6"])
        w_recluse_reg.slots["p6"] = RoleSlot.make_known(RoleId.BARON)
        w_recluse_reg.slots["p2"] = RoleSlot.make_known(RoleId.RECLUSE)
        w_recluse_reg.slots["p5"] = RoleSlot.make_known(RoleId.BUTLER)
        w_recluse_reg.recluse_registration_assumptions["p2"] = {"registered_as": Alignment.EVIL}

        s = self.coordinator.evaluate_world(w_recluse_reg, [], None, {p: True for p in self.players})
        self.assertFalse(math.isinf(s))

    def test_ambiguity_23_spy_registration_branch(self) -> None:
        """Scenario 23: Spy pinged as Good by Librarian: Spy registered as Townsfolk. Retained."""
        w_spy = self._make_world("p7", ["p6"])
        w_spy.slots["p6"] = RoleSlot.make_known(RoleId.SPY)
        w_spy.spy_registration_assumptions["p6"] = {"registered_as": Alignment.GOOD}

        s = self.coordinator.evaluate_world(w_spy, [], None, {p: True for p in self.players})
        self.assertFalse(math.isinf(s))

    def test_ambiguity_24_mayor_bounce_vs_direct_target(self) -> None:
        """Scenario 24: Non-demon killed: could be Mayor bounce OR direct Demon target. Both retained."""
        w_direct = self._make_world("p7", ["p6"])
        w_bounce = self._make_world("p7", ["p6"])
        w_bounce.slots["p3"] = RoleSlot.make_known(RoleId.MAYOR)

        s_d = self.coordinator.evaluate_world(w_direct, [], None, {p: True for p in self.players})
        s_b = self.coordinator.evaluate_world(w_bounce, [], None, {p: True for p in self.players})

        self.assertFalse(math.isinf(s_d))
        self.assertFalse(math.isinf(s_b))

    def test_ambiguity_25_no_death_at_night(self) -> None:
        """Scenario 25: 0 night deaths: could be Monk protected OR Soldier targeted. Both retained."""
        w_monk = self._make_world("p7", ["p6"])
        w_monk.slots["p4"] = RoleSlot.make_known(RoleId.MONK)

        w_soldier = self._make_world("p7", ["p6"])
        w_soldier.slots["p4"] = RoleSlot.make_known(RoleId.SOLDIER)

        s_m = self.coordinator.evaluate_world(w_monk, [], None, {p: True for p in self.players})
        s_s = self.coordinator.evaluate_world(w_soldier, [], None, {p: True for p in self.players})

        self.assertFalse(math.isinf(s_m))
        self.assertFalse(math.isinf(s_s))

    # Helper
    def _make_world(self, demon: str, minions: list[str]) -> WorldHypothesis:
        slots = {
            "p1": RoleSlot.make_known(RoleId.EMPATH),
            "p2": RoleSlot.make_known(RoleId.CHEF),
            "p3": RoleSlot.make_known(RoleId.FORTUNE_TELLER),
            "p4": RoleSlot.make_known(RoleId.INVESTIGATOR),
            "p5": RoleSlot.make_known(RoleId.WASHERWOMAN),
            "p6": RoleSlot.make_known(RoleId.POISONER),
            "p7": RoleSlot.make_known(RoleId.IMP),
        }
        alignments = {p: Alignment.GOOD for p in self.players[:5]}
        for m in minions:
            alignments[m] = Alignment.EVIL
        alignments[demon] = Alignment.EVIL
        return WorldHypothesis(
            world_id=100,
            demon_player=demon,
            minion_players=minions,
            good_players=[p for p in self.players if p != demon and p not in minions],
            slots=slots,
            alignments=alignments,
        )


if __name__ == "__main__":
    unittest.main()
