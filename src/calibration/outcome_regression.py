"""Multivariate Logistic Regression analysis for game outcome associations and multi-seed variance decomposition."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np
from scipy import optimize, stats


@dataclass(slots=True)
class RegressionCoefficient:
    predictor: str
    coefficient: float
    std_error: float
    z_score: float
    p_value: float
    odds_ratio: float
    ci_95_lower: float
    ci_95_upper: float
    relationship_type: str = "ASSOCIATION"


def fit_logistic_regression(
    X: np.ndarray,
    y: np.ndarray,
    feature_names: list[str],
) -> list[RegressionCoefficient]:
    """Fit a logistic regression model using IRLS / numerical optimization with exact standard errors."""
    n_samples, n_features = X.shape

    # Standardize features (zero mean, unit variance) to ensure numerical stability
    means = np.mean(X, axis=0)
    stds = np.std(X, axis=0)
    stds[stds < 1e-6] = 1.0
    X_std = (X - means) / stds

    # Add intercept column
    X_design = np.column_stack([np.ones(n_samples, dtype=np.float64), X_std])

    # Negative log-likelihood objective
    def neg_log_likelihood(beta: np.ndarray) -> float:
        logits = np.dot(X_design, beta)
        logits = np.clip(logits, -25.0, 25.0)
        p = 1.0 / (1.0 + np.exp(-logits))
        eps = 1e-12
        p = np.clip(p, eps, 1.0 - eps)
        ll = np.sum(y * np.log(p) + (1.0 - y) * np.log(1.0 - p))
        return -float(ll)

    def gradient(beta: np.ndarray) -> np.ndarray:
        logits = np.dot(X_design, beta)
        logits = np.clip(logits, -25.0, 25.0)
        p = 1.0 / (1.0 + np.exp(-logits))
        return np.dot(X_design.T, p - y)

    # Solve optimization with BFGS
    init_beta = np.zeros(n_features + 1, dtype=np.float64)
    res = optimize.minimize(neg_log_likelihood, init_beta, jac=gradient, method="BFGS")
    beta_hat = res.x

    # Compute Hessian matrix H = X.T * W * X
    logits = np.clip(np.dot(X_design, beta_hat), -25.0, 25.0)
    p = 1.0 / (1.0 + np.exp(-logits))
    w = p * (1.0 - p)
    W = np.diag(w)
    H = np.dot(X_design.T, np.dot(W, X_design))

    # Invert Hessian to obtain covariance matrix
    try:
        cov = np.linalg.inv(H)
    except np.linalg.LinAlgError:
        cov = np.linalg.pinv(H)

    se = np.sqrt(np.maximum(1e-8, np.diag(cov)))

    coefficients: list[RegressionCoefficient] = []
    names = ["intercept"] + feature_names

    for i in range(len(names)):
        b = float(beta_hat[i])
        s = float(se[i])
        z = b / max(1e-8, s)
        p_val = float(2.0 * (1.0 - stats.norm.cdf(abs(z))))
        or_val = float(math.exp(min(20.0, max(-20.0, b))))
        ci_low = float(math.exp(min(20.0, max(-20.0, b - 1.96 * s))))
        ci_high = float(math.exp(min(20.0, max(-20.0, b + 1.96 * s))))

        coefficients.append(
            RegressionCoefficient(
                predictor=names[i],
                coefficient=round(b, 4),
                std_error=round(s, 4),
                z_score=round(z, 4),
                p_value=round(p_val, 6),
                odds_ratio=round(or_val, 4),
                ci_95_lower=round(ci_low, 4),
                ci_95_upper=round(ci_high, 4),
                relationship_type="ASSOCIATION",
            )
        )

    return coefficients


def decompose_multi_seed_variance(
    seed_win_rates: dict[int, float],
    n_per_seed: int,
) -> dict[str, float]:
    """Decompose outcome variance into within-seed sampling variance and between-seed variance."""
    rates = list(seed_win_rates.values())
    if not rates:
        return {}

    overall_mean = float(np.mean(rates))
    # Between-seed variance: variance of the seed means
    between_seed_var = float(np.var(rates, ddof=1)) if len(rates) > 1 else 0.0

    # Within-seed theoretical Bernoulli sampling variance: p*(1-p)/n
    within_seed_var = float(np.mean([p * (1.0 - p) / float(n_per_seed) for p in rates]))

    total_var = between_seed_var + within_seed_var
    between_ratio = between_seed_var / max(1e-8, total_var)

    return {
        "overall_mean_win_rate": round(overall_mean, 4),
        "between_seed_variance": round(between_seed_var, 6),
        "within_seed_sampling_variance": round(within_seed_var, 6),
        "total_variance": round(total_var, 6),
        "between_seed_variance_ratio": round(between_ratio, 4),
        "between_seed_std": round(math.sqrt(max(0.0, between_seed_var)), 4),
    }
