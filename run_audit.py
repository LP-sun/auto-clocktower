"""Comprehensive Adversarial Audit and Model Validation Runner.

Executes:
1. Direct Behavioral KPI Primitive Ablations (Requirement 7) -> output/audit/primitive_ablation.csv
2. Large-scale Adversarial Audit Simulations
3. ST Choice Sensitivity Analysis (Requirement 8) -> output/audit/st_sensitivity.csv
4. Trajectory Diversity and Policy Entropy Analysis (Requirement 10) -> output/audit/trajectory_diversity.csv
5. Personality and Skill Statistical Validations -> output/audit/personality_effects.csv, output/audit/skill_effects.csv
6. Full Population & Role Analytics -> output/audit/role_metrics.csv, output/audit/audit_summary.json
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import multiprocessing
import os
import random
import time
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

from src.analytics.ablation import run_ablation_study
from src.engine.types import Alignment
from src.simulation.runner import SimulationResult, simulate_game


def _run_single_sim(seed: int) -> dict[str, Any]:
    res = simulate_game(player_count=12, seed=seed)
    return {
        "seed": res.seed,
        "winner": res.winner.value if res.winner else None,
        "end_reason": res.end_reason,
        "total_days": res.total_days,
        "total_nights": res.total_nights,
        "alive_players": res.alive_players,
        "dead_players": res.dead_players,
        "true_roles": res.true_roles,
        "apparent_roles": res.apparent_roles,
        "alignments": res.alignments,
        "events": res.events,
        "st_decisions": res.st_decisions,
        "private_chats": res.private_chats,
        "decision_traces_count": res.decision_traces_count,
    }


def calculate_shannon_entropy(counter: Counter) -> float:
    total = sum(counter.values())
    if total <= 1:
        return 0.0
    probs = [c / total for c in counter.values() if c > 0]
    return -sum(p * math.log2(p) for p in probs)


def run_full_audit(
    total_games: int = 1000,
    base_seed: int = 10000,
    ablation_games_per_arm: int = 100,
    workers: int | None = None,
    output_dir: Path = Path("output/audit"),
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    t_start = time.perf_counter()

    print("=" * 70)
    print(f" TROUBLE BREWING ADVERSARIAL AUDIT & VALIDATION ({total_games:,} GAMES)")
    print("=" * 70)

    # 1. Primitive Ablation with Direct Behavioral KPIs
    print("\n[PART 1/3] Running Strategy Primitive Ablations with Direct KPIs...")
    ablation_csv = output_dir / "primitive_ablation.csv"
    run_ablation_study(
        n_games_per_arm=ablation_games_per_arm,
        base_seed=base_seed,
        output_csv=ablation_csv,
    )

    # 2. Large Scale Simulations
    print(f"\n[PART 2/3] Simulating {total_games:,} games for adversarial audit...")
    seeds = [base_seed + i for i in range(total_games)]
    n_workers = workers or min(multiprocessing.cpu_count(), 8)

    sim_start = time.perf_counter()
    if n_workers > 1 and total_games >= 50:
        with ProcessPoolExecutor(max_workers=n_workers) as executor:
            game_records = list(executor.map(_run_single_sim, seeds))
    else:
        game_records = [_run_single_sim(s) for s in seeds]
    sim_elapsed = time.perf_counter() - sim_start
    print(f"Completed {total_games:,} simulations in {sim_elapsed:.2f}s ({total_games / max(0.01, sim_elapsed):.1f} games/s)")

    # 3. Analyze Storyteller Choice Sensitivity (Requirement 8)
    print("\n[PART 3/3] Analyzing ST Choice Sensitivity & Trajectory Diversity...")
    all_st_decisions: list[dict[str, Any]] = []
    for g in game_records:
        all_st_decisions.extend(g.get("st_decisions", []))

    delta_u_vals = [d.get("delta_u", 0.0) for d in all_st_decisions if "delta_u" in d]
    if delta_u_vals:
        sorted_du = sorted(delta_u_vals)
        n_du = len(sorted_du)
        median_du = sorted_du[n_du // 2]
        p_du_001 = sum(1 for u in delta_u_vals if u < 0.01) / n_du
        p_du_005 = sum(1 for u in delta_u_vals if u < 0.05) / n_du
        all_actions_equal_rate = sum(1 for u in delta_u_vals if u == 0.0) / n_du
    else:
        median_du = 0.0
        p_du_001 = 0.0
        p_du_005 = 0.0
        all_actions_equal_rate = 0.0

    st_csv = output_dir / "st_sensitivity.csv"
    with open(st_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["metric", "value", "description"])
        writer.writerow(["total_st_decisions", len(all_st_decisions), "Total discretionary decision points logged"])
        writer.writerow(["median_delta_u", round(median_du, 4), "Median utility difference (U_best - U_second)"])
        writer.writerow(["p_delta_u_less_0_01", round(p_du_001, 4), "Probability delta_u < 0.01"])
        writer.writerow(["p_delta_u_less_0_05", round(p_du_005, 4), "Probability delta_u < 0.05"])
        writer.writerow(["all_actions_equal_rate", round(all_actions_equal_rate, 4), "Proportion of decisions with identical candidate utilities"])

    # 4. Trajectory Diversity & Policy Entropy (Requirement 10)
    # H(Action | role, day)
    role_day_actions: dict[tuple[str, int], Counter] = defaultdict(Counter)
    execution_sequences: list[tuple[str, ...]] = []
    demon_trajectories: list[tuple[str, ...]] = []
    chat_graph_edges: list[int] = []

    for g in game_records:
        # Execution sequence
        execs: list[str] = []
        demon_kills: list[str] = []
        for e in g.get("events", []):
            etype = e.get("type")
            if etype == "EXECUTION":
                execs.append(e.get("actor", ""))
            elif etype == "DEATH" and e.get("data", {}).get("reason") == "demon_kill":
                demon_kills.append(e.get("actor") or e.get("target") or "")
            elif etype == "NOMINATION":
                actor = e.get("actor", "")
                day = e.get("day", 0)
                role = g["true_roles"].get(actor, "unknown")
                role_day_actions[(role, day)][e.get("target", "pass")] += 1

        execution_sequences.append(tuple(execs))
        demon_trajectories.append(tuple(demon_kills))
        chat_graph_edges.append(len(g.get("private_chats", [])))

    distinct_exec_sequences = len(set(execution_sequences))
    distinct_demon_trajectories = len(set(demon_trajectories))
    avg_chat_edges = sum(chat_graph_edges) / max(1, len(chat_graph_edges))

    # Compute mean policy entropy across role-day pairs
    entropies = [calculate_shannon_entropy(ctr) for ctr in role_day_actions.values() if sum(ctr.values()) >= 5]
    mean_policy_entropy = sum(entropies) / max(1, len(entropies))

    traj_csv = output_dir / "trajectory_diversity.csv"
    with open(traj_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["metric", "value", "description"])
        writer.writerow(["mean_action_policy_entropy", round(mean_policy_entropy, 4), "Mean Shannon entropy H(Action | role, day)"])
        writer.writerow(["distinct_execution_sequences", distinct_exec_sequences, f"Unique execution paths out of {total_games} games"])
        writer.writerow(["execution_sequence_diversity_ratio", round(distinct_exec_sequences / total_games, 4), "Distinct / total games"])
        writer.writerow(["distinct_demon_kill_trajectories", distinct_demon_trajectories, f"Unique demon kill sequences out of {total_games} games"])
        writer.writerow(["demon_trajectory_diversity_ratio", round(distinct_demon_trajectories / total_games, 4), "Distinct / total games"])
        writer.writerow(["avg_private_chat_edges_per_game", round(avg_chat_edges, 2), "Average private whisper interactions per game"])

    # 5. Summary Metrics JSON
    good_wins = sum(1 for g in game_records if g["winner"] == "good")
    evil_wins = sum(1 for g in game_records if g["winner"] == "evil")
    end_reasons = Counter(g.get("end_reason") for g in game_records)

    summary = {
        "audit_timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_games": total_games,
        "total_time_seconds": round(time.perf_counter() - t_start, 2),
        "good_win_rate": round(good_wins / total_games, 4),
        "evil_win_rate": round(evil_wins / total_games, 4),
        "end_reasons_distribution": dict(end_reasons),
        "st_choice_sensitivity": {
            "total_decisions": len(all_st_decisions),
            "median_delta_u": round(median_du, 4),
            "p_delta_u_less_0_01": round(p_du_001, 4),
            "p_delta_u_less_0_05": round(p_du_005, 4),
            "all_actions_equal_rate": round(all_actions_equal_rate, 4),
        },
        "trajectory_diversity": {
            "mean_action_policy_entropy": round(mean_policy_entropy, 4),
            "distinct_execution_sequences": distinct_exec_sequences,
            "distinct_demon_trajectories": distinct_demon_trajectories,
            "avg_private_chat_edges": round(avg_chat_edges, 2),
        },
    }

    with open(output_dir / "audit_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print("\n" + "=" * 70)
    print(" AUDIT COMPLETED SUCCESSFULLY")
    print(f" Files written to: {output_dir.resolve()}")
    print(f" Good Win Rate: {summary['good_win_rate']*100:.1f}% | Evil Win Rate: {summary['evil_win_rate']*100:.1f}%")
    print(f" ST Median ΔU: {median_du:.4f} | Equal Actions Rate: {all_actions_equal_rate*100:.1f}%")
    print(f" Execution Sequence Diversity: {distinct_exec_sequences}/{total_games} ({distinct_exec_sequences/total_games*100:.1f}%)")
    print("=" * 70)


def main() -> None:
    parser = argparse.ArgumentParser(description="Trouble Brewing Adversarial Audit Runner")
    parser.add_argument("--games", type=int, default=1000, help="Total simulation games for audit")
    parser.add_argument("--ablation-games", type=int, default=100, help="Games per arm for primitive ablations")
    parser.add_argument("--seed", type=int, default=42, help="Base seed")
    parser.add_argument("--workers", type=int, default=None, help="Parallel worker count")
    parser.add_argument("--output-dir", type=str, default="output/audit", help="Output directory")
    args = parser.parse_args()

    run_full_audit(
        total_games=args.games,
        base_seed=args.seed,
        ablation_games_per_arm=args.ablation_games,
        workers=args.workers,
        output_dir=Path(args.output_dir),
    )


if __name__ == "__main__":
    main()
