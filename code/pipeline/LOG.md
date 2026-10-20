# Build log

## Phase A — ledger reset (2026-10-04)

`governance/run_ledger.jsonl` was cleared of its 2 example `example-linear` lines before any real run. Those lines had `git_commit` `nogit`. Backup: `/tmp/ps-example-ledger.bak`. Clearing example data before the first real run is the exception. The append-only rule binds from the next line written by `run_logged()`.

Phase 0's exit is not met: the eight requested docking runs have not been logged, and a same-seed repeat has not been shown.

## Governance sweep (2026-10-04)

Quote checker, `KIT.md`, assumption register, and `FINDINGS.md`.

`tools/check_evidence.py` on the five notes outside the repo: 0 cards, 0 quote callouts, 0 bib keys, 0 FAIL, 6 WARN. Each warning is a missing bibliography. No card was invented.

`just` is not on PATH (`command not found`, exit 127). The tier-0 steps were run with the same `uv run` commands the justfile names. At the snapshot after the register was brought in line with the tags: ruff format would reformat 11 files; ruff check reported 52 errors; pyright reported 17 errors; `pytest -m "not slow"` passed; `check_ledger.py` printed `ledger OK: 1 lines (no committed version)`; `lint_tags.py` printed `lint_tags OK`. The failures are in cluster code and in `smoke.py`, which still imports `clusters.example`. Those paths were not edited from this track.

The one ledger line is `m1-ligand-harvest`, status ok, `git_commit` `nogit`. At the checker snapshot `results/docking/`, `results/pocket/`, and `results/ml_audit/` were empty. Pocket files (`docking_box.json`, `pockets.json`, `histidines.json`, `README.md`, `topology.png`) appeared immediately afterwards and are what `FINDINGS.md` uses. Docking scores and the ML audit were still absent. Assumption A10 is tagged for two different quantities; the register records the collision and does not renumber it. No row is `cited`.

## Consolidation (2026-10-04, later the same day)

The eight smina runs are on the ledger, still with `git_commit` `nogit`. Pocket 1 was diagnosed and not re-docked: the box is on the P2Rank centroid, and the control's better scores are a property of this conformation plus the open groove. A10's Morgan fingerprint is now A32; A11's Meeko flag is now A33. `lint_tags.py` prints `lint_tags OK`. `smoke.py` no longer imports `clusters.example`. The decision report was re-rendered. No row is `cited`. The current one-page summary is `FINDINGS.md`.
