"""Write the pocket artefacts: chain R, both protomers, docking boxes, topology figure.

Run from the repo root:

    .venv/bin/python -m clusters.pocket.src.pipeline
"""

from __future__ import annotations

import json
import shutil
import subprocess
import urllib.request
from pathlib import Path
from typing import Any

from clusters.pocket.src.annotate import centroid
from clusters.pocket.src.extract import extract_chain, heavy_atom_count
from clusters.pocket.src.facts import PLAN_CHAIN, PLAN_CHAIN_R_ATOMS
from clusters.pocket.src.figure import ca_trace, write_topology
from clusters.pocket.src.pdbio import iter_atoms
from clusters.pocket.src.points import read_pockets
from clusters.pocket.src.protonate import (
    PH_COMPARISON,
    PH_PRIMARY,
    flipped_histidines,
    pdbqt_from_pdb,
    protonate_pdb,
    read_states,
)
from clusters.pocket.src.summary import chain_r_facts, contradictions, gs_geometry, pocket_records
from core.errors import ContractViolation

REPO = Path(__file__).resolve().parents[3]
POINTS_PDB = REPO / "data" / "pocket" / "8Z68_GPR68_only.pdb_points.pdb"
PDB_URL = "https://files.rcsb.org/download/8Z68.pdb"
TMP_PDB = Path("/tmp/8Z68.pdb")

DATA = REPO / "data" / "pocket"
STRUCTURES = REPO / "data" / "structures"
RESULTS = REPO / "results" / "pocket"


def main() -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    DATA.mkdir(parents=True, exist_ok=True)
    pdb_path = ensure_pdb(STRUCTURES / "8Z68.pdb")
    full_text = pdb_path.read_text()
    chain_text = extract_chain(full_text, PLAN_CHAIN)
    chain_path = DATA / "chainR.pdb"
    chain_path.write_text(chain_text)
    chain_atoms = iter_atoms(chain_text)
    facts = chain_r_facts(chain_atoms)
    if facts["atom_count"] != PLAN_CHAIN_R_ATOMS:
        raise ContractViolation(
            f"chain R has {facts['atom_count']} atoms; the plan states {PLAN_CHAIN_R_ATOMS}. "
            "Refusing to continue with a different structure."
        )
    acidic_path = DATA / "chainR_pH6.8.pdb"
    neutral_path = DATA / "chainR_pH7.4.pdb"
    acidic_cmd = protonate_pdb(chain_path, acidic_path, PH_PRIMARY)
    neutral_cmd = protonate_pdb(chain_path, neutral_path, PH_COMPARISON)
    _require_same_heavy_atoms(chain_path, acidic_path, neutral_path)
    acidic_states = read_states(acidic_path.read_text())
    neutral_states = read_states(neutral_path.read_text())
    flips = flipped_histidines(acidic_states, neutral_states)
    receptor_path = DATA / "receptor_pH6.8.pdbqt"
    pdbqt_cmd = pdbqt_from_pdb(acidic_path, receptor_path)
    points = read_pockets(POINTS_PDB.read_text())
    full_atoms = iter_atoms(full_text)
    records = pocket_records(points, chain_atoms)
    geometry = gs_geometry(
        points,
        [atom for atom in chain_atoms if atom.name == "CA"],
        [atom for atom in full_atoms if atom.chain == "A"],
        [atom for atom in full_atoms if atom.chain in {"A", "B", "G"}],
    )
    notes = contradictions(facts, geometry, records)
    histidine_payload = {
        "engine": "openbabel",
        "ph_primary": PH_PRIMARY,
        "ph_comparison": PH_COMPARISON,
        "assumption": "A5",
        "method": (
            "OpenBabel -p writes hydrogens named 'H'. State is the heavy atom nearest each hydrogen: "
            "HID if only ND1, HIE if only NE2, HIP if both, UNPROTONATED if neither imidazole nitrogen "
            "has a hydrogen. Atoms are not moved."
        ),
        "commands": {"ph_6_8": acidic_cmd, "ph_7_4": neutral_cmd, "pdbqt": pdbqt_cmd},
        "pdbqt_tool": (
            "OpenBabel -xr. Meeko's receptor templates reject this protonated PDB because every "
            "hydrogen is named H, so the production receptor PDBQT is the OpenBabel file. "
            "Vina scoring uses atom types; OpenBabel writes partial charges as 0."
        ),
        "states_ph_6_8": [row.as_dict() for row in acidic_states],
        "states_ph_7_4": [row.as_dict() for row in neutral_states],
        "flipped": list(flips),
        "unprotonated_at_both_ph": [
            row.resseq
            for row in acidic_states
            if row.state == "UNPROTONATED"
            and next(item.state == "UNPROTONATED" for item in neutral_states if item.resseq == row.resseq)
        ],
    }
    pockets_payload = {
        "structure": "8Z68",
        "chain": PLAN_CHAIN,
        "chain_R": facts,
        "box_edge_A": records[0]["size_x"],
        "assumption_box_edge": "A1",
        "gs_geometry": geometry,
        "contradictions": notes,
        "pockets": records,
    }
    _write_json(RESULTS / "histidines.json", histidine_payload)
    _write_json(RESULTS / "pockets.json", pockets_payload)
    _write_json(RESULTS / "docking_box.json", _docking_box(records))
    ca_xyz, ca_resseq = ca_trace(chain_atoms)
    write_topology(
        RESULTS / "topology.png",
        ca_xyz,
        ca_resseq,
        points[1].xyz,
        points[2].xyz,
        geometry["axis_unit_from_chainA_through_chainR"],
        centroid([atom for atom in chain_atoms if atom.name == "CA"]),
    )
    _write_readme(RESULTS / "README.md", histidine_payload, pockets_payload)
    for note in notes:
        print(f"CONTRADICTION: {note}")
    print(f"wrote {RESULTS / 'docking_box.json'}")
    print(f"histidines flipped: {histidine_payload['flipped']}")
    print(f"unprotonated at both pH: {histidine_payload['unprotonated_at_both_ph']}")


