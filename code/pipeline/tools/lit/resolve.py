"""Resolve a DOI, arXiv id, or 'title: …' string to a Record."""

from __future__ import annotations

import re
from difflib import SequenceMatcher

from tools.lit.dedupe import norm_text
from tools.lit.schema import Record
from tools.lit.sources import (
    SourceUnavailable,
    arxiv_abs,
    crossref_search,
    crossref_work,
    record_from_arxiv,
    record_from_crossref,
)

_DOI = re.compile(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.I)
_ARXIV = re.compile(r"(?:arxiv:)?(\d{4}\.\d{4,5}|[a-z\-]+/\d{7})(?:v\d+)?", re.I)


def _ratio(a: str, b: str) -> float:
    return SequenceMatcher(None, norm_text(a), norm_text(b)).ratio()


def _from_doi(doi: str) -> Record | SourceUnavailable:
    got = crossref_work(doi)
    if isinstance(got, SourceUnavailable):
        return got
    msg, prov = got
    return record_from_crossref(msg, rec_id="r-tmp", prov=prov)


def _from_arxiv(arxiv_id: str) -> Record | SourceUnavailable:
    got = arxiv_abs(arxiv_id)
    if isinstance(got, SourceUnavailable):
        return got
    payload, prov = got
    return record_from_arxiv(payload, rec_id="r-tmp", prov=prov)


def _from_title(title: str) -> Record | SourceUnavailable:
    got = crossref_search(title, rows=5)
    if isinstance(got, SourceUnavailable):
        return got
    msg, prov = got
    items = msg.get("items") or []
    best: tuple[float, Record] | None = None
    for item in items:
        if not isinstance(item, dict):
            continue
        rec = record_from_crossref(item, rec_id="r-tmp", prov=prov)
        score = _ratio(title, rec.title)
        if best is None or score > best[0]:
            best = (score, rec)
    if best is None or best[0] < 0.9:
        return SourceUnavailable("crossref", f"unresolved title (best={best[0] if best else 0:.2f})")
    return best[1]


def resolve_identifier(s: str) -> Record | SourceUnavailable:
    text = s.strip()
    if text.lower().startswith("title:"):
        return _from_title(text.split(":", 1)[1].strip())
    if text.lower().startswith("doi:"):
        text = text.split(":", 1)[1].strip()
    if text.lower().startswith("https://doi.org/"):
        text = text[16:]
    m_doi = _DOI.search(text)
    if text.lower().startswith("10.") and m_doi:
        return _from_doi(m_doi.group(0))
    if m_doi and "arxiv" not in text.lower() and not text.lower().startswith("arxiv"):
        return _from_doi(m_doi.group(0))
    m_arx = _ARXIV.fullmatch(text.strip())
    if m_arx:
        return _from_arxiv(m_arx.group(1))
    m_arx = _ARXIV.search(text)
    if m_arx and ("arxiv" in text.lower() or re.match(r"^\d{4}\.\d{4,5}", text)):
        return _from_arxiv(m_arx.group(1))
    return SourceUnavailable("resolve", f"unrecognised identifier: {s!r}")
