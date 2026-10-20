"""Hash helpers and git_commit fallback."""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

from core.hashing import git_commit, sha256_file, sha256_json


def test_sha256_json_ignores_key_order() -> None:
    assert sha256_json({"b": 1, "a": {"d": 2, "c": 3}}) == sha256_json({"a": {"c": 3, "d": 2}, "b": 1})


def test_sha256_file_matches_bytes(tmp_path: Path) -> None:
    path = tmp_path / "blob.bin"
    payload = b"abc"
    path.write_bytes(payload)
    assert sha256_file(path) == hashlib.sha256(payload).hexdigest()


def _git(repo: Path, *args: str) -> None:
    cmd = ["git", "-c", "user.name=kit", "-c", "user.email=kit@example.com"]
    cmd += ["-c", "commit.gpgsign=false", *args]
    subprocess.run(cmd, cwd=repo, check=True, capture_output=True)


def test_git_commit_nogit_outside_repo_and_hash_inside(tmp_path: Path) -> None:
    assert git_commit(tmp_path) == "nogit"
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    (repo / "f.txt").write_text("x\n", encoding="utf-8")
    _git(repo, "add", "f.txt")
    _git(repo, "commit", "-m", "init")
    short = git_commit(repo)
    assert short != "nogit"
    assert len(short) >= 7
