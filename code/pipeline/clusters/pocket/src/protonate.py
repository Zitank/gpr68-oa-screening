"""Histidine protonation states, and OpenBabel pH protonation.

## [ASSUMPTION: A5] pH 6.8 is the primary receptor state because 8Z68 is the
pH 6.8 cryo-EM structure. pH 7.4 is the comparison state, not a cited pKa
for HIS20 or HIS269.

State names come from which imidazole nitrogen is nearest to a hydrogen:
HID = ND1 only, HIE = NE2 only, HIP = both, UNPROTONATED = neither.
This describes the coordinates OpenBabel wrote. It does not move atoms.
"""

from __future__ import annotations

import math
import subprocess
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

from clusters.pocket.src.pdbio import AtomRec, iter_atoms
from core.errors import ContractViolation

# ## [ASSUMPTION: A5]
PH_PRIMARY: float = 6.8
PH_COMPARISON: float = 7.4

_HIS_NAMES = frozenset({"HIS", "HID", "HIE", "HIP", "HSD", "HSE", "HSP"})
# pixi install from the pipeline root creates this binary. The environment is not in the repository.
_OBABEL = Path(__file__).resolve().parents[3] / ".pixi" / "envs" / "default" / "bin" / "obabel"


@dataclass(frozen=True)
class HisState:
    """Protonation of one histidine, inferred from hydrogen placement."""

    resseq: int
    resname: str
    state: str
    parents: tuple[tuple[str, int], ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "resseq": self.resseq,
            "resname": self.resname,
            "state": self.state,
            "parents": {name: count for name, count in self.parents},
        }


def classify_histidines(atoms: list[AtomRec], chain: str = "R") -> tuple[HisState, ...]:
    """Classify every histidine on ``chain``. Empty input is a contract failure."""
    grouped: dict[int, list[AtomRec]] = defaultdict(list)
    resnames: dict[int, str] = {}
    for atom in atoms:
        if atom.chain != chain or atom.resname not in _HIS_NAMES:
            continue
        grouped[atom.resseq].append(atom)
        resnames[atom.resseq] = atom.resname
    if not grouped:
        raise ContractViolation(f"no histidine residues on chain {chain}")
    return tuple(_one_histidine(resseq, grouped[resseq], resnames[resseq]) for resseq in sorted(grouped))


def flipped_histidines(
    acidic: tuple[HisState, ...],
    neutral: tuple[HisState, ...],
) -> tuple[dict[str, object], ...]:
    """Residues whose state differs between the two pH classifications."""
    by_neutral = {row.resseq: row for row in neutral}
    if set(by_neutral) != {row.resseq for row in acidic}:
        raise ContractViolation("the two pH structures do not contain the same histidine resSeqs")
    changes: list[dict[str, object]] = []
    for row in acidic:
        other = by_neutral[row.resseq]
        if row.state == other.state:
            continue
        changes.append(
            {
                "resseq": row.resseq,
                "ph_6_8": row.state,
                "ph_7_4": other.state,
            }
        )
    return tuple(changes)


def protonate_pdb(source: Path, dest: Path, ph: float, obabel: Path = _OBABEL) -> list[str]:
    """Run OpenBabel ``-p <ph>`` and write a protonated PDB. Returns the command."""
    if not obabel.is_file():
        raise ContractViolation(f"obabel binary is missing: {obabel}")
    if ph not in (PH_PRIMARY, PH_COMPARISON):
        raise ContractViolation(
            f"pH {ph} is not one of the two registered states ({PH_PRIMARY}, {PH_COMPARISON})"
        )
    dest.parent.mkdir(parents=True, exist_ok=True)
    command = [str(obabel), str(source), "-O", str(dest), "-p", f"{ph}"]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0 or not dest.is_file():
        detail = (completed.stderr or completed.stdout or "").strip()
        raise ContractViolation(f"obabel protonation at pH {ph} failed ({completed.returncode}): {detail}")
    return command


def pdbqt_from_pdb(source: Path, dest: Path, obabel: Path = _OBABEL) -> list[str]:
    """Rigid-receptor PDBQT via OpenBabel (``-xr``). No re-protonation."""
    if not obabel.is_file():
        raise ContractViolation(f"obabel binary is missing: {obabel}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    command = [str(obabel), str(source), "-O", str(dest), "-xr"]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0 or not dest.is_file():
        detail = (completed.stderr or completed.stdout or "").strip()
        raise ContractViolation(f"obabel PDBQT conversion failed ({completed.returncode}): {detail}")
    return command


def read_states(text: str, chain: str = "R") -> tuple[HisState, ...]:
    return classify_histidines(iter_atoms(text), chain=chain)


def _one_histidine(resseq: int, atoms: list[AtomRec], resname: str) -> HisState:
    heavies = [atom for atom in atoms if atom.element.upper() != "H"]
    hydrogens = [atom for atom in atoms if atom.element.upper() == "H"]
    if not heavies:
        raise ContractViolation(f"histidine {resseq} has no heavy atoms")
    names = {atom.name for atom in heavies}
    if "ND1" not in names or "NE2" not in names:
        raise ContractViolation(f"histidine {resseq} is missing ND1/NE2; found {sorted(names)}")
    counts: Counter[str] = Counter()
    for hydrogen in hydrogens:
        parent = min(heavies, key=lambda heavy: math.dist(heavy.xyz, hydrogen.xyz))
        counts[parent.name] += 1
    nd1 = counts.get("ND1", 0)
    ne2 = counts.get("NE2", 0)
    if nd1 and ne2:
        state = "HIP"
    elif nd1:
        state = "HID"
    elif ne2:
        state = "HIE"
    else:
        state = "UNPROTONATED"
    parents = tuple(sorted(counts.items()))
    return HisState(resseq=resseq, resname=resname, state=state, parents=parents)
