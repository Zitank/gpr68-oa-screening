from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.check_corpus import _fake, check_paths
from tools.lit.schema import Record, dump_records
from tools.lit.sources import SourceUnavailable, crossref_work, record_from_crossref


def _write(path: Path, recs: list[dict[str, object]]) -> Path:
    path.write_text("".join(json.dumps(r) + "\n" for r in recs), encoding="utf-8")
    return path


def test_fabricated_without_provenance_fails(tmp_path: Path) -> None:
    p = _write(tmp_path / "a.jsonl", [_fake(provenance=False)])
    n, f, w, msgs = check_paths([p], online=False)
    assert n == 0
    assert f >= 1
    assert w == 0
    assert any("FAIL" in m for m in msgs)


def test_duplicate_doi_fails(tmp_path: Path) -> None:
    a = _fake(provenance=True)
    b = _fake(provenance=True)
    b["id"] = "r-fake-2"
    p = _write(tmp_path / "a.jsonl", [a, b])
    _n, f, _w, msgs = check_paths([p], online=False)
    assert f >= 1
    assert any("duplicate" in m for m in msgs)


def test_valid_record_passes(tmp_path: Path) -> None:
    rec = _fake(provenance=True)
    rec["id"] = "r-0001"
    rec["doi"] = "10.1234/valid.offline.test"
    rec["arxiv_id"] = None
    p = _write(tmp_path / "a.jsonl", [rec])
    n, f, w, msgs = check_paths([p], online=False)
    assert n == 1
    assert f == 0
    assert w == 0
    assert msgs == []
    loaded = Record.model_validate(rec)
    dump_records([loaded], tmp_path / "round.jsonl")


@pytest.mark.slow
def test_online_real_doi_and_fake(tmp_path: Path) -> None:
    got = crossref_work("10.1038/nature14539")
    if isinstance(got, SourceUnavailable):
        pytest.skip(f"Crossref unavailable: {got.reason}")
    msg, prov = got
    rec = record_from_crossref(msg, rec_id="r-0001", prov=prov)
    ok = tmp_path / "ok.jsonl"
    dump_records([rec], ok)
    n, f, _w, _msgs = check_paths([ok], online=True)
    assert n == 1
    assert f == 0
    fake = _fake(provenance=True)
    fake["arxiv_id"] = None
    bad = _write(tmp_path / "bad.jsonl", [fake])
    _n, f, w, msgs = check_paths([bad], online=True)
    assert f >= 1
    assert any("does not resolve" in m or "HTTP 404" in m or "FAIL" in m for m in msgs)
