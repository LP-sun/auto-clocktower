"""Finite working memory manager with exponential decay and importance weighting."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum, unique
from typing import Any

from src.engine.types import PlayerId


@unique
class MemoryCategory(str, Enum):
    HARD_ROLE_INFO = "HARD_ROLE_INFO"      # Verified tokens, night info, execution reveals
    PRIVATE_CLAIM = "PRIVATE_CLAIM"        # 1-on-1 whisper claims
    PUBLIC_CLAIM = "PUBLIC_CLAIM"          # Public role claims and announcements
    VOTE_OBSERVATION = "VOTE_OBSERVATION"  # Who voted for whom on the block
    SOCIAL_OPINION = "SOCIAL_OPINION"      # General chatter, opinions, hunches


CATEGORY_BASE_DECAY: dict[str, float] = {
    MemoryCategory.HARD_ROLE_INFO.value: 0.01,
    MemoryCategory.PRIVATE_CLAIM.value: 0.05,
    MemoryCategory.PUBLIC_CLAIM.value: 0.08,
    MemoryCategory.VOTE_OBSERVATION.value: 0.12,
    MemoryCategory.SOCIAL_OPINION.value: 0.25,
}


@dataclass(slots=True)
class MemoryItem:
    item_id: int
    day: int
    type: str
    source: PlayerId | str
    data: dict[str, Any]
    category: str = MemoryCategory.SOCIAL_OPINION.value
    importance: float = 1.0  # [0.1, 2.0]
    initial_strength: float = 1.0
    decay_rate: float = 0.15  # lambda in e^(-lambda * delta_t)

    def current_strength(self, current_day: int) -> float:
        delta_t = max(0, current_day - self.day)
        return self.initial_strength * self.importance * math.exp(-self.decay_rate * delta_t)


class FiniteMemoryManager:
    """Manages working memory items subject to finite capacity, category-dependent decay, and retrieval."""

    def __init__(self, skill_factor: float = 1.0, max_items: int = 30) -> None:
        self.skill_factor = max(0.1, min(2.0, skill_factor))
        self.max_items = max_items
        self._items: list[MemoryItem] = []
        self._next_id = 1

    def store(
        self,
        day: int,
        item_type: str,
        source: PlayerId | str,
        data: dict[str, Any],
        importance: float = 1.0,
        category: MemoryCategory | str | None = None,
    ) -> MemoryItem:
        cat_str = category.value if isinstance(category, MemoryCategory) else category
        if not cat_str:
            if item_type.startswith("INFO_") or item_type in ("VIRGIN_PROC", "SLAYER_SHOT", "EXECUTION_REVEAL", "butler_master"):
                cat_str = MemoryCategory.HARD_ROLE_INFO.value
            elif "private_claim" in item_type.lower():
                cat_str = MemoryCategory.PRIVATE_CLAIM.value
            elif "claim" in item_type.lower():
                cat_str = MemoryCategory.PUBLIC_CLAIM.value
            elif "vote" in item_type.lower() or "nomination" in item_type.lower():
                cat_str = MemoryCategory.VOTE_OBSERVATION.value
            else:
                cat_str = MemoryCategory.SOCIAL_OPINION.value

        base_decay = CATEGORY_BASE_DECAY.get(cat_str, 0.15)
        # Skill factor modulates decay: higher skill = lower decay
        decay = base_decay / self.skill_factor

        # Hard role info receives high base importance
        eff_importance = max(importance, 1.8) if cat_str == MemoryCategory.HARD_ROLE_INFO.value else importance

        item = MemoryItem(
            item_id=self._next_id,
            day=day,
            type=item_type,
            source=source,
            data=data,
            category=cat_str,
            importance=eff_importance,
            decay_rate=decay,
        )
        self._next_id += 1
        self._items.append(item)
        self.prune(day)
        return item


    def prune(self, current_day: int) -> None:
        """Drop items whose current strength falls below threshold or exceeds capacity."""
        # Sort by current strength descending
        self._items.sort(key=lambda x: x.current_strength(current_day), reverse=True)
        # Keep top max_items, drop items with strength < 0.15 (unless critical importance >= 1.8)
        self._items = [
            it for it in self._items[:self.max_items]
            if it.current_strength(current_day) >= 0.15 or it.importance >= 1.8
        ]

    def retrieve(self, current_day: int, item_type: str | None = None) -> list[MemoryItem]:
        self.prune(current_day)
        if item_type is None:
            return list(self._items)
        return [it for it in self._items if it.type == item_type]
