# Eight docking runs

Engine: **smina** (build November 2017), scoring **Vina 1.1.2**.
GNINA was not run. `gnina_runs.sh` and `gnina_colab.ipynb`
repeat these eight jobs with `--cnn_scoring rescore` on a GPU.
A GNINA number is not the number in the table below.

Receptor: `receptor_pH6.8.pdbqt`, OpenBabel, pH 6.8,
PDB 8Z68 chain R (assumption A5).
Ligand 3D: RDKit ETKDGv3 seed 1, MMFF94, meeko PDBQT (A10).

Settings held fixed (A1, A2, A6–A9): box edge 24.00 Å,
exhaustiveness 16, seed 1, cpu 1, num_modes 9,
energy_range 3.00 kcal/mol.
The only change between the eight runs is the box centre.

Each smina log had to echo `Using random seed: 1`.
A ninth run repeated lorazepam pocket 1
with config hash `795d0fb0e20df91537362f8277815b8a0a39ac0ba662e4fb757c811241903fb6`
and reproduced the same mode table. See `determinism.json`.

## Scores

| ligand | pocket | role | best score (kcal/mol) | seconds | engine |
| --- | --- | --- | --- | --- | --- |
| lorazepam | 1 | primary | -2.54612637 | 198.8 | smina (Vina 1.1.2) |
| lorazepam | 2 | negative_control | -8.57495213 | 134.9 | smina (Vina 1.1.2) |
| ms48107 | 1 | primary | 0.332255006 | 290.3 | smina (Vina 1.1.2) |
| ms48107 | 2 | negative_control | -9.85403347 | 186.3 | smina (Vina 1.1.2) |
| ogerin | 1 | primary | -5.25780487 | 112.0 | smina (Vina 1.1.2) |
| ogerin | 2 | negative_control | -8.57721233 | 92.8 | smina (Vina 1.1.2) |
| zinc32547799 | 1 | primary | -5.06354856 | 108.2 | smina (Vina 1.1.2) |
| zinc32547799 | 2 | negative_control | -8.62334538 | 87.0 | smina (Vina 1.1.2) |

Full mode tables: `scores_modes.csv`. One row per run: `scores.csv`.

Example command (first row). The other seven swap only the centre:

```
.pixi/envs/default/bin/smina -r data/pocket/receptor_pH6.8.pdbqt -l data/docking/ligands/lorazepam.pdbqt --center_x 145.67 --center_y 128.56 --center_z 99.49 --size_x 24.00 --size_y 24.00 --size_z 24.00 --exhaustiveness 16 --num_modes 9 --energy_range 3.00 --seed 1 --cpu 1 -o results/docking/runs/lorazepam_p1/out.pdbqt
```

Paths are relative to `code/pipeline` after `pixi install`. The ledger and `determinism.json` still store the original command lines from the machine that produced these scores. Those records were not rewritten.

## Site discrimination

Pocket 2 is the lipid-facing groove on the outer face of the bundle.
It is a negative control, not a second candidate site.
In the membrane that groove is occupied by phospholipid.

Pocket 1 scored better (more negative) for: none.
Pocket 1 did not score better for: lorazepam, ms48107, ogerin, zinc32547799.
Mean (pocket 1 − pocket 2) = 5.774 kcal/mol.
Negative means pocket 1 scored better.
Exploratory description of four compounds. Not a claim.

## Ogerin and ZINC32547799

Positional isomers (ortho versus meta hydroxymethyl).
Pocket 1 best scores differ by -0.1942563100000001 kcal/mol.
Hydroxymethyl oxygens in the two best pocket-1 poses are 18.181702835543195 Å apart.
Scores differ at pocket 1: True.

## Time

Mean wall time per run (one ligand, one pocket, one state, one thread):
151.3 s (min 87.0, max 290.3).
