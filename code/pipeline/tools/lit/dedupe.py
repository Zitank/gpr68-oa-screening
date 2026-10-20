"""Dedupe corpus records: doi → arxiv_id → norm(title)+first-author-family+year."""

from __future__ import annotations

import argparse
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

from tools.lit.schema import Record, dump_records, load_records

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RECORDS = ROOT / "literature" / "corpus" / "records.jsonl"


def norm_text(s: str) -> str:
    t = unicodedata.normalize("NFKC", s).casefold()
    t = t.replace("\u2019", "'").replace("\u2018", "'").replace("\u201c", '"').replace("\u201d", '"')
    t = re.sub(r"[^\w\s]", " ", t)
    return " ".join(t.split())


def title_key(rec: Record) -> str:
    family = rec.authors[0].split(",")[0].strip().casefold() if rec.authors else ""
    return f"{norm_text(rec.title)}|{family}|{rec.year or ''}"


def keys_of(rec: Record) -> list[str]:
    ks: list[str] = []
    if rec.doi:
        ks.append(f"doi:{rec.doi}")
    if rec.arxiv_id:
        ks.append(f"arxiv:{rec.arxiv_id}")
    if rec.title.strip():
        ks.append(f"t:{title_key(rec)}")
    if not ks:
        ks.append(f"id:{rec.id}")
    return ks


@dataclass
class DedupeReport:
    n_in: int
    n_out: int
    n_merged: int
    pairs: list[tuple[str, str]] = field(default_factory=list)

    def summary(self) -> str:
        return f"dedupe: {self.n_in} → {self.n_out} (merged {self.n_merged})"


def _merge_pair(a: Record, b: Record) -> Record:
    primary, secondary = a, b
    if a.is_preprint and not b.is_preprint:
        primary, secondary = b, a
    both_ids = bool((a.doi or b.doi) and (a.arxiv_id or b.arxiv_id))
    prov, seen = list(primary.provenance), {(p.source, p.url, p.retrieved_utc) for p in primary.provenance}
    for p in secondary.provenance:
        key = (p.source, p.url, p.retrieved_utc)
        if key not in seen:
            seen.add(key)
            prov.append(p)
    retracted: bool | None
    if primary.retracted is True or secondary.retracted is True:
        retracted = True
    elif primary.retracted is False or secondary.retracted is False:
        retracted = False
    else:
        retracted = None
    return primary.model_copy(
        update={
            "doi": primary.doi or secondary.doi,
            "arxiv_id": primary.arxiv_id or secondary.arxiv_id,
            "is_preprint": False if both_ids else primary.is_preprint and secondary.is_preprint,
            "published_version_of": None,
            "abstract": primary.abstract or secondary.abstract,
            "url": primary.url or secondary.url,
            "cluster": sorted(set(primary.cluster) | set(secondary.cluster)),
            "seed_id": primary.seed_id or secondary.seed_id,
            "found_in": sorted(set(primary.found_in) | set(secondary.found_in)),
            "queries": sorted(set(primary.queries) | set(secondary.queries)),
            "cited_by_count": max(
                (x for x in (primary.cited_by_count, secondary.cited_by_count) if x is not None),
                default=None,
            ),
            "retracted": retracted,
            "provenance": prov,
            "notes": " ".join(x for x in (primary.notes, secondary.notes) if x).strip(),
        }
    )


def _merge_group(group: list[Record]) -> Record:
    acc = group[0]
    for other in group[1:]:
        acc = _merge_pair(acc, other)
    return acc


def dedupe(records: list[Record]) -> tuple[list[Record], DedupeReport]:
    parent = list(range(len(records)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    index: dict[str, int] = {}
    pairs: list[tuple[str, str]] = []
    for i, rec in enumerate(records):
        for k in keys_of(rec):
            if k in index:
                j = find(index[k])
                ri = find(i)
                if ri != j:
                    parent[ri] = j
                    pairs.append((records[j].id, rec.id))
            else:
                index[k] = i
    groups: dict[int, list[Record]] = {}
    for i, rec in enumerate(records):
        groups.setdefault(find(i), []).append(rec)
    merged = [_merge_group(g) for g in groups.values()]
    n_merged = sum(len(g) - 1 for g in groups.values())
    return merged, DedupeReport(len(records), len(merged), n_merged, pairs)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="tools.lit.dedupe")
    p.add_argument("--records", type=Path, default=DEFAULT_RECORDS)
    args = p.parse_args(argv)
    if not args.records.is_file():
        print(f"NOTE missing file: {args.records}")
        return 0
    merged, report = dedupe(load_records(args.records))
    dump_records(merged, args.records)
    print(report.summary())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
