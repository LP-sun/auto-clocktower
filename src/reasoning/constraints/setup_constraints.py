"""Trouble Brewing Setup Constraints and Composition Legality Engine."""
from __future__ import annotations

from typing import Any

from src.engine.types import Alignment, CharacterType, PlayerId, RoleId
from src.reasoning.world import RoleSlot, SlotState, WorldHypothesis
from src.roles.trouble_brewing import ROLES


# Trouble Brewing base composition table: (Townsfolk, Outsiders, Minions, Demons)
TB_COMPOSITION: dict[int, tuple[int, int, int, int]] = {
    5: (3, 0, 1, 1),
    6: (3, 1, 1, 1),
    7: (5, 0, 1, 1),
    8: (5, 1, 1, 1),
    9: (5, 2, 1, 1),
    10: (7, 0, 2, 1),
    11: (7, 1, 2, 1),
    12: (7, 2, 2, 1),
    13: (9, 0, 3, 1),
    14: (9, 1, 3, 1),
    15: (9, 2, 3, 1),
}


def check_setup_legality(
    world: WorldHypothesis,
    total_players: int,
    observer_id: PlayerId,
    observer_alignment: Alignment,
) -> tuple[bool, str | None]:
    """Verify that a WorldHypothesis adheres strictly to Trouble Brewing setup legality."""
    # 1. Demon validity
    if not world.demon_player:
        return False, "NO_DEMON_ASSIGNED"
    if world.demon_player in world.minion_players:
        return False, "DEMON_CANNOT_BE_MINION"
    if world.demon_player in world.good_players:
        return False, "DEMON_CANNOT_BE_GOOD"
    if observer_alignment == Alignment.GOOD and world.demon_player == observer_id:
        return False, "GOOD_OBSERVER_CANNOT_BE_DEMON"

    # 2. Minions and Demons count
    base_counts = TB_COMPOSITION.get(total_players, (7, 2, 2, 1))
    base_tf, base_out, base_min, base_dem = base_counts

    if len(world.minion_players) != base_min:
        return False, f"MINION_COUNT_MISMATCH: expected {base_min}, got {len(world.minion_players)}"

    # 3. Baron modifier (+2 Outsiders, -2 Townsfolk)
    has_baron = any(
        world.slots.get(m) and world.slots[m].matches_role(RoleId.BARON)
        for m in world.minion_players
    )
    expected_outsiders = base_out + (2 if has_baron else 0)
    expected_townsfolk = base_tf - (2 if has_baron else 0)

    # 4. Drunk legality
    if world.drunk_player:
        if world.drunk_player not in world.good_players:
            return False, "DRUNK_MUST_BE_GOOD"
        if world.drunk_player in world.minion_players or world.drunk_player == world.demon_player:
            return False, "DRUNK_CANNOT_BE_EVIL"

    # 5. Role Duplication among KNOWN roles
    known_roles: list[RoleId] = []
    for p, slot in world.slots.items():
        if slot.state == SlotState.KNOWN and slot.role is not None:
            # Imp is the only demon; minions and townsfolk are singletons
            # (Drunk is technically an Outsider displaying a townsfolk role)
            if p == world.drunk_player:
                continue
            if slot.role in known_roles:
                return False, f"DUPLICATE_ROLE_ASSIGNMENT: {slot.role.value}"
            known_roles.append(slot.role)

    # 6. Character Type Counts among KNOWN roles (cannot exceed legal limits)
    known_tf_count = sum(
        1 for p, s in world.slots.items()
        if s.state == SlotState.KNOWN and s.role and ROLES[s.role].type == CharacterType.TOWNSFOLK and p != world.drunk_player
    )
    known_out_count = sum(
        1 for p, s in world.slots.items()
        if (s.state == SlotState.KNOWN and s.role and ROLES[s.role].type == CharacterType.OUTSIDER) or p == world.drunk_player
    )

    if known_tf_count > expected_townsfolk:
        return False, f"TOO_MANY_TOWNSFOLK: {known_tf_count} > {expected_townsfolk}"
    if known_out_count > expected_outsiders:
        return False, f"TOO_MANY_OUTSIDERS: {known_out_count} > {expected_outsiders}"

    return True, None
