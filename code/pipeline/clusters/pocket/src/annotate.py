"""Residue shells and distances from pocket points to chain R.

## [EXPLORATORY]
A residue is inside a shell when any of its atoms is within the cutoff of any
pocket point. That shell is a contact list around a predicted candidate site,
not a binding-site annotation.
"""

from __future__ import annotations

import math
from collections import defaultdict

from clusters.pocket.src.pdbio import AtomRec
from clusters.pocket.src.points import PocketPoints


def _by_residue(atoms: list[AtomRec]) -> dict[tuple[str, int], list[AtomRec]]:
    grouped: dict[tuple[str, int], list[AtomRec]] = defaultdict(list)
    for atom in atoms:
        grouped[(atom.resname, atom.resseq)].append(atom)
    return grouped


def residue_shell(
    atoms: list[AtomRec],
    pocket: PocketPoints,
    cutoff_a: float,
) -> list[str]:
    """Residue labels ``RESNAME+resSeq`` within ``cutoff_a`` of any pocket point, sorted by resSeq."""
    labels: list[tuple[int, str]] = []
    for (resname, resseq), group in _by_residue(atoms).items():
        if _min_distance(group, pocket) <= cutoff_a:
            labels.append((resseq, f"{resname}{resseq}"))
    labels.sort()
    return [label for _, label in labels]


def nearest_atom_distance(atoms: list[AtomRec], centre: tuple[float, float, float]) -> float:
    """Distance from a centre to the nearest atom."""
    return min(math.dist(centre, atom.xyz) for atom in atoms)


def centroid(atoms: list[AtomRec]) -> tuple[float, float, float]:
    """Unweighted mean of atom coordinates."""
    n = len(atoms)
    if n == 0:
        raise ValueError("centroid of an empty atom list")
    return (
        sum(atom.x for atom in atoms) / n,
        sum(atom.y for atom in atoms) / n,
        sum(atom.z for atom in atoms) / n,
    )


def _min_distance(group: list[AtomRec], pocket: PocketPoints) -> float:
    best = math.inf
    for atom in group:
        for point in pocket.xyz:
            distance = math.dist(atom.xyz, point)
            if distance < best:
                best = distance
    return best
