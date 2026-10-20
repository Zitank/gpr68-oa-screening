"""One row per molecule-assay-endpoint; activity endpoints are never pooled.

## [EXPLORATORY]
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

from pydantic import BaseModel, ConfigDict

from core.errors import ContractViolation


class ActivityRecord(BaseModel):
    """One measured activity row for a compound, assay and endpoint."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    compound_id: str
    smiles: str
    source: Literal["chembl", "pubchem"]
    source_assay_id: str
    document_id: str | None = None
    endpoint: str
    value: float | None = None
    unit: str | None = None
    comment: str | None = None


def row_key(record: ActivityRecord) -> tuple[str, str, str]:
    """Identity of one activity row: compound, assay and endpoint."""
    return (record.compound_id, record.source_assay_id, record.endpoint)


def assert_one_row_per_endpoint(records: Sequence[ActivityRecord]) -> None:
    """Reject duplicate rows and empty input."""
    if not records:
        raise ContractViolation("no activity records provided")
    seen: set[tuple[str, str, str]] = set()
    for record in records:
        key = row_key(record)
        if key in seen:
            raise ContractViolation(f"duplicate activity row for key {key}")
        seen.add(key)


def assert_units_consistent(records: Sequence[ActivityRecord]) -> None:
    """Require every non-None unit to match within each endpoint."""
    units_by_endpoint: dict[str, set[str]] = {}
    for record in records:
        if record.unit is not None:
            units_by_endpoint.setdefault(record.endpoint, set()).add(record.unit)
    for endpoint, units in units_by_endpoint.items():
        if len(units) > 1:
            raise ContractViolation(f"endpoint {endpoint!r} has conflicting units {sorted(units)}")


def endpoint_counts(records: Sequence[ActivityRecord]) -> dict[str, int]:
    """Row count per endpoint, keys sorted."""
    counts: dict[str, int] = {}
    for record in records:
        counts[record.endpoint] = counts.get(record.endpoint, 0) + 1
    return dict(sorted(counts.items()))
