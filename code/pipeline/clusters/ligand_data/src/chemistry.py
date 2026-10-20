"""RDKit structure handling. Fingerprint size is an assumption, not a measured constant.

## [EXPLORATORY]
## [ASSUMPTION: A32]
Morgan fingerprint radius 2 and 2048 bits. RDKit Morgan defaults, fixed here and not tuned.
"""

from __future__ import annotations

from dataclasses import dataclass

from rdkit import Chem, DataStructs
from rdkit.Chem import Crippen, Descriptors, Lipinski, rdFingerprintGenerator
from rdkit.Chem.Scaffolds import MurckoScaffold

from core.errors import ContractViolation

# ## [ASSUMPTION: A32]
MORGAN_RADIUS = 2
MORGAN_BITS = 2048

_GENERATOR = rdFingerprintGenerator.GetMorganGenerator(radius=MORGAN_RADIUS, fpSize=MORGAN_BITS)

DESCRIPTOR_COLUMNS = ("MW", "LogP", "TPSA", "HBD", "HBA", "RotatableBonds")


@dataclass(frozen=True)
class ParsedStructure:
    """One RDKit-canonicalised structure."""

    smiles: str
    murcko: str
    inchikey: str


def parse_structure(smiles: str, *, label: str) -> ParsedStructure:
    """Canonicalise ``smiles``. Raises ``ContractViolation`` if RDKit cannot parse it."""
    if smiles.strip() == "":
        raise ContractViolation(f"empty SMILES for {label}")
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        raise ContractViolation(f"RDKit could not parse SMILES for {label}: {smiles}")
    canonical = Chem.MolToSmiles(mol, canonical=True)
    murcko = MurckoScaffold.MurckoScaffoldSmiles(mol=mol, includeChirality=False)
    inchikey = Chem.MolToInchiKey(mol)
    if inchikey == "":
        raise ContractViolation(f"RDKit returned an empty InChIKey for {label}")
    return ParsedStructure(smiles=canonical, murcko=murcko, inchikey=inchikey)


def morgan_fingerprint(smiles: str, *, label: str):
    """Bit vector for ``smiles`` using the A10 Morgan settings."""
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        raise ContractViolation(f"RDKit could not parse SMILES for {label}: {smiles}")
    return _GENERATOR.GetFingerprint(mol)


def tanimoto(left, right) -> float:
    """Tanimoto similarity of two RDKit fingerprints."""
    return float(DataStructs.TanimotoSimilarity(left, right))


def descriptor_row(smiles: str, *, label: str) -> dict[str, float]:
    """Methods-document descriptors: MW, LogP, TPSA, HBD, HBA, rotatable bonds."""
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        raise ContractViolation(f"RDKit could not parse SMILES for {label}: {smiles}")
    return {
        "MW": float(Descriptors.MolWt(mol)),
        "LogP": float(Crippen.MolLogP(mol)),
        "TPSA": float(Descriptors.TPSA(mol)),
        "HBD": float(Lipinski.NumHDonors(mol)),
        "HBA": float(Lipinski.NumHAcceptors(mol)),
        "RotatableBonds": float(Lipinski.NumRotatableBonds(mol)),
    }


def same_scaffold_different_structure(left: ParsedStructure, right: ParsedStructure) -> bool:
    """True when two molecules share a Murcko scaffold and are not the same structure."""
    return left.murcko != "" and left.murcko == right.murcko and left.inchikey != right.inchikey
