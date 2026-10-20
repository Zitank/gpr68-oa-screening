"""Pre-declared rule that turns the dose-response grid into a plate layout.

## [EXPLORATORY]
## [ASSUMPTION: A27]
"""

from __future__ import annotations

import math
from collections.abc import Callable

from clusters.report.src.assumptions import (
    CI_FOLD_FRACTION,
    CI_FOLD_LIMIT,
    CONVERGENCE_FLOOR,
    COVERAGE_FLOOR,
    SHIFT_POWER,
)
from core.errors import ContractViolation

Row = dict[str, float | int | str]


def _required(row: Row, key: str) -> float:
    value = row[key]
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ContractViolation(f"{key} must be numeric, got {value!r}")
    if math.isnan(float(value)):
        return float("nan")
    return float(value)


def is_precise(row: Row) -> bool:
    """True when a normalised curve usually returns a 95% CI no wider than 3-fold."""
    if _required(row, "frac_converged") < CONVERGENCE_FLOOR:
        return False
    if _required(row, "coverage") < COVERAGE_FLOOR:
        return False
    return _required(row, "frac_fold_le_3") >= CI_FOLD_FRACTION


def can_distinguish(row: Row) -> bool:
    """True when a 3-fold EC50 shift is declared in at least the required fraction of replicates."""
    return _required(row, "power") >= SHIFT_POWER


def _wells(row: Row) -> tuple[int, int, int]:
    n_conc = int(row["n_conc"])
    n_rep = int(row["n_rep"])
    return (n_conc * n_rep, n_conc, n_rep)


def choose_smallest(rows: list[Row], predicate: Callable[[Row], bool]) -> Row | None:
    """Fewest wells, then fewer concentrations, then fewer replicates."""
    meeting = [row for row in rows if predicate(row)]
    if not meeting:
        return None
    return min(meeting, key=_wells)


def decide_dose(single: list[Row], shift: list[Row]) -> dict[str, float | int | str | None]:
    """Choose the EC50 layout and the layout that can also see a 3-fold shift.

    Primary rows are fixed-asymptote fits. Free-asymptote rows are reported beside the choice.
    """
    fixed_single = [row for row in single if row.get("asymptotes") == "fixed"]
    fixed_shift = [row for row in shift if row.get("asymptotes") == "fixed"]
    if not fixed_single or not fixed_shift:
        raise ContractViolation("dose decision needs fixed-asymptote single-curve and shift rows")
    precise = choose_smallest(fixed_single, is_precise)
    paired = {(str(row["design_id_base"]), int(row["n_rep"])): row for row in fixed_shift}

    def precise_and_powered(row: Row) -> bool:
        partner = paired.get((str(row["design_id_base"]), int(row["n_rep"])))
        return partner is not None and is_precise(row) and can_distinguish(partner)

    both = choose_smallest(fixed_single, precise_and_powered)
    return {
        "ci_fold_limit": CI_FOLD_LIMIT,
        "precision_design": None if precise is None else str(precise["design_id"]),
        "precision_n_conc": None if precise is None else int(precise["n_conc"]),
        "precision_n_rep": None if precise is None else int(precise["n_rep"]),
        "precision_median_fold": None if precise is None else _required(precise, "median_fold"),
        "precision_coverage": None if precise is None else _required(precise, "coverage"),
        "shift_design": None if both is None else str(both["design_id"]),
        "shift_n_conc": None if both is None else int(both["n_conc"]),
        "shift_n_rep": None if both is None else int(both["n_rep"]),
        "shift_power": None
        if both is None
        else _required(paired[(str(both["design_id_base"]), int(both["n_rep"]))], "power"),
        "shift_median_fold": None if both is None else _required(both, "median_fold"),
        "free_median_fold_at_shift_design": _free_fold(single, both),
    }


def _free_fold(single: list[Row], chosen: Row | None) -> float | None:
    if chosen is None:
        return None
    for row in single:
        same_design = row.get("design_id_base") == chosen["design_id_base"]
        same_rep = int(row["n_rep"]) == int(chosen["n_rep"])
        if row.get("asymptotes") == "free" and same_design and same_rep:
            value = _required(row, "median_fold")
            if math.isnan(value):
                return None
            return value
    return None
