"""Belief update logic processing perceptual events and evidence into score belief adjustments."""
from __future__ import annotations

from typing import Any

from src.cognition.player_state import PlayerState
from src.engine.types import DeathReason, PlayerId, RoleId


def update_belief_from_event(
    event: dict[str, Any],
    observer: PlayerState,
    alive_roster: dict[PlayerId, bool] | None = None,
) -> None:
    """Incrementally update an observer's score beliefs upon receiving or perceiving an event."""
    etype = event.get("type", "")
    data = event.get("data", {})
    actor = event.get("actor")
    target = event.get("target")

    # Skill factor modulates private evidence interpretation (alpha)
    acc = observer.skill.belief_accuracy
    # Conformity factor modulates social evidence influence (beta)
    conf = observer.personality.conformity

    if etype == "INFO_WASHERWOMAN":
        pair = data.get("players", [])
        for p in pair:
            if p in observer.score_beliefs and p != observer.player_id:
                observer.score_beliefs[p].good_score += 0.8 * acc

    elif etype == "INFO_LIBRARIAN":
        pair = data.get("players", [])
        for p in pair:
            if p in observer.score_beliefs and p != observer.player_id:
                observer.score_beliefs[p].good_score += 0.5 * acc

    elif etype == "INFO_INVESTIGATOR":
        pair = data.get("players", [])
        for p in pair:
            if p in observer.score_beliefs and p != observer.player_id:
                observer.score_beliefs[p].minion_score += 1.2 * acc

    elif etype == "INFO_FORTUNE_TELLER":
        targets = data.get("targets", [])
        result = data.get("result", False)
        for t in targets:
            if t in observer.score_beliefs and t != observer.player_id:
                if result:
                    observer.score_beliefs[t].demon_score += 1.0 * acc
                else:
                    observer.score_beliefs[t].demon_score -= 1.2 * acc
                    observer.score_beliefs[t].good_score += 0.4 * acc

    elif etype == "INFO_EMPATH":
        number = data.get("number", 0)
        # Empath updates living neighbors
        if alive_roster:
            alive_list = [p for p, a in alive_roster.items() if a]
            if observer.player_id in alive_list and len(alive_list) > 2:
                idx = alive_list.index(observer.player_id)
                left = alive_list[(idx - 1) % len(alive_list)]
                right = alive_list[(idx + 1) % len(alive_list)]
                neighbors = [left, right] if left != right else [left]
                if number == 0:
                    for n in neighbors:
                        if n in observer.score_beliefs:
                            observer.score_beliefs[n].good_score += 1.5 * acc
                            observer.score_beliefs[n].minion_score -= 1.0 * acc
                            observer.score_beliefs[n].demon_score -= 1.0 * acc
                elif number >= 1:
                    for n in neighbors:
                        if n in observer.score_beliefs:
                            observer.score_beliefs[n].minion_score += 0.8 * acc
                            observer.score_beliefs[n].demon_score += 0.8 * acc

    elif etype == "INFO_UNDERTAKER":
        role_str = data.get("executed_role")
        if target and target in observer.score_beliefs and target != observer.player_id:
            # Target's role revealed
            observer.score_beliefs[target].good_score += 1.0 * acc

    elif etype == "INFO_RAVENKEEPER":
        t = data.get("target")
        r = data.get("role")
        if t and t in observer.score_beliefs and t != observer.player_id:
            if r == RoleId.IMP.value:
                observer.score_beliefs[t].demon_score += 4.0 * acc
            else:
                observer.score_beliefs[t].good_score += 2.0 * acc

    elif etype == "DEATH":
        reason = data.get("reason")
        dead_p = target or actor
        # Night demon kill is typically good evidence (Delta s_evil < 0, but NOT P(G)=1 due to star-pass)
        if reason == DeathReason.DEMON_KILL.value and dead_p:
            if dead_p in observer.score_beliefs and dead_p != observer.player_id:
                observer.score_beliefs[dead_p].good_score += 1.5 * acc
                observer.score_beliefs[dead_p].demon_score -= 1.5 * acc
                observer.score_beliefs[dead_p].minion_score -= 0.5 * acc

    elif etype == "VIRGIN_PROC":
        # Nominator was executed by Virgin -> nominator confirmed Townsfolk
        nominator = target
        if nominator and nominator in observer.score_beliefs and nominator != observer.player_id:
            observer.score_beliefs[nominator].good_score += 3.0 * acc
            observer.score_beliefs[nominator].minion_score -= 2.0 * acc
            observer.score_beliefs[nominator].demon_score -= 2.0 * acc

    elif etype == "SLAYER_SHOT":
        success = data.get("success", False)
        # If shot failed, target is not demon
        if not success and target and target in observer.score_beliefs and target != observer.player_id:
            observer.score_beliefs[target].demon_score -= 2.0 * acc

    # --- Social Evidence Updates (modulated strictly by social conformity beta) ---
    elif etype == "PUBLIC_NOMINATION":
        # Seeing a player nominated raises social suspicion on them proportional to observer's conformity
        nominee = target or data.get("nominee")
        if nominee and nominee in observer.score_beliefs and nominee != observer.player_id:
            observer.score_beliefs[nominee].demon_score += 0.25 * conf
            observer.score_beliefs[nominee].minion_score += 0.20 * conf

    elif etype == "PUBLIC_CLAIM" or etype == "SOCIAL_ACCUSATION":
        accused = target or data.get("accused")
        direction = data.get("direction", "evil")
        if accused and accused in observer.score_beliefs and accused != observer.player_id:
            if direction == "evil":
                observer.score_beliefs[accused].demon_score += 0.35 * conf
                observer.score_beliefs[accused].minion_score += 0.25 * conf
            else:
                observer.score_beliefs[accused].good_score += 0.35 * conf

    elif etype == "SOCIAL_CONSENSUS":
        p = target or data.get("target")
        direction = data.get("direction", "evil")
        if p and p in observer.score_beliefs and p != observer.player_id:
            if direction == "evil":
                observer.score_beliefs[p].demon_score += 0.5 * conf
            else:
                observer.score_beliefs[p].good_score += 0.5 * conf

    # Update probabilities
    observer.refresh_beliefs()

