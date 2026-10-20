from __future__ import annotations

from pathlib import Path

from tools.ideas import main as ideas_main
from tools.lint_tags import lint_tags


def _tag(body: str) -> str:
    return "## " + "[" + body + "]"


def test_speculation_outside_explore_is_quarantined(tmp_path: Path) -> None:
    path = tmp_path / "clusters" / "x" / "src" / "confirm.py"
    path.parent.mkdir(parents=True)
    path.write_text(_tag("SPECULATION: T-001") + "\n", encoding="utf-8")
    errors = lint_tags(tmp_path)
    assert any("quarantine" in err for err in errors)


def test_speculation_under_explore_is_ok(tmp_path: Path) -> None:
    assert ideas_main(["--root", str(tmp_path), "add", "a speculation"]) == 0
    path = tmp_path / "clusters" / "x" / "src" / "explore" / "confirm.py"
    path.parent.mkdir(parents=True)
    path.write_text(_tag("SPECULATION: T-001") + "\n", encoding="utf-8")
    assert lint_tags(tmp_path) == []


def test_exploratory_marker_allows_speculation(tmp_path: Path) -> None:
    assert ideas_main(["--root", str(tmp_path), "add", "a speculation"]) == 0
    path = tmp_path / "clusters" / "x" / "src" / "confirm.py"
    path.parent.mkdir(parents=True)
    path.write_text(_tag("EXPLORATORY") + "\n" + _tag("SPECULATION: T-001") + "\n", encoding="utf-8")
    assert lint_tags(tmp_path) == []


def test_speculation_id_in_claims_yaml_errors(tmp_path: Path) -> None:
    claims = tmp_path / "governance" / "claims.yaml"
    claims.parent.mkdir(parents=True)
    claims.write_text("note: T-001\n", encoding="utf-8")
    errors = lint_tags(tmp_path)
    assert errors
    assert any("T-001" in err for err in errors)


def test_unknown_tag_errors(tmp_path: Path) -> None:
    path = tmp_path / "core" / "x.py"
    path.parent.mkdir(parents=True)
    path.write_text(_tag("NOT-A-TAG: nope") + "\n", encoding="utf-8")
    errors = lint_tags(tmp_path)
    assert any("unknown tag" in err for err in errors)


def test_repo_tree_passes() -> None:
    root = Path(__file__).resolve().parents[2]
    assert lint_tags(root) == []
