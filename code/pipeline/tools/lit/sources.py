"""Thin literature API clients. Failures return SourceUnavailable; never invent payloads."""

from __future__ import annotations

import re
import urllib.parse
from html import unescape
from typing import Any

from tools.lit import SourceUnavailable, _get, _json
from tools.lit.schema import (
    OA,
    Provenance,
    Record,
    crossref_authors,
    crossref_year,
    infer_access,
    reconstruct_abstract,
)

_OA_OK = frozenset({"gold", "green", "hybrid", "bronze", "closed", "unknown"})
_META = re.compile(
    r"<meta\s[^>]*name=['\"]([^'\"]+)['\"][^>]*content=['\"]([^'\"]*)['\"][^>]*>|"
    r"<meta\s[^>]*content=['\"]([^'\"]*)['\"][^>]*name=['\"]([^'\"]+)['\"][^>]*>",
    re.I,
)
_ABS_ID = re.compile(r"/abs/([a-z\-]+/\d{7}|\d{4}\.\d{4,5})(?:v\d+)?", re.I)


def _unwrap(got: object, source: str) -> tuple[dict[str, Any], Provenance] | SourceUnavailable:
    if isinstance(got, SourceUnavailable):
        return got
    if not isinstance(got, tuple) or not isinstance(got[0], dict):
        return SourceUnavailable(source, "not an object")
    inner = got[0].get("message")
    return (inner if isinstance(inner, dict) else got[0]), got[1]


def crossref_work(doi: str) -> tuple[dict[str, Any], Provenance] | SourceUnavailable:
    return _unwrap(
        _json("https://api.crossref.org/works/" + urllib.parse.quote(doi), "crossref", throttle=True),
        "crossref",
    )


def crossref_search(
    query: str, rows: int, filter: str | None = None
) -> tuple[dict[str, Any], Provenance] | SourceUnavailable:
    q = {"query.bibliographic": query, "rows": str(rows)}
    if filter:
        q["filter"] = filter
    return _unwrap(
        _json("https://api.crossref.org/works?" + urllib.parse.urlencode(q), "crossref", throttle=True),
        "crossref",
    )


def openalex_work(doi_or_id: str) -> tuple[dict[str, Any], Provenance] | SourceUnavailable:
    s = doi_or_id.strip()
    if s.startswith("10."):
        url = "https://api.openalex.org/works/https://doi.org/" + urllib.parse.quote(s)
    elif s.startswith("http"):
        url = "https://api.openalex.org/works/" + urllib.parse.quote(s, safe="")
    else:
        url = "https://api.openalex.org/works/" + urllib.parse.quote(s)
    return _unwrap(_json(url, "openalex", throttle=True), "openalex")


def openalex_search(
    query: str, per_page: int, filter: str | None = None
) -> tuple[dict[str, Any], Provenance] | SourceUnavailable:
    q: dict[str, str] = {"search": query, "per-page": str(per_page)}
    if filter:
        q["filter"] = filter
    return _json("https://api.openalex.org/works?" + urllib.parse.urlencode(q), "openalex", throttle=True)


def openalex_cited_by(work_id: str) -> tuple[dict[str, Any], Provenance] | SourceUnavailable:
    q = urllib.parse.urlencode({"filter": f"cites:{work_id}", "per-page": "25"})
    return _json("https://api.openalex.org/works?" + q, "openalex", throttle=True)


def openalex_references(work_id: str) -> tuple[dict[str, Any], Provenance] | SourceUnavailable:
    return openalex_work(work_id)


def arxiv_abs(arxiv_id: str) -> tuple[dict[str, Any], Provenance] | SourceUnavailable:
    got = _get(f"https://arxiv.org/abs/{arxiv_id}", "arxiv", throttle=False)
    if isinstance(got, SourceUnavailable):
        return got
    tags: dict[str, list[str]] = {}
    for a, b, c, d in _META.findall(got[0].decode("utf-8", "replace")):
        name, val = (a, unescape(b)) if a else (d, unescape(c))
        tags.setdefault(name.lower(), []).append(val)
    return {"arxiv_id": arxiv_id, "meta": tags}, got[1]


def s2_paper(id: str) -> tuple[dict[str, Any], Provenance] | SourceUnavailable:
    url = "https://api.semanticscholar.org/graph/v1/paper/" + urllib.parse.quote(id)
    return _json(url, "s2", throttle=False, retries=0)


