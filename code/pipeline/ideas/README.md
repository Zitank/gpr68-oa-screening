# Idea registry

Append-only log: `ideas/events.jsonl`. Cards (`ideas/cards/`) and `INDEX.md` are a view (`ideas.py render`). A hand edit is kept with `ingest <id>`. Frontmatter is a small YAML subset parsed by `ideas.py` (not PyYAML).

## Types

`T` speculation, `I` improvement, `E` extension, `C` concern, `N` negative.

## Status

`untested` → `queued` → `pilot` → `supported` | `contradicted` | `retired`.

The `status` command refuses to leave `untested` until "What would falsify it" is non-empty.

## Evidence

`speculative` < `mechanism-argued` < `literature-supported` < `pilot-supported` < `preregistered-supported`.

Non-human `--by` cannot set evidence above `mechanism-argued`. `literature-supported` needs a citekey; `pilot-supported` needs a UUID run id.

## Commands

`just idea "text"` · `just ideas` · `just speculate "topic"` · `just triage-ideas` · `just idea-promote <id> <question|study>` · `just ideas-digest <study>` · `just future-map` · `just lint-tags`

`speculate` prints the Scout prompt and does not call an LLM (later: DeepSeek via `dispatch_coder`). Feed results back with `ideas.py add "<text>" --by scout`.
