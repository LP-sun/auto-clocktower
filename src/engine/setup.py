"""Player distribution, role generation, and initial game setup for Trouble Brewing."""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Mapping

from src.engine.types import Alignment, CharacterType, PlayerId, RoleId
from src.roles.trouble_brewing import ROLES

# Standard BotC distribution table: player_count -> (townsfolk, outsider, minion, demon)
DISTRIBUTION_TABLE: Mapping[int, tuple[int, int, int, int]] = {
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


@dataclass(slots=True)
class SetupResult:
    players: list[PlayerId]
    true_roles: dict[PlayerId, RoleId]
    apparent_roles: dict[PlayerId, RoleId]  # Drunk sees their fake townsfolk token
    alignments: dict[PlayerId, Alignment]
    drunk_fake_role: RoleId | None
    red_herring: PlayerId | None
    imp_bluffs: list[RoleId]


def get_base_distribution(player_count: int) -> tuple[int, int, int, int]:
    if player_count not in DISTRIBUTION_TABLE:
        raise ValueError(f"Unsupported player count: {player_count}. Expected 5-15.")
    return DISTRIBUTION_TABLE[player_count]


def generate_setup(
    player_count: int = 12,
    seed: int | None = None,
    custom_roles: dict[PlayerId, RoleId] | None = None,
    custom_drunk_fake: RoleId | None = None,
    custom_red_herring: PlayerId | None = None,
) -> SetupResult:
    """Generate a valid, deterministic Trouble Brewing role distribution and initial assignments."""
    rng = random.Random(seed)
    players = [f"P{i+1:02d}" for i in range(player_count)]

    if custom_roles is not None:
        # Predefined roles setup (e.g. for deterministic unit testing)
        true_roles = dict(custom_roles)
        apparent_roles = dict(custom_roles)
        alignments = {
            p: Alignment.GOOD if ROLES[r].type in (CharacterType.TOWNSFOLK, CharacterType.OUTSIDER) else Alignment.EVIL
            for p, r in true_roles.items()
        }
        drunk_fake = custom_drunk_fake
        drunk_player = next((p for p, r in true_roles.items() if r == RoleId.DRUNK), None)
        if drunk_player and drunk_fake:
            apparent_roles[drunk_player] = drunk_fake

        # Red herring
        red_herring = custom_red_herring
        if red_herring is None and any(r == RoleId.FORTUNE_TELLER for r in true_roles.values()):
            good_players = [p for p, a in alignments.items() if a == Alignment.GOOD]
            red_herring = rng.choice(good_players) if good_players else None

        # Bluffs
        unused_good = [
            r for r, d in ROLES.items()
            if d.type in (CharacterType.TOWNSFOLK, CharacterType.OUTSIDER)
            and r not in true_roles.values()
            and r != drunk_fake
        ]
        bluffs = rng.sample(unused_good, min(3, len(unused_good)))

        return SetupResult(
            players=players,
            true_roles=true_roles,
            apparent_roles=apparent_roles,
            alignments=alignments,
            drunk_fake_role=drunk_fake,
            red_herring=red_herring,
            imp_bluffs=bluffs,
        )

    # 1. Base counts
    tf_count, out_count, min_count, demon_count = get_base_distribution(player_count)

    # 2. Select Minions and Demon
    all_minions = [r for r, d in ROLES.items() if d.type == CharacterType.MINION]
    selected_minions = rng.sample(all_minions, min_count)
    selected_demon = [RoleId.IMP]

    # Baron modifier: +2 Outsiders, -2 Townsfolk
    if RoleId.BARON in selected_minions:
        out_count += 2
        tf_count -= 2

    # 3. Select Outsiders and Townsfolk
    all_outsiders = [r for r, d in ROLES.items() if d.type == CharacterType.OUTSIDER]
    selected_outsiders = rng.sample(all_outsiders, out_count)

    all_townsfolk = [r for r, d in ROLES.items() if d.type == CharacterType.TOWNSFOLK]
    selected_townsfolk = rng.sample(all_townsfolk, tf_count)

    # 4. Pool of in-game roles
    in_game_roles = selected_townsfolk + selected_outsiders + selected_minions + selected_demon
    rng.shuffle(in_game_roles)

    true_roles: dict[PlayerId, RoleId] = {players[i]: in_game_roles[i] for i in range(player_count)}
    apparent_roles: dict[PlayerId, RoleId] = dict(true_roles)

    alignments = {
        p: Alignment.GOOD if ROLES[r].type in (CharacterType.TOWNSFOLK, CharacterType.OUTSIDER) else Alignment.EVIL
        for p, r in true_roles.items()
    }

    # 5. Handle Drunk assignment
    drunk_fake: RoleId | None = None
    drunk_player = next((p for p, r in true_roles.items() if r == RoleId.DRUNK), None)
    if drunk_player:
        unused_townsfolk = [r for r in all_townsfolk if r not in true_roles.values()]
        drunk_fake = rng.choice(unused_townsfolk)
        apparent_roles[drunk_player] = drunk_fake

    # 6. Red Herring for Fortune Teller
    red_herring: PlayerId | None = None
    if any(r == RoleId.FORTUNE_TELLER for r in true_roles.values()):
        good_players = [p for p, a in alignments.items() if a == Alignment.GOOD]
        red_herring = rng.choice(good_players) if good_players else None

    # 7. Imp bluffs (3 unused Good roles)
    unused_good = [
        r for r, d in ROLES.items()
        if d.type in (CharacterType.TOWNSFOLK, CharacterType.OUTSIDER)
        and r not in true_roles.values()
        and r != drunk_fake
    ]
    bluffs = rng.sample(unused_good, min(3, len(unused_good)))

    return SetupResult(
        players=players,
        true_roles=true_roles,
        apparent_roles=apparent_roles,
        alignments=alignments,
        drunk_fake_role=drunk_fake,
        red_herring=red_herring,
        imp_bluffs=bluffs,
    )
