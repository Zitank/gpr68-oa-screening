from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

_KNOWN = frozenset(
    "CITE HYP ASSUMPTION DECISION VERIFIED-BY NEEDS-SOURCE EXPLORATORY SPECULATION IMPROVE".split()
)
_TAG = re.compile(r"## \[([A-Z][A-Z0-9-]*)(?::\s*([^\]\n]*))?\]")
_SPEC_ID = re.compile(r"(?<![A-Za-z0-9-])T-\d{3,}(?!\d)")
_IDEA_ID = {"SPECULATION": re.compile(r"^T-\d{3,}$"), "IMPROVE": re.compile(r"^I-\d{3,}$")}
_SCAN = ("core", "clusters", "tools", "studies", "governance")
_SUFFIXES = {".py", ".md", ".yaml", ".yml", ".txt", ".just", ".toml"}
_SKIP = frozenset({"__pycache__", ".venv", ".git", ".ruff_cache", ".pytest_cache"})


def lint_tags(root: Path) -> list[str]:
    root = root.resolve()
    ids, err = _idea_ids(root)
    errors = [err] if err else []
    assumptions_path = root / "governance" / "assumptions.md"
    assumptions = assumptions_path.read_text(encoding="utf-8") if assumptions_path.is_file() else ""
    bib_path = root / "governance" / "references.bib"
    bib = bib_path.read_text(encoding="utf-8") if bib_path.is_file() else None
    errors.extend(msg for path in _files(root) for msg in _file_tags(root, path, ids, assumptions, bib))
    errors.extend(_quarantine_files(root))
    return errors


def _idea_ids(root: Path) -> tuple[set[str], str | None]:
    path = root / "ideas" / "events.jsonl"
    if not path.is_file():
        return set(), None
    ids: set[str] = set()
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as exc:
            return ids, f"ideas/events.jsonl:{number}: {exc}"
        if isinstance(obj, dict) and obj.get("event") == "created" and isinstance(obj.get("id"), str):
            ids.add(obj["id"])
    return ids, None


def _files(root: Path) -> list[Path]:
    found: list[Path] = []
    for name in _SCAN:
        base = root / name
        if not base.exists():
            continue
        found.extend(path for path in base.rglob("*") if _kept(path))
    smoke = root / "smoke.py"
    if smoke.is_file():
        found.append(smoke)
    return sorted(set(found))


def _file_tags(root: Path, path: Path, ids: set[str], assumptions: str, bib: str | None) -> list[str]:
    rel = path.relative_to(root).as_posix()
    text = path.read_text(encoding="utf-8")
    tags = [(text.count("\n", 0, m.start()) + 1, m.group(1), m.group(2)) for m in _TAG.finditer(text)]
    exploratory = any(tag == "EXPLORATORY" for _, tag, _ in tags) or "/explore/" in f"/{rel}"
    out: list[str] = []
    for line, tag, payload in tags:
        out.extend(_one(f"{rel}:{line}", tag, payload, ids, exploratory, assumptions, bib))
    return out


def _one(
    loc: str,
    tag: str,
    payload: str | None,
    ids: set[str],
    exploratory: bool,
    assumptions: str,
    bib: str | None,
) -> list[str]:
    if tag not in _KNOWN:
        return [f"{loc}: unknown tag {tag}"]
    if tag == "SPECULATION":
        return _speculation(loc, payload, ids, exploratory)
    if tag == "IMPROVE":
        return _idea_ref(loc, "IMPROVE", "I-NNN", payload, ids)
    if tag == "CITE":
        return _cite(loc, payload, bib)
    if tag == "ASSUMPTION":
        return _assumption(loc, payload, assumptions)
    found = _SPEC_ID.search(payload) if tag == "VERIFIED-BY" and payload else None
    if found:
        return [f"{loc}: quarantine: speculation id {found.group(0)} in VERIFIED-BY"]
    return []


def _speculation(loc: str, payload: str | None, ids: set[str], exploratory: bool) -> list[str]:
    errors: list[str] = []
    if not exploratory:
        errors.append(f"{loc}: quarantine: SPECULATION tag requires /explore/ or EXPLORATORY")
    errors.extend(_idea_ref(loc, "SPECULATION", "T-NNN", payload, ids))
    return errors


def _idea_ref(loc: str, tag: str, shape: str, payload: str | None, ids: set[str]) -> list[str]:
    token = payload.split()[0] if payload else ""
    if _IDEA_ID[tag].fullmatch(token) is None:
        return [f"{loc}: {tag} payload must be {shape}"]
    if token not in ids:
        return [f"{loc}: idea {token} is not in the registry"]
    return []


def _cite(loc: str, payload: str | None, bib: str | None) -> list[str]:
    if bib is None:
        return [f"{loc}: no references.bib"]
    raw = (payload or "").split("|", 1)[0].strip()
    key = raw.split()[0] if raw else ""
    if not key:
        return [f"{loc}: CITE requires a key"]
    if re.search(r"@\w+\{\s*" + re.escape(key) + r"\s*,", bib) is None:
        return [f"{loc}: citekey {key} not in references.bib"]
    return []


def _assumption(loc: str, payload: str | None, assumptions: str) -> list[str]:
    token = payload.split()[0] if payload else ""
    if not token or not assumptions:
        return [f"{loc}: assumption {token or '?'} not in assumptions.md"]
    pattern = r"(?<![A-Za-z0-9])" + re.escape(token) + r"(?![A-Za-z0-9])"
    if re.search(pattern, assumptions) is None:
        return [f"{loc}: assumption {token} not in assumptions.md"]
    return []


def _quarantine_files(root: Path) -> list[str]:
    targets: list[Path] = []
    claims = root / "governance" / "claims.yaml"
    prereg = root / "governance" / "prereg"
    if claims.is_file():
        targets.append(claims)
    if prereg.is_dir():
        targets.extend(path for path in sorted(prereg.rglob("*")) if _kept_doc(path))
    errors: list[str] = []
    for path in targets:
        rel = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8")
        where = "claims.yaml" if path.name == "claims.yaml" else "prereg"
        for match in _SPEC_ID.finditer(text):
            line = text.count("\n", 0, match.start()) + 1
            errors.append(f"{rel}:{line}: quarantine: speculation id {match.group(0)} in {where}")
    return errors


def _kept(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in _SUFFIXES and _SKIP.isdisjoint(path.parts)


def _kept_doc(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in {".md", ".yaml", ".yml"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lint_tags.py")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    errors = lint_tags(args.root)
    if not errors:
        print("lint_tags OK")
        return 0
    print("\n".join(errors))
    return 1


if __name__ == "__main__":
    sys.exit(main())
