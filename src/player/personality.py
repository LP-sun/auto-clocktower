"""10-dimensional personality vector initialized from realistic Beta distributions with population hyperparameter control."""
from __future__ import annotations

import random
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(slots=True)
class PersonalityVector:
    activity: float           # Propensity to initiate discussion and take actions [0, 1]
    openness: float           # Willingness to disclose private information [0, 1]
    aggression: float         # Likelihood of accusing, nominating, and pushing executions [0, 1]
    risk_tolerance: float     # Tolerance for high-risk gambles (slayer, virgin testing) [0, 1]
    deception_tendency: float # Tendency to lie, bluff, or conceal as good or evil [0, 1]
    trust_propensity: float   # Baseline inclination to believe others' claims [0, 1]
    conformity: float         # Tendency to follow majority votes and public consensus [0, 1]
    stubbornness: float       # Resistance to changing prior beliefs upon new evidence [0, 1]
    confidence: float         # Subjective certainty in own reads and theories [0, 1]
    social_initiative: float  # Proactivity in seeking private whispers [0, 1]

    def to_dict(self) -> dict[str, float]:
        return asdict(self)


def sample_personality(
    rng: random.Random | None = None,
    seed: int | None = None,
    config: Any = None,
) -> PersonalityVector:
    """Sample an individual personality from population Beta distributions parameterized by (mu, kappa)."""
    r = rng or random.Random(seed)

    # Dispersion kappa controls variance across the population
    kappa = float(config.get("pop_dispersion_kappa", 6.0)) if config else 6.0
    kappa = max(1.5, kappa)

    def beta_from_mu(mu_key: str, default_mu: float) -> float:
        mu = float(config.get(mu_key, default_mu)) if config else default_mu
        mu = max(0.01, min(0.99, mu))
        a = max(0.1, mu * kappa)
        b = max(0.1, (1.0 - mu) * kappa)
        return r.betavariate(a, b)

    return PersonalityVector(
        activity=beta_from_mu("pop_activity_mu", 0.50),
        openness=beta_from_mu("pop_openness_mu", 0.50),
        aggression=beta_from_mu("pop_aggression_mu", 2.5 / 6.0),
        risk_tolerance=beta_from_mu("pop_risk_tolerance_mu", 2.5 / 5.5),
        deception_tendency=beta_from_mu("pop_deception_tendency_mu", 2.0 / 6.0),
        trust_propensity=beta_from_mu("pop_trust_propensity_mu", 3.5 / 6.5),
        conformity=beta_from_mu("pop_conformity_mu", 0.50),
        stubbornness=beta_from_mu("pop_stubbornness_mu", 2.5 / 5.5),
        confidence=beta_from_mu("pop_confidence_mu", 0.50),
        social_initiative=beta_from_mu("pop_social_initiative_mu", 0.50),
    )
