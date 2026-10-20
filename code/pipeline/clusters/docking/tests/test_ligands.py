"""Hardcoded reference SMILES stay the plan's strings. No network."""

from __future__ import annotations

from clusters.docking.src.ligands import LIGAND_SMILES, formula


def test_ogerin_and_zinc_are_isomers() -> None:
    assert formula(LIGAND_SMILES["ogerin"]) == formula(LIGAND_SMILES["zinc32547799"])
    assert LIGAND_SMILES["ogerin"] != LIGAND_SMILES["zinc32547799"]


def test_lorazepam_formula() -> None:
    assert formula(LIGAND_SMILES["lorazepam"]) == "C15H10Cl2N2O2"


def test_plan_smiles_unchanged() -> None:
    assert LIGAND_SMILES["ogerin"] == "Nc1nc(NCc2ccccc2)nc(-c2ccccc2CO)n1"
    assert LIGAND_SMILES["zinc32547799"] == "Nc1nc(NCc2ccccc2)nc(-c2cccc(CO)c2)n1"
