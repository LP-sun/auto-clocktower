"""Human Game Structure Benchmark and Survival Analysis for Trouble Brewing."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.simulation.runner import SimulationResult


@dataclass(slots=True)
class DeathTempo:
    p_zero_deaths: float = 0.0
    p_one_death: float = 0.0
    p_two_deaths: float = 0.0
    p_more_than_two: float = 0.0
    mean_deaths_per_cycle: float = 0.0
    mean_day_deaths: float = 0.0
    mean_night_deaths: float = 0.0
    total_cycles_observed: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "p_0_death": round(self.p_zero_deaths, 4),
            "p_1_death": round(self.p_one_death, 4),
            "p_2_deaths": round(self.p_two_deaths, 4),
            "p_gt_2_deaths": round(self.p_more_than_two, 4),
            "mean_deaths_per_cycle": round(self.mean_deaths_per_cycle, 4),
            "mean_day_deaths": round(self.mean_day_deaths, 4),
            "mean_night_deaths": round(self.mean_night_deaths, 4),
            "total_cycles_observed": self.total_cycles_observed,
        }


@dataclass(slots=True)
class SurvivalFunnel:
    # Full granularity alive counts: 12 down to 2
    alive_counts: dict[int, int] = field(default_factory=lambda: {k: 0 for k in range(12, 1, -1)})
    alive_rates: dict[int, float] = field(default_factory=lambda: {k: 0.0 for k in range(12, 1, -1)})
    total_games: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "alive_counts": {str(k): v for k, v in self.alive_counts.items()},
            "alive_rates": {str(k): round(v, 4) for k, v in self.alive_rates.items()},
            "display_rates_12_10_8_6_4_3": {
                str(k): round(self.alive_rates.get(k, 0.0), 4)
                for k in [12, 10, 8, 6, 4, 3]
            },
        }


@dataclass(slots=True)
class NominationMetrics:
    avg_nominations_per_day: float = 0.0
    no_execution_day_rate: float = 0.0
    total_days_observed: int = 0
    total_nominations: int = 0
    total_no_execution_days: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "avg_nominations_per_day": round(self.avg_nominations_per_day, 4),
            "no_execution_day_rate": round(self.no_execution_day_rate, 4),
            "total_days_observed": self.total_days_observed,
            "total_nominations": self.total_nominations,
            "total_no_execution_days": self.total_no_execution_days,
        }


@dataclass(slots=True)
class HumanStructureBenchmark:
    total_games: int = 0
    # Day-start late game benchmarks (primary metrics for human comparisons)
    reached_4_alive_day_rate_all: float = 0.0
    reached_4_alive_day_rate_non_special: float = 0.0
    reached_3_alive_day_rate_all: float = 0.0
    reached_3_alive_day_rate_non_special: float = 0.0

    # Ever-had state benchmarks (secondary metrics)
    ever_had_4_alive_rate_all: float = 0.0
    ever_had_3_alive_rate_all: float = 0.0

    # Survival funnel (full 12..2)
    survival_funnel: SurvivalFunnel = field(default_factory=SurvivalFunnel)

    # Hazard rates h_d = P(End on day d | Reach day d)
    hazard_rates: dict[int, float] = field(default_factory=dict)

    # Death tempo
    death_tempo: DeathTempo = field(default_factory=DeathTempo)

    # Early end breakdown (3-tier taxonomy)
    early_end_counts: dict[str, int] = field(default_factory=dict)
    early_end_rates: dict[str, float] = field(default_factory=dict)

    # Nomination saturation & no-execution
    nomination_metrics: NominationMetrics = field(default_factory=NominationMetrics)

    # Status tag
    status: str = "HUMAN_BENCHMARK_PENDING"

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "total_games": self.total_games,
            "late_game_metrics": {
                "reached_4_alive_day_rate_all": round(self.reached_4_alive_day_rate_all, 4),
                "reached_4_alive_day_rate_non_special": round(self.reached_4_alive_day_rate_non_special, 4),
                "reached_3_alive_day_rate_all": round(self.reached_3_alive_day_rate_all, 4),
                "reached_3_alive_day_rate_non_special": round(self.reached_3_alive_day_rate_non_special, 4),
                "ever_had_4_alive_rate_all": round(self.ever_had_4_alive_rate_all, 4),
                "ever_had_3_alive_rate_all": round(self.ever_had_3_alive_rate_all, 4),
            },
            "survival_funnel": self.survival_funnel.to_dict(),
            "hazard_rates": {str(k): round(v, 4) for k, v in self.hazard_rates.items()},
            "death_tempo": self.death_tempo.to_dict(),
            "early_end_taxonomy": {
                "counts": self.early_end_counts,
                "rates": {k: round(v, 4) for k, v in self.early_end_rates.items()},
            },
            "nomination_metrics": self.nomination_metrics.to_dict(),
        }


def compute_human_structure_benchmark(results: list[SimulationResult]) -> HumanStructureBenchmark:
    """Compute human game structure benchmark over a set of simulation results."""
    n_games = len(results)
    if n_games == 0:
        return HumanStructureBenchmark()

    # 1. Late game & day-start metrics
    count_reached_4 = sum(1 for r in results if getattr(r, "reached_4_alive_day", False))
    count_reached_3 = sum(1 for r in results if getattr(r, "reached_3_alive_day", False))
    count_ever_4 = sum(1 for r in results if getattr(r, "ever_had_4_alive_state", False))
    count_ever_3 = sum(1 for r in results if getattr(r, "ever_had_3_alive_state", False))

    # Early end categorization
    early_end_counts: dict[str, int] = {
        "RULE_SPECIAL_END": 0,
        "ORDINARY_BUT_EARLY_END": 0,
        "STRUCTURAL_COLLAPSE_CANDIDATE": 0,
        "NORMAL_END": 0,
    }
    non_special_results: list[SimulationResult] = []

    for r in results:
        cat = getattr(r, "early_end_category", None)
        if not cat:
            cat = "NORMAL_END"
        early_end_counts[cat] = early_end_counts.get(cat, 0) + 1
        if cat != "RULE_SPECIAL_END":
            non_special_results.append(r)

    n_non_special = len(non_special_results)
    reached_4_non_special = (
        sum(1 for r in non_special_results if getattr(r, "reached_4_alive_day", False)) / n_non_special
        if n_non_special > 0 else 0.0
    )
    reached_3_non_special = (
        sum(1 for r in non_special_results if getattr(r, "reached_3_alive_day", False)) / n_non_special
        if n_non_special > 0 else 0.0
    )

    # 2. Survival funnel (complete 12..2 alive counts)
    funnel_counts = {k: 0 for k in range(12, 1, -1)}
    for r in results:
        traj = getattr(r, "alive_trajectory", [])
        observed_alives = set(traj)
        # If trajectory is empty, fall back to initial and final alive
        if not observed_alives:
            observed_alives.add(12)  # default initial
            observed_alives.add(getattr(r, "alive_count", 3))
        for k in range(12, 1, -1):
            if any(a <= k for a in observed_alives):
                funnel_counts[k] += 1

    funnel_rates = {k: funnel_counts[k] / n_games for k in funnel_counts}
    survival_funnel = SurvivalFunnel(
        alive_counts=funnel_counts,
        alive_rates=funnel_rates,
        total_games=n_games,
    )

    # 3. Hazard rate h_d = P(End on day d | Reach day d)
    day_reached_counts: dict[int, int] = {}
    day_ended_counts: dict[int, int] = {}
    max_day = 1
    for r in results:
        end_day = r.days
        max_day = max(max_day, end_day)
        day_ended_counts[end_day] = day_ended_counts.get(end_day, 0) + 1
        for d in range(1, end_day + 1):
            day_reached_counts[d] = day_reached_counts.get(d, 0) + 1

    hazard_rates: dict[int, float] = {}
    for d in range(1, max_day + 1):
        reached = day_reached_counts.get(d, 0)
        ended = day_ended_counts.get(d, 0)
        hazard_rates[d] = (ended / reached) if reached > 0 else 0.0

    # 4. Death tempo (distribution of deaths per cycle, day, night)
    all_cycle_deaths: list[int] = []
    all_day_deaths: list[int] = []
    all_night_deaths: list[int] = []
    for r in results:
        cycle_deaths = getattr(r, "cycle_deaths", {})
        if isinstance(cycle_deaths, dict):
            all_cycle_deaths.extend(cycle_deaths.values())
        elif isinstance(cycle_deaths, (list, tuple)):
            all_cycle_deaths.extend(cycle_deaths)

        day_deaths = getattr(r, "actual_day_deaths", {})
        if isinstance(day_deaths, dict):
            all_day_deaths.extend(day_deaths.values())

        night_deaths = getattr(r, "actual_night_deaths", {})
        if isinstance(night_deaths, dict):
            all_night_deaths.extend(night_deaths.values())

    if all_cycle_deaths:
        n_cycles = len(all_cycle_deaths)
        p0 = sum(1 for c in all_cycle_deaths if c == 0) / n_cycles
        p1 = sum(1 for c in all_cycle_deaths if c == 1) / n_cycles
        p2 = sum(1 for c in all_cycle_deaths if c == 2) / n_cycles
        pgt2 = sum(1 for c in all_cycle_deaths if c > 2) / n_cycles
        mean_d = sum(all_cycle_deaths) / n_cycles

        mean_day = sum(all_day_deaths) / len(all_day_deaths) if all_day_deaths else 0.0
        mean_night = sum(all_night_deaths) / len(all_night_deaths) if all_night_deaths else 0.0

        death_tempo = DeathTempo(
            p_zero_deaths=p0,
            p_one_death=p1,
            p_two_deaths=p2,
            p_more_than_two=pgt2,
            mean_deaths_per_cycle=mean_d,
            mean_day_deaths=mean_day,
            mean_night_deaths=mean_night,
            total_cycles_observed=n_cycles,
        )
    else:
        death_tempo = DeathTempo()

    # 5. Nomination saturation & no-execution rate
    total_days = sum(r.days for r in results)
    total_noms = 0
    no_exec_days = 0
    for r in results:
        # Check executions vs days
        exec_count = getattr(r, "executions_count", 0)
        if r.days > exec_count:
            no_exec_days += (r.days - exec_count)
        # Approximated nomination count from nominations_count if tracked
        total_noms += getattr(r, "nominations_count", r.days * 2)

    nom_metrics = NominationMetrics(
        avg_nominations_per_day=(total_noms / total_days) if total_days > 0 else 0.0,
        no_execution_day_rate=(no_exec_days / total_days) if total_days > 0 else 0.0,
        total_days_observed=total_days,
        total_nominations=total_noms,
        total_no_execution_days=no_exec_days,
    )

    return HumanStructureBenchmark(
        total_games=n_games,
        reached_4_alive_day_rate_all=count_reached_4 / n_games,
        reached_4_alive_day_rate_non_special=reached_4_non_special,
        reached_3_alive_day_rate_all=count_reached_3 / n_games,
        reached_3_alive_day_rate_non_special=reached_3_non_special,
        ever_had_4_alive_rate_all=count_ever_4 / n_games,
        ever_had_3_alive_rate_all=count_ever_3 / n_games,
        survival_funnel=survival_funnel,
        hazard_rates=hazard_rates,
        death_tempo=death_tempo,
        early_end_counts=early_end_counts,
        early_end_rates={k: v / n_games for k, v in early_end_counts.items()},
        nomination_metrics=nom_metrics,
        status="HUMAN_BENCHMARK_PENDING",
    )
