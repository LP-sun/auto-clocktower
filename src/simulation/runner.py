"""Single game simulation runner coordinating the Engine, Observations, and Player Policies."""
from __future__ import annotations

import random
from dataclasses import asdict, dataclass, field
from typing import Any, Mapping

from src.cognition.observation import observe
from src.cognition.player_state import ClaimRecord
from src.engine.game import ClocktowerEngine
from src.engine.setup import SetupResult
from src.engine.types import Alignment, CharacterType, PlayerId, RoleId
from src.player.cognitive_player import CognitivePlayer
from src.player.random_player import RandomPlayer
from src.roles.trouble_brewing import ROLES
from src.storyteller.st_policy import StorytellerPolicy


@dataclass(slots=True)
class SimulationResult:
    seed: int
    player_count: int
    winner: Alignment | None
    end_reason: str | None
    total_days: int
    total_nights: int
    event_count: int
    alive_players: list[PlayerId]
    dead_players: list[PlayerId]
    true_roles: dict[PlayerId, str]
    apparent_roles: dict[PlayerId, str]
    alignments: dict[PlayerId, str]
    events: list[dict[str, Any]]
    st_decisions: list[dict[str, Any]] = field(default_factory=list)
    private_chats: list[dict[str, Any]] = field(default_factory=list)
    decision_traces: list[dict[str, Any]] = field(default_factory=list)
    decision_traces_count: int = 0
    day_start_alives: dict[int, int] = field(default_factory=dict)
    alive_trajectory: list[int] = field(default_factory=list)
    cycle_deaths: dict[int, int] = field(default_factory=dict)
    actual_day_deaths: dict[int, int] = field(default_factory=dict)
    actual_night_deaths: dict[int, int] = field(default_factory=dict)
    nomination_history: list[dict[str, Any]] = field(default_factory=list)
    f4_snapshot: dict[str, Any] | None = None
    f3_snapshot: dict[str, Any] | None = None
    reached_4_alive_day: bool = False
    reached_3_alive_day: bool = False
    ever_had_4_alive_state: bool = False
    ever_had_3_alive_state: bool = False
    early_end_category: str = "LATE_GAME_NORMAL"

    @property
    def days(self) -> int:
        return self.total_days

    @property
    def alive_count(self) -> int:
        return len(self.alive_players)

    @classmethod
    def create_mock(
        cls,
        seed: int = 42,
        winner: Alignment | str = Alignment.GOOD,
        end_reason: str = "DEMON_EXECUTED",
        total_days: int = 4,
        player_count: int = 12,
        alive_players: list[PlayerId] | None = None,
        dead_players: list[PlayerId] | None = None,
        day_start_alives: dict[int, int] | None = None,
        alive_trajectory: list[int] | None = None,
        cycle_deaths: dict[int, int] | None = None,
        reached_4_alive_day: bool = False,
        reached_3_alive_day: bool = False,
        ever_had_4_alive_state: bool = False,
        ever_had_3_alive_state: bool = False,
        early_end_category: str = "LATE_GAME_NORMAL",
    ) -> SimulationResult:
        if isinstance(winner, str):
            w = Alignment.GOOD if winner.lower() == "good" else Alignment.EVIL
        else:
            w = winner
        alive = alive_players or ["p0", "p1", "p2"]
        dead = dead_players or [f"p{i}" for i in range(len(alive), player_count)]
        return cls(
            seed=seed,
            player_count=player_count,
            winner=w,
            end_reason=end_reason,
            total_days=total_days,
            total_nights=total_days,
            event_count=50,
            alive_players=alive,
            dead_players=dead,
            true_roles={},
            apparent_roles={},
            alignments={},
            events=[],
            day_start_alives=day_start_alives or {},
            alive_trajectory=alive_trajectory or [player_count, len(alive)],
            cycle_deaths=cycle_deaths or {},
            reached_4_alive_day=reached_4_alive_day,
            reached_3_alive_day=reached_3_alive_day,
            ever_had_4_alive_state=ever_had_4_alive_state,
            ever_had_3_alive_state=ever_had_3_alive_state,
            early_end_category=early_end_category,
        )

    def to_dict(self) -> dict[str, Any]:

        return {
            "seed": self.seed,
            "player_count": self.player_count,
            "winner": self.winner.value if self.winner else None,
            "end_reason": self.end_reason,
            "total_days": self.total_days,
            "total_nights": self.total_nights,
            "event_count": self.event_count,
            "alive_players": self.alive_players,
            "dead_players": self.dead_players,
            "true_roles": self.true_roles,
            "apparent_roles": self.apparent_roles,
            "alignments": self.alignments,
            "st_decisions_count": len(self.st_decisions),
            "private_chats_count": len(self.private_chats),
            "decision_traces_count": self.decision_traces_count,
            "day_start_alives": self.day_start_alives,
            "alive_trajectory": self.alive_trajectory,
            "cycle_deaths": self.cycle_deaths,
            "reached_4_alive_day": self.reached_4_alive_day,
            "reached_3_alive_day": self.reached_3_alive_day,
            "ever_had_4_alive_state": self.ever_had_4_alive_state,
            "ever_had_3_alive_state": self.ever_had_3_alive_state,
            "early_end_category": self.early_end_category,
            "events": self.events,
            "st_decisions": self.st_decisions,
            "private_chats": self.private_chats,
            "decision_traces": self.decision_traces,
        }


