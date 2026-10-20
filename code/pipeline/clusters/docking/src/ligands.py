"""Reference-ligand coordinates and PDBQT.

Three SMILES are the plan's resolved strings. MS48107 is fetched from PubChem
over IPv4 and accepted only when the formula is C23H20FN5O2.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from meeko import MoleculePreparation, PDBQTWriterLegacy
from rdkit import Chem
from rdkit.Chem import AllChem
from rdkit.Chem.rdMolDescriptors import CalcMolFormula

from clusters.docking.src.plan import REFERENCE_LIGANDS
from clusters.docking.src.settings import MMFF_MAX_ITERS, RIGID_MACROCYCLES, SEED
from core.errors import ContractViolation

# Plan values. Do not replace these with a fresh lookup.
LIGAND_SMILES: dict[str, str] = {
    "ogerin": "Nc1nc(NCc2ccccc2)nc(-c2ccccc2CO)n1",
    "zinc32547799": "Nc1nc(NCc2ccccc2)nc(-c2cccc(CO)c2)n1",
    "lorazepam": "O=C1Nc2ccc(Cl)cc2C(c2ccccc2Cl)=NC1O",
}

_SMINA_TYPES = frozenset({"A", "Br", "C", "Cl", "F", "HD", "I", "N", "NA", "OA", "P", "S", "SA"})
MS48107_CID = REFERENCE_LIGANDS["ms48107"]
MS48107_FORMULA = "C23H20FN5O2"
PUBCHEM_URL = (
    "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/"
    f"{MS48107_CID}/property/SMILES,MolecularFormula/JSON"
)


def all_smiles(cache: Path) -> dict[str, str]:
    """SMILES keyed by ligand name. Fetches MS48107 and checks its formula."""
    smiles = dict(LIGAND_SMILES)
    smiles["ms48107"] = fetch_ms48107(cache)
    missing = set(REFERENCE_LIGANDS) - set(smiles)
    if missing:
        raise ContractViolation(f"SMILES missing for {sorted(missing)}")
    return smiles


def fetch_ms48107(cache: Path) -> str:
    """PubChem CID 139030523 over IPv4. The response is saved as provenance."""
    curl = shutil.which("curl")
    if curl is None:
        raise ContractViolation("curl is not on PATH; cannot force IPv4 for PubChem")
    completed = subprocess.run(
        [curl, "-4", "-fsSL", "--max-time", "60", PUBCHEM_URL],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0 or not completed.stdout.strip():
        raise ContractViolation(f"PubChem CID {MS48107_CID} fetch failed: {completed.stderr.strip()}")
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(completed.stdout)
    payload = json.loads(completed.stdout)
    try:
        props = payload["PropertyTable"]["Properties"][0]
        formula = props["MolecularFormula"]
        smiles = props["SMILES"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ContractViolation(f"PubChem payload missing SMILES or formula: {exc}") from exc
    if formula != MS48107_FORMULA:
        raise ContractViolation(f"MS48107 formula is {formula}, expected {MS48107_FORMULA}")
    if Chem.MolFromSmiles(smiles) is None:
        raise ContractViolation(f"RDKit rejected the PubChem SMILES: {smiles}")
    return smiles


def write_ligand_files(name: str, smiles: str, directory: Path, seed: int = SEED) -> tuple[Path, Path]:
    """Write an SDF (coordinates) and a meeko PDBQT. Returns both paths."""
    if seed == 0:
        raise ContractViolation("seed 0 is rejected for ligand embedding")
    mol = embed_smiles(smiles, seed)
    directory.mkdir(parents=True, exist_ok=True)
    sdf_path = directory / f"{name}.sdf"
    pdbqt_path = directory / f"{name}.pdbqt"
    writer = Chem.SDWriter(str(sdf_path))
    writer.write(mol)
    writer.close()
    pdbqt_path.write_text(mol_to_pdbqt(mol))
    return sdf_path, pdbqt_path


def embed_smiles(smiles: str, seed: int) -> Chem.Mol:
    """One ETKDGv3 conformer, then MMFF94. ## [ASSUMPTION: A10]"""
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        raise ContractViolation(f"RDKit could not parse SMILES: {smiles}")
    mol = Chem.AddHs(mol)
    params = AllChem.ETKDGv3()
    params.randomSeed = seed
    status = AllChem.EmbedMolecule(mol, params)
    if status != 0:
        raise ContractViolation(f"ETKDGv3 failed for {smiles} with status {status}")
    mmff_status = AllChem.MMFFOptimizeMolecule(mol, maxIters=MMFF_MAX_ITERS)
    if mmff_status != 0:
        raise ContractViolation(f"MMFF94 did not converge for {smiles} (status {mmff_status})")
    return mol


def mol_to_pdbqt(mol: Chem.Mol) -> str:
    """Meeko PDBQT with Gasteiger charges. Macrocycles stay rigid (assumption A11)."""
    preparator = MoleculePreparation(rigid_macrocycles=RIGID_MACROCYCLES)
    setups = preparator.prepare(mol)
    if len(setups) != 1:
        raise ContractViolation(f"meeko returned {len(setups)} setups; expected 1")
    pdbqt, ok, error = PDBQTWriterLegacy.write_string(setups[0])
    if not ok:
        raise ContractViolation(f"meeko PDBQT writer failed: {error}")
    _require_smina_types(pdbqt)
    return pdbqt


def _require_smina_types(pdbqt: str) -> None:
    """Smina 2017 rejects meeko glue types such as CG0 and G0."""
    for line in pdbqt.splitlines():
        if not line.startswith(("ATOM", "HETATM")) or len(line) < 79:
            continue
        atom_type = line[77:79].strip()
        if atom_type not in _SMINA_TYPES:
            raise ContractViolation(f"PDBQT atom type {atom_type} is not in the smina 2017 set")


def formula(smiles: str) -> str:
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        raise ContractViolation(f"RDKit could not parse SMILES: {smiles}")
    return CalcMolFormula(mol)
