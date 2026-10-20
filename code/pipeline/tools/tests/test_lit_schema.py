from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from tools.lit.schema import OA, Provenance, Record, dump_records, load_records, next_record_id


def _valid(**kwargs: object) -> dict[str, object]:
    rec: dict[str, object] = {
        "id": "r-0001",
        "doi": "10.1000/example.1",
        "arxiv_id": None,
        "title": "Example title",
        "authors": ["Doe, Jane"],
        "year": 2020,
        "venue": "Example Venue",
        "type": "journal-article",
        "is_preprint": False,
        "published_version_of": None,
        "abstract": None,
        "url": "https://doi.org/10.1000/example.1",
        "oa": {"status": "gold", "url": None, "license": "cc-by"},
        "access_class": "oa-cc",
        "cluster": ["C"],
        "seed_id": "c1",
        "found_in": ["crossref"],
        "queries": ["seed:c1"],
        "cited_by_count": 1,
        "retracted": False,
        "provenance": [
            {
                "source": "crossref",
                "url": "https://api.crossref.org/works/10.1000/example.1",
                "retrieved_utc": "2026-10-04T08:00:00Z",
            }
        ],
        "screening": None,
        "tier": None,
        "notes": "",
    }
    rec.update(kwargs)
    return rec


def test_doi_stripped_and_lowercased() -> None:
    rec = Record.model_validate(_valid(doi="https://doi.org/10.1000/EXAMPLE.1"))
    assert rec.doi == "10.1000/example.1"


def test_arxiv_version_stripped() -> None:
    rec = Record.model_validate(_valid(doi=None, arxiv_id="arxiv:1706.03762v2"))
    assert rec.arxiv_id == "1706.03762"


def test_empty_provenance_rejected() -> None:
    with pytest.raises(ValidationError):
        Record.model_validate(_valid(provenance=[]))


def test_empty_found_in_rejected() -> None:
    with pytest.raises(ValidationError):
        Record.model_validate(_valid(found_in=[]))


def test_extra_field_forbidden() -> None:
    with pytest.raises(ValidationError):
        Record.model_validate(_valid(invented=True))  # type: ignore[arg-type]


def test_access_class_enum() -> None:
    with pytest.raises(ValidationError):
        Record.model_validate(_valid(access_class="paywalled"))


def test_load_records_line_number(tmp_path: Path) -> None:
    path = tmp_path / "r.jsonl"
    path.write_text(Record.model_validate(_valid()).model_dump_json() + "\n{not json}\n", encoding="utf-8")
    with pytest.raises(ValueError, match=":2:"):
        load_records(path)


def test_dump_roundtrip(tmp_path: Path) -> None:
    rec = Record.model_validate(_valid())
    path = tmp_path / "r.jsonl"
    dump_records([rec], path)
    back = load_records(path)
    assert back[0].id == rec.id
    assert next_record_id(back) == "r-0002"
    assert isinstance(rec.oa, OA)
    assert isinstance(rec.provenance[0], Provenance)
