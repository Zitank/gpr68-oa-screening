"""PRISMA-lite counts → Markdown; --write patches PROTOCOL.md markers."""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path

from tools.lit import _ua
from tools.lit.schema import Record, load_records

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = ROOT / "literature" / "PROTOCOL.md"
DEFAULT_RECORDS = ROOT / "literature" / "corpus" / "records.jsonl"
START = "<!-- prisma:start -->"
END = "<!-- prisma:end -->"


def _tally(records: list[Record]) -> tuple[Counter[str], Counter[str], Counter[str], int]:
    identified: Counter[str] = Counter()
    excluded: Counter[str] = Counter()
    retained: Counter[str] = Counter()
    screened = 0
    for rec in records:
        identified.update(rec.found_in)
        if rec.screening is None:
            continue
        screened += 1
        if rec.screening.decision == "exclude":
            excluded[rec.screening.code] += 1
        elif rec.screening.decision == "include":
            retained[f"T{rec.tier}" if rec.tier else "T?"] += 1
    return identified, excluded, retained, screened


def prisma_counts(records: list[Record]) -> dict[str, int]:
    identified, excluded, retained, screened = _tally(records)
    out: dict[str, int] = {}
    for src in sorted(identified) or ["crossref", "openalex", "arxiv"]:
        out[f"identified:{src}"] = identified.get(src, 0)
    out["deduped"] = len(records)
    out["screened"] = screened
    for code in ["E1", "E2", "E3", "E4", "E5"]:
        out[f"excluded:{code}"] = excluded.get(code, 0)
    for extra in excluded:
        if f"excluded:{extra}" not in out:
            out[f"excluded:{extra}"] = excluded[extra]
    for tier in ["T1", "T2", "T3", "T4", "T?"]:
        out[f"retained:{tier}"] = retained.get(tier, 0)
    return out


def to_markdown(counts: dict[str, int]) -> str:
    lines = ["| stage | n |", "| --- | ---: |"]
    for k, v in counts.items():
        lines.append(f"| {k} | {v} |")
    return "\n".join(lines) + "\n"


def write_protocol(md: str, path: Path = PROTOCOL) -> None:
    text = path.read_text(encoding="utf-8")
    i, j = text.find(START), text.find(END)
    if i < 0 or j < 0 or j < i:
        raise ValueError(f"{path}: missing {START} / {END} markers")
    path.write_text(text[: i + len(START)] + "\n" + md + text[j:], encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="tools.lit.prisma")
    p.add_argument("--records", type=Path, default=DEFAULT_RECORDS)
    p.add_argument("--write", action="store_true")
    args = p.parse_args(argv)
    recs: list[Record] = []
    if args.records.is_file():
        recs = load_records(args.records)
    else:
        print(f"NOTE missing file: {args.records}")
    md = to_markdown(prisma_counts(recs))
    print(md, end="")
    if args.write:
        write_protocol(md)
        print(f"wrote PRISMA-lite into {PROTOCOL}")
    return 0


def _header_notes(headers: object) -> str:
    keys = (
        "retry-after",
        "x-rate-limit-limit",
        "x-rate-limit-interval",
        "x-rate-limit-remaining",
        "x-ratelimit-limit",
        "x-ratelimit-remaining",
        "warning",
    )
    get = getattr(headers, "get", None) if headers is not None else None
    if get is None:
        return "(no headers)"
    bits = [f"{k}={get(k)}" for k in keys if get(k)]
    return "; ".join(bits) if bits else "(no rate-limit headers in response)"


def _probe(name: str, url: str) -> tuple[str, str, int, str, str, bytes | None]:
    t0, date, body = time.monotonic(), time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), None
    try:
        req = urllib.request.Request(url, headers=_ua())
        with urllib.request.urlopen(req, timeout=20) as resp:
            body, status, notes = resp.read(), str(resp.status), _header_notes(resp.headers)
    except urllib.error.HTTPError as exc:
        body, status, notes = exc.read(), str(exc.code), _header_notes(exc.headers)
    except TimeoutError:
        status, notes = "timeout", "TimeoutError"
    except urllib.error.URLError as exc:
        status, notes = "error", str(getattr(exc, "reason", exc))
    return name, status, int((time.monotonic() - t0) * 1000), date, notes, body


def capability() -> int:
    doi = "10.1038/nature14539"
    rows = [
        _probe("Crossref works", f"https://api.crossref.org/works/{doi}"),
        _probe("Crossref search", "https://api.crossref.org/works?query.bibliographic=deep+learning&rows=1"),
        _probe("OpenAlex work", f"https://api.openalex.org/works/https://doi.org/{doi}"),
        _probe("OpenAlex search", "https://api.openalex.org/works?search=deep%20learning&per-page=1"),
    ]
    cited = "https://api.openalex.org/works?filter=cites:unverified&per-page=1"
    if rows[2][1] == "200" and rows[2][5]:
        try:
            wid = json.loads(rows[2][5].decode("utf-8")).get("id")
            if isinstance(wid, str) and wid:
                cited = "https://api.openalex.org/works?filter=cites:" + wid + "&per-page=1"
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass
    rows += [
        _probe("OpenAlex cited_by", cited),
        _probe("arXiv abs", "https://arxiv.org/abs/1706.03762"),
        _probe("Semantic Scholar", f"https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}"),
        _probe("Google Scholar", "https://scholar.google.com/scholar?q=deep+learning"),
        _probe(
            "export.arxiv.org API", "https://export.arxiv.org/api/query?search_query=all:test&max_results=1"
        ),
    ]
    print("| endpoint | HTTP status | latency_ms | date_utc | header_notes |")
    print("| --- | --- | ---: | --- | --- |")
    for name, status, ms, date, notes, _b in rows:
        print(f"| {name} | {status} | {ms} | {date} | {notes} |")
    print(
        "unverified: terms of use beyond response headers; "
        "OpenAlex TLS intermittency not sampled beyond this run."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
