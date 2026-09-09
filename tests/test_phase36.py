"""Unit tests for Phase 3.6: Endgame Cognition, World-Hypothesis Model, and Death Tempo Audit."""
import math
import random
import unittest

from src.belief.world_model import WorldHypothesis, WorldHypothesisManager
from src.calibration.endgame_audit import run_endgame_audit
from src.calibration.human_benchmark import DeathTempo, compute_human_structure_benchmark
from src.cognition.memory import FiniteMemoryManager, MemoryCategory, MemoryItem
from src.cognition.observation import Observation
from src.cognition.player_state import PlayerState
from src.engine.game import ClocktowerEngine
from src.engine.state import DeathRecord, GameState
from src.engine.types import Alignment, CharacterType, DeathReason, GamePhase, PlayerId, RoleId
from src.player.personality import PersonalityVector, sample_personality
from src.player.policy import CognitionPolicy
from src.player.skill import SkillProfile, sample_skill_profile
from src.simulation.runner import SimulationResult


class TestPhase36EngineAndDeathTempo(unittest.TestCase):
    def test_death_record_canonical_fields(self):
        """Verify DeathRecord has death_id, cause, source, alive_count_before, alive_count_after."""
        rec = DeathRecord(
            death_id=1,
            player_id="p1",
            day=1,
            phase=GamePhase.NIGHT,
            reason=DeathReason.DEMON_KILL,
            alive_count_before=12,
            alive_count_after=11,
            cause="demon_kill",
            source="imp",
        )
        self.assertEqual(rec.death_id, 1)
        self.assertEqual(rec.cause, "demon_kill")
        self.assertEqual(rec.source, "imp")
        self.assertEqual(rec.alive_count_before, 12)
        self.assertEqual(rec.alive_count_after, 11)

    def test_game_engine_death_logging(self):
        """Verify ClocktowerEngine.kill_player assigns incremental death_ids and logs canonical data."""
        engine = ClocktowerEngine.create(player_count=12, seed=42)

        self.assertEqual(len(engine.state.dead_players), 0)
        p_to_kill = engine.state.players[2]
        rec = engine.state.kill_player(p_to_kill, reason=DeathReason.EXECUTION, source="town_vote")

        self.assertIsNotNone(rec)
        self.assertEqual(rec.death_id, 1)
        self.assertEqual(rec.alive_count_before, 12)
        self.assertEqual(rec.alive_count_after, 11)
        self.assertIn(p_to_kill, engine.state.dead_players)

        # Second kill
        p_to_kill_2 = engine.state.players[3]
        rec2 = engine.state.kill_player(p_to_kill_2, reason=DeathReason.DEMON_KILL, source="imp")
        self.assertIsNotNone(rec2)
        self.assertEqual(rec2.death_id, 2)
        self.assertEqual(rec2.alive_count_before, 11)
        self.assertEqual(rec2.alive_count_after, 10)

    def test_death_tempo_dict_iteration_bug_fixed(self):
        """Verify Death Tempo calculates actual death counts, not day number dictionary keys."""
        # 3 games, each lasting 3 days with realistic deaths: 1 or 2 deaths per cycle
        results = [
            SimulationResult.create_mock(
                seed=1,
                cycle_deaths={1: 2, 2: 1, 3: 2},
                day_start_alives={1: 12, 2: 10, 3: 9},
            ),
            SimulationResult.create_mock(
                seed=2,
                cycle_deaths={1: 1, 2: 2, 3: 1},
                day_start_alives={1: 12, 2: 11, 3: 9},
            ),
        ]
        # Attach actual_day_deaths and actual_night_deaths
        for r in results:
            r.actual_day_deaths = {1: 1, 2: 1, 3: 1}
            r.actual_night_deaths = {1: 1, 2: 0, 3: 1}

        bench = compute_human_structure_benchmark(results)
        tempo = bench.death_tempo

        # All cycle death values are 1 or 2, NONE are > 2!
        self.assertEqual(tempo.p_more_than_two, 0.0)
        self.assertAlmostEqual(tempo.p_one_death + tempo.p_two_deaths, 1.0)
        # Mean deaths should be around 1.5, definitely NOT 4.8!
        self.assertAlmostEqual(tempo.mean_deaths_per_cycle, 1.5, places=2)


def make_test_obs(
    observer: str = "p0",
    day: int = 2,
    phase: GamePhase = GamePhase.NOMINATION,
    alive: bool = True,
    ghost_vote_available: bool = False,
    roster_alive: dict[str, bool] | None = None,
    execution_threshold: int = 3,
    current_nomination: dict | None = None,
    nominations_today: list | None = None,
) -> Observation:
    roster = roster_alive or {f"p{i}": True for i in range(5)}
    return Observation(
        observer=observer,
        day=day,
        phase=phase,
        night_number=max(1, day - 1),
        self_role=RoleId.WASHERWOMAN,
        self_alignment=Alignment.GOOD,
        alive=alive,
        ghost_vote_available=ghost_vote_available,
        roster_alive=roster,
        deaths_public=[],
        execution_threshold=execution_threshold,
        nominated_by_today=[],
        nominated_today=[],
        nominations_today=nominations_today or [],
        current_nomination=current_nomination,
    )


