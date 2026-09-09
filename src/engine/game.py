"""Authoritative game engine loop, role abilities resolution, and win condition checking."""
from __future__ import annotations

import random
from typing import Any, Callable

from src.engine.events import EventLog
from src.engine.setup import SetupResult, generate_setup
from src.engine.state import DeathRecord, GameState, NominationRecord
from src.engine.types import (
    ActionType,
    Alignment,
    CharacterType,
    DeathReason,
    GamePhase,
    PlayerId,
    RoleId,
    STDecisionType,
)
from src.roles.trouble_brewing import ROLES


def get_adjacent_alive_neighbors(state: GameState, player_id: PlayerId) -> tuple[PlayerId, PlayerId]:
    """Get the clockwise and counter-clockwise living neighbors of a player."""
    alive = state.alive_players
    if len(alive) <= 1:
        raise ValueError("Cannot find neighbors with <= 1 alive player")
    if player_id not in alive:
        idx = state.players.index(player_id)
        n = len(state.players)
        left: PlayerId | None = None
        for step in range(1, n):
            candidate = state.players[(idx - step) % n]
            if state.alive[candidate]:
                left = candidate
                break
        right: PlayerId | None = None
        for step in range(1, n):
            candidate = state.players[(idx + step) % n]
            if state.alive[candidate]:
                right = candidate
                break
        assert left is not None and right is not None
        return left, right

    idx = alive.index(player_id)
    left = alive[(idx - 1) % len(alive)]
    right = alive[(idx + 1) % len(alive)]
    return left, right


def check_win_conditions(state: GameState) -> Alignment | None:
    """Evaluate victory conditions according to Trouble Brewing authoritative rules."""
    if state.winner is not None:
        return state.winner

    alive_demons = [
        p for p in state.alive_players if state.true_roles[p] == RoleId.IMP
    ]

    # 1. Demon dead condition
    if not alive_demons:
        # Check Scarlet Woman promotion using pre-death context from the latest death record
        sw_player = next(
            (p for p in state.alive_players if state.true_roles[p] == RoleId.SCARLET_WOMAN),
            None,
        )
        last_demon_death = next(
            (d for d in reversed(state.deaths) if state.true_roles.get(d.player_id) == RoleId.IMP),
            None,
        )
        alive_before = last_demon_death.alive_count_before if last_demon_death else state.alive_count + 1

        if sw_player and alive_before >= 5 and not state.is_poisoned_or_drunk(sw_player):
            state.true_roles[sw_player] = RoleId.IMP
            state.apparent_roles[sw_player] = RoleId.IMP
            state.event_log.append(
                day=state.day,
                phase=state.phase,
                event_type="SCARLET_WOMAN_PROMOTED",
                actor=sw_player,
                data={"new_role": RoleId.IMP.value, "alive_before": alive_before},
                visibility="public",
            )
            alive_demons = [sw_player]
        else:
            state.winner = Alignment.GOOD
            state.end_reason = "imp_dead"
            state.phase = GamePhase.ENDED
            state.event_log.append(
                day=state.day,
                phase=state.phase,
                event_type="GAME_OVER",
                data={"winner": Alignment.GOOD.value, "reason": state.end_reason},
                visibility="public",
            )
            return Alignment.GOOD

    # 2. Evil win condition: only 2 players left alive (with living demon)
    if state.alive_count <= 2 and alive_demons:
        state.winner = Alignment.EVIL
        state.end_reason = "demon_in_final_two"
        state.phase = GamePhase.ENDED
        state.event_log.append(
            day=state.day,
            phase=state.phase,
            event_type="GAME_OVER",
            data={"winner": Alignment.EVIL.value, "reason": state.end_reason},
            visibility="public",
        )
        return Alignment.EVIL

    return None


