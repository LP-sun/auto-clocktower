"""Phase 3.6 Endgame Cognition Audit, Conversion Funnel, and 9-Class Failure Attribution."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.engine.types import Alignment, RoleId
from src.simulation.runner import SimulationResult


@dataclass(slots=True)
class EndgameConversionMetrics:
    total_games: int = 0
    reach_f4_games: int = 0
    reach_f3_games: int = 0
    good_wins: int = 0
    f4_good_wins: int = 0
    f3_good_wins: int = 0

    p_reach_f4: float = 0.0
    p_reach_f3: float = 0.0
    f4_to_f3_conversion: float = 0.0
    f3_to_good_win_conversion: float = 0.0
    f4_to_good_win_conversion: float = 0.0
    baseline_good_win_rate: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_games": self.total_games,
            "reach_f4_games": self.reach_f4_games,
            "reach_f3_games": self.reach_f3_games,
            "good_wins": self.good_wins,
            "f4_good_wins": self.f4_good_wins,
            "f3_good_wins": self.f3_good_wins,
            "p_reach_f4": round(self.p_reach_f4, 4),
            "p_reach_f3": round(self.p_reach_f3, 4),
            "f4_to_f3_conversion": round(self.f4_to_f3_conversion, 4),
            "f3_to_good_win_conversion": round(self.f3_to_good_win_conversion, 4),
            "f4_to_good_win_conversion": round(self.f4_to_good_win_conversion, 4),
            "baseline_good_win_rate": round(self.baseline_good_win_rate, 4),
        }


@dataclass(slots=True)
class F4DecisionAudit:
    total_f4_days: int = 0
    passed_f4_count: int = 0
    executed_good_f4_count: int = 0
    executed_demon_f4_count: int = 0
    executed_minion_f4_count: int = 0

    win_rate_if_passed: float = 0.0
    win_rate_if_exec_good: float = 0.0
    win_rate_if_exec_demon: float = 0.0
    f4_mistake_cost: float = 0.0  # P(Good Win | Pass) - P(Good Win | Exec Good)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_f4_days": self.total_f4_days,
            "passed_f4_count": self.passed_f4_count,
            "executed_good_f4_count": self.executed_good_f4_count,
            "executed_demon_f4_count": self.executed_demon_f4_count,
            "executed_minion_f4_count": self.executed_minion_f4_count,
            "win_rate_if_passed": round(self.win_rate_if_passed, 4),
            "win_rate_if_exec_good": round(self.win_rate_if_exec_good, 4),
            "win_rate_if_exec_demon": round(self.win_rate_if_exec_demon, 4),
            "f4_mistake_cost": round(self.f4_mistake_cost, 4),
        }


@dataclass(slots=True)
class GhostVoteAudit:
    ghost_votes_early: int = 0      # Cast when > 4 alive
    ghost_votes_f4: int = 0         # Cast when == 4 alive
    ghost_votes_f3: int = 0         # Cast when == 3 alive
    total_ghost_votes_cast: int = 0

    early_rate: float = 0.0
    f4_rate: float = 0.0
    f3_rate: float = 0.0

    target_evil_count: int = 0
    target_good_count: int = 0
    ghost_accuracy: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "ghost_votes_early": self.ghost_votes_early,
            "ghost_votes_f4": self.ghost_votes_f4,
            "ghost_votes_f3": self.ghost_votes_f3,
            "total_ghost_votes_cast": self.total_ghost_votes_cast,
            "early_rate": round(self.early_rate, 4),
            "f4_rate": round(self.f4_rate, 4),
            "f3_rate": round(self.f3_rate, 4),
            "target_evil_count": self.target_evil_count,
            "target_good_count": self.target_good_count,
            "ghost_accuracy": round(self.ghost_accuracy, 4),
        }


@dataclass(slots=True)
class NominationOrderAudit:
    total_f3_days: int = 0
    f3_demon_nominated_first: int = 0
    f3_demon_nominated_second: int = 0
    f3_demon_not_nominated: int = 0

    win_rate_demon_nom_first: float = 0.0
    win_rate_demon_nom_second: float = 0.0
    order_advantage: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_f3_days": self.total_f3_days,
            "f3_demon_nominated_first": self.f3_demon_nominated_first,
            "f3_demon_nominated_second": self.f3_demon_nominated_second,
            "f3_demon_not_nominated": self.f3_demon_not_nominated,
            "win_rate_demon_nom_first": round(self.win_rate_demon_nom_first, 4),
            "win_rate_demon_nom_second": round(self.win_rate_demon_nom_second, 4),
            "order_advantage": round(self.order_advantage, 4),
        }


@dataclass(slots=True)
class GoodLossAttribution9Class:
    counts: dict[str, int] = field(default_factory=lambda: {
        "RULE_SPECIAL_DEFEAT": 0,
        "EARLY_STRUCTURAL_COLLAPSE": 0,
        "F4_WRONG_EXECUTION_FATAL": 0,
        "F3_WRONG_EXECUTION": 0,
        "F3_PASS_NO_MAYOR_FATAL": 0,
        "F3_VOTE_COORDINATION_FAILURE": 0,
        "F3_BELIEF_MISALIGNMENT": 0,
        "MIDGAME_ATTRITION": 0,
        "OTHER_DEFEAT": 0,
    })
    percentages: dict[str, float] = field(default_factory=dict)
    total_losses: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_losses": self.total_losses,
            "counts": self.counts,
            "percentages": {k: round(v, 4) for k, v in self.percentages.items()},
        }


@dataclass(slots=True)
class EndgameAuditReport:
    conversion_metrics: EndgameConversionMetrics = field(default_factory=EndgameConversionMetrics)
    f4_audit: F4DecisionAudit = field(default_factory=F4DecisionAudit)
    ghost_vote_audit: GhostVoteAudit = field(default_factory=GhostVoteAudit)
    nomination_order_audit: NominationOrderAudit = field(default_factory=NominationOrderAudit)
    loss_attribution_9class: GoodLossAttribution9Class = field(default_factory=GoodLossAttribution9Class)

    def to_dict(self) -> dict[str, Any]:
        return {
            "conversion_metrics": self.conversion_metrics.to_dict(),
            "f4_audit": self.f4_audit.to_dict(),
            "ghost_vote_audit": self.ghost_vote_audit.to_dict(),
            "nomination_order_audit": self.nomination_order_audit.to_dict(),
            "loss_attribution_9class": self.loss_attribution_9class.to_dict(),
        }


def run_endgame_audit(results: list[SimulationResult]) -> EndgameAuditReport:
    """Analyze simulation results for endgame conversion, F4 decisions, ghost votes, and 9-class loss attribution."""
    total_games = len(results)
    if total_games == 0:
        return EndgameAuditReport()

    good_wins = sum(1 for r in results if r.winner == Alignment.GOOD)
    reach_f4 = sum(1 for r in results if getattr(r, "reached_4_alive_day", False))
    reach_f3 = sum(1 for r in results if getattr(r, "reached_3_alive_day", False))

    f4_wins = sum(1 for r in results if getattr(r, "reached_4_alive_day", False) and r.winner == Alignment.GOOD)
    f3_wins = sum(1 for r in results if getattr(r, "reached_3_alive_day", False) and r.winner == Alignment.GOOD)

    conv = EndgameConversionMetrics(
        total_games=total_games,
        reach_f4_games=reach_f4,
        reach_f3_games=reach_f3,
        good_wins=good_wins,
        f4_good_wins=f4_wins,
        f3_good_wins=f3_wins,
        p_reach_f4=reach_f4 / total_games,
        p_reach_f3=reach_f3 / total_games,
        f4_to_f3_conversion=reach_f3 / reach_f4 if reach_f4 > 0 else 0.0,
        f3_to_good_win_conversion=f3_wins / reach_f3 if reach_f3 > 0 else 0.0,
        f4_to_good_win_conversion=f4_wins / reach_f4 if reach_f4 > 0 else 0.0,
        baseline_good_win_rate=good_wins / total_games,
    )

    # 2. F4 Audit
    total_f4 = 0
    passed_f4 = 0
    exec_good_f4 = 0
    exec_demon_f4 = 0
    exec_minion_f4 = 0
    win_passed = 0
    win_exec_good = 0
    win_exec_demon = 0

    # 3. Ghost Vote Audit
    gv_early = 0
    gv_f4 = 0
    gv_f3 = 0
    gv_evil = 0
    gv_good = 0

    # 4. F3 Nomination Order Audit
    total_f3 = 0
    f3_demon_first = 0
    f3_demon_second = 0
    f3_demon_none = 0
    win_f3_demon_first = 0
    win_f3_demon_second = 0

    # 5. 9-Class Loss Attribution
    loss_counts = {
        "RULE_SPECIAL_DEFEAT": 0,
        "EARLY_STRUCTURAL_COLLAPSE": 0,
        "F4_WRONG_EXECUTION_FATAL": 0,
        "F3_WRONG_EXECUTION": 0,
        "F3_PASS_NO_MAYOR_FATAL": 0,
        "F3_VOTE_COORDINATION_FAILURE": 0,
        "F3_BELIEF_MISALIGNMENT": 0,
        "MIDGAME_ATTRITION": 0,
        "OTHER_DEFEAT": 0,
    }
    total_losses = 0

    for r in results:
        demon_player = next((p for p, role in r.true_roles.items() if role == RoleId.IMP.value), None)

        # Inspect ghost votes from events
        for e in r.events:
            etype = getattr(e, "type", None) or e.get("type")
            if etype == "GHOST_VOTE_USED":
                actor = getattr(e, "actor", None) or e.get("actor")
                target = getattr(e, "target", None) or e.get("target")
                day = getattr(e, "day", 1) or e.get("day", 1)
                alive_at_day = r.day_start_alives.get(day, 5)

                if alive_at_day > 4:
                    gv_early += 1
                elif alive_at_day == 4:
                    gv_f4 += 1
                else:
                    gv_f3 += 1

                if target:
                    if r.alignments.get(target) == Alignment.EVIL.value:
                        gv_evil += 1
                    else:
                        gv_good += 1

        # Inspect F4 day
        f4_day = next((d for d, cnt in r.day_start_alives.items() if cnt == 4), None)
        f4_exec_victim = None
        f4_passed = False
        if f4_day is not None:
            total_f4 += 1
            # Find execution on f4_day
            exec_events = [
                e for e in r.events
                if (getattr(e, "type", None) or e.get("type")) == "EXECUTION"
                and (getattr(e, "day", None) or e.get("day")) == f4_day
            ]
            if exec_events:
                target = getattr(exec_events[0], "target", None) or exec_events[0].get("target")
                f4_exec_victim = target
                if target == demon_player:
                    exec_demon_f4 += 1
                    if r.winner == Alignment.GOOD:
                        win_exec_demon += 1
                elif r.alignments.get(target) == Alignment.EVIL.value:
                    exec_minion_f4 += 1
                else:
                    exec_good_f4 += 1
                    if r.winner == Alignment.GOOD:
                        win_exec_good += 1
            else:
                f4_passed = True
                passed_f4 += 1
                if r.winner == Alignment.GOOD:
                    win_passed += 1

        # Inspect F3 day
        f3_day = next((d for d, cnt in r.day_start_alives.items() if cnt == 3), None)
        f3_demon_nom_rank = None
        f3_exec_victim = None
        f3_demon_nominated = False
        f3_demon_reached_threshold = False
        f3_demon_tie_or_outvoted = False

        if f3_day is not None:
            total_f3 += 1
            # Check nominations on F3 day
            f3_noms = [
                n for n in getattr(r, "nomination_history", [])
                if n.get("day") == f3_day
            ]
            if not f3_noms:
                # Fallback: check events
                f3_noms_events = [
                    e for e in r.events
                    if (getattr(e, "type", None) or e.get("type")) == "VOTE_RECORD"
                    and (getattr(e, "day", None) or e.get("day")) == f3_day
                ]
                f3_noms = [{"nominee": getattr(e, "target", None) or e.get("target")} for e in f3_noms_events]

            for idx, nom in enumerate(f3_noms):
                nominee = nom.get("nominee")
                if nominee == demon_player:
                    f3_demon_nominated = True
                    if f3_demon_nom_rank is None:
                        f3_demon_nom_rank = idx + 1
                    if nom.get("exceeded", False):
                        f3_demon_reached_threshold = True

            if f3_demon_nom_rank == 1:
                f3_demon_first += 1
                if r.winner == Alignment.GOOD:
                    win_f3_demon_first += 1
            elif f3_demon_nom_rank and f3_demon_nom_rank >= 2:
                f3_demon_second += 1
                if r.winner == Alignment.GOOD:
                    win_f3_demon_second += 1
            else:
                f3_demon_none += 1

            # Execution on F3 day
            f3_exec_events = [
                e for e in r.events
                if (getattr(e, "type", None) or e.get("type")) == "EXECUTION"
                and (getattr(e, "day", None) or e.get("day")) == f3_day
            ]
            if f3_exec_events:
                f3_exec_victim = getattr(f3_exec_events[0], "target", None) or f3_exec_events[0].get("target")

        # 9-Class Loss Attribution for Good Defeats
        if r.winner == Alignment.EVIL:
            total_losses += 1
            assigned = False

            # 1. RULE_SPECIAL_DEFEAT
            if r.end_reason in ("saint_executed", "saint_death"):
                loss_counts["RULE_SPECIAL_DEFEAT"] += 1
                assigned = True

            # 2. EARLY_STRUCTURAL_COLLAPSE
            elif r.early_end_category == "STRUCTURAL_COLLAPSE_CANDIDATE" or r.days <= 2:
                loss_counts["EARLY_STRUCTURAL_COLLAPSE"] += 1
                assigned = True

            # 3. F4_WRONG_EXECUTION_FATAL
            elif f4_day is not None and f4_exec_victim is not None and r.alignments.get(f4_exec_victim) == Alignment.GOOD.value:
                # Executing good in F4 reduces living to 3, subsequent night kill leaves 2 -> instant evil victory
                loss_counts["F4_WRONG_EXECUTION_FATAL"] += 1
                assigned = True

            # 4. F3_WRONG_EXECUTION
            elif f3_day is not None and f3_exec_victim is not None and r.alignments.get(f3_exec_victim) == Alignment.GOOD.value:
                loss_counts["F3_WRONG_EXECUTION"] += 1
                assigned = True

            # 5. F3_PASS_NO_MAYOR_FATAL
            elif f3_day is not None and f3_exec_victim is None:
                # No execution in F3
                has_active_mayor = any(
                    r.true_roles.get(p) == RoleId.MAYOR.value and p in r.alive_players
                    for p in r.alive_players
                )
                if not has_active_mayor:
                    loss_counts["F3_PASS_NO_MAYOR_FATAL"] += 1
                    assigned = True
                else:
                    loss_counts["OTHER_DEFEAT"] += 1
                    assigned = True

            # 6. F3_VOTE_COORDINATION_FAILURE
            elif f3_day is not None and f3_demon_nominated and not f3_demon_reached_threshold:
                loss_counts["F3_VOTE_COORDINATION_FAILURE"] += 1
                assigned = True

            # 7. F3_BELIEF_MISALIGNMENT
            elif f3_day is not None and not f3_demon_nominated:
                # In F3, Demon was never nominated because Good beliefs placed suspicion on someone else
                loss_counts["F3_BELIEF_MISALIGNMENT"] += 1
                assigned = True

            # 8. MIDGAME_ATTRITION
            elif not getattr(r, "reached_4_alive_day", False) and r.days >= 3:
                loss_counts["MIDGAME_ATTRITION"] += 1
                assigned = True

            # 9. OTHER_DEFEAT fallback
            if not assigned:
                loss_counts["OTHER_DEFEAT"] += 1

    f4_audit = F4DecisionAudit(
        total_f4_days=total_f4,
        passed_f4_count=passed_f4,
        executed_good_f4_count=exec_good_f4,
        executed_demon_f4_count=exec_demon_f4,
        executed_minion_f4_count=exec_minion_f4,
        win_rate_if_passed=win_passed / passed_f4 if passed_f4 > 0 else 0.0,
        win_rate_if_exec_good=win_exec_good / exec_good_f4 if exec_good_f4 > 0 else 0.0,
        win_rate_if_exec_demon=win_exec_demon / exec_demon_f4 if exec_demon_f4 > 0 else 0.0,
        f4_mistake_cost=(win_passed / passed_f4 if passed_f4 > 0 else 0.0) - (win_exec_good / exec_good_f4 if exec_good_f4 > 0 else 0.0),
    )

    tot_gv = gv_early + gv_f4 + gv_f3
    gv_audit = GhostVoteAudit(
        ghost_votes_early=gv_early,
        ghost_votes_f4=gv_f4,
        ghost_votes_f3=gv_f3,
        total_ghost_votes_cast=tot_gv,
        early_rate=gv_early / tot_gv if tot_gv > 0 else 0.0,
        f4_rate=gv_f4 / tot_gv if tot_gv > 0 else 0.0,
        f3_rate=gv_f3 / tot_gv if tot_gv > 0 else 0.0,
        target_evil_count=gv_evil,
        target_good_count=gv_good,
        ghost_accuracy=gv_evil / tot_gv if tot_gv > 0 else 0.0,
    )

    wr_first = win_f3_demon_first / f3_demon_first if f3_demon_first > 0 else 0.0
    wr_second = win_f3_demon_second / f3_demon_second if f3_demon_second > 0 else 0.0
    order_audit = NominationOrderAudit(
        total_f3_days=total_f3,
        f3_demon_nominated_first=f3_demon_first,
        f3_demon_nominated_second=f3_demon_second,
        f3_demon_not_nominated=f3_demon_none,
        win_rate_demon_nom_first=wr_first,
        win_rate_demon_nom_second=wr_second,
        order_advantage=wr_second - wr_first,
    )

    pcts = {k: v / total_losses if total_losses > 0 else 0.0 for k, v in loss_counts.items()}
    loss_att = GoodLossAttribution9Class(
        counts=loss_counts,
        percentages=pcts,
        total_losses=total_losses,
    )

    return EndgameAuditReport(
        conversion_metrics=conv,
        f4_audit=f4_audit,
        ghost_vote_audit=gv_audit,
        nomination_order_audit=order_audit,
        loss_attribution_9class=loss_att,
    )
