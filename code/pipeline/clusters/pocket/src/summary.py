"""Pocket table: centres, extents, scores, and residue shells.

## [EXPLORATORY]
Shell membership is a distance from P2Rank points to chain-R atoms. A residue
in a shell lines a computationally predicted candidate site. It is not a
binding-site annotation.

The 5 Å and 6 Å cutoffs are the ones the M2 task asks for.
"""

from __future__ import annotations

import math
from typing import Any

from clusters.pocket.src.annotate import centroid, nearest_atom_distance, residue_shell
from clusters.pocket.src.box import BOX_EDGE_A, POCKET_ROLES
from clusters.pocket.src.facts import (
    PLAN_CENTRES,
    PLAN_CHAIN_R_ATOMS,
    PLAN_CHAIN_R_HETATM,
    PLAN_LINING,
    PLAN_NEAREST_ATOM_RANGE_A,
    PLAN_POCKET1_GS_DISTANCE_A,
    PLAN_RESSEQ_RANGE,
)
from clusters.pocket.src.pdbio import AtomRec
from clusters.pocket.src.points import PocketPoints, docking_centre
from core.errors import ContractViolation

SHELL_A: tuple[float, float] = (5.0, 6.0)


def pocket_records(
    pockets: dict[int, PocketPoints],
    chain_atoms: list[AtomRec],
) -> list[dict[str, Any]]:
    """One JSON-ready record per pocket id 1..7."""
    records: list[dict[str, Any]] = []
    for pocket_id in sorted(pockets):
        pocket = pockets[pocket_id]
        centre = docking_centre(pockets, pocket_id)
        shell_5 = residue_shell(chain_atoms, pocket, SHELL_A[0])
        shell_6 = residue_shell(chain_atoms, pocket, SHELL_A[1])
        role = POCKET_ROLES.get(pocket_id, "not_in_the_eight_runs")
        record: dict[str, Any] = {
            "pocket_id": pocket_id,
            "role": role,
            "centre_source": "plan" if pocket_id in PLAN_CENTRES else "point_mean_rounded_2dp",
            "center_x": centre[0],
            "center_y": centre[1],
            "center_z": centre[2],
            "size_x": BOX_EDGE_A,
            "size_y": BOX_EDGE_A,
            "size_z": BOX_EDGE_A,
            "point_count": pocket.count,
            "score_sum": pocket.score_sum,
            "score_max": pocket.score_max,
            "extent_min": list(pocket.extent_min),
            "extent_max": list(pocket.extent_max),
            "span": list(pocket.span),
            "nearest_chain_atom_A": nearest_atom_distance(chain_atoms, centre),
            "residues_5A": shell_5,
            "residues_6A": shell_6,
        }
        if pocket_id in PLAN_LINING:
            planned = set(PLAN_LINING[pocket_id])
            record["plan_lining"] = list(PLAN_LINING[pocket_id])
            record["plan_lining_missing_from_5A"] = sorted(planned - set(shell_5))
            record["plan_lining_missing_from_6A"] = sorted(planned - set(shell_6))
            record["residues_in_5A_not_named_by_plan"] = sorted(set(shell_5) - planned)
        records.append(record)
    return records


def chain_r_facts(chain_atoms: list[AtomRec]) -> dict[str, Any]:
    """Counts the plan states for chain R. A mismatch is reported, not edited away."""
    if not chain_atoms:
        raise ContractViolation("chain R atom list is empty")
    resseqs = [atom.resseq for atom in chain_atoms]
    hetatm = sum(1 for atom in chain_atoms if atom.line.startswith("HETATM"))
    return {
        "chain": "R",
        "atom_count": len(chain_atoms),
        "hetatm_count": hetatm,
        "resseq_min": min(resseqs),
        "resseq_max": max(resseqs),
        "plan_atom_count": PLAN_CHAIN_R_ATOMS,
        "plan_hetatm_count": PLAN_CHAIN_R_HETATM,
        "plan_resseq_range": list(PLAN_RESSEQ_RANGE),
        "atom_count_matches_plan": len(chain_atoms) == PLAN_CHAIN_R_ATOMS and hetatm == PLAN_CHAIN_R_HETATM,
        "resseq_matches_plan": (min(resseqs), max(resseqs)) == PLAN_RESSEQ_RANGE,
    }


