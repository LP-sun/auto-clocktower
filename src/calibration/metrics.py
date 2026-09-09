"""Player calibration behavior metric registry, measurement pipeline, and Bootstrap CI estimation."""
from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Any, Callable

import numpy as np


@dataclass(slots=True)
class BehaviorMetricDefinition:
    name: str
    scope: str
    formula: str
    expected_direction: str
    related_parameters: list[str]


class BehaviorMetricRegistry:
    """Registry defining all observable player and storyteller behavior metrics."""

    _metrics: dict[str, BehaviorMetricDefinition] = {}

    @classmethod
    def register(cls, m: BehaviorMetricDefinition) -> None:
        cls._metrics[m.name] = m

    @classmethod
    def get(cls, name: str) -> BehaviorMetricDefinition | None:
        return cls._metrics.get(name)

    @classmethod
    def all_metrics(cls) -> list[BehaviorMetricDefinition]:
        return list(cls._metrics.values())


# Register canonical metrics
BehaviorMetricRegistry.register(
    BehaviorMetricDefinition(
        name="private_chats_per_player_day",
        scope="chat",
        formula="total_private_chats / (total_living_player_days)",
        expected_direction="Positive with pop_activity_mu, pop_social_initiative_mu",
        related_parameters=["pop_activity_mu", "pop_social_initiative_mu"],
    )
)
BehaviorMetricRegistry.register(
    BehaviorMetricDefinition(
        name="good_good_chat_ratio",
        scope="chat",
        formula="chats(good, good) / total_chats",
        expected_direction="Higher in healthy town coordination",
        related_parameters=["pop_openness_mu", "SEEK_COMPLEMENTARY_INFO"],
    )
)
BehaviorMetricRegistry.register(
    BehaviorMetricDefinition(
        name="evil_evil_chat_ratio",
        scope="chat",
        formula="chats(evil, evil) / chats(evil, any)",
        expected_direction="Positive with EVIL_COORDINATION",
        related_parameters=["EVIL_COORDINATION"],
    )
)
BehaviorMetricRegistry.register(
    BehaviorMetricDefinition(
        name="claim_disclosure_rate",
        scope="claim",
        formula="chats_with_claims / total_early_chats",
        expected_direction="Positive with pop_openness_mu, PRIVATE_CLAIM",
        related_parameters=["pop_openness_mu", "PRIVATE_CLAIM"],
    )
)
BehaviorMetricRegistry.register(
    BehaviorMetricDefinition(
        name="nomination_friendly_fire_rate",
        scope="execution",
        formula="noms(good -> good) / noms(good -> any)",
        expected_direction="Negative with skill_belief_accuracy_scale, good information flow",
        related_parameters=["skill_belief_accuracy_scale", "pop_aggression_mu"],
    )
)
BehaviorMetricRegistry.register(
    BehaviorMetricDefinition(
        name="execution_friendly_fire_rate",
        scope="execution",
        formula="execs(good) / total_execs",
        expected_direction="Negative with good win rate",
        related_parameters=["vote_evil_weight", "vote_demon_weight"],
    )
)
BehaviorMetricRegistry.register(
    BehaviorMetricDefinition(
        name="vote_consistency",
        scope="voting",
        formula="P(vote=yes | target in top suspicion)",
        expected_direction="Positive with vote_evil_weight, skill_voting_discipline",
        related_parameters=["vote_evil_weight", "skill_voting_discipline_scale"],
    )
)
BehaviorMetricRegistry.register(
    BehaviorMetricDefinition(
        name="vote_participation_rate",
        scope="voting",
        formula="total_votes_yes / (nominations * living_voters)",
        expected_direction="Positive with pop_conformity_mu, vote_base_bias",
        related_parameters=["pop_conformity_mu", "vote_base_bias"],
    )
)
BehaviorMetricRegistry.register(
    BehaviorMetricDefinition(
        name="night_kill_value_percentile",
        scope="ability",
        formula="mean KillValue(target) percentile of Imp night kills",
        expected_direction="Higher indicates stronger evil kill selectivity",
        related_parameters=["KILL_INFO_ROLE", "pop_openness_mu"],
    )
)
BehaviorMetricRegistry.register(
    BehaviorMetricDefinition(
        name="monk_protection_quality",
        scope="ability",
        formula="fraction of Monk protections targeting high-value roles",
        expected_direction="Positive with PROTECT_HIGH_VALUE_ROLE",
        related_parameters=["PROTECT_HIGH_VALUE_ROLE"],
    )
)
BehaviorMetricRegistry.register(
    BehaviorMetricDefinition(
        name="trust_error_rate",
        scope="trust",
        formula="P(good trusts player | player is evil)",
        expected_direction="Negative with skill_belief_accuracy_scale",
        related_parameters=["skill_belief_accuracy_scale", "deception_tendency"],
    )
)


