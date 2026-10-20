# Contributing

This repository is the public package for an undergraduate competition project and a later computational check. It is published by the Student Union of the International School of Medicine, Zhejiang University, under the Apache License 2.0. See [LICENSE](LICENSE).

Open an issue or a pull request on this repository. Keep changes small enough to review. Describe which file a new number comes from.

## Scientific work that would move the project

The README section "How to continue" matches the order in the slides. In short:

1. Finish the GNINA pocket-1 versus pocket-2 run. Change only the centre. CNN rescoring can disagree with the smina table in `code/pipeline/results/docking/scores.csv`.
2. Dock an inactive-state model. PDB 8Z68 is active and G-protein-bound, and pocket 1 is a shallow patch in that conformation.
3. Repair histidine protonation, including His269, before any electrostatic or CNN claim.
4. Keep AID 2060853 out of a screening model until a scaffold split excludes 0.5.
5. Treat a purchase of 6–10 compounds as a pilot. Under the stated prior and enrichment it is a 6.3% design at the top 8.
6. Add cited evidence cards. No literature quote in `paper/FINDINGS.md` is verified.
7. Run a known-versus-decoy enrichment check. The eight smina runs were not that test.

## What to leave out

Do not add secrets, `.env` files, tokens, or API keys. Do not add the raw commercial screening SDF. Derived descriptor tables already in `code/submission/` stay, because the submission README states that the raw SDF is not redistributed. Do not commit `.pixi`, `.venv`, or caches. Do not hand-edit `code/pipeline/governance/run_ledger.jsonl`. The ledger check rejects a rewritten prefix.

State simulations as simulations. The purchase, calcium, and qPCR numbers are planning calculations under written assumptions.