def record_from_crossref(msg: dict[str, Any], *, rec_id: str, prov: Provenance, query_id: str = "") -> Record:
    doi, titles = msg.get("DOI"), msg.get("title") or [""]
    venue = (msg.get("container-title") or [None])[0]
    lic = (msg.get("license") or [{}])[0].get("URL") if msg.get("license") else None
    abs_ = msg.get("abstract")
    if isinstance(abs_, str):
        abs_ = " ".join(re.sub(r"<[^>]+>", " ", abs_).split())
    typ = msg.get("type")
    ret = any((u.get("type") or "").lower() == "retraction" for u in msg.get("update-to") or [])
    return Record(
        id=rec_id,
        doi=doi,
        title=titles[0] if titles else "",
        authors=crossref_authors(msg.get("author") or []),
        year=crossref_year(msg),
        venue=venue,
        type=typ,
        is_preprint=typ in {"posted-content", "preprint"},
        abstract=abs_,
        url=msg.get("URL") or (f"https://doi.org/{doi}" if doi else None),
        oa=OA(status="unknown", url=None, license=lic),
        access_class=infer_access("unknown", lic, venue, False),
        found_in=["crossref"],
        queries=[query_id] if query_id else [],
        cited_by_count=msg.get("is-referenced-by-count"),
        retracted=True if ret else None,
        provenance=[prov],
    )


def record_from_openalex(
    work: dict[str, Any], *, rec_id: str, prov: Provenance, query_id: str = ""
) -> Record:
    ids, loc, oa_b = work.get("ids") or {}, work.get("primary_location") or {}, work.get("open_access") or {}
    src, status, lic = loc.get("source") or {}, oa_b.get("oa_status") or "unknown", loc.get("license")
    doi = (work.get("doi") or ids.get("doi") or "").replace("https://doi.org/", "") or None
    inv, venue, authors, arxiv = work.get("abstract_inverted_index"), src.get("display_name"), [], None
    for i, a in enumerate(work.get("authorships") or []):
        if i == 10:
            authors.append("et al.")
            break
        name = (a.get("author") or {}).get("display_name") or a.get("raw_author_name") or ""
        parts = name.rsplit(" ", 1)
        authors.append(f"{parts[1]}, {parts[0]}" if len(parts) == 2 else name)
    for locn in work.get("locations") or []:
        m = _ABS_ID.search((locn.get("landing_page_url") or "") + (locn.get("pdf_url") or ""))
        if m:
            arxiv = m.group(1)
            break
    return Record(
        id=rec_id,
        doi=doi,
        arxiv_id=arxiv,
        title=work.get("title") or work.get("display_name") or "",
        authors=authors,
        year=work.get("publication_year"),
        venue=venue,
        type=work.get("type"),
        is_preprint=work.get("type") == "preprint",
        abstract=reconstruct_abstract(inv) if isinstance(inv, dict) else None,
        url=ids.get("doi") or work.get("id"),
        oa=OA(status=status if status in _OA_OK else "unknown", url=oa_b.get("oa_url"), license=lic),
        access_class=infer_access(status, lic, venue, arxiv is not None),
        found_in=["openalex"],
        queries=[query_id] if query_id else [],
        cited_by_count=work.get("cited_by_count"),
        retracted=work.get("is_retracted"),
        provenance=[prov],
    )


def record_from_arxiv(
    payload: dict[str, Any], *, rec_id: str, prov: Provenance, query_id: str = ""
) -> Record:
    meta: dict[str, list[str]] = payload.get("meta") or {}
    aid = payload.get("arxiv_id") or (meta.get("citation_arxiv_id") or [None])[0]
    date = (meta.get("citation_date") or [""])[0]
    authors = meta.get("citation_author") or []
    return Record(
        id=rec_id,
        doi=(meta.get("citation_doi") or [None])[0],
        arxiv_id=aid,
        title=(meta.get("citation_title") or [""])[0],
        authors=authors[:10] + ["et al."] if len(authors) > 10 else authors,
        year=int(date[:4]) if date[:4].isdigit() else None,
        venue="arXiv",
        type="preprint",
        is_preprint=True,
        abstract=(meta.get("citation_abstract") or [None])[0],
        url=f"https://arxiv.org/abs/{aid}" if aid else None,
        oa=OA(status="green", url=f"https://arxiv.org/abs/{aid}" if aid else None, license=None),
        access_class="oa-arxiv",
        found_in=["arxiv"],
        queries=[query_id] if query_id else [],
        provenance=[prov],
    )