def gs_geometry(
    pockets: dict[int, PocketPoints],
    chain_ca: list[AtomRec],
    chain_a_atoms: list[AtomRec],
    heterotrimer_atoms: list[AtomRec],
) -> dict[str, Any]:
    """Distances from pocket centres to Gs centroids.

    ## [EXPLORATORY]
    The plan's 60.3 Å is checked against two centroids: chain A alone (Gαs,
    the molecule the PDB header names as Gs subunit alpha) and chains A+B+G
    together. The axis used for the topology figure runs from the chain A
    centroid through the chain R Cα centroid, pointing away from Gα.
    """
    if not chain_ca or not chain_a_atoms or not heterotrimer_atoms:
        raise ContractViolation("Gs geometry needs chain R Cα, chain A, and chains A+B+G")
    galpha = centroid(chain_a_atoms)
    heterotrimer = centroid(heterotrimer_atoms)
    receptor = centroid(chain_ca)
    axis = _unit([receptor[i] - galpha[i] for i in range(3)])
    centre_1 = docking_centre(pockets, 1)
    centre_2 = docking_centre(pockets, 2)
    return {
        "label": "EXPLORATORY",
        "plan_pocket1_gs_distance_A": PLAN_POCKET1_GS_DISTANCE_A,
        "chain_A_centroid": list(galpha),
        "chains_ABG_centroid": list(heterotrimer),
        "chain_R_CA_centroid": list(receptor),
        "pocket1_distance_to_chain_A_A": math.dist(centre_1, galpha),
        "pocket1_distance_to_ABG_A": math.dist(centre_1, heterotrimer),
        "pocket2_distance_to_chain_A_A": math.dist(centre_2, galpha),
        "pocket2_axial_offset_from_receptor_A": _along(centre_2, receptor, axis),
        "pocket1_axial_offset_from_receptor_A": _along(centre_1, receptor, axis),
        "pocket1_radial_A": _radial(centre_1, receptor, axis),
        "pocket2_radial_A": _radial(centre_2, receptor, axis),
        "axis_unit_from_chainA_through_chainR": list(axis),
        "nearest_atom_plan_range_A": list(PLAN_NEAREST_ATOM_RANGE_A),
    }


def contradictions(
    chain_facts: dict[str, Any], geometry: dict[str, Any], records: list[dict[str, Any]]
) -> list[str]:
    """Statements where a computed quantity disagrees with the plan's wording."""
    found: list[str] = []
    if not chain_facts["atom_count_matches_plan"]:
        found.append(
            f"chain R atom count is {chain_facts['atom_count']} (HETATM {chain_facts['hetatm_count']}); "
            f"plan states {chain_facts['plan_atom_count']} atoms "
            f"and {chain_facts['plan_hetatm_count']} HETATM"
        )
    if not chain_facts["resseq_matches_plan"]:
        found.append(
            f"chain R resSeq range is {chain_facts['resseq_min']}-{chain_facts['resseq_max']}; "
            f"plan states {chain_facts['plan_resseq_range'][0]}-{chain_facts['plan_resseq_range'][1]}"
        )
    chain_a = float(geometry["pocket1_distance_to_chain_A_A"])
    abg = float(geometry["pocket1_distance_to_ABG_A"])
    stated = float(geometry["plan_pocket1_gs_distance_A"])
    if round(chain_a, 1) != stated:
        found.append(
            f"pocket 1 is {chain_a:.2f} Å from the chain A (Gαs) all-atom centroid; "
            f"the plan states {stated} Å from the Gs centroid"
        )
    if round(abg, 1) != stated:
        found.append(
            f"pocket 1 is {abg:.2f} Å from the chains A+B+G all-atom centroid, "
            f"which does not round to the plan's {stated} Å. "
            f"The chain A centroid ({chain_a:.2f} Å) does round to {stated} Å."
        )
    low, high = PLAN_NEAREST_ATOM_RANGE_A
    for record in records:
        if record["pocket_id"] not in (1, 2):
            continue
        distance = float(record["nearest_chain_atom_A"])
        if distance < low or distance > high:
            found.append(
                f"pocket {record['pocket_id']} nearest chain-R atom is {distance:.2f} Å; "
                f"plan range is {low}-{high} Å"
            )
        missing = record.get("plan_lining_missing_from_6A") or []
        if missing:
            found.append(
                f"plan lining residues absent from the 6 Å shell of pocket {record['pocket_id']}: {missing}"
            )
    return found


def _unit(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        raise ContractViolation("Gs axis has zero length")
    return [value / norm for value in vector]


def _along(point: tuple[float, float, float], origin: tuple[float, float, float], axis: list[float]) -> float:
    return sum((point[i] - origin[i]) * axis[i] for i in range(3))


def _radial(
    point: tuple[float, float, float], origin: tuple[float, float, float], axis: list[float]
) -> float:
    offset = [point[i] - origin[i] for i in range(3)]
    along = sum(offset[i] * axis[i] for i in range(3))
    perp = [offset[i] - along * axis[i] for i in range(3)]
    return math.sqrt(sum(value * value for value in perp))
