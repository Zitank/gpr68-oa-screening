"""The plate-layout rule is applied to a fake grid, not to a drc fit."""

from __future__ import annotations

from clusters.report.src.dose_decision import decide_dose, is_precise


def _single(
    design: str, n_conc: int, n_rep: int, fold: float, asymptotes: str = "fixed"
) -> dict[str, float | int | str]:
    return {
        "design_id": f"{design}-r{n_rep}",
        "design_id_base": design,
        "n_conc": n_conc,
        "n_rep": n_rep,
        "asymptotes": asymptotes,
        "frac_converged": 1.0,
        "coverage": 0.95,
        "frac_fold_le_3": 0.9 if fold <= 3 else 0.2,
        "median_fold": fold,
    }


def _shift(design: str, n_conc: int, n_rep: int, power: float) -> dict[str, float | int | str]:
    return {
        "design_id": f"{design}-r{n_rep}",
        "design_id_base": design,
        "n_conc": n_conc,
        "n_rep": n_rep,
        "asymptotes": "fixed",
        "power": power,
    }


def test_wide_interval_is_not_precise() -> None:
    row = _single("C8", 8, 2, fold=5.0)
    row["frac_fold_le_3"] = 0.4
    assert not is_precise(row)


def test_smallest_design_that_meets_both_bars_is_chosen() -> None:
    single = [
        _single("C6", 6, 2, fold=4.0),
        _single("C8", 8, 3, fold=2.4),
        _single("C10", 10, 3, fold=2.1),
        _single("C8", 8, 3, fold=6.0, asymptotes="free"),
    ]
    shift = [
        _shift("C6", 6, 2, power=0.4),
        _shift("C8", 8, 3, power=0.85),
        _shift("C10", 10, 3, power=0.9),
    ]
    decision = decide_dose(single, shift)
    assert decision["precision_design"] == "C8-r3"
    assert decision["shift_design"] == "C8-r3"
    assert decision["free_median_fold_at_shift_design"] == 6.0
