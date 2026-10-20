"""Harvest ChEMBL CHEMBL3713916 and PubChem GeneID 8111 compound assays.

## [EXPLORATORY]
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from rdkit import Chem
from rdkit.Chem import rdMolDescriptors

from clusters.ligand_data.src.baseline import compare_baseline
from clusters.ligand_data.src.chemistry import morgan_fingerprint, parse_structure, tanimoto
from clusters.ligand_data.src.curate import (
    CURATED_COLUMNS,
    REFERENCE_COLUMNS,
    chembl_rows,
    modeling_table,
    pubchem_rows,
    reference_frame_rows,
    select_reference_rows,
)
from clusters.ligand_data.src.figures import write_provenance_figure
from clusters.ligand_data.src.http_client import fetch_bytes
from clusters.ligand_data.src.parse_chembl import chembl_census, parse_activity_document
from clusters.ligand_data.src.parse_pubchem import (
    compound_assays,
    parse_aid_list,
    parse_assay_csv,
    parse_summaries,
)
from clusters.ligand_data.src.references import isomer_status, reference_report
from clusters.ligand_data.src.tables import write_matrix, write_table
from core.config import ExperimentConfig
from core.errors import ContractViolation
from core.hashing import sha256_file
from core.ledger import run_logged

_REPO = Path(__file__).resolve().parents[3]
_CHEMBL_URL = "https://www.ebi.ac.uk/chembl/api/data/activity.json?target_chembl_id=CHEMBL3713916&limit=1000"
_AID_URL = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/assay/target/geneid/8111/aids/JSON"
_SUMMARY_URL = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/assay/target/geneid/8111/summary/JSON"
_SEED = 20261004
_NAMED_USABLE_AIDS = {2060853, 1607983, 1912832, 1364851}
_MS48107_URL = (
    "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/139030523/"
    "property/MolecularFormula,IsomericSMILES/JSON"
)
_MS48107_FORMULA = "C23H20FN5O2"
_PATENT_ASSAY = "AID2060853"


def main() -> dict[str, Any]:
    """Logged harvest. The ledger line is the audit record; files land under data/ and results/."""
    cfg = ExperimentConfig(
        name="m1-ligand-harvest",
        seed=_SEED,
        mode="exploratory",
        condition_code="chembl3713916-pubchem-gene8111",
        study_id="M1",
        params={
            "target_chembl_id": "CHEMBL3713916",
            "gene_id": 8111,
            "morgan_radius": 2,
            "morgan_bits": 2048,
        },
    )
    return run_logged(cfg, _harvest, ledger_path=_REPO / "governance" / "run_ledger.jsonl")


def _harvest() -> dict[str, Any]:
    raw_dir = _REPO / "data" / "ligand_data" / "raw"
    data_dir = _REPO / "data" / "ligand_data"
    result_dir = _REPO / "results" / "ligand_data"
    raw_dir.mkdir(parents=True, exist_ok=True)
    activities, chembl_retrieved = _load_chembl(raw_dir)
    aids, summaries, summary_retrieved = _load_pubchem_index(raw_dir)
    census = chembl_census(activities)
    aid_counts = {
        row["AID"]: {
            "cid_count_all": row["CIDCountAll"],
            "cid_count_active": row["CIDCountActive"],
            "cid_count_inactive": row["CIDCountInactive"],
        }
        for row in summaries
    }
    baseline = compare_baseline(
        census,
        census["standard_types"],
        len(aids),
        aid_counts,
        census["molecules_per_document"],
    )
    usable = compound_assays(summaries)
    curated, off_target = _curate_all(activities, usable, raw_dir, chembl_retrieved, summary_retrieved)
    reference = select_reference_rows(curated)
    # Handoff files land before scaffolds, the similarity matrix, and the figure.
    _write_handoff(data_dir, result_dir, curated, reference)
    identity = _load_ms48107(raw_dir)
    _write_outputs(
        data_dir,
        result_dir,
        curated,
        reference,
        off_target,
        summaries,
        usable,
        baseline,
        census,
        identity,
    )
    manifest = sha256_file(result_dir / "GPR68_reference_ligands.csv")
    patent = [row for row in curated if row["assay_id"] == _PATENT_ASSAY]
    inactive_ids = {row["compound_id"] for row in patent if row["activity_outcome"] == "Inactive"}
    active_ids = {row["compound_id"] for row in patent if row["activity_outcome"] == "Active"}
    return {
        "data_manifest_hash": manifest,
        "chembl_activities": census["activities"],
        "chembl_molecules": census["molecules"],
        "chembl_assays": census["assays"],
        "chembl_documents": census["documents"],
        "pchembl_rows": census["pchembl_rows"],
        "pchembl_molecules": census["pchembl_molecules"],
        "pubchem_aids": len(aids),
        "pubchem_compound_assays": len(usable),
        "curated_rows": len(curated),
        "reference_rows": len(reference),
        "unique_inchikeys": len({row["inchikey"] for row in curated}),
        "patent_active_molecules": len(active_ids),
        "patent_inactive_molecules": len(inactive_ids),
        "off_target_rows": len(off_target),
        "discrepancy_count": len(baseline["discrepancies"]),
        "discrepancies": " | ".join(baseline["discrepancies"]),
    }


def _load_chembl(raw_dir: Path) -> tuple[list[dict[str, Any]], str]:
    body, retrieved = fetch_bytes(_CHEMBL_URL, ipv4=False)
    (raw_dir / "chembl_activities.json").write_bytes(body)
    payload = json.loads(body)
    return parse_activity_document(payload), retrieved


def _load_pubchem_index(raw_dir: Path) -> tuple[list[int], list[dict[str, Any]], str]:
    aid_body, _ = fetch_bytes(_AID_URL, ipv4=True)
    (raw_dir / "pubchem_aids.json").write_bytes(aid_body)
    summary_body, retrieved = fetch_bytes(_SUMMARY_URL, ipv4=True)
    (raw_dir / "pubchem_summaries.json").write_bytes(summary_body)
    aids = parse_aid_list(json.loads(aid_body))
    summaries = parse_summaries(json.loads(summary_body))
    if {row["AID"] for row in summaries} != set(aids):
        raise ContractViolation("PubChem AID list and summary list do not name the same assays")
    return aids, summaries, retrieved


def _curate_all(
    activities: list[dict[str, Any]],
    usable: list[dict[str, Any]],
    raw_dir: Path,
    chembl_retrieved: str,
    summary_retrieved: str,
) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
    rows = chembl_rows(activities, source_url=_CHEMBL_URL, retrieved_utc=chembl_retrieved)
    off_target: list[dict[str, Any]] = []
    for summary in usable:
        aid = int(summary["AID"])
        url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/assay/aid/{aid}/CSV"
        body, retrieved = fetch_bytes(url, ipv4=True)
        (raw_dir / f"aid_{aid}.csv").write_bytes(body)
        kept, excluded = parse_assay_csv(body.decode("utf-8"), aid=aid)
        off_target.extend(excluded)
        rows.extend(pubchem_rows(kept, summary=summary, source_url=url, retrieved_utc=retrieved))
    rows.sort(key=lambda row: (row["source"], row["assay_id"], row["compound_id"], row["activity_type"]))
    _ = summary_retrieved
    return rows, off_target


def _write_handoff(
    data_dir: Path,
    result_dir: Path,
    curated: list[dict[str, str]],
    reference: list[dict[str, str]],
) -> None:
    """Reference table plus the patent active/inactive split. Written before anything slower."""
    model_rows = modeling_table(curated)
    write_table(
        result_dir / "GPR68_reference_ligands.csv", reference_frame_rows(reference), REFERENCE_COLUMNS
    )
    write_table(data_dir / "modeling_table.csv", model_rows, _MODEL_COLUMNS)
    actives = [row for row in model_rows if row["activity_outcome"] == "Active"]
    inactives = [row for row in model_rows if row["activity_outcome"] == "Inactive"]
    write_table(result_dir / "AID2060853_actives.csv", actives, _MODEL_COLUMNS)
    write_table(result_dir / "AID2060853_inactives.csv", inactives, _MODEL_COLUMNS)


def _write_outputs(
    data_dir: Path,
    result_dir: Path,
    curated: list[dict[str, str]],
    reference: list[dict[str, str]],
    off_target: list[dict[str, Any]],
    summaries: list[dict[str, Any]],
    usable: list[dict[str, Any]],
    baseline: dict[str, list[str]],
    census: dict[str, Any],
    identity: dict[str, str],
) -> None:
    write_table(data_dir / "curated_activities.csv", curated, CURATED_COLUMNS)
    write_table(
        result_dir / "reference_compounds.csv",
        reference_report(curated, identities=[identity]),
        _FLAG_COLUMNS,
    )
    _write_scaffolds(data_dir / "scaffolds.csv", curated)
    _write_tanimoto(data_dir / "tanimoto.csv", curated)
    if off_target:
        write_table(data_dir / "off_target_rows.csv", [_stringify(row) for row in off_target], _OFF_COLUMNS)
    dropped = [row for row in summaries if row["CIDCountAll"] == 0]
    write_table(
        data_dir / "dropped_no_compound_assays.csv", [_summary_row(row) for row in dropped], _DROP_COLUMNS
    )
    write_provenance_figure(curated, result_dir / "provenance_by_document.png")
    check = {
        "discrepancies": baseline["discrepancies"],
        "qualifications": _qualifications(curated, usable, off_target),
        "standard_types": census["standard_types"],
        "molecules_per_document": census["molecules_per_document"],
        "activities_per_document": census["activities_per_document"],
        "isomers": isomer_status(curated),
        "document_concentration": _document_note(census),
        "ms48107": identity,
    }
    (result_dir / "baseline_check.json").write_text(
        json.dumps(check, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


_MODEL_COLUMNS = (
    "compound_id",
    "compound_name",
    "smiles",
    "inchikey",
    "murcko_scaffold",
    "label",
    "activity_outcome",
    "n_endpoints",
    "activity_types",
    "activity_values",
)
_FLAG_COLUMNS = (
    "compound_name",
    "chembl_id",
    "pubchem_id",
    "smiles",
    "n_chembl_rows",
    "n_pubchem_rows",
    "present",
)
_OFF_COLUMNS = (
    "aid",
    "cid",
    "smiles",
    "outcome",
    "standard_type",
    "relation",
    "value",
    "unit",
    "target_accession",
)
_DROP_COLUMNS = ("AID", "Name", "SourceName", "CIDCountAll", "SIDCountAll")


def _write_scaffolds(path: Path, rows: list[dict[str, str]]) -> None:
    grouped: dict[str, dict[str, str]] = {}
    for row in rows:
        bucket = grouped.setdefault(
            row["inchikey"],
            {
                "inchikey": row["inchikey"],
                "smiles": row["smiles"],
                "murcko_scaffold": row["murcko_scaffold"],
                "compound_ids": row["compound_id"],
            },
        )
        ids = set(bucket["compound_ids"].split(";"))
        ids.add(row["compound_id"])
        bucket["compound_ids"] = ";".join(sorted(ids))
    ordered = [grouped[key] for key in sorted(grouped)]
    write_table(path, ordered, ("inchikey", "smiles", "murcko_scaffold", "compound_ids"))


def _write_tanimoto(path: Path, rows: list[dict[str, str]]) -> None:
    structures = {}
    for row in rows:
        structures.setdefault(row["inchikey"], row["smiles"])
    labels = sorted(structures)
    fingerprints = [morgan_fingerprint(structures[label], label=label) for label in labels]
    matrix = [[tanimoto(left, right) for right in fingerprints] for left in fingerprints]
    write_matrix(path, labels, matrix)


def _qualifications(
    curated: list[dict[str, str]],
    usable: list[dict[str, Any]],
    off_target: list[dict[str, Any]],
) -> list[str]:
    notes: list[str] = []
    extra = sorted(int(row["AID"]) for row in usable if int(row["AID"]) not in _NAMED_USABLE_AIDS)
    if extra:
        notes.append(
            "CIDCountAll > 0 keeps PubChem AIDs the plan did not list as usable: "
            + ", ".join(map(str, extra))
        )
    if off_target:
        accessions = Counter(str(row["target_accession"]) for row in off_target)
        notes.append(f"AID 2060853 off-target rows excluded from GPR68 tables: {dict(accessions)}")
    inactive = [
        row for row in curated if row["assay_id"] == _PATENT_ASSAY and row["activity_outcome"] == "Inactive"
    ]
    censored = [row["activity_value"] for row in inactive]
    notes.append(f"AID 2060853 inactive activity values (relation preserved): {censored}")
    not_active = {row["compound_id"] for row in curated if row["activity_value"] == "Not Active"}
    notes.append(
        f"ChEMBL or PubChem rows with a Not Active text value cover {len(not_active)} compound ids; "
        "these are endpoint-level annotations, counted separately from the patent inactive calls"
    )
    return notes


def _document_note(census: dict[str, Any]) -> str:
    """State the two-paper concentration in molecules and in activity rows."""
    molecules = census["molecules_per_document"]
    activities = census["activities_per_document"]
    top = sorted(molecules, key=lambda doc: (-molecules[doc], doc))[:2]
    parts = [f"{doc}: {molecules[doc]} molecules, {activities[doc]} activity rows" for doc in top]
    mol_pair = [molecules[doc] for doc in top]
    act_pair = [activities[doc] for doc in top]
    molecule_clause = (
        "These molecule counts match the plan's 67 and 29."
        if mol_pair == [67, 29]
        else f"These molecule counts {mol_pair} do not match the plan's [67, 29]."
    )
    if act_pair == [67, 29]:
        activity_clause = "Activity rows in those documents are also 67 and 29."
    else:
        activity_clause = (
            f"Activity rows in those documents are {act_pair}. "
            "The figures 67 and 29 are molecule counts, not activity-row counts."
        )
    return (
        "Largest documents by molecule count: "
        + "; ".join(parts)
        + ". "
        + molecule_clause
        + " "
        + activity_clause
    )


def _load_ms48107(raw_dir: Path) -> dict[str, str]:
    """CID 139030523 has no GeneID 8111 row. The structure is CHEMBL4449712."""
    body, retrieved = fetch_bytes(_MS48107_URL, ipv4=True)
    (raw_dir / "ms48107_cid139030523.json").write_bytes(body)
    payload = json.loads(body)
    try:
        prop = payload["PropertyTable"]["Properties"][0]
    except (KeyError, IndexError, TypeError) as exc:
        raise ContractViolation("MS48107 PubChem property payload is not the expected shape") from exc
    formula = prop.get("MolecularFormula")
    if formula != _MS48107_FORMULA:
        raise ContractViolation(f"MS48107 formula {formula!r} does not match {_MS48107_FORMULA}")
    smiles = prop.get("IsomericSMILES")
    if not isinstance(smiles, str) or smiles.strip() == "":
        smiles = prop.get("SMILES")
    if not isinstance(smiles, str) or smiles.strip() == "":
        raise ContractViolation(f"MS48107 property record has no SMILES; keys={sorted(prop)}")
    parsed = parse_structure(smiles, label="MS48107")
    mol = Chem.MolFromSmiles(parsed.smiles)
    if mol is None:
        raise ContractViolation("MS48107 canonical SMILES did not reparse")
    rdkit_formula = rdMolDescriptors.CalcMolFormula(mol)
    if rdkit_formula != _MS48107_FORMULA:
        raise ContractViolation(f"MS48107 RDKit formula {rdkit_formula} != {_MS48107_FORMULA}")
    return {
        "compound_name": "MS48107",
        "chembl_id": "CHEMBL4449712",
        "pubchem_id": "CID139030523",
        "smiles": parsed.smiles,
        "formula": rdkit_formula,
        "source_url": _MS48107_URL,
        "retrieved_utc": retrieved,
    }


def _stringify(row: dict[str, Any]) -> dict[str, str]:
    return {column: "" if row.get(column) is None else str(row.get(column, "")) for column in _OFF_COLUMNS}


def _summary_row(row: dict[str, Any]) -> dict[str, str]:
    return {column: str(row[column]) for column in _DROP_COLUMNS}


if __name__ == "__main__":
    print(json.dumps(main(), indent=2, sort_keys=True))
