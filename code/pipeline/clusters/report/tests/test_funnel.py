"""Deterministic checks for the funnel calibration. The full grid is the logged run."""

from __future__ import annotations

import math

import numpy as np
import pytest

from clusters.report.src.funnel import (
    delta_for_ef,
    diversity_success_probability,
    k_for_confidence,
    norm_ppf,
    p_at_k,
    simulate_library,
)
from core.errors import ContractViolation


def test_norm_ppf_known_values() -> None:
    assert norm_ppf(0.5) == pytest.approx(0.0, abs=1e-8)
    assert norm_ppf(0.975) == pytest.approx(1.95996398454, abs=1e-6)


def test_unit_enrichment_has_no_score_gap() -> None:
    assert delta_for_ef(1.0) == pytest.approx(0.0, abs=1e-8)


def test_enrichment_gap_increases() -> None:
    assert delta_for_ef(2.0) < delta_for_ef(5.0) < delta_for_ef(20.0)


def test_impossible_enrichment_raises() -> None:
    with pytest.raises(ContractViolation):
        delta_for_ef(100.0, fraction=0.01)


def test_k_for_confidence_order_statistic() -> None:
    best = np.array([1, 1, 1, 2, 5])
    assert k_for_confidence(best, 0.8, library_size=10) == 2
    assert k_for_confidence(best, 0.5, library_size=10) == 1
    assert k_for_confidence(np.array([11, 11, 11, 11, 2]), 0.8, library_size=10) == -1


def test_simulate_library_is_reproducible() -> None:
    kwargs = {"n": 80, "pi": 0.05, "delta": 1.0, "n_rep": 30, "review": 10}
    first = simulate_library(**kwargs, rng=np.random.default_rng(7))
    second = simulate_library(**kwargs, rng=np.random.default_rng(7))
    assert np.array_equal(first["best"], second["best"])


def test_stronger_enrichment_raises_purchase_probability() -> None:
    weak = simulate_library(
        n=400, pi=0.02, delta=delta_for_ef(1.0), n_rep=400, review=40, rng=np.random.default_rng(1)
    )
    strong = simulate_library(
        n=400, pi=0.02, delta=delta_for_ef(20.0), n_rep=400, review=40, rng=np.random.default_rng(1)
    )
    assert p_at_k(strong["best"], 8) > p_at_k(weak["best"], 8)


def test_diversity_draw_is_certain_when_the_review_set_is_all_hits() -> None:
    hits = np.array([10, 10, 10])
    assert diversity_success_probability(hits, review=10, k=6) == pytest.approx(1.0)


def test_diversity_draw_is_zero_when_the_review_set_has_no_hits() -> None:
    hits = np.zeros(5, dtype=int)
    assert diversity_success_probability(hits, review=10, k=6) == pytest.approx(0.0)
    assert math.isclose(diversity_success_probability(hits, review=10, k=6), 0.0)
