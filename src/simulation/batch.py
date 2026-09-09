"""High-throughput multi-game batch simulator with multiprocessing support."""
from __future__ import annotations

import multiprocessing
import time
from dataclasses import dataclass
from typing import Sequence

from src.simulation.runner import SimulationResult, simulate_game


@dataclass(slots=True)
class BatchSummary:
    total_games: int
    good_wins: int
    evil_wins: int
    good_win_rate: float
    avg_days: float
    elapsed_seconds: float
    games_per_second: float
    end_reasons: dict[str, int]


def _run_single_worker(args: tuple[int, int, int, bool]) -> SimulationResult:
    player_count, seed, max_days, use_random_players = args
    return simulate_game(player_count=player_count, seed=seed, max_days=max_days, use_random_players=use_random_players)


def simulate_batch(
    n_games: int = 100,
    player_count: int = 12,
    base_seed: int = 42,
    max_days: int = 20,
    parallel: bool = True,
    workers: int | None = None,
    use_random_players: bool = False,
) -> tuple[list[SimulationResult], BatchSummary]:
    """Run a batch of game simulations with optional multiprocessing parallelism."""
    start_time = time.perf_counter()
    tasks = [(player_count, base_seed + i, max_days, use_random_players) for i in range(n_games)]

    results: list[SimulationResult] = []
    if parallel and n_games > 5:
        worker_count = workers or max(1, (multiprocessing.cpu_count() or 4) - 1)
        with multiprocessing.Pool(processes=worker_count) as pool:
            results = pool.map(_run_single_worker, tasks)
    else:
        results = [_run_single_worker(t) for t in tasks]

    elapsed = time.perf_counter() - start_time
    good_wins = sum(1 for r in results if r.winner and r.winner.value == "good")
    evil_wins = sum(1 for r in results if r.winner and r.winner.value == "evil")
    end_reasons: dict[str, int] = {}
    total_days = 0

    for r in results:
        total_days += r.total_days
        reason = r.end_reason or "unknown"
        end_reasons[reason] = end_reasons.get(reason, 0) + 1

    summary = BatchSummary(
        total_games=n_games,
        good_wins=good_wins,
        evil_wins=evil_wins,
        good_win_rate=good_wins / n_games if n_games else 0.0,
        avg_days=total_days / n_games if n_games else 0.0,
        elapsed_seconds=elapsed,
        games_per_second=n_games / elapsed if elapsed > 0 else 0.0,
        end_reasons=end_reasons,
    )

    return results, summary