class ClocktowerEngine:
    """Deterministic game engine running Trouble Brewing rules with OngoingEffect lifecycle."""

    def __init__(self, state: GameState, rng_seed: int | None = None) -> None:
        self.state = state
        self.rng = random.Random(rng_seed or state.seed)

    @property
    def events(self) -> EventLog:
        return self.state.event_log

    def handle_slayer_shot(self, slayer_id: PlayerId, target_id: PlayerId, st_policy: Any = None) -> bool:
        return self.use_slayer_ability(slayer_id, target_id, st_policy=st_policy)

    @classmethod
    def create(
        cls,
        player_count: int = 12,
        seed: int = 42,
        custom_setup: SetupResult | None = None,
    ) -> ClocktowerEngine:
        setup = custom_setup or generate_setup(player_count=player_count, seed=seed)
        event_log = EventLog()

        state = GameState(
            seed=seed,
            player_count=len(setup.players),
            players=setup.players,
            day=0,
            phase=GamePhase.SETUP,
            true_roles=setup.true_roles,
            apparent_roles=setup.apparent_roles,
            alignments=setup.alignments,
            alive={p: True for p in setup.players},
            ghost_votes={p: False for p in setup.players},
            drunk_fake_role=setup.drunk_fake_role,
            red_herring=setup.red_herring,
            imp_bluffs=setup.imp_bluffs,
            event_log=event_log,
        )

        drunk_player = next((p for p, r in state.true_roles.items() if r == RoleId.DRUNK), None)
        if drunk_player:
            state.drunk.add(drunk_player)

        event_log.append(
            day=0,
            phase=GamePhase.SETUP,
            event_type="GAME_START",
            data={
                "player_count": state.player_count,
                "players": state.players,
                "red_herring": state.red_herring,
                "imp_bluffs": [b.value for b in state.imp_bluffs],
                "drunk_fake_role": state.drunk_fake_role.value if state.drunk_fake_role else None,
            },
            visibility="private",
            audience=None,
        )

        return cls(state, rng_seed=seed)

    # ------------------ FIRST NIGHT ------------------
    def run_first_night(
        self,
        poisoner_target: PlayerId | None = None,
        fortune_teller_targets: tuple[PlayerId, PlayerId] | None = None,
        butler_target: PlayerId | None = None,
        custom_st_info: dict[PlayerId, dict] | None = None,
        st_policy: Any = None,
    ) -> None:
        """Resolve all first night actions and deliver initial private information."""
        s = self.state
        s.day = 0
        s.night_number = 1
        s.phase = GamePhase.FIRST_NIGHT

        # 1. Poisoner: ongoing effect expires at dusk of next day
        poisoner = next((p for p in s.alive_players if s.true_roles[p] == RoleId.POISONER), None)
        if poisoner and poisoner_target and poisoner_target in s.players:
            if not s.is_poisoned_or_drunk(poisoner):
                s.add_ongoing_effect("POISON", source_player=poisoner, target_player=poisoner_target, expires_at="dusk")
            s.event_log.append(
                day=0,
                phase=s.phase,
                event_type="NIGHT_ACTION",
                actor=poisoner,
                target=poisoner_target,
                data={"role": RoleId.POISONER.value},
                visibility="private",
                audience=[poisoner],
            )

        # 2. Demon & Minion info
        imp = next((p for p in s.players if s.true_roles[p] == RoleId.IMP), None)
        minions = [p for p in s.players if ROLES[s.true_roles[p]].type == CharacterType.MINION]
        if imp:
            s.event_log.append(
                day=0,
                phase=s.phase,
                event_type="DEMON_INFO",
                actor=imp,
                data={"minions": minions, "bluffs": [b.value for b in s.imp_bluffs]},
                visibility="private",
                audience=[imp],
            )
        for m in minions:
            s.event_log.append(
                day=0,
                phase=s.phase,
                event_type="MINION_INFO",
                actor=m,
                data={"demon": imp, "other_minions": [x for x in minions if x != m]},
                visibility="private",
                audience=[m],
            )

        # 3. Spy
        spy = next((p for p in s.alive_players if s.true_roles[p] == RoleId.SPY), None)
        if spy:
            s.event_log.append(
                day=0,
                phase=s.phase,
                event_type="SPY_GRIMOIRE",
                actor=spy,
                data={"grimoire": {p: s.true_roles[p].value for p in s.players}},
                visibility="private",
                audience=[spy],
            )

        # 4. Washerwoman
        ww = next((p for p in s.alive_players if s.apparent_roles[p] == RoleId.WASHERWOMAN), None)
        if ww:
            self._resolve_washerwoman(ww, custom_st_info, st_policy)

        # 5. Librarian
        lib = next((p for p in s.alive_players if s.apparent_roles[p] == RoleId.LIBRARIAN), None)
        if lib:
            self._resolve_librarian(lib, custom_st_info, st_policy)

        # 6. Investigator
        inv = next((p for p in s.alive_players if s.apparent_roles[p] == RoleId.INVESTIGATOR), None)
        if inv:
            self._resolve_investigator(inv, custom_st_info, st_policy)

        # 7. Chef
        chef = next((p for p in s.alive_players if s.apparent_roles[p] == RoleId.CHEF), None)
        if chef:
            self._resolve_chef(chef, custom_st_info, st_policy)

        # 8. Empath
        empath = next((p for p in s.alive_players if s.apparent_roles[p] == RoleId.EMPATH), None)
        if empath:
            self._resolve_empath(empath, custom_st_info, st_policy)

        # 9. Fortune Teller
        ft = next((p for p in s.alive_players if s.apparent_roles[p] == RoleId.FORTUNE_TELLER), None)
        if ft and fortune_teller_targets:
            self._resolve_fortune_teller(ft, fortune_teller_targets, custom_st_info, st_policy)

        # 10. Butler
        butler = next((p for p in s.alive_players if s.true_roles[p] == RoleId.BUTLER), None)
        if butler and butler_target and butler_target != butler and butler_target in s.players:
            s.butler_masters[butler] = butler_target
            s.event_log.append(
                day=0,
                phase=s.phase,
                event_type="BUTLER_CHOOSE_MASTER",
                actor=butler,
                target=butler_target,
                visibility="private",
                audience=[butler],
            )

    # ------------------ SUBSEQUENT NIGHTS ------------------
    def run_night(
        self,
        poisoner_target: PlayerId | None = None,
        monk_target: PlayerId | None = None,
        imp_target: PlayerId | None = None,
        demon_target: PlayerId | None = None,
        ravenkeeper_target: PlayerId | None = None,
        fortune_teller_targets: tuple[PlayerId, PlayerId] | None = None,
        butler_target: PlayerId | None = None,
        mayor_bounce_target: PlayerId | None = None,
        custom_st_info: dict[PlayerId, dict] | None = None,
        st_policy: Any = None,
    ) -> list[PlayerId]:
        """Resolve other night actions in standard TB sequence. Returns players killed during the night."""
        s = self.state
        s.night_number += 1
        s.phase = GamePhase.NIGHT

        # Expire previous protection effects that lasted until dawn
        s.expire_ongoing_effects("dawn")

        # 1. Poisoner
        poisoner = next((p for p in s.alive_players if s.true_roles[p] == RoleId.POISONER), None)
        if poisoner and poisoner_target and poisoner_target in s.players:
            if not s.is_poisoned_or_drunk(poisoner):
                s.add_ongoing_effect("POISON", source_player=poisoner, target_player=poisoner_target, expires_at="dusk")
            s.event_log.append(
                day=s.day,
                phase=s.phase,
                event_type="NIGHT_ACTION",
                actor=poisoner,
                target=poisoner_target,
                data={"role": RoleId.POISONER.value},
                visibility="private",
                audience=[poisoner],
            )

        # 2. Monk: cannot protect self, expires at dawn
        monk = next((p for p in s.alive_players if s.true_roles[p] == RoleId.MONK), None)
        if monk and monk_target and monk_target != monk and monk_target in s.alive_players:
            if not s.is_poisoned_or_drunk(monk):
                s.add_ongoing_effect("PROTECTION", source_player=monk, target_player=monk_target, expires_at="dawn")
            s.event_log.append(
                day=s.day,
                phase=s.phase,
                event_type="NIGHT_ACTION",
                actor=monk,
                target=monk_target,
                data={"role": RoleId.MONK.value},
                visibility="private",
                audience=[monk],
            )

        # 3. Spy
        spy = next((p for p in s.alive_players if s.true_roles[p] == RoleId.SPY), None)
        if spy:
            s.event_log.append(
                day=s.day,
                phase=s.phase,
                event_type="SPY_GRIMOIRE",
                actor=spy,
                data={"grimoire": {p: s.true_roles[p].value for p in s.players}},
                visibility="private",
                audience=[spy],
            )

        # 4. Imp kill & Star-Pass
        night_killed: list[PlayerId] = []
        actual_demon_target = imp_target if imp_target is not None else demon_target
        imp = next((p for p in s.alive_players if s.true_roles[p] == RoleId.IMP), None)
        if imp and actual_demon_target:
            if actual_demon_target == imp:
                # Star pass!
                s.kill_player(imp, DeathReason.STAR_PASS)
                night_killed.append(imp)
                minion_candidates = [
                    p for p in s.alive_players
                    if ROLES[s.true_roles[p]].type == CharacterType.MINION
                ]
                if minion_candidates:
                    # ST chooses which minion becomes Imp; Scarlet Woman preferred if present
                    new_imp = (
                        next((p for p in minion_candidates if s.true_roles[p] == RoleId.SCARLET_WOMAN), None)
                        or minion_candidates[0]
                    )
                    s.true_roles[new_imp] = RoleId.IMP
                    s.apparent_roles[new_imp] = RoleId.IMP
                    s.event_log.append(
                        day=s.day,
                        phase=s.phase,
                        event_type="STAR_PASS_PROMOTION",
                        actor=new_imp,
                        data={"new_imp": new_imp},
                        visibility="private",
                        audience=[new_imp],
                    )
            else:
                chosen_victim = actual_demon_target
                # Mayor bounce check
                if (
                    chosen_victim in s.alive_players
                    and s.true_roles[chosen_victim] == RoleId.MAYOR
                    and not s.is_poisoned_or_drunk(chosen_victim)
                ):
                    # Query ST policy or passed target
                    actual_bounce = mayor_bounce_target
                    if st_policy and actual_bounce is None:
                        actual_bounce = st_policy.decide(STDecisionType.MAYOR_BOUNCE, s, actor=chosen_victim)
                    if actual_bounce and actual_bounce in s.alive_players and actual_bounce != chosen_victim:
                        chosen_victim = actual_bounce

                # Protection / Soldier immunity check
                is_protected = chosen_victim in s.protected
                is_soldier = (
                    s.true_roles.get(chosen_victim) == RoleId.SOLDIER
                    and not s.is_poisoned_or_drunk(chosen_victim)
                )

                if not is_protected and not is_soldier and chosen_victim in s.alive_players:
                    s.kill_player(chosen_victim, DeathReason.DEMON_KILL)
                    night_killed.append(chosen_victim)

        # 5. Ravenkeeper (wakes ONLY if killed tonight)
        for dead_id in night_killed:
            if s.true_roles[dead_id] == RoleId.RAVENKEEPER and ravenkeeper_target:
                self._resolve_ravenkeeper(dead_id, ravenkeeper_target, custom_st_info, st_policy)

        # 6. Undertaker (learns yesterday's executed player; NO WAKE if nobody executed yesterday)
        undertaker = next((p for p in s.alive_players if s.apparent_roles[p] == RoleId.UNDERTAKER), None)
        if undertaker:
            last_exec = s.executed_today or s.last_executed_player_yesterday
            if last_exec is not None:
                self._resolve_undertaker(undertaker, custom_st_info, st_policy)
            # If strictly None: no wake / no event!

        # 7. Empath
        empath = next((p for p in s.alive_players if s.apparent_roles[p] == RoleId.EMPATH), None)
        if empath:
            self._resolve_empath(empath, custom_st_info, st_policy)

        # 8. Fortune Teller
        ft = next((p for p in s.alive_players if s.apparent_roles[p] == RoleId.FORTUNE_TELLER), None)
        if ft and fortune_teller_targets:
            self._resolve_fortune_teller(ft, fortune_teller_targets, custom_st_info, st_policy)

        # 9. Butler
        butler = next((p for p in s.alive_players if s.true_roles[p] == RoleId.BUTLER), None)
        if butler and butler_target and butler_target != butler and butler_target in s.players:
            s.butler_masters[butler] = butler_target
            s.event_log.append(
                day=s.day,
                phase=s.phase,
                event_type="BUTLER_CHOOSE_MASTER",
                actor=butler,
                target=butler_target,
                visibility="private",
                audience=[butler],
            )

        check_win_conditions(s)
        return night_killed

    # ------------------ DAY PHASE ------------------
    def start_day(self) -> None:
        """Dawn announcement of deaths, updating yesterday execution state, and starting day."""
        s = self.state
        s.day += 1
        s.phase = GamePhase.DAWN

        # Expire effects that last until dawn (e.g. Monk protection)
        s.expire_ongoing_effects("dawn")

        # Advance executed_today into last_executed_player_yesterday for the new day
        s.last_executed_player_yesterday = s.executed_today
        s.executed_today = None

        # Clear day temporary records
        s.nominations_today.clear()
        s.nominator_ids_today.clear()
        s.nominee_ids_today.clear()
        s.current_nomination = None

        s.event_log.append(
            day=s.day,
            phase=s.phase,
            event_type="DAWN",
            data={
                "alive_players": s.alive_players,
                "execution_threshold": s.execution_threshold,
                "last_executed_yesterday": s.last_executed_player_yesterday,
            },
            visibility="public",
        )

        check_win_conditions(s)
        if s.winner is None:
            s.phase = GamePhase.DAY_PUBLIC

    def use_slayer_ability(self, slayer_id: PlayerId, target_id: PlayerId, st_policy: Any = None) -> bool:
        """Publicly attempt a Slayer shot. Returns True if target was demon (or Recluse registered as demon) and died."""
        s = self.state
        if slayer_id not in s.alive_players:
            raise ValueError(f"Slayer {slayer_id} is not alive.")
        if slayer_id in s.ability_used:
            raise ValueError(f"Slayer {slayer_id} already used ability.")
        if target_id not in s.alive_players:
            raise ValueError(f"Target {target_id} is not alive.")

        s.ability_used.add(slayer_id)
        is_poisoned = s.is_poisoned_or_drunk(slayer_id)

        target_true_role = s.true_roles[target_id]
        is_target_demon = target_true_role == RoleId.IMP

        # Recluse registration interaction: Recluse can register as Demon to Slayer
        if target_true_role == RoleId.RECLUSE and not is_target_demon:
            if st_policy:
                reg = st_policy.decide(STDecisionType.RECLUSE_REGISTRATION, s, actor=target_id, context="slayer")
                if reg and reg.get("role") == RoleId.IMP:
                    is_target_demon = True
                    s.event_log.append(
                        day=s.day,
                        phase=s.phase,
                        event_type="ST_REGISTRATION",
                        actor=target_id,
                        data={"character": "recluse", "registered_as": "imp", "context": "slayer_shot"},
                        visibility="private",
                    )

        shot_success = is_target_demon and not is_poisoned
        s.event_log.append(
            day=s.day,
            phase=s.phase,
            event_type="SLAYER_SHOT",
            actor=slayer_id,
            target=target_id,
            data={"success": shot_success},
            visibility="public",
        )

        if shot_success:
            s.kill_player(target_id, DeathReason.SLAYER_SHOT)
            check_win_conditions(s)

        return shot_success

    def handle_nomination(
        self,
        nominator_id: PlayerId,
        nominee_id: PlayerId,
        st_policy: Any = None,
    ) -> NominationRecord | None:
        """Register a nomination. Checks Virgin execution immediately. Returns NominationRecord or None if Virgin proc ends day."""
        s = self.state
        if s.executed_today is not None:
            raise ValueError(f"An execution ({s.executed_today}) has already occurred today. Nominations closed.")
        if nominator_id not in s.alive_players:
            raise ValueError(f"Nominator {nominator_id} must be alive.")
        if nominator_id in s.nominator_ids_today:
            raise ValueError(f"Player {nominator_id} already nominated today.")
        if nominee_id in s.nominee_ids_today:
            raise ValueError(f"Player {nominee_id} already nominated today.")

        s.nominator_ids_today.add(nominator_id)
        s.nominee_ids_today.add(nominee_id)

        rec = NominationRecord(
            nominator_id=nominator_id,
            nominee_id=nominee_id,
            day=s.day,
        )
        s.current_nomination = rec
        s.nominations_today.append(rec)

        s.event_log.append(
            day=s.day,
            phase=s.phase,
            event_type="NOMINATION",
            actor=nominator_id,
            target=nominee_id,
            visibility="public",
        )

        # Check Virgin proc!
        if (
            s.true_roles.get(nominee_id) == RoleId.VIRGIN
            and nominee_id not in s.ability_used
        ):
            s.ability_used.add(nominee_id)
            nominator_role = s.true_roles[nominator_id]
            is_nominator_townsfolk = (
                ROLES[nominator_role].type == CharacterType.TOWNSFOLK
            )

            # Spy registration interaction: Spy may register as Townsfolk to Virgin
            if nominator_role == RoleId.SPY and not is_nominator_townsfolk:
                if st_policy:
                    reg = st_policy.decide(STDecisionType.SPY_REGISTRATION, s, actor=nominator_id, context="virgin")
                    if reg and reg.get("alignment") == Alignment.GOOD:
                        is_nominator_townsfolk = True
                        s.event_log.append(
                            day=s.day,
                            phase=s.phase,
                            event_type="ST_REGISTRATION",
                            actor=nominator_id,
                            data={"character": "spy", "registered_as": "townsfolk", "context": "virgin_nomination"},
                            visibility="private",
                        )

            virgin_not_poisoned = not s.is_poisoned_or_drunk(nominee_id)

            if is_nominator_townsfolk and virgin_not_poisoned:
                # Nominator is executed immediately by Virgin ability!
                s.executed_today = nominator_id
                s.kill_player(nominator_id, DeathReason.VIRGIN_PROC)
                s.ghost_votes[nominator_id] = True
                s.event_log.append(
                    day=s.day,
                    phase=s.phase,
                    event_type="VIRGIN_PROC",
                    actor=nominee_id,
                    target=nominator_id,
                    data={"executed": nominator_id},
                    visibility="public",
                )
                check_win_conditions(s)
                # Day immediately ends, and NO OTHER execution may occur
                self.end_day()
                return None

        return rec

    def cast_votes(
        self,
        votes: dict[PlayerId, bool],
    ) -> tuple[int, bool]:
        """Tally votes for the active nomination. Returns (vote_count, exceeded_threshold)."""
        s = self.state
        rec = s.current_nomination
        if not rec:
            raise ValueError("No active nomination to vote on.")

        threshold = s.execution_threshold
        tally = 0

        for player_id in s.players:
            voted_yes = votes.get(player_id, False)
            if not voted_yes:
                continue

            is_alive = s.alive.get(player_id, False)
            has_ghost_vote = s.ghost_votes.get(player_id, False)

            if not is_alive and not has_ghost_vote:
                continue

            # Butler restriction check: strictly enforced in rules layer (waived if drunk/poisoned)
            if is_alive and s.true_roles.get(player_id) == RoleId.BUTLER and not s.is_poisoned_or_drunk(player_id):
                master = s.butler_masters.get(player_id)
                if master and not votes.get(master, False):
                    continue

            rec.votes[player_id] = True
            tally += 1

            if not is_alive and has_ghost_vote:
                s.ghost_votes[player_id] = False
                s.event_log.append(
                    day=s.day,
                    phase=s.phase,
                    event_type="GHOST_VOTE_USED",
                    actor=player_id,
                    target=rec.nominee_id,
                    visibility="public",
                )

        rec.final_vote_count = tally
        rec.exceeded_threshold = tally >= threshold

        s.event_log.append(
            day=s.day,
            phase=s.phase,
            event_type="VOTE_RESULT",
            actor=rec.nominee_id,
            data={"votes": tally, "threshold": threshold, "exceeded": rec.exceeded_threshold},
            visibility="public",
        )

        s.current_nomination = None
        return tally, rec.exceeded_threshold

    def end_day(self) -> PlayerId | None:
        """Resolve dusk execution, Saint trigger, Mayor 3-alive win, and expire dusk effects."""
        s = self.state
        s.phase = GamePhase.DUSK

        # If an execution has already taken place today (e.g. Virgin proc), no second execution!
        if s.executed_today is not None:
            s.event_log.append(
                day=s.day,
                phase=s.phase,
                event_type="DAY_END",
                data={"already_executed": s.executed_today},
                visibility="public",
            )
            check_win_conditions(s)
            ret = s.executed_today
            s.last_executed_player_yesterday = s.executed_today
            s.expire_ongoing_effects("dusk")
            return ret

        # Find candidate with strictly highest votes exceeding threshold
        qualifying = [n for n in s.nominations_today if n.exceeded_threshold]
        executed_player: PlayerId | None = None

        if qualifying:
            max_votes = max(n.final_vote_count for n in qualifying)
            top_candidates = [n for n in qualifying if n.final_vote_count == max_votes]
            if len(top_candidates) == 1:
                executed_player = top_candidates[0].nominee_id

        if executed_player and s.alive.get(executed_player, False):
            s.executed_today = executed_player
            is_saint = s.true_roles[executed_player] == RoleId.SAINT
            was_poisoned_or_drunk = s.is_poisoned_or_drunk(executed_player)

            s.kill_player(executed_player, DeathReason.EXECUTION)
            s.ghost_votes[executed_player] = True

            s.event_log.append(
                day=s.day,
                phase=s.phase,
                event_type="EXECUTION",
                actor=executed_player,
                data={"role": s.true_roles[executed_player].value},
                visibility="public",
            )

            # Saint execution check: only triggers evil win if Saint is NOT poisoned/drunk!
            if is_saint and not was_poisoned_or_drunk:
                s.winner = Alignment.EVIL
                s.end_reason = "saint_executed"
                s.phase = GamePhase.ENDED
                s.event_log.append(
                    day=s.day,
                    phase=s.phase,
                    event_type="GAME_OVER",
                    data={"winner": Alignment.EVIL.value, "reason": s.end_reason},
                    visibility="public",
                )
                s.last_executed_player_yesterday = executed_player
                s.expire_ongoing_effects("dusk")
                return executed_player
        else:
            s.event_log.append(
                day=s.day,
                phase=s.phase,
                event_type="NO_EXECUTION",
                visibility="public",
            )
            # Mayor 3-alive win condition: exactly 3 alive, no execution, Mayor functioning
            if s.alive_count == 3:
                mayor = next((p for p in s.alive_players if s.true_roles[p] == RoleId.MAYOR), None)
                if mayor and not s.is_poisoned_or_drunk(mayor):
                    s.winner = Alignment.GOOD
                    s.end_reason = "mayor_three_alive"
                    s.phase = GamePhase.ENDED
                    s.event_log.append(
                        day=s.day,
                        phase=s.phase,
                        event_type="GAME_OVER",
                        data={"winner": Alignment.GOOD.value, "reason": s.end_reason},
                        visibility="public",
                    )
                    s.last_executed_player_yesterday = None
                    s.expire_ongoing_effects("dusk")
                    return None

        s.last_executed_player_yesterday = executed_player
        s.expire_ongoing_effects("dusk")
        check_win_conditions(s)
        return executed_player

    # ------------------ INFO RESOLUTION HELPERS ------------------
    def _resolve_washerwoman(self, actor: PlayerId, custom: dict | None, st_policy: Any) -> None:
        s = self.state
        if custom and actor in custom:
            info = custom[actor]
        else:
            is_poisoned = s.is_poisoned_or_drunk(actor)
            townsfolk_players = [p for p in s.players if ROLES[s.true_roles[p]].type == CharacterType.TOWNSFOLK and p != actor]
            if townsfolk_players and not is_poisoned:
                tf_target = self.rng.choice(townsfolk_players)
                other_candidates = [p for p in s.players if p != actor and p != tf_target]
                other_target = self.rng.choice(other_candidates)
                pair = [tf_target, other_target]
                self.rng.shuffle(pair)
                info = {"players": pair, "role": s.true_roles[tf_target].value}
            else:
                pool = [p for p in s.players if p != actor]
                pair = self.rng.sample(pool, 2)
                all_tf = [r.value for r, d in ROLES.items() if d.type == CharacterType.TOWNSFOLK]
                info = {"players": pair, "role": self.rng.choice(all_tf)}

        s.event_log.append(
            day=0,
            phase=s.phase,
            event_type="INFO_WASHERWOMAN",
            actor=actor,
            data=info,
            visibility="private",
            audience=[actor],
        )

    def _resolve_librarian(self, actor: PlayerId, custom: dict | None, st_policy: Any) -> None:
        s = self.state
        if custom and actor in custom:
            info = custom[actor]
        else:
            is_poisoned = s.is_poisoned_or_drunk(actor)
            outsider_players = [p for p in s.players if ROLES[s.true_roles[p]].type == CharacterType.OUTSIDER and p != actor]
            if not outsider_players and not is_poisoned:
                info = {"players": [], "role": None, "count": 0}
            elif outsider_players and not is_poisoned:
                out_target = self.rng.choice(outsider_players)
                other_candidates = [p for p in s.players if p != actor and p != out_target]
                other_target = self.rng.choice(other_candidates)
                pair = [out_target, other_target]
                self.rng.shuffle(pair)
                info = {"players": pair, "role": s.true_roles[out_target].value, "count": len(outsider_players)}
            else:
                pool = [p for p in s.players if p != actor]
                pair = self.rng.sample(pool, 2)
                all_outsiders = [r.value for r, d in ROLES.items() if d.type == CharacterType.OUTSIDER]
                info = {"players": pair, "role": self.rng.choice(all_outsiders), "count": 1}

        s.event_log.append(
            day=0,
            phase=s.phase,
            event_type="INFO_LIBRARIAN",
            actor=actor,
            data=info,
            visibility="private",
            audience=[actor],
        )

    def _resolve_investigator(self, actor: PlayerId, custom: dict | None, st_policy: Any) -> None:
        s = self.state
        if custom and actor in custom:
            info = custom[actor]
        else:
            is_poisoned = s.is_poisoned_or_drunk(actor)
            minion_players = [p for p in s.players if ROLES[s.true_roles[p]].type == CharacterType.MINION]
            if minion_players and not is_poisoned:
                minion_target = self.rng.choice(minion_players)
                other_candidates = [p for p in s.players if p != actor and p != minion_target]
                other_target = self.rng.choice(other_candidates)
                pair = [minion_target, other_target]
                self.rng.shuffle(pair)
                info = {"players": pair, "role": s.true_roles[minion_target].value}
            else:
                pool = [p for p in s.players if p != actor]
                pair = self.rng.sample(pool, 2)
                all_minions = [r.value for r, d in ROLES.items() if d.type == CharacterType.MINION]
                info = {"players": pair, "role": self.rng.choice(all_minions)}

        s.event_log.append(
            day=0,
            phase=s.phase,
            event_type="INFO_INVESTIGATOR",
            actor=actor,
            data=info,
            visibility="private",
            audience=[actor],
        )

    def _resolve_chef(self, actor: PlayerId, custom: dict | None, st_policy: Any) -> None:
        s = self.state
        if custom and actor in custom:
            info = custom[actor]
        else:
            is_poisoned = s.is_poisoned_or_drunk(actor)
            # Recluse and Spy registration check for Chef
            true_pairs = 0
            n = len(s.players)
            for i in range(n):
                p1, p2 = s.players[i], s.players[(i + 1) % n]
                e1 = s.is_evil(p1)
                e2 = s.is_evil(p2)
                if s.true_roles[p1] == RoleId.RECLUSE and st_policy:
                    reg = st_policy.decide(STDecisionType.RECLUSE_REGISTRATION, s, actor=p1, context="chef")
                    if reg and reg.get("alignment") == Alignment.EVIL:
                        e1 = True
                elif s.true_roles[p1] == RoleId.SPY and st_policy:
                    reg = st_policy.decide(STDecisionType.SPY_REGISTRATION, s, actor=p1, context="chef")
                    if reg and reg.get("alignment") == Alignment.GOOD:
                        e1 = False
                if s.true_roles[p2] == RoleId.RECLUSE and st_policy:
                    reg = st_policy.decide(STDecisionType.RECLUSE_REGISTRATION, s, actor=p2, context="chef")
                    if reg and reg.get("alignment") == Alignment.EVIL:
                        e2 = True
                elif s.true_roles[p2] == RoleId.SPY and st_policy:
                    reg = st_policy.decide(STDecisionType.SPY_REGISTRATION, s, actor=p2, context="chef")
                    if reg and reg.get("alignment") == Alignment.GOOD:
                        e2 = False
                if e1 and e2:
                    true_pairs += 1

            if not is_poisoned:
                pairs = true_pairs
            else:
                if st_policy:
                    pairs = st_policy.decide(STDecisionType.DRUNK_POISON_MISINFO, s, actor=actor)
                else:
                    pairs = 1 if true_pairs == 0 else 0
            info = {"pairs": pairs}

        s.event_log.append(
            day=0,
            phase=s.phase,
            event_type="INFO_CHEF",
            actor=actor,
            data=info,
            visibility="private",
            audience=[actor],
        )

    def _resolve_empath(self, actor: PlayerId, custom: dict | None, st_policy: Any) -> None:
        s = self.state
        if custom and actor in custom:
            info = custom[actor]
        else:
            is_poisoned = s.is_poisoned_or_drunk(actor)
            left, right = get_adjacent_alive_neighbors(s, actor)
            true_num = 0
            for neighbor in (left, right if right != left else None):
                if not neighbor:
                    continue
                is_ev = s.is_evil(neighbor)
                if s.true_roles[neighbor] == RoleId.RECLUSE and st_policy:
                    reg = st_policy.decide(STDecisionType.RECLUSE_REGISTRATION, s, actor=neighbor, context="empath")
                    if reg and reg.get("alignment") == Alignment.EVIL:
                        is_ev = True
                elif s.true_roles[neighbor] == RoleId.SPY and st_policy:
                    reg = st_policy.decide(STDecisionType.SPY_REGISTRATION, s, actor=neighbor, context="empath")
                    if reg and reg.get("alignment") == Alignment.GOOD:
                        is_ev = False
                if is_ev:
                    true_num += 1

            if not is_poisoned:
                num = true_num
            else:
                if st_policy:
                    num = st_policy.decide(STDecisionType.DRUNK_POISON_MISINFO, s, actor=actor)
                else:
                    num = 1 if true_num == 0 else 0
            info = {"number": num}

        s.event_log.append(
            day=s.day,
            phase=s.phase,
            event_type="INFO_EMPATH",
            actor=actor,
            data=info,
            visibility="private",
            audience=[actor],
        )

    def _resolve_fortune_teller(
        self,
        actor: PlayerId,
        targets: tuple[PlayerId, PlayerId],
        custom: dict | None,
        st_policy: Any,
    ) -> None:
        s = self.state
        if custom and actor in custom:
            info = custom[actor]
        else:
            is_poisoned = s.is_poisoned_or_drunk(actor)
            has_demon = False
            for t in targets:
                if s.true_roles[t] == RoleId.IMP or t == s.red_herring:
                    has_demon = True
                elif s.true_roles[t] == RoleId.RECLUSE and st_policy:
                    reg = st_policy.decide(STDecisionType.RECLUSE_REGISTRATION, s, actor=t, context="fortune_teller")
                    if reg and reg.get("role") == RoleId.IMP:
                        has_demon = True

            if not is_poisoned:
                result = has_demon
            else:
                if st_policy:
                    result = st_policy.decide(STDecisionType.DRUNK_POISON_MISINFO, s, actor=actor)
                else:
                    result = not has_demon
            info = {"targets": list(targets), "result": result}

        s.event_log.append(
            day=s.day,
            phase=s.phase,
            event_type="INFO_FORTUNE_TELLER",
            actor=actor,
            data=info,
            visibility="private",
            audience=[actor],
        )

    def _resolve_undertaker(self, actor: PlayerId, custom: dict | None, st_policy: Any) -> None:
        s = self.state
        if custom and actor in custom:
            info = custom[actor]
        else:
            is_poisoned = s.is_poisoned_or_drunk(actor)
            target_p = s.executed_today or s.last_executed_player_yesterday
            if not target_p:
                return  # No wake / no info

            true_role = s.true_roles[target_p]
            # Spy registration: Spy can register as Townsfolk/Outsider to Undertaker
            if true_role == RoleId.SPY and st_policy:
                reg = st_policy.decide(STDecisionType.SPY_REGISTRATION, s, actor=target_p, context="undertaker")
                if reg and reg.get("role") != RoleId.SPY:
                    true_role = reg["role"]
            elif true_role == RoleId.RECLUSE and st_policy:
                reg = st_policy.decide(STDecisionType.RECLUSE_REGISTRATION, s, actor=target_p, context="undertaker")
                if reg and reg.get("role") != RoleId.RECLUSE:
                    true_role = reg["role"]

            if not is_poisoned:
                role = true_role
            else:
                if st_policy:
                    role = st_policy.decide(STDecisionType.DRUNK_POISON_MISINFO, s, actor=actor)
                else:
                    all_roles = list(ROLES.keys())
                    role = self.rng.choice(all_roles)
            info = {"executed_player": target_p, "executed_role": role.value if hasattr(role, "value") else str(role)}

        s.event_log.append(
            day=s.day,
            phase=s.phase,
            event_type="INFO_UNDERTAKER",
            actor=actor,
            data=info,
            visibility="private",
            audience=[actor],
        )

    def _resolve_ravenkeeper(
        self,
        actor: PlayerId,
        target: PlayerId,
        custom: dict | None,
        st_policy: Any,
    ) -> None:
        s = self.state
        if custom and actor in custom:
            info = custom[actor]
        else:
            is_poisoned = s.is_poisoned_or_drunk(actor)
            true_role = s.true_roles[target]
            # Recluse / Spy registration check
            if true_role == RoleId.SPY and st_policy:
                reg = st_policy.decide(STDecisionType.SPY_REGISTRATION, s, actor=target, context="ravenkeeper")
                if reg and reg.get("role") != RoleId.SPY:
                    true_role = reg["role"]
            elif true_role == RoleId.RECLUSE and st_policy:
                reg = st_policy.decide(STDecisionType.RECLUSE_REGISTRATION, s, actor=target, context="ravenkeeper")
                if reg and reg.get("role") != RoleId.RECLUSE:
                    true_role = reg["role"]

            if not is_poisoned:
                role = true_role
            else:
                all_roles = list(ROLES.keys())
                role = self.rng.choice(all_roles)
            info = {
                "target": target,
                "chosen_player": target,
                "role": role.value if hasattr(role, "value") else str(role),
                "character": role.value if hasattr(role, "value") else str(role),
            }

        s.event_log.append(
            day=s.day,
            phase=s.phase,
            event_type="INFO_RAVENKEEPER",
            actor=actor,
            data=info,
            visibility="private",
            audience=[actor],
        )
