"""Applicability domain on a ChEMBL substitute for the missing MCE library.

## [EXPLORATORY]
## [ASSUMPTION: A15] The substitute is at most 400 ChEMBL molecules with freebase MW 200-500
## and ALogP -1 to 5, then kept only when all six descriptors sit inside the patent-set min/max.
## InChIKeys already in the GPR68 curated table are removed.
## [ASSUMPTION: A16] A substitute molecule is inside the applicability domain when its maximum
## Morgan Tanimoto to the patent set is at least 0.40.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from clusters.ligand_data.src.chemistry import (
    DESCRIPTOR_COLUMNS,
    descriptor_row,
    morgan_fingerprint,
    parse_structure,
    tanimoto,
)
from clusters.ligand_data.src.http_client import fetch_bytes
from clusters.ligand_data.src.tables import read_table
from core.errors import ContractViolation

# ## [ASSUMPTION: A15]
_QUERY = (
    "https://www.ebi.ac.uk/chembl/api/data/molecule.json"
    "?molecule_properties__mw_freebase__gte=200"
    "&molecule_properties__mw_freebase__lte=500"
    "&molecule_properties__alogp__gte=-1"
    "&molecule_properties__alogp__lte=5"
    "&limit=200"
)
_MAX_MOLECULES = 400
# ## [ASSUMPTION: A16]
TANIMOTO_MIN = 0.40
SUBSTITUTION = (
    "SUBSTITUTION: the MCE 5,000 screening library was not available. "
    "This applicability domain uses a property-matched lead-like sample drawn from ChEMBL, "
    "not the MCE library."
)


def applicability(
    patent_rows: list[dict[str, str]],
    curated_path: Path,
    raw_dir: Path,
) -> tuple[list[dict[str, str]], dict[str, float | int | str]]:
    """Nearest-neighbour Tanimoto of the substitute sample against the patent set."""
    known = {row["inchikey"] for row in read_table(curated_path)}
    raw_dir.mkdir(parents=True, exist_ok=True)
    retrieved = _fetch_pages(raw_dir)
    bounds = _bounds(patent_rows)
    patent_fps = [morgan_fingerprint(row["smiles"], label=row["compound_id"]) for row in patent_rows]
    kept: list[dict[str, str]] = []
    skipped_known = 0
    skipped_parse = 0
    skipped_match = 0
    for chembl_id, smiles in retrieved:
        try:
            parsed = parse_structure(smiles, label=chembl_id)
            descriptors = descriptor_row(parsed.smiles, label=chembl_id)
        except ContractViolation:
            skipped_parse += 1
            continue
        if parsed.inchikey in known:
            skipped_known += 1
            continue
        if not _inside(descriptors, bounds):
            skipped_match += 1
            continue
        fp = morgan_fingerprint(parsed.smiles, label=chembl_id)
        nearest = max(tanimoto(fp, other) for other in patent_fps)
        kept.append(
            {
                "chembl_id": chembl_id,
                "smiles": parsed.smiles,
                "max_tanimoto": f"{nearest:.6f}",
                "in_domain": "yes" if nearest >= TANIMOTO_MIN else "no",
                **{name: f"{descriptors[name]:.6g}" for name in DESCRIPTOR_COLUMNS},
            }
        )
    if not kept:
        raise ContractViolation("property-matched ChEMBL substitute sample is empty")
    in_domain = sum(1 for row in kept if row["in_domain"] == "yes")
    summary = {
        "substitution": SUBSTITUTION,
        "n_retrieved": len(retrieved),
        "n_property_matched": len(kept),
        "n_in_domain": in_domain,
        "fraction_in_domain": in_domain / len(kept),
        "tanimoto_min": TANIMOTO_MIN,
        "skipped_known_gpr68": skipped_known,
        "skipped_unparsed": skipped_parse,
        "skipped_outside_property_box": skipped_match,
        "median_max_tanimoto": float(np.median([float(row["max_tanimoto"]) for row in kept])),
    }
    return kept, summary


def _fetch_pages(raw_dir: Path) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    offset = 0
    while len(found) < _MAX_MOLECULES:
        url = f"{_QUERY}&offset={offset}"
        body, _retrieved = fetch_bytes(url, ipv4=True)
        (raw_dir / f"chembl_leadlike_offset_{offset}.json").write_bytes(body)
        payload = json.loads(body)
        page = _page(payload)
        if not page:
            break
        found.extend(page)
        meta = payload.get("page_meta") or {}
        if not meta.get("next"):
            break
        offset += 200
    if not found:
        raise ContractViolation("ChEMBL lead-like query returned no structures")
    return found[:_MAX_MOLECULES]


def _page(payload: dict) -> list[tuple[str, str]]:
    molecules = payload.get("molecules")
    if not isinstance(molecules, list):
        raise ContractViolation("ChEMBL molecule payload has no molecules list")
    rows: list[tuple[str, str]] = []
    for molecule in molecules:
        chembl_id = molecule.get("molecule_chembl_id")
        structures = molecule.get("molecule_structures") or {}
        smiles = structures.get("canonical_smiles") if isinstance(structures, dict) else None
        if isinstance(chembl_id, str) and isinstance(smiles, str) and smiles.strip():
            rows.append((chembl_id, smiles))
    return rows


def _bounds(rows: list[dict[str, str]]) -> dict[str, tuple[float, float]]:
    columns = {name: [] for name in DESCRIPTOR_COLUMNS}
    for row in rows:
        values = descriptor_row(row["smiles"], label=row["compound_id"])
        for name in DESCRIPTOR_COLUMNS:
            columns[name].append(values[name])
    return {name: (min(values), max(values)) for name, values in columns.items()}


def _inside(values: dict[str, float], bounds: dict[str, tuple[float, float]]) -> bool:
    for name, (low, high) in bounds.items():
        if values[name] < low or values[name] > high:
            return False
    return True
