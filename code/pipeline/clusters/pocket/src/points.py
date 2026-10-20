"""P2Rank point groups. ``resSeq`` is the pocket rank.

## [EXPLORATORY]
Group 0 is unassigned surface and is ignored. Ranking by summed per-point score
reproduces ranks 1..7; ranking by point count does not.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from clusters.pocket.src.facts import PLAN_CENTRES
from clusters.pocket.src.pdbio import iter_atoms
from core.errors import ContractViolation

# B-factor column holds the per-point score in this P2Rank points file.
_SCORE_SLICE = slice(60, 66)


@dataclass(frozen=True)
class PocketPoints:
    """One resSeq group with resSeq != 0."""

    pocket_id: int
    xyz: tuple[tuple[float, float, float], ...]
    scores: tuple[float, ...]

    @property
    def count(self) -> int:
        return len(self.xyz)

    @property
    def score_sum(self) -> float:
        return sum(self.scores)

    @property
    def score_max(self) -> float:
        return max(self.scores)

    @property
    def centre_mean(self) -> tuple[float, float, float]:
        n = self.count
        return (
            sum(p[0] for p in self.xyz) / n,
            sum(p[1] for p in self.xyz) / n,
            sum(p[2] for p in self.xyz) / n,
        )

    @property
    def extent_min(self) -> tuple[float, float, float]:
        return (
            min(p[0] for p in self.xyz),
            min(p[1] for p in self.xyz),
            min(p[2] for p in self.xyz),
        )

    @property
    def extent_max(self) -> tuple[float, float, float]:
        return (
            max(p[0] for p in self.xyz),
            max(p[1] for p in self.xyz),
            max(p[2] for p in self.xyz),
        )

    @property
    def span(self) -> tuple[float, float, float]:
        lo, hi = self.extent_min, self.extent_max
        return (hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2])


def _score(line: str) -> float:
    if len(line) < 66:
        raise ContractViolation(f"points record has no B-factor score column: {line!r}")
    try:
        return float(line[_SCORE_SLICE])
    except ValueError as exc:
        raise ContractViolation(f"unreadable point score: {line!r}") from exc


def read_pockets(text: str) -> dict[int, PocketPoints]:
    """Group points by resSeq. Group 0 is dropped. Ids must be exactly 1..7."""
    buckets: dict[int, list[tuple[tuple[float, float, float], float]]] = defaultdict(list)
    for atom in iter_atoms(text):
        if not atom.line.startswith("HETATM"):
            raise ContractViolation("P2Rank points file contains a non-HETATM atom record")
        buckets[atom.resseq].append((atom.xyz, _score(atom.line)))
    if 0 not in buckets:
        raise ContractViolation("points file has no resSeq 0 unassigned-surface group")
    pockets = {
        pocket_id: PocketPoints(
            pocket_id=pocket_id,
            xyz=tuple(item[0] for item in items),
            scores=tuple(item[1] for item in items),
        )
        for pocket_id, items in buckets.items()
        if pocket_id != 0
    }
    if sorted(pockets) != [1, 2, 3, 4, 5, 6, 7]:
        raise ContractViolation(f"expected pocket ids 1..7, found {sorted(pockets)}")
    _require_score_rank(pockets)
    _require_plan_centres(pockets)
    return pockets


def rank_by_score_sum(pockets: dict[int, PocketPoints]) -> list[int]:
    """Pocket ids ordered by descending summed per-point score."""
    return sorted(pockets, key=lambda pocket_id: (-pockets[pocket_id].score_sum, pocket_id))


def rank_by_count(pockets: dict[int, PocketPoints]) -> list[int]:
    """Pocket ids ordered by descending point count. This is not the P2Rank rank."""
    return sorted(pockets, key=lambda pocket_id: (-pockets[pocket_id].count, pocket_id))


def _require_score_rank(pockets: dict[int, PocketPoints]) -> None:
    ranked = rank_by_score_sum(pockets)
    if ranked != [1, 2, 3, 4, 5, 6, 7]:
        raise ContractViolation(f"score-sum rank is {ranked}, not 1..7; refusing to relabel pockets")
    if rank_by_count(pockets) == [1, 2, 3, 4, 5, 6, 7]:
        raise ContractViolation("point-count rank reproduced 1..7; the plan says it must not")


def _require_plan_centres(pockets: dict[int, PocketPoints]) -> None:
    """The plan's two-decimal centres are the rounded means. A mismatch is fatal."""
    for pocket_id, stated in PLAN_CENTRES.items():
        mean = pockets[pocket_id].centre_mean
        rounded = tuple(round(value, 2) for value in mean)
        if rounded != stated:
            raise ContractViolation(
                f"pocket {pocket_id} mean {mean} rounds to {rounded}, plan states {stated}. "
                "Refusing to replace the plan centre."
            )


def docking_centre(pockets: dict[int, PocketPoints], pocket_id: int) -> tuple[float, float, float]:
    """Centre used for a search box.

    Pockets 1 and 2 return the plan's exact stated values. Other pockets return the
    point-mean rounded to two decimal places, which is how pockets 1 and 2 were stated.
    """
    if pocket_id in PLAN_CENTRES:
        return PLAN_CENTRES[pocket_id]
    mean = pockets[pocket_id].centre_mean
    return (round(mean[0], 2), round(mean[1], 2), round(mean[2], 2))
