"""Upstream files are read or marked pending. Missing numbers stay missing."""

from __future__ import annotations

from clusters.report.src.upstream import _box_rows, _key_wanted


def test_box_rows_from_a_list() -> None:
    payload = [{"pocket_id": 1, "center_x": 1.0, "center_y": 2.0, "center_z": 3.0}]
    rows = _box_rows(payload)
    assert rows[0]["pocket_id"] == 1


def test_box_rows_from_a_pockets_object() -> None:
    payload = {"ph": 6.8, "pockets": [{"center_x": 1, "center_y": 2, "center_z": 3, "role": "primary"}]}
    assert _box_rows(payload)[0]["role"] == "primary"


def test_unrecognised_json_yields_no_rows() -> None:
    assert _box_rows({"note": "not a box"}) == []


def test_metric_keys() -> None:
    assert _key_wanted("scaffold_split_roc_auc")
    assert not _key_wanted("duration_s")
