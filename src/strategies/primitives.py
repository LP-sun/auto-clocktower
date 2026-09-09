"""Strategy Primitives library defining canonical atomic game behaviors and 6-class taxonomy."""
from __future__ import annotations

from enum import Enum, unique


@unique
class PrimitiveType(str, Enum):
    """6-class taxonomy of strategy primitives distinguishing gates, preferences, and modifiers."""
    ELIGIBILITY = "ELIGIBILITY"            # Ability/action availability gating
    ACTION_GATE = "ACTION_GATE"            # Hard gating whether a behavior can occur (e.g. claim sharing)
    PREFERENCE = "PREFERENCE"              # Directional strategic preference
    UTILITY_MODIFIER = "UTILITY_MODIFIER"  # Additive/multiplicative utility term
    BELIEF_UPDATE = "BELIEF_UPDATE"        # Evidence-driven cognitive belief revision
    TARGET_SELECTOR = "TARGET_SELECTOR"    # Target selection heuristic


@unique
class StrategyPrimitive(str, Enum):
    # Information Primitives
    PUBLIC_CLAIM = "PUBLIC_CLAIM"
    PRIVATE_CLAIM = "PRIVATE_CLAIM"
    SOFT_CLAIM = "SOFT_CLAIM"
    HARD_CLAIM = "HARD_CLAIM"
    DELAY_CLAIM = "DELAY_CLAIM"
    WITHHOLD_INFORMATION = "WITHHOLD_INFORMATION"
    SHARE_INFORMATION = "SHARE_INFORMATION"
    PARTIAL_DISCLOSURE = "PARTIAL_DISCLOSURE"
    FABRICATE_INFORMATION = "FABRICATE_INFORMATION"

    # Social Primitives
    SEEK_PRIVATE_CHAT = "SEEK_PRIVATE_CHAT"
    SEEK_TRUSTED_PLAYER = "SEEK_TRUSTED_PLAYER"
    SEEK_COMPLEMENTARY_INFO = "SEEK_COMPLEMENTARY_INFO"
    EXCHANGE_ROLE = "EXCHANGE_ROLE"
    BUILD_TRUST_CHAIN = "BUILD_TRUST_CHAIN"
    DEFEND_PLAYER = "DEFEND_PLAYER"
    PRESSURE_PLAYER = "PRESSURE_PLAYER"
    DISTANCE_FROM_PLAYER = "DISTANCE_FROM_PLAYER"

    # Reasoning Primitives
    CROSS_CHECK_INFORMATION = "CROSS_CHECK_INFORMATION"
    UPDATE_FROM_VOTE = "UPDATE_FROM_VOTE"
    UPDATE_FROM_DEATH = "UPDATE_FROM_DEATH"
    UPDATE_FROM_CLAIM_CONFLICT = "UPDATE_FROM_CLAIM_CONFLICT"
    BUILD_WORLD = "BUILD_WORLD"

    # Execution Primitives
    NOMINATE = "NOMINATE"
    PUSH_EXECUTION = "PUSH_EXECUTION"
    RESIST_EXECUTION = "RESIST_EXECUTION"
    ACCEPT_EXECUTION = "ACCEPT_EXECUTION"
    VOLUNTEER_EXECUTION = "VOLUNTEER_EXECUTION"
    TEST_VIRGIN = "TEST_VIRGIN"
    EXECUTE_FOR_UNDERTAKER = "EXECUTE_FOR_UNDERTAKER"
    PROTECT_HIGH_VALUE_ROLE = "PROTECT_HIGH_VALUE_ROLE"

    # Ability Timing & Target Primitives
    USE_ABILITY_NOW = "USE_ABILITY_NOW"
    DELAY_ABILITY = "DELAY_ABILITY"
    TARGET_SUSPICIOUS = "TARGET_SUSPICIOUS"
    TARGET_TRUSTED = "TARGET_TRUSTED"
    TARGET_INFO_RELEVANT = "TARGET_INFO_RELEVANT"
    SELF_SACRIFICE = "SELF_SACRIFICE"

    # Evil Alignment Primitives
    PROTECT_DEMON = "PROTECT_DEMON"
    BUS_MINION = "BUS_MINION"
    FRAME_GOOD = "FRAME_GOOD"
    FAKE_CONFIRMATION = "FAKE_CONFIRMATION"
    CLAIM_SAFE_ROLE = "CLAIM_SAFE_ROLE"
    CLAIM_INFO_ROLE = "CLAIM_INFO_ROLE"
    KILL_INFO_ROLE = "KILL_INFO_ROLE"
    EVIL_COORDINATION = "EVIL_COORDINATION"
    STAR_PASS = "STAR_PASS"
    CREATE_POISON_CONFUSION = "CREATE_POISON_CONFUSION"


