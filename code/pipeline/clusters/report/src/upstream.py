"""Read other packets' result files. Missing files stay pending; numbers are never filled in.

## [EXPLORATORY]
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from core.errors import ContractViolation

_REPO = Path(__file__).resolve().parents[3]
_POCKET = _REPO / "results" / "pocket" / "docking_box.json"
_SCORES = _REPO / "results" / "docking" / "scores.csv"
_LIGANDS = _REPO / "results" / "ligand_data" / "GPR68_reference_ligands.csv"
_DOCKING_DIR = _REPO / "results" / "docking"
_ML_DIR = _REPO / "results" / "ml_audit"

_SCORE_COLUMNS = (
    "best_score_kcal_mol",
    "affinity_kcal_mol",
    "affinity",
    "minimized_affinity",
    "vina_affinity",
    "smina_affinity",
    "cnn_affinity",
    "cnnaffinity",
    "smina_score",
    "score",
)
_LIGAND_COLUMNS = ("ligand", "ligand_name", "compound", "compound_name", "name")
_POCKET_COLUMNS = ("pocket_id", "pocket", "site")
_METRIC_NEEDLES = (
    "auc",
    "bedroc",
    "enrich",
    "ef1",
    "ef5",
    "ef_1",
    "ef_5",
    "ci_low",
    "ci_high",
    "ci_lower",
    "ci_upper",
    "ci95",
    "scaffold",
    "scramble",
    "y_scram",
    "verdict",
    "sentence",
    "substitution",
    "h1_",
    "h2_",
    "h3_",
    "fraction_in_domain",
    "n_molecules",
    "n_active",
    "n_inactive",
    "n_required",
    "primary_model",
    "label_source",
)
_MAX_CSV_METRIC_ROWS = 8
_BOX_LIST_KEYS = ("pockets", "boxes", "docking_boxes")
_CENTRE_KEYS = ("center_x", "center_y", "center_z")


def write_snapshot(path: Path) -> dict[str, object]:
    """Refresh the upstream snapshot the Quarto note reads."""
    snapshot = {
        "generated_utc": datetime.now(UTC).isoformat(),
        "pocket": _pocket(),
        "docking_scores": _scores(),
        "docking_metrics": _directory_metrics(_DOCKING_DIR, ignore_names={"scores.csv"}),
        "ligands": _ligands(),
        "ml_audit": _directory_metrics(_ML_DIR, ignore_names=set()),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return snapshot


def _pending(file_path: Path) -> dict[str, object]:
    return {"status": "pending", "path": str(file_path), "detail": "file not on disk at snapshot time"}


def _unreadable(file_path: Path, exc: Exception) -> dict[str, object]:
    return {"status": "unreadable", "path": str(file_path), "detail": f"{type(exc).__name__}: {exc}"}


def _pocket() -> dict[str, object]:
    if not _POCKET.is_file():
        return _pending(_POCKET)
    try:
        payload = json.loads(_POCKET.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return _unreadable(_POCKET, exc)
    rows = _box_rows(payload)
    if not rows:
        keys = sorted(payload.keys()) if isinstance(payload, dict) else [type(payload).__name__]
        return {
            "status": "present_unparsed",
            "path": str(_POCKET),
            "detail": "JSON parsed, but no pocket centre fields were found. No centres are reported.",
            "top_level_keys": keys,
            "rows": [],
        }
    return {"status": "present", "path": str(_POCKET), "detail": f"{len(rows)} pocket boxes", "rows": rows}


def _box_rows(payload: object) -> list[dict[str, object]]:
    records = _candidate_records(payload)
    rows: list[dict[str, object]] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        lowered = {str(key).lower(): value for key, value in record.items()}
        if not all(key in lowered for key in _CENTRE_KEYS):
            continue
        rows.append({str(key): value for key, value in record.items()})
    return rows


def _candidate_records(payload: object) -> list[object]:
    if isinstance(payload, list):
        return list(payload)
    if not isinstance(payload, dict):
        return []
    for key in _BOX_LIST_KEYS:
        found = payload.get(key)
        if isinstance(found, list):
            return list(found)
    if all(isinstance(value, dict) for value in payload.values()) and payload:
        return list(payload.values())
    return [payload]


def _scores() -> dict[str, object]:
    if not _SCORES.is_file():
        return _pending(_SCORES)
    try:
        frame = pd.read_csv(_SCORES, dtype=str, keep_default_na=False)
    except (OSError, UnicodeError, pd.errors.ParserError, pd.errors.EmptyDataError, ValueError) as exc:
        return _unreadable(_SCORES, exc)
    columns = [str(column) for column in frame.columns]
    score = _match_column(columns, _SCORE_COLUMNS)
    ligand = _match_column(columns, _LIGAND_COLUMNS)
    pocket = _match_column(columns, _POCKET_COLUMNS)
    base = {"path": str(_SCORES), "columns": columns, "n_rows": int(frame.shape[0])}
    if score is None or ligand is None or pocket is None:
        missing = [
            name
            for name, found in (("score", score), ("ligand", ligand), ("pocket", pocket))
            if found is None
        ]
        return {
            **base,
            "status": "present_unparsed",
            "detail": "scores.csv is on disk. Pocket comparison was not computed. Missing: "
            + ", ".join(missing),
            "by_ligand_pocket": [],
        }
    grouped = _median_by(frame, ligand, pocket, score)
    return {
        **base,
        "status": "present",
        "detail": f"median of {score} by {ligand} and {pocket}. Sign is whatever the file uses.",
        "score_column": score,
        "by_ligand_pocket": grouped,
    }


def _match_column(columns: list[str], candidates: tuple[str, ...]) -> str | None:
    lowered = {column.lower(): column for column in columns}
    for candidate in candidates:
        if candidate in lowered:
            return lowered[candidate]
    return None


def _median_by(frame: pd.DataFrame, ligand: str, pocket: str, score: str) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for (ligand_value, pocket_value), group in frame.groupby([ligand, pocket], sort=True):
        numbers = [_as_float(value) for value in group[score].tolist()]
        kept = [value for value in numbers if value is not None]
        if not kept:
            raise ContractViolation(
                f"score column {score} has no numeric values for {ligand_value} / {pocket_value}"
            )
        ordered = sorted(kept)
        mid = ordered[(len(ordered) - 1) // 2]
        rows.append(
            {
                "ligand": ligand_value,
                "pocket": pocket_value,
                "n": len(kept),
                "median": mid,
                "minimum": ordered[0],
            }
        )
    return rows


def _as_float(value: object) -> float | None:
    if not isinstance(value, str) or value.strip() == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _ligands() -> dict[str, object]:
    if not _LIGANDS.is_file():
        return _pending(_LIGANDS)
    try:
        frame = pd.read_csv(_LIGANDS, dtype=str, keep_default_na=False)
    except (OSError, UnicodeError, pd.errors.ParserError, pd.errors.EmptyDataError, ValueError) as exc:
        return _unreadable(_LIGANDS, exc)
    columns = [str(column) for column in frame.columns]
    by_type: list[dict[str, object]] = []
    if "activity_type" in frame.columns:
        counts = frame["activity_type"].value_counts(sort=True)
        by_type = [{"activity_type": str(key), "n_rows": int(value)} for key, value in counts.items()]
    n_compounds = int(frame["compound_name"].nunique()) if "compound_name" in frame.columns else -1
    return {
        "status": "present",
        "path": str(_LIGANDS),
        "detail": "Endpoints are counted separately and are not pooled.",
        "columns": columns,
        "n_rows": int(frame.shape[0]),
        "n_compounds": n_compounds,
        "by_activity_type": by_type,
    }


def _directory_metrics(directory: Path, *, ignore_names: set[str]) -> dict[str, object]:
    if not directory.is_dir():
        return _pending(directory)
    files = [
        path for path in sorted(directory.rglob("*")) if path.is_file() and path.name not in ignore_names
    ]
    if not files:
        return {
            "status": "pending",
            "path": str(directory),
            "detail": "directory exists but contains no result files",
            "files": [],
            "metrics": [],
        }
    metrics: list[dict[str, object]] = []
    listed: list[str] = []
    unreadable: list[str] = []
    for path in files:
        listed.append(str(path.relative_to(_REPO)))
        metrics.extend(_metrics_in_file(path))
        if path.suffix.lower() in {".json", ".csv"} and not _metrics_in_file(path) and _file_failed(path):
            unreadable.append(path.name)
    tables = _small_tables(files)
    status = "present" if metrics or tables else "present_unparsed"
    detail = (
        f"{len(metrics)} recognised metric fields"
        if metrics
        else "files are on disk; none exposed AUC, EF, BEDROC, or CI fields this note knows"
    )
    if unreadable:
        detail += ". Unreadable: " + ", ".join(unreadable)
    return {
        "status": status,
        "path": str(directory),
        "detail": detail,
        "files": listed,
        "metrics": metrics,
        "tables": tables,
    }


def _file_failed(path: Path) -> bool:
    try:
        if path.suffix.lower() == ".json":
            json.loads(path.read_text(encoding="utf-8"))
        elif path.suffix.lower() == ".csv":
            pd.read_csv(path, dtype=str, keep_default_na=False)
    except (
        OSError,
        UnicodeError,
        json.JSONDecodeError,
        pd.errors.ParserError,
        pd.errors.EmptyDataError,
        ValueError,
    ):
        return True
    return False


def _metrics_in_file(path: Path) -> list[dict[str, object]]:
    try:
        if path.suffix.lower() == ".json":
            return _metrics_from_json(path, json.loads(path.read_text(encoding="utf-8")))
        if path.suffix.lower() == ".csv":
            return _metrics_from_csv(path, pd.read_csv(path, dtype=str, keep_default_na=False))
    except (
        OSError,
        UnicodeError,
        json.JSONDecodeError,
        pd.errors.ParserError,
        pd.errors.EmptyDataError,
        ValueError,
    ):
        return []
    return []


def _metrics_from_json(path: Path, payload: object) -> list[dict[str, object]]:
    found: list[dict[str, object]] = []
    for key, value in _numeric_leaves(payload):
        if _key_wanted(key):
            found.append({"file": path.name, "key": key, "value": value})
    return found


def _metrics_from_csv(path: Path, frame: pd.DataFrame) -> list[dict[str, object]]:
    if len(frame) > _MAX_CSV_METRIC_ROWS:
        return []
    wanted = [column for column in frame.columns if _key_wanted(str(column))]
    if not wanted:
        return []
    rows: list[dict[str, object]] = []
    for column in wanted:
        for raw in frame[column].tolist():
            number = _as_float(raw)
            if number is None:
                continue
            rows.append({"file": path.name, "key": str(column), "value": number})
    return rows


def _small_tables(files: list[Path]) -> list[dict[str, object]]:
    tables: list[dict[str, object]] = []
    for path in files:
        if path.suffix.lower() != ".csv":
            continue
        try:
            frame = pd.read_csv(path, dtype=str, keep_default_na=False)
        except (OSError, UnicodeError, pd.errors.ParserError, pd.errors.EmptyDataError, ValueError):
            continue
        if frame.empty or len(frame) > 12 or frame.shape[1] > 8:
            continue
        tables.append(
            {
                "file": path.name,
                "columns": [str(column) for column in frame.columns],
                "rows": frame.to_dict(orient="records"),
            }
        )
    return tables


def _leaf(prefix: str, payload: object) -> tuple[str, object] | None:
    if not prefix:
        return None
    if isinstance(payload, list) and _short_number_list(payload):
        return prefix, ", ".join(f"{float(item):.4g}" for item in payload)
    if isinstance(payload, str) and payload.strip() and len(payload) <= 500:
        return prefix, payload
    if isinstance(payload, bool):
        return prefix, payload
    if isinstance(payload, (int, float)) and not isinstance(payload, bool):
        return prefix, float(payload)
    return None


def _short_number_list(payload: list[object]) -> bool:
    if not 0 < len(payload) <= 4:
        return False
    return all(isinstance(item, (int, float)) and not isinstance(item, bool) for item in payload)


def _numeric_leaves(payload: object, prefix: str = "", depth: int = 0) -> list[tuple[str, object]]:
    if depth > 4:
        return []
    if isinstance(payload, dict):
        found: list[tuple[str, object]] = []
        for key, value in payload.items():
            child = f"{prefix}.{key}" if prefix else str(key)
            found.extend(_numeric_leaves(value, child, depth + 1))
        return found
    leaf = _leaf(prefix, payload)
    if leaf is None:
        return []
    return [leaf]


def _key_wanted(key: str) -> bool:
    lowered = key.lower()
    return any(needle in lowered for needle in _METRIC_NEEDLES)
