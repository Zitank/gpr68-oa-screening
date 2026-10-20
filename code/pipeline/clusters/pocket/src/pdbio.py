"""PDB atom records. Column layout is the PDB v3 coordinate section."""

from __future__ import annotations

from dataclasses import dataclass

from core.errors import ContractViolation


@dataclass(frozen=True)
class AtomRec:
    """One ATOM/HETATM record."""

    serial: int
    name: str
    resname: str
    chain: str
    resseq: int
    x: float
    y: float
    z: float
    element: str
    line: str

    @property
    def xyz(self) -> tuple[float, float, float]:
        return (self.x, self.y, self.z)


def parse_atom(line: str) -> AtomRec:
    """Parse one ATOM or HETATM line. ``ContractViolation`` if the record is short."""
    if not (line.startswith("ATOM") or line.startswith("HETATM")):
        raise ContractViolation(f"not an atom record: {line[:6]!r}")
    if len(line) < 54:
        raise ContractViolation(f"atom record shorter than the coordinate fields: {line!r}")
    name = line[12:16].strip()
    element = line[76:78].strip() if len(line) >= 78 else ""
    if element == "":
        element = "".join(ch for ch in name if ch.isalpha())[:1]
    try:
        serial = int(line[6:11])
        resseq = int(line[22:26])
        x = float(line[30:38])
        y = float(line[38:46])
        z = float(line[46:54])
    except ValueError as exc:
        raise ContractViolation(f"unreadable atom record: {line!r}") from exc
    return AtomRec(
        serial=serial,
        name=name,
        resname=line[17:20].strip(),
        chain=line[21],
        resseq=resseq,
        x=x,
        y=y,
        z=z,
        element=element,
        line=line,
    )


def format_atom(
    serial: int,
    name: str,
    resname: str,
    chain: str,
    resseq: int,
    xyz: tuple[float, float, float],
    element: str,
) -> str:
    """Write one ATOM line. Names of 1–3 characters are prefixed by a space, PDB-style."""
    if len(name) > 4 or len(resname) > 3 or len(element) > 2:
        raise ContractViolation(
            f"atom name {name!r} resname {resname!r} element {element!r} do not fit PDB columns"
        )
    atom_name = f" {name:<3s}" if len(name) <= 3 else f"{name:<4s}"
    return (
        f"ATOM  {serial:5d} {atom_name} {resname:>3s} {chain}{resseq:4d}    "
        f"{xyz[0]:8.3f}{xyz[1]:8.3f}{xyz[2]:8.3f}  1.00  0.00           {element:>2s}"
    )


def iter_atoms(text: str) -> list[AtomRec]:
    """ATOM and HETATM records in file order."""
    return [parse_atom(line) for line in text.splitlines() if line.startswith(("ATOM", "HETATM"))]
