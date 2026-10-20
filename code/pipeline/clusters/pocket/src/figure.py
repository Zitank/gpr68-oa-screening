"""Topology figure: pocket 1 versus pocket 2 on chain R.

## [EXPLORATORY]
The vertical axis is the vector from the chain A (Gαs) centroid through the
chain R Cα centroid. Positive is the side away from Gα. Pocket 2 is drawn as
the site-discrimination negative control, not as an alternative binding site.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401  (registers the 3d projection)

from clusters.pocket.src.pdbio import AtomRec

POCKET1_COLOR = "#D55E00"
POCKET2_COLOR = "#0072B2"
TRACE_COLOR = "#8A8F98"
PAPER = "#F7F4EF"
INK = "#1A1A1A"


def write_topology(
    path: Path,
    ca_xyz: list[tuple[float, float, float]],
    ca_resseq: list[int],
    pocket1: tuple[tuple[float, float, float], ...],
    pocket2: tuple[tuple[float, float, float], ...],
    axis: list[float],
    origin: tuple[float, float, float],
) -> None:
    """Write a two-panel PNG. ``axis`` is a unit vector; ``origin`` is the chain R Cα centroid."""
    path.parent.mkdir(parents=True, exist_ok=True)
    framed_ca = _frame(ca_xyz, origin, axis)
    framed_1 = _frame(pocket1, origin, axis)
    framed_2 = _frame(pocket2, origin, axis)
    fig = plt.figure(figsize=(19.2, 10.8), dpi=100, facecolor=PAPER)
    ax3d = fig.add_subplot(1, 2, 1, projection="3d")
    ax2d = fig.add_subplot(1, 2, 2)
    _draw_trace(ax3d, framed_ca, ca_resseq)
    _scatter(ax3d, framed_1, POCKET1_COLOR, "pocket 1 points")
    _scatter(ax3d, framed_2, POCKET2_COLOR, "pocket 2 points")
    ax3d.set_title("Chain R Cα, pockets 1 and 2", color=INK, fontsize=16, pad=12)
    ax3d.set_xlabel("in-plane x (Å)", color=INK, fontsize=12)
    ax3d.set_ylabel("in-plane y (Å)", color=INK, fontsize=12)
    ax3d.set_zlabel("away from Gα (Å)", color=INK, fontsize=12)
    ax3d.legend(loc="upper left", fontsize=11, frameon=False)
    ax3d.set_facecolor(PAPER)
    _style_3d(ax3d)
    _draw_radial(ax2d, framed_1, framed_2)
    fig.suptitle(
        "GPR68  PDB 8Z68 chain R    computationally predicted candidate sites",
        color=INK,
        fontsize=18,
        y=0.98,
    )
    fig.text(
        0.5,
        0.02,
        "EXPLORATORY orientation: z points from the chain A (Gαs) centroid through the chain R Cα centroid.  "
        "Pocket 2 is the lipid-facing negative control.",
        ha="center",
        color=INK,
        fontsize=12,
    )
    fig.tight_layout(rect=(0, 0.04, 1, 0.95))
    fig.savefig(path, facecolor=PAPER)
    plt.close(fig)


def _frame(
    points: list[tuple[float, float, float]] | tuple[tuple[float, float, float], ...],
    origin: tuple[float, float, float],
    axis: list[float],
) -> np.ndarray:
    """Columns are (x', y', z') with z' along ``axis`` and the origin at the receptor centroid."""
    raw = np.asarray(points, dtype=float) - np.asarray(origin, dtype=float)
    z_hat = np.asarray(axis, dtype=float)
    helper = np.array([1.0, 0.0, 0.0]) if abs(z_hat[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
    x_hat = np.cross(helper, z_hat)
    x_hat = x_hat / np.linalg.norm(x_hat)
    y_hat = np.cross(z_hat, x_hat)
    rotation = np.stack([x_hat, y_hat, z_hat], axis=1)
    return raw @ rotation


def _draw_trace(ax: plt.Axes, framed: np.ndarray, resseq: list[int]) -> None:
    start = 0
    for index in range(1, len(resseq) + 1):
        broken = index == len(resseq) or resseq[index] != resseq[index - 1] + 1
        if not broken:
            continue
        segment = framed[start:index]
        label = "Cα trace" if start == 0 else None
        ax.plot(segment[:, 0], segment[:, 1], segment[:, 2], color=TRACE_COLOR, linewidth=1.4, label=label)
        start = index


def _scatter(ax: plt.Axes, framed: np.ndarray, color: str, label: str) -> None:
    ax.scatter(framed[:, 0], framed[:, 1], framed[:, 2], s=28, c=color, depthshade=False, label=label)


def _style_3d(ax: plt.Axes) -> None:
    ax.tick_params(colors=INK, labelsize=10)
    for axis in (ax.xaxis, ax.yaxis, ax.zaxis):
        axis.label.set_color(INK)
    ax.view_init(elev=18, azim=-58)


def _draw_radial(ax: plt.Axes, pocket1: np.ndarray, pocket2: np.ndarray) -> None:
    def radii(points: np.ndarray) -> np.ndarray:
        return np.sqrt(points[:, 0] ** 2 + points[:, 1] ** 2)

    ax.scatter(radii(pocket1), pocket1[:, 2], s=36, c=POCKET1_COLOR, label="pocket 1  (primary)")
    ax.scatter(radii(pocket2), pocket2[:, 2], s=36, c=POCKET2_COLOR, label="pocket 2  (negative control)")
    ax.axhline(0.0, color=TRACE_COLOR, linewidth=1.0)
    ax.set_xlabel("distance from the bundle axis (Å)", color=INK, fontsize=13)
    ax.set_ylabel("position along the Gα axis (Å)\npositive = away from Gα", color=INK, fontsize=13)
    ax.set_title("Where the two point clouds sit", color=INK, fontsize=16)
    ax.legend(loc="best", fontsize=12, frameon=False)
    ax.set_facecolor(PAPER)
    ax.tick_params(colors=INK, labelsize=11)
    for spine in ax.spines.values():
        spine.set_color("#C8C2B8")


def ca_trace(atoms: list[AtomRec]) -> tuple[list[tuple[float, float, float]], list[int]]:
    """Cα coordinates in residue order."""
    cas = [atom for atom in atoms if atom.name == "CA"]
    cas.sort(key=lambda atom: atom.resseq)
    return [atom.xyz for atom in cas], [atom.resseq for atom in cas]