def simulate_game(
    player_count: int = 12,
    seed: int = 42,
    max_days: int = 20,
    custom_setup: SetupResult | None = None,
    player_factory: Any = None,
    use_random_players: bool = False,
    ablated_primitives: set[str] | None = None,
    config: Any = None,
) -> SimulationResult:
    """Run an autonomous game simulation to completion with full cognitive agents and Storyteller policy."""
    rng = random.Random(seed)
    engine = ClocktowerEngine.create(player_count=player_count, seed=seed, custom_setup=custom_setup)
    state = engine.state
    st_policy = StorytellerPolicy(seed=seed)

    # Instantiate player policies
    players: dict[PlayerId, Any] = {}
    for p in state.players:
        p_seed = rng.randint(0, 0xFFFFFFFF)
        if player_factory:
            players[p] = player_factory(p, p_seed)
        elif use_random_players:
            players[p] = RandomPlayer(p, seed=p_seed)
        else:
            players[p] = CognitivePlayer(
                player_id=p,
                all_players=state.players,
                initial_role=state.apparent_roles[p],
                initial_alignment=state.alignments[p],
                seed=p_seed,
                ablated_primitives=ablated_primitives,
                config=config,
            )

    private_chats: list[dict[str, Any]] = []

    # ------------------ FIRST NIGHT ------------------
    # Query night choices from legitimate living actors
    p_poisoner = next((p for p in state.alive_players if state.true_roles[p] == RoleId.POISONER), None)
    poisoner_target = players[p_poisoner].choose_night_target(observe(state, p_poisoner), "poisoner") if p_poisoner else None

    p_ft = next((p for p in state.alive_players if state.apparent_roles[p] == RoleId.FORTUNE_TELLER), None)
    ft_targets = players[p_ft].choose_night_target(observe(state, p_ft), "fortune_teller") if p_ft else None

    p_butler = next((p for p in state.alive_players if state.true_roles[p] == RoleId.BUTLER), None)
    butler_target = players[p_butler].choose_night_target(observe(state, p_butler), "butler") if p_butler else None

    engine.run_first_night(
        poisoner_target=poisoner_target,
        fortune_teller_targets=ft_targets,
        butler_target=butler_target,
        st_policy=st_policy,
    )

    # Track day-start and cycle death trajectory
    day_start_alives: dict[int, int] = {}
    alive_trajectory: list[int] = [len(state.alive_players)]
    cycle_deaths: dict[int, int] = {}
    actual_day_deaths: dict[int, int] = {}
    actual_night_deaths: dict[int, int] = {}
    nomination_history: list[dict[str, Any]] = []
    f4_snapshot: dict[str, Any] | None = None
    f3_snapshot: dict[str, Any] | None = None

    # ------------------ GAME LOOP ------------------
    while state.winner is None and state.day < max_days:
        # --- DAWN & DAY START ---
        engine.start_day()
        cur_day = state.day
        alive_at_dawn = len(state.alive_players)
        day_start_alives[cur_day] = alive_at_dawn
        alive_trajectory.append(alive_at_dawn)

        if alive_at_dawn == 4 and f4_snapshot is None:
            f4_snapshot = {
                "day": cur_day,
                "alive_players": list(state.alive_players),
                "demon": next((p for p in state.players if state.true_roles[p] == RoleId.IMP), None),
                "good_beliefs": {
                    p: {target: b.demon for target, b in players[p].state.beliefs.items()}
                    for p in state.alive_players
                    if state.alignments[p] == Alignment.GOOD and hasattr(players[p], "state")
                },
            }

        if alive_at_dawn == 3 and f3_snapshot is None:
            f3_snapshot = {
                "day": cur_day,
                "alive_players": list(state.alive_players),
                "demon": next((p for p in state.players if state.true_roles[p] == RoleId.IMP), None),
                "good_beliefs": {
                    p: {target: b.demon for target, b in players[p].state.beliefs.items()}
                    for p in state.alive_players
                    if state.alignments[p] == Alignment.GOOD and hasattr(players[p], "state")
                },
            }

        if state.winner is not None:
            break

        # --- SOCIAL / PRIVATE CHAT ROUND ---
        alive_list = list(state.alive_players)
        rng.shuffle(alive_list)

        whispered_today: set[PlayerId] = set()
        for p1 in alive_list:
            if p1 in whispered_today or p1 not in state.alive_players:
                continue
            player1 = players[p1]
            obs1 = observe(state, p1)

            p2 = None
            if hasattr(player1, "choose_whisper_target"):
                p2 = player1.choose_whisper_target(obs1)
            else:
                other_alives = [p for p in state.alive_players if p != p1 and p not in whispered_today]
                if other_alives:
                    p2 = rng.choice(other_alives)

            if not p2 or p2 in whispered_today or p2 not in state.alive_players:
                continue

            whispered_today.add(p1)
            whispered_today.add(p2)
            player2 = players[p2]
            obs2 = observe(state, p2)

            claim1 = player1.decide_whisper_claim(p2, obs1) if hasattr(player1, "decide_whisper_claim") else None
            claim2 = player2.decide_whisper_claim(p1, obs2) if hasattr(player2, "decide_whisper_claim") else None

            claims_exchanged = False
            if claim1 is not None:
                if hasattr(player2, "state"):
                    player2.state.private_claims[p1] = ClaimRecord(player_id=p1, claimed_role=claim1, day=state.day, is_public=False)
                    # Communication only between the actual whisper participants (no telepathic leak to third-party evil players)
                    if state.alignments[p1] == Alignment.EVIL and state.alignments[p2] == Alignment.EVIL:
                        player2.state.public_claims[p1] = ClaimRecord(player_id=p1, claimed_role=claim1, day=state.day)
                claims_exchanged = True

            if claim2 is not None:
                if hasattr(player1, "state"):
                    player1.state.private_claims[p2] = ClaimRecord(player_id=p2, claimed_role=claim2, day=state.day, is_public=False)
                    if state.alignments[p1] == Alignment.EVIL and state.alignments[p2] == Alignment.EVIL:
                        player1.state.public_claims[p2] = ClaimRecord(player_id=p2, claimed_role=claim2, day=state.day)
                claims_exchanged = True

            chat_rec = {
                "day": state.day,
                "p1": p1,
                "p2": p2,
                "p1_role": state.apparent_roles[p1].value,
                "p2_role": state.apparent_roles[p2].value,
                "claims_exchanged": claims_exchanged,
            }
            private_chats.append(chat_rec)

        # Open morning claims (especially info roles sharing publicly on Day 1/2)
        for p in state.alive_players:
            pl = players[p]
            if hasattr(pl, "state") and getattr(pl, "personality", None):
                info_roles_set = {
                    RoleId.EMPATH, RoleId.FORTUNE_TELLER, RoleId.UNDERTAKER,
                    RoleId.VIRGIN, RoleId.SLAYER, RoleId.CHEF
                }
                if pl.state.perceived_role in info_roles_set and (pl.personality.openness > 0.4 or state.day >= 2):
                    rec = ClaimRecord(player_id=p, claimed_role=pl.state.perceived_role, day=state.day, is_public=True)
                    for other_p in state.players:
                        if hasattr(players[other_p], "state"):
                            players[other_p].state.public_claims[p] = rec

        # --- SLAYER SHOTS (if any living slayer decides to shoot) ---
        for p in state.alive_players:
            if state.true_roles[p] == RoleId.SLAYER and p not in state.ability_used:
                obs = observe(state, p)
                target = players[p].decide_slayer_shot(obs)
                if target and target in state.alive_players:
                    engine.use_slayer_ability(p, target, st_policy=st_policy)
                    if state.winner is not None:
                        break
        if state.winner is not None:
            break

        # --- NOMINATIONS & VOTING ROUNDS ---
        shuffled_living = list(state.alive_players)
        rng.shuffle(shuffled_living)

        for nominator_id in shuffled_living:
            if state.winner is not None:
                break
            if nominator_id not in state.alive_players:
                continue
            if nominator_id in state.nominator_ids_today:
                continue

            obs = observe(state, nominator_id)
            nominee_id = players[nominator_id].decide_nomination(obs)
            if not nominee_id or nominee_id not in state.players:
                continue
            if nominee_id in state.nominee_ids_today:
                continue

            # Handle nomination (might trigger Virgin proc)
            nom_record = engine.handle_nomination(nominator_id, nominee_id, st_policy=st_policy)
            if nom_record is None:
                # Virgin proc occurred, day immediately ended
                break

            # Collect votes on active nomination in clockwise order starting next to nominee
            nominee_idx = state.players.index(nominee_id)
            voting_order = [state.players[(nominee_idx + 1 + i) % len(state.players)] for i in range(len(state.players))]
            votes: dict[PlayerId, bool] = {}
            for voter_id in voting_order:
                v_obs = observe(state, voter_id)
                v_choice = players[voter_id].decide_vote(v_obs)
                votes[voter_id] = v_choice
                if v_choice:
                    state.current_nomination.votes[voter_id] = True

            v_count, exceeded = engine.cast_votes(votes)
            qualifying = [n for n in state.nominations_today if n.exceeded_threshold]
            if qualifying:
                max_v = max(n.final_vote_count for n in qualifying)
                tops = [n for n in qualifying if n.final_vote_count == max_v]
                current_on_block = tops[0].nominee_id if len(tops) == 1 else None
            else:
                current_on_block = None

            nomination_history.append({
                "day": cur_day,
                "alive_at_nom": len(state.alive_players),
                "nom_index": len(state.nominations_today),
                "nominator": nominator_id,
                "nominee": nominee_id,
                "yes_votes": v_count,
                "threshold": state.execution_threshold,
                "exceeded": exceeded,
                "current_on_block": current_on_block,
            })

        # --- DUSK / END OF DAY ---
        if state.winner is None:
            engine.end_day()

        alive_dusk = len(state.alive_players)
        alive_trajectory.append(alive_dusk)
        actual_day_deaths[cur_day] = alive_at_dawn - alive_dusk

        if state.winner is not None:
            cycle_deaths[cur_day] = alive_at_dawn - alive_dusk
            actual_night_deaths[cur_day] = 0
            break

        # --- NIGHT PHASE ---
        p_poisoner = next((p for p in state.alive_players if state.true_roles[p] == RoleId.POISONER), None)
        poisoner_target = players[p_poisoner].choose_night_target(observe(state, p_poisoner), "poisoner") if p_poisoner else None

        p_monk = next((p for p in state.alive_players if state.true_roles[p] == RoleId.MONK), None)
        monk_target = players[p_monk].choose_night_target(observe(state, p_monk), "monk") if p_monk else None

        p_imp = next((p for p in state.alive_players if state.true_roles[p] == RoleId.IMP), None)
        imp_target = players[p_imp].choose_night_target(observe(state, p_imp), "imp") if p_imp else None

        p_rk = next((p for p in state.players if state.true_roles[p] == RoleId.RAVENKEEPER), None)
        rk_target = players[p_rk].choose_night_target(observe(state, p_rk), "ravenkeeper") if p_rk else None

        p_ft = next((p for p in state.alive_players if state.apparent_roles[p] == RoleId.FORTUNE_TELLER), None)
        ft_targets = players[p_ft].choose_night_target(observe(state, p_ft), "fortune_teller") if p_ft else None

        p_butler = next((p for p in state.alive_players if state.true_roles[p] == RoleId.BUTLER), None)
        butler_target = players[p_butler].choose_night_target(observe(state, p_butler), "butler") if p_butler else None

        engine.run_night(
            poisoner_target=poisoner_target,
            monk_target=monk_target,
            imp_target=imp_target,
            ravenkeeper_target=rk_target,
            fortune_teller_targets=ft_targets,
            butler_target=butler_target,
            st_policy=st_policy,
        )

        alive_after_night = len(state.alive_players)
        alive_trajectory.append(alive_after_night)
        actual_night_deaths[cur_day] = alive_dusk - alive_after_night
        cycle_deaths[cur_day] = alive_at_dawn - alive_after_night

    # In case max days reached without winner
    if state.winner is None:
        state.winner = Alignment.EVIL
        state.end_reason = "max_days_reached"

    # Evaluate Human Benchmark indicators
    reached_4_alive_day = any(cnt <= 4 for cnt in day_start_alives.values())
    reached_3_alive_day = any(cnt == 3 for cnt in day_start_alives.values())
    ever_had_4_alive_state = any(cnt <= 4 for cnt in alive_trajectory)
    ever_had_3_alive_state = any(cnt <= 3 for cnt in alive_trajectory)

    alive_end = len(state.alive_players)
    if alive_end <= 4 or reached_4_alive_day:
        early_end_category = "LATE_GAME_NORMAL"
    else:
        special_reasons = {"saint_executed", "mayor_three_alive"}
        has_slayer_kill = any(
            (getattr(e, "type", None) or e.get("type")) == "DEATH"
            and (getattr(e, "data", None) or e.get("data", {})).get("reason") == "slayer_shot"
            for e in state.event_log
        )
        has_virgin_proc = any(
            (getattr(e, "type", None) or e.get("type")) == "VIRGIN_PROC"
            for e in state.event_log
        )

        has_star_pass_fail = (
            state.end_reason == "imp_dead"
            and not any(state.true_roles[p] == RoleId.SCARLET_WOMAN and p in state.players for p in state.players)
        )
        if state.end_reason in special_reasons or has_slayer_kill or has_virgin_proc or has_star_pass_fail:
            early_end_category = "RULE_SPECIAL_END"
        elif state.day <= 2 and alive_end <= 7:
            early_end_category = "STRUCTURAL_COLLAPSE_CANDIDATE"
        else:
            early_end_category = "ORDINARY_BUT_EARLY_END"

    all_traces: list[dict[str, Any]] = []
    for p in players.values():
        for t in getattr(p, "decision_traces", []):
            all_traces.append({
                "action_type": t.action_type,
                "legal_actions": t.legal_actions,
                "applicable_primitives": t.applicable_primitives,
                "candidate_scores": t.candidate_scores,
                "utility_components": t.utility_components,
                "softmax_probabilities": t.softmax_probabilities,
                "chosen_action": t.chosen_action,
                "collapse_warning": getattr(t, "collapse_warning", False),
            })

    return SimulationResult(
        seed=state.seed,
        player_count=state.player_count,
        winner=state.winner,
        end_reason=state.end_reason,
        total_days=state.day,
        total_nights=state.night_number,
        event_count=len(state.event_log),
        alive_players=state.alive_players,
        dead_players=state.dead_players,
        true_roles={p: state.true_roles[p].value for p in state.players},
        apparent_roles={p: state.apparent_roles[p].value for p in state.players},
        alignments={p: state.alignments[p].value for p in state.players},
        events=state.event_log.to_list(),
        st_decisions=[d.to_dict() for d in st_policy.decisions_log],
        private_chats=private_chats,
        decision_traces=all_traces,
        decision_traces_count=len(all_traces),
        day_start_alives=day_start_alives,
        alive_trajectory=alive_trajectory,
        cycle_deaths=cycle_deaths,
        actual_day_deaths=actual_day_deaths,
        actual_night_deaths=actual_night_deaths,
        nomination_history=nomination_history,
        f4_snapshot=f4_snapshot,
        f3_snapshot=f3_snapshot,
        reached_4_alive_day=reached_4_alive_day,
        reached_3_alive_day=reached_3_alive_day,
        ever_had_4_alive_state=ever_had_4_alive_state,
        ever_had_3_alive_state=ever_had_3_alive_state,
        early_end_category=early_end_category,
    )
