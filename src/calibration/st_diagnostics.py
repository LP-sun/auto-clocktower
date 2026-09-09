"""Storyteller utility diagnostic engine: decision stratification, component variance, scale diagnosis, and rank stability."""
from __future__ import annotations

import math
from collections import Counter, defaultdict
from typing import Any

import numpy as np

from src.storyteller.types import STDecisionPhase, STDecisionRecord


class StorytellerDiagnostics:
    """Diagnostic framework analyzing the discriminative power, stability, and scale of Storyteller utility policies."""

    @staticmethod
    def analyze_stratified_decisions(
        decisions: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Stratify Storyteller decisions by (phase, decision_type) and compute discriminative metrics."""
        groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)

        for d in decisions:
            phase = d.get("phase", STDecisionPhase.NIGHT.value)
            dtype = d.get("decision_type", "unknown")
            groups[(phase, dtype)].append(d)

        stratified_results: list[dict[str, Any]] = []

        for (phase, dtype), dec_list in sorted(groups.items()):
            count = len(dec_list)
            legal_counts = [len(d.get("legal_actions", [])) for d in dec_list]
            delta_us = [d.get("delta_u", 0.0) for d in dec_list]
            all_equal_count = sum(1 for du in delta_us if abs(du) < 1e-6)

            sorted_du = sorted(delta_us)
            median_du = sorted_du[count // 2] if count > 0 else 0.0
            mean_du = float(np.mean(delta_us)) if count > 0 else 0.0

            # Choice entropy
            choices = [str(d.get("chosen_action")) for d in dec_list]
            choice_ctr = Counter(choices)
            probs = [c / count for c in choice_ctr.values()]
            choice_entropy = -sum(p * math.log2(p) for p in probs if p > 0)

            # Top 1 selection rate (how often the highest utility action was chosen)
            top1_chosen = 0
            for d in dec_list:
                cf = d.get("counterfactual_scores", {})
                if cf:
                    max_u = max((v.get("total_utility", 0.0) for v in cf.values()), default=0.0)
                    chosen_str = str(d.get("chosen_action"))
                    chosen_u = cf.get(chosen_str, {}).get("total_utility", 0.0)
                    if abs(chosen_u - max_u) < 1e-4:
                        top1_chosen += 1
            top1_rate = top1_chosen / max(1, count)

            stratified_results.append({
                "phase": phase,
                "decision_type": dtype,
                "decision_count": count,
                "avg_legal_actions": round(float(np.mean(legal_counts)), 2) if legal_counts else 0.0,
                "all_equal_rate": round(all_equal_count / max(1, count), 4),
                "median_delta_u": round(median_du, 4),
                "mean_delta_u": round(mean_du, 4),
                "choice_entropy": round(choice_entropy, 4),
                "top1_selection_rate": round(top1_rate, 4),
            })

        return stratified_results

    @staticmethod
    def analyze_component_variance_and_scale(
        decisions: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Compute variance, min, max, mean, std, and contribution share for each utility component."""
        comp_values: dict[str, list[float]] = defaultdict(list)

        for d in decisions:
            cf = d.get("counterfactual_scores", {})
            for act_str, scores in cf.items():
                for k in ("fairness", "tension", "solvability", "drama"):
                    if k in scores:
                        comp_values[k].append(scores[k])

        scale_reports: list[dict[str, Any]] = []
        for comp_name in ("fairness", "tension", "solvability", "drama"):
            vals = comp_values.get(comp_name, [])
            if vals:
                arr = np.array(vals, dtype=np.float64)
                scale_reports.append({
                    "component": comp_name,
                    "sample_size": len(arr),
                    "min": round(float(np.min(arr)), 4),
                    "max": round(float(np.max(arr)), 4),
                    "mean": round(float(np.mean(arr)), 4),
                    "std": round(float(np.std(arr)), 4),
                    "variance": round(float(np.var(arr)), 6),
                    "contribution_share": 0.25,  # Nominal equal weight in base ST policy
                })

        return scale_reports

    @staticmethod
    def evaluate_rank_stability(
        decisions: list[dict[str, Any]],
        perturbation_levels: list[float] = [0.05, 0.10],
        seed: int = 42,
    ) -> dict[str, float]:
        """Test how frequently the top-utility candidate changes under +/-5% and +/-10% weight perturbations."""
        rng = np.random.RandomState(seed)
        dec_with_alternatives = [
            d for d in decisions
            if len(d.get("counterfactual_scores", {})) >= 2
        ]
        if not dec_with_alternatives:
            return {f"rank_stability_{int(p*100)}pct": 1.0 for p in perturbation_levels}

        stability_results: dict[str, float] = {}

        base_weights = np.array([0.25, 0.25, 0.25, 0.25], dtype=np.float64)
        comp_keys = ["fairness", "tension", "solvability", "drama"]

        for level in perturbation_levels:
            flips = 0
            n_eval = len(dec_with_alternatives)

            for d in dec_with_alternatives:
                cf = d.get("counterfactual_scores", {})
                # Base top candidate
                base_scores = {
                    act: sum(base_weights[i] * scores.get(k, 0.0) for i, k in enumerate(comp_keys))
                    for act, scores in cf.items()
                }
                base_top = max(base_scores.items(), key=lambda x: x[1])[0]

                # Perturbed weights
                delta_w = rng.uniform(-level, level, size=4)
                pert_weights = np.maximum(0.01, base_weights + delta_w)
                pert_weights /= np.sum(pert_weights)

                pert_scores = {
                    act: sum(pert_weights[i] * scores.get(k, 0.0) for i, k in enumerate(comp_keys))
                    for act, scores in cf.items()
                }
                pert_top = max(pert_scores.items(), key=lambda x: x[1])[0]

                if pert_top != base_top:
                    flips += 1

            stability_results[f"rank_stability_{int(level * 100)}pct"] = round(1.0 - (flips / max(1, n_eval)), 4)

        return stability_results

    @staticmethod
    def audit_no_future_peeking(decisions: list[dict[str, Any]]) -> bool:
        """Audit assertion ensuring ST decisions only utilize strictly present-time observable features."""
        forbidden_keys = {
            "future_kill", "future_action", "future_day", "future_roll",
            "next_day", "next_kill", "outcome_prediction", "true_winner"
        }
        for d in decisions:
            sf = d.get("state_features", {})
            for k in sf.keys():
                if any(f in k.lower() for f in forbidden_keys):
                    raise AssertionError(f"ST FUTURE PEEKING VIOLATION: Discovered forbidden feature '{k}' in STDecisionRecord!")
        return True
