"""Q-003 audit: scaffold split, random split, learning curve, Y-scramble, applicability domain.

## [EXPLORATORY]
The verdict model is the Morgan random forest. A descriptor forest is reported beside it
and cannot replace the verdict.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from clusters.ligand_data.src.tables import write_table
from clusters.ml_audit.src.curve import learning_points, plateaued, required_n
from clusters.ml_audit.src.domain import TANIMOTO_MIN, applicability
from clusters.ml_audit.src.features import (
    descriptor_matrix,
    group_labels,
    labels_from,
    load_patent_table,
    morgan_matrix,
)
from clusters.ml_audit.src.figures import (
    percentile_interval,
    write_curve_figure,
    write_domain_figure,
    write_scramble_figure,
    write_split_figure,
)
from clusters.ml_audit.src.holdouts import TEST_FRACTION, random_holdouts, scaffold_holdouts
from clusters.ml_audit.src.model import (
    MAX_DEPTH,
    MIN_SAMPLES_LEAF,
    N_ESTIMATORS,
    score_holdouts,
)
from core.config import ExperimentConfig
from core.errors import ContractViolation
from core.hashing import sha256_file
from core.ledger import run_logged

_REPO = Path(__file__).resolve().parents[3]
_SEED = 20261004
_N_ATTEMPTS = 80
_N_PERM = 30
_MIN_HOLDOUTS = 30
_MIN_NULL = 20
_MIN_SCORED = 15


def main() -> dict[str, Any]:
    """Logged Q-003 audit."""
    cfg = ExperimentConfig(
        name="m4-ml-audit",
        seed=_SEED,
        mode="exploratory",
        condition_code="aid2060853-morgan-rf",
        study_id="M4",
        params={
            "n_estimators": N_ESTIMATORS,
            "max_depth": MAX_DEPTH,
            "min_samples_leaf": MIN_SAMPLES_LEAF,
            "frac_test": TEST_FRACTION,
            "n_attempts": _N_ATTEMPTS,
            "n_permutations": _N_PERM,
            "ad_tanimoto_min": TANIMOTO_MIN,
            "library": "chembl-leadlike-substitute",
        },
    )
    return run_logged(cfg, _audit, ledger_path=_REPO / "governance" / "run_ledger.jsonl")


def _audit() -> dict[str, Any]:
    data_dir = _REPO / "data" / "ligand_data"
    result_dir = _REPO / "results" / "ml_audit"
    result_dir.mkdir(parents=True, exist_ok=True)
    rows = load_patent_table(data_dir / "modeling_table.csv")
    y = labels_from(rows)
    groups = group_labels(rows)
    morgan = morgan_matrix(rows)
    descriptors = descriptor_matrix(rows)
    scaffold, dropped = scaffold_holdouts(groups, y, n_attempts=_N_ATTEMPTS, seed=_SEED)
    if len(scaffold) < _MIN_HOLDOUTS:
        raise ContractViolation(
            f"only {len(scaffold)} scaffold holdouts kept both classes out of {_N_ATTEMPTS} "
            f"({dropped} dropped); the interval is not estimable"
        )
    random_splits = random_holdouts(y, n_splits=len(scaffold), seed=_SEED)
    print(f"scoring {len(scaffold)} scaffold and {len(random_splits)} random holdouts", flush=True)
    scaffold_auc = score_holdouts(morgan, y, scaffold, seed=_SEED)
    random_auc = score_holdouts(morgan, y, random_splits, seed=_SEED + 1000)
    descriptor_auc = score_holdouts(descriptors, y, scaffold, seed=_SEED)
    print("y-scrambling", flush=True)
    null_medians = _scramble(morgan, y, scaffold)
    print("learning curve", flush=True)
    points = learning_points(morgan, y, groups, scaffold, seed=_SEED + 7)
    if len(points) < 2:
        raise ContractViolation("learning curve produced fewer than two training sizes")
    domain_rows, domain_summary = applicability(
        rows,
        data_dir / "curated_activities.csv",
        _REPO / "data" / "ml_audit" / "raw",
    )
    verdict = _verdict(
        rows, groups, y, scaffold_auc, random_auc, descriptor_auc, null_medians, points, dropped
    )
    verdict["applicability"] = {key: _jsonable(value) for key, value in domain_summary.items()}
    _write(result_dir, scaffold_auc, random_auc, descriptor_auc, points, null_medians, domain_rows, verdict)
    verdict_path = result_dir / "q003_verdict.json"
    return {
        "data_manifest_hash": sha256_file(verdict_path),
        "verdict": verdict["verdict"],
        "scaffold_auc_median": verdict["scaffold_auc"]["median"],
        "scaffold_auc_ci95_low": verdict["scaffold_auc"]["ci95"][0],
        "scaffold_auc_ci95_high": verdict["scaffold_auc"]["ci95"][1],
        "random_auc_median": verdict["random_auc"]["median"],
        "random_auc_ci95_low": verdict["random_auc"]["ci95"][0],
        "random_auc_ci95_high": verdict["random_auc"]["ci95"][1],
        "y_scramble_inside_central_95": verdict["y_scramble_inside_central_95"],
        "n_required": verdict["n_required"],
        "n_molecules": int(len(rows)),
        "n_active": int(np.sum(y == 1)),
        "n_inactive": int(np.sum(y == 0)),
        "fraction_in_domain": float(domain_summary["fraction_in_domain"]),
    }


def _scramble(features: np.ndarray, y: np.ndarray, holdouts: list) -> list[float]:
    rng = np.random.default_rng(_SEED + 99)
    medians: list[float] = []
    for perm in range(_N_PERM):
        scores = score_holdouts(features, rng.permutation(y), holdouts, seed=_SEED)
        if len(scores) < _MIN_SCORED:
            continue
        medians.append(float(np.median(scores)))
        if (perm + 1) % 10 == 0:
            print(f"  permutations {perm + 1}/{_N_PERM}", flush=True)
    if len(medians) < _MIN_NULL:
        raise ContractViolation(f"Y-scramble kept only {len(medians)} permutations")
    return medians


def _verdict(
    rows: list[dict[str, str]],
    groups: np.ndarray,
    y: np.ndarray,
    scaffold_auc: list[float],
    random_auc: list[float],
    descriptor_auc: list[float],
    null_medians: list[float],
    points: list,
    dropped: int,
) -> dict[str, Any]:
    scaffold_ci = percentile_interval(scaffold_auc)
    random_ci = percentile_interval(random_auc)
    descriptor_ci = percentile_interval(descriptor_auc)
    null_ci = percentile_interval(null_medians)
    observed = float(np.median(scaffold_auc))
    inside_null = bool(null_ci[0] <= observed <= null_ci[2])
    rank = float(np.mean(np.asarray(null_medians) <= observed))
    flat = plateaued(points)
    fit = required_n(points)
    n_required = None if flat or fit["status"] != "estimated" else fit["n"]
    h3_status = "plateau" if flat else str(fit["status"])
    unique, counts = np.unique(groups, return_counts=True)
    largest_n = int(counts.max())
    biggest = unique[int(np.argmax(counts))]
    in_biggest = y[groups == biggest]
    verdict, sentence = _call(scaffold_ci, inside_null)
    return {
        "question": "Q-003",
        "verdict": verdict,
        "sentence": sentence,
        "h1_lower_bound_above_0.5": bool(scaffold_ci[0] > 0.5),
        "h2_random_ci_above_scaffold_ci": bool(random_ci[0] > scaffold_ci[2]),
        "h3_status": h3_status,
        "n_required": n_required,
        "n_required_fit": {key: _jsonable(value) for key, value in fit.items()},
        "scaffold_auc": _ci_block(scaffold_ci, scaffold_auc),
        "random_auc": _ci_block(random_ci, random_auc),
        "descriptor_scaffold_auc": _ci_block(descriptor_ci, descriptor_auc),
        "y_scramble_inside_central_95": inside_null,
        "y_scramble_percentile_rank": rank,
        "y_scramble_null_ci95": [null_ci[0], null_ci[2]],
        "n_molecules": len(rows),
        "n_active": int(np.sum(y == 1)),
        "n_inactive": int(np.sum(y == 0)),
        "n_scaffolds": int(unique.size),
        "largest_scaffold_n": largest_n,
        "largest_scaffold_active": int(np.sum(in_biggest == 1)),
        "largest_scaffold_inactive": int(np.sum(in_biggest == 0)),
        "scaffold_holdouts_kept": len(scaffold_auc),
        "scaffold_holdouts_dropped": dropped,
        "label_source": "AID 2060853 deposited Active/Inactive calls only; endpoints were not pooled",
        "primary_model": "RandomForest Morgan radius 2, 2048 bits",
    }


def _call(scaffold_ci: tuple[float, float, float], inside_null: bool) -> tuple[str, str]:
    low, _mid, high = scaffold_ci
    if inside_null:
        return (
            "not_sufficient",
            "The scaffold-split ROC-AUC sits inside the central 95% of the Y-scrambling null, "
            "so the fit is noise.",
        )
    if low > 0.5:
        return (
            "sufficient",
            "The scaffold-split ROC-AUC 95% interval lies entirely above 0.5, "
            "so H1's prediction is overturned. Exploratory only; not a claim.",
        )
    if high < 0.5:
        return (
            "not_sufficient",
            "The scaffold-split ROC-AUC 95% interval lies entirely below 0.5.",
        )
    return (
        "not_sufficient",
        "The scaffold-split ROC-AUC 95% interval includes 0.5, "
        "so the public data do not support a model that generalises across chemical series.",
    )


def _ci_block(ci: tuple[float, float, float], scores: list[float]) -> dict[str, Any]:
    return {"low": ci[0], "median": ci[1], "high": ci[2], "ci95": [ci[0], ci[2]], "n": len(scores)}


def _write(
    result_dir: Path,
    scaffold_auc: list[float],
    random_auc: list[float],
    descriptor_auc: list[float],
    points: list,
    null_medians: list[float],
    domain_rows: list[dict[str, str]],
    verdict: dict[str, Any],
) -> None:
    holdout_rows = _long(scaffold_auc, "scaffold_morgan") + _long(random_auc, "random_morgan")
    holdout_rows += _long(descriptor_auc, "scaffold_descriptors")
    write_table(result_dir / "holdout_aucs.csv", holdout_rows, ("split", "repeat", "roc_auc"))
    curve_rows = [
        {
            "n_train": str(point.n_train),
            "n_scores": str(len(point.aucs)),
            "mean": f"{point.mean:.6f}",
            "p2.5": f"{point.low:.6f}",
            "p97.5": f"{point.high:.6f}",
        }
        for point in points
    ]
    write_table(
        result_dir / "learning_curve.csv", curve_rows, ("n_train", "n_scores", "mean", "p2.5", "p97.5")
    )
    write_table(
        result_dir / "yscramble_medians.csv",
        [{"permutation": str(i), "median_roc_auc": f"{value:.6f}"} for i, value in enumerate(null_medians)],
        ("permutation", "median_roc_auc"),
    )
    domain_columns = list(domain_rows[0])
    write_table(result_dir / "applicability_domain.csv", domain_rows, domain_columns)
    write_split_figure(scaffold_auc, random_auc, result_dir / "split_auc.png")
    write_curve_figure(points, int(verdict["n_molecules"]), result_dir / "learning_curve.png")
    write_scramble_figure(
        null_medians, float(verdict["scaffold_auc"]["median"]), result_dir / "yscramble.png"
    )
    write_domain_figure(
        [float(row["max_tanimoto"]) for row in domain_rows],
        TANIMOTO_MIN,
        result_dir / "applicability_domain.png",
    )
    payload = json.dumps(verdict, indent=2, sort_keys=True, allow_nan=False) + "\n"
    (result_dir / "q003_verdict.json").write_text(payload, encoding="utf-8")


def _long(scores: list[float], name: str) -> list[dict[str, str]]:
    return [{"split": name, "repeat": str(i), "roc_auc": f"{value:.6f}"} for i, value in enumerate(scores)]


def _jsonable(value: object) -> object:
    if value is None or isinstance(value, (str, int, float, bool)):
        if isinstance(value, float) and not np.isfinite(value):
            raise ContractViolation("refusing a non-finite number in the verdict")
        return value
    raise ContractViolation(f"verdict value type {type(value).__name__} is not JSON-safe")


if __name__ == "__main__":
    print(json.dumps(main(), indent=2, sort_keys=True))
