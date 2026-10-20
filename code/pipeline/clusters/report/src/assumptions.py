"""Constants for the report packet. Ids from A20, plus the open A4 prior.

## [EXPLORATORY]
Registration belongs in governance/assumptions.md; this module does not write that file.
"""

from __future__ import annotations

# ## [ASSUMPTION: A4] per-compound prior that a library member is a true functional GPR68 modulator.
# Bounds were unset. The sweep is this grid, from 1e-4 to 1e-2. Not a literature hit rate.
PRIOR_GRID: tuple[float, ...] = (1e-4, 2e-4, 5e-4, 1e-3, 2e-3, 5e-3, 1e-2)

# ## [ASSUMPTION: A20] first-round library size named in Methods.md (MCE 5K / 5,000 compounds).
LIBRARY_SIZE: int = 5000

# ## [ASSUMPTION: A21] docked compounds kept for clustering and review.
# Upper end of the Methods.md "top 50–100".
REVIEW_SET_SIZE: int = 100

# ## [ASSUMPTION: A22] diversity purchase draws k compounds uniformly from the review set.
# Scaffold clustering plus manual review is modelled as diversity selection, not as a second activity model.

# ## [ASSUMPTION: A23] docking scores are independent N(delta, 1) for actives and N(0, 1) for inactives.
# delta is set so the large-sample rare-hit enrichment at the top 1% equals the swept EF.
# The sweep is this grid. EF = 1 is no enrichment. EF = 30 is strong for a classical score.
EF_GRID: tuple[float, ...] = (1.0, 2.0, 3.0, 5.0, 8.0, 12.0, 20.0, 30.0)
EF_FRACTION: float = 0.01

# ## [ASSUMPTION: A24] row quoted in the plain-language recommendation. A grid point, not a believed truth.
QUOTED_PRIOR: float = 1e-3
QUOTED_EF: float = 5.0

# ## [ASSUMPTION: A25] confidence used for the recommended purchase count. 0.50 is reported beside it.
CONFIDENCE_PRIMARY: float = 0.80
CONFIDENCE_SECONDARY: float = 0.50

# Curve figure scenarios. All three sit on PRIOR_GRID x EF_GRID.
CURVE_SCENARIOS: tuple[tuple[str, float, float], ...] = (
    ("low", 1e-4, 2.0),
    ("quoted", QUOTED_PRIOR, QUOTED_EF),
    ("high", 1e-2, 30.0),
)
CURVE_K_MAX: int = 250

FUNNEL_SEED: int = 20261004
FUNNEL_REPS: int = 2000

# ## [ASSUMPTION: A26] calcium-assay simulation truth, percent of a reference maximum.
# Not a measured ogerin potency. Primary fit fixes the asymptotes at the same bounds.
# drc's LL.4 slope is negative when the response rises with dose.
DOSE_SLOPE: float = -1.0
DOSE_LOWER: float = 0.0
DOSE_UPPER: float = 100.0
DOSE_EC50_UM: float = 1.0
DOSE_SD: float = 10.0
DOSE_SEED: int = 20261005
DOSE_REPS: int = 250

# ## [ASSUMPTION: A27] shift the assay must distinguish, and the precision bar, on the EC50 fold scale.
# The pH 7.4 versus pH 6.8 contrast reuses this shift and the same noise model. pH 7.0 is not a third curve.
POTENCY_SHIFT: float = 3.0
CI_FOLD_LIMIT: float = 3.0
CI_FOLD_FRACTION: float = 0.80
COVERAGE_FLOOR: float = 0.90
CONVERGENCE_FLOOR: float = 0.95
SHIFT_POWER: float = 0.80

DOSE_DESIGNS: tuple[tuple[str, tuple[float, ...]], ...] = (
    ("C6", (0.1, 0.3, 1.0, 3.0, 10.0, 30.0)),
    ("C8", (0.03, 0.1, 0.3, 1.0, 3.0, 10.0, 30.0, 100.0)),
    ("C10", (0.01, 0.03, 0.1, 0.3, 1.0, 3.0, 10.0, 30.0, 100.0, 300.0)),
)
DOSE_REPLICATES: tuple[int, ...] = (2, 3, 4, 6)

# ## [ASSUMPTION: A28] SD of delta-Ct across biological replicates, in Ct cycles.
# The primary value is 0.5. 0.3 and 0.8 are the sensitivity. Housekeeping is already inside this SD.
QPCR_SD_PRIMARY: float = 0.5
QPCR_SD_GRID: tuple[float, ...] = (0.3, 0.5, 0.8)

# ## [ASSUMPTION: A29] fold-change the chondrocyte qPCR is sized to detect, and the power target.
QPCR_FOLD: float = 2.0
QPCR_POWER: float = 0.80

# ## [ASSUMPTION: A30] two-sided alpha. Primary contrast is OA model versus OA model plus compound.
# The four genes are not pooled. 0.0125 is Bonferroni for those four genes.
QPCR_ALPHA: float = 0.05
QPCR_ALPHA_BONFERRONI: float = 0.0125
QPCR_GENES: tuple[str, ...] = ("MMP13", "ADAMTS5", "COL2A1", "ACAN")
QPCR_N_GRID: tuple[int, ...] = (3, 4, 5, 6, 8, 10, 12, 16)
QPCR_SEED: int = 20261006

# ## [ASSUMPTION: A31] programme-scale library sizes from the preliminary plan, sensitivity only.
# Same per-compound prior and same score separation as the primary run. Not a compute plan.
LARGE_LIBRARY_SIZES: tuple[int, ...] = (100_000, 500_000)
LARGE_LIBRARY_REPS: int = 4000
LARGE_LIBRARY_TOLERANCE: float = 0.03
