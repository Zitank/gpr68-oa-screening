"""Numbers taken from the project plan's direct checks.

These are inputs, not quantities to re-derive. Analysis that disagrees is recorded;
it does not replace the value.
"""

from __future__ import annotations

# Pocket centres in the 8Z68 RCSB frame, two decimal places, as stated in the plan.
PLAN_CENTRES: dict[int, tuple[float, float, float]] = {
    1: (145.67, 128.56, 99.49),
    2: (129.32, 131.62, 117.61),
}

# Residues the plan names as lining each pocket. The 5 Å / 6 Å shells are computed
# separately and compared with these lists; the lists are not a filter.
PLAN_LINING: dict[int, tuple[str, ...]] = {
    1: (
        "HIS20",
        "TYR28",
        "TRP77",
        "TYR80",
        "VAL81",
        "LEU101",
        "TYR102",
        "CYS172",
        "GLU174",
        "TYR176",
        "HIS269",
        "LEU272",
    ),
    2: (
        "TYR106",
        "VAL109",
        "GLY110",
        "CYS113",
        "ILE145",
        "PHE196",
        "PRO197",
        "LEU200",
    ),
}

# Plan: chain R, residues 13–297, 2,174 atoms, zero HETATM.
PLAN_CHAIN = "R"
PLAN_RESSEQ_RANGE = (13, 297)
PLAN_CHAIN_R_ATOMS = 2174
PLAN_CHAIN_R_HETATM = 0

# Plan: pocket 1 is 60.3 Å from the Gs centroid; nearest chain-R atom is 2.7–4.1 Å.
PLAN_POCKET1_GS_DISTANCE_A = 60.3
PLAN_NEAREST_ATOM_RANGE_A = (2.7, 4.1)
