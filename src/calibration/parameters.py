"""Parameter registry, domain/transform metadata, config override, and identifiability Jacobian analysis."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum, unique
from typing import Any, Callable

import numpy as np


@unique
class ParameterDomain(str, Enum):
    PROBABILITY = "PROBABILITY"          # [0, 1]
    UNIT_INTERVAL = "UNIT_INTERVAL"      # [0, 1]
    POSITIVE_REAL = "POSITIVE_REAL"      # (0, inf)
    REAL = "REAL"                        # (-inf, inf)
    DISCRETE = "DISCRETE"


@unique
class TransformType(str, Enum):
    LOGIT = "LOGIT"                      # logit space perturbation for probabilities: sigma(logit(p) +/- delta)
    MULTIPLICATIVE = "MULTIPLICATIVE"    # theta * [0.5, 0.8, 1.0, 1.2, 1.5] for positive weights
    LOG = "LOG"                          # log(theta) +/- delta
    ADDITIVE = "ADDITIVE"                # theta + delta for unconstrained reals


@dataclass(slots=True)
class CalibrationParameter:
    name: str
    default: float
    bounds: tuple[float, float]
    domain: ParameterDomain
    transform: TransformType
    module: str
    description: str
    expected_effects: str

    def generate_sweep_values(self) -> list[float]:
        """Generate 5-point sweep values strictly adhering to parameter domain and transform type."""
        d = self.default
        low, high = self.bounds

        if self.transform == TransformType.LOGIT:
            # Clamp default to avoid logit singularity
            p = max(0.01, min(0.99, d))
            logit_d = math.log(p / (1.0 - p))
            deltas = [-0.8, -0.4, 0.0, 0.4, 0.8]
            vals = [1.0 / (1.0 + math.exp(-(logit_d + delta))) for delta in deltas]
        elif self.transform == TransformType.MULTIPLICATIVE:
            factors = [0.5, 0.8, 1.0, 1.2, 1.5]
            vals = [d * f for f in factors]
        elif self.transform == TransformType.ADDITIVE:
            span = (high - low) * 0.15
            deltas = [-2.0 * span, -1.0 * span, 0.0, 1.0 * span, 2.0 * span]
            vals = [d + delta for delta in deltas]
        else:
            vals = [d * 0.5, d * 0.8, d, d * 1.2, d * 1.5]

        # Clamp all values strictly within parameter bounds
        clamped = [max(low, min(high, round(v, 4))) for v in vals]
        # Ensure monotone uniqueness
        unique_vals: list[float] = []
        for v in clamped:
            if not unique_vals or v != unique_vals[-1]:
                unique_vals.append(v)
        while len(unique_vals) < 5:
            # Fallback interpolation if clamped collapsed
            unique_vals = [round(low + (high - low) * i / 4.0, 4) for i in range(5)]
            break
        return unique_vals


@dataclass
class CalibrationConfig:
    """Config-driven container of hyperparameter overrides for population distributions and policies."""
    overrides: dict[str, float] = field(default_factory=dict)

    def get(self, name: str, default: float) -> float:
        return self.overrides.get(name, default)

    def with_override(self, name: str, value: float) -> CalibrationConfig:
        new_ov = dict(self.overrides)
        new_ov[name] = value
        return CalibrationConfig(overrides=new_ov)


class CalibrationRegistry:
    """Central repository of registered calibration parameters eliminating magic numbers."""

    _registry: dict[str, CalibrationParameter] = {}

    @classmethod
    def register(cls, param: CalibrationParameter) -> None:
        cls._registry[param.name] = param

    @classmethod
    def get(cls, name: str) -> CalibrationParameter | None:
        return cls._registry.get(name)

    @classmethod
    def all_parameters(cls) -> list[CalibrationParameter]:
        return list(cls._registry.values())


# Register core parameters
CalibrationRegistry.register(
    CalibrationParameter(
        name="pop_activity_mu",
        default=0.50,
        bounds=(0.1, 0.9),
        domain=ParameterDomain.UNIT_INTERVAL,
        transform=TransformType.LOGIT,
        module="personality_population",
        description="Population mean activity level in Beta(mu*kappa, (1-mu)*kappa)",
        expected_effects="Increases private chat counts, nomination frequency, and day activity",
    )
)
CalibrationRegistry.register(
    CalibrationParameter(
        name="pop_social_initiative_mu",
        default=0.50,
        bounds=(0.1, 0.9),
        domain=ParameterDomain.UNIT_INTERVAL,
        transform=TransformType.LOGIT,
        module="personality_population",
        description="Population mean social initiative level for seeking private whispers",
        expected_effects="Increases private chat edge density and early claim exchanges",
    )
)
CalibrationRegistry.register(
    CalibrationParameter(
        name="pop_openness_mu",
        default=0.50,
        bounds=(0.1, 0.9),
        domain=ParameterDomain.UNIT_INTERVAL,
        transform=TransformType.LOGIT,
        module="personality_population",
        description="Population mean openness to disclosing identity in whispers/public",
        expected_effects="Increases early claim disclosure and evil information harvesting",
    )
)
CalibrationRegistry.register(
    CalibrationParameter(
        name="pop_aggression_mu",
        default=0.4167,
        bounds=(0.1, 0.9),
        domain=ParameterDomain.UNIT_INTERVAL,
        transform=TransformType.LOGIT,
        module="personality_population",
        description="Population mean aggression driving nomination and execution pushes",
        expected_effects="Increases nomination count per day and lowers execution threshold hesitation",
    )
)
CalibrationRegistry.register(
    CalibrationParameter(
        name="pop_conformity_mu",
        default=0.50,
        bounds=(0.1, 0.9),
        domain=ParameterDomain.UNIT_INTERVAL,
        transform=TransformType.LOGIT,
        module="personality_population",
        description="Population mean conformity following public voting bandwagons",
        expected_effects="Increases voting consensus and reduces split votes on nominations",
    )
)
CalibrationRegistry.register(
    CalibrationParameter(
        name="pop_dispersion_kappa",
        default=6.0,
        bounds=(2.0, 20.0),
        domain=ParameterDomain.POSITIVE_REAL,
        transform=TransformType.MULTIPLICATIVE,
        module="personality_population",
        description="Population dispersion (effective sample size) controlling inter-player personality variance",
        expected_effects="Higher kappa concentrates population around mean; lower kappa expands extremes",
    )
)
CalibrationRegistry.register(
    CalibrationParameter(
        name="skill_temperature_scale",
        default=1.0,
        bounds=(0.3, 3.0),
        domain=ParameterDomain.POSITIVE_REAL,
        transform=TransformType.MULTIPLICATIVE,
        module="skill_profile",
        description="Global multiplier on softmax temperatures across all skill tiers",
        expected_effects="Lower temperature increases rationality and policy determinism",
    )
)
CalibrationRegistry.register(
    CalibrationParameter(
        name="skill_belief_accuracy_scale",
        default=1.0,
        bounds=(0.4, 2.0),
        domain=ParameterDomain.POSITIVE_REAL,
        transform=TransformType.MULTIPLICATIVE,
        module="skill_profile",
        description="Multiplier on belief update magnitude and evidence fidelity",
        expected_effects="Improves demon discovery time and reduces trust errors",
    )
)
CalibrationRegistry.register(
    CalibrationParameter(
        name="vote_evil_weight",
        default=3.0,
        bounds=(0.5, 6.0),
        domain=ParameterDomain.POSITIVE_REAL,
        transform=TransformType.MULTIPLICATIVE,
        module="decision_policy",
        description="Good player utility weight placed on target evil probability during voting",
        expected_effects="Higher weight increases vote consistency with suspicion and execution focus",
    )
)
CalibrationRegistry.register(
    CalibrationParameter(
        name="vote_demon_weight",
        default=2.0,
        bounds=(0.5, 6.0),
        domain=ParameterDomain.POSITIVE_REAL,
        transform=TransformType.MULTIPLICATIVE,
        module="decision_policy",
        description="Good player utility weight placed on target demon probability during voting",
        expected_effects="Higher weight sharpens vote focus when demon is suspected",
    )
)
CalibrationRegistry.register(
    CalibrationParameter(
        name="nomination_evil_weight",
        default=2.5,
        bounds=(0.5, 6.0),
        domain=ParameterDomain.POSITIVE_REAL,
        transform=TransformType.MULTIPLICATIVE,
        module="decision_policy",
        description="Utility weight on target evil probability when selecting nominations",
        expected_effects="Higher weight leads to nomination targets having higher average suspicion",
    )
)
CalibrationRegistry.register(
    CalibrationParameter(
        name="vote_base_bias",
        default=-1.2,
        bounds=(-3.0, 0.5),
        domain=ParameterDomain.REAL,
        transform=TransformType.ADDITIVE,
        module="decision_policy",
        description="Base negative utility bias against voting yes (hesitation barrier)",
        expected_effects="More negative bias reduces daily executions; higher bias increases executions",
    )
)


@dataclass(slots=True)
class IdentifiabilityReport:
    parameter_names: list[str]
    metric_names: list[str]
    jacobian: np.ndarray             # Shape: (n_metrics, n_parameters)
    singular_values: list[float]
    condition_number: float
    effective_rank: int
    correlation_matrix: np.ndarray  # Shape: (n_parameters, n_parameters)
    collinear_pairs: list[tuple[str, str, float, str]]  # (p1, p2, corr, recommendation)


def compute_identifiability_analysis(
    param_names: list[str],
    metric_names: list[str],
    base_metrics: dict[str, float],
    perturbed_metrics: dict[str, dict[str, float]],  # param_name -> {metric_name -> perturbed_value}
    delta_thetas: dict[str, float],                  # param_name -> delta_theta / theta_0
) -> IdentifiabilityReport:
    """Compute sensitivity Jacobian J, condition number, collinearity matrix, and redundancy recommendations."""
    n_p = len(param_names)
    n_m = len(metric_names)
    J = np.zeros((n_m, n_p), dtype=np.float64)

    for j, p in enumerate(param_names):
        d_theta = delta_thetas.get(p, 0.2)
        if abs(d_theta) < 1e-6:
            d_theta = 0.2
        for i, m in enumerate(metric_names):
            val_base = base_metrics.get(m, 0.0)
            val_pert = perturbed_metrics.get(p, {}).get(m, val_base)
            # Normalized relative elasticity if base != 0, else raw finite difference
            if abs(val_base) > 1e-4:
                elasticity = ((val_pert - val_base) / val_base) / d_theta
            else:
                elasticity = (val_pert - val_base) / d_theta
            J[i, j] = elasticity

    # SVD analysis
    u, s, vh = np.linalg.svd(J, full_matrices=False)
    s_list = [float(val) for val in s]
    cond_num = float(s[0] / max(1e-9, s[-1])) if len(s) > 0 and s[-1] > 1e-9 else 9999.0
    tol = max(J.shape) * np.finfo(J.dtype).eps * s[0] if len(s) > 0 else 1e-9
    eff_rank = int(np.sum(s > tol))

    # Pairwise correlation between parameter sensitivity columns
    corr = np.eye(n_p, dtype=np.float64)
    collinear_pairs: list[tuple[str, str, float, str]] = []

    for i in range(n_p):
        col_i = J[:, i]
        norm_i = np.linalg.norm(col_i)
        for j in range(i + 1, n_p):
            col_j = J[:, j]
            norm_j = np.linalg.norm(col_j)
            if norm_i > 1e-6 and norm_j > 1e-6:
                r = float(np.dot(col_i, col_j) / (norm_i * norm_j))
            else:
                r = 0.0
            corr[i, j] = r
            corr[j, i] = r

            if abs(r) > 0.85:
                # High collinearity: recommend action
                p1, p2 = param_names[i], param_names[j]
                if "social" in p1 and "activity" in p2:
                    rec = "MERGE: Highly collinear social initiation and general activity"
                elif "openness" in p1 and "social" in p2:
                    rec = "REDEFINE: Separate chat frequency from information disclosure threshold"
                else:
                    rec = f"REDUNDANT: Sensitivity profile similarity |r|={abs(r):.2f} > 0.85; consider fixing one"
                collinear_pairs.append((p1, p2, round(r, 4), rec))

    return IdentifiabilityReport(
        parameter_names=param_names,
        metric_names=metric_names,
        jacobian=J,
        singular_values=[round(x, 4) for x in s_list],
        condition_number=round(cond_num, 2),
        effective_rank=eff_rank,
        correlation_matrix=np.round(corr, 4),
        collinear_pairs=collinear_pairs,
    )


@dataclass(slots=True)
class ReducedPersonality6D:
    """6D reduced personality profile resolving high-collinearity and low-identifiability traits."""
    assertiveness: float = 0.50   # Merges aggression and risk_tolerance
    skepticism: float = 0.50      # Inverted gullibility / evidence scrutiny
    conformity: float = 0.50      # Social cascade sensitivity beta
    expressiveness: float = 0.50  # Chat / disclosure activity
    patience: float = 0.50        # Execution threshold conservativeness
    evil_loyalty: float = 0.70    # Demon protection vs busing utility

    def to_10d_mapping(self) -> dict[str, float]:
        """Project 6D reduced coordinates into equivalent 10D personality vector."""
        return {
            "activity": max(0.0, min(1.0, 0.7 - 0.3 * self.patience)),
            "openness": self.expressiveness,
            "aggression": self.assertiveness,
            "risk_tolerance": self.assertiveness,
            "deception_tendency": self.evil_loyalty,
            "trust_propensity": max(0.0, min(1.0, 1.0 - self.skepticism)),
            "conformity": self.conformity,
            "stubbornness": 0.50,         # Fixed (low identifiability)
            "confidence": max(0.0, min(1.0, 1.0 - 0.5 * self.patience)),
            "social_initiative": self.expressiveness,
        }



def get_6d_calibration_parameters() -> list[CalibrationParameter]:
    """Return calibration parameter definitions for the 6D reduced personality model."""
    return [
        CalibrationParameter(
            name="pop_assertiveness_mu",
            default=0.50,
            bounds=(0.1, 0.9),
            domain=ParameterDomain.UNIT_INTERVAL,
            transform=TransformType.LOGIT,
            module="personality_6d",
            description="Mean assertiveness (merges aggression and risk tolerance)",
            expected_effects="Increases nomination rate and Slayer firing",
        ),
        CalibrationParameter(
            name="pop_skepticism_mu",
            default=0.50,
            bounds=(0.1, 0.9),
            domain=ParameterDomain.UNIT_INTERVAL,
            transform=TransformType.LOGIT,
            module="personality_6d",
            description="Mean skepticism (evidence scrutiny and claim resistance)",
            expected_effects="Reduces vulnerability to evil bluffs, increases audit of suspicious claims",
        ),
        CalibrationParameter(
            name="pop_conformity_mu",
            default=0.50,
            bounds=(0.1, 0.9),
            domain=ParameterDomain.UNIT_INTERVAL,
            transform=TransformType.LOGIT,
            module="personality_6d",
            description="Mean social conformity beta",
            expected_effects="Higher values produce stronger vote cascades and bandwagoning",
        ),
        CalibrationParameter(
            name="pop_expressiveness_mu",
            default=0.50,
            bounds=(0.1, 0.9),
            domain=ParameterDomain.UNIT_INTERVAL,
            transform=TransformType.LOGIT,
            module="personality_6d",
            description="Mean expressiveness / disclosure propensity",
            expected_effects="Increases public claim frequency and whisper communication",
        ),
        CalibrationParameter(
            name="pop_patience_mu",
            default=0.50,
            bounds=(0.1, 0.9),
            domain=ParameterDomain.UNIT_INTERVAL,
            transform=TransformType.LOGIT,
            module="personality_6d",
            description="Mean strategic patience / conservative execution threshold",
            expected_effects="Increases no-execution rate on uncertain days, especially at 4 alive",
        ),
        CalibrationParameter(
            name="pop_evil_loyalty_mu",
            default=0.70,
            bounds=(0.2, 0.95),
            domain=ParameterDomain.UNIT_INTERVAL,
            transform=TransformType.LOGIT,
            module="personality_6d",
            description="Mean evil loyalty / resistance to busing Demon",
            expected_effects="Controls evil voting coordination and willing busing under pressure",
        ),
    ]

