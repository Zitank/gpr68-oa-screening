"""Content hashes and the git commit stamp recorded on each ledger line."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

_GIT_TIMEOUT_S = 5.0


def sha256_json(obj: Any) -> str:
    """sha256 hex of canonical JSON (sorted keys, no insignificant whitespace)."""
    payload = json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    """sha256 hex of a file's raw bytes."""
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_commit(repo: Path | None = None) -> str:
    """Short HEAD (`git rev-parse --short HEAD`), or ``nogit`` if that fails.

    Never raises: missing git, a non-work-tree, or a timeout all return ``nogit``.
    """
    cmd = ["git", "rev-parse", "--short", "HEAD"]
    cwd = str(repo) if repo is not None else None
    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT_S,
            check=False,
        )
    except (OSError, subprocess.SubprocessError, UnicodeError):
        return "nogit"
    if proc.returncode != 0:
        return "nogit"
    short = proc.stdout.strip()
    if not short or any(ch.isspace() for ch in short):
        return "nogit"
    return short
