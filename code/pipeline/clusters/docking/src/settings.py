"""Frozen smina settings for the eight runs.

Only the box centre changes between runs. Every other flag is one of these values.
"""

from __future__ import annotations

from pathlib import Path

# ## [ASSUMPTION: A6] Non-zero seed. AutoDock Vina treats 0 as "draw a time-based seed".
SEED: int = 1

# ## [ASSUMPTION: A7] One thread. Multi-threaded smina does not reproduce a fixed seed.
CPU: int = 1

# ## [ASSUMPTION: A8] smina's default mode count, written into the command so it cannot drift.
NUM_MODES: int = 9

# ## [ASSUMPTION: A9] smina's default energy window (kcal/mol), written into the command.
ENERGY_RANGE: float = 3.0

# ## [ASSUMPTION: A10] Ligand 3D is one ETKDGv3 conformer (seed A6) minimised with MMFF94.
# 500 iterations is enough for these four molecules to converge (status 0).
# Protonation is RDKit AddHs of the given SMILES, not an OpenBabel pH scan.
MMFF_MAX_ITERS: int = 500

# ## [ASSUMPTION: A33] Meeko keeps macrocycles rigid.
# Opening a 7-membered ring (lorazepam) emits CG0/G0 glue types, which smina 2017 rejects.
RIGID_MACROCYCLES: bool = True

# pixi install from the pipeline root creates this binary. The environment is not in the repository.
_PIPELINE = Path(__file__).resolve().parents[3]
SMINA = _PIPELINE / ".pixi" / "envs" / "default" / "bin" / "smina"
ENGINE = "smina"
ENGINE_SCORING = "vina-1.1.2"
