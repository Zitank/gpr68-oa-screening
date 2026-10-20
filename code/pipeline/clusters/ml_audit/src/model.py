"""Random forest used for the Q-003 audit.

## [EXPLORATORY]
## [ASSUMPTION: A17] RandomForestClassifier, 40 trees, max_depth 6, min_samples_leaf 2,
## max_features sqrt, class_weight balanced. Tree count and depth are fixed for runtime
## on this machine; they are not tuned to the AUC.
"""

from __future__ import annotations

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import roc_auc_score

from core.errors import ContractViolation

# ## [ASSUMPTION: A17]
N_ESTIMATORS = 40
MAX_DEPTH = 6
MIN_SAMPLES_LEAF = 2


def holdout_auc(
    features: np.ndarray,
    y: np.ndarray,
    train: np.ndarray,
    test: np.ndarray,
    *,
    seed: int,
) -> float:
    """ROC-AUC of one forest. Both sides must already contain both classes."""
    forest = RandomForestClassifier(
        n_estimators=N_ESTIMATORS,
        max_depth=MAX_DEPTH,
        min_samples_leaf=MIN_SAMPLES_LEAF,
        max_features="sqrt",
        class_weight="balanced",
        random_state=seed,
        n_jobs=1,
    )
    forest.fit(features[train], y[train])
    if list(forest.classes_) != [0, 1]:
        raise ContractViolation(f"forest classes were {list(forest.classes_)}, expected [0, 1]")
    scores = forest.predict_proba(features[test])[:, 1]
    return float(roc_auc_score(y[test], scores))


def score_holdouts(
    features: np.ndarray,
    y: np.ndarray,
    holdouts: list,
    *,
    seed: int,
) -> list[float]:
    """AUC for every holdout that still has both classes under ``y``."""
    scores: list[float] = []
    for index, holdout in enumerate(holdouts):
        if set(np.unique(y[holdout.train]).tolist()) != {0, 1}:
            continue
        if set(np.unique(y[holdout.test]).tolist()) != {0, 1}:
            continue
        scores.append(holdout_auc(features, y, holdout.train, holdout.test, seed=seed + index))
    return scores
