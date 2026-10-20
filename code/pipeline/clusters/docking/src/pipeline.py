"""Run the eight smina dockings and write the score table.

.venv/bin/python -m clusters.docking.src.pipeline
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from clusters.docking.src.gnina import write_notebook, write_shell
from clusters.docking.src.interpret import discrimination, isomer_resolution, oxygen_distance, seconds_per_run
from clusters.docking.src.ligands import all_smiles, write_ligand_files
from clusters.docking.src.plan import RunSpec, plan_runs
from clusters.docking.src.settings import ENGINE, ENGINE_SCORING, SEED
from clusters.docking.src.smina import docking_config, execute, oxygen_xyz
from clusters.pocket.src.pipeline import main as pocket_main
from core.config import config_hash
from core.errors import ContractViolation
from core.ledger import read_ledger

REPO = Path(__file__).resolve().parents[3]
LEDGER = REPO / "governance" / "run_ledger.jsonl"
RECEPTOR = REPO / "data" / "pocket" / "receptor_pH6.8.pdbqt"
LIGAND_DIR = REPO / "data" / "docking" / "ligands"
RESULTS = REPO / "results" / "docking"
RUNS = RESULTS / "runs"

SCORE_FIELDS = [
    "engine",
    "scoring",
    "ligand",
    "pubchem_cid",
    "pocket_id",
    "pocket_role",
    "ph",
    "center_x",
    "center_y",
    "center_z",
    "size_x",
    "size_y",
    "size_z",
    "exhaustiveness",
    "seed",
    "cpu",
    "num_modes",
    "energy_range",
    "best_score_kcal_mol",
    "n_modes",
    "seconds",
    "config_hash",
    "run_id",
]


def main() -> None:
    if not RECEPTOR.is_file():
        pocket_main()
    if not RECEPTOR.is_file():
        raise ContractViolation(f"receptor PDBQT missing after pocket pipeline: {RECEPTOR}")
    smiles = all_smiles(REPO / "data" / "docking" / "ms48107_pubchem.json")
    ligands = {
        name: write_ligand_files(name, smile, LIGAND_DIR, seed=SEED)[1]
        for name, smile in sorted(smiles.items())
    }
    specs = plan_runs(seed=SEED)
    if len(specs) != 8:
        raise ContractViolation(f"expected 8 runs, planned {len(specs)}")
    rows = [_one(spec, ligands[spec.ligand], RUNS / f"{spec.ligand}_p{spec.pocket_id}") for spec in specs]
    repeat_spec = specs[0]
    repeat = _one(
        repeat_spec,
        ligands[repeat_spec.ligand],
        RUNS / f"{repeat_spec.ligand}_p{repeat_spec.pocket_id}_repeat",
    )
    _require_repeat(rows[0], repeat)
    oxygen_gap = _isomer_oxygen_distance(rows)
    resolution = isomer_resolution(rows, oxygen_gap)
    site = discrimination(rows)
    timing = seconds_per_run(rows)
    _write_csv(RESULTS / "scores.csv", rows, SCORE_FIELDS)
    _write_csv(
        RESULTS / "scores_modes.csv",
        _mode_rows(rows),
        ["engine", "ligand", "pocket_id", "mode", "affinity_kcal_mol", "rmsd_lb", "rmsd_ub", "config_hash"],
    )
    _write_json(RESULTS / "determinism.json", {"original": rows[0], "repeat": repeat, "match": True})
    _write_json(
        RESULTS / "interpretation.json",
        {"discrimination": site, "isomers": resolution, "seconds_per_run": timing},
    )
    write_shell(RESULTS / "gnina_runs.sh", specs)
    write_notebook(RESULTS / "gnina_colab.ipynb", specs)
    _copy_receptor_for_replay()
    _write_readme(rows, site, resolution, timing)
    print(f"eight smina runs written to {RESULTS / 'scores.csv'}")
    print(f"seconds per run mean={timing['mean_s']:.1f}")
    print(f"isomer pocket-1 score difference={resolution['pocket_1_score_difference']}")


def _one(spec: RunSpec, ligand: Path, directory: Path) -> dict[str, Any]:
    output = directory / "out.pdbqt"
    log_path = directory / "smina.log"
    result = execute(spec, RECEPTOR, ligand, output, log_path, LEDGER)
    cfg = docking_config(spec)
    line = _ledger_line_for_output(output)
    params = cfg.params
    modes = result["modes"]
    if not isinstance(modes, list) or not modes:
        raise ContractViolation(f"no modes recorded for {spec.ligand} pocket {spec.pocket_id}")
    return {
        "engine": ENGINE,
        "scoring": ENGINE_SCORING,
        "ligand": spec.ligand,
        "pubchem_cid": spec.pubchem_cid,
        "pocket_id": spec.pocket_id,
        "pocket_role": result["pocket_role"],
        "ph": params["ph"],
        "center_x": params["center_x"],
        "center_y": params["center_y"],
        "center_z": params["center_z"],
        "size_x": params["box_edge_a"],
        "size_y": params["box_edge_a"],
        "size_z": params["box_edge_a"],
        "exhaustiveness": spec.exhaustiveness,
        "seed": spec.seed,
        "cpu": params["cpu"],
        "num_modes": params["num_modes"],
        "energy_range": params["energy_range"],
        "best_score_kcal_mol": result["best_score_kcal_mol"],
        "n_modes": len(modes),
        "seconds": result["seconds"],
        "config_hash": config_hash(cfg),
        "run_id": line["run_id"],
        "modes": modes,
        "output": str(output),
        "command": result["command"],
    }


def _ledger_line_for_output(output: Path) -> dict[str, Any]:
    needle = str(output)
    matches = []
    for line in read_ledger(LEDGER):
        result = line.get("result")
        if isinstance(result, dict) and needle in json.dumps(result.get("command")):
            matches.append(line)
    if not matches:
        raise ContractViolation(f"no ledger line contains the output path {output}")
    chosen = matches[-1]
    if chosen["status"] != "ok":
        raise ContractViolation(f"ledger line for {output} is not ok")
    rebuilt = config_hash(docking_config(_spec_from_line(chosen)))
    if chosen["config_hash"] != rebuilt:
        raise ContractViolation(f"ledger config hash disagrees with the rebuilt config for {output}")
    return chosen


def _spec_from_line(line: dict[str, Any]) -> RunSpec:
    params = line["config"]["params"]
    return RunSpec(
        ligand=str(params["ligand"]),
        pubchem_cid=str(params["pubchem_cid"]),
        pocket_id=int(params["pocket_id"]),
        exhaustiveness=int(params["exhaustiveness"]),
        seed=int(line["config"]["seed"]),
    )


def _require_repeat(original: dict[str, Any], repeat: dict[str, Any]) -> None:
    if original["config_hash"] != repeat["config_hash"]:
        raise ContractViolation("repeat run config hash differs from the original")
    if original["modes"] != repeat["modes"]:
        raise ContractViolation(
            f"repeat scores differ for {original['ligand']} pocket {original['pocket_id']}: "
            f"{original['modes']} vs {repeat['modes']}"
        )


def _isomer_oxygen_distance(rows: list[dict[str, Any]]) -> float:
    poses = {}
    for row in rows:
        if row["ligand"] in {"ogerin", "zinc32547799"} and int(row["pocket_id"]) == 1:
            poses[row["ligand"]] = oxygen_xyz(Path(row["output"]).read_text())
    return oxygen_distance(poses["ogerin"], poses["zinc32547799"])


def _mode_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    flat = []
    for row in rows:
        for mode in row["modes"]:
            flat.append(
                {
                    "engine": ENGINE,
                    "ligand": row["ligand"],
                    "pocket_id": row["pocket_id"],
                    "mode": mode["mode"],
                    "affinity_kcal_mol": mode["affinity_kcal_mol"],
                    "rmsd_lb": mode["rmsd_lb"],
                    "rmsd_ub": mode["rmsd_ub"],
                    "config_hash": row["config_hash"],
                }
            )
    return flat


def _copy_receptor_for_replay() -> None:
    """The GNINA script looks for the receptor next to itself. Copy, do not symlink out of data/."""
    dest = RESULTS / "receptor_pH6.8.pdbqt"
    dest.write_bytes(RECEPTOR.read_bytes())
    for ligand in sorted(LIGAND_DIR.glob("*.pdbqt")):
        (RESULTS / ligand.name).write_bytes(ligand.read_bytes())


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row[key] for key in fields})


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _write_readme(
    rows: list[dict[str, Any]],
    site: dict[str, Any],
    resolution: dict[str, Any],
    timing: dict[str, float],
) -> None:
    header = (
        "| ligand | pocket | role | best score (kcal/mol) | seconds | engine |\n"
        "| --- | --- | --- | --- | --- | --- |\n"
    )
    body = ""
    for row in rows:
        body += (
            f"| {row['ligand']} | {row['pocket_id']} | {row['pocket_role']} | "
            f"{row['best_score_kcal_mol']} | {float(row['seconds']):.1f} | smina (Vina 1.1.2) |\n"
        )
    command = " ".join(str(part) for part in rows[0]["command"])
    prefer = ", ".join(site["pocket_1_better_than_pocket_2"]) or "none"
    worse = ", ".join(site["pocket_1_worse_or_equal"]) or "none"
    delta = site["mean_delta_p1_minus_p2"]
    gap = resolution["hydroxymethyl_oxygen_distance_A"]
    score_gap = resolution["pocket_1_score_difference"]
    repeated = rows[0]
    text = "\n".join(
        [
            "# Eight docking runs",
            "",
            "Engine: **smina** (build November 2017), scoring **Vina 1.1.2**.",
            "GNINA was not run. `gnina_runs.sh` and `gnina_colab.ipynb`",
            "repeat these eight jobs with `--cnn_scoring rescore` on a GPU.",
            "A GNINA number is not the number in the table below.",
            "",
            "Receptor: `receptor_pH6.8.pdbqt`, OpenBabel, pH 6.8,",
            "PDB 8Z68 chain R (assumption A5).",
            f"Ligand 3D: RDKit ETKDGv3 seed {SEED}, MMFF94, meeko PDBQT (A10).",
            "",
            "Settings held fixed (A1, A2, A6–A9): box edge 24.00 Å,",
            f"exhaustiveness 16, seed {SEED}, cpu 1, num_modes 9,",
            "energy_range 3.00 kcal/mol.",
            "The only change between the eight runs is the box centre.",
            "",
            f"Each smina log had to echo `Using random seed: {SEED}`.",
            f"A ninth run repeated {repeated['ligand']} pocket {repeated['pocket_id']}",
            f"with config hash `{repeated['config_hash']}`",
            "and reproduced the same mode table. See `determinism.json`.",
            "",
            "## Scores",
            "",
            header.rstrip("\n"),
            body.rstrip("\n"),
            "",
            "Full mode tables: `scores_modes.csv`. One row per run: `scores.csv`.",
            "",
            "Example command (first row). The other seven swap only the centre:",
            "",
            "```",
            command,
            "```",
            "",
            "## Site discrimination",
            "",
            "Pocket 2 is the lipid-facing groove on the outer face of the bundle.",
            "It is a negative control, not a second candidate site.",
            "In the membrane that groove is occupied by phospholipid.",
            "",
            f"Pocket 1 scored better (more negative) for: {prefer}.",
            f"Pocket 1 did not score better for: {worse}.",
            f"Mean (pocket 1 − pocket 2) = {delta:.3f} kcal/mol.",
            "Negative means pocket 1 scored better.",
            "Exploratory description of four compounds. Not a claim.",
            "",
            "## Ogerin and ZINC32547799",
            "",
            "Positional isomers (ortho versus meta hydroxymethyl).",
            f"Pocket 1 best scores differ by {score_gap} kcal/mol.",
            f"Hydroxymethyl oxygens in the two best pocket-1 poses are {gap} Å apart.",
            f"Scores differ at pocket 1: {resolution['scores_differ_at_pocket_1']}.",
            "",
            "## Time",
            "",
            "Mean wall time per run (one ligand, one pocket, one state, one thread):",
            f"{timing['mean_s']:.1f} s (min {timing['min_s']:.1f}, max {timing['max_s']:.1f}).",
            "",
        ]
    )
    (RESULTS / "README.md").write_text(text)


if __name__ == "__main__":
    main()
