"""Features for the AID 2060853 classifier. Endpoints are not pooled into the label.

## [EXPLORATORY]
## [ASSUMPTION: A19] An empty Murcko scaffold is its own group, keyed by InChIKey.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from rdkit import DataStructs

from clusters.ligand_data.src.chemistry import (
    DESCRIPTOR_COLUMNS,
    MORGAN_BITS,
    descriptor_row,
    morgan_fingerprint,
)
from clusters.ligand_data.src.tables import read_table
from core.errors import ContractViolation

# ## [ASSUMPTION: A19]
_ACYCLIC_PREFIX = "ACYCLIC:"


def load_patent_table(path: Path) -> list[dict[str, str]]:
    """One row per compound from the patent modeling table."""
    rows = read_table(path)
    if len(rows) < 2:
        raise ContractViolation(f"{path} has too few rows")
    ids = [row["compound_id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise ContractViolation("modeling table has duplicate compound ids")
    return rows


def scaffold_group(murcko: str, inchikey: str) -> str:
    """Group key that keeps acyclic molecules from sharing one empty scaffold. See A19."""
    if murcko.strip() == "":
        return f"{_ACYCLIC_PREFIX}{inchikey}"
    return murcko


def labels_from(rows: list[dict[str, str]]) -> np.ndarray:
    """Map the deposited outcome to 0/1. Do not re-threshold potency."""
    mapped: list[int] = []
    for row in rows:
        if row["label"] == "1" and row["activity_outcome"] == "Active":
            mapped.append(1)
        elif row["label"] == "0" and row["activity_outcome"] == "Inactive":
            mapped.append(0)
        else:
            raise ContractViolation(
                f"{row['compound_id']} label {row['label']!r} disagrees with {row['activity_outcome']!r}"
            )
    values = np.asarray(mapped, dtype=int)
    if set(values.tolist()) != {0, 1}:
        raise ContractViolation("the patent table does not contain both classes")
    return values


def morgan_matrix(rows: list[dict[str, str]]) -> np.ndarray:
    """Morgan bits, shape (n, A10 bits)."""
    matrix = np.zeros((len(rows), MORGAN_BITS), dtype=np.uint8)
    for index, row in enumerate(rows):
        fp = morgan_fingerprint(row["smiles"], label=row["compound_id"])
        DataStructs.ConvertToNumpyArray(fp, matrix[index])
    return matrix


def descriptor_matrix(rows: list[dict[str, str]]) -> np.ndarray:
    """Methods-document descriptors, columns in DESCRIPTOR_COLUMNS order."""
    matrix = np.zeros((len(rows), len(DESCRIPTOR_COLUMNS)), dtype=float)
    for index, row in enumerate(rows):
        values = descriptor_row(row["smiles"], label=row["compound_id"])
        matrix[index] = [values[name] for name in DESCRIPTOR_COLUMNS]
    return matrix


def group_labels(rows: list[dict[str, str]]) -> np.ndarray:
    """Scaffold group per row."""
    return np.asarray(
        [scaffold_group(row["murcko_scaffold"], row["inchikey"]) for row in rows],
        dtype=object,
    )
