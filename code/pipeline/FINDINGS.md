# Findings

Exploratory note for the GPR68 osteoarthritis sprint. This is not a claim. A human has not verified any of it against the papers, and `governance/references.bib` does not exist. No assumption is marked cited. The ledger stamp `git_commit` is `nogit` because this repo has no commit yet. That was left as it is.

Every docking number below is smina (November 2017 build, Vina 1.1.2 scoring). GNINA was not run. `results/docking/gnina_runs.sh` and `results/docking/gnina_colab.ipynb` repeat the same eight jobs with CNN rescoring on a GPU.

## The eight docking runs

Receptor: PDB 8Z68 chain R only, residues 13–297, 2174 atoms, OpenBabel protonation at pH 6.8. Box 24 Å, exhaustiveness 16, seed 1, one thread. Pocket 1 centre (145.67, 128.56, 99.49) is the proton-sensing candidate. Pocket 2 centre (129.32, 131.62, 117.61) is the lipid-facing groove, a site-discrimination negative control.

Best mode, kcal/mol. A more negative score is a better Vina score. Pocket 2 is better for every compound. Mean (pocket 1 − pocket 2) = +5.77 kcal/mol.

| Compound | Pocket 1 | Pocket 2 |
| --- | ---: | ---: |
| Ogerin | −5.258 | −8.577 |
| MS48107 | +0.332 | −9.854 |
| Lorazepam | −2.546 | −8.575 |
| ZINC32547799 | −5.064 | −8.623 |

A positive score means the ligand could not be placed without a clash. MS48107 at pocket 1 is that case. These are the original eight runs. The box was already on the cavity, so the pocket 1 runs were left as they are.

Ogerin and ZINC32547799 are resolved. At pocket 1 their best scores differ by 0.194 kcal/mol, and the hydroxymethyl oxygens in those two best poses are 18.2 Å apart. That is two different placements, not one shared pose.

## Why pocket 1 lost

This is a real observation about the active-state conformation, with a Vina bias toward the more open groove. It is not a box-placement error, and it is not Gs filling the site.

The P2Rank point centroid and the box centre differ by 0.005 Å at pocket 1 and 0.006 Å at pocket 2. All 28 pocket-1 points, and all 36 pocket-2 points, sit inside the 24 Å cube. Recentring would move the box by less than a hundredth of an angstrom.

Docking used chain R alone. Zero heavy atoms from Gs chains A, B and G fall inside either box or within 8 Å of either centroid. Pocket 1 is on the extracellular side: +15.1 Å from the chain-R Cα centroid along the axis that runs from Gα through the receptor toward the N-terminus (residue 13 is +28.7 Å on that axis; residue 297 is −16.9 Å). His20 and His269 sit on that same side. Pocket 2 is −5.1 Å along the axis and 10.5 Å off it.

Free volume, 1 Å grid, a cell free when it is more than 2.0 Å from every chain-R heavy atom: pocket 1 is 0.342 (5337/15625), pocket 2 is 0.559 (8737/15625). The pocket 1 centre is 2.72 Å from the nearest heavy atom; pocket 2 is 4.05 Å. Receptor heavy atoms inside the box: 643 versus 409. Within 8 Å of the point centroid: 105 versus 69. Cells more than 3 Å from any heavy atom: 8.9% of the pocket 1 box and 36.5% of the pocket 2 box. Almost all of the free space opens onto solvent. Enclosed free cells are 49 and 39, and they are not the pocket centre. The pocket 1 point cloud is a flat patch. The four pocket 1 poses sit 9.7–14.8 Å from the box centre; the pocket 2 poses sit 3.2–9.0 Å from theirs.

So the candidate site in this conformation is a shallow extracellular patch, too tight for these four ligands, and the control is a more open surface groove. Vina is known to reward buried hydrophobic contact in that kind of groove. The +5.77 kcal/mol gap is not evidence that pocket 2 is the proton-sensing site. P2Rank pockets are candidate sites, not binding sites. Full grid counts are in `results/pocket/box_diagnosis.json`.

## Protonation

OpenBabel wrote a malformed histidine for His17, His125, His175, His216 and His269: no hydrogen on ND1 or NE2, and two hydrogens on CD2, at both pH 6.8 and pH 7.4. His20 and the other seven histidines that the pH scan did flip (84, 89, 130, 159, 169, 245, 294) went from HID at pH 7.4 to HIP at pH 6.8. His20 and His269 both line pocket 1.

