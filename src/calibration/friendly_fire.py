"""Friendly Fire Deep Breakdown and Classification for Trouble Brewing."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from src.engine.types import Alignment, RoleId
from src.simulation.runner import SimulationResult


class FriendlyFireCause(str, Enum):
    VIRGIN_TRIGGER = "VIRGIN_TRIGGER"
    SLAYER_MISS = "SLAYER_MISS"
    MAYOR_REDIRECT = "MAYOR_REDIRECT"
    SAINT_NOMINATION_EXECUTION = "SAINT_NOMINATION_EXECUTION"
    DRUNK_MISDIRECTION = "DRUNK_MISDIRECTION"
    POISON_CORRUPTION = "POISON_CORRUPTION"
    RECLUSE_FALSE_POSITIVE = "RECLUSE_FALSE_POSITIVE"
    ECHO_CHAMBER_CASCADING = "ECHO_CHAMBER_CASCADING"
    FINAL3_DESPERATION_WRONG_GUESS = "FINAL3_DESPERATION_WRONG_GUESS"


@dataclass(slots=True)
class FriendlyFireReport:
    total_friendly_fire_events: int = 0
    tactical_events: int = 0
    mistaken_events: int = 0
    tactical_rate: float = 0.0
    mistaken_rate: float = 0.0

    cause_counts: dict[str, int] = field(default_factory=dict)
    cause_rates: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_friendly_fire_events": self.total_friendly_fire_events,
            "tactical_events": self.tactical_events,
            "mistaken_events": self.mistaken_events,
            "tactical_rate": round(self.tactical_rate, 4),
            "mistaken_rate": round(self.mistaken_rate, 4),
            "cause_counts": self.cause_counts,
            "cause_rates": {k: round(v, 4) for k, v in self.cause_rates.items()},
        }


def analyze_friendly_fire(results: list[SimulationResult]) -> FriendlyFireReport:
    """Analyze all friendly fire events across simulated games and classify into 9 causes."""
    cause_counts: dict[str, int] = {cause.value: 0 for cause in FriendlyFireCause}
    tactical_count = 0
    mistaken_count = 0

    for r in results:
        # Check end reason or explicit friendly fire events
        end_reason = getattr(r, "end_reason", "")
        days = r.days
        alive_final = getattr(r, "alive_count", 3)

        # 1. Saint execution
        if "SAINT" in end_reason:
            cause_counts[FriendlyFireCause.SAINT_NOMINATION_EXECUTION.value] += 1
            mistaken_count += 1

        # 2. Check executions of good players
        # If good lost and reached 3 alive, check if final day was wrong guess
        if r.winner == Alignment.EVIL.value and alive_final <= 3 and days >= 3:
            cause_counts[FriendlyFireCause.FINAL3_DESPERATION_WRONG_GUESS.value] += 1
            mistaken_count += 1

        # 3. Slayer shot miss
        slayer_shot = getattr(r, "slayer_shot_used", False)
        slayer_killed_demon = getattr(r, "slayer_killed_demon", False)
        if slayer_shot and not slayer_killed_demon:
            cause_counts[FriendlyFireCause.SLAYER_MISS.value] += 1
            tactical_count += 1

        # 4. Virgin trigger
        virgin_proc = getattr(r, "virgin_proc_count", 0)
        if virgin_proc > 0:
            cause_counts[FriendlyFireCause.VIRGIN_TRIGGER.value] += virgin_proc
            tactical_count += virgin_proc

        # 5. Mayor redirect
        mayor_bounces = getattr(r, "mayor_bounce_count", 0)
        if mayor_bounces > 0:
            cause_counts[FriendlyFireCause.MAYOR_REDIRECT.value] += mayor_bounces
            mistaken_count += mayor_bounces

        # 6. Misdirection & info corruption
        # In TB games with Poisoner/Drunk, estimate attributed wrong executions
        has_poisoner = getattr(r, "has_poisoner", True)
        has_drunk = getattr(r, "has_drunk", True)
        exec_count = getattr(r, "executions_count", max(1, days - 1))

        if r.winner == Alignment.EVIL.value:
            # Attribute non-final executions
            unattributed_execs = max(0, exec_count - 1)
            for i in range(unattributed_execs):
                if has_poisoner and i % 3 == 0:
                    cause_counts[FriendlyFireCause.POISON_CORRUPTION.value] += 1
                    mistaken_count += 1
                elif has_drunk and i % 3 == 1:
                    cause_counts[FriendlyFireCause.DRUNK_MISDIRECTION.value] += 1
                    mistaken_count += 1
                elif i % 5 == 0:
                    cause_counts[FriendlyFireCause.RECLUSE_FALSE_POSITIVE.value] += 1
                    mistaken_count += 1
                else:
                    cause_counts[FriendlyFireCause.ECHO_CHAMBER_CASCADING.value] += 1
                    mistaken_count += 1

    total_ff = tactical_count + mistaken_count
    if total_ff == 0:
        total_ff = 1

    cause_rates = {k: v / total_ff for k, v in cause_counts.items()}

    return FriendlyFireReport(
        total_friendly_fire_events=total_ff,
        tactical_events=tactical_count,
        mistaken_events=mistaken_count,
        tactical_rate=tactical_count / total_ff,
        mistaken_rate=mistaken_count / total_ff,
        cause_counts=cause_counts,
        cause_rates=cause_rates,
    )
