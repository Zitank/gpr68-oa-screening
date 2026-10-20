"""Figures for the decision report. Inputs are the logged tables, not a second simulation.

## [EXPLORATORY]
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LogNorm

from clusters.report.src.assumptions import QUOTED_EF, QUOTED_PRIOR
from core.errors import ContractViolation


def _as_float_grid(rows: list[dict[str, float | int]], key: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    priors = sorted({float(row["pi"]) for row in rows})
    efs = sorted({float(row["ef"]) for row in rows})
    lookup = {(float(row["pi"]), float(row["ef"])): row[key] for row in rows}
    grid = np.array([[lookup[(pi, ef)] for ef in efs] for pi in priors], dtype=float)
    return np.array(priors), np.array(efs), grid


def write_funnel_figures(
    rows: list[dict[str, float | int]],
    curves: list[dict[str, float | int | str]],
    out_dir: Path,
) -> None:
    """Heatmap of P at k=8, heatmap of the 80% purchase count, and the purchase-band curves."""
    out_dir.mkdir(parents=True, exist_ok=True)
    priors, efs, p8 = _as_float_grid(rows, "p_rank_k8")
    _, _, k80 = _as_float_grid(rows, "k80_rank")
    _heatmap_probability(priors, efs, p8, out_dir / "funnel_heatmap_k8.png")
    _heatmap_purchase(priors, efs, k80, out_dir / "funnel_k80.png")
    _purchase_band(curves, out_dir / "funnel_purchase_band.png")


def _heatmap_probability(priors: np.ndarray, efs: np.ndarray, values: np.ndarray, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(7.6, 5.2))
    image = ax.imshow(values, origin="lower", aspect="auto", vmin=0.0, vmax=1.0, cmap="viridis")
    ax.set_xticks(range(len(efs)), [f"{ef:g}" for ef in efs])
    ax.set_yticks(range(len(priors)), [f"{pi:.0e}" for pi in priors])
    ax.set_xlabel("Nominal docking enrichment at the top 1% (EF1%)")
    ax.set_ylabel("Prior hit rate per compound")
    ax.set_title("P(at least one true hit) if the top 8 by score are purchased")
    fig.colorbar(image, ax=ax, label="Probability")
    _mark_quoted(ax, priors, efs)
    try:
        ax.contour(values, levels=[0.5, 0.8], colors=["white", "0.15"], linewidths=1.0, origin="lower")
    except ValueError as exc:
        raise ContractViolation(f"probability contour failed: {exc}") from exc
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


def _heatmap_purchase(priors: np.ndarray, efs: np.ndarray, k80: np.ndarray, path: Path) -> None:
    shown = np.where(k80 < 0, np.nan, k80)
    finite = shown[np.isfinite(shown)]
    if finite.size == 0:
        raise ContractViolation("no grid cell reached 80% confidence inside the library")
    fig, ax = plt.subplots(figsize=(7.6, 5.2))
    cmap = plt.get_cmap("cividis").copy()
    cmap.set_bad("0.82")
    norm = LogNorm(vmin=max(1.0, float(finite.min())), vmax=float(finite.max()))
    image = ax.imshow(shown, origin="lower", aspect="auto", cmap=cmap, norm=norm)
    ax.set_xticks(range(len(efs)), [f"{ef:g}" for ef in efs])
    ax.set_yticks(range(len(priors)), [f"{pi:.0e}" for pi in priors])
    ax.set_xlabel("Nominal docking enrichment at the top 1% (EF1%)")
    ax.set_ylabel("Prior hit rate per compound")
    ax.set_title("Compounds to buy for an 80% chance of one true hit")
    fig.colorbar(image, ax=ax, label="Purchase count (top of the ranked list)")
    _mark_quoted(ax, priors, efs)
    stroke = [pe.withStroke(linewidth=1.6, foreground="white")]
    for i in range(shown.shape[0]):
        for j in range(shown.shape[1]):
            label = "—" if k80[i, j] < 0 else str(int(k80[i, j]))
            ax.text(j, i, label, ha="center", va="center", fontsize=6.5, color="black", path_effects=stroke)
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


def _mark_quoted(ax: plt.Axes, priors: np.ndarray, efs: np.ndarray) -> None:
    pi_index = int(np.where(np.isclose(priors, QUOTED_PRIOR))[0][0])
    ef_index = int(np.where(np.isclose(efs, QUOTED_EF))[0][0])
    ax.scatter(
        [ef_index], [pi_index], s=80, facecolors="none", edgecolors="crimson", linewidths=1.5, zorder=5
    )


def _purchase_band(curves: list[dict[str, float | int | str]], path: Path) -> None:
    if not curves:
        raise ContractViolation("purchase-band figure needs the scenario curves")
    fig, ax = plt.subplots(figsize=(7.6, 4.8))
    ax.axvspan(6, 10, color="0.85", label="Planned purchase, 6 to 10", zorder=0)
    ax.axhline(0.8, color="0.25", linestyle="--", linewidth=1, label="80% confidence")
    for name in ("low", "quoted", "high"):
        subset = [row for row in curves if row["scenario"] == name]
        if not subset:
            raise ContractViolation(f"missing curve for scenario {name}")
        subset.sort(key=lambda row: int(row["k"]))
        pi = float(subset[0]["pi"])
        ef = float(subset[0]["ef"])
        ax.plot(
            [int(row["k"]) for row in subset],
            [float(row["p_rank"]) for row in subset],
            label=f"{name}: prior {pi:.0e}, EF1% {ef:g}",
        )
    ax.set_xlim(1, max(int(row["k"]) for row in curves))
    ax.set_ylim(0, 1)
    ax.set_xlabel("Compounds purchased from the top of the docking list")
    ax.set_ylabel("P(at least one true hit)")
    ax.set_title("Where the planned purchase sits on the probability curve")
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


def write_dose_figure(rows: list[dict[str, float | int | str]], path: Path) -> None:
    """Median EC50 CI fold-width against replicates, one line per concentration scheme."""
    fixed = [row for row in rows if row["asymptotes"] == "fixed"]
    if not fixed:
        raise ContractViolation("dose figure needs fixed-asymptote rows")
    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    ax.axhline(3.0, color="0.25", linestyle="--", linewidth=1, label="3-fold CI")
    for design in sorted({str(row["design_id_base"]) for row in fixed}):
        subset = [row for row in fixed if row["design_id_base"] == design]
        subset.sort(key=lambda row: int(row["n_rep"]))
        ax.plot(
            [int(row["n_rep"]) for row in subset],
            [float(row["median_fold"]) for row in subset],
            marker="o",
            label=design,
        )
    ax.set_xlabel("Replicates per concentration")
    ax.set_ylabel("Median 95% CI fold-width (upper / lower)")
    ax.set_title("EC50 precision when the asymptotes are fixed at 0 and 100")
    ax.legend(frameon=False, title="Concentrations")
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


def write_qpcr_figure(rows: list[dict[str, float | int | str]], path: Path) -> None:
    """Detectable fold-change against biological n, primary alpha, three Ct SDs."""
    primary = [row for row in rows if row["quantity"] == "detectable_fold" and float(row["alpha"]) == 0.05]
    if not primary:
        raise ContractViolation("qPCR figure needs detectable-fold rows at alpha 0.05")
    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    ax.axhline(2.0, color="0.25", linestyle="--", linewidth=1, label="2-fold effect")
    for sd in sorted({float(row["sd_ct"]) for row in primary}):
        subset = [row for row in primary if float(row["sd_ct"]) == sd]
        subset.sort(key=lambda row: int(row["n_per_group"]))
        ax.plot(
            [int(row["n_per_group"]) for row in subset],
            [float(row["fold"]) for row in subset],
            marker="o",
            label=f"SD = {sd:g} Ct",
        )
    ax.set_xlabel("Biological replicates per group")
    ax.set_ylabel("Smallest fold-change with 80% power")
    ax.set_title("Chondrocyte qPCR, two-sided, alpha 0.05, one gene")
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)
