"""Compare a harvest against the plan's pre-checked baseline. Never edits the data to match.

## [EXPLORATORY]
"""

from __future__ import annotations

from typing import Any

# Counts established by a direct API check and recorded in the project plan.
# They are the comparison baseline, not values to force the harvest toward.
EXPECTED_CHEMBL = {
    "activities": 340,
    "molecules": 94,
    "assays": 21,
    "documents": 8,
    "pchembl_rows": 14,
    "pchembl_molecules": 10,
}
EXPECTED_STANDARD_TYPES = {
    "log(activity)": 134,
    "pKb": 96,
    "Activity_index": 67,
    "EC50": 14,
    "Activity": 12,
    "Emax": 12,
    "IC50": 2,
}
EXPECTED_PUBCHEM_AIDS = 22
EXPECTED_AID_CIDS = {
    2060853: {"cid_count_all": 52, "cid_count_active": 39, "cid_count_inactive": 13},
    1607983: {"cid_count_all": 67},
    1912832: {"cid_count_all": 1},
    1364851: {"cid_count_all": 1},
}
# The plan names these four. CIDCountAll > 0 is the filter that decides what is kept.
EXPECTED_COMPOUND_AIDS = frozenset(EXPECTED_AID_CIDS)


def compare_baseline(
    chembl: dict[str, Any],
    standard_types: dict[str, int],
    n_aids: int,
    aid_summaries: dict[int, dict[str, int]],
    molecules_per_document: dict[str, int],
) -> dict[str, list[str]]:
    """Return discrepancy strings. An empty list means the headline counts matched."""
    discrepancies: list[str] = []
    _chembl_counts(chembl, discrepancies)
    _type_counts(standard_types, discrepancies)
    if n_aids != EXPECTED_PUBCHEM_AIDS:
        discrepancies.append(f"PubChem AID count: observed {n_aids}, baseline {EXPECTED_PUBCHEM_AIDS}")
    _aid_counts(aid_summaries, discrepancies)
    top_two = sorted(molecules_per_document.values(), reverse=True)[:2]
    if top_two != [67, 29]:
        discrepancies.append(f"molecules in the two largest documents: observed {top_two}, baseline [67, 29]")
    return {"discrepancies": discrepancies}


def _chembl_counts(chembl: dict[str, Any], discrepancies: list[str]) -> None:
    for key, expected in EXPECTED_CHEMBL.items():
        observed = chembl[key]
        if observed != expected:
            discrepancies.append(f"ChEMBL {key}: observed {observed}, baseline {expected}")


def _type_counts(standard_types: dict[str, int], discrepancies: list[str]) -> None:
    for name, expected in EXPECTED_STANDARD_TYPES.items():
        observed = standard_types.get(name, 0)
        if observed != expected:
            discrepancies.append(f"ChEMBL standard_type {name}: observed {observed}, baseline {expected}")
    extra = sorted(set(standard_types) - set(EXPECTED_STANDARD_TYPES))
    for name in extra:
        discrepancies.append(
            f"ChEMBL standard_type {name} has {standard_types[name]} rows and is absent "
            "from the plan's endpoint list"
        )


def _aid_counts(aid_summaries: dict[int, dict[str, int]], discrepancies: list[str]) -> None:
    for aid, expected_fields in EXPECTED_AID_CIDS.items():
        if aid not in aid_summaries:
            discrepancies.append(f"PubChem AID {aid} missing from the GeneID 8111 summary")
            continue
        observed = aid_summaries[aid]
        for field, expected in expected_fields.items():
            if observed.get(field) != expected:
                discrepancies.append(
                    f"PubChem AID {aid} {field}: observed {observed.get(field)}, baseline {expected}"
                )
    observed_compound = sorted(
        aid for aid, fields in aid_summaries.items() if fields.get("cid_count_all", 0) > 0
    )
    for aid in observed_compound:
        if aid not in EXPECTED_COMPOUND_AIDS:
            discrepancies.append(
                f"PubChem AID {aid} has CIDCountAll > 0 and is not in the plan's named usable "
                f"set {sorted(EXPECTED_COMPOUND_AIDS)}; it is kept because the filter is CIDCountAll > 0"
            )
    for aid in sorted(EXPECTED_COMPOUND_AIDS.difference(observed_compound)):
        discrepancies.append(f"PubChem AID {aid} was named as usable but has no compounds in the summary")
