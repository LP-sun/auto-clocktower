"""Skill level modeling modulating rationality, noise, memory, and strategic discipline with continuous calibration support."""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any

from src.engine.types import SkillLevel


@dataclass(slots=True)
class SkillProfile:
    level: SkillLevel
    skill_score: float        # Normalized skill in [0, 1]
    belief_accuracy: float    # How accurately evidence updates belief [0.5, 1.0]
    temperature: float        # Softmax temperature (higher = more erratic/noisy) [0.4, 2.5]
    memory_retention: float   # Factor modulating memory decay [0.5, 2.0]
    voting_discipline: float  # Discipline regarding ghost votes & threshold [0.3, 1.0]
    bluff_consistency: float  # Evil bluff plausibility & consistency [0.4, 1.0]


SKILL_PRESETS: dict[SkillLevel, SkillProfile] = {
    SkillLevel.BEGINNER: SkillProfile(
        level=SkillLevel.BEGINNER,
        skill_score=0.25,
        belief_accuracy=0.60,
        temperature=1.8,
        memory_retention=0.65,
        voting_discipline=0.45,
        bluff_consistency=0.45,
    ),
    SkillLevel.INTERMEDIATE: SkillProfile(
        level=SkillLevel.INTERMEDIATE,
        skill_score=0.50,
        belief_accuracy=0.78,
        temperature=1.2,
        memory_retention=1.0,
        voting_discipline=0.70,
        bluff_consistency=0.70,
    ),
    SkillLevel.EXPERIENCED: SkillProfile(
        level=SkillLevel.EXPERIENCED,
        skill_score=0.75,
        belief_accuracy=0.90,
        temperature=0.8,
        memory_retention=1.35,
        voting_discipline=0.88,
        bluff_consistency=0.88,
    ),
    SkillLevel.EXPERT: SkillProfile(
        level=SkillLevel.EXPERT,
        skill_score=0.95,
        belief_accuracy=0.98,
        temperature=0.5,
        memory_retention=1.8,
        voting_discipline=0.98,
        bluff_consistency=0.96,
    ),
}


def create_skill_profile_from_score(score: float, config: Any = None) -> SkillProfile:
    """Interpolate a continuous skill profile from score in [0, 1] for decile calibration curves."""
    s = max(0.0, min(1.0, score))
    if s < 0.35:
        lvl = SkillLevel.BEGINNER
    elif s < 0.65:
        lvl = SkillLevel.INTERMEDIATE
    elif s < 0.85:
        lvl = SkillLevel.EXPERIENCED
    else:
        lvl = SkillLevel.EXPERT

    # Linear continuous interpolation between beginner (0.0) and expert (1.0)
    base_acc = 0.55 + 0.43 * s
    base_temp = 2.0 - 1.5 * s
    base_mem = 0.5 + 1.4 * s
    base_disc = 0.4 + 0.58 * s
    base_bluff = 0.4 + 0.58 * s

    t_scale = float(config.get("skill_temperature_scale", 1.0)) if config else 1.0
    acc_scale = float(config.get("skill_belief_accuracy_scale", 1.0)) if config else 1.0
    mem_scale = float(config.get("skill_memory_retention_scale", 1.0)) if config else 1.0
    disc_scale = float(config.get("skill_voting_discipline_scale", 1.0)) if config else 1.0

    return SkillProfile(
        level=lvl,
        skill_score=round(s, 3),
        belief_accuracy=min(1.0, max(0.4, base_acc * acc_scale)),
        temperature=max(0.2, base_temp * t_scale),
        memory_retention=max(0.3, base_mem * mem_scale),
        voting_discipline=min(1.0, max(0.2, base_disc * disc_scale)),
        bluff_consistency=min(1.0, max(0.2, base_bluff)),
    )


def sample_skill_profile(rng: random.Random | None = None, config: Any = None) -> SkillProfile:
    """Sample skill from a realistic population distribution with config overrides."""
    r = rng or random.Random()
    choice = r.choices(
        population=[
            SkillLevel.BEGINNER,
            SkillLevel.INTERMEDIATE,
            SkillLevel.EXPERIENCED,
            SkillLevel.EXPERT,
        ],
        weights=[0.20, 0.45, 0.25, 0.10],
        k=1,
    )[0]
    base = SKILL_PRESETS[choice]
    if not config:
        return base

    t_scale = float(config.get("skill_temperature_scale", 1.0))
    acc_scale = float(config.get("skill_belief_accuracy_scale", 1.0))
    mem_scale = float(config.get("skill_memory_retention_scale", 1.0))
    disc_scale = float(config.get("skill_voting_discipline_scale", 1.0))

    return SkillProfile(
        level=base.level,
        skill_score=base.skill_score,
        belief_accuracy=min(1.0, max(0.3, base.belief_accuracy * acc_scale)),
        temperature=max(0.2, base.temperature * t_scale),
        memory_retention=max(0.3, base.memory_retention * mem_scale),
        voting_discipline=min(1.0, max(0.2, base.voting_discipline * disc_scale)),
        bluff_consistency=base.bluff_consistency,
    )


def sample_skill(level: str | SkillLevel | None = None, seed: int | None = None, config: Any = None) -> SkillProfile:
    """Helper returning a SkillProfile by level name or sampled randomly."""
    if isinstance(level, str):
        level = SkillLevel(level.lower())
    if level in SKILL_PRESETS:
        base = SKILL_PRESETS[level]
        if not config:
            return base
        return SkillProfile(
            level=base.level,
            skill_score=base.skill_score,
            belief_accuracy=min(1.0, max(0.3, base.belief_accuracy * float(config.get("skill_belief_accuracy_scale", 1.0)))),
            temperature=max(0.2, base.temperature * float(config.get("skill_temperature_scale", 1.0))),
            memory_retention=max(0.3, base.memory_retention * float(config.get("skill_memory_retention_scale", 1.0))),
            voting_discipline=min(1.0, max(0.2, base.voting_discipline * float(config.get("skill_voting_discipline_scale", 1.0)))),
            bluff_consistency=base.bluff_consistency,
        )
    r = random.Random(seed) if seed is not None else None
    return sample_skill_profile(r, config=config)
