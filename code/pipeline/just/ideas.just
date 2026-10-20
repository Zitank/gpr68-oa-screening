# Idea registry. Imported by the root justfile; recipe names stay unique.

idea text:
    uv run python tools/ideas.py add "{{text}}"

ideas *args:
    uv run python tools/ideas.py list {{args}}

speculate topic:
    uv run python tools/ideas.py speculate "{{topic}}"

triage-ideas:
    uv run python tools/ideas.py triage

idea-promote id as:
    uv run python tools/ideas.py promote {{id}} --as {{as}}

ideas-digest study:
    uv run python tools/ideas.py digest {{study}}

future-map:
    uv run python tools/ideas.py future-map

lint-tags:
    uv run python tools/lint_tags.py
