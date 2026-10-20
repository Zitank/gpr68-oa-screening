"""Append-only JSONL check for governance/run_ledger.jsonl."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REQUIRED = frozenset({"run_id", "time_utc", "config_hash", "status", "mode"})
DEFAULT_LEDGER = Path("governance/run_ledger.jsonl")


def _git_show(repo: Path, spec: str) -> bytes | None:
    try:
        proc = subprocess.run(["git", "show", spec], cwd=repo, capture_output=True, check=True)
    except FileNotFoundError:
        raise
    except subprocess.CalledProcessError:
        return None
    return proc.stdout


def _read_file(path: Path) -> bytes | None:
    try:
        return path.read_bytes()
    except FileNotFoundError:
        return None


def _check_jsonl(raw: bytes) -> tuple[bool, str, int]:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return False, "line 1: not JSON", 0
    n = 0
    for i, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        n += 1
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            return False, f"line {i}: not JSON", n
        if not isinstance(obj, dict) or REQUIRED.difference(obj):
            missing = sorted(REQUIRED.difference(obj)) if isinstance(obj, dict) else []
            if missing:
                return False, f"line {i}: missing keys {missing}", n
            return False, f"line {i}: not JSON", n
    return True, "", n


def _prefix_fail(committed: bytes, current: bytes) -> str | None:
    if current.startswith(committed):
        return None
    limit = min(len(committed), len(current))
    byte = limit
    for i in range(limit):
        if committed[i] != current[i]:
            byte = i
            break
    return f"ledger not append-only: committed prefix differs at byte {byte}"


def check_ledger(path: Path, repo: Path, staged: bool) -> tuple[bool, str]:
    ledger = path.resolve() if path.is_absolute() else (repo / path).resolve()
    rel = ledger.relative_to(repo.resolve()).as_posix()
    committed = _git_show(repo, f"HEAD:{rel}")
    current = _git_show(repo, f":{rel}") if staged else _read_file(ledger)
    if current is None:
        if committed is None:
            return True, "ledger OK: 0 lines (missing file)"
        current = b""
    ok, err, n = _check_jsonl(current)
    if not ok:
        return False, err
    if committed is None:
        return True, f"ledger OK: {n} lines (no committed version)"
    fail = _prefix_fail(committed, current)
    if fail is not None:
        return False, fail
    return True, f"ledger OK: {n} lines"


def main() -> int:
    parser = argparse.ArgumentParser(prog="check_ledger.py")
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    parser.add_argument("--staged", action="store_true")
    args = parser.parse_args()
    try:
        ok, msg = check_ledger(args.ledger, Path.cwd(), args.staged)
    except FileNotFoundError as exc:
        print(f"ledger check failed: {exc}", file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as exc:
        print(f"ledger check failed: {exc}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as exc:
        print(f"ledger check failed: {exc}", file=sys.stderr)
        return 1
    print(msg)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