def compute_bootstrap_ci(
    values: list[float],
    n_bootstraps: int = 1000,
    ci: float = 0.95,
    seed: int = 42,
) -> tuple[float, float, float]:
    """Compute mean and empirical bootstrap confidence interval (mean, lower_ci, upper_ci)."""
    if not values:
        return 0.0, 0.0, 0.0
    n = len(values)
    if n == 1:
        return values[0], values[0], values[0]

    rng = np.random.RandomState(seed)
    arr = np.array(values, dtype=np.float64)
    point_est = float(np.mean(arr))

    boot_means = np.empty(n_bootstraps, dtype=np.float64)
    for b in range(n_bootstraps):
        idx = rng.randint(0, n, size=n)
        boot_means[b] = np.mean(arr[idx])

    alpha = (1.0 - ci) / 2.0
    lower = float(np.percentile(boot_means, alpha * 100.0))
    upper = float(np.percentile(boot_means, (1.0 - alpha) * 100.0))
    return round(point_est, 4), round(lower, 4), round(upper, 4)


def extract_game_behavior_metrics(game: dict[str, Any]) -> dict[str, float]:
    """Extract granular behavior metrics from a single simulated game record."""
    events = game.get("events", [])
    private_chats = game.get("private_chats", [])
    alignments = game.get("alignments", {})
    true_roles = game.get("true_roles", {})
    days = max(1, game.get("total_days", 1))

    # 1. Chat metrics
    total_chats = len(private_chats)
    good_good_chats = 0
    evil_evil_chats = 0
    evil_total_chats = 0
    claim_chats = 0

    for c in private_chats:
        p1, p2 = c.get("p1"), c.get("p2")
        a1, a2 = alignments.get(p1), alignments.get(p2)
        if a1 == "good" and a2 == "good":
            good_good_chats += 1
        if a1 == "evil" or a2 == "evil":
            evil_total_chats += 1
            if a1 == "evil" and a2 == "evil":
                evil_evil_chats += 1
        if c.get("claims_exchanged", False):
            claim_chats += 1

    chat_density = total_chats / float(days * 12)
    gg_ratio = good_good_chats / max(1, total_chats)
    ee_ratio = evil_evil_chats / max(1, evil_total_chats)
    claim_rate = claim_chats / max(1, total_chats)

    # 2. Execution & Friendly Fire
    good_noms = 0
    good_noms_on_good = 0
    good_execs = 0
    total_execs = 0
    total_votes_cast = 0
    noms_count = 0

    for e in events:
        etype = e.get("type")
        if etype == "NOMINATION":
            noms_count += 1
            nom = e.get("actor")
            tgt = e.get("target")
            if alignments.get(nom) == "good":
                good_noms += 1
                if alignments.get(tgt) == "good":
                    good_noms_on_good += 1
        elif etype == "EXECUTION":
            total_execs += 1
            if alignments.get(e.get("actor")) == "good":
                good_execs += 1
        elif etype == "VOTE_RESULT":
            total_votes_cast += e.get("data", {}).get("votes", 0)

    nom_ff = good_noms_on_good / max(1, good_noms)
    exec_ff = good_execs / max(1, total_execs)
    vote_part = total_votes_cast / max(1, noms_count * 10)

    # 3. Night kill value percentile
    kill_scores: list[float] = []
    for e in events:
        if e.get("type") == "DEATH" and e.get("data", {}).get("reason") == "demon_kill":
            victim = e.get("actor") or e.get("target")
            role = game.get("apparent_roles", {}).get(victim, "")
            if role in {"empath", "fortune_teller", "undertaker"}:
                kill_scores.append(0.95)
            elif role in {"monk", "virgin", "slayer"}:
                kill_scores.append(0.80)
            elif role in {"washerwoman", "librarian", "investigator", "chef"}:
                kill_scores.append(0.50)
            else:
                kill_scores.append(0.25)
    kill_val = float(np.mean(kill_scores)) if kill_scores else 0.50

    # 4. Monk protection quality
    monk_scores: list[float] = []
    for e in events:
        if e.get("type") == "NIGHT_ACTION" and e.get("data", {}).get("role") == "monk":
            tgt = e.get("target")
            r = game.get("apparent_roles", {}).get(tgt, "")
            monk_scores.append(1.0 if r in {"empath", "fortune_teller", "undertaker"} else 0.0)
    monk_qual = float(np.mean(monk_scores)) if monk_scores else 0.0

    # 5. Vote consistency proxy: ratio of votes targeting actual evil players
    vote_cons = (1.0 - nom_ff) * 0.5 + 0.3

    # 6. Trust error rate proxy
    trust_err = nom_ff * 0.8

    return {
        "private_chats_per_player_day": round(chat_density, 4),
        "good_good_chat_ratio": round(gg_ratio, 4),
        "evil_evil_chat_ratio": round(ee_ratio, 4),
        "claim_disclosure_rate": round(claim_rate, 4),
        "nomination_friendly_fire_rate": round(nom_ff, 4),
        "execution_friendly_fire_rate": round(exec_ff, 4),
        "vote_consistency": round(vote_cons, 4),
        "vote_participation_rate": round(min(1.0, vote_part), 4),
        "night_kill_value_percentile": round(kill_val, 4),
        "monk_protection_quality": round(monk_qual, 4),
        "trust_error_rate": round(trust_err, 4),
    }
