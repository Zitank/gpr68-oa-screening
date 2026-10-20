"""Parse a ChEMBL activity JSON document for one target. No network.

## [EXPLORATORY]
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from core.errors import ContractViolation


def parse_activity_document(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Return one dict per activity. Raises if the document is not the activity schema."""
    if "activities" not in payload or "page_meta" not in payload:
        raise ContractViolation("ChEMBL payload is missing activities or page_meta")
    activities = payload["activities"]
    if not isinstance(activities, list) or not activities:
        raise ContractViolation("ChEMBL activities list is empty")
    total = payload["page_meta"].get("total_count")
    if total != len(activities):
        raise ContractViolation(
            f"ChEMBL page is incomplete: got {len(activities)} activities, total_count={total}"
        )
    rows: list[dict[str, Any]] = []
    for activity in activities:
        rows.append(_one_activity(activity))
    return rows


def chembl_census(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Headline counts used by the baseline check."""
    pchembl = [row for row in rows if row["pchembl_value"] is not None]
    return {
        "activities": len(rows),
        "molecules": len({row["molecule_chembl_id"] for row in rows}),
        "assays": len({row["assay_chembl_id"] for row in rows}),
        "documents": len({row["document_chembl_id"] for row in rows}),
        "pchembl_rows": len(pchembl),
        "pchembl_molecules": len({row["molecule_chembl_id"] for row in pchembl}),
        "standard_types": dict(Counter(row["standard_type"] for row in rows)),
        "molecules_per_document": _molecules_per_document(rows),
        "activities_per_document": dict(Counter(row["document_chembl_id"] for row in rows)),
    }


def _molecules_per_document(rows: list[dict[str, Any]]) -> dict[str, int]:
    grouped: dict[str, set[str]] = {}
    for row in rows:
        grouped.setdefault(row["document_chembl_id"], set()).add(row["molecule_chembl_id"])
    return {doc: len(mols) for doc, mols in grouped.items()}


def _one_activity(activity: dict[str, Any]) -> dict[str, Any]:
    required = (
        "molecule_chembl_id",
        "canonical_smiles",
        "assay_chembl_id",
        "document_chembl_id",
        "standard_type",
        "assay_description",
    )
    missing = [key for key in required if key not in activity]
    if missing:
        raise ContractViolation(f"ChEMBL activity missing fields {missing}")
    smiles = activity["canonical_smiles"]
    if not isinstance(smiles, str) or smiles.strip() == "":
        raise ContractViolation(f"ChEMBL activity {activity.get('activity_id')} has no SMILES")
    return {
        "activity_id": activity.get("activity_id"),
        "molecule_chembl_id": activity["molecule_chembl_id"],
        "pref_name": activity.get("molecule_pref_name"),
        "canonical_smiles": smiles,
        "assay_chembl_id": activity["assay_chembl_id"],
        "assay_description": activity["assay_description"] or "",
        "document_chembl_id": activity["document_chembl_id"],
        "document_journal": activity.get("document_journal"),
        "document_year": activity.get("document_year"),
        "standard_type": activity["standard_type"],
        "standard_relation": activity.get("standard_relation"),
        "standard_value": activity.get("standard_value"),
        "standard_units": activity.get("standard_units"),
        "standard_text_value": activity.get("standard_text_value"),
        "activity_comment": activity.get("activity_comment"),
        "pchembl_value": activity.get("pchembl_value"),
        "target_chembl_id": activity.get("target_chembl_id"),
    }
