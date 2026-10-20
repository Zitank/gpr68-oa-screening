"""Parse PubChem assay summary and CSV. No network.

## [EXPLORATORY]
"""

from __future__ import annotations

import csv
import io
from typing import Any

from core.errors import ContractViolation

_GPR68_ACCESSION = "Q15743"
_SUMMARY_COUNT_FIELDS = (
    "CIDCountAll",
    "CIDCountActive",
    "CIDCountInactive",
    "CIDCountInconclusive",
    "CIDCountUnspecified",
    "SIDCountAll",
)


def parse_aid_list(payload: dict[str, Any]) -> list[int]:
    """AID integers from a PUG identifier-list document."""
    try:
        aids = payload["IdentifierList"]["AID"]
    except (KeyError, TypeError) as exc:
        raise ContractViolation("PubChem AID list payload has no IdentifierList.AID") from exc
    if not isinstance(aids, list) or not aids:
        raise ContractViolation("PubChem AID list is empty")
    return [int(aid) for aid in aids]


def parse_summaries(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """One dict per assay summary."""
    try:
        rows = payload["AssaySummaries"]["AssaySummary"]
    except (KeyError, TypeError) as exc:
        raise ContractViolation("PubChem summary payload has no AssaySummaries") from exc
    if not isinstance(rows, list) or not rows:
        raise ContractViolation("PubChem assay summary list is empty")
    parsed: list[dict[str, Any]] = []
    for row in rows:
        parsed.append(_one_summary(row))
    return parsed


def compound_assays(summaries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Assays with at least one compound. siRNA screens have CIDCountAll == 0."""
    usable = [row for row in summaries if row["CIDCountAll"] > 0]
    if not usable:
        raise ContractViolation("no PubChem assay has CIDCountAll > 0")
    return usable


def parse_assay_csv(text: str, *, aid: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Split an assay CSV into kept rows and off-target rows.

    BindingDB AID 2060853 names the protein on each row and includes non-GPR68
    receptors. Those rows are returned as off-target, not dropped quietly.
    ChEMBL-deposited assays have no target column; every data row is kept and
    marked ``target_accession='column_absent'``.
    """
    reader = csv.DictReader(io.StringIO(text))
    fieldnames = list(reader.fieldnames or [])
    if "PUBCHEM_CID" not in fieldnames:
        raise ContractViolation(f"AID {aid} CSV has no PUBCHEM_CID column")
    schema = _schema(fieldnames, aid)
    raw_rows = list(reader)
    if schema == "bindingdb":
        _assert_nanomolar(raw_rows, aid)
    kept: list[dict[str, Any]] = []
    off_target: list[dict[str, Any]] = []
    for raw in raw_rows:
        tag = (raw.get("PUBCHEM_RESULT_TAG") or "").strip()
        if not tag.isdigit():
            continue
        row = _one_result(raw, aid=aid, schema=schema)
        if row["target_accession"] not in {_GPR68_ACCESSION, "column_absent"}:
            off_target.append(row)
        else:
            kept.append(row)
    if not kept:
        raise ContractViolation(f"AID {aid} CSV has no rows to keep")
    return kept, off_target


def _one_summary(row: dict[str, Any]) -> dict[str, Any]:
    if "AID" not in row or "CIDCountAll" not in row:
        raise ContractViolation("PubChem summary row is missing AID or CIDCountAll")
    parsed: dict[str, Any] = {
        "AID": int(row["AID"]),
        "Name": _text(row.get("Name")),
        "SourceName": _text(row.get("SourceName")),
        "SourceID": _text(row.get("SourceID")),
    }
    for field in _SUMMARY_COUNT_FIELDS:
        if field not in row:
            raise ContractViolation(f"PubChem summary AID {row['AID']} missing {field}")
        parsed[field] = int(row[field])
    return parsed


def _assert_nanomolar(rows: list[dict[str, str]], aid: int) -> None:
    """BindingDB RESULT_UNIT must say NANOMOLAR for EC50 and IC50. Do not assume it."""
    unit_rows = [row for row in rows if (row.get("PUBCHEM_RESULT_TAG") or "").strip() == "RESULT_UNIT"]
    if len(unit_rows) != 1:
        raise ContractViolation(f"AID {aid} bindingdb CSV has {len(unit_rows)} RESULT_UNIT rows")
    for column in ("EC50", "IC50"):
        observed = (unit_rows[0].get(column) or "").strip().upper()
        if observed != "NANOMOLAR":
            raise ContractViolation(f"AID {aid} {column} unit is {observed!r}, expected NANOMOLAR")


def _schema(fieldnames: list[str], aid: int) -> str:
    if "Target Accession(s)" in fieldnames and "EC50" in fieldnames:
        return "bindingdb"
    if "Standard Type" in fieldnames and "Standard Value" in fieldnames:
        return "standard"
    raise ContractViolation(f"AID {aid} CSV columns are not a known schema: {fieldnames}")


def _one_result(raw: dict[str, str], *, aid: int, schema: str) -> dict[str, Any]:
    cid = (raw.get("PUBCHEM_CID") or "").strip()
    smiles = (raw.get("PUBCHEM_EXT_DATASOURCE_SMILES") or "").strip()
    outcome = (raw.get("PUBCHEM_ACTIVITY_OUTCOME") or "").strip()
    tag = (raw.get("PUBCHEM_RESULT_TAG") or "").strip()
    if cid == "" or smiles == "" or outcome == "":
        raise ContractViolation(f"AID {aid} result tag {tag} is incomplete")
    standard_type = (raw.get("Standard Type") or "").strip()
    if standard_type == "":
        raise ContractViolation(f"AID {aid} result tag {tag} has no Standard Type")
    if schema == "bindingdb":
        measurement = _bindingdb_measurement(raw, aid=aid, tag=tag, standard_type=standard_type)
    else:
        measurement = _standard_measurement(raw)
    return {
        "aid": aid,
        "sid": (raw.get("PUBCHEM_SID") or "").strip(),
        "cid": cid,
        "smiles": smiles,
        "outcome": outcome,
        "standard_type": standard_type,
        "relation": measurement["relation"],
        "value": measurement["value"],
        "unit": measurement["unit"],
        "target_accession": measurement["target_accession"],
        "comment": (raw.get("Activity Comment") or raw.get("PUBCHEM_ASSAYDATA_COMMENT") or "").strip(),
    }


def _bindingdb_measurement(raw: dict[str, str], *, aid: int, tag: str, standard_type: str) -> dict[str, str]:
    accession = (raw.get("Target Accession(s)") or "").strip()
    if accession == "":
        raise ContractViolation(f"AID {aid} result tag {tag} has an empty target accession")
    if standard_type == "EC50":
        value = (raw.get("EC50") or "").strip()
        unit = "nM"
        relation = _agreeing_relation(
            (raw.get("EC50 Qualifier") or "").strip(),
            (raw.get("Standard Relation") or "").strip(),
            aid=aid,
            tag=tag,
        )
    elif standard_type == "IC50":
        value = (raw.get("IC50") or "").strip()
        unit = "nM"
        relation = (raw.get("Standard Relation") or "").strip()
    else:
        raise ContractViolation(f"AID {aid} result tag {tag} has unsupported type {standard_type}")
    if value == "":
        raise ContractViolation(f"AID {aid} result tag {tag} has an empty {standard_type}")
    return {"relation": relation, "value": value, "unit": unit, "target_accession": accession}


def _standard_measurement(raw: dict[str, str]) -> dict[str, str]:
    return {
        "relation": (raw.get("Standard Relation") or "").strip(),
        "value": (raw.get("Standard Value") or "").strip(),
        "unit": (raw.get("Standard Units") or "").strip(),
        "target_accession": "column_absent",
    }


def _agreeing_relation(left: str, right: str, *, aid: int, tag: str) -> str:
    if left and right and left != right:
        raise ContractViolation(f"AID {aid} result tag {tag} qualifiers disagree: {left!r} vs {right!r}")
    return left or right


def _text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return " ".join(str(part) for part in value)
    return str(value)
