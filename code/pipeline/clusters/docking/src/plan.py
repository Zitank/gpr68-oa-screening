"""Enumerate the eight requested docking runs; no docking binary is invoked.

## [EXPLORATORY]
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from clusters.pocket.src.box import BOX_EDGE_A, POCKET_CENTRES
from core.config import ExperimentConfig
from core.errors import ContractViolation

# ## [ASSUMPTION: A2] smina/vina exhaustiveness for the pilot runs
EXHAUSTIVENESS: int = 16

# Identifiers resolved against PubChem; ogerin and zinc32547799 are positional isomers.
REFERENCE_LIGANDS: dict[str, str] = {
    "ogerin": "56707820",
    "ms48107": "139030523",
    "lorazepam": "3958",
    "zinc32547799": "39791182",
}

PLANNED_RUNS: int = 8


class RunSpec(BaseModel):
    """One planned docking run."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    ligand: str
    pubchem_cid: str
    pocket_id: int
    exhaustiveness: int
    seed: int


def plan_runs(seed: int = 0, exhaustiveness: int = EXHAUSTIVENESS) -> list[RunSpec]:
    """List the eight runs: sorted ligands, pocket 1 before pocket 2 per ligand."""
    if exhaustiveness < 1:
        raise ContractViolation(f"exhaustiveness must be >= 1, got {exhaustiveness}")
    specs = [
        RunSpec(
            ligand=ligand,
            pubchem_cid=REFERENCE_LIGANDS[ligand],
            pocket_id=pocket_id,
            exhaustiveness=exhaustiveness,
            seed=seed,
        )
        for ligand in sorted(REFERENCE_LIGANDS)
        for pocket_id in sorted(POCKET_CENTRES)
    ]
    if len(specs) != PLANNED_RUNS:
        raise ContractViolation(f"planned {len(specs)} runs, expected {PLANNED_RUNS}")
    return specs


def run_config(spec: RunSpec) -> ExperimentConfig:
    """Convert one run spec into a logged experiment config."""
    if spec.pocket_id not in POCKET_CENTRES:
        raise ContractViolation(f"unknown pocket_id {spec.pocket_id}; known ids: {sorted(POCKET_CENTRES)}")
    return ExperimentConfig(
        name="dock8",
        seed=spec.seed,
        mode="exploratory",
        condition_code=f"P{spec.pocket_id}",
        params={
            "ligand": spec.ligand,
            "pubchem_cid": spec.pubchem_cid,
            "pocket_id": spec.pocket_id,
            "exhaustiveness": spec.exhaustiveness,
            "box_edge_a": BOX_EDGE_A,
        },
    )
