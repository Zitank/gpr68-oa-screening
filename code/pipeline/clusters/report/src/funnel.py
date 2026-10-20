"""Screening-funnel Monte Carlo for the purchase decision.

## [EXPLORATORY]
Probabilities are simulation results under A4 and A20–A25 and A31, not measured hit rates.
"""

from __future__ import annotations

import math
from collections.abc import Iterable

import numpy as np

from clusters.report.src.assumptions import (
    CONFIDENCE_PRIMARY,
    CONFIDENCE_SECONDARY,
    CURVE_K_MAX,
    CURVE_SCENARIOS,
    EF_FRACTION,
    EF_GRID,
    LARGE_LIBRARY_REPS,
    LARGE_LIBRARY_SIZES,
    LARGE_LIBRARY_TOLERANCE,
    LIBRARY_SIZE,
    PRIOR_GRID,
    QUOTED_EF,
    QUOTED_PRIOR,
    REVIEW_SET_SIZE,
)
from core.errors import ContractViolation

_CHECK_KS = (8, 20, 50)


def norm_ppf(p: float) -> float:
    """Inverse standard-normal CDF by bisection on math.erf."""
    if not 0.0 < p < 1.0:
        raise ContractViolation(f"normal quantile is defined on (0, 1), got {p}")
    lo, hi = -12.0, 12.0
    for _ in range(80):
        mid = (lo + hi) / 2.0
        cdf = 0.5 * (1.0 + math.erf(mid / math.sqrt(2.0)))
        if cdf < p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def norm_cdf(x: float) -> float:
    """Standard-normal CDF."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def delta_for_ef(ef: float, fraction: float = EF_FRACTION) -> float:
    """Score gap that yields nominal EF at ``fraction`` under the rare-hit normal model.

    ## [ASSUMPTION: A23]
    """
    if ef < 1.0:
        raise ContractViolation(f"enrichment factor must be >= 1, got {ef}")
    if not 0.0 < fraction < 1.0:
        raise ContractViolation(f"EF fraction must lie in (0, 1), got {fraction}")
    captured = ef * fraction
    if captured >= 1.0:
        raise ContractViolation(f"EF {ef} is impossible at the top {fraction:.1%} of the library")
    return norm_ppf(1.0 - fraction) - norm_ppf(1.0 - captured)


def k_for_confidence(best_rank: np.ndarray, confidence: float, library_size: int) -> int:
    """Smallest k with P(best active rank <= k) >= confidence. -1 if the library cannot reach it."""
    if best_rank.ndim != 1 or best_rank.size == 0:
        raise ContractViolation("best_rank must be a non-empty 1-d array")
    if not 0.0 < confidence <= 1.0:
        raise ContractViolation(f"confidence must lie in (0, 1], got {confidence}")
    ordered = np.sort(best_rank)
    index = math.ceil(confidence * int(ordered.size)) - 1
    k = int(ordered[index])
    if k > library_size:
        return -1
    return k


def p_at_k(best_rank: np.ndarray, k: int) -> float:
    """Fraction of replicates whose best active is at rank k or better."""
    if k < 1:
        raise ContractViolation(f"k must be >= 1, got {k}")
    return float(np.mean(best_rank <= k))


def diversity_success_probability(n_hits_in_review: np.ndarray, review: int, k: int) -> float:
    """Mean P(at least one hit) for a uniform draw of k compounds from the review set.

    ## [ASSUMPTION: A22]
    """
    if k < 1 or k > review:
        raise ContractViolation(f"diversity k must lie in 1..{review}, got {k}")
    non_hits = review - n_hits_in_review
    success = np.ones(n_hits_in_review.shape, dtype=float)
    can_miss = non_hits >= k
    if np.any(can_miss):
        steps = np.arange(k)
        chosen = non_hits[can_miss][:, None]
        log_none = np.log(chosen - steps) - np.log(float(review) - steps)
        success[can_miss] = 1.0 - np.exp(log_none.sum(axis=1))
    return float(success.mean())


def diversity_k_for_confidence(n_hits_in_review: np.ndarray, review: int, confidence: float) -> int:
    """Smallest diversity purchase that reaches ``confidence``. -1 if the review set cannot."""
    for k in range(1, review + 1):
        if diversity_success_probability(n_hits_in_review, review, k) >= confidence:
            return k
    return -1


def simulate_library(
    *,
    n: int,
    pi: float,
    delta: float,
    n_rep: int,
    review: int,
    rng: np.random.Generator,
) -> dict[str, np.ndarray]:
    """Rank one library per replicate. Rank ``n + 1`` means that replicate had no active."""
    if n < review or review < 1:
        raise ContractViolation(f"review set {review} does not fit inside library {n}")
    if not 0.0 < pi < 1.0:
        raise ContractViolation(f"prior must lie in (0, 1), got {pi}")
    if n_rep < 1:
        raise ContractViolation(f"n_rep must be >= 1, got {n_rep}")
    active = rng.random((n_rep, n)) < pi
    scores = rng.normal(loc=np.where(active, delta, 0.0), scale=1.0)
    ranked = np.take_along_axis(active, np.argsort(-scores, axis=1), axis=1)
    has = ranked.any(axis=1)
    first = np.argmax(ranked, axis=1)
    n_top1 = int(round(EF_FRACTION * n))
    if n_top1 < 1:
        raise ContractViolation(f"top 1% of {n} is empty")
    return {
        "best": np.where(has, first + 1, n + 1).astype(int),
        "in_review": ranked[:, :review].sum(axis=1).astype(int),
        "in_top1": ranked[:, :n_top1].sum(axis=1).astype(int),
        "in_k8": ranked[:, :8].sum(axis=1).astype(int),
        "n_active": active.sum(axis=1).astype(int),
    }


def _empirical_ef(in_top1: np.ndarray, n_active: np.ndarray, n: int) -> float:
    n_top1 = int(round(EF_FRACTION * n))
    usable = n_active > 0
    if not np.any(usable):
        return float("nan")
    realised = (in_top1[usable] / n_top1) / (n_active[usable] / n)
    return float(np.mean(realised))


def _rank_curve(best: np.ndarray, k_max: int) -> list[float]:
    capped = np.minimum(best, k_max + 1)
    counts = np.bincount(capped, minlength=k_max + 2)
    cdf = np.cumsum(counts)
    return [float(value) for value in cdf[1 : k_max + 1] / best.size]


def summarise_cell(
    *,
    pi: float,
    ef: float,
    delta: float,
    drawn: dict[str, np.ndarray],
    library_size: int,
    review: int,
    scenario: str | None,
) -> tuple[dict[str, float | int], list[dict[str, float | int | str]]]:
    """Collapse one cell's replicates to the purchase probabilities."""
    best = drawn["best"]
    in_review = drawn["in_review"]
    n_rep = int(best.size)
    p8 = p_at_k(best, 8)
    mean_hits_k8 = float(np.mean(drawn["in_k8"]))
    row: dict[str, float | int] = {
        "pi": pi,
        "ef": ef,
        "delta": delta,
        "p_rank_k6": p_at_k(best, 6),
        "p_rank_k8": p8,
        "p_rank_k10": p_at_k(best, 10),
        "se_rank_k8": math.sqrt(p8 * (1.0 - p8) / n_rep),
        "k80_rank": k_for_confidence(best, CONFIDENCE_PRIMARY, library_size),
        "k50_rank": k_for_confidence(best, CONFIDENCE_SECONDARY, library_size),
        "p_div_k6": diversity_success_probability(in_review, review, 6),
        "p_div_k8": diversity_success_probability(in_review, review, 8),
        "p_div_k10": diversity_success_probability(in_review, review, 10),
        "k80_div": diversity_k_for_confidence(in_review, review, CONFIDENCE_PRIMARY),
        "p_library_has_active": float(np.mean(drawn["n_active"] > 0)),
        "mean_actives": float(np.mean(drawn["n_active"])),
        "mean_actives_in_review": float(np.mean(in_review)),
        "mean_hits_k8": mean_hits_k8,
        "enrichment_at_k8": mean_hits_k8 / 8.0 / pi,
        "empirical_ef1": _empirical_ef(drawn["in_top1"], drawn["n_active"], library_size),
        "n_reps": n_rep,
    }
    curves: list[dict[str, float | int | str]] = []
    if scenario is None:
        return row, curves
    for k, prob in enumerate(_rank_curve(best, CURVE_K_MAX), start=1):
        curves.append({"scenario": scenario, "pi": pi, "ef": ef, "k": k, "p_rank": prob})
    return row, curves


