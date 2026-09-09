"""Primitive taxonomy analysis, co-activation matrix, dominance detection, and conditional policy entropy."""
from __future__ import annotations

import math
from collections import Counter, defaultdict
from typing import Any

from src.strategies.primitives import PRIMITIVE_TAXONOMY, PrimitiveType, StrategyPrimitive, get_primitive_type


def calculate_entropy(counter: Counter) -> float:
    """Calculate Shannon entropy in bits for a discrete frequency counter."""
    total = sum(counter.values())
    if total <= 1:
        return 0.0
    probs = [c / total for c in counter.values() if c > 0]
    return -sum(p * math.log2(p) for p in probs)


class PrimitiveInteractionAnalyzer:
    """Analyzes co-activation, contribution share dominance, and policy degeneration."""

    @staticmethod
    def compute_coactivation_matrix(
        decision_traces: list[dict[str, Any]]
    ) -> dict[tuple[str, str], int]:
        """Compute the pairwise co-activation frequency of primitives appearing together in decision traces."""
        pair_counts: dict[tuple[str, str], int] = defaultdict(int)

        for trace in decision_traces:
            prims = trace.get("applicable_primitives", [])
            if len(prims) >= 2:
                sorted_p = sorted(list(set(prims)))
                for i in range(len(sorted_p)):
                    for j in range(i + 1, len(sorted_p)):
                        p1, p2 = sorted_p[i], sorted_p[j]
                        pair_counts[(p1, p2)] += 1

        return dict(pair_counts)

    @staticmethod
    def detect_primitive_dominance(
        decision_traces: list[dict[str, Any]],
        dominance_threshold: float = 0.80,
    ) -> list[dict[str, Any]]:
        """Identify primitives that account for >80% of total absolute utility in decisions."""
        primitive_dominance_counts: dict[str, int] = defaultdict(int)
        total_evaluations: dict[str, int] = defaultdict(int)

        for trace in decision_traces:
            comps = trace.get("utility_components", {})
            for candidate, comp_dict in comps.items():
                abs_vals = {k: abs(v) for k, v in comp_dict.items()}
                total_sum = sum(abs_vals.values())
                if total_sum > 1e-6:
                    for comp_name, val in abs_vals.items():
                        total_evaluations[comp_name] += 1
                        share = val / total_sum
                        if share >= dominance_threshold:
                            primitive_dominance_counts[comp_name] += 1

        dominance_reports: list[dict[str, Any]] = []
        for comp_name, dom_count in primitive_dominance_counts.items():
            total = total_evaluations.get(comp_name, 1)
            dom_rate = dom_count / max(1, total)
            dominance_reports.append({
                "component": comp_name,
                "dominant_occurrences": dom_count,
                "total_occurrences": total,
                "dominance_ratio": round(dom_rate, 4),
                "is_dominant": dom_rate >= 0.20,  # Dominates in >=20% of its appearances
            })

        return sorted(dominance_reports, key=lambda x: x["dominance_ratio"], reverse=True)

    @staticmethod
    def compute_conditional_entropies(
        game_records: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Compute fine-grained conditional policy entropies and check for policy collapse warnings."""
        role_day_actions: dict[tuple[str, int], Counter] = defaultdict(Counter)
        role_day_chats: dict[tuple[str, int], Counter] = defaultdict(Counter)
        role_day_claims: dict[tuple[str, int], Counter] = defaultdict(Counter)

        for g in game_records:
            true_roles = g.get("true_roles", {})
            events = g.get("events", [])
            chats = g.get("private_chats", [])

            for e in events:
                if e.get("type") == "NOMINATION":
                    actor = e.get("actor")
                    day = e.get("day", 1)
                    role = true_roles.get(actor, "unknown")
                    tgt = e.get("target", "pass")
                    role_day_actions[(role, day)][tgt] += 1

            for c in chats:
                day = c.get("day", 1)
                p1, p2 = c.get("p1"), c.get("p2")
                r1 = true_roles.get(p1, "unknown")
                role_day_chats[(r1, day)][p2] += 1
                if c.get("claims_exchanged"):
                    role_day_claims[(r1, day)]["claimed"] += 1
                else:
                    role_day_claims[(r1, day)]["silent"] += 1

        # Calculate mean entropies
        h_actions = [calculate_entropy(c) for c in role_day_actions.values() if sum(c.values()) >= 5]
        h_chats = [calculate_entropy(c) for c in role_day_chats.values() if sum(c.values()) >= 5]
        h_claims = [calculate_entropy(c) for c in role_day_claims.values() if sum(c.values()) >= 5]

        mean_h_action = sum(h_actions) / max(1, len(h_actions))
        mean_h_chat = sum(h_chats) / max(1, len(h_chats))
        mean_h_claim = sum(h_claims) / max(1, len(h_claims))

        # Check for determinism / policy collapse warnings
        collapse_warnings: list[str] = []
        for (role, day), ctr in role_day_actions.items():
            total = sum(ctr.values())
            if total >= 20:
                max_prob = max(ctr.values()) / total
                if max_prob > 0.95:
                    top_tgt = ctr.most_common(1)[0][0]
                    collapse_warnings.append(
                        f"POLICY_COLLAPSE_WARNING: Role {role} Day {day} chooses {top_tgt} with prob {max_prob:.3f} > 0.95"
                    )

        return {
            "h_action_given_role_day": round(mean_h_action, 4),
            "h_chattarget_given_role_day": round(mean_h_chat, 4),
            "h_claimtype_given_role_day": round(mean_h_claim, 4),
            "collapse_warnings_count": len(collapse_warnings),
            "collapse_warnings": collapse_warnings[:10],
        }
