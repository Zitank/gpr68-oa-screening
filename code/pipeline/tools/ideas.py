"""Append-only idea registry. Cards and INDEX.md are a materialised view."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from core.errors import PipelineError

_ACTORS = frozenset({"human", "scout", "coder", "challenger", "literature"})
_STATUSES = frozenset({"untested", "queued", "pilot", "supported", "contradicted", "retired"})
_EVIDENCE = (
    "speculative",
    "mechanism-argued",
    "literature-supported",
    "pilot-supported",
    "preregistered-supported",
)
_PREFIX = {
    "SPECULATION": "T",
    "IMPROVEMENT": "I",
    "EXTENSION": "E",
    "CONCERN": "C",
    "NEGATIVE": "N",
}
_BY_PREFIX = {prefix: name for name, prefix in _PREFIX.items()}
_FORWARD: dict[str, frozenset[str]] = {
    "untested": frozenset({"queued"}),
    "queued": frozenset({"pilot"}),
    "pilot": frozenset({"supported", "contradicted"}),
    "supported": frozenset(),
    "contradicted": frozenset(),
    "retired": frozenset(),
}
_EVENTS = frozenset({"created", "edited", "status_changed", "linked", "promoted", "triaged"})
_EDITABLE = (
    "type",
    "status",
    "evidence",
    "origin",
    "study",
    "question",
    "grounding",
    "statement",
    "why",
    "falsify",
    "cheapest",
    "change",
    "notes",
)
_SECTIONS = (
    ("statement", "Statement (one or two sentences)"),
    ("why", "Why it might be true (mechanism)"),
    ("falsify", "What would falsify it (REQUIRED to leave `untested` → `queued`)"),
    ("cheapest", "Cheapest test"),
    ("change", "What it would change if true (which study, spec or component)"),
    ("notes", "Notes"),
)
_QUESTION_SECTIONS = (
    "Question (one sentence)",
    "Falsifiable form (what result would say no?)",
    "So what? If yes: ... / If no: ... / If null: ...",
    "Cheapest discriminating experiment",
    "Prior art (citekeys; closest three; search log link; novelty verdict by human)",
    "Pilot plan (time box, compute budget, data, what is measured)",
    "Kill criteria (written BEFORE the pilot)",
    "Dependencies / spawns",
    "Status log (dated, one line each)",
)
_STUDY_SECTIONS = (
    ("Milestones (each with a deliverable and an exit check)", "TBD (human)"),
    ("What this study teaches the programme", "TBD (human)"),
    ("Risks", "TBD (human)"),
)
_RUN_ID = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
_CITEKEY = re.compile(r"^[A-Za-z][A-Za-z0-9_:.+-]*$")
_HEADING = re.compile(r"^## (.+)$", re.MULTILINE)
_SAFE = re.compile(r"[A-Za-z0-9_./+-]+")


class IdeaError(PipelineError):
    """The idea registry rejected a command."""


@dataclass
class Idea:
    id: str
    type: str
    status: str
    evidence: str
    origin: str
    study: str | None
    question: str | None
    grounding: list[str]
    created: str
    statement: str
    why: str
    falsify: str
    cheapest: str
    change: str
    notes: str
    triage: str | None = None
    promoted_as: str | None = None
    promoted_target: str | None = None


def _events_path(root: Path) -> Path:
    return root / "ideas" / "events.jsonl"


def _now(moment: datetime | None = None) -> str:
    when = moment if moment is not None else datetime.now(UTC)
    return when.strftime("%Y-%m-%dT%H:%M:%SZ")


def _event(
    kind: str, idea_id: str, by: str, data: dict[str, Any], *, when: datetime | None = None
) -> dict[str, Any]:
    return {"by": by, "data": data, "event": kind, "id": idea_id, "time_utc": _now(when)}


def _append(root: Path, event: dict[str, Any]) -> None:
    """Append one JSON line. The events file is never rewritten."""
    path = _events_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(event, ensure_ascii=False, sort_keys=True)
    if "\n" in line:
        raise IdeaError("event is not a single line")
    with path.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(line + "\n")


def _check_actor(by: str) -> str:
    if by not in _ACTORS:
        raise IdeaError(f"unknown by {by}")
    return by


def _resolve_type(token: str) -> str:
    key = token.strip()
    if key in _BY_PREFIX:
        return _BY_PREFIX[key]
    upper = key.upper()
    if upper in _BY_PREFIX:
        return _BY_PREFIX[upper]
    if upper in _PREFIX:
        return upper
    raise IdeaError(f"unknown type {token}")


def _classify(token: str) -> str:
    if _RUN_ID.fullmatch(token):
        return "run"
    if _CITEKEY.fullmatch(token):
        return "cite"
    raise IdeaError(f"{token} is neither a citekey nor a run id")


def _assert_evidence(evidence: str, by: str, grounding: list[str]) -> None:
    if evidence not in _EVIDENCE:
        raise IdeaError(f"unknown evidence {evidence}")
    _check_actor(by)
    kinds = {_classify(item) for item in grounding}
    rank = _EVIDENCE.index(evidence)
    if by != "human" and rank > _EVIDENCE.index("mechanism-argued"):
        raise IdeaError("non-human origin cannot set evidence above mechanism-argued")
    if evidence == "literature-supported" and "cite" not in kinds:
        raise IdeaError("literature-supported requires a citekey in grounding")
    if evidence == "pilot-supported" and "run" not in kinds:
        raise IdeaError("pilot-supported requires a run id in grounding")


def _status_allowed(old: str, new: str) -> bool:
    if new == "retired":
        return old != "retired"
    return new in _FORWARD[old]


def _require_falsify(old: str, new: str, falsify: str, *, enforce: bool) -> None:
    leaving = old == "untested" and new != "untested"
    if enforce and leaving and not falsify.strip():
        raise IdeaError("leaving untested requires a non-empty 'What would falsify it'")


def _opt_str(value: Any) -> str | None:
    if value is None or value == "":
        return None
    if isinstance(value, str):
        return value
    raise IdeaError(f"expected a string or null, got {value!r}")


def _str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return list(value)
    raise IdeaError(f"expected a list of strings, got {value!r}")


def _data(event: dict[str, Any], line_no: int) -> dict[str, Any]:
    raw = event.get("data")
    if isinstance(raw, dict):
        return raw
    raise IdeaError(f"events line {line_no}: data is not an object")


def _read_events(root: Path) -> list[tuple[int, dict[str, Any]]]:
    path = _events_path(root)
    if not path.is_file():
        return []
    rows: list[tuple[int, dict[str, Any]]] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if line.strip() == "":
            raise IdeaError(f"events line {number}: empty")
        rows.append((number, _parse_event(line, number)))
    return rows


def _parse_event(line: str, number: int) -> dict[str, Any]:
    try:
        obj = json.loads(line)
    except json.JSONDecodeError as exc:
        raise IdeaError(f"events line {number}: {exc}") from exc
    if not isinstance(obj, dict):
        raise IdeaError(f"events line {number}: not an object")
    missing = [key for key in ("event", "id", "time_utc", "by", "data") if key not in obj]
    if missing:
        raise IdeaError(f"events line {number}: missing {missing}")
    if obj["event"] not in _EVENTS:
        raise IdeaError(f"events line {number}: unknown event {obj['event']}")
    if obj["by"] not in _ACTORS:
        raise IdeaError(f"events line {number}: unknown by {obj['by']}")
    return obj


def _created_idea(event: dict[str, Any], line_no: int) -> Idea:
    data = _data(event, line_no)
    try:
        return Idea(
            id=str(event["id"]),
            type=str(data["type"]),
            status=str(data["status"]),
            evidence=str(data["evidence"]),
            origin=str(data["origin"]),
            study=_opt_str(data.get("study")),
            question=_opt_str(data.get("question")),
            grounding=_str_list(data.get("grounding")),
            created=str(data["created"]),
            statement=str(data["statement"]),
            why=str(data.get("why", "")),
            falsify=str(data.get("falsify", "")),
            cheapest=str(data.get("cheapest", "")),
            change=str(data.get("change", "")),
            notes=str(data.get("notes", "")),
        )
    except KeyError as exc:
        raise IdeaError(f"events line {line_no}: created event missing {exc}") from exc


def _apply_data(idea: Idea, data: dict[str, Any]) -> None:
    for key in _EDITABLE:
        if key not in data:
            continue
        setattr(idea, key, _coerce_field(idea.id, key, data[key]))


def _coerce_field(idea_id: str, key: str, value: Any) -> Any:
    if key in {"study", "question"}:
        return _opt_str(value)
    if key == "grounding":
        return _str_list(value)
    if isinstance(value, str):
        return value
    raise IdeaError(f"{idea_id}: field {key} must be a string")


def _apply(ideas: dict[str, Idea], event: dict[str, Any], line_no: int) -> None:
    kind = str(event["event"])
    idea_id = str(event["id"])
    if kind == "created":
        ideas[idea_id] = _created_idea(event, line_no)
        return
    if idea_id not in ideas:
        raise IdeaError(f"events line {line_no}: {kind} for unknown id {idea_id}")
    idea = ideas[idea_id]
    data = _data(event, line_no)
    if kind == "edited":
        _apply_data(idea, data)
    elif kind == "status_changed":
        idea.status = str(data["status"])
    elif kind == "linked":
        _link_token(idea, str(data["grounding"]))
    elif kind == "promoted":
        idea.promoted_as = str(data["as"])
        idea.promoted_target = str(data["target"])
    elif kind == "triaged":
        idea.triage = str(data["decision"])
    else:
        raise IdeaError(f"events line {line_no}: unknown event {kind}")


def _link_token(idea: Idea, token: str) -> None:
    _classify(token)
    if token not in idea.grounding:
        idea.grounding.append(token)


def load_ideas(root: Path) -> dict[str, Idea]:
    ideas: dict[str, Idea] = {}
    for line_no, event in _read_events(root):
        _apply(ideas, event, line_no)
    return ideas


def _require(root: Path, idea_id: str) -> Idea:
    ideas = load_ideas(root)
    if idea_id not in ideas:
        raise IdeaError(f"unknown idea {idea_id}")
    return ideas[idea_id]


def _id_key(idea_id: str) -> tuple[str, int]:
    prefix, _, number = idea_id.partition("-")
    return prefix, int(number)


def _next_id(ideas: dict[str, Idea], type_name: str) -> str:
    prefix = _PREFIX[type_name]
    nums = [_id_key(idea_id)[1] for idea_id in ideas if idea_id.startswith(prefix + "-")]
    return f"{prefix}-{max(nums, default=0) + 1:03d}"


def _quote(value: str) -> str:
    if _SAFE.fullmatch(value):
        return value
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _unquote(value: str) -> str:
    if len(value) < 2 or value[0] != value[-1] or value[0] not in {'"', "'"}:
        return value
    body = value[1:-1]
    if value[0] == "'":
        return body
    out: list[str] = []
    index = 0
    while index < len(body):
        if body[index] == "\\" and index + 1 < len(body):
            out.append(body[index + 1])
            index += 2
        else:
            out.append(body[index])
            index += 1
    return "".join(out)


def _scalar_value(value: str) -> Any:
    if value in {"null", "~"}:
        return None
    if value == "[]":
        return []
    if value.startswith("[") and value.endswith("]"):
        return _inline_list(value)
    return _unquote(value)


def _inline_list(value: str) -> list[str]:
    inner = value[1:-1].strip()
    if inner == "":
        return []
    return [_unquote(part.strip()) for part in inner.split(",")]


def _parse_items(lines: list[str], index: int) -> tuple[list[str], int]:
    items: list[str] = []
    while index < len(lines) and lines[index].startswith("  - "):
        items.append(_unquote(lines[index][4:].strip()))
        index += 1
    return items, index


def _parse_line(data: dict[str, Any], lines: list[str], index: int) -> int:
    line = lines[index]
    if not line.strip():
        return index + 1
    if line.startswith(("  - ", "\t- ")):
        raise IdeaError(f"list item outside a key: {line}")
    key, sep, rest = line.partition(":")
    if sep == "" or key != key.strip():
        raise IdeaError(f"bad frontmatter line: {line}")
    value = rest.strip()
    if value == "":
        items, index = _parse_items(lines, index + 1)
        data[key.strip()] = items if items else None
        return index
    data[key.strip()] = _scalar_value(value)
    return index + 1


def _parse_block(raw: str) -> dict[str, Any]:
    data: dict[str, Any] = {}
    lines = raw.splitlines()
    index = 0
    while index < len(lines):
        index = _parse_line(data, lines, index)
    return data


def _split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---\n"):
        raise IdeaError("card missing frontmatter")
    end = text.find("\n---\n", 4)
    if end == -1:
        raise IdeaError("card frontmatter not closed")
    return _parse_block(text[4:end]), text[end + 5 :]


def _section_key(title: str) -> str:
    for key, full in _SECTIONS:
        head = full.split(" (", 1)[0]
        if title == full or title == head:
            return key
    raise IdeaError(f"unknown section {title!r}")


def _sections(body: str) -> dict[str, str]:
    matches = list(_HEADING.finditer(body))
    found: dict[str, str] = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        found[_section_key(match.group(1).strip())] = body[match.end() : end].strip()
    missing = [key for key, _title in _SECTIONS if key not in found]
    if missing:
        raise IdeaError(f"card missing section {missing[0]}")
    return found


def _need_str(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if isinstance(value, str) and value != "":
        return value
    raise IdeaError(f"card field {key} must be a string")


def _idea_from_card(current: Idea, text: str) -> Idea:
    fm, body = _split_frontmatter(text)
    if fm.get("id") != current.id:
        raise IdeaError(f"card id is {fm.get('id')!r}, expected {current.id}")
    created = fm.get("created")
    if created is not None and str(created) != current.created:
        raise IdeaError("created is immutable")
    for key in ("study", "question", "grounding"):
        if key not in fm:
            raise IdeaError(f"card missing {key}")
    sections = _sections(body)
    return Idea(
        id=current.id,
        type=_need_str(fm, "type"),
        status=_need_str(fm, "status"),
        evidence=_need_str(fm, "evidence"),
        origin=_need_str(fm, "origin"),
        study=_opt_str(fm["study"]),
        question=_opt_str(fm["question"]),
        grounding=_str_list(fm["grounding"]),
        created=current.created,
        statement=sections["statement"],
        why=sections["why"],
        falsify=sections["falsify"],
        cheapest=sections["cheapest"],
        change=sections["change"],
        notes=sections["notes"],
        triage=current.triage,
        promoted_as=current.promoted_as,
        promoted_target=current.promoted_target,
    )


def _check_identity(idea: Idea) -> None:
    if idea.type not in _PREFIX:
        raise IdeaError(f"unknown type {idea.type}")
    if idea.status not in _STATUSES:
        raise IdeaError(f"unknown status {idea.status}")
    if idea.origin not in _ACTORS:
        raise IdeaError(f"unknown origin {idea.origin}")


def _check_edit(old: Idea, new: Idea) -> None:
    _check_identity(new)
    _assert_evidence(new.evidence, "human", new.grounding)
    if old.status == new.status:
        return
    if not _status_allowed(old.status, new.status):
        raise IdeaError(f"cannot change status {old.status} to {new.status}")
    _require_falsify(old.status, new.status, new.falsify, enforce=True)


def _diff(old: Idea, new: Idea) -> dict[str, Any]:
    changed: dict[str, Any] = {}
    for key in _EDITABLE:
        before = getattr(old, key)
        after = getattr(new, key)
        if before != after:
            changed[key] = after
    return changed


def _frontmatter(idea: Idea) -> str:
    lines = [
        "---",
        f"id: {idea.id}",
        f"type: {idea.type}",
        f"status: {idea.status}",
        f"evidence: {idea.evidence}",
        f"origin: {idea.origin}",
        f"study: {_quote(idea.study) if idea.study else 'null'}",
        f"question: {_quote(idea.question) if idea.question else 'null'}",
    ]
    lines.extend(_grounding_lines(idea.grounding))
    lines.append(f"created: {idea.created}")
    lines.append("---")
    return "\n".join(lines)


def _grounding_lines(items: list[str]) -> list[str]:
    if not items:
        return ["grounding: []"]
    return ["grounding:", *[f"  - {_quote(item)}" for item in items]]


def _card_text(idea: Idea) -> str:
    chunks = [_frontmatter(idea), ""]
    if idea.origin != "human" and idea.triage is None:
        chunks.extend(["> agent-proposed, unreviewed", ""])
    if idea.promoted_target:
        chunks.extend([f"> promoted: {idea.promoted_as} {idea.promoted_target}", ""])
    for key, title in _SECTIONS:
        chunks.extend([f"## {title}", ""])
        body = str(getattr(idea, key))
        if body:
            chunks.extend([body, ""])
    return "\n".join(chunks).rstrip() + "\n"


def _cell(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(value.replace("|", "\\|").split())


def _origin_cell(idea: Idea) -> str:
    if idea.origin != "human" and idea.triage is None:
        return f"{idea.origin} unreviewed"
    return idea.origin


def _index_row(idea: Idea) -> str:
    cells = [
        f"[{idea.id}](cards/{idea.id}.md)",
        idea.type,
        idea.status,
        idea.evidence,
        _origin_cell(idea),
        _cell(idea.study),
        _cell(idea.question),
        _cell(idea.statement),
    ]
    return "| " + " | ".join(cells) + " |"


def _index(ideas: dict[str, Idea]) -> str:
    lines = [
        "# Ideas",
        "",
        "| ID | Type | Status | Evidence | Origin | Study | Question | Statement |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    ordered = sorted(ideas.values(), key=lambda item: _id_key(item.id))
    lines.extend(_index_row(idea) for idea in ordered)
    return "\n".join(lines) + "\n"


def _render_all(root: Path) -> int:
    ideas = load_ideas(root)
    cards = root / "ideas" / "cards"
    cards.mkdir(parents=True, exist_ok=True)
    for idea in ideas.values():
        (cards / f"{idea.id}.md").write_text(_card_text(idea), encoding="utf-8")
    (root / "ideas" / "INDEX.md").write_text(_index(ideas), encoding="utf-8")
    return len(ideas)


def _list_line(idea: Idea) -> str:
    statement = " ".join(idea.statement.split())
    return f"{idea.id}  {idea.type}  {idea.status}  {idea.evidence}  {_origin_cell(idea)}  {statement}"


def _cmd_add(args: argparse.Namespace) -> int:
    by = _check_actor(str(args.by))
    type_name = _resolve_type(str(args.type_name))
    statement = str(args.text).strip()
    if statement == "":
        raise IdeaError("idea text is empty")
    evidence = str(args.evidence)
    _assert_evidence(evidence, by, [])
    moment = datetime.now(UTC)
    file_ref = args.file if isinstance(args.file, str) else None
    data: dict[str, Any] = {
        "change": "",
        "cheapest": "",
        "created": moment.strftime("%Y-%m-%d"),
        "evidence": evidence,
        "falsify": "",
        "file": file_ref,
        "grounding": [],
        "notes": f"file: {file_ref}" if file_ref else "",
        "origin": by,
        "question": args.q,
        "statement": statement,
        "status": "untested",
        "study": args.study,
        "type": type_name,
        "why": "",
    }
    new_id = _next_id(load_ideas(args.root), type_name)
    _append(args.root, _event("created", new_id, by, data, when=moment))
    _render_all(args.root)
    print(new_id)
    return 0


def _selected(idea: Idea, study: str | None, status: str | None, type_name: str | None) -> bool:
    if study is not None and idea.study != study:
        return False
    if status is not None and idea.status != status:
        return False
    return type_name is None or idea.type == type_name


def _cmd_list(args: argparse.Namespace) -> int:
    if args.status is not None and args.status not in _STATUSES:
        raise IdeaError(f"unknown status {args.status}")
    type_name = _resolve_type(str(args.type_name)) if args.type_name else None
    ideas = load_ideas(args.root)
    ordered = sorted(ideas.values(), key=lambda item: _id_key(item.id))
    for idea in ordered:
        if _selected(idea, args.study, args.status, type_name):
            print(_list_line(idea))
    return 0


def _change_status(root: Path, idea: Idea, new: str, by: str, *, enforce_falsify: bool) -> None:
    if new not in _STATUSES:
        raise IdeaError(f"unknown status {new}")
    if new == idea.status:
        raise IdeaError(f"status is already {new}")
    if not _status_allowed(idea.status, new):
        raise IdeaError(f"cannot change status {idea.status} to {new}")
    _require_falsify(idea.status, new, idea.falsify, enforce=enforce_falsify)
    payload = {"from": idea.status, "status": new}
    _append(root, _event("status_changed", idea.id, by, payload))


def _cmd_status(args: argparse.Namespace) -> int:
    by = _check_actor(str(args.by))
    idea = _require(args.root, str(args.id))
    _change_status(args.root, idea, str(args.new), by, enforce_falsify=True)
    _render_all(args.root)
    print(f"{idea.id} {args.new}")
    return 0


def _cmd_link(args: argparse.Namespace) -> int:
    by = _check_actor(str(args.by))
    idea = _require(args.root, str(args.id))
    token = str(args.grounding)
    _classify(token)
    if token in idea.grounding:
        raise IdeaError(f"{idea.id} already links {token}")
    _append(args.root, _event("linked", idea.id, by, {"grounding": token}))
    _render_all(args.root)
    print(f"{idea.id} {token}")
    return 0


def _cmd_render(args: argparse.Namespace) -> int:
    print(f"rendered {_render_all(args.root)}")
    return 0


def _cmd_ingest(args: argparse.Namespace) -> int:
    current = _require(args.root, str(args.id))
    path = args.root / "ideas" / "cards" / f"{current.id}.md"
    if not path.is_file():
        raise IdeaError(f"card not found: {path}")
    updated = _idea_from_card(current, path.read_text(encoding="utf-8"))
    _check_edit(current, updated)
    changed = _diff(current, updated)
    if not changed:
        print(f"{current.id} unchanged")
    else:
        _append(args.root, _event("edited", current.id, "human", changed))
        print(f"{current.id} edited")
    _render_all(args.root)
    return 0


def _ask(idea: Idea) -> str:
    print(f"{idea.id} [{idea.origin}] {idea.statement}")
    choice = input("keep, retire, or promote? ").strip()
    if choice not in {"keep", "retire", "promote"}:
        raise IdeaError(f"unknown triage decision {choice}")
    return choice


def _parse_decisions(raw: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    if raw.strip() == "":
        return parsed
    for part in raw.split(","):
        if "=" not in part:
            raise IdeaError(f"bad decision {part}")
        idea_id, _, choice = part.partition("=")
        choice = choice.strip()
        if choice not in {"keep", "retire", "promote"}:
            raise IdeaError(f"unknown triage decision {choice}")
        parsed[idea_id.strip()] = choice
    return parsed


def _decisions(raw: str | None, pending: list[Idea]) -> dict[str, str]:
    if raw is None:
        return _interactive_decisions(pending)
    parsed = _parse_decisions(raw)
    pending_ids = {idea.id for idea in pending}
    missing = [idea.id for idea in pending if idea.id not in parsed]
    extra = [idea_id for idea_id in parsed if idea_id not in pending_ids]
    if missing or extra:
        raise IdeaError(f"triage decisions do not match pending: missing {missing} extra {extra}")
    return parsed


def _interactive_decisions(pending: list[Idea]) -> dict[str, str]:
    if not pending:
        return {}
    if not sys.stdin.isatty():
        raise IdeaError("triage needs a TTY or --decisions id=keep|retire|promote,...")
    return {idea.id: _ask(idea) for idea in pending}


def _pending(ideas: dict[str, Idea]) -> list[Idea]:
    rows = [idea for idea in ideas.values() if idea.origin != "human" and idea.triage is None]
    return sorted(rows, key=lambda item: _id_key(item.id))


def _apply_triage(root: Path, idea: Idea, decision: str, by: str) -> None:
    if decision == "retire":
        _change_status(root, idea, "retired", by, enforce_falsify=False)
    _append(root, _event("triaged", idea.id, by, {"decision": decision}))


def _cmd_triage(args: argparse.Namespace) -> int:
    by = _check_actor(str(args.by))
    ideas = load_ideas(args.root)
    pending = _pending(ideas)
    decisions = _decisions(args.decisions, pending)
    for idea in pending:
        _apply_triage(args.root, idea, decisions[idea.id], by)
        print(f"{idea.id} {decisions[idea.id]}")
    if pending:
        _render_all(args.root)
    print(f"triaged {len(pending)}")
    return 0


def _next_question_number(folder: Path) -> int:
    nums: list[int] = []
    for path in folder.glob("Q-*.md"):
        match = re.fullmatch(r"Q-(\d+)(?:-.+)?", path.stem)
        if match:
            nums.append(int(match.group(1)))
    return max(nums, default=0) + 1


def _exclusive(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8") as fh:
            fh.write(text)
    except FileExistsError as exc:
        raise IdeaError(f"refusing to overwrite {path}") from exc


def _question_text(qid: str, title: str) -> str:
    lines = ["---", f"id: {qid}", "state: SEED", f"title: {_quote(title)}", "---", ""]
    for section in _QUESTION_SECTIONS:
        lines.extend([f"## {section}", "", "TBD (human)", ""])
    return "\n".join(lines)


def _write_question(root: Path, idea: Idea) -> tuple[str, Path]:
    folder = root / "governance" / "questions"
    folder.mkdir(parents=True, exist_ok=True)
    qid = f"Q-{_next_question_number(folder):03d}"
    path = folder / f"{qid}.md"
    _exclusive(path, _question_text(qid, " ".join(idea.statement.split())))
    return qid, path


def _slug(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:48].strip("-") or "idea"


def _next_study_number(folder: Path) -> int:
    nums: list[int] = []
    if not folder.is_dir():
        return 1
    for path in folder.iterdir():
        match = re.match(r"S(\d+)", path.name) if path.is_dir() else None
        if match:
            nums.append(int(match.group(1)))
    return max(nums, default=0) + 1


def _study_text(sid: str, idea: Idea) -> str:
    title = " ".join(idea.statement.split())
    lines = [
        "---",
        f"id: {sid}",
        f"title: {_quote(title)}",
        "state: PLANNED",
        'standalone_claim: "TBD (human)"',
        "---",
        "",
    ]
    for section, body in _STUDY_SECTIONS:
        lines.extend([f"## {section}", "", body, ""])
    lines.extend(["## Linked ideas (generated from ideas/)", "", idea.id, ""])
    return "\n".join(lines)


def _write_study(root: Path, idea: Idea) -> tuple[str, Path]:
    folder = root / "studies"
    sid = f"S{_next_study_number(folder):02d}"
    path = folder / f"{sid}-{_slug(idea.statement)}" / "STUDY.md"
    _exclusive(path, _study_text(sid, idea))
    return sid, path


def _cmd_promote(args: argparse.Namespace) -> int:
    by = _check_actor(str(args.by))
    idea = _require(args.root, str(args.id))
    if idea.promoted_target:
        raise IdeaError(f"{idea.id} is already promoted to {idea.promoted_target}")
    target, path = (
        _write_question(args.root, idea) if args.kind == "question" else _write_study(args.root, idea)
    )
    rel = path.relative_to(args.root).as_posix()
    payload = {"as": str(args.kind), "path": rel, "target": target}
    _append(args.root, _event("promoted", idea.id, by, payload))
    _render_all(args.root)
    print(f"{idea.id} {target}")
    return 0


def _in_study(idea: Idea, study: str) -> bool:
    if idea.study == study:
        return True
    return idea.promoted_as == "study" and idea.promoted_target == study


def _digest(ideas: dict[str, Idea], study: str) -> str:
    chosen = [idea for idea in ideas.values() if _in_study(idea, study)]
    lines = ["## Further work and untested ideas", ""]
    for level in _EVIDENCE:
        group = [idea for idea in chosen if idea.evidence == level]
        group.sort(key=lambda item: _id_key(item.id))
        if not group:
            continue
        lines.extend([f"### {level}", ""])
        for idea in group:
            label = "supported" if idea.status == "supported" else "untested"
            statement = " ".join(idea.statement.split())
            lines.append(f"- **{idea.id}** {statement} — **{label}**")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _cmd_digest(args: argparse.Namespace) -> int:
    print(_digest(load_ideas(args.root), str(args.study)), end="")
    return 0


def _nid(key: str) -> str:
    node = re.sub(r"[^A-Za-z0-9]", "_", key)
    if node == "" or node[0].isdigit():
        return "n_" + node
    return node


def _remember(nodes: dict[str, str], key: str, label: str) -> str:
    nid = _nid(key)
    nodes.setdefault(nid, label.replace('"', "'"))
    return nid


def _mermaid(ideas: dict[str, Idea]) -> str:
    nodes: dict[str, str] = {}
    edges: list[str] = []
    ordered = sorted(ideas.values(), key=lambda item: _id_key(item.id))
    for idea in ordered:
        src = _remember(nodes, idea.id, f"{idea.id} {idea.type}")
        _edge(edges, nodes, src, idea.study, idea.study)
        _edge(edges, nodes, src, idea.question, idea.question)
        if idea.promoted_target not in {None, idea.study, idea.question}:
            _edge(edges, nodes, src, idea.promoted_target, idea.promoted_target)
    lines = ["flowchart LR"]
    lines.extend(f'  {nid}["{label}"]' for nid, label in nodes.items())
    lines.extend(f"  {edge}" for edge in edges)
    return "\n".join(lines) + "\n"


def _edge(edges: list[str], nodes: dict[str, str], src: str, key: str | None, label: str | None) -> None:
    if key is None or label is None:
        return
    edge = f"{src} --> {_remember(nodes, key, label)}"
    if edge not in edges:
        edges.append(edge)


def _cmd_future_map(args: argparse.Namespace) -> int:
    path = args.root / "programme" / "future_map.mmd"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_mermaid(load_ideas(args.root)), encoding="utf-8")
    print(path)
    return 0


def _scout_prompt(root: Path, topic: str) -> str:
    path = root / ".cursor" / "rules" / "60-scout.mdc"
    if not path.is_file():
        raise IdeaError(f"scout rule not found: {path}")
    raw = path.read_text(encoding="utf-8")
    body = re.sub(r"^---\n.*?\n---\n", "", raw, count=1, flags=re.DOTALL).strip()
    return (
        f"Topic: {topic}\n\n"
        f"{body}\n\n"
        "Phase 1 does not call an LLM. Propose at most 5 speculations or improvements, "
        "each with a falsification condition. Cite only keys in references.bib or "
        "literature/candidates.bib (mark unverified). Feed each result back with:\n"
        '  uv run python tools/ideas.py add "<statement>" --by scout\n'
        "A later phase will call DeepSeek via dispatch_coder.\n"
    )


def _cmd_speculate(args: argparse.Namespace) -> int:
    print(_scout_prompt(args.root, str(args.topic)), end="")
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ideas.py")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    sub = parser.add_subparsers(dest="command", required=True)
    add = sub.add_parser("add")
    add.add_argument("text")
    add.add_argument("--type", dest="type_name", default="T")
    add.add_argument("--study", default=None)
    add.add_argument("--q", default=None)
    add.add_argument("--file", default=None)
    add.add_argument("--by", default="human", choices=sorted(_ACTORS))
    add.add_argument("--evidence", default="speculative")
    listing = sub.add_parser("list")
    listing.add_argument("--study", default=None)
    listing.add_argument("--status", default=None)
    listing.add_argument("--type", dest="type_name", default=None)
    status = sub.add_parser("status")
    status.add_argument("id")
    status.add_argument("new")
    status.add_argument("--by", default="human", choices=sorted(_ACTORS))
    link = sub.add_parser("link")
    link.add_argument("id")
    link.add_argument("--grounding", required=True)
    link.add_argument("--by", default="human", choices=sorted(_ACTORS))
    sub.add_parser("render")
    ingest = sub.add_parser("ingest")
    ingest.add_argument("id")
    triage = sub.add_parser("triage")
    triage.add_argument("--decisions", default=None)
    triage.add_argument("--by", default="human", choices=sorted(_ACTORS))
    promote = sub.add_parser("promote")
    promote.add_argument("id")
    promote.add_argument("--as", dest="kind", required=True, choices=("question", "study"))
    promote.add_argument("--by", default="human", choices=sorted(_ACTORS))
    digest = sub.add_parser("digest")
    digest.add_argument("study")
    sub.add_parser("future-map")
    speculate = sub.add_parser("speculate")
    speculate.add_argument("topic")
    return parser


_HANDLERS: dict[str, Callable[[argparse.Namespace], int]] = {
    "add": _cmd_add,
    "list": _cmd_list,
    "status": _cmd_status,
    "link": _cmd_link,
    "render": _cmd_render,
    "ingest": _cmd_ingest,
    "triage": _cmd_triage,
    "promote": _cmd_promote,
    "digest": _cmd_digest,
    "future-map": _cmd_future_map,
    "speculate": _cmd_speculate,
}


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        return _HANDLERS[str(args.command)](args)
    except IdeaError as exc:
        print(f"ideas: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
