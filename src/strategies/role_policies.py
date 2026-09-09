"""Role-specific strategy policies mapping Trouble Brewing roles to primitive utility biases."""
from __future__ import annotations

from typing import Mapping

from src.engine.types import RoleId
from src.strategies.primitives import StrategyPrimitive

# Utility bias dictionary: RoleId -> {StrategyPrimitive: weight_modifier}
ROLE_PRIMITIVE_MODIFIERS: Mapping[RoleId, dict[StrategyPrimitive, float]] = {
    RoleId.WASHERWOMAN: {
        StrategyPrimitive.SEEK_PRIVATE_CHAT: 1.5,
        StrategyPrimitive.EXCHANGE_ROLE: 1.2,
        StrategyPrimitive.DELAY_CLAIM: 0.6,
        StrategyPrimitive.TEST_VIRGIN: 1.0,
        StrategyPrimitive.ACCEPT_EXECUTION: 0.3,
    },
    RoleId.LIBRARIAN: {
        StrategyPrimitive.SEEK_PRIVATE_CHAT: 1.4,
        StrategyPrimitive.CROSS_CHECK_INFORMATION: 1.3,
        StrategyPrimitive.DELAY_CLAIM: 0.5,
        StrategyPrimitive.TEST_VIRGIN: 1.0,
        StrategyPrimitive.ACCEPT_EXECUTION: 0.3,
    },
    RoleId.INVESTIGATOR: {
        StrategyPrimitive.SEEK_PRIVATE_CHAT: 1.6,
        StrategyPrimitive.PRESSURE_PLAYER: 1.2,
        StrategyPrimitive.CROSS_CHECK_INFORMATION: 1.4,
        StrategyPrimitive.DELAY_CLAIM: 0.8,
        StrategyPrimitive.TEST_VIRGIN: 0.8,
    },
    RoleId.CHEF: {
        StrategyPrimitive.SEEK_COMPLEMENTARY_INFO: 1.4,
        StrategyPrimitive.CROSS_CHECK_INFORMATION: 1.5,
        StrategyPrimitive.ACCEPT_EXECUTION: 0.4,
        StrategyPrimitive.TEST_VIRGIN: 1.2,
    },
    RoleId.EMPATH: {
        StrategyPrimitive.DELAY_CLAIM: 1.2,
        StrategyPrimitive.PRIVATE_CLAIM: 1.0,
        StrategyPrimitive.PROTECT_HIGH_VALUE_ROLE: 1.5,
        StrategyPrimitive.RESIST_EXECUTION: 1.3,
        StrategyPrimitive.TEST_VIRGIN: -1.0,  # Do not risk dying on Virgin
    },
    RoleId.FORTUNE_TELLER: {
        StrategyPrimitive.DELAY_CLAIM: 1.4,
        StrategyPrimitive.PRIVATE_CLAIM: 1.1,
        StrategyPrimitive.PROTECT_HIGH_VALUE_ROLE: 1.8,
        StrategyPrimitive.RESIST_EXECUTION: 1.6,
        StrategyPrimitive.TARGET_SUSPICIOUS: 1.5,
        StrategyPrimitive.TEST_VIRGIN: -1.5,
    },
    RoleId.UNDERTAKER: {
        StrategyPrimitive.DELAY_CLAIM: 1.5,
        StrategyPrimitive.EXECUTE_FOR_UNDERTAKER: 1.8,
        StrategyPrimitive.PROTECT_HIGH_VALUE_ROLE: 1.6,
        StrategyPrimitive.RESIST_EXECUTION: 1.4,
        StrategyPrimitive.TEST_VIRGIN: -1.5,
    },
    RoleId.MONK: {
        StrategyPrimitive.DELAY_CLAIM: 1.6,
        StrategyPrimitive.TARGET_TRUSTED: 1.8,  # Protect trusted info roles
        StrategyPrimitive.PROTECT_HIGH_VALUE_ROLE: 1.9,
        StrategyPrimitive.RESIST_EXECUTION: 0.8,
    },
    RoleId.RAVENKEEPER: {
        StrategyPrimitive.DELAY_CLAIM: 1.8,
        StrategyPrimitive.CLAIM_INFO_ROLE: 1.5,  # Bait demon kill by claiming high value
        StrategyPrimitive.SELF_SACRIFICE: 2.0,
        StrategyPrimitive.TARGET_SUSPICIOUS: 1.6,
    },
    RoleId.VIRGIN: {
        StrategyPrimitive.TEST_VIRGIN: 2.5,
        StrategyPrimitive.PUBLIC_CLAIM: 1.4,
        StrategyPrimitive.BUILD_TRUST_CHAIN: 1.8,
    },
    RoleId.SLAYER: {
        StrategyPrimitive.DELAY_ABILITY: 1.3,  # Shoot later when demon pool is small
        StrategyPrimitive.TARGET_SUSPICIOUS: 2.0,
        StrategyPrimitive.DELAY_CLAIM: 0.9,
    },
    RoleId.SOLDIER: {
        StrategyPrimitive.DELAY_CLAIM: 0.8,
        StrategyPrimitive.VOLUNTEER_EXECUTION: 0.3,
        StrategyPrimitive.SELF_SACRIFICE: 0.5,
    },
    RoleId.MAYOR: {
        StrategyPrimitive.DELAY_CLAIM: 1.4,
        StrategyPrimitive.RESIST_EXECUTION: 1.8,
        StrategyPrimitive.PROTECT_HIGH_VALUE_ROLE: 1.2,
    },
    RoleId.BUTLER: {
        StrategyPrimitive.SEEK_TRUSTED_PLAYER: 1.5,
        StrategyPrimitive.DELAY_CLAIM: 0.5,
        StrategyPrimitive.ACCEPT_EXECUTION: 0.4,
    },
    RoleId.DRUNK: {
        # Drunk thinks they are townsfolk, uses apparent role policy!
        StrategyPrimitive.CROSS_CHECK_INFORMATION: 1.2,
    },
    RoleId.RECLUSE: {
        StrategyPrimitive.DELAY_CLAIM: 1.2,
        StrategyPrimitive.ACCEPT_EXECUTION: 0.6,
        StrategyPrimitive.DEFEND_PLAYER: 0.5,
    },
    RoleId.SAINT: {
        StrategyPrimitive.RESIST_EXECUTION: 3.5,  # Absolute priority: never get executed!
        StrategyPrimitive.PUBLIC_CLAIM: 1.2,
        StrategyPrimitive.DEFEND_PLAYER: -0.5,
    },
    RoleId.POISONER: {
        StrategyPrimitive.TARGET_SUSPICIOUS: -1.0,
        StrategyPrimitive.TARGET_INFO_RELEVANT: 2.0,  # Poison ongoing info roles (Empath, FT, Undertaker, Monk)
        StrategyPrimitive.CLAIM_SAFE_ROLE: 1.4,
        StrategyPrimitive.CREATE_POISON_CONFUSION: 1.8,
    },
    RoleId.SPY: {
        StrategyPrimitive.SEEK_TRUSTED_PLAYER: 1.8,  # Infiltrate good trust networks
        StrategyPrimitive.FAKE_CONFIRMATION: 1.6,
        StrategyPrimitive.FRAME_GOOD: 1.5,
        StrategyPrimitive.CLAIM_INFO_ROLE: 1.4,
    },
    RoleId.SCARLET_WOMAN: {
        StrategyPrimitive.PROTECT_DEMON: 1.5,
        StrategyPrimitive.CLAIM_SAFE_ROLE: 1.6,
        StrategyPrimitive.RESIST_EXECUTION: 1.5,
    },
    RoleId.BARON: {
        StrategyPrimitive.BUS_MINION: 1.2,  # Baron is safe to sacrifice after setup
        StrategyPrimitive.ACCEPT_EXECUTION: 0.8,
        StrategyPrimitive.FRAME_GOOD: 1.4,
        StrategyPrimitive.CLAIM_SAFE_ROLE: 1.5,
    },
    RoleId.IMP: {
        StrategyPrimitive.KILL_INFO_ROLE: 2.2,
        StrategyPrimitive.PROTECT_DEMON: 2.5,
        StrategyPrimitive.STAR_PASS: 0.8,  # Star pass when cornered
        StrategyPrimitive.FRAME_GOOD: 1.8,
        StrategyPrimitive.CLAIM_SAFE_ROLE: 1.7,
    },
}


def get_role_modifiers(
    role: RoleId,
    ablated_primitives: set[StrategyPrimitive | str] | None = None,
) -> dict[StrategyPrimitive, float]:
    mods = dict(ROLE_PRIMITIVE_MODIFIERS.get(role, {}))
    if ablated_primitives:
        ablated_set = {p.value if hasattr(p, "value") else str(p) for p in ablated_primitives}
        for k in list(mods.keys()):
            if k.value in ablated_set:
                mods[k] = 0.0
    return mods
