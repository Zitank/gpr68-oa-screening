"""Histidine state from hydrogen placement. No OpenBabel call."""

from __future__ import annotations

from clusters.pocket.src.pdbio import AtomRec
from clusters.pocket.src.protonate import HisState, classify_histidines, flipped_histidines


def _atom(name: str, xyz: tuple[float, float, float], element: str) -> AtomRec:
    return AtomRec(
        serial=1,
        name=name,
        resname="HIS",
        chain="R",
        resseq=20,
        x=xyz[0],
        y=xyz[1],
        z=xyz[2],
        element=element,
        line="ATOM",
    )


def _scaffold() -> list[AtomRec]:
    heavies = {
        "N": (0.0, 6.0, 0.0),
        "CA": (0.0, 5.0, 0.0),
        "ND1": (0.0, 0.0, 0.0),
        "NE2": (4.0, 0.0, 0.0),
        "CD2": (2.0, 2.0, 0.0),
        "CE1": (2.0, -2.0, 0.0),
    }
    return [_atom(name, xyz, "C" if name.startswith("C") else "N") for name, xyz in heavies.items()]


def test_nd1_hydrogen_is_hid() -> None:
    atoms = [*_scaffold(), _atom("H", (0.0, 0.0, 1.0), "H")]
    (state,) = classify_histidines(atoms)
    assert state.state == "HID"
    assert dict(state.parents)["ND1"] == 1


def test_both_nitrogens_are_hip() -> None:
    atoms = [
        *_scaffold(),
        _atom("H", (0.0, 0.0, 1.0), "H"),
        _atom("H", (4.0, 0.0, 1.0), "H"),
    ]
    (state,) = classify_histidines(atoms)
    assert state.state == "HIP"


def test_no_imidazole_hydrogen_is_unprotonated() -> None:
    atoms = [*_scaffold(), _atom("H", (2.0, 2.0, 1.0), "H")]
    (state,) = classify_histidines(atoms)
    assert state.state == "UNPROTONATED"
    assert dict(state.parents)["CD2"] == 1


def test_flip_reports_only_changes() -> None:
    acidic = (HisState(20, "HIS", "HIP", ()), HisState(269, "HIS", "UNPROTONATED", ()))
    neutral = (HisState(20, "HIS", "HID", ()), HisState(269, "HIS", "UNPROTONATED", ()))
    assert flipped_histidines(acidic, neutral) == ({"resseq": 20, "ph_6_8": "HIP", "ph_7_4": "HID"},)
