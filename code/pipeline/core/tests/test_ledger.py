"""Append-only ledger: one line per call, including failures."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from core.config import config_hash
from core.errors import LedgerError
from core.ledger import effective_study_id, read_ledger, run_logged
from core.tests import make_config


def test_run_logged_success_appends_one_ok_line(tmp_path: Path) -> None:
    path = tmp_path / "governance" / "run_ledger.jsonl"
    cfg = make_config()

    def ok() -> dict[str, Any]:
        return {"acc": 0.25, "data_manifest_hash": "abc"}

    out = run_logged(cfg, ok, path)
    assert out == {"acc": 0.25, "data_manifest_hash": "abc"}
    raw = path.read_text(encoding="utf-8").splitlines()
    assert len(raw) == 1
    row = json.loads(raw[0])
    assert row["status"] == "ok"
    assert row["result"] == out
    assert row["data_manifest_hash"] == "abc"
    assert row["config_hash"] == config_hash(cfg)
    assert row["config"] == cfg.model_dump()
    assert row["seed"] == 0
    assert row["condition_code"] == "A"
    assert row["mode"] == "exploratory"
    assert row["error_type"] is None
    assert row["error_msg"] is None
    assert isinstance(row["python"], str)
    assert row["torch"] is None or isinstance(row["torch"], str)
    assert isinstance(row["duration_s"], int | float)
    stamp = datetime.fromisoformat(row["time_utc"])
    offset = stamp.utcoffset()
    assert stamp.tzinfo is not None
    assert offset is not None
    assert offset.total_seconds() == 0


def test_run_logged_failure_appends_and_reraises(tmp_path: Path) -> None:
    path = tmp_path / "run_ledger.jsonl"

    def boom() -> dict[str, Any]:
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        run_logged(make_config(), boom, path)
    rows = read_ledger(path)
    assert len(rows) == 1
    assert rows[0]["status"] == "failed"
    assert rows[0]["result"] is None
    assert rows[0]["error_type"] == "RuntimeError"
    assert rows[0]["error_msg"] == "boom"


def test_second_call_appends_without_touching_first_line(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "run_ledger.jsonl"

    def first() -> dict[str, Any]:
        return {"i": 1}

    def second() -> dict[str, Any]:
        return {"i": 2}

    run_logged(make_config(), first, path)
    before = path.read_bytes()
    run_logged(make_config(), second, path)
    after = path.read_bytes()
    assert before.endswith(b"\n")
    assert after.startswith(before)
    lines = after.splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["result"] == {"i": 1}
    assert json.loads(lines[1])["result"] == {"i": 2}
    assert json.loads(lines[0])["run_id"] != json.loads(lines[1])["run_id"]


def test_prereg_hash_null_in_exploratory_mode(tmp_path: Path) -> None:
    path = tmp_path / "run_ledger.jsonl"

    def ok() -> dict[str, Any]:
        return {"n": 0}

    run_logged(make_config(mode="exploratory"), ok, path)
    row = read_ledger(path)[0]
    assert row["mode"] == "exploratory"
    assert row["prereg_hash"] is None


def test_read_ledger_raises_on_corrupt_line(tmp_path: Path) -> None:
    path = tmp_path / "run_ledger.jsonl"
    path.write_text('{"status": "ok"}\n{"status": \n', encoding="utf-8")
    with pytest.raises(LedgerError, match=r"line 2"):
        read_ledger(path)


def test_nonserialisable_result_writes_nothing(tmp_path: Path) -> None:
    path = tmp_path / "run_ledger.jsonl"

    def bad() -> dict[str, Any]:
        return {"x": {1, 2}}

    with pytest.raises(LedgerError):
        run_logged(make_config(), bad, path)
    assert not path.exists()


def test_study_id_written_and_legacy_hash_unchanged(tmp_path: Path) -> None:
    assert "study_id" not in make_config().model_dump()
    assert config_hash(make_config(study_id="S01")) != config_hash(make_config())

    path = tmp_path / "run_ledger.jsonl"

    def ok() -> dict[str, Any]:
        return {"n": 1}

    run_logged(make_config(study_id="S01"), ok, path)
    run_logged(make_config(), ok, path)
    rows = read_ledger(path)
    assert rows[0]["study_id"] == "S01"
    assert rows[1]["study_id"] is None
    assert effective_study_id(rows[0]) == "S01"
    assert effective_study_id(rows[1]) == "S00-legacy"
    assert effective_study_id({}) == "S00-legacy"
