from __future__ import annotations

from tools.lit.dedupe import dedupe, keys_of
from tools.lit.schema import OA, Provenance, Record


def _rec(**kwargs: object) -> Record:
    base: dict[str, object] = {
        "id": "r-0001",
        "doi": None,
        "arxiv_id": None,
        "title": "Example title",
        "authors": ["Doe, Jane"],
        "year": 2023,
        "venue": None,
        "type": "journal-article",
        "is_preprint": False,
        "published_version_of": None,
        "abstract": None,
        "url": None,
        "oa": OA(status="unknown", url=None, license=None),
        "access_class": "unknown",
        "cluster": ["E"],
        "seed_id": None,
        "found_in": ["crossref"],
        "queries": ["E-q1"],
        "cited_by_count": None,
        "retracted": False,
        "provenance": [
            Provenance(
                source="crossref", url="https://api.crossref.org/works", retrieved_utc="2026-10-04T00:00:00Z"
            )
        ],
        "screening": None,
        "tier": None,
        "notes": "",
    }
    base.update(kwargs)
    return Record.model_validate(base)


def test_merge_preprint_and_published_keeps_both_ids() -> None:
    pub = _rec(
        id="r-0001", doi="10.1234/test.pub", is_preprint=False, found_in=["crossref"], queries=["E-q1"]
    )
    pre = _rec(
        id="r-0002",
        doi=None,
        arxiv_id="1234.56789",
        is_preprint=True,
        found_in=["arxiv"],
        queries=["snowball:fwd:x"],
        provenance=[
            Provenance(
                source="arxiv", url="https://arxiv.org/abs/1234.56789", retrieved_utc="2026-10-04T01:00:00Z"
            )
        ],
        venue="arXiv",
        type="preprint",
    )
    merged, report = dedupe([pub, pre])
    assert report.n_out == 1
    rec = merged[0]
    assert rec.doi == "10.1234/test.pub"
    assert rec.arxiv_id == "1234.56789"
    assert rec.is_preprint is False
    assert set(rec.found_in) == {"arxiv", "crossref"}
    assert set(rec.queries) == {"E-q1", "snowball:fwd:x"}
    assert len(rec.provenance) == 2


def test_same_doi_merges() -> None:
    a = _rec(id="r-0001", doi="10.1/abc", title="One")
    b = _rec(id="r-0002", doi="10.1/abc", title="Two different", authors=["Other, A"], year=2020)
    merged, report = dedupe([a, b])
    assert report.n_out == 1
    assert merged[0].doi == "10.1/abc"


def test_distinct_stay_distinct() -> None:
    a = _rec(id="r-0001", doi="10.1/a", title="Alpha", year=2020)
    b = _rec(id="r-0002", doi="10.1/b", title="Beta", year=2021)
    merged, report = dedupe([a, b])
    assert report.n_out == 2
    assert report.n_merged == 0
    assert "doi:10.1/a" in keys_of(a)
