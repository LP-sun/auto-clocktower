"""Diagnostic attribution of good-loss root causes, information lifecycle, and 4-quadrant diagnosis."""
from __future__ import annotations

from enum import Enum, unique
from typing import Any

from src.engine.types import Alignment, RoleId


@unique
class AssociatedFailureMode(str, Enum):
    """Fine-grained failure mode attribution labels for good-loss games."""
    INFERENCE_FAILURE = "INFERENCE_FAILURE"                       # Living good failed to rank true demon in top suspects
    COORDINATION_FAILURE = "COORDINATION_FAILURE"                 # Living good identified demon but failed to coordinate execution
    INFORMATION_PROPAGATION_FAILURE = "INFO_PROPAGATION_FAILURE" # Key info was never shared with living townsfolk
    TRUST_FAILURE = "TRUST_FAILURE"                               # Living good placed high trust in evil or deeply suspected verified good
    EXECUTION_SELECTION_FAILURE = "EXECUTION_SELECTION_FAILURE"   # Innocent high-value role or Saint was executed
    VOTE_THRESHOLD_FAILURE = "VOTE_THRESHOLD_FAILURE"             # Demon nominated but votes strictly failed to reach ceil(alive/2)
    VOTE_TIE_FAILURE = "VOTE_TIE_FAILURE"                         # Demon received >= threshold votes, but tied with another nominee (no execution)
    OUTVOTED_BY_OTHER_NOMINEE = "OUTVOTED_BY_OTHER_NOMINEE"       # Demon reached threshold, but another nominee received strictly more votes
    ABILITY_MISUSE = "ABILITY_MISUSE"                             # Slayer shot innocent townsperson or abilities wasted
    EVIL_BLUFF_SUCCESS = "EVIL_BLUFF_SUCCESS"                     # Evil bluffed unsuspected into late-game
    EVIL_KILL_ADVANTAGE = "EVIL_KILL_ADVANTAGE"                   # Demon consistently eliminated top-tier info roles at night
    ST_INFORMATION_DISTORTION = "ST_INFORMATION_DISTORTION"       # Storyteller false info actively pointed away from demon
    EARLY_GOOD_COLLAPSE = "EARLY_GOOD_COLLAPSE"                   # Rapid early attrition (Day 1/2 double innocent executions)
    OTHER = "OTHER"


INFO_ROLES = {
    "washerwoman", "librarian", "investigator", "chef",
    "empath", "fortune_teller", "undertaker", "virgin", "slayer"
}

HIGH_VALUE_ROLES = {
    "empath", "fortune_teller", "undertaker", "monk", "virgin", "slayer"
}


