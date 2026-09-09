"""Dataset exporter generating structured training data for AI Storyteller models."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Sequence

from src.simulation.runner import SimulationResult
from src.storyteller.types import STDecisionRecord


def export_st_dataset(records: Sequence[STDecisionRecord], output_file: str | Path) -> int:
    """Export Storyteller decision samples to JSONL format for imitation learning or SFT."""
    path = Path(output_file)
    path.parent.mkdir(parents=True, exist_ok=True)

    count = 0
    with path.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec.to_dict(), ensure_ascii=False) + "\n")
            count += 1
    return count


def export_trajectories(results: Sequence[SimulationResult], output_file: str | Path) -> int:
    """Export complete game trajectories to JSONL format."""
    path = Path(output_file)
    path.parent.mkdir(parents=True, exist_ok=True)

    count = 0
    with path.open("w", encoding="utf-8") as f:
        for r in results:
            data = {
                "seed": r.seed,
                "player_count": r.player_count,
                "winner": r.winner.value if r.winner else None,
                "end_reason": r.end_reason,
                "total_days": r.total_days,
                "true_roles": r.true_roles,
                "events": r.events,
            }
            f.write(json.dumps(data, ensure_ascii=False) + "\n")
            count += 1
    return count
