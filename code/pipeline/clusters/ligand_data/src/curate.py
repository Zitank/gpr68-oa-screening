"""Build one activity row per molecule, assay and endpoint.

## [EXPLORATORY]
## [ASSUMPTION: A11]
A PubChem row whose SourceName is ChEMBL is a mirror of the ChEMBL harvest.
It enters the reference table only when that InChIKey and endpoint are absent from the ChEMBL rows.
## [ASSUMPTION: A12]
modulation_type is read from assay text: positive allosteric or allosteric modulator maps to PAM;
antagonist; inhibitor or inhibition; agonist; otherwise unspecified.
"""

from __future__ import annotations

from typing import Any

from clusters.ligand_data.src.chemistry import ParsedStructure, parse_structure
from clusters.ligand_data.src.records import (
    ActivityRecord,
    assert_one_row_per_endpoint,
    assert_units_consistent,
)
from core.errors import ContractViolation

REFERENCE_COLUMNS = (
    "compound_name",
    "smiles",
    "modulation_type",
    "activity_type",
    "activity_value",
    "activity_unit",
    "assay",
    "reference",
    "source",
)

CURATED_COLUMNS = (
    "compound_id",
    "compound_name",
    "smiles",
    "raw_smiles",
    "inchikey",
    "murcko_scaffold",
    "modulation_type",
    "activity_type",
    "activity_value",
    "activity_unit",
    "assay_id",
    "assay",
    "document_chembl_id",
    "reference",
    "source",
    "source_url",
    "retrieved_utc",
    "activity_outcome",
    "mirror_of_chembl",
    "in_reference_table",
)

# Names fixed by the task for the four reference compounds. Other names come from the source.
_REFERENCE_NAMES = {
    "CHEMBL4548689": "Ogerin",
    "CHEMBL4460070": "ZINC32547799",
    "CHEMBL580": "lorazepam",
    "139030523": "MS48107",
}

_PATENT_TOKEN = "US12194027"


def modulation_type(text: str) -> str:
    """Map assay wording onto a modulation label. See A12."""
    lowered = text.lower()
    if "positive allosteric" in lowered or "allosteric modulator" in lowered:
        return "PAM"
    if "antagonist" in lowered:
        return "antagonist"
    if "inhibitor" in lowered or "inhibition of" in lowered:
        return "inhibitor"
    if "agonist" in lowered:
        return "agonist"
    return "unspecified"


def format_activity_value(relation: object, value: object, text: object) -> str:
    """Keep censored measurements censored. Do not coerce '>' into a point estimate."""
    if value is None or value == "":
        return _text_value(text)
    number = _number_string(value)
    rel = "" if relation is None else str(relation).strip()
    if rel in {"", "="}:
        return number
    if rel not in {">", "<", ">=", "<=", "~"}:
        raise ContractViolation(f"unrecognised activity relation {rel!r}")
    return f"{rel}{number}"


def chembl_rows(
    activities: list[dict[str, Any]],
    *,
    source_url: str,
    retrieved_utc: str,
) -> list[dict[str, str]]:
    """One curated row per ChEMBL activity."""
    rows: list[dict[str, str]] = []
    for activity in activities:
        parsed = parse_structure(activity["canonical_smiles"], label=activity["molecule_chembl_id"])
        assay_text = f"{activity['assay_chembl_id']}: {activity['assay_description']}"
        rows.append(
            _row(
                compound_id=activity["molecule_chembl_id"],
                compound_name=_chembl_name(activity),
                parsed=parsed,
                raw_smiles=activity["canonical_smiles"],
                modulation=modulation_type(activity["assay_description"]),
                activity_type=activity["standard_type"],
                activity_value=format_activity_value(
                    activity["standard_relation"],
                    activity["standard_value"],
                    activity["standard_text_value"] or activity["activity_comment"],
                ),
                activity_unit="" if activity["standard_units"] is None else str(activity["standard_units"]),
                assay_id=activity["assay_chembl_id"],
                assay=assay_text,
                document_id=activity["document_chembl_id"],
                reference=_document_reference(activity),
                source="ChEMBL",
                source_url=source_url,
                retrieved_utc=retrieved_utc,
                outcome="",
                mirror="no",
            )
        )
    return rows


