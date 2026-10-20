"""Plan the eight docking runs deterministically; configs differ by pocket."""

from __future__ import annotations

import pytest

from clusters.docking.src.plan import (
    EXHAUSTIVENESS,
    PLANNED_RUNS,
    REFERENCE_LIGANDS,
    plan_runs,
    run_config,
)
from clusters.pocket.src.box import POCKET_CENTRES
from core.config import config_hash
from core.errors import ContractViolation


def test_plan_runs_returns_eight() -> None:
    assert len(plan_runs()) == PLANNED_RUNS


def test_each_ligand_twice_once_per_pocket() -> None:
    by_ligand: dict[str, list[int]] = {}
    for spec in plan_runs():
        by_ligand.setdefault(spec.ligand, []).append(spec.pocket_id)
    assert set(by_ligand) == set(REFERENCE_LIGANDS)
    for pockets in by_ligand.values():
        assert sorted(pockets) == sorted(POCKET_CENTRES)


def test_plan_runs_deterministic() -> None:
    assert plan_runs() == plan_runs()


def test_default_exhaustiveness() -> None:
    assert all(spec.exhaustiveness == EXHAUSTIVENESS for spec in plan_runs())


def test_exhaustiveness_zero_raises() -> None:
    with pytest.raises(ContractViolation):
        plan_runs(exhaustiveness=0)


def test_run_config_condition_code() -> None:
    specs = plan_runs()
    assert run_config(specs[0]).condition_code == "P1"
    pocket2 = next(spec for spec in specs if spec.pocket_id == 2)
    assert run_config(pocket2).condition_code == "P2"


def test_configs_differing_only_by_pocket_hash_differently() -> None:
    specs = plan_runs()
    ligand = specs[0].ligand
    first = next(spec for spec in specs if spec.ligand == ligand and spec.pocket_id == 1)
    second = next(spec for spec in specs if spec.ligand == ligand and spec.pocket_id == 2)
    assert first.seed == second.seed
    assert first.exhaustiveness == second.exhaustiveness
    assert config_hash(run_config(first)) != config_hash(run_config(second))
