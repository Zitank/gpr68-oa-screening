"""Re-execute one of the eight runs through ``run_logged``.

.venv/bin/python -m clusters.docking.src.rerun
"""

from __future__ import annotations

from clusters.docking.src.plan import plan_runs
from clusters.docking.src.settings import SEED
from clusters.docking.src.smina import execute
from clusters.pocket.src.pipeline import REPO
from core.errors import ContractViolation

LEDGER = REPO / "governance" / "run_ledger.jsonl"
RECEPTOR = REPO / "data" / "pocket" / "receptor_pH6.8.pdbqt"
LIGANDS = REPO / "data" / "docking" / "ligands"
OUT = REPO / "results" / "demo" / "rerun"


def main() -> None:
    """Ogerin into pocket 1, same config as the pilot, output under results/demo."""
    spec = next(item for item in plan_runs(seed=SEED) if item.ligand == "ogerin" and item.pocket_id == 1)
    ligand = LIGANDS / "ogerin.pdbqt"
    if not ligand.is_file() or not RECEPTOR.is_file():
        raise ContractViolation("ligand or receptor PDBQT is missing; run the docking pipeline first")
    print(f"re-executing {spec.ligand} pocket {spec.pocket_id} through run_logged")
    result = execute(
        spec,
        RECEPTOR,
        ligand,
        OUT / "out.pdbqt",
        OUT / "smina.log",
        LEDGER,
        echo=True,
    )
    seconds = result["seconds"]
    score = result["best_score_kcal_mol"]
    if not isinstance(seconds, float) or not isinstance(score, float):
        raise ContractViolation("smina result is missing a float score or runtime")
    print(f"engine: {result['engine']} ({result['scoring']})")
    print(f"best score: {score} kcal/mol")
    print(f"seconds: {seconds:.1f}")


if __name__ == "__main__":
    main()