def ensure_pdb(dest: Path) -> Path:
    """Copy a validated local 8Z68, otherwise download it over IPv4."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if _pdb_ok(dest):
        return dest
    if _pdb_ok(TMP_PDB):
        shutil.copyfile(TMP_PDB, dest)
        return dest
    _download_ipv4(PDB_URL, dest)
    if not _pdb_ok(dest):
        raise ContractViolation(f"downloaded {dest} is not 8Z68 chain R")
    return dest


def _pdb_ok(path: Path) -> bool:
    if not path.is_file() or path.stat().st_size < 100_000:
        return False
    text = path.read_text(errors="replace")
    return "8Z68" in text[:500] or "GPR68" in text[:2500] or "OGR" in text[:2500]


def _download_ipv4(url: str, dest: Path) -> None:
    """Force IPv4. NCBI/RCSB TLS is reset on this box when IPv6 is selected."""
    curl = shutil.which("curl")
    if curl is None:
        raise ContractViolation("curl is not on PATH; cannot download 8Z68 over IPv4")
    completed = subprocess.run(
        [curl, "-4", "-fsSL", "--retry", "3", "--max-time", "120", "-o", str(dest), url],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        # urllib fallback also pinned to IPv4
        try:
            _urllib_ipv4(url, dest)
        except OSError as exc:
            raise ContractViolation(f"8Z68 download failed: {completed.stderr.strip()} / {exc}") from exc


def _urllib_ipv4(url: str, dest: Path) -> None:
    import socket

    original = socket.getaddrinfo

    def ipv4_only(host, port, family=0, type=0, proto=0, flags=0):  # noqa: A002
        return original(host, port, socket.AF_INET, type, proto, flags)

    socket.getaddrinfo = ipv4_only
    try:
        urllib.request.urlretrieve(url, dest)  # noqa: S310 — fixed RCSB URL
    finally:
        socket.getaddrinfo = original


def _require_same_heavy_atoms(reference: Path, *others: Path) -> None:
    expected = heavy_atom_count(reference.read_text())
    for path in others:
        found = heavy_atom_count(path.read_text())
        if found != expected:
            raise ContractViolation(f"{path.name} has {found} heavy atoms; chain R PDB has {expected}")


def _docking_box(records: list[dict[str, Any]]) -> dict[str, Any]:
    boxes = []
    for record in records:
        boxes.append(
            {
                "pocket_id": record["pocket_id"],
                "role": record["role"],
                "center_x": record["center_x"],
                "center_y": record["center_y"],
                "center_z": record["center_z"],
                "size_x": record["size_x"],
                "size_y": record["size_y"],
                "size_z": record["size_z"],
                "centre_source": record["centre_source"],
            }
        )
    return {
        "structure": "8Z68",
        "chain": "R",
        "ph_primary": PH_PRIMARY,
        "box_edge_A": records[0]["size_x"],
        "assumption_box_edge": "A1",
        "note": (
            "Pockets 1 and 2 use the plan centres exactly. Other pockets use the "
            "point-mean rounded to two decimals. The edge is the same for every pocket."
        ),
        "pockets": boxes,
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _write_readme(path: Path, histones: dict[str, Any], pockets: dict[str, Any]) -> None:
    flips = histones["flipped"]
    flip_text = ", ".join(f"HIS{row['resseq']} {row['ph_7_4']}→{row['ph_6_8']}" for row in flips) or "none"
    bare = ", ".join(f"HIS{resseq}" for resseq in histones["unprotonated_at_both_ph"]) or "none"
    lines = [
        "# Pocket module",
        "",
        "Engine for protonation and the receptor PDBQT: **OpenBabel 3.2.1**.",
        "No docking scores in this folder.",
        "",
        f"Primary state pH {histones['ph_primary']} (assumption A5).",
        f"Comparison state pH {histones['ph_comparison']}.",
        f"Histidines whose state changed: {flip_text}.",
        f"Histidines with no hydrogen on ND1 or NE2 at either pH: {bare}.",
        "",
        "OpenBabel names every hydrogen `H`.",
        "States above are nearest-heavy-atom assignments, not residue-name changes.",
        "Where the state is UNPROTONATED, OpenBabel placed two hydrogens on CD2",
        "and none on the imidazole nitrogens.",
        "That is a property of OpenBabel's pH model on this structure.",
        "The coordinates were not edited to correct it.",
        "",
        "Meeko could not build a receptor from the protonated PDB",
        "(every hydrogen is named H, so residue templates do not match).",
        "The docking receptor is `data/pocket/receptor_pH6.8.pdbqt`,",
        "written by OpenBabel `-xr` from the pH 6.8 PDB.",
        "OpenBabel writes partial charges as 0. Smina's Vina score uses atom types, not those charges.",
        "",
        "## Plan checks",
        "",
    ]
    for note in pockets["contradictions"]:
        lines.append(f"- CONTRADICTION: {note}")
    if not pockets["contradictions"]:
        lines.append(
            "- No numerical contradiction with the plan's chain-R counts, centres, or 60.3 Å figure."
        )
    lines.extend(
        ["", "Pocket centres used for the eight runs are the plan values. They were not replaced.", ""]
    )
    path.write_text("\n".join(lines))


if __name__ == "__main__":
    main()
