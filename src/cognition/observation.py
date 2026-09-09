"""Player Observation model enforcing strict information boundaries and perceptual isolation."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.engine.state import GameState
from src.engine.types import Alignment, CharacterType, GamePhase, PlayerId, RoleId
from src.roles.trouble_brewing import ROLES


@dataclass(slots=True)
class Observation:
    observer: PlayerId
    day: int
    phase: GamePhase
    night_number: int

    # Player's perceived identity
    self_role: RoleId
    self_alignment: Alignment
    alive: bool
    ghost_vote_available: bool

    # Public game state
    roster_alive: dict[PlayerId, bool]
    deaths_public: list[dict[str, Any]]
    execution_threshold: int
    nominated_by_today: list[PlayerId]
    nominated_today: list[PlayerId]
    nominations_today: list[dict[str, Any]]
    current_nomination: dict[str, Any] | None

    # Legitimate private knowledge
    private_info: list[dict[str, Any]] = field(default_factory=list)
    evil_team_knowledge: dict[str, Any] | None = None
    butler_master: PlayerId | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "observer": self.observer,
            "day": self.day,
            "phase": self.phase.value,
            "night_number": self.night_number,
            "self_role": self.self_role.value,
            "self_alignment": self.self_alignment.value,
            "alive": self.alive,
            "ghost_vote_available": self.ghost_vote_available,
            "roster_alive": self.roster_alive,
            "deaths_public": self.deaths_public,
            "execution_threshold": self.execution_threshold,
            "nominated_by_today": self.nominated_by_today,
            "nominated_today": self.nominated_today,
            "nominations_today": self.nominations_today,
            "current_nomination": self.current_nomination,
            "private_info": self.private_info,
            "evil_team_knowledge": self.evil_team_knowledge,
            "butler_master": self.butler_master,
        }


def observe(state: GameState, player_id: PlayerId) -> Observation:
    """Project the True GameState into a strictly isolated, unprivileged Player Observation."""
    if player_id not in state.players:
        raise ValueError(f"Unknown player ID: {player_id}")

    # 1. Perceived identity: Drunk sees their fake townsfolk token!
    self_role = state.apparent_roles[player_id]
    self_alignment = state.alignments[player_id]
    alive = state.alive.get(player_id, False)
    ghost_vote_available = state.ghost_votes.get(player_id, False)

    # 2. Public information
    roster_alive = dict(state.alive)
    deaths_public = [
        {
            "player": d.player_id,
            "day": d.day,
            "phase": d.phase.value,
            "reason": d.reason.value,
        }
        for d in state.deaths
    ]
    threshold = state.execution_threshold

    # 3. Nominations & Voting state
    nominated_by = list(state.nominator_ids_today)
    nominated = list(state.nominee_ids_today)
    nominations_today = [
        {
            "nominator": n.nominator_id,
            "nominee": n.nominee_id,
            "day": n.day,
            "votes": n.final_vote_count,
            "exceeded": n.exceeded_threshold,
        }
        for n in state.nominations_today
    ]
    curr_nom = None
    if state.current_nomination:
        curr_nom = {
            "nominator": state.current_nomination.nominator_id,
            "nominee": state.current_nomination.nominee_id,
            "day": state.current_nomination.day,
            "votes": dict(state.current_nomination.votes),
        }

    # 4. Filter private events specifically intended for this observer
    visible_events = state.event_log.player_visible_events(player_id)
    private_info = [
        {"type": e.type, "day": e.day, "data": e.data}
        for e in visible_events
        if e.visibility == "private" and e.type.startswith("INFO_")
    ]

    # 5. Evil team knowledge (only if evil)
    evil_knowledge = None
    if self_alignment == Alignment.EVIL:
        true_role = state.true_roles[player_id]
        if true_role == RoleId.IMP:
            minions = [
                p for p in state.players
                if ROLES[state.true_roles[p]].type == CharacterType.MINION
            ]
            evil_knowledge = {
                "role": "demon",
                "minions": minions,
                "bluffs": [b.value for b in state.imp_bluffs],
            }
        elif ROLES[true_role].type == CharacterType.MINION:
            imp = next(
                (p for p in state.players if state.true_roles[p] == RoleId.IMP),
                None,
            )
            other_minions = [
                p for p in state.players
                if ROLES[state.true_roles[p]].type == CharacterType.MINION and p != player_id
            ]
            evil_knowledge = {
                "role": "minion",
                "demon": imp,
                "other_minions": other_minions,
            }

    # 6. Butler master
    butler_master = state.butler_masters.get(player_id)

    return Observation(
        observer=player_id,
        day=state.day,
        phase=state.phase,
        night_number=state.night_number,
        self_role=self_role,
        self_alignment=self_alignment,
        alive=alive,
        ghost_vote_available=ghost_vote_available,
        roster_alive=roster_alive,
        deaths_public=deaths_public,
        execution_threshold=threshold,
        nominated_by_today=nominated_by,
        nominated_today=nominated,
        nominations_today=nominations_today,
        current_nomination=curr_nom,
        private_info=private_info,
        evil_team_knowledge=evil_knowledge,
        butler_master=butler_master,
    )
