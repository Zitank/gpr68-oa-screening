"""GNINA replay commands keep the smina centres and add CNN rescoring."""

from __future__ import annotations

from clusters.docking.src.gnina import gnina_argv
from clusters.docking.src.plan import plan_runs
from clusters.docking.src.settings import SEED
from clusters.pocket.src.facts import PLAN_CENTRES


def test_gnina_adds_cnn_and_keeps_centres() -> None:
    specs = [spec for spec in plan_runs(seed=SEED) if spec.ligand == "ogerin"]
    pocket1 = gnina_argv(specs[0], "rec.pdbqt", "ogerin.pdbqt", "out.sdf")
    pocket2 = gnina_argv(specs[1], "rec.pdbqt", "ogerin.pdbqt", "out.sdf")
    assert pocket1[pocket1.index("--cnn_scoring") + 1] == "rescore"
    assert pocket1[pocket1.index("--center_x") + 1] == f"{PLAN_CENTRES[1][0]:.2f}"
    assert pocket2[pocket2.index("--center_x") + 1] == f"{PLAN_CENTRES[2][0]:.2f}"
    assert "--cnn_scoring" not in pocket1[: pocket1.index("--cnn_scoring")]
