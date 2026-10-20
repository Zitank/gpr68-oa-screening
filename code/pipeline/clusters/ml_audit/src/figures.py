"""Figures for the Q-003 audit.

## [EXPLORATORY]
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from clusters.ml_audit.src.curve import CurvePoint
from clusters.ml_audit.src.domain import SUBSTITUTION


def write_split_figure(scaffold: list[float], random_scores: list[float], path: Path) -> None:
    """Side-by-side holdout ROC-AUC distributions."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, axis = plt.subplots(figsize=(7.2, 4.4))
    axis.hist(scaffold, bins=12, alpha=0.75, label="Scaffold holdout", color="#1f4e79")
    axis.hist(random_scores, bins=12, alpha=0.55, label="Random holdout", color="#d9782d")
    axis.axvline(0.5, color="black", linestyle="--", linewidth=1, label="Chance")
    axis.set_xlabel("ROC-AUC")
    axis.set_ylabel("Holdouts")
    axis.set_title("AID 2060853 random forest: scaffold split versus random split")
    axis.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def write_curve_figure(points: list[CurvePoint], n_labeled: int, path: Path) -> None:
    """Learning curve with the 2.5–97.5 percentile band."""
    path.parent.mkdir(parents=True, exist_ok=True)
    order = sorted(points, key=lambda point: point.n_train)
    xs = [point.n_train for point in order]
    fig, axis = plt.subplots(figsize=(7.2, 4.4))
    axis.fill_between(
        xs, [point.low for point in order], [point.high for point in order], color="#1f4e79", alpha=0.25
    )
    axis.plot(xs, [point.mean for point in order], color="#1f4e79", marker="o", label="Mean ROC-AUC")
    axis.axhline(0.5, color="black", linestyle="--", linewidth=1)
    axis.axvline(n_labeled, color="#666666", linestyle=":", linewidth=1, label=f"Labeled n = {n_labeled}")
    axis.set_xlabel("Training molecules (scaffold-respecting subsample)")
    axis.set_ylabel("ROC-AUC on the held-out scaffolds")
    axis.set_title("Learning curve, AID 2060853, Morgan random forest")
    axis.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def write_scramble_figure(null_medians: list[float], observed: float, path: Path) -> None:
    """Y-scrambling null with the real median marked."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, axis = plt.subplots(figsize=(7.2, 4.4))
    axis.hist(null_medians, bins=12, color="#8d99a6", label="Label-permuted medians")
    axis.axvline(observed, color="#1f4e79", linewidth=2, label="Real median")
    axis.set_xlabel("Median scaffold-holdout ROC-AUC")
    axis.set_ylabel("Permutations")
    axis.set_title("Y-scrambling null, AID 2060853")
    axis.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def write_domain_figure(max_tanimoto: list[float], threshold: float, path: Path) -> None:
    """Nearest-neighbour similarities. The title states the library substitution."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, axis = plt.subplots(figsize=(7.4, 4.6))
    axis.hist(max_tanimoto, bins=15, color="#1f4e79")
    axis.axvline(threshold, color="#d9782d", linewidth=2, label=f"In-domain threshold {threshold:.2f}")
    axis.set_xlabel("Max Morgan Tanimoto to the AID 2060853 set")
    axis.set_ylabel("Substitute molecules")
    axis.set_title("Applicability domain\n" + SUBSTITUTION, fontsize=9)
    axis.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def percentile_interval(values: list[float]) -> tuple[float, float, float]:
    """2.5, 50 and 97.5 percentiles. This is the bootstrap-style interval used throughout."""
    arr = np.asarray(values, dtype=float)
    low, mid, high = np.percentile(arr, [2.5, 50.0, 97.5])
    return float(low), float(mid), float(high)
