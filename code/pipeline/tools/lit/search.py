"""CLI: search cluster queries; update re-runs with --since last run."""

from __future__ import annotations

import argparse
import time
import urllib.parse
from pathlib import Path
from typing import Any

import yaml

from tools.lit import SourceUnavailable, _get
from tools.lit.dedupe import keys_of
from tools.lit.schema import Provenance, Record, dump_records, load_records, next_record_id
from tools.lit.sources import (
    _ABS_ID,
    arxiv_abs,
    crossref_search,
    openalex_search,
    record_from_arxiv,
    record_from_crossref,
    record_from_openalex,
)

ROOT = Path(__file__).resolve().parents[2]
QUERIES = ROOT / "literature" / "queries"
CORPUS = ROOT / "literature" / "corpus" / "records.jsonl"


def _utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected mapping")
    return data


def _arxiv_search(query: str, rows: int) -> tuple[dict[str, Any], Provenance] | SourceUnavailable:
    q = urllib.parse.urlencode({"searchtype": "all", "query": query, "size": str(min(rows, 200))})
    got = _get("https://arxiv.org/search/?" + q, "arxiv", throttle=False)
    if isinstance(got, SourceUnavailable):
        return got
    ids = list(dict.fromkeys(_ABS_ID.findall(got[0].decode("utf-8", "replace"))))[:rows]
    return {"arxiv_ids": ids, "query": query}, got[1]


def _run_source(
    source: str, query: str, rows: int, since: str | None
) -> tuple[list[dict[str, Any]], Provenance] | SourceUnavailable:
    filt = None
    if since and source == "crossref":
        filt = f"from-created-date:{since}"
    elif since and source == "openalex":
        filt = f"from_created_date:{since}"
    if source == "crossref":
        got = crossref_search(query, rows, filter=filt)
        if isinstance(got, SourceUnavailable):
            return got
        msg, prov = got
        return list(msg.get("items") or []), prov
    if source == "openalex":
        got = openalex_search(query, rows, filter=filt)
        if isinstance(got, SourceUnavailable):
            return got
        data, prov = got
        return list(data.get("results") or []), prov
    if source == "arxiv":
        got = _arxiv_search(query, rows)
        if isinstance(got, SourceUnavailable):
            return got
        payload, prov = got
        return [{"arxiv_id": i} for i in payload.get("arxiv_ids") or []], prov
    return SourceUnavailable(source, "unknown source")


def _to_record(
    source: str, item: dict[str, Any], rec_id: str, qid: str, prov: Provenance
) -> Record | SourceUnavailable:
    if source == "crossref":
        return record_from_crossref(item, rec_id=rec_id, prov=prov, query_id=qid)
    if source == "openalex":
        return record_from_openalex(item, rec_id=rec_id, prov=prov, query_id=qid)
    got = arxiv_abs(item["arxiv_id"])
    if isinstance(got, SourceUnavailable):
        return got
    payload, abs_prov = got
    return record_from_arxiv(payload, rec_id=rec_id, prov=abs_prov, query_id=qid)


def _append_run(data: dict[str, Any], qid: str, src: str, n_ret: int, n_new: int, note: str | None) -> None:
    row: dict[str, Any] = {
        "query_id": qid,
        "date_utc": _utc(),
        "source": src,
        "n_returned": n_ret,
        "n_new": n_new,
    }
    if note:
        row["note"] = note
    data.setdefault("runs", []).append(row)


def search_cluster(cluster: str, *, source: str | None, rows: int, since: str | None) -> dict[str, int]:
    path = QUERIES / f"{cluster}.yaml"
    data = _load_yaml(path)
    records = load_records(CORPUS) if CORPUS.is_file() else []
    seen: set[str] = set()
    for rec in records:
        seen.update(keys_of(rec))
    totals = {"returned": 0, "new": 0, "unavailable": 0}
    for q in data.get("queries") or []:
        sources = [s for s in (q.get("sources") or []) if source is None or s == source]
        for src in sources:
            _search_one(q["id"], q["string"], src, rows, since, cluster, records, seen, totals, data)
    dump_records(records, CORPUS)
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    print(
        f"search {cluster}: returned={totals['returned']} "
        f"new={totals['new']} unavailable={totals['unavailable']}"
    )
    return totals


def _search_one(
    qid: str,
    string: str,
    src: str,
    rows: int,
    since: str | None,
    cluster: str,
    records: list[Record],
    seen: set[str],
    totals: dict[str, int],
    data: dict[str, Any],
) -> None:
    got = _run_source(src, string, rows, since)
    if isinstance(got, SourceUnavailable):
        totals["unavailable"] += 1
        print(f"UNAVAILABLE {qid} {src}: {got.reason}")
        _append_run(data, qid, src, 0, 0, got.reason)
        return
    items, prov = got
    n_new = 0
    for item in items:
        totals["returned"] += 1
        rec = _to_record(src, item, next_record_id(records), qid, prov)
        if isinstance(rec, SourceUnavailable):
            totals["unavailable"] += 1
            continue
        rec = rec.model_copy(update={"cluster": sorted(set(rec.cluster) | {cluster})})
        ks = keys_of(rec)
        if seen.intersection(ks):
            continue
        records.append(rec)
        seen.update(ks)
        n_new += 1
        totals["new"] += 1
    _append_run(data, qid, src, len(items), n_new, None)


def update_all() -> int:
    total_new = 0
    for path in sorted(QUERIES.glob("*.yaml")):
        data = _load_yaml(path)
        dates = [str(r.get("date_utc", ""))[:10] for r in data.get("runs") or [] if r.get("date_utc")]
        since = max(dates) if dates else None
        print(f"# {path.stem} since={since or 'none'}")
        total_new += search_cluster(path.stem, source=None, rows=50, since=since)["new"]
    print(f"lit-update digest: {total_new} new (inbox only; no promotion)")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="tools.lit.search")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("search")
    s.add_argument("--cluster", required=True)
    s.add_argument("--source", choices=["crossref", "openalex", "arxiv"])
    s.add_argument("--rows", type=int, default=50)
    s.add_argument("--since")
    sub.add_parser("update")
    args = p.parse_args(argv)
    if args.cmd == "update":
        return update_all()
    search_cluster(args.cluster, source=args.source, rows=args.rows, since=args.since)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