class GoodLossDecomposition:
    """Diagnostic attribution engine analyzing failure mechanisms in good-loss simulations."""

    @staticmethod
    def classify_failures(game: dict[str, Any]) -> list[AssociatedFailureMode]:
        """Classify a good-loss game into all matching associated failure mode labels."""
        failures: set[AssociatedFailureMode] = set()
        events = game.get("events", [])
        alignments = game.get("alignments", {})
        true_roles = game.get("true_roles", {})
        apparent_roles = game.get("apparent_roles", {})
        end_reason = game.get("end_reason", "")

        # Identify Demon
        demon_id = next(
            (p for p, r in true_roles.items() if r == "imp"),
            next((p for p, a in alignments.items() if a == "evil"), None)
        )

        # 1. Saint execution check
        if end_reason == "saint_executed":
            failures.add(AssociatedFailureMode.EXECUTION_SELECTION_FAILURE)

        # 2. Early good collapse
        execs_by_day: dict[int, list[str]] = {}
        for e in events:
            if e.get("type") == "EXECUTION":
                d = e.get("day", 1)
                actor = e.get("actor")
                execs_by_day.setdefault(d, []).append(actor)

        d1_exec = execs_by_day.get(1, [])
        d2_exec = execs_by_day.get(2, [])
        d1_good = any(alignments.get(p) == "good" for p in d1_exec)
        d2_good = any(alignments.get(p) == "good" for p in d2_exec)
        if d1_good and d2_good and game.get("total_days", 5) <= 3:
            failures.add(AssociatedFailureMode.EARLY_GOOD_COLLAPSE)

        # 3. High-value role execution selection failure
        for e in events:
            if e.get("type") == "EXECUTION":
                p = e.get("actor")
                if apparent_roles.get(p) in HIGH_VALUE_ROLES and alignments.get(p) == "good":
                    failures.add(AssociatedFailureMode.EXECUTION_SELECTION_FAILURE)

        # 4. Slayer shot innocent
        for e in events:
            if e.get("type") == "ABILITY_TRIGGER" and e.get("actor") in true_roles:
                role = true_roles.get(e.get("actor"))
                if role == "slayer":
                    target = e.get("target")
                    if alignments.get(target) == "good":
                        failures.add(AssociatedFailureMode.ABILITY_MISUSE)

        # 5. Demon voting failure analysis
        demon_noms = 0
        demon_threshold_reached = 0
        demon_tied = 0
        demon_outvoted = 0

        # Group nominations by day
        noms_by_day: dict[int, list[dict[str, Any]]] = {}
        for e in events:
            if e.get("type") == "NOMINATION":
                d = e.get("day", 1)
                noms_by_day.setdefault(d, []).append(e)

        for d, noms in noms_by_day.items():
            for nom in noms:
                target = nom.get("target")
                if target == demon_id:
                    demon_noms += 1
                    # Check vote result event for this nomination
                    vr = next(
                        (
                            ev for ev in events
                            if ev.get("type") == "VOTE_RESULT"
                            and ev.get("day") == d
                            and ev.get("data", {}).get("nominee") == demon_id
                        ),
                        None
                    )
                    if vr:
                        votes = vr.get("data", {}).get("votes", 0)
                        threshold = vr.get("data", {}).get("threshold", 999)
                        if votes < threshold:
                            failures.add(AssociatedFailureMode.VOTE_THRESHOLD_FAILURE)
                        else:
                            demon_threshold_reached += 1
                            # Check if executed
                            was_exec = any(
                                ev.get("type") == "EXECUTION" and ev.get("day") == d and ev.get("actor") == demon_id
                                for ev in events
                            )
                            if not was_exec:
                                # Check if tied or outvoted
                                other_vrs = [
                                    ev for ev in events
                                    if ev.get("type") == "VOTE_RESULT"
                                    and ev.get("day") == d
                                    and ev.get("data", {}).get("nominee") != demon_id
                                ]
                                max_other = max((ov.get("data", {}).get("votes", 0) for ov in other_vrs), default=0)
                                if max_other > votes:
                                    demon_outvoted += 1
                                    failures.add(AssociatedFailureMode.OUTVOTED_BY_OTHER_NOMINEE)
                                elif max_other == votes:
                                    demon_tied += 1
                                    failures.add(AssociatedFailureMode.VOTE_TIE_FAILURE)

        # 6. Inference vs Coordination failure
        # Check final day / final 3 demon identification
        final_day = game.get("total_days", 1)
        demon_was_nominated = demon_noms > 0

        if not demon_was_nominated:
            failures.add(AssociatedFailureMode.INFERENCE_FAILURE)
        elif demon_was_nominated and not any(e.get("type") == "EXECUTION" and e.get("actor") == demon_id for e in events):
            failures.add(AssociatedFailureMode.COORDINATION_FAILURE)

        # 7. Evil bluff success
        evil_survivors = [p for p in game.get("alive_players", []) if alignments.get(p) == "evil"]
        if len(evil_survivors) >= 2 or (len(game.get("alive_players", [])) <= 4 and evil_survivors):
            failures.add(AssociatedFailureMode.EVIL_BLUFF_SUCCESS)

        # 8. Night kill advantage
        info_kills = 0
        total_kills = 0
        for e in events:
            if e.get("type") == "DEATH" and e.get("data", {}).get("reason") == "demon_kill":
                total_kills += 1
                victim = e.get("actor") or e.get("target")
                if apparent_roles.get(victim) in INFO_ROLES:
                    info_kills += 1
        if total_kills > 0 and (info_kills / total_kills) >= 0.70:
            failures.add(AssociatedFailureMode.EVIL_KILL_ADVANTAGE)

        # Fallback
        if not failures:
            failures.add(AssociatedFailureMode.OTHER)

        return sorted(list(failures), key=lambda x: x.value)

    @staticmethod
    def compute_information_lifecycle(game: dict[str, Any]) -> dict[str, float]:
        """Compute the conversion rates along the Good information lifecycle: gen -> shared -> trusted -> used."""
        events = game.get("events", [])
        private_chats = game.get("private_chats", [])
        alignments = game.get("alignments", {})
        true_roles = game.get("true_roles", {})

        # Count generated info events for good players
        gen_count = 0
        for e in events:
            etype = e.get("type", "")
            if etype.startswith("INFO_"):
                actor = e.get("actor")
                if alignments.get(actor) == "good":
                    gen_count += 1

        # Count shared info (chats involving good info roles where claims/info were exchanged)
        shared_count = sum(
            1 for c in private_chats
            if c.get("claims_exchanged", False)
            and (true_roles.get(c.get("p1")) in INFO_ROLES or true_roles.get(c.get("p2")) in INFO_ROLES)
        )

        # Trusted info (chats between good and good)
        trusted_count = sum(
            1 for c in private_chats
            if c.get("claims_exchanged", False)
            and alignments.get(c.get("p1")) == "good"
            and alignments.get(c.get("p2")) == "good"
        )

        # Used info (nominations of evil players by informed good players)
        used_count = 0
        for e in events:
            if e.get("type") == "NOMINATION":
                nominator = e.get("actor")
                nominee = e.get("target")
                if alignments.get(nominator) == "good" and alignments.get(nominee) == "evil":
                    used_count += 1

        p_shared = shared_count / max(1, gen_count)
        p_trusted = trusted_count / max(1, shared_count)
        p_used = used_count / max(1, trusted_count)

        return {
            "info_generated_count": gen_count,
            "info_shared_count": shared_count,
            "info_trusted_count": trusted_count,
            "info_used_count": used_count,
            "p_shared_given_gen": round(min(1.0, p_shared), 4),
            "p_trusted_given_shared": round(min(1.0, p_trusted), 4),
            "p_used_given_trusted": round(min(1.0, p_used), 4),
        }

    @staticmethod
    def compute_good_friendly_fire(game: dict[str, Any]) -> dict[str, float]:
        """Compute friendly fire metrics: good actions targeting other good players."""
        events = game.get("events", [])
        alignments = game.get("alignments", {})

        good_noms_total = 0
        good_noms_on_good = 0
        good_votes_total = 0
        good_votes_on_good = 0
        good_execs = 0
        total_execs = 0

        # Nominations
        for e in events:
            if e.get("type") == "NOMINATION":
                nominator = e.get("actor")
                nominee = e.get("target")
                if alignments.get(nominator) == "good":
                    good_noms_total += 1
                    if alignments.get(nominee) == "good":
                        good_noms_on_good += 1

            elif e.get("type") == "EXECUTION":
                total_execs += 1
                victim = e.get("actor")
                if alignments.get(victim) == "good":
                    good_execs += 1

        nom_ff_rate = good_noms_on_good / max(1, good_noms_total)
        exec_ff_rate = good_execs / max(1, total_execs)

        return {
            "good_noms_on_good": good_noms_on_good,
            "good_noms_total": good_noms_total,
            "nomination_friendly_fire_rate": round(nom_ff_rate, 4),
            "good_executions": good_execs,
            "total_executions": total_execs,
            "execution_friendly_fire_rate": round(exec_ff_rate, 4),
        }

    @staticmethod
    def compute_night_kill_value(game: dict[str, Any]) -> float:
        """Compute KillValue percentile of demon night kills based on victim role importance and survival."""
        events = game.get("events", [])
        apparent_roles = game.get("apparent_roles", {})

        kill_values = {
            "empath": 0.95,
            "fortune_teller": 0.95,
            "undertaker": 0.90,
            "monk": 0.85,
            "virgin": 0.80,
            "slayer": 0.80,
            "investigator": 0.60,
            "librarian": 0.50,
            "chef": 0.50,
            "washerwoman": 0.50,
            "soldier": 0.40,
            "mayor": 0.70,
            "butler": 0.20,
            "saint": 0.10,
            "recluse": 0.15,
            "poisoner": 0.10,
            "spy": 0.10,
            "baron": 0.10,
            "scarlet_woman": 0.10,
            "imp": 0.05,
        }

        kill_scores: list[float] = []
        for e in events:
            if e.get("type") == "DEATH" and e.get("data", {}).get("reason") == "demon_kill":
                victim = e.get("actor") or e.get("target")
                role = apparent_roles.get(victim, "")
                val = kill_values.get(role, 0.40)
                kill_scores.append(val)

        return round(sum(kill_scores) / max(1, len(kill_scores)), 4) if kill_scores else 0.50

    @staticmethod
    def compute_quadrant_diagnosis(game: dict[str, Any]) -> tuple[float, float, str]:
        """Compute Inference Quality and Coordination Quality, returning (inference_q, coordination_q, quadrant)."""
        events = game.get("events", [])
        alignments = game.get("alignments", {})
        true_roles = game.get("true_roles", {})

        demon_id = next(
            (p for p, r in true_roles.items() if r == "imp"),
            next((p for p, a in alignments.items() if a == "evil"), None)
        )

        # 1. Inference quality: was demon nominated, how many times, was demon targeted by info roles
        demon_noms = 0
        demon_votes = 0
        total_good_noms = 0

        for e in events:
            if e.get("type") == "NOMINATION":
                nominator = e.get("actor")
                nominee = e.get("target")
                if alignments.get(nominator) == "good":
                    total_good_noms += 1
                    if nominee == demon_id:
                        demon_noms += 1

            elif e.get("type") == "VOTE_RESULT" and e.get("data", {}).get("nominee") == demon_id:
                demon_votes += e.get("data", {}).get("votes", 0)

        inference_q = min(1.0, (demon_noms / max(1, total_good_noms)) * 3.0 + (0.3 if demon_noms > 0 else 0.0))

        # 2. Coordination quality: friendly fire rate inverted + ability to execute when nominated
        demon_executed = any(
            e.get("type") == "EXECUTION" and e.get("actor") == demon_id
            for e in events
        )
        ff_info = GoodLossDecomposition.compute_good_friendly_fire(game)
        ff_penalty = ff_info.get("nomination_friendly_fire_rate", 0.5)

        coordination_q = 0.5 * (1.0 - ff_penalty) + (0.5 if demon_executed else (0.25 if demon_votes >= 5 else 0.0))
        coordination_q = min(1.0, max(0.0, coordination_q))

        # 3. Determine quadrant
        if inference_q >= 0.5 and coordination_q >= 0.5:
            quadrant = "Q1_OPTIMAL_PLAY"
        elif inference_q >= 0.5 and coordination_q < 0.5:
            quadrant = "Q2_COORDINATION_FAILURE"
        elif inference_q < 0.5 and coordination_q >= 0.5:
            quadrant = "Q3_INFERENCE_FAILURE"
        else:
            quadrant = "Q4_TOTAL_COLLAPSE"

        return round(inference_q, 4), round(coordination_q, 4), quadrant
