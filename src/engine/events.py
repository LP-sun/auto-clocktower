"""Structured game event models and event log for deterministic replay and audit."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from src.engine.types import GamePhase, PlayerId


@dataclass(slots=True)
class GameEvent:
    event_id: int
    day: int
    phase: GamePhase
    type: str
    actor: PlayerId | None = None
    target: PlayerId | None = None
    data: dict[str, Any] = field(default_factory=dict)
    visibility: str = "public"  # "public" or "private"
    audience: list[PlayerId] | None = None  # None for public events

    def to_dict(self) -> dict[str, Any]:
        res = asdict(self)
        res["phase"] = self.phase.value
        return res


class EventLog:
    """Sequential append-only log of game events."""

    def __init__(self) -> None:
        self._events: list[GameEvent] = []
        self._next_id: int = 1

    def append(
        self,
        day: int,
        phase: GamePhase,
        event_type: str,
        actor: PlayerId | None = None,
        target: PlayerId | None = None,
        data: dict[str, Any] | None = None,
        visibility: str = "public",
        audience: list[PlayerId] | None = None,
    ) -> GameEvent:
        event = GameEvent(
            event_id=self._next_id,
            day=day,
            phase=phase,
            type=event_type,
            actor=actor,
            target=target,
            data=data or {},
            visibility=visibility,
            audience=audience,
        )
        self._events.append(event)
        self._next_id += 1
        return event

    @property
    def events(self) -> list[GameEvent]:
        return self._events

    def __len__(self) -> int:
        return len(self._events)

    def __iter__(self):
        return iter(self._events)


    def to_list(self) -> list[dict[str, Any]]:
        return [e.to_dict() for e in self._events]

    def get_events_for_player(self, player_id: PlayerId) -> list[GameEvent]:
        """Return all events visible to player (public or player is in audience)."""
        return [
            e for e in self._events
            if e.visibility == "public" or (e.audience is not None and player_id in e.audience)
        ]

    def player_visible_events(self, player_id: PlayerId) -> list[GameEvent]:
        """Filter events visible to a specific player for observation projection."""
        return [
            e
            for e in self._events
            if e.visibility == "public" or (e.audience is not None and player_id in e.audience)
        ]
