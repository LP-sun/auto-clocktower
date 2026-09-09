"""GameState dataclass, OngoingEffect lifecycle, and runtime records."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from src.engine.events import EventLog
from src.engine.types import Alignment, DeathReason, GamePhase, PlayerId, RoleId


@dataclass(slots=True)
class DeathRecord:
    death_id: int
    player_id: PlayerId
    day: int
    phase: GamePhase
    reason: DeathReason
    alive_count_before: int
    alive_count_after: int = 0
    cause: str = ""
    source: PlayerId | None = None
    was_poisoned_or_drunk: bool = False



@dataclass(slots=True)
class OngoingEffect:
    """Generic lifecycle model for ongoing effects (poison, monk protection, drunk)."""
    effect_id: int
    effect_type: str  # "POISON", "PROTECTION", "DRUNK"
    source_player: PlayerId | None
    target_player: PlayerId
    expires_at: str  # "dusk", "night_start", "permanent"
    is_active: bool = True


@dataclass(slots=True)
class NominationRecord:
    nominator_id: PlayerId
    nominee_id: PlayerId
    day: int
    votes: dict[PlayerId, bool] = field(default_factory=dict)
    final_vote_count: int = 0
    exceeded_threshold: bool = False


@dataclass(slots=True)
class GameState:
    seed: int
    player_count: int
    players: list[PlayerId]
    day: int = 0
    phase: GamePhase = GamePhase.SETUP
    night_number: int = 0

    # True Grimoire
    true_roles: dict[PlayerId, RoleId] = field(default_factory=dict)
    apparent_roles: dict[PlayerId, RoleId] = field(default_factory=dict)
    alignments: dict[PlayerId, Alignment] = field(default_factory=dict)
    alive: dict[PlayerId, bool] = field(default_factory=dict)
    ghost_votes: dict[PlayerId, bool] = field(default_factory=dict)

    # Generic Ongoing Effects Registry
    ongoing_effects: list[OngoingEffect] = field(default_factory=list)
    _next_effect_id: int = 1

    # Status modifiers & tags
    drunk: set[PlayerId] = field(default_factory=set)
    ability_used: set[PlayerId] = field(default_factory=set)  # Virgin proc, Slayer shot
    red_herring: PlayerId | None = None
    imp_bluffs: list[RoleId] = field(default_factory=list)
    drunk_fake_role: RoleId | None = None

    # Role persistent states
    butler_masters: dict[PlayerId, PlayerId] = field(default_factory=dict)

    # Day & Execution semantics
    executed_today: PlayerId | None = None  # At most one execution per day
    last_executed_player_yesterday: PlayerId | None = None  # For Undertaker

    # Day / Nomination states
    nominations_today: list[NominationRecord] = field(default_factory=list)
    nominator_ids_today: set[PlayerId] = field(default_factory=set)
    nominee_ids_today: set[PlayerId] = field(default_factory=set)
    current_nomination: NominationRecord | None = None

    # Deaths & Results
    deaths: list[DeathRecord] = field(default_factory=list)
    winner: Alignment | None = None
    end_reason: str | None = None

    # Event Sourcing
    event_log: EventLog = field(default_factory=EventLog)

    @property
    def alive_players(self) -> list[PlayerId]:
        return [p for p in self.players if self.alive.get(p, False)]

    @property
    def dead_players(self) -> list[PlayerId]:
        return [p for p in self.players if not self.alive.get(p, False)]

    @property
    def alive_count(self) -> int:
        return len(self.alive_players)

    @property
    def execution_threshold(self) -> int:
        """Standard execution requires at least half of living players: ceil(alive / 2)."""
        count = self.alive_count
        if count <= 0:
            return 0
        return math.ceil(count / 2)

    @property
    def poisoned(self) -> set[PlayerId]:
        """Dynamically derived from active ongoing POISON effects."""
        return {
            e.target_player
            for e in self.ongoing_effects
            if e.is_active and e.effect_type == "POISON"
        }

    @property
    def protected(self) -> set[PlayerId]:
        """Dynamically derived from active ongoing PROTECTION effects."""
        return {
            e.target_player
            for e in self.ongoing_effects
            if e.is_active and e.effect_type == "PROTECTION"
        }

    def is_poisoned(self, player_id: PlayerId) -> bool:
        return player_id in self.poisoned

    def is_protected(self, player_id: PlayerId) -> bool:
        return player_id in self.protected

    def add_ongoing_effect(
        self,
        effect_type: str,
        source_player: PlayerId | None,
        target_player: PlayerId,
        expires_at: str,
    ) -> OngoingEffect:
        effect = OngoingEffect(
            effect_id=self._next_effect_id,
            effect_type=effect_type,
            source_player=source_player,
            target_player=target_player,
            expires_at=expires_at,
            is_active=True,
        )
        self._next_effect_id += 1
        self.ongoing_effects.append(effect)
        return effect

    def cease_effects_from_source(self, source_player: PlayerId) -> list[OngoingEffect]:
        """Generic ongoing effect lifecycle: when source ability ceases (e.g. death or drunk), deactivate effects."""
        ceased = []
        for e in self.ongoing_effects:
            if e.is_active and e.source_player == source_player:
                e.is_active = False
                ceased.append(e)
                self.event_log.append(
                    day=self.day,
                    phase=self.phase,
                    event_type="EFFECT_CEASED",
                    actor=source_player,
                    target=e.target_player,
                    data={"effect_type": e.effect_type, "reason": "source_ability_ceased"},
                    visibility="private",
                )
        return ceased

    def expire_ongoing_effects(self, expiry_trigger: str) -> None:
        """Deactivate ongoing effects that expire at this trigger (e.g. 'dusk' or 'night_start')."""
        for e in self.ongoing_effects:
            if e.is_active and e.expires_at == expiry_trigger:
                e.is_active = False

    def is_poisoned_or_drunk(self, player_id: PlayerId) -> bool:
        return (player_id in self.poisoned) or (player_id in self.drunk)

    def is_evil(self, player_id: PlayerId) -> bool:
        return self.alignments.get(player_id) == Alignment.EVIL

    def kill_player(
        self,
        player_id: PlayerId,
        reason: DeathReason,
        source: PlayerId | None = None,
    ) -> DeathRecord:
        """Mark a player as dead and record the canonical death event with unique death_id."""
        if not self.alive.get(player_id, False):
            raise ValueError(f"Player {player_id} is already dead.")

        alive_before = self.alive_count
        was_pd = self.is_poisoned_or_drunk(player_id)
        self.alive[player_id] = False
        alive_after = self.alive_count
        death_id = len(self.deaths) + 1

        record = DeathRecord(
            death_id=death_id,
            player_id=player_id,
            day=self.day,
            phase=self.phase,
            reason=reason,
            alive_count_before=alive_before,
            alive_count_after=alive_after,
            cause=reason.value,
            source=source,
            was_poisoned_or_drunk=was_pd,
        )
        self.deaths.append(record)

        self.event_log.append(
            day=self.day,
            phase=self.phase,
            event_type="DEATH",
            actor=player_id,
            data={
                "death_id": death_id,
                "player_id": player_id,
                "reason": reason.value,
                "cause": reason.value,
                "source": source,
                "alive_before": alive_before,
                "alive_after": alive_after,
                "alive_count_before": alive_before,
                "alive_count_after": alive_after,
            },
            visibility="public",
        )

        # Ongoing effect lifecycle: when source player dies, their active effects cease immediately!
        self.cease_effects_from_source(player_id)

        return record

