"""Logged entry points. R scripts are the calculators; this module records the run.

## [EXPLORATORY]
"""

from __future__ import annotations

import csv
import json
import math
import subprocess
from collections.abc import Callable
from pathlib import Path

from clusters.report.src.assumptions import (
    CI_FOLD_LIMIT,
    CONFIDENCE_PRIMARY,
    DOSE_DESIGNS,
    DOSE_EC50_UM,
    DOSE_LOWER,
    DOSE_REPLICATES,
    DOSE_REPS,
    DOSE_SD,
    DOSE_SEED,
    DOSE_SLOPE,
    DOSE_UPPER,
    EF_GRID,
    FUNNEL_REPS,
    FUNNEL_SEED,
    LIBRARY_SIZE,
    POTENCY_SHIFT,
    PRIOR_GRID,
    QPCR_ALPHA,
    QPCR_ALPHA_BONFERRONI,
    QPCR_FOLD,
    QPCR_GENES,
    QPCR_N_GRID,
    QPCR_POWER,
    QPCR_SD_GRID,
    QPCR_SD_PRIMARY,
    QPCR_SEED,
    QUOTED_EF,
    QUOTED_PRIOR,
    REVIEW_SET_SIZE,
)
from clusters.report.src.dose_decision import decide_dose
from clusters.report.src.figures import write_dose_figure, write_funnel_figures, write_qpcr_figure
from clusters.report.src.funnel import large_library_sensitivity, run_grid
from core.config import ExperimentConfig
from core.errors import ContractViolation
from core.hashing import sha256_file
from core.ledger import run_logged

_REPO = Path(__file__).resolve().parents[3]
_OUT = _REPO / "results" / "report"
_LEDGER = _REPO / "governance" / "run_ledger.jsonl"
_PIXI = Path.home() / ".pixi" / "bin" / "pixi"
_MANIFEST = _REPO / "pixi.toml"


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise ContractViolation(f"refusing to write an empty table to {path}")
    fields = list(rows[0].keys())
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _csv_value(row[key]) for key in fields})


def _csv_value(value: object) -> str:
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return ""
        return f"{value:.8g}"
    return str(value)


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise ContractViolation(f"expected table missing: {path}")
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _as_number(text: str) -> float | int | str:
    if text == "":
        return float("nan")
    try:
        number = float(text)
    except ValueError:
        return text
    if number.is_integer():
        return int(number)
    return number


def _typed_rows(path: Path) -> list[dict[str, float | int | str]]:
    typed: list[dict[str, float | int | str]] = []
    for raw in _read_csv(path):
        row: dict[str, float | int | str] = {}
        for key, value in raw.items():
            parsed = _as_number(value)
            if not isinstance(parsed, (int, float, str)):
                raise ContractViolation(f"unexpected cell {key}={value!r}")
            row[key] = parsed
        typed.append(row)
    if not typed:
        raise ContractViolation(f"{path} has a header but no rows")
    return typed


