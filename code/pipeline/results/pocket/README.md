# Pocket module

Engine for protonation and the receptor PDBQT: **OpenBabel 3.2.1**.
No docking scores in this folder.

Primary state pH 6.8 (assumption A5).
Comparison state pH 7.4.
Histidines whose state changed: HIS20 HID→HIP, HIS84 HID→HIP, HIS89 HID→HIP, HIS130 HID→HIP, HIS159 HID→HIP, HIS169 HID→HIP, HIS245 HID→HIP, HIS294 HID→HIP.
Histidines with no hydrogen on ND1 or NE2 at either pH: HIS17, HIS125, HIS175, HIS216, HIS269.

OpenBabel names every hydrogen `H`.
States above are nearest-heavy-atom assignments, not residue-name changes.
Where the state is UNPROTONATED, OpenBabel placed two hydrogens on CD2
and none on the imidazole nitrogens.
That is a property of OpenBabel's pH model on this structure.
The coordinates were not edited to correct it.

Meeko could not build a receptor from the protonated PDB
(every hydrogen is named H, so residue templates do not match).
The docking receptor is `data/pocket/receptor_pH6.8.pdbqt`,
written by OpenBabel `-xr` from the pH 6.8 PDB.
OpenBabel writes partial charges as 0. Smina's Vina score uses atom types, not those charges.

## Plan checks

- CONTRADICTION: pocket 1 is 63.40 Å from the chains A+B+G all-atom centroid, which does not round to the plan's 60.3 Å. The chain A centroid (60.27 Å) does round to 60.3 Å.

Pocket centres used for the eight runs are the plan values. They were not replaced.

## Pocket 1 versus pocket 2: why the control scored better

## [EXPLORATORY]

Numbers are in `box_diagnosis.json`. The eight smina scores were not replaced.

The pocket 1 box is centred on the P2Rank cavity. The point centroid and the box centre differ by 0.005 Å, and all 28 pocket-1 points sit inside the 24 Å cube (pocket 2: 0.006 Å, all 36 points inside). This is not a box-placement error. Recentring on the centroid would move the box by less than a hundredth of an angstrom, so the four pocket 1 runs were not repeated.

The box is not the G-protein interface, and Gs does not fill it. Docking used chain R only. Zero heavy atoms from chains A, B and G lie inside either box or within 8 Å of either point centroid. The axis used here runs from the Gα centroid through the chain-R Cα centroid, toward the extracellular N-terminus. Pocket 1 is +15.1 Å along that axis (radial 3.6 Å). Residue 13 is +28.7 Å; residue 297 is −16.9 Å. His20 Cα is +17.2 Å and His269 Cα is +13.2 Å, on the same side as pocket 1. Pocket 2 is −5.1 Å and 10.5 Å off the axis: a lipid-facing groove, not a second copy of the extracellular site.

Free volume of each cube, 1 Å grid, a point counted free when it is more than 2.0 Å from every chain-R heavy atom:

| | pocket 1 | pocket 2 |
| --- | --- | --- |
| free fraction | 0.342 (5337 / 15625) | 0.559 (8737 / 15625) |
| nearest heavy atom to the centre | 2.72 Å | 4.05 Å |
| receptor heavy atoms inside the box | 643 | 409 |
| receptor heavy atoms within 8 Å of the point centroid | 105 | 69 |
| grid fraction more than 3 Å from any heavy atom | 0.089 | 0.365 |
| enclosed free cells (not connected to the box face) | 49 | 39 |

Pocket 1 is tighter. It is not a protein-filled box. Almost all free cells open onto the solvent; the enclosed remainder is about 49 Å³ and starts 5.5 Å from the centroid. The pocket 1 point cloud is a flat patch (principal standard deviations 3.39, 1.10 and 0.58 Å). The four pocket 1 poses sit 9.7–14.8 Å from the box centre. The pocket 2 poses sit 3.2–9.0 Å from theirs.

The working hypothesis that the box is largely occluded because Gs is bound is not what these distances show. The competing hypothesis, that Vina over-rewards a shallow lipid-facing groove, fits the burial and the ligand-scale clearance: pocket 2 has fewer atoms within 8 Å and about four times as much space more than 3 Å from protein. Both can be true together. The scores describe this active-state chain-R conformation and that scoring bias. They do not show that pocket 2 is the proton-sensing site.

## Protonation defect (known limitation)

OpenBabel 3.2.1, on His17, His125, His175, His216 and His269, wrote no hydrogen on ND1 or NE2 and two hydrogens on CD2 in `chainR_pH6.8.pdb` and `chainR_pH7.4.pdb`. His20, His84, His89, His130, His159, His169, His245 and His294 did flip from HID at pH 7.4 to HIP at pH 6.8.

The docking receptor is the OpenBabel PDBQT. That writer keeps polar hydrogens and drops the rest. For His269 the only hydrogen in the PDBQT is the backbone NH. ND1 and NE2 are atom type NA (acceptor). The two bogus CD2 hydrogens are not in the PDBQT, so they do not add steric bulk to the Vina score. His20, which lines the same candidate site, has polar hydrogens on both imidazole nitrogens and is typed as a donor.

Vina 1.1.2 scores atom types, not partial charges. Every charge in `receptor_pH6.8.pdbqt` is 0.000 (2601 atoms). That is acceptable for this smina run and not acceptable for any electrostatic method.

Could the His269 defect have produced the pocket 1 scores? The heavy-atom imidazole is present either way. What changes is the hydrogen-bond term on one residue: both nitrogens are acceptors, and the donor hydrogens are missing. A missing hydrogen bond does not place a ligand 10 Å off the cavity or turn a score positive. MS48107's pocket 1 score is +0.332 kcal/mol, and the pocket 1 minus pocket 2 gap averages +5.77 kcal/mol for all four compounds. Those are shape and burial, which this hydrogen assignment does not create. The defect is real and uncorrected. Rebuilding the receptor and re-docking eight ligands was not a small edit, and it would not open a cavity that the heavy atoms do not contain.

Meeko still cannot read the protonated PDB, because every hydrogen is named H. That is why the receptor PDBQT is the OpenBabel file.
