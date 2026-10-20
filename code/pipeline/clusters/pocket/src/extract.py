"""Extract one chain from a PDB text block.

## [EXPLORATORY]
Chain R of 8Z68 is GPR68. Chains A, B and G are the Gs heterotrimer; S is scFv16.
"""

from __future__ import annotations

from clusters.pocket.src.pdbio import iter_atoms
from core.errors import ContractViolation


def extract_chain(text: str, chain: str) -> str:
    """ATOM records for ``chain``, original lines preserved, terminated by END.

    HETATM on that chain is a contract failure: the plan's chain R is apo.
    Alternate-location records are a contract failure: this extractor does not choose one.
    """
    if len(chain) != 1:
        raise ContractViolation(f"chain id must be one character, got {chain!r}")
    kept: list[str] = []
    for line in text.splitlines():
        if not line.startswith(("ATOM", "HETATM")):
            continue
        if len(line) < 22 or line[21] != chain:
            continue
        if line[16] not in (" ", ""):
            raise ContractViolation(f"alternate location on chain {chain}: {line!r}")
        if line.startswith("HETATM"):
            raise ContractViolation(f"HETATM on chain {chain}; refusing to drop it silently: {line!r}")
        kept.append(line)
    if not kept:
        raise ContractViolation(f"no ATOM records for chain {chain}")
    return "\n".join(kept) + "\nEND\n"


def heavy_atom_count(text: str) -> int:
    """Count ATOM/HETATM records whose element is not hydrogen."""
    return sum(1 for atom in iter_atoms(text) if atom.element.upper() != "H")
