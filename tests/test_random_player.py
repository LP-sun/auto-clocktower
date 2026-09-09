"""Unit and stress tests for the minimal random legal-action player policy."""
import unittest

from src.engine.types import Alignment
from src.simulation.batch import simulate_batch
from src.simulation.runner import simulate_game


class TestRandomPlayerSimulation(unittest.TestCase):
    def test_single_game_completes(self):
        """A single 12-player game runs to completion and produces valid results."""
        res = simulate_game(player_count=12, seed=42)
        self.assertIn(res.winner, (Alignment.GOOD, Alignment.EVIL))
        self.assertIsNotNone(res.end_reason)
        self.assertGreater(res.total_days, 0)
        self.assertGreater(res.event_count, 10)
        self.assertEqual(len(res.true_roles), 12)

    def test_batch_500_games_stress(self):
        """Stress test: 500 consecutive games complete with zero crashes or deadlocks."""
        results, summary = simulate_batch(n_games=500, player_count=12, base_seed=1000, parallel=False, use_random_players=True)
        self.assertEqual(summary.total_games, 500)
        self.assertEqual(summary.good_wins + summary.evil_wins, 500)
        self.assertGreater(summary.games_per_second, 100)  # Expect hundreds of games per second!
        print(f"\n[STRESS TEST] 500 games completed in {summary.elapsed_seconds:.2f}s ({summary.games_per_second:.1f} games/sec)")
        print(f"Good Win Rate: {summary.good_win_rate * 100:.1f}%, Avg Days: {summary.avg_days:.2f}")
        print(f"End reasons breakdown: {summary.end_reasons}")


if __name__ == "__main__":
    unittest.main()
