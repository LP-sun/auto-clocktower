"""Unit tests for Poison and Drunk Resource Accounting (Amendment 4).

Validates:
1. Poisoner capacity is strictly 1 target per night per living functioning Poisoner.
2. Multiple falsified observations on the same night cannot be casually attributed
   to a single Poisoner without exceeding capacity.
3. Dead Poisoners cannot poison.
4. Explanations exceeding capacity are penalized or rejected.
"""
from __future__ import annotations

import math
import unittest

from src.engine.types import Alignment, RoleId
from src.reasoning.information_constraints import (
    InformationConstraintsCoordinator,
)
from src.reasoning.world import RoleSlot, WorldHypothesis


class TestPoisonDrunkResources(unittest.TestCase):
    def setUp(self) -> None:
        self.coordinator = InformationConstraintsCoordinator()

    def test_single_poison_target_per_night_legal(self) -> None:
        """One target per night for a living Poisoner is valid."""
        players = [f"p{i}" for i in range(1, 8)]
        slots = {
            "p1": RoleSlot.make_known(RoleId.EMPATH),
            "p2": RoleSlot.make_known(RoleId.CHEF),
            "p3": RoleSlot.make_known(RoleId.FORTUNE_TELLER),
            "p4": RoleSlot.make_known(RoleId.INVESTIGATOR),
            "p5": RoleSlot.make_known(RoleId.WASHERWOMAN),
            "p6": RoleSlot.make_known(RoleId.POISONER),
            "p7": RoleSlot.make_known(RoleId.IMP),
        }
        alignments = {p: Alignment.GOOD for p in players[:5]}
        alignments["p6"] = Alignment.EVIL
        alignments["p7"] = Alignment.EVIL

        world = WorldHypothesis(
            world_id=1,
            demon_player="p7",
            minion_players=["p6"],
            good_players=players[:5],
            slots=slots,
            alignments=alignments,
            poison_history=[
                {"night": 1, "source": "p6", "target": "p1"},
                {"night": 2, "source": "p6", "target": "p3"},
            ],
        )

        alive_roster = {p: True for p in players}
        living_by_day = {1: players, 2: players}

        valid = self.coordinator._validate_poison_resource_capacity(world, alive_roster, living_by_day)
        self.assertTrue(valid)

    def test_over_capacity_poison_rejected(self) -> None:
        """Attempting to poison 2 targets on the same night with 1 Poisoner violates capacity."""
        players = [f"p{i}" for i in range(1, 8)]
        slots = {
            "p1": RoleSlot.make_known(RoleId.EMPATH),
            "p2": RoleSlot.make_known(RoleId.CHEF),
            "p3": RoleSlot.make_known(RoleId.FORTUNE_TELLER),
            "p4": RoleSlot.make_known(RoleId.INVESTIGATOR),
            "p5": RoleSlot.make_known(RoleId.WASHERWOMAN),
            "p6": RoleSlot.make_known(RoleId.POISONER),
            "p7": RoleSlot.make_known(RoleId.IMP),
        }
        alignments = {p: Alignment.GOOD for p in players[:5]}
        alignments["p6"] = Alignment.EVIL
        alignments["p7"] = Alignment.EVIL

        world = WorldHypothesis(
            world_id=2,
            demon_player="p7",
            minion_players=["p6"],
            good_players=players[:5],
            slots=slots,
            alignments=alignments,
            poison_history=[
                {"night": 1, "source": "p6", "target": "p1"},
                {"night": 1, "source": "p6", "target": "p3"},  # 2nd target on Night 1! Capacity violation!
            ],
        )

        alive_roster = {p: True for p in players}
        living_by_day = {1: players}

        valid = self.coordinator._validate_poison_resource_capacity(world, alive_roster, living_by_day)
        self.assertFalse(valid)

    def test_dead_poisoner_cannot_poison(self) -> None:
        """A dead Poisoner attempting to poison on night 2 violates alive constraint."""
        players = [f"p{i}" for i in range(1, 8)]
        slots = {
            "p1": RoleSlot.make_known(RoleId.EMPATH),
            "p2": RoleSlot.make_known(RoleId.CHEF),
            "p3": RoleSlot.make_known(RoleId.FORTUNE_TELLER),
            "p4": RoleSlot.make_known(RoleId.INVESTIGATOR),
            "p5": RoleSlot.make_known(RoleId.WASHERWOMAN),
            "p6": RoleSlot.make_known(RoleId.POISONER),
            "p7": RoleSlot.make_known(RoleId.IMP),
        }
        alignments = {p: Alignment.GOOD for p in players[:5]}
        alignments["p6"] = Alignment.EVIL
        alignments["p7"] = Alignment.EVIL

        world = WorldHypothesis(
            world_id=3,
            demon_player="p7",
            minion_players=["p6"],
            good_players=players[:5],
            slots=slots,
            alignments=alignments,
            poison_history=[
                {"night": 2, "source": "p6", "target": "p1"},
            ],
        )

        alive_roster = {p: True for p in players}
        alive_roster["p6"] = False  # p6 died day 1!
        living_by_day = {1: players, 2: [p for p in players if p != "p6"]}

        valid = self.coordinator._validate_poison_resource_capacity(world, alive_roster, living_by_day)
        self.assertFalse(valid)


if __name__ == "__main__":
    unittest.main()
