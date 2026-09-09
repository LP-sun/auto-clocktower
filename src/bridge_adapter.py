"""Compatibility bridge adapter exposing the mathematical Storyteller to external callers (e.g. Node.js bridge)."""
from __future__ import annotations

import json
import sys
from typing import Any

from src.engine.game import ClocktowerEngine
from src.engine.types import PlayerId, RoleId, STDecisionType
from src.storyteller.st_policy import StorytellerPolicy


def evaluate_st_decision_json(payload: dict[str, Any]) -> dict[str, Any]:
    """Evaluate a Storyteller decision from a JSON payload and return structured results."""
    dtype_str = payload.get("decision_type", "drunk_poison_misinfo")
    decision_type = STDecisionType(dtype_str)
    actor = payload.get("actor")
    player_count = payload.get("player_count", 12)
    seed = payload.get("seed", 42)

    engine = ClocktowerEngine.create(player_count=player_count, seed=seed)
    st_policy = StorytellerPolicy(seed=seed)

    suspicions = payload.get("suspicions", {})
    chosen = st_policy.decide(
        decision_type=decision_type,
        state=engine.state,
        actor=actor,
        suspicions=suspicions,
    )

    last_record = st_policy.decisions_log[-1] if st_policy.decisions_log else None

    return {
        "chosen_action": chosen,
        "record": last_record.to_dict() if last_record else None,
    }


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "--json":
        raw = sys.stdin.read()
        payload = json.loads(raw)
        result = evaluate_st_decision_json(payload)
        print(json.dumps(result, ensure_ascii=False))
    else:
        print("BotC Math ST Bridge Adapter ready.")


if __name__ == "__main__":
    main()
