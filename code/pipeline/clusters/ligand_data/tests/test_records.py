"""Activity records: no endpoint pooling, consistent units, sorted counts."""

from __future__ import annotations

import pytest

from clusters.ligand_data.src.records import (
    ActivityRecord,
    assert_one_row_per_endpoint,
    assert_units_consistent,
    endpoint_counts,
)
from core.errors import ContractViolation


def record(
    compound_id: str,
    assay: str,
    endpoint: str,
    unit: str | None = None,
) -> ActivityRecord:
    return ActivityRecord(
        compound_id=compound_id,
        smiles="C",
        source="chembl",
        source_assay_id=assay,
        endpoint=endpoint,
        unit=unit,
    )


def test_valid_set_passes_and_counts() -> None:
    records = [
        record("C1", "A1", "IC50", "nM"),
        record("C2", "A1", "IC50", "nM"),
        record("C1", "A2", "Ki", "uM"),
    ]
    assert_one_row_per_endpoint(records)
    assert_units_consistent(records)
    assert endpoint_counts(records) == {"IC50": 2, "Ki": 1}


def test_duplicate_triple_raises() -> None:
    records = [
        record("C1", "A1", "IC50", "nM"),
        record("C1", "A1", "IC50", "nM"),
    ]
    with pytest.raises(ContractViolation, match="C1"):
        assert_one_row_per_endpoint(records)


def test_conflicting_units_within_endpoint_raise() -> None:
    records = [
        record("C1", "A1", "IC50", "nM"),
        record("C2", "A1", "IC50", "uM"),
    ]
    with pytest.raises(ContractViolation, match="IC50"):
        assert_units_consistent(records)


def test_same_units_across_endpoints_ok() -> None:
    records = [
        record("C1", "A1", "IC50", "nM"),
        record("C1", "A1", "Ki", "uM"),
    ]
    assert_units_consistent(records)


def test_empty_input_raises() -> None:
    with pytest.raises(ContractViolation):
        assert_one_row_per_endpoint([])