def pubchem_rows(
    measurements: list[dict[str, Any]],
    *,
    summary: dict[str, Any],
    source_url: str,
    retrieved_utc: str,
) -> list[dict[str, str]]:
    """One curated row per kept PubChem result row."""
    aid = int(summary["AID"])
    assay_text = f"AID {aid}: {summary['Name']}"
    reference = _pubchem_reference(summary)
    mirror = "yes" if summary["SourceName"] == "ChEMBL" else "no"
    rows: list[dict[str, str]] = []
    for measurement in measurements:
        label = f"CID{measurement['cid']}"
        parsed = parse_structure(measurement["smiles"], label=label)
        rows.append(
            _row(
                compound_id=f"CID{measurement['cid']}",
                compound_name=_pubchem_name(measurement["cid"]),
                parsed=parsed,
                raw_smiles=measurement["smiles"],
                modulation=modulation_type(summary["Name"]),
                activity_type=measurement["standard_type"],
                activity_value=format_activity_value(
                    measurement["relation"], measurement["value"], measurement["comment"]
                ),
                activity_unit=measurement["unit"],
                assay_id=f"AID{aid}",
                assay=assay_text,
                document_id="",
                reference=reference,
                source="PubChem",
                source_url=source_url,
                retrieved_utc=retrieved_utc,
                outcome=measurement["outcome"],
                mirror=mirror,
            )
        )
    return rows


def select_reference_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """Apply LD2 and mark ``in_reference_table`` on every row. Returns the reference subset."""
    chembl_keys = {(row["inchikey"], row["activity_type"]) for row in rows if row["source"] == "ChEMBL"}
    selected: list[dict[str, str]] = []
    for row in rows:
        keep = _keep_for_reference(row, chembl_keys)
        row["in_reference_table"] = "yes" if keep else "no"
        if keep:
            selected.append(row)
    if not selected:
        raise ContractViolation("reference table is empty")
    _assert_reference_contract(selected)
    return selected


def reference_frame_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """Project curated rows onto the methods-document columns, in that order."""
    projected: list[dict[str, str]] = []
    for row in rows:
        projected.append({column: row[column] for column in REFERENCE_COLUMNS})
    return projected


