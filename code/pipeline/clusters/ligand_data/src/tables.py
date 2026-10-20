"""CSV tables. Strings stay strings; nothing is coerced to NaN.

## [EXPLORATORY]
"""

from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd

from core.errors import ContractViolation


def write_table(path: Path, rows: list[dict[str, str]], columns: tuple[str, ...] | list[str]) -> None:
    """Write ``rows`` with exactly ``columns``. Pandas 3 is used only as the CSV writer."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise ContractViolation(f"refusing to write an empty table to {path}")
    frame = pd.DataFrame([{column: row[column] for column in columns} for row in rows])
    frame = frame.loc[:, list(columns)]
    if frame.shape[1] != len(columns):
        raise ContractViolation(f"{path} column count drifted")
    frame.to_csv(path, index=False)


def read_table(path: Path) -> list[dict[str, str]]:
    """Read a table back as strings. Empty fields stay empty."""
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    return frame.to_dict(orient="records")


def write_matrix(path: Path, labels: list[str], matrix: list[list[float]]) -> None:
    """Square similarity matrix with the label repeated as the first column."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["inchikey", *labels])
        for label, row in zip(labels, matrix, strict=True):
            writer.writerow([label, *[f"{value:.6f}" for value in row]])
