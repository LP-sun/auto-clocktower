"""Unit tests verifying 100% deterministic seed replayability."""
import unittest

from src.simulation.runner import simulate_game


class TestDeterministicReplay(unittest.TestCase):
    def test_exact_replay_consistency(self):
        """Two runs with the exact same seed must produce identical game trajectories."""
        res1 = simulate_game(player_count=12, seed=42)
        res2 = simulate_game(player_count=12, seed=42)

        self.assertEqual(res1.winner, res2.winner)
        self.assertEqual(res1.end_reason, res2.end_reason)
        self.assertEqual(res1.total_days, res2.total_days)
        self.assertEqual(res1.event_count, res2.event_count)
        self.assertEqual(res1.true_roles, res2.true_roles)
        self.assertEqual(res1.apparent_roles, res2.apparent_roles)
        self.assertEqual(res1.alive_players, res2.alive_players)

        # Step by step event log comparison
        self.assertEqual(len(res1.events), len(res2.events))
        for i in range(len(res1.events)):
            e1 = res1.events[i]
            e2 = res2.events[i]
            self.assertEqual(e1, e2, f"Event divergence at index {i}: {e1} != {e2}")

    def test_seed_variance(self):
        """Different seeds must produce different role assignments and trajectories."""
        res_a = simulate_game(player_count=12, seed=100)
        res_b = simulate_game(player_count=12, seed=200)

        # Roles distribution should differ
        self.assertNotEqual(res_a.true_roles, res_b.true_roles)


if __name__ == "__main__":
    unittest.main()
