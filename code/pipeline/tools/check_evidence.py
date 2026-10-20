"""Check reading notes (lit/@<key>.md) and evidence cards against the bibliography and local source texts.

Ported from Project N ``tools/check_evidence.py``. The check rules are the same. The root is
configurable because this project's frozen extracts and reading notes live outside the git repo.

Default root: ``EVIDENCE_ROOT`` if set, otherwise the parent of this repo when that parent
contains ``sources/`` and ``lit/``, otherwise the repo itself. ``--root`` overrides both.

Scans ``<root>/lit/*.md`` (plus ``evidence.md`` / ``evidence/*.md`` if present). Two checked objects:

- quote callouts in a lit note::

      > [!quote] §IV-A (or p. 6 for no-AI sources)
      > verbatim text ...

  Key and access come from the note's front matter (``key:``, ``access:``).
- cards: ``### ID · title`` plus a yaml block
  (``cite``, ``claim``, ``quote``, ``loc``, ``access``, ``status``).

Checks:

1. schema: required fields, enums, unique card IDs;
2. cite/key exists in ``<root>/refs/*.bib`` or in ``governance/references.bib``
   (this repo, or ``<root>/repo``);
3. quotes occur verbatim (after whitespace/quote/dash/emphasis normalisation)
   in ``sources/<key>.md``;
   no-AI sources (IEEE, paywalled) must not have a local text and need a page
   locator; their cards may only be ``human-read``;
4. every number in a card's claim appears in its quote or loc;
5. ``--cites FILE...``: every ``\\cite{key}`` / ``[@key]`` in a draft has at least one verified card.

``--list`` prints all cards. Exit 1 on any FAIL. This tool does not create a bib file or a card.

Legal ``access`` values: oa-cc, oa-arxiv, oa-other, ieee-no-ai, paywalled-no-ai.

Run: ``uv run python tools/check_evidence.py [--root DIR] [--list] [--cites draft.tex ...]``
"""

from __future__ import annotations

import argparse
import difflib
import os
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

KINDS = {"number", "formula", "method", "finding", "definition", "figure", "dataset", "negative"}
ACCESS = {"oa-cc", "oa-arxiv", "oa-other", "ieee-no-ai", "paywalled-no-ai"}
NO_AI = {"ieee-no-ai", "paywalled-no-ai"}
STATUS = ["todo", "ai-extracted", "quote-verified", "human-read"]
VERIFIED = {"quote-verified", "human-read"}
REQUIRED = {"cite", "claim", "access", "status"}
MAX_NO_AI_QUOTE_WORDS = 60

CARD_RE = re.compile(r"^### +(?P<id>[A-Z]+-\d{3})\b(?P<title>.*?)\n+```ya?ml\n(?P<body>.*?)```", re.M | re.S)
CALLOUT_RE = re.compile(r"^> *\[!quote\][-+]? *(?P<loc>[^\n]*)\n(?P<body>(?:>[^\n]*(?:\n|$))+)", re.M | re.I)
NUM_RE = re.compile(r"(?<![\w.])\d+(?:\.\d+)?")  # trailing units allowed: "22nm" -> 22
PAGE_RE = re.compile(r"\bp{1,2}\.?\s*\d+")
BIB_KEY_RE = re.compile(r"@\w+\s*\{\s*([^,\s]+)\s*,")
FRONT_RE = re.compile(r"^---\n(.*?)\n---", re.S)


@dataclass
class Report:
    fails: int = 0
    warns: int = 0

    def add(self, level: str, where: str, msg: str) -> None:
        if level == "FAIL":
            self.fails += 1
        elif level == "WARN":
            self.warns += 1
        print(f"{level:4s} {where:32s} {msg}")


@dataclass
class Ctx:
    root: Path
    report: Report
    keys: set[str]
    sources: dict[str, str | None] = field(default_factory=dict)

    def source_text(self, key: str) -> str | None:
        if key not in self.sources:
            path = self.root / "sources" / f"{key}.md"
            self.sources[key] = norm(path.read_text(encoding="utf-8")) if path.is_file() else None
        return self.sources[key]


def resolve_root(cli: Path | None) -> Path:
    """Evidence root: ``--root``, else ``EVIDENCE_ROOT``, else the vault beside this repo."""
    if cli is not None:
        return cli.expanduser().resolve()
    env = os.environ.get("EVIDENCE_ROOT")
    if env:
        return Path(env).expanduser().resolve()
    repo = Path(__file__).resolve().parents[1]
    vault = repo.parent
    if (vault / "sources").is_dir() and (vault / "lit").is_dir():
        return vault
    return repo


