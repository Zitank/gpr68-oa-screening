"""The four task-specified reference compounds, checked against the harvest.

## [EXPLORATORY]
"""

from __future__ import annotations

from clusters.ligand_data.src.chemistry import parse_structure, same_scaffold_different_structure
from core.errors import ContractViolation

# The plan's ZINC SMILES is printed with a space (`cccc c2`). This is that string with the space removed.
_OGERIN_PLAN = "Nc1nc(NCc2ccccc2)nc(-c2ccccc2CO)n1"
_ZINC_PLAN = "Nc1nc(NCc2ccccc2)nc(-c2cccc(CO)c2)n1"

_SPECS = (
    {"name": "Ogerin", "chembl_id": "CHEMBL4548689", "pubchem_id": "CID56707820"},
    {"name": "ZINC32547799", "chembl_id": "CHEMBL4460070", "pubchem_id": "CID39791182"},
    {"name": "lorazepam", "chembl_id": "CHEMBL580", "pubchem_id": "CID3958"},
    {"name": "MS48107", "chembl_id": "CHEMBL4449712", "pubchem_id": "CID139030523"},
)


def reference_report(
    rows: list[dict[str, str]],
    *,
    identities: list[dict[str, str]] | None = None,
) -> list[dict[str, str]]:
    """One row per reference compound. Missing Ogerin or ZINC32547799 is a contract failure.

    ``identities`` supplies a structure fetched on its own when a named compound has no
    preferred name. MS48107 is CHEMBL4449712 (no preferred name; InChIKey
    KKHDNAZPEMYUNO-UHFFFAOYSA-N, five rows in CHEMBL4406806 including pKb 5.85).
    A name search misses it. It is not in the GeneID 8111 PubChem assays.
    """
    report: list[dict[str, str]] = []
    for spec in _SPECS:
        report.append(_one(spec, rows, identities or []))
    _assert_isomers(rows)
    return report


def isomer_status(rows: list[dict[str, str]]) -> dict[str, str]:
    """Compare harvested Ogerin and ZINC32547799 with each other and with the plan SMILES."""
    ogerin = _required_smiles(rows, "CHEMBL4548689", "Ogerin")
    zinc = _required_smiles(rows, "CHEMBL4460070", "ZINC32547799")
    left = parse_structure(ogerin, label="Ogerin")
    right = parse_structure(zinc, label="ZINC32547799")
    plan_ogerin = parse_structure(_OGERIN_PLAN, label="plan Ogerin")
    plan_zinc = parse_structure(_ZINC_PLAN, label="plan ZINC32547799")
    return {
        "ogerin_matches_plan_smiles": str(left.smiles == plan_ogerin.smiles).lower(),
        "zinc_matches_plan_smiles": str(right.smiles == plan_zinc.smiles).lower(),
        "same_murcko_different_structure": str(same_scaffold_different_structure(left, right)).lower(),
        "ogerin_murcko": left.murcko,
        "zinc_murcko": right.murcko,
        "ogerin_inchikey": left.inchikey,
        "zinc_inchikey": right.inchikey,
    }


def _assert_isomers(rows: list[dict[str, str]]) -> None:
    status = isomer_status(rows)
    if status["same_murcko_different_structure"] != "true":
        raise ContractViolation(
            "Ogerin and ZINC32547799 are not a same-scaffold pair in the harvested structures"
        )


def _one(
    spec: dict[str, str], rows: list[dict[str, str]], identities: list[dict[str, str]]
) -> dict[str, str]:
    chembl_hits = (
        [row for row in rows if row["compound_id"] == spec["chembl_id"]] if spec["chembl_id"] else []
    )
    pubchem_hits = [row for row in rows if row["compound_id"] == spec["pubchem_id"]]
    if spec["name"] in {"Ogerin", "ZINC32547799", "lorazepam"} and not chembl_hits:
        raise ContractViolation(f"{spec['name']} is absent from the ChEMBL harvest")
    if chembl_hits or pubchem_hits:
        smiles = (chembl_hits or pubchem_hits)[0]["smiles"]
        present = "yes"
    else:
        identity = next((item for item in identities if item["pubchem_id"] == spec["pubchem_id"]), None)
        if identity is None:
            raise ContractViolation(f"{spec['name']} is absent from the harvest and has no identity record")
        smiles = identity["smiles"]
        present = "identity_only"
    return {
        "compound_name": spec["name"],
        "chembl_id": spec["chembl_id"],
        "pubchem_id": spec["pubchem_id"],
        "smiles": smiles,
        "n_chembl_rows": str(len(chembl_hits)),
        "n_pubchem_rows": str(len(pubchem_hits)),
        "present": present,
    }


def _required_smiles(rows: list[dict[str, str]], compound_id: str, label: str) -> str:
    matches = [row["smiles"] for row in rows if row["compound_id"] == compound_id]
    if not matches:
        raise ContractViolation(f"{label} ({compound_id}) has no harvested SMILES")
    unique = set(matches)
    if len(unique) != 1:
        raise ContractViolation(f"{label} has multiple canonical SMILES: {sorted(unique)}")
    return next(iter(unique))
