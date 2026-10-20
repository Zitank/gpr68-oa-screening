"""Pydantic v2 corpus record schema. Mirrors literature/corpus/SCHEMA.md exactly."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

AccessClass = Literal["oa-cc", "oa-arxiv", "oa-other", "ieee-no-ai", "paywalled-no-ai", "unknown"]
OAStatus = Literal["diamond", "gold", "green", "hybrid", "bronze", "closed", "unknown"]
ACCESS_CLASSES: frozenset[str] = frozenset(AccessClass.__args__)  # type: ignore[attr-defined]

_DOI_PREFIXES = ("https://doi.org/", "http://doi.org/", "https://dx.doi.org/", "http://dx.doi.org/", "doi:")


class OA(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: OAStatus
    url: str | None
    license: str | None


class Provenance(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: str
    url: str
    retrieved_utc: str


class Screening(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["include", "exclude"]
    code: str
    reason: str
    by: Literal["librarian", "human"]
    date: str


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    doi: str | None = None
    arxiv_id: str | None = None
    title: str
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    venue: str | None = None
    type: str | None = None
    is_preprint: bool = False
    published_version_of: str | None = None
    abstract: str | None = None
    url: str | None = None
    oa: OA
    access_class: AccessClass
    cluster: list[str] = Field(default_factory=list)
    seed_id: str | None = None
    found_in: Annotated[list[str], Field(min_length=1)]
    queries: list[str] = Field(default_factory=list)
    cited_by_count: int | None = None
    retracted: bool | None = None
    provenance: Annotated[list[Provenance], Field(min_length=1)]
    screening: Screening | None = None
    tier: int | None = None
    notes: str = ""

    @field_validator("doi", mode="before")
    @classmethod
    def _doi(cls, v: object) -> str | None:
        if v is None or v == "":
            return None
        if not isinstance(v, str):
            raise ValueError("doi must be a string or null")
        s = v.strip().lower()
        for p in _DOI_PREFIXES:
            if s.startswith(p):
                s = s[len(p) :]
                break
        return s or None

    @field_validator("arxiv_id", mode="before")
    @classmethod
    def _arxiv(cls, v: object) -> str | None:
        if v is None or v == "":
            return None
        if not isinstance(v, str):
            raise ValueError("arxiv_id must be a string or null")
        s = re.sub(r"(?i)^arxiv:", "", v.strip())
        s = re.sub(r"v\d+$", "", s)
        return s or None

    @field_validator("access_class")
    @classmethod
    def _access(cls, v: str) -> str:
        if v not in ACCESS_CLASSES:
            raise ValueError(f"access_class not in {sorted(ACCESS_CLASSES)}")
        return v

    @field_validator("tier")
    @classmethod
    def _tier(cls, v: int | None) -> int | None:
        if v is not None and v not in {1, 2, 3, 4}:
            raise ValueError("tier must be 1..4 or null")
        return v


def load_records(path: Path) -> list[Record]:
    out: list[Record] = []
    text = path.read_text(encoding="utf-8")
    for i, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
            out.append(Record.model_validate(obj))
        except (json.JSONDecodeError, ValidationError) as exc:
            raise ValueError(f"{path}:{i}: {exc}") from exc
    return out


def dump_records(records: list[Record], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(rec.model_dump_json() + "\n")


def next_record_id(records: list[Record]) -> str:
    n = 0
    for rec in records:
        if rec.id.startswith("r-"):
            try:
                n = max(n, int(rec.id[2:]))
            except ValueError:
                continue
    return f"r-{n + 1:04d}"


def reconstruct_abstract(inverted: dict[str, list[int]]) -> str:
    n = max((max(p) for p in inverted.values() if p), default=-1)
    words = [""] * (n + 1)
    for word, pos in inverted.items():
        for i in pos:
            words[i] = word
    return " ".join(words)


def crossref_authors(items: list[Any]) -> list[str]:
    names: list[str] = []
    for i, a in enumerate(items):
        if i == 10:
            names.append("et al.")
            break
        names.append(f"{a.get('family', '')}, {a.get('given', '')}".strip(", "))
    return names


def crossref_year(msg: dict[str, Any]) -> int | None:
    for k in ("published-print", "published-online", "issued", "posted"):
        parts = (msg.get(k) or {}).get("date-parts") or [[]]
        if parts and parts[0]:
            return int(parts[0][0])
    return None


def infer_access(status: str, license: str | None, venue: str | None, arxiv: bool) -> AccessClass:
    lic, ven = (license or "").lower(), (venue or "").lower()
    if "ieee" in ven:
        return "ieee-no-ai"
    if lic.startswith("cc-") or "creativecommons" in lic:
        return "oa-cc"
    if arxiv:
        return "oa-arxiv"
    if status in {"diamond", "gold", "hybrid", "bronze"}:
        return "oa-other"
    return "paywalled-no-ai" if status == "closed" else "unknown"
