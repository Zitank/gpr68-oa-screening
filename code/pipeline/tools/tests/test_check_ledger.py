from __future__ import annotations

import json
import subprocess
from pathlib import Path

from tools.check_ledger import check_ledger

_FIELDS = {
    "time_utc": "2026-01-01T00:00:00Z",
    "config_hash": "abc",
    "status": "ok",
    "mode": "exploratory",
}


def _line(run_id: str) -> str:
    return json.dumps({"run_id": run_id, **_FIELDS})


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=p1",
            "-c",
            "user.email=p1@example.com",
            "-c",
            "commit.gpgsign=false",
            *args,
        ],
        cwd=repo,
        check=True,
        capture_output=True,
    )


def _seed(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-b", "main")
    ledger = tmp_path / "governance" / "run_ledger.jsonl"
    ledger.parent.mkdir()
    ledger.write_text(_line("a") + "\n" + _line("b") + "\n", encoding="utf-8")
    _git(tmp_path, "add", "governance/run_ledger.jsonl")
    _git(tmp_path, "commit", "-m", "ledger")
    return ledger


def test_append_passes(tmp_path: Path) -> None:
    ledger = _seed(tmp_path)
    with ledger.open("a", encoding="utf-8") as fh:
        fh.write(_line("c") + "\n")
    ok, msg = check_ledger(ledger, tmp_path, staged=False)
    assert ok, msg
    assert "ledger OK: 3 lines" in msg


def test_modify_first_line_fails_append_only(tmp_path: Path) -> None:
    ledger = _seed(tmp_path)
    lines = ledger.read_text(encoding="utf-8").splitlines(keepends=True)
    lines[0] = _line("mutated") + "\n"
    ledger.write_text("".join(lines), encoding="utf-8")
    ok, msg = check_ledger(ledger, tmp_path, staged=False)
    assert not ok
    assert "append-only" in msg


def test_delete_line_fails(tmp_path: Path) -> None:
    ledger = _seed(tmp_path)
    first = ledger.read_text(encoding="utf-8").splitlines(keepends=True)[0]
    ledger.write_text(first, encoding="utf-8")
    ok, msg = check_ledger(ledger, tmp_path, staged=False)
    assert not ok
    assert "append-only" in msg


def test_non_json_reports_line_number(tmp_path: Path) -> None:
    ledger = _seed(tmp_path)
    with ledger.open("a", encoding="utf-8") as fh:
        fh.write("not-json\n")
    ok, msg = check_ledger(ledger, tmp_path, staged=False)
    assert not ok
    assert "line 3" in msg
    assert "not JSON" in msg


def test_missing_ledger_passes(tmp_path: Path) -> None:
    _git(tmp_path, "init", "-b", "main")
    ok, msg = check_ledger(tmp_path / "governance" / "run_ledger.jsonl", tmp_path, staged=False)
    assert ok, msg


def test_staged_detects_modification(tmp_path: Path) -> None:
    ledger = _seed(tmp_path)
    lines = ledger.read_text(encoding="utf-8").splitlines(keepends=True)
    lines[0] = _line("mutated") + "\n"
    ledger.write_text("".join(lines), encoding="utf-8")
    ok, msg = check_ledger(ledger, tmp_path, staged=True)
    assert ok, msg
    _git(tmp_path, "add", "governance/run_ledger.jsonl")
    ok, msg = check_ledger(ledger, tmp_path, staged=True)
    assert not ok
    assert "append-only" in msg
