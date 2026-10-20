# Corpus record schema (v1) — owned by the Architect

One JSON object per line in `records.jsonl`. Every record MUST come from a retrieved API/web response; a record
without `provenance` is invalid and `tools/check_corpus.py` rejects it. No field is ever filled from memory:
unknown → `null`.

```json
{
  "id": "r-0001",
  "doi": "10.1000/example.1",
  "arxiv_id": "1706.03762",
  "title": "…",
  "authors": ["Doe, Jane"],
  "year": 2020,
  "venue": "Example Venue",
  "type": "journal-article",
  "is_preprint": false,
  "published_version_of": null,
  "abstract": "…",
  "url": "https://doi.org/10.1000/example.1",
  "oa": {"status": "gold", "url": null, "license": "cc-by"},
  "access_class": "oa-cc|oa-arxiv|oa-other|ieee-no-ai|paywalled-no-ai|unknown",
  "cluster": ["A"],
  "seed_id": null,
  "found_in": ["crossref", "arxiv"],
  "queries": ["A-q1"],
  "cited_by_count": null,
  "retracted": false,
  "provenance": [
    {"source": "crossref", "url": "https://api.crossref.org/works/10.1000/example.1", "retrieved_utc": "2026-01-01T00:00:00Z"}
  ],
  "screening": null,
  "tier": null,
  "notes": ""
}
```

Field notes:

- `doi`: lowercase, no URL prefix, or null.
- `arxiv_id`: without a version suffix, or null.
- `authors`: `"Family, Given"` as returned; may be truncated to 10 + `"et al."`.
- `type`: the source's type string, or null.
- `is_preprint`: true if only a preprint version is known.
- `published_version_of`: record id of the peer-reviewed twin if merged, or null.
- `abstract`: as returned, or null.
- `oa.status`: `diamond|gold|green|hybrid|bronze|closed|unknown`.
- `cluster`: ids from `literature/queries/`; may be empty before screening.
- `seed_id`: id from the project's seed list, else null.
- `queries`: query ids from `literature/queries/*.yaml`, or `seed:<id>`, `snowball:fwd:<id>`.
- `cited_by_count`: from OpenAlex or Semantic Scholar if present, else null.
- `screening`: filled at L3: `{"decision": "include|exclude", "code": "I1|E2|…", "reason": "…", "by": "librarian|human", "date": "…"}`.
- `tier`: 1..4 after L3.
- `notes`: free text; never a substitute for a field.

Dedupe key order: `doi` → `arxiv_id` → `norm(title) + first author family + year`. Merged preprint/published pairs keep
both ids on one record (`doi` + `arxiv_id`) with `is_preprint=false`.

`access_class`: IEEE Xplore full text and other paywalled text are **never** fetched, parsed, or reasoned over; only
metadata. OA text goes to the vault `sources/<key>.md` via the optional vault `tools/fetch_arxiv.py`, never into this
repo.

Citekey suggestion (`key_map.yaml`, created when you start a corpus): `<firstauthorfamily lower><year><first significant title word lower>`,
for example `smith2020example`. Final keys come from the human's reference manager.
