"""One smina docking run: command, score table, ledger entry.

The binary is smina (November 2017, Vina 1.1.2 scoring). GNINA is not invoked.
"""

from __future__ import annotations

import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from clusters.docking.src.plan import RunSpec, run_config
from clusters.docking.src.settings import CPU, ENERGY_RANGE, ENGINE, ENGINE_SCORING, NUM_MODES, SEED, SMINA
from clusters.pocket.src.box import BOX_EDGE_A, POCKET_CENTRES, POCKET_ROLES
from clusters.pocket.src.protonate import PH_PRIMARY
from core.config import ExperimentConfig
from core.errors import ContractViolation
from core.hashing import sha256_file, sha256_json
from core.ledger import run_logged

_RESULT = re.compile(r"REMARK VINA RESULT:\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)")
_AFFINITY = re.compile(r"REMARK minimizedAffinity\s+(-?\d+(?:\.\d+)?)")
_LOG_ROW = re.compile(r"^\s*(\d+)\s+(-?\d+\.\d+)\s+(\d+\.\d+)\s+(\d+\.\d+)\s*$", re.MULTILINE)
_SEED_LINE = re.compile(r"Using random seed:\s+(-?\d+)")


@dataclass(frozen=True)
class ModeScore:
    mode: int
    affinity: float
    rmsd_lb: float
    rmsd_ub: float

    def as_dict(self) -> dict[str, float | int]:
        return {
            "mode": self.mode,
            "affinity_kcal_mol": self.affinity,
            "rmsd_lb": self.rmsd_lb,
            "rmsd_ub": self.rmsd_ub,
        }


def docking_config(spec: RunSpec) -> ExperimentConfig:
    """Logged config. The pocket centre is in the params, not only the pocket id."""
    if spec.seed == 0:
        raise ContractViolation("seed 0 is rejected; smina would not be deterministic")
    base = run_config(spec)
    centre = POCKET_CENTRES[spec.pocket_id]
    params = dict(base.params)
    params.update(
        {
            "center_x": centre[0],
            "center_y": centre[1],
            "center_z": centre[2],
            "ph": PH_PRIMARY,
            "cpu": CPU,
            "num_modes": NUM_MODES,
            "energy_range": ENERGY_RANGE,
            "engine": ENGINE,
        }
    )
    return base.model_copy(update={"params": params})


def smina_command(
    receptor: Path,
    ligand: Path,
    spec: RunSpec,
    output: Path,
) -> list[str]:
    """The exact argv. Pocket 1 and pocket 2 differ only in the three centre flags."""
    if spec.seed != SEED:
        raise ContractViolation(f"run seed {spec.seed} does not match the registered seed {SEED}")
    if not SMINA.is_file():
        raise ContractViolation(f"smina binary is missing: {SMINA}")
    centre = POCKET_CENTRES[spec.pocket_id]
    return [
        str(SMINA),
        "-r",
        str(receptor),
        "-l",
        str(ligand),
        "--center_x",
        _num(centre[0]),
        "--center_y",
        _num(centre[1]),
        "--center_z",
        _num(centre[2]),
        "--size_x",
        _num(BOX_EDGE_A),
        "--size_y",
        _num(BOX_EDGE_A),
        "--size_z",
        _num(BOX_EDGE_A),
        "--exhaustiveness",
        str(spec.exhaustiveness),
        "--num_modes",
        str(NUM_MODES),
        "--energy_range",
        _num(ENERGY_RANGE),
        "--seed",
        str(spec.seed),
        "--cpu",
        str(CPU),
        "-o",
        str(output),
    ]