class TestPhase36MemoryDecayAndPolicy(unittest.TestCase):
    def test_memory_category_decay_rates(self):
        """Verify memory decay rates differ by category (hard role info survives longer than social opinion)."""
        mem = FiniteMemoryManager(skill_factor=1.0, max_items=20)
        # Store items of different categories
        hard_item = mem.store(
            day=1,
            item_type="INFO_EMPATH",
            source="storyteller",
            data={"role": "empath"},
            importance=2.0,
            category=MemoryCategory.HARD_ROLE_INFO,
        )
        social_item = mem.store(
            day=1,
            item_type="social_opinion",
            source="p2",
            data={"opinion": "p3 is sus"},
            importance=1.0,
            category=MemoryCategory.SOCIAL_OPINION,
        )

        # After 3 days (day 4), check current strength
        hard_str = hard_item.current_strength(4)
        social_str = social_item.current_strength(4)

        # Hard role info retains much higher strength than social opinion
        self.assertGreater(hard_str, social_str * 1.5)

    def test_vote_counting_ignores_false_votes(self):
        """Verify vote calculation counts only YES votes and ignores NO (False) votes."""
        players = [f"p{i}" for i in range(5)]
        state = PlayerState.create(
            player_id="p0",
            all_players=players,
            perceived_role=RoleId.WASHERWOMAN,
            perceived_alignment=Alignment.GOOD,
            personality=sample_personality(random.Random(42)),
            skill=sample_skill_profile(random.Random(42)),
        )
        policy = CognitionPolicy(state)

        # Observation where 3 players voted NO (False) and 1 voted YES (True)
        obs = make_test_obs(
            observer="p0",
            day=2,
            alive=True,
            roster_alive={p: True for p in players},
            execution_threshold=3,
            current_nomination={
                "nominator": "p1",
                "nominee": "p2",
                "votes": {"p1": True, "p3": False, "p4": False},  # Only 1 YES vote!
            },
        )

        # In policy.py, current_votes should be 1, NOT 3!
        # If it was 3, conformity would kick in (3 >= threshold 3)
        # With 1 YES vote, it should not trigger conformity
        _, trace = policy.score_vote_detailed(obs)
        self.assertIsNotNone(trace)
        self.assertEqual(trace.utility_components["yes"]["conformity"], 0.0)

    def test_dynamic_ghost_vote_conservation(self):
        """Verify ghost vote penalty is heavy when alive > 4, moderate at 4, and 0 at <= 3."""
        players = [f"p{i}" for i in range(8)]
        state = PlayerState.create(
            player_id="p0",
            all_players=players,
            perceived_role=RoleId.WASHERWOMAN,
            perceived_alignment=Alignment.GOOD,
            personality=sample_personality(random.Random(42)),
            skill=sample_skill_profile(random.Random(42)),
        )
        policy = CognitionPolicy(state)

        # Dead player with ghost vote available
        obs_early = make_test_obs(
            observer="p0",
            day=2,
            alive=False,
            ghost_vote_available=True,
            roster_alive={p: (i < 6) for i, p in enumerate(players)},  # 6 alive (>4)
            execution_threshold=3,
            current_nomination={"nominator": "p1", "nominee": "p2", "votes": {}},
        )
        _, trace_early = policy.score_vote_detailed(obs_early)
        cost_early = trace_early.utility_components["yes"]["ghost_cost"]
        self.assertLess(cost_early, -1.5)  # Heavy penalty

        obs_f4 = make_test_obs(
            observer="p0",
            day=3,
            alive=False,
            ghost_vote_available=True,
            roster_alive={p: (i < 4) for i, p in enumerate(players)},  # 4 alive
            execution_threshold=2,
            current_nomination={"nominator": "p1", "nominee": "p2", "votes": {}},
        )
        _, trace_f4 = policy.score_vote_detailed(obs_f4)
        cost_f4 = trace_f4.utility_components["yes"]["ghost_cost"]
        self.assertGreater(cost_f4, cost_early)  # Moderate penalty

        obs_f3 = make_test_obs(
            observer="p0",
            day=4,
            alive=False,
            ghost_vote_available=True,
            roster_alive={p: (i < 3) for i, p in enumerate(players)},  # 3 alive
            execution_threshold=2,
            current_nomination={"nominator": "p1", "nominee": "p2", "votes": {}},
        )
        _, trace_f3 = policy.score_vote_detailed(obs_f3)
        cost_f3 = trace_f3.utility_components["yes"]["ghost_cost"]
        self.assertEqual(cost_f3, 0.0)  # Zero penalty in final 3!

    def test_f3_pass_policy_mayor_awareness(self):
        """Verify F3 PASS policy applies heavy penalty without Mayor and bonus with Mayor."""
        players = [f"p{i}" for i in range(5)]
        state = PlayerState.create(
            player_id="p0",
            all_players=players,
            perceived_role=RoleId.WASHERWOMAN,
            perceived_alignment=Alignment.GOOD,
            personality=sample_personality(random.Random(42)),
            skill=sample_skill_profile(random.Random(42)),
        )
        policy = CognitionPolicy(state)

        # F3 without Mayor
        obs_no_mayor = make_test_obs(
            observer="p0",
            day=4,
            alive=True,
            roster_alive={"p0": True, "p1": True, "p2": True, "p3": False, "p4": False},
            execution_threshold=2,
            nominations_today=[],
        )
        _, trace_no_m = policy.score_nomination_detailed(obs_no_mayor)
        pass_u_no_m = trace_no_m.candidate_scores.get("pass", 0.0)
        self.assertLess(pass_u_no_m, -4.0)  # Heavily discouraged

        # F3 with living Mayor
        from src.cognition.player_state import ClaimRecord
        state.public_claims["p1"] = ClaimRecord(player_id="p1", claimed_role=RoleId.MAYOR, day=1)
        _, trace_with_m = policy.score_nomination_detailed(obs_no_mayor)
        pass_u_with_m = trace_with_m.candidate_scores.get("pass", 0.0)
        self.assertGreater(pass_u_with_m, pass_u_no_m)


