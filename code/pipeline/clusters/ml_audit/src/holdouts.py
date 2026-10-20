"""Repeated scaffold and stratified holdouts.

## [EXPLORATORY]
## [ASSUMPTION: A18] Test fraction is 0.25. A scaffold moves to the test set only as a whole.
## A scaffold stays in train when adding it would push the test set past 1.5 times the target,
## unless the test set is still empty.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.model_selection import StratifiedShuffleSplit

from core.errors import ContractViolation

# ## [ASSUMPTION: A18]
TEST_FRACTION = 0.25
_OVERSHOOT = 1.5


@dataclass(frozen=True)
class Holdout:
    """Integer positions into the modeling table."""

    train: np.ndarray
    test: np.ndarray


def scaffold_holdouts(
    groups: np.ndarray,
    y: np.ndarray,
    *,
    n_attempts: int,
    seed: int,
) -> tuple[list[Holdout], int]:
    """Seeded scaffold holdouts that keep both classes on each side.

    Returns the kept holdouts and how many attempts were dropped.
    """
    if len(groups) != len(y):
        raise ContractViolation("groups and labels have different lengths")
    rng = np.random.default_rng(seed)
    members = _members(groups)
    order = list(members)
    target = max(2, int(round(TEST_FRACTION * len(y))))
    kept: list[Holdout] = []
    dropped = 0
    for _ in range(n_attempts):
        holdout = _one_scaffold_holdout(order, members, len(y), target, rng)
        if holdout is not None and _both_classes(y, holdout.train) and _both_classes(y, holdout.test):
            kept.append(holdout)
        else:
            dropped += 1
    return kept, dropped


def random_holdouts(y: np.ndarray, *, n_splits: int, seed: int) -> list[Holdout]:
    """Stratified shuffle splits with the same test fraction as the scaffold holdouts."""
    if n_splits < 1:
        raise ContractViolation("random holdouts need at least one split")
    splitter = StratifiedShuffleSplit(n_splits=n_splits, test_size=TEST_FRACTION, random_state=seed)
    dummy = np.zeros(len(y))
    return [Holdout(train=train, test=test) for train, test in splitter.split(dummy, y)]


def _one_scaffold_holdout(
    order: list[str],
    members: dict[str, np.ndarray],
    n_rows: int,
    target: int,
    rng: np.random.Generator,
) -> Holdout | None:
    test: list[int] = []
    for name in rng.permutation(np.asarray(order, dtype=object)):
        block = members[str(name)].tolist()
        if len(test) >= target:
            break
        if test and len(test) + len(block) > int(target * _OVERSHOOT):
            continue
        test.extend(block)
    test_index = np.asarray(test, dtype=int)
    if test_index.size == 0 or test_index.size == n_rows:
        return None
    mask = np.ones(n_rows, dtype=bool)
    mask[test_index] = False
    train_index = np.flatnonzero(mask)
    return Holdout(train=train_index, test=test_index)


def _members(groups: np.ndarray) -> dict[str, np.ndarray]:
    grouped: dict[str, list[int]] = {}
    for index, name in enumerate(groups.tolist()):
        grouped.setdefault(str(name), []).append(index)
    return {name: np.asarray(indexes, dtype=int) for name, indexes in grouped.items()}


def _both_classes(y: np.ndarray, index: np.ndarray) -> bool:
    return set(np.unique(y[index]).tolist()) == {0, 1}
