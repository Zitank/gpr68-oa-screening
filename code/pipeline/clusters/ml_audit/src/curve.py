"""Learning curve, plateau rule, and the n extrapolation.

## [EXPLORATORY]
## [ASSUMPTION: A13] Training sizes are 25, 40, 55 and 70 percent of the labeled set.
## The curve has plateaued when the mean-AUC gain from the penultimate size to the largest
## is smaller than the standard error of that difference.
## [ASSUMPTION: A14] The 2.5th percentile of holdout ROC-AUC is fit as a + b/sqrt(n_train).
## A required n is reported only when that fit has R^2 >= 0.5, asymptote a > 0.5 and slope b < 0.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from clusters.ml_audit.src.holdouts import Holdout, _both_classes, _members
from clusters.ml_audit.src.model import holdout_auc
from core.errors import ContractViolation

# ## [ASSUMPTION: A13]
TRAIN_FRACTIONS = (0.25, 0.40, 0.55, 0.70)
_MIN_SCORES = 15
# ## [ASSUMPTION: A14]
_MIN_R2 = 0.5


@dataclass(frozen=True)
class CurvePoint:
    """Scores at one training size."""

    n_train: int
    aucs: tuple[float, ...]

    @property
    def mean(self) -> float:
        return float(np.mean(self.aucs))

    @property
    def low(self) -> float:
        return float(np.percentile(self.aucs, 2.5))

    @property
    def high(self) -> float:
        return float(np.percentile(self.aucs, 97.5))


def learning_points(
    features: np.ndarray,
    y: np.ndarray,
    groups: np.ndarray,
    holdouts: list[Holdout],
    *,
    seed: int,
) -> list[CurvePoint]:
    """Subsample each scaffold-holdout's train side and score the same test side."""
    n_rows = len(y)
    targets = [max(8, int(round(fraction * n_rows))) for fraction in TRAIN_FRACTIONS]
    buckets: dict[int, list[float]] = {target: [] for target in targets}
    members = _members(groups)
    rng = np.random.default_rng(seed)
    for index, holdout in enumerate(holdouts):
        for target in targets:
            subset = _subsample(holdout.train, members, y, target, rng)
            if subset is None:
                continue
            auc = holdout_auc(features, y, subset, holdout.test, seed=seed + index + target)
            buckets[target].append(auc)
    points = [CurvePoint(n_train=target, aucs=tuple(buckets[target])) for target in targets]
    return [point for point in points if len(point.aucs) >= _MIN_SCORES]


def plateaued(points: list[CurvePoint]) -> bool:
    """A13 plateau test on the two largest training sizes."""
    if len(points) < 2:
        raise ContractViolation("plateau test needs two training sizes")
    ordered = sorted(points, key=lambda point: point.n_train)
    earlier, later = ordered[-2], ordered[-1]
    gain = later.mean - earlier.mean
    se = float(np.sqrt(_se(earlier.aucs) ** 2 + _se(later.aucs) ** 2))
    return bool(gain < se)


def required_n(points: list[CurvePoint]) -> dict[str, float | str | None]:
    """A14 extrapolation. Returns status and n, or a reason n is not identified."""
    if len(points) < 3:
        return {
            "status": "not_identified",
            "n": None,
            "r2": None,
            "asymptote": None,
            "reason": "fewer than 3 sizes",
        }
    sizes = np.asarray([point.n_train for point in points], dtype=float)
    lows = np.asarray([point.low for point in points], dtype=float)
    slope, asymptote = np.polyfit(1.0 / np.sqrt(sizes), lows, 1)
    predicted = asymptote + slope / np.sqrt(sizes)
    r2 = _r2(lows, predicted)
    if r2 < _MIN_R2 or not np.isfinite(r2):
        return {
            "status": "not_identified",
            "n": None,
            "r2": float(r2),
            "asymptote": float(asymptote),
            "reason": "fit r2 below 0.5",
        }
    if asymptote <= 0.5 or slope >= 0:
        return {
            "status": "not_identified",
            "n": None,
            "r2": float(r2),
            "asymptote": float(asymptote),
            "reason": "lower band does not rise toward a value above 0.5",
        }
    # a + b/sqrt(n) = 0.5 => sqrt(n) = b / (0.5 - a) => n = (b / (0.5 - a))^2
    estimate = (float(slope) / (0.5 - float(asymptote))) ** 2
    if not np.isfinite(estimate) or estimate <= 0:
        return {
            "status": "not_identified",
            "n": None,
            "r2": float(r2),
            "asymptote": float(asymptote),
            "reason": "non-finite n",
        }
    return {
        "status": "estimated",
        "n": float(estimate),
        "r2": float(r2),
        "asymptote": float(asymptote),
        "reason": "",
    }


def _subsample(
    train: np.ndarray,
    members: dict[str, np.ndarray],
    y: np.ndarray,
    target: int,
    rng: np.random.Generator,
) -> np.ndarray | None:
    in_train = set(train.tolist())
    blocks = [name for name, index in members.items() if set(index.tolist()).issubset(in_train)]
    if not blocks:
        return None
    chosen: list[int] = []
    for name in rng.permutation(np.asarray(blocks, dtype=object)):
        block = members[str(name)]
        if len(chosen) >= target:
            break
        if chosen and len(chosen) + len(block) > int(target * 1.25):
            continue
        chosen.extend(block.tolist())
    if len(chosen) < 8:
        return None
    subset = np.asarray(chosen, dtype=int)
    if not _both_classes(y, subset):
        return None
    return subset


def _se(values: tuple[float, ...]) -> float:
    arr = np.asarray(values, dtype=float)
    if arr.size < 2:
        return float("inf")
    return float(np.std(arr, ddof=1) / np.sqrt(arr.size))


def _r2(observed: np.ndarray, predicted: np.ndarray) -> float:
    total = float(np.sum((observed - np.mean(observed)) ** 2))
    if total == 0.0:
        return 0.0
    residual = float(np.sum((observed - predicted) ** 2))
    return 1.0 - residual / total