def parse_scores(pdbqt_text: str, log_text: str | None = None) -> tuple[ModeScore, ...]:
    """Scores from this smina build's ``minimizedAffinity`` remarks, or classic Vina remarks.

    Smina 2017 writes ``REMARK minimizedAffinity`` in the PDBQT and a 1-decimal
    table in the log. RMSD lower/upper bounds come from that log table.
    """
    affinities = [float(value) for value in _AFFINITY.findall(pdbqt_text)]
    if affinities:
        rmsds = _log_rmsds(log_text, len(affinities))
        return tuple(
            ModeScore(mode=index, affinity=affinity, rmsd_lb=rmsd[0], rmsd_ub=rmsd[1])
            for index, (affinity, rmsd) in enumerate(zip(affinities, rmsds, strict=True), start=1)
        )
    vina = _RESULT.findall(pdbqt_text)
    if vina:
        return tuple(
            ModeScore(mode=index, affinity=float(row[0]), rmsd_lb=float(row[1]), rmsd_ub=float(row[2]))
            for index, row in enumerate(vina, start=1)
        )
    raise ContractViolation("smina output has neither minimizedAffinity nor VINA RESULT remarks")


def _log_rmsds(log_text: str | None, n_modes: int) -> tuple[tuple[float, float], ...]:
    if log_text is None:
        raise ContractViolation("smina log is required to read RMSD columns")
    rows = [(float(match.group(3)), float(match.group(4))) for match in _LOG_ROW.finditer(log_text)]
    if len(rows) != n_modes:
        raise ContractViolation(f"log has {len(rows)} score rows and the PDBQT has {n_modes} affinities")
    return tuple(rows)


def oxygen_xyz(pdbqt_text: str) -> tuple[tuple[float, float, float], ...]:
    """Oxygen coordinates of the first pose (atom type OA)."""
    coords: list[tuple[float, float, float]] = []
    for line in pdbqt_text.splitlines():
        if line.startswith("ENDMDL"):
            break
        if not line.startswith(("ATOM", "HETATM")) or len(line) < 54:
            continue
        atom_type = line[77:79].strip() if len(line) >= 79 else ""
        if atom_type != "OA":
            continue
        coords.append((float(line[30:38]), float(line[38:46]), float(line[46:54])))
    return tuple(coords)


def execute(
    spec: RunSpec,
    receptor: Path,
    ligand: Path,
    output: Path,
    log_path: Path,
    ledger_path: Path,
    echo: bool = False,
) -> dict[str, object]:
    """Dock one ligand into one pocket and append one ledger line."""
    cfg = docking_config(spec)
    command = smina_command(receptor, ligand, spec, output)

    def _run() -> dict[str, object]:
        output.parent.mkdir(parents=True, exist_ok=True)
        started = time.perf_counter()
        chunks: list[str] = []
        with log_path.open("w", encoding="utf-8") as handle:
            proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            if proc.stdout is None:
                raise ContractViolation("smina stdout pipe was not created")
            for line in proc.stdout:
                handle.write(line)
                chunks.append(line)
                if echo:
                    print(line, end="")
            returncode = proc.wait()
        seconds = time.perf_counter() - started
        log_text = "".join(chunks)
        if returncode != 0:
            tail = "\n".join(log_text.splitlines()[-20:])
            raise ContractViolation(
                f"smina exited {returncode} for {spec.ligand} pocket {spec.pocket_id}: {tail}"
            )
        _require_seed(log_text, spec.seed)
        if not output.is_file():
            raise ContractViolation(f"smina wrote no output file at {output}")
        modes = parse_scores(output.read_text(), log_text)
        manifest = sha256_json(
            {
                "ligand_pdbqt": sha256_file(ligand),
                "receptor_pdbqt": sha256_file(receptor),
            }
        )
        return {
            "engine": ENGINE,
            "scoring": ENGINE_SCORING,
            "ligand": spec.ligand,
            "pubchem_cid": spec.pubchem_cid,
            "pocket_id": spec.pocket_id,
            "pocket_role": POCKET_ROLES[spec.pocket_id],
            "best_score_kcal_mol": modes[0].affinity,
            "modes": [mode.as_dict() for mode in modes],
            "seconds": seconds,
            "command": command,
            "seed_echo_ok": True,
            "data_manifest_hash": manifest,
        }

    return run_logged(cfg, _run, ledger_path=ledger_path)


def _require_seed(log_text: str, seed: int) -> None:
    match = _SEED_LINE.search(log_text)
    if match is None:
        raise ContractViolation("smina log does not report the random seed it used")
    used = int(match.group(1))
    if used != seed:
        raise ContractViolation(f"smina used seed {used}, requested {seed}")


def _num(value: float) -> str:
    return f"{value:.2f}"