def note_files(root: Path) -> list[Path]:
    lit = root / "lit"
    notes = sorted(lit.glob("*.md")) if lit.is_dir() else []
    extra = [path for path in [root / "evidence.md"] if path.is_file()]
    evidence = root / "evidence"
    cards = sorted(evidence.glob("*.md")) if evidence.is_dir() else []
    return notes + extra + cards


def bib_files(root: Path) -> list[Path]:
    """Vault ``refs/*.bib``, plus the human-owned ``governance/references.bib`` if it exists."""
    found: list[Path] = []
    refs = root / "refs"
    if refs.is_dir():
        found.extend(sorted(path for path in refs.glob("*.bib") if path.is_file()))
    for path in (
        root / "governance" / "references.bib",
        root / "repo" / "governance" / "references.bib",
    ):
        if path.is_file() and path not in found:
            found.append(path)
    return found


def bib_keys(files: list[Path]) -> set[str]:
    keys: set[str] = set()
    for bib in files:
        keys |= set(BIB_KEY_RE.findall(bib.read_text(encoding="utf-8")))
    return keys


def norm(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = text.translate(
        str.maketrans(
            {
                "“": '"',
                "”": '"',
                "‘": "'",
                "’": "'",
                "–": "-",
                "—": "-",
                "−": "-",
                "\u00ad": "",
                "\u00a0": " ",
            }
        )
    )
    text = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", text)  # hyphenation across line breaks
    text = re.sub(r"[*_`]|==", "", text)  # markdown emphasis / highlight
    return re.sub(r"\s+", " ", text).strip().lower()


def closest(quote: str, text: str) -> str:
    folded = norm(quote)
    words = text.split(" ")
    width = max(1, len(folded.split(" ")))
    best, best_s = 0.0, ""
    step = max(1, width // 4)
    for i in range(0, max(1, len(words) - width + 1), step):
        cand = " ".join(words[i : i + width])
        ratio = difflib.SequenceMatcher(None, folded, cand).ratio()
        if ratio > best:
            best, best_s = ratio, cand
    return f'closest ({best:.0%}): "{best_s[:160]}"'


def _rel(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def check_quote(ctx: Ctx, where: str, key: str, access: str, quote: str, loc: str) -> bool:
    """Return True if the quote is acceptable for its access class."""
    if access in NO_AI:
        return _check_no_ai_quote(ctx, where, key, quote, loc)
    src = ctx.source_text(key)
    if src is None:
        ctx.report.add("FAIL", where, f"no local source sources/{key}.md")
        return False
    if norm(quote) not in src:
        ctx.report.add("FAIL", where, "quote not found verbatim in source; " + closest(quote, src))
        return False
    return True


def _check_no_ai_quote(ctx: Ctx, where: str, key: str, quote: str, loc: str) -> bool:
    ok = True
    if (ctx.root / "sources" / f"{key}.md").is_file():
        ctx.report.add("FAIL", where, f"sources/{key}.md exists for a no-AI source; delete it")
        ok = False
    if not PAGE_RE.search(loc):
        ctx.report.add("FAIL", where, "no-AI source needs a page locator, e.g. 'p. 6, Table 2'")
        ok = False
    if len(quote.split()) > MAX_NO_AI_QUOTE_WORDS:
        ctx.report.add("WARN", where, f"quote > {MAX_NO_AI_QUOTE_WORDS} words; keep no-AI quotes brief")
    return ok


def _front_matter(report: Report, rel: str, text: str) -> dict[str, Any]:
    matched = FRONT_RE.match(text)
    if not matched:
        return {}
    try:
        loaded = yaml.safe_load(matched.group(1))
    except yaml.YAMLError as exc:
        report.add("FAIL", rel, f"front matter YAML error: {exc}")
        return {}
    if loaded is None:
        return {}
    if isinstance(loaded, dict):
        return loaded
    report.add("FAIL", rel, "front matter is not a mapping")
    return {}


def _load_card(report: Report, where: str, body: str) -> dict[str, Any] | None:
    try:
        loaded = yaml.safe_load(body)
    except yaml.YAMLError as exc:
        report.add("FAIL", where, f"YAML error: {exc}")
        return None
    if loaded is None:
        return {}
    if isinstance(loaded, dict):
        return loaded
    report.add("FAIL", where, "card YAML is not a mapping")
    return None


def _missing_required(card: dict[str, Any]) -> list[str]:
    present = {key for key, value in card.items() if value not in (None, "")}
    return sorted(REQUIRED - present)


def _status_illegal(report: Report, where: str, card: dict[str, Any]) -> bool:
    """Report bad kind/access/status. Return True when status itself is illegal."""
    if "kind" in card and card["kind"] not in KINDS:
        report.add("FAIL", where, f"kind {card['kind']!r} not in {sorted(KINDS)}")
    if card["access"] not in ACCESS:
        report.add("FAIL", where, f"access {card['access']!r} not in {sorted(ACCESS)}")
    if card["status"] not in STATUS:
        report.add("FAIL", where, f"status {card['status']!r} not in {STATUS}")
        return True
    return False


def _number_level(card: dict[str, Any], quote: str, loc: str) -> str | None:
    quoted = set(NUM_RE.findall(quote.replace(",", ""))) | set(NUM_RE.findall(loc))
    claim_text = re.sub(r"\b[A-Z]+-\d{3}\b", "", str(card["claim"]).replace(",", ""))
    stray = [n for n in NUM_RE.findall(claim_text) if n not in quoted]
    if not stray:
        return None
    level = "FAIL" if card["status"] in VERIFIED else "WARN"
    return f"{level}\tnumbers in claim not in quote/loc: {stray}"


def _apply_number_level(report: Report, where: str, encoded: str) -> bool:
    level, msg = encoded.split("\t", 1)
    report.add(level, where, msg)
    return False


def check_card(
    ctx: Ctx,
    rel: str,
    match: re.Match[str],
    note_key: Any,
    note_access: Any,
    seen: dict[str, str],
    counts: dict[str, int],
    index: list[str],
    verified_by_key: dict[str, int],
) -> None:
    cid, where = match["id"], f"{rel}:{match['id']}"
    if cid in seen:
        ctx.report.add("FAIL", where, f"duplicate ID (also in {seen[cid]})")
    seen[cid] = rel
    card = _load_card(ctx.report, where, match["body"])
    if card is None:
        return
    card.setdefault("cite", note_key)
    card.setdefault("access", note_access)
    missing = _missing_required(card)
    if missing:
        ctx.report.add("FAIL", where, f"missing {missing}")
        return
    if _status_illegal(ctx.report, where, card):
        return
    counts[str(card["status"])] += 1
    key = str(card["cite"])
    title = match["title"].strip(" ·")[:70]
    index.append(f"{cid:9s} {card['status']:15s} {key:28s} {title}")
    if card["status"] == "todo":
        return
    _check_card_claim(ctx, where, card, verified_by_key)


def _check_card_claim(ctx: Ctx, where: str, card: dict[str, Any], verified_by_key: dict[str, int]) -> None:
    key = str(card["cite"])
    if key not in ctx.keys:
        level = "FAIL" if card["status"] in VERIFIED else "WARN"
        ctx.report.add(level, where, f"cite key {key!r} not in bib")
    quote, loc = str(card.get("quote") or ""), str(card.get("loc") or "")
    if not quote:
        ctx.report.add("FAIL", where, "status needs a quote")
        return
    ok = check_quote(ctx, where, key, str(card["access"]), quote, loc)
    ok = _no_ai_status(ctx, where, card) and ok
    if card["status"] == "ai-extracted":
        ctx.report.add("WARN", where, "ai-extracted: read the paragraph, then promote the status")
    encoded = _number_level(card, quote, loc)
    if encoded is not None:
        ok = _apply_number_level(ctx.report, where, encoded)
    if ok and card["status"] in VERIFIED:
        verified_by_key[key] = verified_by_key.get(key, 0) + 1


def _no_ai_status(ctx: Ctx, where: str, card: dict[str, Any]) -> bool:
    if card["access"] in NO_AI and card["status"] == "quote-verified":
        ctx.report.add(
            "FAIL",
            where,
            "no-AI sources can only be 'human-read' (checked by you against the PDF)",
        )
        return False
    return True


def check_callouts(ctx: Ctx, rel: str, note_key: str, note_access: Any, text: str) -> int:
    n = 0
    access = note_access if isinstance(note_access, str) else ""
    for i, match in enumerate(CALLOUT_RE.finditer(text), 1):
        n += 1
        quote = " ".join(line.lstrip(">").strip() for line in match["body"].splitlines())
        if quote.strip():
            check_quote(ctx, f"{rel}:quote#{i}", note_key, access, quote, match["loc"])
    return n


def check_note(
    ctx: Ctx,
    path: Path,
    seen: dict[str, str],
    counts: dict[str, int],
    index: list[str],
    verified_by_key: dict[str, int],
) -> int:
    if path.name.startswith("_"):
        return 0
    rel = _rel(ctx.root, path)
    text = path.read_text(encoding="utf-8")
    fm = _front_matter(ctx.report, rel, text)
    note_key, note_access = fm.get("key"), fm.get("access")
    n_callouts = 0
    if isinstance(note_key, str) and note_key:
        if note_key not in ctx.keys:
            ctx.report.add("WARN", rel, f"key {note_key!r} not in bib yet")
        if note_access not in ACCESS:
            ctx.report.add("FAIL", rel, f"front matter access {note_access!r} not in {sorted(ACCESS)}")
        n_callouts = check_callouts(ctx, rel, note_key, note_access, text)
    elif note_key not in (None, ""):
        ctx.report.add("FAIL", rel, f"front matter key {note_key!r} is not a string")
    for match in CARD_RE.finditer(text):
        check_card(ctx, rel, match, note_key, note_access, seen, counts, index, verified_by_key)
    return n_callouts


def check_draft(ctx: Ctx, draft: str, verified_by_key: dict[str, int]) -> None:
    path = Path(draft)
    text = path.read_text(encoding="utf-8")
    cited = set(re.findall(r"\[?@([\w:.-]+)", text))
    for grp in re.findall(r"\\cite\w*\{([^}]+)\}", text):
        cited |= {k.strip() for k in grp.split(",")}
    for key in sorted({k.rstrip(".") for k in cited}):
        _one_cite(ctx, path.name, key, verified_by_key)


def _one_cite(ctx: Ctx, name: str, key: str, verified_by_key: dict[str, int]) -> None:
    if key not in ctx.keys:
        ctx.report.add("FAIL", name, f"cites {key!r}: not in bib")
    elif not verified_by_key.get(key):
        ctx.report.add("FAIL", name, f"cites {key!r}: no verified card")


def _warn_layout(ctx: Ctx) -> None:
    if not (ctx.root / "lit").is_dir():
        ctx.report.add("FAIL", "lit/", f"no lit/ under {ctx.root}")
    if not (ctx.root / "sources").is_dir():
        ctx.report.add("WARN", "sources/", f"no sources/ under {ctx.root}")
    if not ctx.keys:
        ctx.report.add(
            "WARN",
            "refs/",
            "no .bib found (refs/library.bib from Better BibTeX, or governance/references.bib)",
        )


def _summary(ctx: Ctx, counts: dict[str, int], n_callouts: int) -> None:
    total = sum(counts.values())
    detail = ", ".join(f"{v} {k}" for k, v in counts.items())
    print(f"\nroot {ctx.root}")
    print(
        f"{total} cards ({detail}), {n_callouts} quote callouts | "
        f"{len(ctx.keys)} bib keys | {ctx.report.fails} FAIL, {ctx.report.warns} WARN"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="check_evidence.py")
    parser.add_argument("--root", type=Path, default=None, help="vault root (sources/, lit/, refs/)")
    parser.add_argument("--cites", nargs="*", default=[], help="drafts whose citations need verified cards")
    parser.add_argument("--list", action="store_true", help="print an index of all cards")
    args = parser.parse_args(argv)

    root = resolve_root(args.root)
    ctx = Ctx(root=root, report=Report(), keys=bib_keys(bib_files(root)))
    _warn_layout(ctx)
    seen: dict[str, str] = {}
    verified_by_key: dict[str, int] = {}
    counts: dict[str, int] = dict.fromkeys(STATUS, 0)
    index: list[str] = []
    n_callouts = 0
    for path in note_files(root):
        n_callouts += check_note(ctx, path, seen, counts, index, verified_by_key)
    for draft in args.cites:
        check_draft(ctx, draft, verified_by_key)
    if args.list:
        print("\n".join(["", *sorted(index)]))
    _summary(ctx, counts, n_callouts)
    return 1 if ctx.report.fails else 0


if __name__ == "__main__":
    sys.exit(main())
