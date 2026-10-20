"""Append-only run ledger. The only writer is ``run_logged``."""

from __future__ import annotations

import json
import platform
import time
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from core.config import ExperimentConfig, config_hash
from core.errors import LedgerError
from core.hashing import git_commit

_DEFAULT_LEDGER_PATH = Path("governance/run_ledger.jsonl")


def run_logged(
    cfg: ExperimentConfig,
    fn: Callable[[], dict[str, Any]],
    ledger_path: Path = _DEFAULT_LEDGER_PATH,
) -> dict[str, Any]:
    """Call ``fn``, append one JSON line, and return its dict.

    On any exception from ``fn``, append ``status="failed"`` and re-raise.
    A result that is not JSON-serialisable raises ``LedgerError`` and writes nothing.
    """
    run_id = str(uuid.uuid4())
    started = datetime.now(UTC)
    t0 = time.perf_counter()
    try:
        result = fn()
    except BaseException as exc:  # noqa: BLE001 — log every failure or abort, then re-raise
        _append(
            ledger_path,
            _line(
                cfg,
                run_id,
                started,
                time.perf_counter() - t0,
                status="failed",
                result=None,
                error_type=type(exc).__name__,
                error_msg=str(exc),
                data_manifest_hash=None,
            ),
        )
        raise
    duration_s = time.perf_counter() - t0
    if not isinstance(result, dict):
        raise LedgerError(f"run result must be a dict, got {type(result).__name__}")
    manifest = result["data_manifest_hash"] if "data_manifest_hash" in result else None
    _append(
        ledger_path,
        _line(
            cfg,
            run_id,
            started,
            duration_s,
            status="ok",
            result=result,
            error_type=None,
            error_msg=None,
            data_manifest_hash=manifest,
        ),
    )
    return result


def effective_study_id(line: dict[str, Any]) -> str:
    """Study id recorded on a ledger line.

    Missing or null ``study_id`` (lines written before the field existed) reads as
    ``S00-legacy``. This does not rewrite the line.
    """
    found = line.get("study_id")
    if isinstance(found, str) and found != "":
        return found
    return "S00-legacy"


def read_ledger(path: Path) -> list[dict[str, Any]]:
    """Parse each JSONL line. ``LedgerError`` names the 1-based line on bad JSON."""
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as fh:
        for number, raw in enumerate(fh, start=1):
            text = raw.strip()
            if text == "":
                raise LedgerError(f"malformed JSON at line {number}: empty line")
            try:
                obj = json.loads(text)
            except json.JSONDecodeError as exc:
                raise LedgerError(f"malformed JSON at line {number}: {exc.msg}") from exc
            if not isinstance(obj, dict):
                raise LedgerError(f"malformed JSON at line {number}: expected an object")
            rows.append(obj)
    return rows


def _line(
    cfg: ExperimentConfig,
    run_id: str,
    started: datetime,
    duration_s: float,
    *,
    status: Literal["ok", "failed"],
    result: dict[str, Any] | None,
    error_type: str | None,
    error_msg: str | None,
    data_manifest_hash: Any,
) -> dict[str, Any]:
    # Exploratory prereg_hash is null. Confirmatory stays null too: run_logged
    # has no prereg argument yet (Phase 0 never opens confirmatory).
    return {
        "run_id": run_id,
        "time_utc": started.isoformat(),
        "git_commit": git_commit(),
        "config_hash": config_hash(cfg),
        "config": cfg.model_dump(),
        "data_manifest_hash": data_manifest_hash,
        "seed": cfg.seed,
        "condition_code": cfg.condition_code,
        "mode": cfg.mode,
        "study_id": cfg.study_id,
        "prereg_hash": None,
        "status": status,
        "result": result,
        "error_type": error_type,
        "error_msg": error_msg,
        "python": platform.python_version(),
        "torch": _torch_version(),
        "duration_s": duration_s,
    }


def _append(path: Path, record: dict[str, Any]) -> None:
    try:
        line = json.dumps(record, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise LedgerError(
            f"refusing to write a partial ledger line; record is not JSON-serialisable: {exc}"
        ) from exc
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def _torch_version() -> str | None:
    try:
        import torch  # pyright: ignore[reportMissingImports]
    except ImportError:
        return None
    return str(torch.__version__)
