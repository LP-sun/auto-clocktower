"""Trouble Brewing Death Pattern Consistency and Ability Constraints."""
from __future__ import annotations

from typing import Any

from src.engine.types import Alignment, CharacterType, PlayerId, RoleId
from src.reasoning.evidence import AtomicEvidence, EvidenceType
from src.reasoning.world import RoleSlot, SlotState, WorldHypothesis


def evaluate_death_pattern_consistency(
    world: WorldHypothesis,
    death_evidence: list[AtomicEvidence],
    living_players_by_day: dict[int, list[PlayerId]],
) -> tuple[float, list[dict[str, Any]], list[str]]:
    """Evaluate observed night deaths against hypothesized world roles (Monk, Soldier, Mayor, Imp)."""
    score_delta = 0.0
    explanations: list[dict[str, Any]] = []
    reason_codes: list[str] = []

    # Map deaths by day and source/phase
    night_deaths_by_day: dict[int, list[PlayerId]] = {}
    slayer_deaths: list[dict[str, Any]] = []

    for ev in death_evidence:
        if ev.evidence_type in (EvidenceType.DEATH_INFO, EvidenceType.ROLE_INFO):
            target = ev.content.get("dead_player") or ev.content.get("player_id") or ev.content.get("player") or ev.content.get("target")
            reason = ev.content.get("reason", "")
            d_day = ev.day
            if reason == "slayer_shot" or ev.content.get("slayer") or ev.content.get("type") == "SLAYER_KILL":
                slayer_deaths.append({"day": d_day, "target": target, "died": ev.content.get("died", True)})
            elif "night" in str(ev.phase).lower() or reason in ("demon_kill", "night_kill", "imp_kill", "") or "night" in ev.content:
                if target:
                    night_deaths_by_day.setdefault(d_day, []).append(target)

    # 1. Evaluate Slayer deaths
    for sd in slayer_deaths:
        t = sd["target"]
        t_slot = world.slots.get(t)
        died = sd.get("died", True)
        can_register_demon = (
            t == world.demon_player or
            (t_slot and t_slot.matches_role(RoleId.RECLUSE))
        )
        if died:
            if can_register_demon:
                score_delta += 1.5
                reason_codes.append(f"SLAYER_KILL_SUPPORTS_DEMON_{t}")
            else:
                score_delta -= 3.0
                reason_codes.append(f"SLAYER_KILL_CONTRADICTS_NON_DEMON_{t}")

    # 2. Evaluate No-Death Nights (0 night deaths)
    has_monk = any(s.matches_role(RoleId.MONK) for s in world.slots.values())
    has_soldier = any(s.matches_role(RoleId.SOLDIER) for s in world.slots.values())
    has_mayor = any(s.matches_role(RoleId.MAYOR) for s in world.slots.values())

    for d, deaths in night_deaths_by_day.items():
        if len(deaths) == 0 and d >= 2:
            # Plausible explanation: Monk protected target, Soldier attacked, or Mayor bounced
            if has_monk or has_soldier or has_mayor:
                score_delta += 0.5
                explanations.append({"type": "NO_DEATH_NIGHT_PROTECTED", "day": d})
                reason_codes.append(f"NO_DEATH_EXPLAINED_DAY_{d}")
            else:
                score_delta -= 1.2
                reason_codes.append(f"UNEXPLAINED_NO_DEATH_DAY_{d}")

        elif len(deaths) >= 1:
            for victim in deaths:
                v_slot = world.slots.get(victim)
                is_poisoned = any(
                    p.get("target") == victim for p in world.poison_history
                ) or victim == world.drunk_player

                # Soldier cannot die to demon at night unless poisoned/drunk
                if v_slot and v_slot.matches_role(RoleId.SOLDIER) and not is_poisoned:
                    score_delta -= 3.0
                    reason_codes.append(f"SOLDIER_NIGHT_DEATH_CONTRADICTION_{victim}")

                # Monk protected victim cannot die unless poisoned/drunk
                is_monk_protected = any(
                    ev.content.get("protected") == victim
                    for ev in death_evidence
                    if ev.content.get("type") in ("INFO_MONK", "ROLE_INFO") or "protected" in ev.content
                )
                if is_monk_protected and not is_poisoned:
                    score_delta -= 3.0
                    reason_codes.append(f"MONK_PROTECTED_DEATH_CONTRADICTION_{victim}")

                if victim == world.demon_player:
                    # Imp star pass
                    has_living_minions = any(
                        m in living_players_by_day.get(d, [])
                        for m in world.minion_players
                    )
                    if has_living_minions:
                        score_delta += 0.8
                        explanations.append({"type": "IMP_STAR_PASS", "day": d, "victim": victim})
                        reason_codes.append(f"IMP_STAR_PASS_DAY_{d}")
                    else:
                        score_delta -= 2.0
                        reason_codes.append(f"IMP_SELF_KILL_WITHOUT_MINION_DAY_{d}")

    return score_delta, explanations, reason_codes
