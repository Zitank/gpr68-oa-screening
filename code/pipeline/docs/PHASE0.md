# Phase 0 — walking skeleton (architecture packet)

No frozen SPEC or CONTRACT tree exists yet. This file is the architect's cut of Phase 0. On conflict with a cluster `LOG.md`, this file wins. A later frozen spec would win only after the human unfreezing gate, and would be recorded under `governance/decisions/`. That tree does not exist yet. This file is the Architect's cut of the current phase into disjoint work packets.

Exit criterion:

> The eight requested docking runs (ogerin, MS48107, lorazepam, ZINC32547799, each into pocket 1 and pocket 2) are logged through `run_logged()`, and a second run with the same seed reproduces them identically.

## Fixed decisions (do not relitigate inside a packet)

- **D-1** smina is the Vina-level docking engine. GNINA command files are shipped for GPU replay.
- **D-2** Pocket 1 is the primary site. Pocket 2 is the lipid-facing negative control.
- **D-3** Bioactivity endpoints are never pooled.
- **D-4** This sprint is exploratory only. Nothing promotes to a claim.
- **D-5** uv owns Python dependencies. pixi owns external binaries (smina, R, Quarto, OpenBabel).
- Python 3.12 via `uv`. Fail loudly (`core.errors`). One phase per session.

## Shared interfaces (owned by Architect)

`core/errors.py`: `ContractViolation`, `LedgerError`, `ScopeViolation`, `NeedsSource`. `core/config.py`: frozen `ExperimentConfig` and `config_hash`. `core/ledger.py`: `run_logged` appends one JSON line per call. Workers import these; they do not redefine or edit them. If an interface is wrong, write the problem in your packet's `LOG.md` and stop that part.

`ExperimentConfig.params` is the shared parameter dict. No new config type is added for this project. Packet-owned types stay inside that packet's tree: `DockingBox` in `clusters/pocket/`, `RunSpec` in `clusters/docking/`, `ActivityRecord` in `clusters/ligand_data/`, `Split` in `clusters/ml_audit/`. Docking reads box geometry; it does not redefine it. `governance/assumptions.md` is architect-owned. Packets tag `## [ASSUMPTION: Ax]` and append rows; they do not mark a row `cited`.

## Packets

Write sets are disjoint. A path appears in one "Writes only" cell.

| Packet | Owner | Writes only | Reads |
| --- | --- | --- | --- |
| ligand_data | Cluster lead | `clusters/ligand_data/`, `results/ligand_data/` | `core/`, `governance/assumptions.md`, `governance/questions/` |
| pocket | Cluster lead | `clusters/pocket/`, `results/pocket/` | `core/`, `governance/assumptions.md`, `governance/questions/` |
| docking | Cluster lead | `clusters/docking/`, `results/docking/` | `core/`, `clusters/pocket/`, `results/ligand_data/`, `governance/assumptions.md`, `governance/questions/` |
| ml_audit | Cluster lead | `clusters/ml_audit/`, `results/ml_audit/` | `core/`, `clusters/ligand_data/`, `results/ligand_data/`, `governance/assumptions.md`, `governance/questions/` |

`ligand_data` is done when ChEMBL CHEMBL3713916 and the usable PubChem AIDs are one row per molecule–assay–endpoint, endpoints unpooled, document id retained. Paste the assertion output, not a pooled activity table.

`pocket` is done when chain R is extracted, protomers exist at pH 7.4 and pH 6.8, and `docking_box.json` reproduces pocket 1 centre (145.67, 128.56, 99.49) and pocket 2 centre (129.32, 131.62, 117.61). Paste that file's centres.

`docking` is done when the phase exit above is true: eight `run_logged()` lines and a second same-seed run with the same scores. Paste both ledger excerpts. This packet's exit is the phase exit.

`ml_audit` is done when Q-003 has a scaffold-split ROC-AUC bootstrap CI, a random-split comparison, a learning curve and a Y-scramble null. Paste the intervals. Do not paste an opinion in their place.

## Conventions for all packets

- Only touch paths in your "Writes only" column. Add `__init__.py` where needed in your own tree.
- Tag non-trivial blocks per blueprint §5, staged per Addendum C12: `## [ASSUMPTION: Ax]`, `## [EXPLORATORY]`, `## [NEEDS-SOURCE: …]`. Never a `CITE` without a key in `references.bib`.
- Never invent constants. Each one is an assumption id in `governance/assumptions.md`, or a verified citation.
- Run `uv run ruff check . && uv run ruff format --check . && uv run pytest -m "not slow"` on your tree before reporting. The venv is created by `uv sync --all-groups` at repo root (may already exist).
- Write a short `LOG.md` in your tree: what you built, what you skipped, what is NEEDS-SOURCE, which library versions you pinned and whether their API matched expectations.