The docking PDBQT does not contain those extra CD2 hydrogens. OpenBabel's PDBQT writer keeps polar hydrogens only. His269's imidazole nitrogens are atom type NA, with no polar hydrogen. His20 has polar hydrogens on both nitrogens. Every partial charge in the receptor PDBQT is 0 (2601 atoms). Vina scores atom types, so those zeros do not enter the eight numbers, and they must not be reused for anything electrostatic.

The His269 defect can change a hydrogen-bond term. It does not add steric bulk, and it does not explain a positive score or a 6 kcal/mol gap that shows up for all four ligands. The coordinates were not rebuilt. Meeko still rejects the protonated PDB because every hydrogen is named H.

## Can the public tables train a model?

Not supported, as an interval, not as a yes-or-no fact. The question is Q-003. The label is the AID 2060853 Active/Inactive call (39 active, 13 inactive). Endpoints were not pooled.

The scaffold-split ROC-AUC 95% interval is 0.29–0.97, which includes 0.5. The random-split interval is 0.53–1.00, which does not. A writeup that used only the random split would look successful and would be the wrong conclusion. The scaffold-split median is 0.773. The Y-scramble null's central 95% is 0.285–0.670, and 0.773 sits above it, so there is real within-series signal. The model does not generalise across series.

The learning-curve mean ROC-AUC at train fractions 0.25, 0.40, 0.55 and 0.70 is 0.681, 0.687, 0.753, 0.742. That curve has plateaued, and the lower-percentile fit did not pass its R² gate, so no required n was identified.

Of 108 property-matched ChEMBL molecules used in place of the missing MCE library, 0 are within Morgan Tanimoto 0.40 of the patent set. That applicability number is for the substitute library, not for the MCE 5,000.

MS48107 is in ChEMBL as CHEMBL4449712. There is no preferred name. The InChIKey is KKHDNAZPEMYUNO-UHFFFAOYSA-N, the same as PubChem CID 139030523. Document CHEMBL4406806 has five rows for it, including pKb 5.85. A name search misses it. The reference table now carries that ChEMBL id.

CHEMBL4406806 has 67 molecules and 273 activity rows. CHEMBL5661984 has 29 molecules and 60 activity rows. The figures 67 and 29 are molecule counts.

## Buying compounds, and wet-lab power

These are simulations under the assumptions in `governance/assumptions.md`. They are not measurements of GPR68.

At the quoted row (prior 0.001 per compound, docking EF1% of 5, library of 5,000), the chance of at least one true hit in the top 8 by score is 6.3%, and in the top 10 it is 7.9%. An 80% chance on that row means buying 655 compounds from the ranked list, not 6–10. A diverse draw of 8 from the top 100 has a 3.5% chance, and 80% is not reached inside that review set. Across the whole prior × EF grid, the top-8 probability runs from 0 to 99.7%. Ten purchases reach 80% in only five cells, all at a prior of at least 0.5% and an EF1% of at least 12. A purchase of 6–10 is a pilot whose hit probability is the quoted-row number, unless a later docking run actually lands in that bright corner.

The calcium grid is the full Monte Carlo: 250 replicates, designs C6, C8 and C10. The layout that meets the 3-fold CI rule and 80% power for a 3-fold potency shift is 6 concentrations × 2 replicates (C6, 0.1–30 µM). Median 95% CI fold-width 2.24, power 93%. The same layout with free asymptotes has a median fold-width of 6.46, so the recommendation assumes the curve is normalised to 0 and 100. The EC50 of 1 µM is a planning truth, not a published ogerin potency.

Chondrocyte qPCR, SD 0.5 Ct on delta-Ct, 2-fold change, two-sided alpha 0.05: 6 biological replicates per group (achieved power 0.88). Bonferroni across MMP13, ADAMTS5, COL2A1 and ACAN raises that to 8 per group. The four genes are not one test.

The decision note is `results/report/GPR68_decision_report.html`. It was re-rendered from the score table, the pocket diagnosis, the ligand table, the ML audit, the purchase grid and the qPCR table. No section is a pending block. The docking folder has no AUC, EF or BEDROC file, and the note says so; those are not what the eight runs were for.

## Limits

Predicted pockets are candidate sites. Nothing here is literature-verified. The ML verdict is an interval. The receptor PDBQT has zero partial charges and a missing donor hydrogen on His269. smina produced every docking number. The ledger is not tied to a git commit.