def _clean(value: object) -> object:
    if isinstance(value, dict):
        return {str(key): _clean(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_clean(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _dump(path: Path, payload: dict[str, object]) -> None:
    cleaned = _clean(payload)
    if not isinstance(cleaned, dict):
        raise ContractViolation("JSON payload did not stay a dict")
    path.write_text(json.dumps(cleaned, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def _run_r(script: Path, config_path: Path) -> None:
    if not _PIXI.is_file():
        raise ContractViolation(f"pixi binary missing at {_PIXI}")
    command = [
        str(_PIXI),
        "run",
        "--manifest-path",
        str(_MANIFEST),
        "Rscript",
        str(script),
        str(config_path),
    ]
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    if completed.stdout:
        print(completed.stdout)
    if completed.returncode != 0:
        tail = (completed.stderr or completed.stdout or "")[-4000:]
        raise ContractViolation(f"{script.name} exited {completed.returncode}: {tail}")


def _quoted(rows: list[dict[str, float | int]]) -> dict[str, float | int]:
    for row in rows:
        if math.isclose(float(row["pi"]), QUOTED_PRIOR) and math.isclose(float(row["ef"]), QUOTED_EF):
            return row
    raise ContractViolation("quoted grid row missing from the funnel output")


def _funnel_summary(
    rows: list[dict[str, float | int]], large: dict[str, float | int | str], manifest: str
) -> dict[str, object]:
    quoted = _quoted(rows)
    probabilities = [float(row["p_rank_k8"]) for row in rows]
    band = [
        {
            "pi": float(row["pi"]),
            "ef": float(row["ef"]),
            "k80_rank": int(row["k80_rank"]),
            "p_rank_k8": float(row["p_rank_k8"]),
            "p_rank_k10": float(row["p_rank_k10"]),
        }
        for row in rows
        if 0 < int(row["k80_rank"]) <= 10
    ]
    return {
        "data_manifest_hash": manifest,
        "seed": FUNNEL_SEED,
        "n_reps": FUNNEL_REPS,
        "library_size": LIBRARY_SIZE,
        "review_set_size": REVIEW_SET_SIZE,
        "confidence": CONFIDENCE_PRIMARY,
        "quoted_pi": QUOTED_PRIOR,
        "quoted_ef": QUOTED_EF,
        "quoted_p_k6": float(quoted["p_rank_k6"]),
        "quoted_p_k8": float(quoted["p_rank_k8"]),
        "quoted_p_k10": float(quoted["p_rank_k10"]),
        "quoted_k80_rank": int(quoted["k80_rank"]),
        "quoted_k50_rank": int(quoted["k50_rank"]),
        "quoted_p_div_k8": float(quoted["p_div_k8"]),
        "quoted_p_div_k10": float(quoted["p_div_k10"]),
        "quoted_k80_div": int(quoted["k80_div"]),
        "quoted_empirical_ef1": float(quoted["empirical_ef1"]),
        "quoted_enrichment_at_k8": float(quoted["enrichment_at_k8"]),
        "p_k8_min": min(probabilities),
        "p_k8_max": max(probabilities),
        "p_k6_min": min(float(row["p_rank_k6"]) for row in rows),
        "p_k6_max": max(float(row["p_rank_k6"]) for row in rows),
        "p_k10_min": min(float(row["p_rank_k10"]) for row in rows),
        "p_k10_max": max(float(row["p_rank_k10"]) for row in rows),
        "cells_where_ten_purchases_reach_80": band,
        "large_library": large,
        "prior_grid": list(PRIOR_GRID),
        "ef_grid": list(EF_GRID),
    }


def run_funnel_body() -> dict[str, object]:
    rows, curves = run_grid(seed=FUNNEL_SEED, n_rep=FUNNEL_REPS)
    _OUT.mkdir(parents=True, exist_ok=True)
    grid_path = _OUT / "funnel_grid.csv"
    _write_csv(grid_path, rows)
    _write_csv(_OUT / "funnel_curves.csv", curves)
    write_funnel_figures(rows, curves, _OUT)
    large = large_library_sensitivity(seed=FUNNEL_SEED, n_check=FUNNEL_REPS)
    summary = _funnel_summary(rows, large, sha256_file(grid_path))
    _dump(_OUT / "funnel_summary.json", summary)
    return {
        "data_manifest_hash": summary["data_manifest_hash"],
        "quoted_p_k8": summary["quoted_p_k8"],
        "quoted_k80_rank": summary["quoted_k80_rank"],
        "p_k8_min": summary["p_k8_min"],
        "p_k8_max": summary["p_k8_max"],
        "large_library_status": str(large["status"]),
        "grid_csv": str(grid_path),
    }


def run_dose_body() -> dict[str, object]:
    config = {
        "seed": DOSE_SEED,
        "n_mc": DOSE_REPS,
        "sd": DOSE_SD,
        "ec50": DOSE_EC50_UM,
        "shift": POTENCY_SHIFT,
        "upper": DOSE_UPPER,
        "lower": DOSE_LOWER,
        "slope": DOSE_SLOPE,
        "ci_fold_limit": CI_FOLD_LIMIT,
        "designs": [{"id": name, "doses": list(doses)} for name, doses in DOSE_DESIGNS],
        "replicates": list(DOSE_REPLICATES),
        "out_dir": str(_OUT),
    }
    _OUT.mkdir(parents=True, exist_ok=True)
    config_path = _OUT / "dose_config.json"
    _dump(config_path, config)
    _run_r(_REPO / "clusters" / "report" / "r" / "dose_power.R", config_path)
    single = _typed_rows(_OUT / "dose_single.csv")
    shift = _typed_rows(_OUT / "dose_shift.csv")
    decision = decide_dose(single, shift)
    summary: dict[str, object] = {
        "data_manifest_hash": sha256_file(_OUT / "dose_single.csv"),
        "seed": DOSE_SEED,
        "n_mc": DOSE_REPS,
        "sd": DOSE_SD,
        "ec50_uM": DOSE_EC50_UM,
        "shift": POTENCY_SHIFT,
        "slope": DOSE_SLOPE,
        **decision,
    }
    write_dose_figure(single, _OUT / "dose_ci_width.png")
    _dump(_OUT / "dose_summary.json", summary)
    return {
        "data_manifest_hash": summary["data_manifest_hash"],
        "precision_design": decision["precision_design"],
        "precision_n_conc": decision["precision_n_conc"],
        "precision_n_rep": decision["precision_n_rep"],
        "precision_median_fold": decision["precision_median_fold"],
        "shift_design": decision["shift_design"],
        "shift_n_conc": decision["shift_n_conc"],
        "shift_n_rep": decision["shift_n_rep"],
        "shift_power": decision["shift_power"],
        "shift_median_fold": decision["shift_median_fold"],
    }


def _qpcr_minimum(
    rows: list[dict[str, float | int | str]], sd: float, alpha: float
) -> dict[str, float | int | str]:
    matches = [
        row
        for row in rows
        if row["quantity"] == "minimum_n"
        and math.isclose(float(row["sd_ct"]), sd)
        and math.isclose(float(row["alpha"]), alpha)
    ]
    if len(matches) != 1:
        raise ContractViolation(
            f"expected one qPCR minimum-n row for SD {sd} alpha {alpha}, found {len(matches)}"
        )
    return matches[0]


def run_qpcr_body() -> dict[str, object]:
    config = {
        "seed": QPCR_SEED,
        "sd_grid": list(QPCR_SD_GRID),
        "n_grid": list(QPCR_N_GRID),
        "alpha": QPCR_ALPHA,
        "alpha_bonferroni": QPCR_ALPHA_BONFERRONI,
        "fold": QPCR_FOLD,
        "power": QPCR_POWER,
        "out_dir": str(_OUT),
    }
    _OUT.mkdir(parents=True, exist_ok=True)
    config_path = _OUT / "qpcr_config.json"
    _dump(config_path, config)
    _run_r(_REPO / "clusters" / "report" / "r" / "qpcr_power.R", config_path)
    rows = _typed_rows(_OUT / "qpcr_power.csv")
    primary = _qpcr_minimum(rows, QPCR_SD_PRIMARY, QPCR_ALPHA)
    bonferroni = _qpcr_minimum(rows, QPCR_SD_PRIMARY, QPCR_ALPHA_BONFERRONI)
    write_qpcr_figure(rows, _OUT / "qpcr_detectable_fc.png")
    summary: dict[str, object] = {
        "data_manifest_hash": sha256_file(_OUT / "qpcr_power.csv"),
        "seed": QPCR_SEED,
        "sd_primary": QPCR_SD_PRIMARY,
        "sd_grid": list(QPCR_SD_GRID),
        "fold": QPCR_FOLD,
        "power": QPCR_POWER,
        "alpha": QPCR_ALPHA,
        "alpha_bonferroni": QPCR_ALPHA_BONFERRONI,
        "genes": list(QPCR_GENES),
        "n_per_group": int(primary["n_per_group"]),
        "power_at_n": float(primary["power"]),
        "n_per_group_bonferroni": int(bonferroni["n_per_group"]),
        "power_at_n_bonferroni": float(bonferroni["power"]),
    }
    _dump(_OUT / "qpcr_summary.json", summary)
    return {
        "data_manifest_hash": summary["data_manifest_hash"],
        "sd_primary": QPCR_SD_PRIMARY,
        "n_per_group": summary["n_per_group"],
        "power_at_n": summary["power_at_n"],
        "n_per_group_bonferroni": summary["n_per_group_bonferroni"],
        "fold": QPCR_FOLD,
    }


def _logged(
    name: str,
    condition: str,
    seed: int,
    params: dict[str, float | int | str],
    body: Callable[[], dict[str, object]],
) -> dict[str, object]:
    cfg = ExperimentConfig(
        name=name,
        seed=seed,
        mode="exploratory",
        condition_code=condition,
        study_id="S05-report",
        params=params,
    )

    def logged_body() -> dict[str, object]:
        payload = _clean(body())
        if not isinstance(payload, dict):
            raise ContractViolation("logged run did not return a dict")
        return payload

    result = run_logged(cfg, logged_body, ledger_path=_LEDGER)
    if not isinstance(result, dict):
        raise ContractViolation("logged run did not return a dict")
    return result


def main_funnel() -> None:
    _logged(
        "screening-funnel",
        "A4xA23",
        FUNNEL_SEED,
        {
            "n_library": LIBRARY_SIZE,
            "n_reps": FUNNEL_REPS,
            "review_set": REVIEW_SET_SIZE,
            "quoted_pi": QUOTED_PRIOR,
            "quoted_ef": QUOTED_EF,
            "confidence": CONFIDENCE_PRIMARY,
        },
        run_funnel_body,
    )


def main_dose() -> None:
    _logged(
        "calcium-dose-power",
        "WP5",
        DOSE_SEED,
        {
            "n_mc": DOSE_REPS,
            "sd": DOSE_SD,
            "ec50_uM": DOSE_EC50_UM,
            "shift": POTENCY_SHIFT,
            "slope": DOSE_SLOPE,
        },
        run_dose_body,
    )


def main_qpcr() -> None:
    _logged(
        "qpcr-power",
        "WP6",
        QPCR_SEED,
        {
            "sd_primary": QPCR_SD_PRIMARY,
            "fold": QPCR_FOLD,
            "alpha": QPCR_ALPHA,
            "power": QPCR_POWER,
        },
        run_qpcr_body,
    )
