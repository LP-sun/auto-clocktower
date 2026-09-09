"""Type definitions and enumerations for Blood on the Clocktower (Trouble Brewing)."""
from __future__ import annotations

from enum import Enum, unique


@unique
class CharacterType(str, Enum):
    TOWNSFOLK = "Townsfolk"
    OUTSIDER = "Outsider"
    MINION = "Minion"
    DEMON = "Demon"


@unique
class Alignment(str, Enum):
    GOOD = "good"
    EVIL = "evil"


@unique
class GamePhase(str, Enum):
    SETUP = "setup"
    FIRST_NIGHT = "first_night"
    NIGHT = "night"
    DAWN = "dawn"
    DAY_PRIVATE = "day_private"
    DAY_PUBLIC = "day_public"
    NOMINATION = "nomination"
    VOTING = "voting"
    DUSK = "dusk"
    ENDED = "ended"


@unique
class RoleId(str, Enum):
    # Townsfolk (13)
    WASHERWOMAN = "washerwoman"
    LIBRARIAN = "librarian"
    INVESTIGATOR = "investigator"
    CHEF = "chef"
    EMPATH = "empath"
    FORTUNE_TELLER = "fortune_teller"
    UNDERTAKER = "undertaker"
    MONK = "monk"
    RAVENKEEPER = "ravenkeeper"
    VIRGIN = "virgin"
    SLAYER = "slayer"
    SOLDIER = "soldier"
    MAYOR = "mayor"

    # Outsiders (4)
    BUTLER = "butler"
    DRUNK = "drunk"
    RECLUSE = "recluse"
    SAINT = "saint"

    # Minions (4)
    POISONER = "poisoner"
    SPY = "spy"
    SCARLET_WOMAN = "scarlet_woman"
    BARON = "baron"

    # Demon (1)
    IMP = "imp"


@unique
class DeathReason(str, Enum):
    DEMON_KILL = "demon_kill"
    EXECUTION = "execution"
    VIRGIN_PROC = "virgin_proc"
    SLAYER_SHOT = "slayer_shot"
    STAR_PASS = "star_pass"


@unique
class ActionType(str, Enum):
    # Night Actions
    CHOOSE = "choose"
    PASS_NIGHT = "pass_night"

    # Day Actions
    IDLE = "idle"
    SLAY = "slay"
    NOMINATE = "nominate"
    PASS_NOMINATION = "pass_nomination"
    VOTE_YES = "vote_yes"
    VOTE_NO = "vote_no"

    # Social Actions
    PUBLIC_SPEECH = "public_speech"
    WHISPER = "whisper"


@unique
class SpeechActType(str, Enum):
    CLAIM = "CLAIM"
    SOFT_CLAIM = "SOFT_CLAIM"
    SHARE_INFO = "SHARE_INFO"
    REQUEST_INFO = "REQUEST_INFO"
    ACCUSE = "ACCUSE"
    DEFEND = "DEFEND"
    QUESTION = "QUESTION"
    AGREE = "AGREE"
    DISAGREE = "DISAGREE"
    PROPOSE_WORLD = "PROPOSE_WORLD"
    NOMINATE_INTENT = "NOMINATE_INTENT"
    EXECUTION_SUPPORT = "EXECUTION_SUPPORT"


@unique
class STDecisionType(str, Enum):
    SETUP_DISTRIBUTION = "setup_distribution"
    DRUNK_FAKE_ROLE = "drunk_fake_role"
    RED_HERRING_SELECTION = "red_herring_selection"
    IMP_BLUFFS = "imp_bluffs"
    INFO_GENERATION = "info_generation"
    DRUNK_POISON_MISINFO = "drunk_poison_misinfo"
    SPY_REGISTRATION = "spy_registration"
    RECLUSE_REGISTRATION = "recluse_registration"
    MAYOR_BOUNCE = "mayor_bounce"
    DISCUSSION_PACING = "discussion_pacing"


@unique
class SkillLevel(str, Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    EXPERIENCED = "experienced"
    EXPERT = "expert"


PlayerId = str  # Format: "P01", "P02", ..., "P12"
