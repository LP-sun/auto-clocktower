#!/usr/bin/env python3
"""High-performance mathematical simulation framework for Blood on the Clocktower (Trouble Brewing)."""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from src.analytics.metrics import calculate_population_metrics
from src.datasets.exporter import export_st_dataset, export_trajectories
from src.simulation.batch import simulate_batch
from src.storyteller.st_policy import StorytellerPolicy


def main() -> None:
    parser = argparse.ArgumentParser(description="Blood on the Clocktower Mathematical Simulator")
    parser.add_argument("--script", type=str, default="trouble_brewing", help="Script name (default: trouble_brewing)")
    parser.add_argument("--games", type=int, default=1000, help="Number of games to simulate")
    parser.add_argument("--players", type=int, default=12, help="Number of players (default: 12)")
    parser.add_argument("--seed", type=int, default=42, help="Base random seed")
    parser.add_argument("--workers", type=int, default=None, help="Number of parallel workers")
    parser.add_argument("--output-dir", type=str, default="output", help="Directory to save output datasets")
    parser.add_argument("--no-parallel", action="store_true", help="Disable multiprocessing")
    args = parser.parse_args()

    print("=" * 65)
    print(" BLOOD ON THE CLOCKTOWER: MATHEMATICAL MODELING SIMULATOR")
    print("=" * 65)
    print(f"Script: {args.script} | Players: {args.players} | Games: {args.games:,} | Seed: {args.seed}")
    print(f"Parallel: {not args.no_parallel} (Workers: {args.workers or 'auto'})")
    print("Running simulations...")

    t0 = time.perf_counter()
    results, summary = simulate_batch(
        n_games=args.games,
        player_count=args.players,
        base_seed=args.seed,
        parallel=not args.no_parallel,
        workers=args.workers,
    )
    elapsed = time.perf_counter() - t0

    metrics = calculate_population_metrics(results)

    print("\n" + "-" * 65)
    print(" SIMULATION SUMMARY & POPULATION METRICS")
    print("-" * 65)
    print(f"Completed Games:          {metrics.total_games:,} in {elapsed:.2f}s ({summary.games_per_second:.1f} games/s)")
    print(f"Good Win Rate:            {metrics.good_win_rate * 100:.1f}% ({summary.good_wins} wins)")
    print(f"Evil Win Rate:            {metrics.evil_win_rate * 100:.1f}% ({summary.evil_wins} wins)")
    print(f"Average Game Length:      {metrics.avg_game_length_days:.2f} days (Median: {metrics.median_game_length_days:.0f})")
    print(f"Day 1 Execution Rate:     {metrics.d1_execution_rate * 100:.1f}%")
    print(f"Avg Nominations / Game:   {metrics.avg_nominations_per_game:.2f}")
    print(f"Avg Executions / Game:    {metrics.avg_executions_per_game:.2f}")
    print(f"Virgin Execution Rate:    {metrics.virgin_proc_rate * 100:.2f}%")
    print(f"Slayer Shot Rate:         {metrics.slayer_shot_rate * 100:.2f}%")
    print("\nVictory End Reasons Breakdown:")
    for reason, count in sorted(metrics.end_reasons_distribution.items(), key=lambda x: x[1], reverse=True):
        print(f"  - {reason:25s}: {count:5d} ({count / metrics.total_games * 100:.1f}%)")

    # Export datasets
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    metrics_file = out_dir / "metrics.json"
    with metrics_file.open("w", encoding="utf-8") as f:
        json.dump(metrics.to_dict(), f, indent=2, ensure_ascii=False)

    trajectories_file = out_dir / "trajectories.jsonl"
    traj_count = export_trajectories(results[:1000], trajectories_file)  # Export up to 1000 full trajectories

    print("\n" + "-" * 65)
    print(" DATASET EXPORTS")
    print("-" * 65)
    print(f"Metrics JSON:             {metrics_file}")
    print(f"Trajectories JSONL:       {trajectories_file} ({traj_count} trajectories saved)")
    print("=" * 65)


if __name__ == "__main__":
    main()
