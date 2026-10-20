"""Docking box construction: exact centres, sizes, and validation."""

from __future__ import annotations

import math

import pytest

from clusters.pocket.src.box import (
    BOX_EDGE_A,
    POCKET_CENTRES,
    POCKET_ROLES,
    box_as_dict,
    centre_separation,
    make_box,
)
from core.errors import ContractViolation


def test_known_good_box() -> None:
    box = make_box(1)
    assert box.center_x == 145.67
    assert box.center_y == 128.56
    assert box.center_z == 99.49
    assert box.size_x == BOX_EDGE_A == 24.0
    assert box.size_y == BOX_EDGE_A
    assert box.size_z == BOX_EDGE_A
    assert box.role == POCKET_ROLES[1]


def test_unknown_pocket_raises() -> None:
    with pytest.raises(ContractViolation, match="known ids"):
        make_box(99)


def test_nonpositive_edge_raises() -> None:
    with pytest.raises(ContractViolation):
        make_box(1, edge_a=0)
    with pytest.raises(ContractViolation):
        make_box(1, edge_a=-1)


def test_centre_separation_hand_computed() -> None:
    expected = math.sqrt((145.67 - 129.32) ** 2 + (128.56 - 131.62) ** 2 + (99.49 - 117.61) ** 2)
    assert centre_separation(1, 2) == pytest.approx(expected)
    assert centre_separation(1, 1) == 0.0


def test_box_as_dict_flat() -> None:
    box = make_box(2)
    assert box_as_dict(box) == {
        "pocket_id": 2,
        "role": "negative_control",
        "center_x": POCKET_CENTRES[2][0],
        "center_y": POCKET_CENTRES[2][1],
        "center_z": POCKET_CENTRES[2][2],
        "size_x": 24.0,
        "size_y": 24.0,
        "size_z": 24.0,
    }
