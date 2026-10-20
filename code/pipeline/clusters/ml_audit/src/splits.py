"""Scaffold-aware versus random splitting for a later generalisation gap.

## [EXPLORATORY]
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np
from pydantic import BaseModel, ConfigDict

from core.errors import ContractViolation


class Split(BaseModel):
    """Deterministic train/validation split of compound ids."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    train: tuple[str, ...]
    validation: tuple[str, ...]


def random_split(ids: Sequence[str], frac_train: float = 0.8, seed: int = 0) -> Split:
    """Shuffle ids with a seeded RNG and cut at the train fraction."""
    unique = _validate_ids(ids, frac_train)
    order = np.random.default_rng(seed).permutation(len(unique)).tolist()
    shuffled = [unique[i] for i in order]
    n_train = round(frac_train * len(unique))
    return _build_split(shuffled[:n_train], shuffled[n_train:])


def scaffold_split(scaffolds: Mapping[str, str], frac_train: float = 0.8) -> Split:
    """Greedy whole-scaffold split: fill train until the target size is exceeded."""
    unique = _validate_ids(list(scaffolds.keys()), frac_train)
    groups: dict[str, list[str]] = {}
    for compound_id in unique:
        groups.setdefault(scaffolds[compound_id], []).append(compound_id)
    ordered = sorted(groups.items(), key=lambda item: (-len(item[1]), item[0]))
    target = round(frac_train * len(unique))
    train: list[str] = []
    for _, members in ordered:
        if len(train) + len(members) > target:
            break
        train.extend(members)
    validation = [compound_id for compound_id in unique if compound_id not in train]
    return _build_split(train, validation)


def assert_disjoint(split: Split) -> None:
    """Reject any overlap between train and validation."""
    overlap = set(split.train) & set(split.validation)
    if overlap:
        raise ContractViolation(f"train and validation overlap on ids {sorted(overlap)}")


def _validate_ids(ids: Sequence[str], frac_train: float) -> list[str]:
    if not ids:
        raise ContractViolation("cannot split an empty id list")
    if not 0.0 < frac_train < 1.0:
        raise ContractViolation(f"frac_train must be between 0 and 1, got {frac_train}")
    unique = list(dict.fromkeys(ids))
    seen: set[str] = set()
    duplicates: set[str] = set()
    for item in ids:
        if item in seen:
            duplicates.add(item)
        seen.add(item)
    if duplicates:
        raise ContractViolation(f"duplicate ids in split input: {sorted(duplicates)}")
    return unique


def _build_split(train: list[str], validation: list[str]) -> Split:
    if not train:
        raise ContractViolation("split produced an empty train side")
    if not validation:
        raise ContractViolation("split produced an empty validation side")
    return Split(train=tuple(train), validation=tuple(validation))
