"""Legal candidate action generation for Storyteller discretionary decision points."""
from __future__ import annotations

from typing import Any

from src.engine.state import GameState
from src.engine.types import Alignment, CharacterType, PlayerId, RoleId, STDecisionType
from src.roles.trouble_brewing import ROLES


def generate_legal_st_actions(
    decision_type: STDecisionType,
    state: GameState,
    actor: PlayerId | None = None,
    target: PlayerId | None = None,
    context: str | None = None,
) -> list[Any]:
    """Generate the exhaustive, strictly legal candidate action set for a decision point."""
    if decision_type == STDecisionType.DRUNK_POISON_MISINFO:
        if not actor:
            raise ValueError("Actor required for misinformation generation")
        apparent_role = state.apparent_roles[actor]

        if apparent_role == RoleId.CHEF:
            # Legal chef pairs: 0 to 3
            return [0, 1, 2, 3]

        if apparent_role == RoleId.EMPATH:
            # Legal empath numbers: 0, 1, 2
            return [0, 1, 2]

        if apparent_role == RoleId.FORTUNE_TELLER:
            # Legal FT results: True, False
            return [True, False]

        if apparent_role == RoleId.UNDERTAKER:
            # Legal undertaker roles: all in-game or script roles
            return list(ROLES.keys())

        # Fallback for general misinformation candidates
        return [True, False]

    if decision_type == STDecisionType.MAYOR_BOUNCE:
        # Candidate bounce targets: other living players
        alive_others = [p for p in state.alive_players if p != actor and p not in state.protected]
        # None means do NOT bounce; otherwise player to bounce kill to
        return [None] + alive_others

    if decision_type == STDecisionType.RECLUSE_REGISTRATION:
        # Recluse can only register as Good (self) or Evil / Minion / Demon (never Townsfolk)
        if context in ("slayer", "slayer_shot", "fortune_teller"):
            return [
                {"alignment": Alignment.GOOD, "role": RoleId.RECLUSE},
                {"alignment": Alignment.EVIL, "role": RoleId.IMP},
            ]
        if context in ("chef", "empath"):
            return [
                {"alignment": Alignment.GOOD, "role": RoleId.RECLUSE},
                {"alignment": Alignment.EVIL, "role": RoleId.RECLUSE},
            ]
        return [
            {"alignment": Alignment.GOOD, "role": RoleId.RECLUSE},
            {"alignment": Alignment.EVIL, "role": RoleId.RECLUSE},
            {"alignment": Alignment.EVIL, "role": RoleId.POISONER},
            {"alignment": Alignment.EVIL, "role": RoleId.IMP},
        ]

    if decision_type == STDecisionType.SPY_REGISTRATION:
        # Spy can only register as Evil (self) or Good / Townsfolk / Outsider (never Demon)
        if context in ("virgin", "virgin_nomination"):
            return [
                {"alignment": Alignment.EVIL, "role": RoleId.SPY},
                {"alignment": Alignment.GOOD, "role": RoleId.SOLDIER},
            ]
        if context in ("chef", "empath"):
            return [
                {"alignment": Alignment.EVIL, "role": RoleId.SPY},
                {"alignment": Alignment.GOOD, "role": RoleId.SPY},
            ]
        return [
            {"alignment": Alignment.EVIL, "role": RoleId.SPY},
            {"alignment": Alignment.GOOD, "role": RoleId.SPY},
            {"alignment": Alignment.GOOD, "role": RoleId.SOLDIER},
            {"alignment": Alignment.GOOD, "role": RoleId.BUTLER},
        ]

    return []
