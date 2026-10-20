"""Read the eight scores. Pocket 2 is the site-discrimination negative control.

## [EXPLORATORY]
A more negative Vina score is a better score under this scoring function.
With four compounds this is a description of the pilot, not a claim that the
pocket discriminates.
"""

from __future__ import annotations

import math
from typing import Any

from core.errors import ContractViolation

ISOMER_PAIR = ("ogerin", "zinc32547799")


def paired_table(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One row per ligand with pocket 1, pocket 2, and their difference."""
    by_ligand: dict[str, dict[int, dict[str, Any]]] = {}
    for row in rows:
        by_ligand.setdefault(str(row["ligand"]), {})[int(row["pocket_id"])] = row
    table: list[dict[str, Any]] = []
    for ligand in sorted(by_ligand):
        pair = by_ligand[ligand]
        if 1 not in pair or 2 not in pair:
            continue
        score_1 = float(pair[1]["best_score_kcal_mol"])
        score_2 = float(pair[2]["best_score_kcal_mol"])
        table.append(
            {
                "ligand": ligand,
                "pocket_1": score_1,
                "pocket_2": score_2,
                "delta_p1_minus_p2": score_1 - score_2,
                "pocket_1_better": score_1 < score_2,
            }
        )
    return table


def discrimination(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Whether pocket 1 scores each known better than pocket 2."""
    table = paired_table(rows)
    better = [row["ligand"] for row in table if row["pocket_1_better"]]
    return {
        "label": "EXPLORATORY",
        "n_ligands": len(table),
        "pocket_1_better_than_pocket_2": better,
        "pocket_1_worse_or_equal": [row["ligand"] for row in table if not row["pocket_1_better"]],
        "all_four_prefer_pocket_1": len(better) == len(table) and len(table) == 4,
        "mean_delta_p1_minus_p2": _mean([row["delta_p1_minus_p2"] for row in table]),
        "pairs": table,
        "control": "Pocket 2 is a lipid-facing groove used as a site-discrimination negative control.",
    }


def isomer_resolution(
    rows: list[dict[str, Any]],
    oxygen_distance_pocket_1: float | None,
) -> dict[str, Any]:
    """Ogerin versus ZINC32547799, the ortho/meta hydroxymethyl pair.

    Scores are resolved when the pocket-1 best scores differ.
    Pose placement of the hydroxymethyl is reported as the distance between
    the single oxygen atoms of the two best pocket-1 poses, in the receptor frame.
    """
    scores: dict[tuple[str, int], float] = {}
    for row in rows:
        if row["ligand"] not in ISOMER_PAIR:
            continue
        scores[(str(row["ligand"]), int(row["pocket_id"]))] = float(row["best_score_kcal_mol"])
    pocket_1 = [scores.get((name, 1)) for name in ISOMER_PAIR]
    pocket_2 = [scores.get((name, 2)) for name in ISOMER_PAIR]
    if any(value is None for value in pocket_1):
        return {"resolved_by_score_pocket_1": None, "reason": "missing isomer scores"}
    delta_1 = float(pocket_1[0]) - float(pocket_1[1])  # type: ignore[arg-type]
    delta_2 = None if any(value is None for value in pocket_2) else float(pocket_2[0]) - float(pocket_2[1])  # type: ignore[arg-type]
    return {
        "pair": list(ISOMER_PAIR),
        "relationship": "positional isomers, ortho versus meta hydroxymethyl",
        "pocket_1_scores": {ISOMER_PAIR[0]: pocket_1[0], ISOMER_PAIR[1]: pocket_1[1]},
        "pocket_1_score_difference": delta_1,
        "pocket_2_score_difference": delta_2,
        "scores_differ_at_pocket_1": delta_1 != 0.0,
        "hydroxymethyl_oxygen_distance_A": oxygen_distance_pocket_1,
        "resolved_by_pocket_1_score": delta_1 != 0.0,
    }


def seconds_per_run(rows: list[dict[str, Any]]) -> dict[str, float]:
    values = [float(row["seconds"]) for row in rows]
    return {
        "n": float(len(values)),
        "mean_s": _mean(values),
        "min_s": min(values) if values else float("nan"),
        "max_s": max(values) if values else float("nan"),
    }


def oxygen_distance(
    left: tuple[tuple[float, float, float], ...],
    right: tuple[tuple[float, float, float], ...],
) -> float:
    """Distance between the sole oxygen of each isomer pose."""
    if len(left) != 1 or len(right) != 1:
        raise ContractViolation(f"expected one oxygen on each isomer, found {len(left)} and {len(right)}")
    return math.dist(left[0], right[0])


def _mean(values: list[float]) -> float:
    if not values:
        return float("nan")
    return sum(values) / len(values)
