"""Unit tests verifying Storyteller decision points, legality, and dataset export."""
import json
import tempfile
import unittest
from pathlib import Path

from src.datasets.exporter import export_st_dataset
from src.engine.game import ClocktowerEngine
from src.engine.types import RoleId, STDecisionType
from src.storyteller.st_policy import StorytellerPolicy
from tests.test_engine_rules import make_custom_setup


class TestStorytellerDecisions(unittest.TestCase):
    def setUp(self):
        roles = [
            RoleId.CHEF, RoleId.EMPATH, RoleId.FORTUNE_TELLER, RoleId.UNDERTAKER,
            RoleId.WASHERWOMAN, RoleId.MONK, RoleId.SOLDIER, RoleId.DRUNK,
            RoleId.SAINT, RoleId.POISONER, RoleId.SCARLET_WOMAN, RoleId.IMP,
        ]
        self.setup = make_custom_setup(roles)
        self.engine = ClocktowerEngine.create(custom_setup=self.setup)

    def test_st_misinfo_decision_record(self):
        """ST generating misinformation records complete features, legal candidates, and utility."""
        st_policy = StorytellerPolicy(seed=42)

        # Chef (P01) misinformation decision
        chosen = st_policy.decide(
            decision_type=STDecisionType.DRUNK_POISON_MISINFO,
            state=self.engine.state,
            actor="P01",
        )

        self.assertIn(chosen, [0, 1, 2, 3])
        self.assertEqual(len(st_policy.decisions_log), 1)

        rec = st_policy.decisions_log[0]
        self.assertEqual(rec.decision_type, STDecisionType.DRUNK_POISON_MISINFO)
        self.assertEqual(rec.actor, "P01")
        self.assertIn("tension", rec.state_features)
        self.assertIn("entropy", rec.state_features)
        self.assertIn("fairness", rec.utility_components)
        self.assertIn("solvability", rec.utility_components)
        self.assertGreater(len(rec.reason_codes), 0)

    def test_st_dataset_export_jsonl(self):
        """ST decision records correctly export to JSONL formatted training data."""
        st_policy = StorytellerPolicy(seed=42)

        for _ in range(5):
            st_policy.decide(
                decision_type=STDecisionType.DRUNK_POISON_MISINFO,
                state=self.engine.state,
                actor="P01",
            )

        with tempfile.TemporaryDirectory() as tmpdir:
            out_file = Path(tmpdir) / "st_train.jsonl"
            count = export_st_dataset(st_policy.decisions_log, out_file)
            self.assertEqual(count, 5)

            # Validate reading lines as valid json
            with out_file.open("r", encoding="utf-8") as f:
                lines = [json.loads(line) for line in f]
            self.assertEqual(len(lines), 5)
            self.assertEqual(lines[0]["decision_type"], "drunk_poison_misinfo")


if __name__ == "__main__":
    unittest.main()