def run_grid(
    *,
    seed: int,
    n_rep: int,
    library_size: int = LIBRARY_SIZE,
    review: int = REVIEW_SET_SIZE,
    priors: Iterable[float] = PRIOR_GRID,
    efs: Iterable[float] = EF_GRID,
) -> tuple[list[dict[str, float | int]], list[dict[str, float | int | str]]]:
    """Sweep prior × docking EF. Scenario curves are included for the three named rows."""
    prior_list = tuple(priors)
    ef_list = tuple(efs)
    if QUOTED_PRIOR not in prior_list or QUOTED_EF not in ef_list:
        raise ContractViolation("quoted prior/EF row is not on the sweep grid")
    cells = [(pi, ef) for pi in prior_list for ef in ef_list]
    names = {(pi, ef): name for name, pi, ef in CURVE_SCENARIOS}
    children = np.random.SeedSequence(seed).spawn(len(cells))
    rows: list[dict[str, float | int]] = []
    curves: list[dict[str, float | int | str]] = []
    for (pi, ef), child in zip(cells, children, strict=True):
        delta = delta_for_ef(ef)
        drawn = simulate_library(
            n=library_size,
            pi=pi,
            delta=delta,
            n_rep=n_rep,
            review=review,
            rng=np.random.default_rng(child),
        )
        row, curve = summarise_cell(
            pi=pi,
            ef=ef,
            delta=delta,
            drawn=drawn,
            library_size=library_size,
            review=review,
            scenario=names.get((pi, ef)),
        )
        rows.append(row)
        curves.extend(curve)
    return rows, curves


