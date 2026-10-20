"""Docking box construction for the P2Rank pockets.

## [EXPLORATORY]
"""

from __future__ import annotations

import math

from pydantic import BaseModel, ConfigDict

from core.errors import ContractViolation

# ## [ASSUMPTION: A1] cubic docking box edge, angstrom
BOX_EDGE_A: float = 24.0

# Centres are in the 8Z68 RCSB coordinate frame, keyed by P2Rank rank.
POCKET_CENTRES: dict[int, tuple[float, float, float]] = {
    1: (145.67, 128.56, 99.49),
    2: (129.32, 131.62, 117.61),
}

POCKET_ROLES: dict[int, str] = {1: "primary", 2: "negative_control"}


class DockingBox(BaseModel):
    """Axis-aligned cubic docking search box centred on a P2Rank pocket."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    pocket_id: int
    role: str
    center_x: float
    center_y: float
    center_z: float
    size_x: float
    size_y: float
    size_z: float


def _check_pocket_id(pocket_id: int) -> None:
    if pocket_id not in POCKET_CENTRES:
        raise ContractViolation(f"unknown pocket_id {pocket_id}; known ids: {sorted(POCKET_CENTRES)}")


def make_box(pocket_id: int, edge_a: float = BOX_EDGE_A) -> DockingBox:
    """Build the search box for one pocket."""
    _check_pocket_id(pocket_id)
    if not math.isfinite(edge_a) or edge_a <= 0:
        raise ContractViolation(f"edge_a must be finite and positive, got {edge_a!r}")
    cx, cy, cz = POCKET_CENTRES[pocket_id]
    return DockingBox(
        pocket_id=pocket_id,
        role=POCKET_ROLES[pocket_id],
        center_x=cx,
        center_y=cy,
        center_z=cz,
        size_x=edge_a,
        size_y=edge_a,
        size_z=edge_a,
    )


def box_as_dict(box: DockingBox) -> dict[str, float | int | str]:
    """Flat JSON-ready dict for a ``docking_box.json``."""
    return {
        "pocket_id": box.pocket_id,
        "role": box.role,
        "center_x": box.center_x,
        "center_y": box.center_y,
        "center_z": box.center_z,
        "size_x": box.size_x,
        "size_y": box.size_y,
        "size_z": box.size_z,
    }


def centre_separation(a: int, b: int) -> float:
    """Euclidean distance between two pocket centres.

    Pocket 2 is the site-discrimination negative control, so this distance is what
    separates the test site from its control.
    """
    _check_pocket_id(a)
    _check_pocket_id(b)
    return math.dist(POCKET_CENTRES[a], POCKET_CENTRES[b])
