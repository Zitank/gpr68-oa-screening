# Literature L0 commands. Root justfile imports this file.

lit-capability:
    uv run python tools/check_corpus.py --capability

lit-search cluster:
    uv run python -m tools.lit.search search --cluster {{cluster}}

lit-dedupe:
    uv run python -m tools.lit.dedupe

lit-corpus-check:
    uv run python tools/check_corpus.py --records literature/corpus/records.jsonl --records literature/corpus/seed_records.jsonl

lit-corpus-check-online:
    uv run python tools/check_corpus.py --online --records literature/corpus/records.jsonl --records literature/corpus/seed_records.jsonl

lit-prisma:
    uv run python -m tools.lit.prisma --write

# Optional vault layer. Default is a sibling folder: ../vault/tools/fetch_arxiv.py
# Override: LIT_FETCH=/path/to/fetch_arxiv.py just lit-fetch <arxiv_id> <citekey>
lit-fetch id key:
    script="${LIT_FETCH:-../vault/tools/fetch_arxiv.py}"; test -f "$script" || { echo "lit-fetch: $script not found. Copy research-kit/vault next to this repo, or set LIT_FETCH." >&2; exit 1; }; python3 "$script" "{{id}}" "{{key}}" --bib

lit-update:
    uv run python -m tools.lit.search update
