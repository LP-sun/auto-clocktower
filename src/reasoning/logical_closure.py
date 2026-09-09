"""Logical Closure Engine for Conditioned Reasoning in Trouble Brewing.

Supports hypothesis queries of the form:
    query = {"demon": P7}
    query = {"role_assignments": {P3: RoleId.VIRGIN}}
and computes:
    - forced_assignments: roles determined with 100% agreement across consistent worlds
    - eliminated_claims: claims that are false in 100% of consistent worlds
    - required_explanations: drunk / poison / bluff assumptions required in 100% of consistent worlds
    - likely_minions: minion marginal distribution conditioned on the assumption
    - is_refuted: whether the condition yields zero legal/consistent worlds
"""
from __future__ import annotations

import csv
from dataclasses import dataclass, field
from typing import Any

from src.engine.types import PlayerId, RoleId
from src.reasoning.world import RoleSlot, SlotState, WorldHypothesis


@dataclass(slots=True)
class LogicalClosureResult:
    condition_description: str
    is_refuted: bool
    consistent_world_count: int
    forced_assignments: dict[PlayerId, RoleId] = field(default_factory=dict)
    eliminated_claims: list[dict[str, Any]] = field(default_factory=list)
    required_explanations: list[str] = field(default_factory=list)
    likely_minions: list[tuple[PlayerId, float]] = field(default_factory=list)
    refutation_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "condition": self.condition_description,
            "is_refuted": self.is_refuted,
            "consistent_world_count": self.consistent_world_count,
            "forced_assignments": {p: r.value for p, r in self.forced_assignments.items()},
            "eliminated_claims": self.eliminated_claims,
            "required_explanations": self.required_explanations,
            "likely_minions": [(p, round(prob, 4)) for p, prob in self.likely_minions],
            "refutation_reason": self.refutation_reason,
        }


class LogicalClosureEngine:
    """Evaluates conditional hypotheses against a population of candidate or active worlds."""

    def __init__(self) -> None:
        self.diagnostics_records: list[dict[str, Any]] = []

    def compute_closure(
        self,
        worlds: list[WorldHypothesis],
        demon_player: PlayerId | None = None,
        minion_player: PlayerId | None = None,
        role_assignments: dict[PlayerId, RoleId] | None = None,
        all_players: list[PlayerId] | None = None,
    ) -> LogicalClosureResult:
        """Filter worlds by condition and deduce logical invariants."""
        # 1. Condition the world set
        consistent_worlds = [
            w for w in worlds
            if w.condition(demon=demon_player, minion=minion_player, role_assignments=role_assignments)
        ]

        cond_desc_parts = []
        if demon_player:
            cond_desc_parts.append(f"Demon={demon_player}")
        if minion_player:
            cond_desc_parts.append(f"Minion={minion_player}")
        if role_assignments:
            for p, r in role_assignments.items():
                cond_desc_parts.append(f"{p}={r.value}")
        cond_desc = " & ".join(cond_desc_parts) if cond_desc_parts else "unconditional"

        if not consistent_worlds:
            record = {
                "condition": cond_desc,
                "consistent_world_count": 0,
                "is_refuted": True,
                "refutation_reason": "Zero active/candidate worlds satisfy the condition",
                "forced_assignments_count": 0,
                "eliminated_claims_count": 0,
                "required_explanations_count": 0,
            }
            self.diagnostics_records.append(record)
            return LogicalClosureResult(
                condition_description=cond_desc,
                is_refuted=True,
                consistent_world_count=0,
                refutation_reason="Zero worlds satisfy condition",
            )

        n_worlds = len(consistent_worlds)
        total_prob = sum(w.probability for w in consistent_worlds) or 1.0

        # 2. Determine forced role assignments
        # A role is forced for player P if across 100% of consistent worlds, slot[P] is KNOWN with the same role.
        forced_assignments: dict[PlayerId, RoleId] = {}
        target_players = all_players or list(consistent_worlds[0].slots.keys())

        for p in target_players:
            first_slot = consistent_worlds[0].slots.get(p)
            if not first_slot or first_slot.state != SlotState.KNOWN or first_slot.role is None:
                continue
            common_role = first_slot.role
            is_uniform = True
            for w in consistent_worlds[1:]:
                s = w.slots.get(p)
                if not s or s.state != SlotState.KNOWN or s.role != common_role:
                    is_uniform = False
                    break
            if is_uniform:
                forced_assignments[p] = common_role

        # 3. Determine required explanations (e.g. Drunk, Poison target)
        required_explanations: list[str] = []
        # Check if drunk is forced on a specific player
        first_drunk = consistent_worlds[0].drunk_player
        if first_drunk and all(w.drunk_player == first_drunk for w in consistent_worlds):
            required_explanations.append(f"Drunk={first_drunk} (100% consistent)")

        # 4. Determine eliminated claims
        eliminated_claims: list[dict[str, Any]] = []
        # A claim is eliminated if claim_truth_assignment[P] is False across 100% of consistent worlds
        claim_keys = set()
        for w in consistent_worlds:
            claim_keys.update(w.claim_truth_assignment.keys())

        for p in claim_keys:
            if all(not w.claim_truth_assignment.get(p, True) for w in consistent_worlds):
                eliminated_claims.append({
                    "player": p,
                    "status": "ELIMINATED_FALSE",
                    "reason": "Evaluated as false/bluff in all surviving worlds under condition",
                })

        # 5. Compute Minion conditional marginals
        minion_probs: dict[PlayerId, float] = {}
        for w in consistent_worlds:
            weight = w.probability / total_prob if total_prob > 0 else 1.0 / n_worlds
            for m in w.minion_players:
                minion_probs[m] = minion_probs.get(m, 0.0) + weight

        likely_minions = sorted(minion_probs.items(), key=lambda x: x[1], reverse=True)

        res = LogicalClosureResult(
            condition_description=cond_desc,
            is_refuted=False,
            consistent_world_count=n_worlds,
            forced_assignments=forced_assignments,
            eliminated_claims=eliminated_claims,
            required_explanations=required_explanations,
            likely_minions=likely_minions,
        )

        record = {
            "condition": cond_desc,
            "consistent_world_count": n_worlds,
            "is_refuted": False,
            "refutation_reason": "",
            "forced_assignments_count": len(forced_assignments),
            "eliminated_claims_count": len(eliminated_claims),
            "required_explanations_count": len(required_explanations),
        }
        self.diagnostics_records.append(record)
        return res

    def export_diagnostics_csv(self, filepath: str) -> None:
        """Export cumulative logical closure diagnostic records to CSV."""
        if not self.diagnostics_records:
            return
        fieldnames = [
            "condition",
            "consistent_world_count",
            "is_refuted",
            "refutation_reason",
            "forced_assignments_count",
            "eliminated_claims_count",
            "required_explanations_count",
        ]
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for r in self.diagnostics_records:
                writer.writerow(r)