class TestPhase36WorldHypothesisManager(unittest.TestCase):
    def test_world_generation_and_marginalization(self):
        """Verify WorldHypothesisManager generates valid worlds and extracts Demon marginals."""
        players = [f"p{i}" for i in range(12)]
        mgr = WorldHypothesisManager(k=16)

        claims = {
            "p0": RoleId.EMPATH,
            "p1": RoleId.CHEF,
            "p2": RoleId.FORTUNE_TELLER,
            "p3": RoleId.SLAYER,
            "p4": RoleId.VIRGIN,
        }
        alive_roster = {p: True for p in players}

        worlds = mgr.generate_candidate_worlds(
            observer_id="p0",
            all_players=players,
            claims=claims,
            alive_roster=alive_roster,
            perceived_role=RoleId.EMPATH,
            perceived_alignment=Alignment.GOOD,
        )
        self.assertGreater(len(worlds), 0)

        # Each world must have exactly 1 demon
        for w in worlds:
            self.assertIsNotNone(w.demon)
            self.assertNotIn(w.demon, w.minions)
            self.assertNotEqual(w.demon, "p0")  # Good observer cannot be demon

        # Score worlds
        state = PlayerState.create(
            player_id="p0",
            all_players=players,
            perceived_role=RoleId.EMPATH,
            perceived_alignment=Alignment.GOOD,
            personality=sample_personality(random.Random(42)),
            skill=sample_skill_profile(random.Random(42)),
        )
        for w in worlds:
            mgr.score_world(w, state, alive_roster)

        marginals, report = mgr.update_and_marginalize(worlds, players)
        self.assertAlmostEqual(sum(marginals.values()), 1.0, places=3)
        self.assertEqual(report.total_worlds, min(len(worlds), 16))
        self.assertGreater(report.effective_world_count, 1.0)


class TestPhase36EndgameAuditAndAttribution(unittest.TestCase):
    def test_9class_loss_attribution(self):
        """Verify 9-class Good loss attribution categorizes correctly."""
        results = [
            # Saint executed
            SimulationResult.create_mock(
                seed=10,
                winner=Alignment.EVIL,
                end_reason="saint_executed",
                total_days=2,
            ),
            # Early collapse
            SimulationResult.create_mock(
                seed=11,
                winner=Alignment.EVIL,
                end_reason="demon_kill",
                total_days=2,
                early_end_category="STRUCTURAL_COLLAPSE_CANDIDATE",
            ),
        ]
        # Attach dummy day start alives and events
        for r in results:
            r.day_start_alives = {1: 12, 2: 10}
            r.events = []

        report = run_endgame_audit(results)
        att = report.loss_attribution_9class
        self.assertEqual(att.counts["RULE_SPECIAL_DEFEAT"], 1)
        self.assertEqual(att.counts["EARLY_STRUCTURAL_COLLAPSE"], 1)
        self.assertEqual(att.total_losses, 2)


if __name__ == "__main__":
    unittest.main()
