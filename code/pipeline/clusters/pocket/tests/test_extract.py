"""Chain extraction keeps one chain and refuses heteroatoms and altlocs."""

from __future__ import annotations

import pytest

from clusters.pocket.src.extract import extract_chain
from clusters.pocket.src.pdbio import iter_atoms
from core.errors import ContractViolation

_ATOM = "ATOM      1  N   CYS {chain}  13      11.000  12.000  13.000  1.00 20.00           N"
_HET = "HETATM    2  O   HOH {chain} 201      11.000  12.000  13.000  1.00 20.00           O"


def test_extracts_only_requested_chain() -> None:
    text = "\n".join([_ATOM.format(chain="A"), _ATOM.format(chain="R"), "END"])
    extracted = extract_chain(text, "R")
    atoms = iter_atoms(extracted)
    assert len(atoms) == 1
    assert atoms[0].chain == "R"
    assert extracted.endswith("END\n")


def test_hetatm_on_chain_raises() -> None:
    text = _HET.format(chain="R") + "\n"
    with pytest.raises(ContractViolation, match="HETATM"):
        extract_chain(text, "R")


def test_altloc_raises() -> None:
    line = _ATOM.format(chain="R")
    chars = list(line)
    chars[16] = "A"
    with pytest.raises(ContractViolation, match="alternate"):
        extract_chain("".join(chars) + "\n", "R")
