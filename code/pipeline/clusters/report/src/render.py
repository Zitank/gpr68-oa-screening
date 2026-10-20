"""Refresh the upstream snapshot and render the Quarto note. Not a logged experiment."""

from __future__ import annotations

import subprocess
from pathlib import Path

from clusters.report.src.upstream import write_snapshot
from core.errors import ContractViolation

_REPO = Path(__file__).resolve().parents[3]
_OUT = _REPO / "results" / "report"
_QMD = _OUT / "GPR68_decision_report.qmd"
_PIXI = Path.home() / ".pixi" / "bin" / "pixi"
_MANIFEST = _REPO / "pixi.toml"


def main() -> None:
    if not _QMD.is_file():
        raise ContractViolation(f"Quarto source missing: {_QMD}")
    write_snapshot(_OUT / "upstream_snapshot.json")
    command = [
        str(_PIXI),
        "run",
        "--manifest-path",
        str(_MANIFEST),
        "quarto",
        "render",
        str(_QMD),
        "--to",
        "html",
    ]
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    if completed.stdout:
        print(completed.stdout)
    if completed.returncode != 0:
        tail = (completed.stderr or completed.stdout or "")[-4000:]
        raise ContractViolation(f"quarto render exited {completed.returncode}: {tail}")
    html = _OUT / "GPR68_decision_report.html"
    if not html.is_file():
        raise ContractViolation(f"render reported success but {html} is missing")
    print(html)


if __name__ == "__main__":
    main()