PRIMITIVE_TAXONOMY: dict[StrategyPrimitive, PrimitiveType] = {
    # Action Gates
    StrategyPrimitive.PRIVATE_CLAIM: PrimitiveType.ACTION_GATE,
    StrategyPrimitive.PUBLIC_CLAIM: PrimitiveType.ACTION_GATE,
    StrategyPrimitive.EXCHANGE_ROLE: PrimitiveType.ACTION_GATE,

    # Eligibility
    StrategyPrimitive.USE_ABILITY_NOW: PrimitiveType.ELIGIBILITY,
    StrategyPrimitive.DELAY_ABILITY: PrimitiveType.ELIGIBILITY,
    StrategyPrimitive.ACCEPT_EXECUTION: PrimitiveType.ELIGIBILITY,
    StrategyPrimitive.VOLUNTEER_EXECUTION: PrimitiveType.ELIGIBILITY,

    # Preferences
    StrategyPrimitive.SEEK_PRIVATE_CHAT: PrimitiveType.PREFERENCE,
    StrategyPrimitive.SEEK_TRUSTED_PLAYER: PrimitiveType.PREFERENCE,
    StrategyPrimitive.SEEK_COMPLEMENTARY_INFO: PrimitiveType.PREFERENCE,
    StrategyPrimitive.TEST_VIRGIN: PrimitiveType.PREFERENCE,
    StrategyPrimitive.PROTECT_HIGH_VALUE_ROLE: PrimitiveType.PREFERENCE,
    StrategyPrimitive.EVIL_COORDINATION: PrimitiveType.PREFERENCE,
    StrategyPrimitive.STAR_PASS: PrimitiveType.PREFERENCE,
    StrategyPrimitive.SELF_SACRIFICE: PrimitiveType.PREFERENCE,

    # Utility Modifiers
    StrategyPrimitive.SOFT_CLAIM: PrimitiveType.UTILITY_MODIFIER,
    StrategyPrimitive.HARD_CLAIM: PrimitiveType.UTILITY_MODIFIER,
    StrategyPrimitive.DELAY_CLAIM: PrimitiveType.UTILITY_MODIFIER,
    StrategyPrimitive.WITHHOLD_INFORMATION: PrimitiveType.UTILITY_MODIFIER,
    StrategyPrimitive.SHARE_INFORMATION: PrimitiveType.UTILITY_MODIFIER,
    StrategyPrimitive.PARTIAL_DISCLOSURE: PrimitiveType.UTILITY_MODIFIER,
    StrategyPrimitive.FABRICATE_INFORMATION: PrimitiveType.UTILITY_MODIFIER,
    StrategyPrimitive.BUILD_TRUST_CHAIN: PrimitiveType.UTILITY_MODIFIER,
    StrategyPrimitive.DEFEND_PLAYER: PrimitiveType.UTILITY_MODIFIER,
    StrategyPrimitive.PRESSURE_PLAYER: PrimitiveType.UTILITY_MODIFIER,
    StrategyPrimitive.DISTANCE_FROM_PLAYER: PrimitiveType.UTILITY_MODIFIER,
    StrategyPrimitive.NOMINATE: PrimitiveType.UTILITY_MODIFIER,
    StrategyPrimitive.PUSH_EXECUTION: PrimitiveType.UTILITY_MODIFIER,
    StrategyPrimitive.RESIST_EXECUTION: PrimitiveType.UTILITY_MODIFIER,
    StrategyPrimitive.EXECUTE_FOR_UNDERTAKER: PrimitiveType.UTILITY_MODIFIER,
    StrategyPrimitive.PROTECT_DEMON: PrimitiveType.UTILITY_MODIFIER,
    StrategyPrimitive.BUS_MINION: PrimitiveType.UTILITY_MODIFIER,
    StrategyPrimitive.FRAME_GOOD: PrimitiveType.UTILITY_MODIFIER,
    StrategyPrimitive.FAKE_CONFIRMATION: PrimitiveType.UTILITY_MODIFIER,
    StrategyPrimitive.CLAIM_SAFE_ROLE: PrimitiveType.UTILITY_MODIFIER,
    StrategyPrimitive.CLAIM_INFO_ROLE: PrimitiveType.UTILITY_MODIFIER,
    StrategyPrimitive.CREATE_POISON_CONFUSION: PrimitiveType.UTILITY_MODIFIER,

    # Belief Updates
    StrategyPrimitive.CROSS_CHECK_INFORMATION: PrimitiveType.BELIEF_UPDATE,
    StrategyPrimitive.UPDATE_FROM_VOTE: PrimitiveType.BELIEF_UPDATE,
    StrategyPrimitive.UPDATE_FROM_DEATH: PrimitiveType.BELIEF_UPDATE,
    StrategyPrimitive.UPDATE_FROM_CLAIM_CONFLICT: PrimitiveType.BELIEF_UPDATE,
    StrategyPrimitive.BUILD_WORLD: PrimitiveType.BELIEF_UPDATE,

    # Target Selectors
    StrategyPrimitive.TARGET_SUSPICIOUS: PrimitiveType.TARGET_SELECTOR,
    StrategyPrimitive.TARGET_TRUSTED: PrimitiveType.TARGET_SELECTOR,
    StrategyPrimitive.TARGET_INFO_RELEVANT: PrimitiveType.TARGET_SELECTOR,
    StrategyPrimitive.KILL_INFO_ROLE: PrimitiveType.TARGET_SELECTOR,
}


def get_primitive_type(primitive: StrategyPrimitive | str) -> PrimitiveType:
    """Resolve PrimitiveType for a given StrategyPrimitive enum or string."""
    if isinstance(primitive, str):
        try:
            primitive = StrategyPrimitive(primitive)
        except ValueError:
            return PrimitiveType.UTILITY_MODIFIER
    return PRIMITIVE_TAXONOMY.get(primitive, PrimitiveType.UTILITY_MODIFIER)
