# GPR68 screening

Can an AI-assisted, structure-informed screening workflow identify small-molecule GPR68 modulators that protect cartilage under OA-associated acidic and inflammatory conditions? Walking skeleton. See `docs/PHASE0.md` and `AGENTS.md`.

## Setup

```bash
uv sync --all-groups
# if `just` is missing:
uvx --from rust-just just <recipe>
just hooks
```

## Run

```bash
just smoke     # two logged runs, determinism check
just tier0     # every-commit checks
just ledger-check
uv run python tools/lint_tags.py
uv run python tools/check_evidence.py   # quotes vs ../sources and ../lit
```

## Layout

- `core/` — errors, config, hashing, ledger
- `clusters/` — `ligand_data`, `pocket`, `docking`, `ml_audit`
- `tools/` — ledger, tag, idea, and literature checks
- `governance/` — gates, assumptions, questions; the ledger appears on the first `run_logged()` call
- `ideas/` — append-only idea log
- `literature/` — protocol and queries
- `docs/PHASE0.md` — packets and exit criterion
- `COMPUTE.md` — machine and budget
- `AGENTS.md` — roles and rules
- `KIT.md` — repo layout and the vault paths for papers

No frozen SPEC tree yet. `docs/PHASE0.md` is the phase packet and wins on conflict with cluster notes until a human freezes a spec.

## Published paths

smina and OpenBabel are not stored in this repository. From this directory, `pixi install` places them at `.pixi/envs/default/bin/smina` and `.pixi/envs/default/bin/obabel`. The P2Rank points file is `data/pocket/8Z68_GPR68_only.pdb_points.pdb`. `uv run python smoke.py` checks the ledger and does not call those binaries. Full GNINA redocking is a separate GPU job.

