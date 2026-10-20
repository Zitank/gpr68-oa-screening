# docking

Eight smina runs: four reference ligands into pockets 1 and 2.

## Built
- run plan (eight specs)
- ligand PDBQT via RDKit and meeko
- smina invocation through `run_logged`
- GNINA replay script and Colab notebook (not executed)

Assumptions: A1 (box edge), A2 (exhaustiveness 16), A6 (seed 1), A7 (cpu 1), A8 (num_modes 9), A9 (energy window 3 kcal/mol), A10 (ETKDGv3 + MMFF94), A11 (rigid macrocycles).
