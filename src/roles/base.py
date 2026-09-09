"""Base classes and night order definitions for Blood on the Clocktower roles."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from src.engine.types import Alignment, CharacterType, RoleId


@dataclass(frozen=True, slots=True)
class RoleDefinition:
    id: RoleId
    type: CharacterType
    name_zh: str
    name_en: str
    description_zh: str
    first_night_order: int | None  # None if does not wake on first night
    other_night_order: int | None  # None if does not wake on other nights
    is_info_role: bool = False
    is_ongoing_info: bool = False
    is_protection_role: bool = False
    is_once_per_game: bool = False

    @property
    def alignment(self) -> Alignment:
        if self.type in (CharacterType.TOWNSFOLK, CharacterType.OUTSIDER):
            return Alignment.GOOD
        return Alignment.EVIL


# First Night Wake Order (Trouble Brewing)
FIRST_NIGHT_ORDER: Sequence[RoleId] = (
    RoleId.POISONER,
    RoleId.SPY,
    RoleId.WASHERWOMAN,
    RoleId.LIBRARIAN,
    RoleId.INVESTIGATOR,
    RoleId.CHEF,
    RoleId.EMPATH,
    RoleId.FORTUNE_TELLER,
    RoleId.BUTLER,
)

# Other Nights Wake Order (Trouble Brewing)
OTHER_NIGHT_ORDER: Sequence[RoleId] = (
    RoleId.POISONER,
    RoleId.MONK,
    RoleId.SPY,
    RoleId.SCARLET_WOMAN,
    RoleId.IMP,
    RoleId.RAVENKEEPER,
    RoleId.UNDERTAKER,
    RoleId.EMPATH,
    RoleId.FORTUNE_TELLER,
    RoleId.BUTLER,
)