def best_ranks_fast(
    *,
    n: int,
    pi: float,
    delta: float,
    n_rep: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """Best-active rank without drawing inactive scores.

    Conditional on the best active's score, the inactive count above it is binomial.
    """
    n_act = rng.binomial(n, pi, size=n_rep)
    best = np.full(n_rep, n + 1, dtype=int)
    width = int(n_act.max())
    if width == 0:
        return best
    scores = rng.normal(loc=delta, scale=1.0, size=(n_rep, width))
    keep = np.arange(width)[None, :] < n_act[:, None]
    s_max = np.where(keep, scores, -np.inf).max(axis=1)
    has = n_act > 0
    p_above = np.zeros(n_rep, dtype=float)
    for index in np.flatnonzero(has):
        p_above[int(index)] = 1.0 - norm_cdf(float(s_max[int(index)]))
    n_above = rng.binomial(n - n_act, np.clip(p_above, 0.0, 1.0))
    best[has] = 1 + n_above[has]
    return best


def _probability_gap(full: np.ndarray, fast: np.ndarray) -> float:
    return max(abs(p_at_k(full, k) - p_at_k(fast, k)) for k in _CHECK_KS)


def large_library_sensitivity(*, seed: int, n_check: int) -> dict[str, float | int | str]:
    """Quote N = 100,000 and 500,000 only if the fast rank model matches the full library.

    ## [ASSUMPTION: A31]
    """
    delta = delta_for_ef(QUOTED_EF)
    check_seed = np.random.SeedSequence([seed, 31])
    full_rng, fast_rng = (np.random.default_rng(child) for child in check_seed.spawn(2))
    full = simulate_library(
        n=LIBRARY_SIZE,
        pi=QUOTED_PRIOR,
        delta=delta,
        n_rep=n_check,
        review=REVIEW_SET_SIZE,
        rng=full_rng,
    )["best"]
    fast = best_ranks_fast(n=LIBRARY_SIZE, pi=QUOTED_PRIOR, delta=delta, n_rep=n_check, rng=fast_rng)
    gap = _probability_gap(full, fast)
    payload: dict[str, float | int | str] = {
        "check_max_abs_gap": gap,
        "check_tolerance": LARGE_LIBRARY_TOLERANCE,
        "status": "ok" if gap <= LARGE_LIBRARY_TOLERANCE else "check_failed",
    }
    if gap > LARGE_LIBRARY_TOLERANCE:
        return payload
    for size in LARGE_LIBRARY_SIZES:
        rng = np.random.default_rng(np.random.SeedSequence([seed, size]))
        ranks = best_ranks_fast(
            n=size,
            pi=QUOTED_PRIOR,
            delta=delta,
            n_rep=LARGE_LIBRARY_REPS,
            rng=rng,
        )
        payload[f"n{size}_p_k8"] = p_at_k(ranks, 8)
        payload[f"n{size}_p_k10"] = p_at_k(ranks, 10)
        payload[f"n{size}_k80"] = k_for_confidence(ranks, CONFIDENCE_PRIMARY, size)
    return payload