def modeling_table(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """One molecule per CID from AID 2060853, labeled by the deposited activity outcome.

    Potency is intentionally absent: an EC50 threshold is the outcome rule, so using it
    as a feature would leak the label.
    """
    patent = [row for row in rows if row["assay_id"] == "AID2060853"]
    if not patent:
        raise ContractViolation("AID 2060853 produced no curated rows")
    by_compound: dict[str, list[dict[str, str]]] = {}
    for row in patent:
        by_compound.setdefault(row["compound_id"], []).append(row)
    table: list[dict[str, str]] = []
    for compound_id, group in sorted(by_compound.items()):
        outcomes = {row["activity_outcome"] for row in group}
        if outcomes != {"Active"} and outcomes != {"Inactive"}:
            raise ContractViolation(f"{compound_id} has conflicting AID 2060853 outcomes {sorted(outcomes)}")
        outcome = next(iter(outcomes))
        first = group[0]
        table.append(
            {
                "compound_id": compound_id,
                "compound_name": first["compound_name"],
                "smiles": first["smiles"],
                "inchikey": first["inchikey"],
                "murcko_scaffold": first["murcko_scaffold"],
                "label": "1" if outcome == "Active" else "0",
                "activity_outcome": outcome,
                "n_endpoints": str(len(group)),
                "activity_types": ";".join(sorted({row["activity_type"] for row in group})),
                "activity_values": ";".join(row["activity_value"] for row in group),
            }
        )
    return table


def _keep_for_reference(row: dict[str, str], chembl_keys: set[tuple[str, str]]) -> bool:
    if row["mirror_of_chembl"] != "yes":
        return True
    return (row["inchikey"], row["activity_type"]) not in chembl_keys


def _assert_reference_contract(rows: list[dict[str, str]]) -> None:
    records = [
        ActivityRecord(
            compound_id=row["compound_id"],
            smiles=row["smiles"],
            source="chembl" if row["source"] == "ChEMBL" else "pubchem",
            source_assay_id=row["assay_id"],
            document_id=row["document_chembl_id"] or None,
            endpoint=row["activity_type"],
            value=_optional_float(row["activity_value"]),
            unit=row["activity_unit"] or None,
        )
        for row in rows
    ]
    assert_one_row_per_endpoint(records)
    assert_units_consistent(records)


# Text deposited in place of a number. Anything else with no number is a contract failure.
_NON_NUMERIC_VALUES = frozenset({"Not Active", "Active", "Dose-dependent effect"})


def _optional_float(value: str) -> float | None:
    if value in {"", *_NON_NUMERIC_VALUES}:
        return None
    token = value
    for prefix in (">=", "<=", ">", "<", "~"):
        if token.startswith(prefix):
            token = token[len(prefix) :]
            break
    try:
        return float(token)
    except ValueError as exc:
        raise ContractViolation(f"activity value {value!r} is not numeric") from exc


def _row(
    *,
    compound_id: str,
    compound_name: str,
    parsed: ParsedStructure,
    raw_smiles: str,
    modulation: str,
    activity_type: str,
    activity_value: str,
    activity_unit: str,
    assay_id: str,
    assay: str,
    document_id: str,
    reference: str,
    source: str,
    source_url: str,
    retrieved_utc: str,
    outcome: str,
    mirror: str,
) -> dict[str, str]:
    return {
        "compound_id": compound_id,
        "compound_name": compound_name,
        "smiles": parsed.smiles,
        "raw_smiles": raw_smiles,
        "inchikey": parsed.inchikey,
        "murcko_scaffold": parsed.murcko,
        "modulation_type": modulation,
        "activity_type": activity_type,
        "activity_value": activity_value,
        "activity_unit": activity_unit,
        "assay_id": assay_id,
        "assay": assay,
        "document_chembl_id": document_id,
        "reference": reference,
        "source": source,
        "source_url": source_url,
        "retrieved_utc": retrieved_utc,
        "activity_outcome": outcome,
        "mirror_of_chembl": mirror,
        "in_reference_table": "",
    }


def _chembl_name(activity: dict[str, Any]) -> str:
    chembl_id = activity["molecule_chembl_id"]
    if chembl_id in _REFERENCE_NAMES:
        return _REFERENCE_NAMES[chembl_id]
    pref = activity.get("pref_name")
    if isinstance(pref, str) and pref.strip():
        return pref
    return chembl_id


def _pubchem_name(cid: str) -> str:
    if cid in _REFERENCE_NAMES:
        return _REFERENCE_NAMES[cid]
    return f"CID{cid}"


def _document_reference(activity: dict[str, Any]) -> str:
    journal = activity.get("document_journal") or ""
    year = activity.get("document_year")
    doc = activity["document_chembl_id"]
    head = " ".join(part for part in (str(journal).strip(), "" if year is None else str(year)) if part)
    if head:
        return f"{head} ({doc})"
    return doc


def _pubchem_reference(summary: dict[str, Any]) -> str:
    name = summary["Name"]
    aid = summary["AID"]
    if _PATENT_TOKEN in name:
        return f"US Patent {_PATENT_TOKEN} (AID {aid})"
    source_id = summary["SourceID"]
    source = summary["SourceName"]
    return f"{source} {source_id} (AID {aid})".strip()


def _text_value(text: object) -> str:
    if not isinstance(text, str):
        return ""
    stripped = text.strip()
    lowered = stripped.lower()
    if lowered in {"not active", "notactive"}:
        return "Not Active"
    if lowered == "active":
        return "Active"
    if stripped in _NON_NUMERIC_VALUES:
        return stripped
    if stripped == "":
        return ""
    raise ContractViolation(f"unrecognised non-numeric activity text {stripped!r}")


def _number_string(value: object) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ContractViolation(f"activity value has unsupported type {type(value).__name__}")
    if isinstance(value, str):
        stripped = value.strip()
        if stripped == "":
            raise ContractViolation("empty activity value reached numeric formatting")
        float(stripped)
        return stripped
    return format(value, ".10g")
