"""Trouble Brewing Mathematical Calibration and Diagnostics Package."""
from __future__ import annotations

from src.calibration.alignment import AlignmentMetrics, compute_alignment_and_quadrants
from src.calibration.failure_modes import AssociatedFailureMode, GoodLossDecomposition
from src.calibration.friendly_fire import FriendlyFireCause, FriendlyFireReport, analyze_friendly_fire
from src.calibration.human_benchmark import (
    DeathTempo,
    HumanStructureBenchmark,
    NominationMetrics,
    SurvivalFunnel,
    compute_human_structure_benchmark,
)
from src.calibration.metrics import BehaviorMetricDefinition, BehaviorMetricRegistry, compute_bootstrap_ci, extract_game_behavior_metrics
from src.calibration.outcome_regression import RegressionCoefficient, decompose_multi_seed_variance, fit_logistic_regression
from src.calibration.parameters import (
    CalibrationConfig,
    CalibrationParameter,
    CalibrationRegistry,
    IdentifiabilityReport,
    ParameterDomain,
    ReducedPersonality6D,
    TransformType,
    compute_identifiability_analysis,
    get_6d_calibration_parameters,
)
from src.calibration.primitives import PrimitiveInteractionAnalyzer
from src.calibration.st_diagnostics import StorytellerDiagnostics

__all__ = [
    "AlignmentMetrics",
    "compute_alignment_and_quadrants",
    "AssociatedFailureMode",
    "GoodLossDecomposition",
    "FriendlyFireCause",
    "FriendlyFireReport",
    "analyze_friendly_fire",
    "DeathTempo",
    "HumanStructureBenchmark",
    "NominationMetrics",
    "SurvivalFunnel",
    "compute_human_structure_benchmark",
    "BehaviorMetricDefinition",
    "BehaviorMetricRegistry",
    "compute_bootstrap_ci",
    "extract_game_behavior_metrics",
    "RegressionCoefficient",
    "decompose_multi_seed_variance",
    "fit_logistic_regression",
    "CalibrationConfig",
    "CalibrationParameter",
    "CalibrationRegistry",
    "IdentifiabilityReport",
    "ParameterDomain",
    "ReducedPersonality6D",
    "get_6d_calibration_parameters",
    "TransformType",
    "compute_identifiability_analysis",
    "PrimitiveInteractionAnalyzer",
    "StorytellerDiagnostics",
]

