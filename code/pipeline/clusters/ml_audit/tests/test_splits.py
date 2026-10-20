"""Random and scaffold splits: reproducible, disjoint, covering, validated."""

from __future__ import annotations

import pytest

from clusters.ml_audit.src.splits import (
    Split,
    assert_disjoint,
    random_split,
    scaffold_split,
)
from core.errors import ContractViolation

IDS = [f"c{i}" for i in range(20)]


def test_random_split_reproducible() -> None:
    assert random_split(IDS, seed=3) == random_split(IDS, seed=3)


def test_random_split_differs_by_seed() -> None:
    assert random_split(IDS, seed=3) != random_split(IDS, seed=4)


def test_scaffold_split_never_splits_groups() -> None:
    scaffolds = {
        "a1": "s1",
        "a2": "s1",
        "a3": "s1",
        "b1": "s2",
        "b2": "s2",
        "c1": "s3",
        "d1": "s4",
        "d2": "s4",
        "d3": "s4",
        "d4": "s4",
    }
    split = scaffold_split(scaffolds, frac_train=0.7)
    by_scaffold: dict[str, list[str]] = {}
    for compound_id, scaffold in scaffolds.items():
        by_scaffold.setdefault(scaffold, []).append(compound_id)
    for members in by_scaffold.values():
        in_train = sum(1 for m in members if m in split.train)
        assert in_train in (0, len(members))


def test_both_splits_cover_every_id_once() -> None:
    unique_scaffolds = {compound_id: f"s{i}" for i, compound_id in enumerate(IDS)}
    for split in (random_split(IDS), scaffold_split(unique_scaffolds)):
        combined = list(split.train) + list(split.validation)
        assert sorted(combined) == sorted(IDS)
        assert_disjoint(split)


def test_frac_train_out_of_range_raises() -> None:
    with pytest.raises(ContractViolation):
        random_split(IDS, frac_train=0.0)
    with pytest.raises(ContractViolation):
        random_split(IDS, frac_train=1.5)


def test_duplicate_ids_raise() -> None:
    with pytest.raises(ContractViolation):
        random_split(["a", "b", "a"])


def test_assert_disjoint_catches_overlap() -> None:
    split = Split(train=("a", "b"), validation=("b", "c"))
    with pytest.raises(ContractViolation, match="b"):
        assert_disjoint(split)
