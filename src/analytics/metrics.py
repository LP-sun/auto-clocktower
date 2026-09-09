"""Behavioral metrics and statistical evaluation for BotC simulation populations."""
from __future__ import annotations

import statistics
from dataclasses import asdict, dataclass
from typing import Sequence

from src.simulation.runner import SimulationResult


@dataclass(slots=True)
class PopulationMetrics:
    total_games: int
    good_win_rate: float
    evil_win_rate: float
    avg_game_length_days: float
    median_game_length_days: float
    d1_execution_rate: float
    avg_nominations_per_game: float
    avg_executions_per_game: float
    virgin_proc_rate: float
    slayer_shot_rate: float
    end_reasons_distribution: dict[str, int]

    def to_dict(self) -> dict[str, float | int | dict[str, int]]:
        return asdict(self)


def calculate_population_metrics(results: Sequence[SimulationResult]) -> PopulationMetrics:
    """Compute comprehensive behavioral and balance metrics across a batch of simulations."""
    n = len(results)
    if n == 0:
        raise ValueError("Cannot calculate metrics on empty results list.")

    good_wins = sum(1 for r in results if r.winner and r.winner.value == "good")
    evil_wins = sum(1 for r in results if r.winner and r.winner.value == "evil")

    days_list = [r.total_days for r in results]
    avg_days = statistics.mean(days_list)
    med_days = statistics.median(days_list)

    d1_executions = 0
    total_nominations = 0
    total_executions = 0
    virgin_procs = 0
    slayer_shots = 0
    end_reasons: dict[str, int] = {}

    for r in results:
        reason = r.end_reason or "unknown"
        end_reasons[reason] = end_reasons.get(reason, 0) + 1

        has_d1_exec = False
        for e in r.events:
            etype = e.get("type")
            day = e.get("day", 0)

            if etype == "NOMINATION":
                total_nominations += 1
            elif etype == "EXECUTION":
                total_executions += 1
                if day == 1:
                    has_d1_exec = True
            elif etype == "VIRGIN_PROC":
                virgin_procs += 1
            elif etype == "SLAYER_SHOT":
                slayer_shots += 1

        if has_d1_exec:
            d1_executions += 1

    return PopulationMetrics(
        total_games=n,
        good_win_rate=good_wins / n,
        evil_win_rate=evil_wins / n,
        avg_game_length_days=avg_days,
        median_game_length_days=float(med_days),
        d1_execution_rate=d1_executions / n,
        avg_nominations_per_game=total_nominations / n,
        avg_executions_per_game=total_executions / n,
        virgin_proc_rate=virgin_procs / n,
        slayer_shot_rate=slayer_shots / n,
        end_reasons_distribution=end_reasons,
    )
