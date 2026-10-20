"""Smina score parsing and the eight-run command."""

from __future__ import annotations

from pathlib import Path

import pytest

from clusters.docking.src.plan import plan_runs
from clusters.docking.src.settings import SEED
from clusters.docking.src.smina import parse_scores, smina_command
from clusters.pocket.src.box import POCKET_CENTRES
from clusters.pocket.src.facts import PLAN_CENTRES
from core.errors import ContractViolation

_BLOCK = """MODEL 1
REMARK VINA RESULT:      -7.345      0.000      0.000
ENDMDL
MODEL 2
REMARK VINA RESULT:      -6.100      1.500      2.250
ENDMDL
"""


def test_parse_two_modes() -> None:
    modes = parse_scores(_BLOCK)
    assert len(modes) == 2
    assert modes[0].affinity == pytest.approx(-7.345)
    assert modes[1].rmsd_lb == pytest.approx(1.5)
    assert modes[1].mode == 2


def test_missing_score_raises() -> None:
    with pytest.raises(ContractViolation, match="minimizedAffinity"):
        parse_scores("ATOM\n", log_text="no table")


def test_minimized_affinity_with_log_rmsd() -> None:
    pdbqt = "REMARK minimizedAffinity -2.54612637\nENDMDL\nREMARK minimizedAffinity -1.75060666\n"
    log = "1       -2.5       0.000      0.000\n2       -1.8       10.690     12.556\n"
    modes = parse_scores(pdbqt, log)
    assert modes[0].affinity == pytest.approx(-2.54612637)
    assert modes[1].rmsd_lb == pytest.approx(10.690)


def test_commands_differ_only_by_centre() -> None:
    specs = plan_runs(seed=SEED)
    ligand = specs[0].ligand
    first = next(spec for spec in specs if spec.ligand == ligand and spec.pocket_id == 1)
    second = next(spec for spec in specs if spec.ligand == ligand and spec.pocket_id == 2)
    left = smina_command(Path("rec.pdbqt"), Path("lig.pdbqt"), first, Path("out.pdbqt"))
    right = smina_command(Path("rec.pdbqt"), Path("lig.pdbqt"), second, Path("out.pdbqt"))
    centre_flags = {"--center_x", "--center_y", "--center_z"}
    assert [item for item in left if item not in centre_flags] != right  # full argv differs
    stripped = _without_centres(left)
    assert stripped == _without_centres(right)
    assert left[left.index("--center_x") + 1] == f"{PLAN_CENTRES[1][0]:.2f}"
    assert right[right.index("--center_z") + 1] == f"{PLAN_CENTRES[2][2]:.2f}"
    assert POCKET_CENTRES == PLAN_CENTRES


def _without_centres(argv: list[str]) -> list[str]:
    kept: list[str] = []
    skip = False
    for item in argv:
        if skip:
            skip = False
            continue
        if item in {"--center_x", "--center_y", "--center_z"}:
            skip = True
            continue
        kept.append(item)
    return kept
