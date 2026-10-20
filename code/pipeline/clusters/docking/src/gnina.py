"""GNINA replay of the eight runs. These commands are not executed here.

GNINA adds CNN rescoring on top of the same Vina box, exhaustiveness, and seed.
The numbers in results/docking/scores.csv are smina's, not GNINA's.
"""

from __future__ import annotations

import json
from pathlib import Path

from clusters.docking.src.plan import RunSpec
from clusters.docking.src.settings import CPU, ENERGY_RANGE, NUM_MODES, SEED
from clusters.pocket.src.box import BOX_EDGE_A, POCKET_CENTRES
from clusters.pocket.src.protonate import PH_PRIMARY

GNINA_VERSION = "v1.3.3"
GNINA_URL = "https://github.com/gnina/gnina/releases/download/v1.3.3/gnina.cuda12.8.static"


def gnina_argv(spec: RunSpec, receptor: str, ligand: str, output: str) -> list[str]:
    """One GNINA invocation. Same geometry and search settings as smina, plus CNN rescoring."""
    centre = POCKET_CENTRES[spec.pocket_id]
    return [
        "./gnina",
        "-r",
        receptor,
        "-l",
        ligand,
        "--center_x",
        f"{centre[0]:.2f}",
        "--center_y",
        f"{centre[1]:.2f}",
        "--center_z",
        f"{centre[2]:.2f}",
        "--size_x",
        f"{BOX_EDGE_A:.2f}",
        "--size_y",
        f"{BOX_EDGE_A:.2f}",
        "--size_z",
        f"{BOX_EDGE_A:.2f}",
        "--exhaustiveness",
        str(spec.exhaustiveness),
        "--num_modes",
        str(NUM_MODES),
        "--energy_range",
        f"{ENERGY_RANGE:.2f}",
        "--seed",
        str(SEED),
        "--cpu",
        str(CPU),
        "--cnn_scoring",
        "rescore",
        "-o",
        output,
    ]


def write_shell(path: Path, specs: list[RunSpec]) -> None:
    """Bash script of the eight GNINA commands. Receptor and ligands are local filenames."""
    lines = [
        "#!/usr/bin/env bash",
        "# GNINA replay of the eight GPR68 runs. NOT executed by the smina pipeline.",
        f"# Binary: {GNINA_URL}",
        "# CNN scoring is the only addition relative to the smina commands.",
        f"# Receptor pH {PH_PRIMARY} (OpenBabel). Seed {SEED}.",
        "set -euo pipefail",
        'cd "$(dirname "$0")"',
        "RECEPTOR=${RECEPTOR:-receptor_pH6.8.pdbqt}",
        "mkdir -p gnina_out",
        "",
    ]
    for spec in specs:
        ligand = f"{spec.ligand}.pdbqt"
        output = f"gnina_out/{spec.ligand}_p{spec.pocket_id}.sdf"
        argv = gnina_argv(spec, "$RECEPTOR", ligand, output)
        lines.append(" ".join(argv))
        lines.append("")
    path.write_text("\n".join(lines))
    path.chmod(0o755)


def write_notebook(path: Path, specs: list[RunSpec]) -> None:
    """Colab notebook with the same eight commands."""
    commands = []
    for spec in specs:
        argv = gnina_argv(
            spec,
            "receptor_pH6.8.pdbqt",
            f"{spec.ligand}.pdbqt",
            f"gnina_out/{spec.ligand}_p{spec.pocket_id}.sdf",
        )
        commands.append(" ".join(argv))
    command_block = "\n".join(commands)
    intro = "\n".join(
        [
            "# GPR68 — eight GNINA replays",
            "",
            "These eight commands dock Ogerin, MS48107, lorazepam and",
            "ZINC32547799 into pocket 1 and pocket 2 of PDB 8Z68 chain R.",
            "",
            "Scores already produced in this project used **smina**",
            "(Vina 1.1.2 scoring) on a machine with no GPU.",
            f"This notebook is the GPU replay. GNINA {GNINA_VERSION} uses the",
            "same box, exhaustiveness, seed and Vina search, then",
            "CNN-rescores (`--cnn_scoring rescore`).",
            "A GNINA affinity is not a smina number.",
            "",
            "Upload next to this notebook:",
            "",
            f"- `receptor_pH6.8.pdbqt` (OpenBabel, pH {PH_PRIMARY})",
            "- `ogerin.pdbqt`, `ms48107.pdbqt`, `lorazepam.pdbqt`, `zinc32547799.pdbqt`",
            "",
            f"Runtime: Colab GPU. Binary: `{GNINA_URL}`.",
            "",
        ]
    )
    setup = f"""import os, pathlib, stat, urllib.request
url = {GNINA_URL!r}
dest = pathlib.Path("gnina")
if not dest.exists():
    urllib.request.urlretrieve(url, dest)
dest.chmod(dest.stat().st_mode | stat.S_IEXEC)
os.makedirs("gnina_out", exist_ok=True)
print("gnina binary ready", dest.stat().st_size)
"""
    run = f"""import subprocess, pathlib
commands = r'''{command_block}'''.strip().splitlines()
for command in commands:
    print(command)
    subprocess.run(command.split(), check=True)
print("eight GNINA runs finished; CNN scores are in gnina_out/")
"""
    notebook = {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "pygments_lexer": "ipython3"},
        },
        "cells": [
            _markdown(intro),
            _code(setup),
            _code(run),
        ],
    }
    path.write_text(json.dumps(notebook, indent=2) + "\n")


def _markdown(source: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": _lines(source)}


def _code(source: str) -> dict:
    return {
        "cell_type": "code",
        "metadata": {},
        "execution_count": None,
        "outputs": [],
        "source": _lines(source),
    }


def _lines(source: str) -> list[str]:
    raw = source.splitlines(keepends=True)
    return raw or [""]
