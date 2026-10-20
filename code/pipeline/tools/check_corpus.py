"""Corpus integrity checker. Fail loudly; source-unavailable is WARN not FAIL."""

from __future__ import annotations

import argparse
import json
import sys
from difflib import SequenceMatcher
from pathlib import Path
from tempfile import TemporaryDirectory

from pydantic import ValidationError

from tools.lit.dedupe import keys_of, norm_text
from tools.lit.prisma import capability
from tools.lit.schema import Record
from tools.lit.sources import SourceUnavailable, arxiv_abs, crossref_work

DEFAULT = Path(__file__).resolve().parents[1] / "literature" / "corpus" / "records.jsonl"


def _ratio(a: str, b: str) -> float:
    return SequenceMatcher(None, norm_text(a), norm_text(b)).ratio()


def _load_file(path: Path) -> tuple[list[Record], list[str]]:
    recs, fails = [], []
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            recs.append(Record.model_validate(json.loads(line)))
        except (json.JSONDecodeError, ValidationError) as exc:
            fails.append(f"FAIL {path}:{i}: {exc}")
    return recs, fails


def _offline(recs: list[Record]) -> list[str]:
    fails: list[str] = []
    seen: dict[str, str] = {}
    for rec in recs:
        for p in rec.provenance:
            if not (p.source and p.url and p.retrieved_utc):
                fails.append(f"FAIL {rec.id}: provenance missing source/url/retrieved_utc")
        for k in keys_of(rec):
            if k in seen:
                fails.append(f"FAIL {rec.id}: duplicate of {seen[k]} via {k}")
            else:
                seen[k] = rec.id
    return fails


def _cr_year(msg: dict) -> int | None:
    for k in ("published-print", "published-online", "issued"):
        parts = (msg.get(k) or {}).get("date-parts") or [[]]
        if parts and parts[0]:
            return int(parts[0][0])
    return None


def _remote(
    rec_id: str, label: str, got: object, title: str, year: int | None, remote: str, ryear: int | None
) -> tuple[list[str], list[str]]:
    if isinstance(got, SourceUnavailable):
        if "HTTP 404" in got.reason:
            return [f"FAIL {rec_id}: {label} does not resolve ({got.reason})"], []
        return [], [f"WARN unverifiable {rec_id} {label}: {got.reason}"]
    fails = []
    if _ratio(title, remote) < 0.85:
        fails.append(f"FAIL {rec_id}: {label} title mismatch")
    if year is not None and ryear is not None and abs(year - ryear) > 1:
        fails.append(f"FAIL {rec_id}: year {year} vs {ryear}")
    return fails, []


DATACITE_ARXIV_PREFIX = "10.48550/arxiv."


def _online_one(rec: Record) -> tuple[list[str], list[str]]:
    fails, warns = [], []
    if rec.doi and rec.doi.startswith(DATACITE_ARXIV_PREFIX):
        # arXiv's own DOIs are DataCite, not Crossref; verified through the arXiv abs page below.
        embedded = rec.doi[len(DATACITE_ARXIV_PREFIX) :]
        if rec.arxiv_id != embedded:
            fails.append(f"FAIL {rec.id}: DataCite DOI {rec.doi} does not match arxiv_id {rec.arxiv_id}")
        elif not rec.arxiv_id:
            fails.append(f"FAIL {rec.id}: DataCite DOI {rec.doi} without arxiv_id")
    elif rec.doi:
        got = crossref_work(rec.doi)
        title = (got[0].get("title") or [""])[0] if isinstance(got, tuple) else ""
        f, w = _remote(
            rec.id,
            f"DOI {rec.doi}",
            got,
            rec.title,
            rec.year,
            title,
            _cr_year(got[0]) if isinstance(got, tuple) else None,
        )
        fails, warns = fails + f, warns + w
    if rec.arxiv_id:
        got = arxiv_abs(rec.arxiv_id)
        title = (
            ((got[0].get("meta") or {}).get("citation_title") or [""])[0] if isinstance(got, tuple) else ""
        )
        f, w = _remote(rec.id, f"arXiv {rec.arxiv_id}", got, rec.title, None, title, None)
        fails, warns = fails + f, warns + w
    return fails, warns


def check_paths(paths: list[Path], *, online: bool) -> tuple[int, int, int, list[str]]:
    recs, msgs = [], []
    for path in paths:
        if not path.is_file():
            msgs.append(f"NOTE missing file: {path}")
            continue
        loaded, fails = _load_file(path)
        recs, msgs = recs + loaded, msgs + fails
    msgs.extend(_offline(recs))
    if online:
        for rec in recs:
            f, w = _online_one(rec)
            msgs.extend(f + w)
    n_fail = sum(1 for m in msgs if m.startswith("FAIL"))
    return len(recs), n_fail, sum(1 for m in msgs if m.startswith("WARN")), msgs


def _fake(*, provenance: bool) -> dict[str, object]:
    rec: dict[str, object] = {
        "id": "r-fake",
        "doi": "10.9999/fake.2026.001",
        "arxiv_id": "9912.99999",
        "title": "Fabricated example paper for the corpus canary",
        "authors": ["Fake, Author"],
        "year": 2026,
        "venue": "Journal of Imaginary Results",
        "type": "journal-article",
        "is_preprint": False,
        "published_version_of": None,
        "abstract": None,
        "url": "https://doi.org/10.9999/fake.2026.001",
        "oa": {"status": "unknown", "url": None, "license": None},
        "access_class": "unknown",
        "cluster": ["A"],
        "seed_id": None,
        "found_in": ["planted"],
        "queries": ["canary"],
        "cited_by_count": None,
        "retracted": False,
        "screening": None,
        "tier": None,
        "notes": "planted-fake canary",
        "provenance": [],
    }
    if provenance:
        rec["provenance"] = [
            {
                "source": "planted",
                "url": "https://example.invalid/fake",
                "retrieved_utc": "2026-10-04T00:00:00Z",
            }
        ]
    return rec


def planted_fake_test() -> int:
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "fake.jsonl"
        path.write_text(json.dumps(_fake(provenance=False)) + "\n", encoding="utf-8")
        _n, f, _w, msgs = check_paths([path], online=False)
        print("\n".join(msgs))
        if f == 0:
            print("planted-fake-test: FAIL (offline missing provenance was not caught)")
            return 1
        print("planted-fake offline: FAIL caught (missing provenance) as required")
        path.write_text(json.dumps(_fake(provenance=True)) + "\n", encoding="utf-8")
        _n, f, w, msgs = check_paths([path], online=True)
        print("\n".join(msgs))
        if f == 0:
            print(
                "planted-fake-test: FAIL ("
                + ("inconclusive (source unavailable)" if w else "online 404 not caught")
                + ")"
            )
            return 1
        print("planted-fake online: FAIL caught (DOI does not resolve) as required")
    print("planted-fake-test: PASS")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="check_corpus.py")
    p.add_argument("--records", action="append", type=Path)
    p.add_argument("--online", action="store_true")
    p.add_argument("--planted-fake-test", action="store_true")
    p.add_argument("--capability", action="store_true")
    args = p.parse_args(argv)
    if args.capability:
        return capability()
    if args.planted_fake_test:
        return planted_fake_test()
    n, f, w, msgs = check_paths(args.records or [DEFAULT], online=args.online)
    print("\n".join(msgs))
    print(f"corpus: {n} records, {f} fail, {w} warn")
    return 1 if f else 0


if __name__ == "__main__":
    sys.exit(main())
