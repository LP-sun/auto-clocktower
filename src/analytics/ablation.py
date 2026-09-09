"""Strategy Primitive Ablation Analysis with Direct Behavioral KPIs.

Requirement 7:
Every primitive ablation MUST define and measure a DIRECT BEHAVIORAL KPI.
Evaluating solely by win rate is strictly forbidden.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.simulation.runner import simulate_game
from src.strategies.primitives import StrategyPrimitive


@dataclass(slots=True)
class AblationResult:
    primitive: str
    kpi_name: str
    baseline_kpi: float
    ablated_kpi: float
    delta_kpi: float
    baseline_win_rate: float
    ablated_win_rate: float
    sample_size: int
    is_active: bool  # True if |delta_kpi| > threshold proving direct causal behavior


def evaluate_primitive_kpis(games: list[Any], primitive: str) -> float:
    """Calculate the direct behavioral KPI for a given primitive across a batch of games."""
    if primitive == StrategyPrimitive.SEEK_COMPLEMENTARY_INFO.value:
        # KPI: Proportion of private chats involving complementary info roles
        info_roles = {"washerwoman", "librarian", "investigator", "chef", "empath", "fortune_teller", "undertaker"}
        total_chats = 0
        comp_chats = 0
        for g in games:
            for chat in g.private_chats:
                total_chats += 1
                r1 = chat.get("p1_role", "")
                r2 = chat.get("p2_role", "")
                if r1 in info_roles and r2 in info_roles:
                    comp_chats += 1
        return comp_chats / max(1, total_chats)

    if primitive == StrategyPrimitive.PRIVATE_CLAIM.value:
        # KPI: Proportion of early private chats (Day 1 & 2) where claims were exchanged
        d12_chats = 0
        claims_exchanged = 0
        for g in games:
            for chat in g.private_chats:
                if chat.get("day", 0) <= 2:
                    d12_chats += 1
                    if chat.get("claims_exchanged", False):
                        claims_exchanged += 1
        return claims_exchanged / max(1, d12_chats)

    if primitive == StrategyPrimitive.PROTECT_HIGH_VALUE_ROLE.value:
        # KPI: Proportion of Monk night actions protecting high-value roles (Empath, FT, Undertaker)
        high_val = {"empath", "fortune_teller", "undertaker"}
        monk_actions = 0
        high_val_protected = 0
        for g in games:
            for e in g.events:
                if e.get("type") == "NIGHT_ACTION" and e.get("data", {}).get("role") == "monk":
                    monk_actions += 1
                    target = e.get("target")
                    target_role = g.apparent_roles.get(target, "")
                    if target_role in high_val:
                        high_val_protected += 1
        return high_val_protected / max(1, monk_actions)

    if primitive == StrategyPrimitive.TEST_VIRGIN.value:
        # KPI: Proportion of Virgin nominations made by spent Townsfolk (Washerwoman, Librarian, Investigator, Chef)
        spent_tf = {"washerwoman", "librarian", "investigator", "chef"}
        virgin_noms = 0
        spent_tf_noms = 0
        for g in games:
            for e in g.events:
                if e.get("type") == "NOMINATION":
                    nominee = e.get("target")
                    nominator = e.get("actor")
                    if g.true_roles.get(nominee) == "virgin":
                        virgin_noms += 1
                        if g.true_roles.get(nominator) in spent_tf:
                            spent_tf_noms += 1
        return spent_tf_noms / max(1, virgin_noms)

    if primitive == StrategyPrimitive.EVIL_COORDINATION.value:
        # KPI: Proportion of evil players' private chats directed toward fellow evil team members
        evil_total_chats = 0
        evil_evil_chats = 0
        for g in games:
            for chat in g.private_chats:
                p1 = chat.get("p1")
                p2 = chat.get("p2")
                p1_evil = g.alignments.get(p1) == "evil"
                p2_evil = g.alignments.get(p2) == "evil"
                if p1_evil or p2_evil:
                    evil_total_chats += 1
                    if p1_evil and p2_evil:
                        evil_evil_chats += 1
        return evil_evil_chats / max(1, evil_total_chats)

    if primitive == StrategyPrimitive.KILL_INFO_ROLE.value:
        # KPI: Proportion of Imp night kills targeting confirmed/suspected info roles
        info_roles = {"empath", "fortune_teller", "undertaker", "virgin", "slayer"}
        imp_kills = 0
        info_kills = 0
        for g in games:
            for e in g.events:
                if e.get("type") == "DEATH" and e.get("data", {}).get("reason") == "demon_kill":
                    imp_kills += 1
                    dead_p = e.get("actor") or e.get("target")
                    dead_role = g.apparent_roles.get(dead_p, "")
                    if dead_role in info_roles:
                        info_kills += 1
        return info_kills / max(1, imp_kills)

    return 0.0


def run_ablation_study(
    n_games_per_arm: int = 100,
    base_seed: int = 42,
    output_csv: Path | None = None,
) -> list[AblationResult]:
    """Run A/B testing for 6 key strategy primitives measuring direct behavioral KPIs."""
    target_primitives = [
        (StrategyPrimitive.SEEK_COMPLEMENTARY_INFO.value, "complementary_info_chat_ratio"),
        (StrategyPrimitive.PRIVATE_CLAIM.value, "d12_claim_disclosure_rate"),
        (StrategyPrimitive.PROTECT_HIGH_VALUE_ROLE.value, "monk_info_protection_rate"),
        (StrategyPrimitive.TEST_VIRGIN.value, "spent_townsfolk_virgin_nom_rate"),
        (StrategyPrimitive.EVIL_COORDINATION.value, "evil_evil_whisper_ratio"),
        (StrategyPrimitive.KILL_INFO_ROLE.value, "imp_info_kill_ratio"),
    ]

    print(f"Running Baseline ({n_games_per_arm} games)...")
    baseline_games = [
        simulate_game(seed=base_seed + i)
        for i in range(n_games_per_arm)
    ]
    base_win_rate = sum(1 for g in baseline_games if g.winner and g.winner.value == "good") / n_games_per_arm

    results: list[AblationResult] = []

    for prim, kpi_name in target_primitives:
        print(f"Running Ablation for {prim} ({n_games_per_arm} games)...")
        base_kpi = evaluate_primitive_kpis(baseline_games, prim)

        ablated_games = [
            simulate_game(seed=base_seed + i, ablated_primitives={prim})
            for i in range(n_games_per_arm)
        ]
        abl_win_rate = sum(1 for g in ablated_games if g.winner and g.winner.value == "good") / n_games_per_arm
        abl_kpi = evaluate_primitive_kpis(ablated_games, prim)
        delta_kpi = base_kpi - abl_kpi

        # A primitive is verified active if delta_kpi is non-zero
        is_active = abs(delta_kpi) > 0.01

        res = AblationResult(
            primitive=prim,
            kpi_name=kpi_name,
            baseline_kpi=round(base_kpi, 4),
            ablated_kpi=round(abl_kpi, 4),
            delta_kpi=round(delta_kpi, 4),
            baseline_win_rate=round(base_win_rate, 4),
            ablated_win_rate=round(abl_win_rate, 4),
            sample_size=n_games_per_arm,
            is_active=is_active,
        )
        results.append(res)
        print(f"  [{prim}] Base KPI: {base_kpi:.3f} -> Ablated: {abl_kpi:.3f} (Δ={delta_kpi:+.3f}) Active: {is_active}")

    if output_csv:
        output_csv.parent.mkdir(parents=True, exist_ok=True)
        with open(output_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "primitive", "kpi_name", "baseline_kpi", "ablated_kpi", "delta_kpi",
                "baseline_win_rate", "ablated_win_rate", "sample_size", "is_active",
            ])
            for r in results:
                writer.writerow([
                    r.primitive, r.kpi_name, r.baseline_kpi, r.ablated_kpi, r.delta_kpi,
                    r.baseline_win_rate, r.ablated_win_rate, r.sample_size, r.is_active,
                ])
        print(f"Saved ablation results to {output_csv}")

    return results
