# Data sources and provenance

## GPR68 reference ligands
`GPR68_reference_ligands.csv` contains the curated reference-ligand records used during workflow development. The file preserves reported assay/activity fields rather than coercing heterogeneous EC50/IC50 and qualitative measurements into one artificial label.

Key literature represented in the project includes:
- Huang XP et al. Nature (2015). DOI: 10.1038/nature15699.
- Yu M et al. Journal of Medicinal Chemistry (2019). DOI: 10.1021/acs.jmedchem.9b00869.

## Receptor structure
Experimental GPR68 structure: PDB 8Z68. The supplied `receptor/8Z68_GPR68_only.pdb` is the receptor-only structure used for the project workflow.

## Commercial screening library
The project processed a commercial molecular library supplied to the team as SDF data. The raw commercial SDF is intentionally not redistributed in this competition package because redistribution rights/licensing have not been established here. The derived descriptor table is supplied under `results/preliminary_results/MCE_5K_RDKit_properties.csv` for reproducibility of the reported preprocessing statistics.

## Pocket prediction
`GPR68_P2Rank_pockets.csv` records candidate pockets derived from P2Rank/PrankWeb analysis of the receptor-only structure. These are computationally predicted candidate sites, not experimentally validated binding sites.

## Data leakage / deduplication
No self-trained predictive model is claimed in this package, so a train/validation/test split is not applicable to the current submitted stage. During RDKit preprocessing, canonical-SMILES duplicate checking was performed; the processed library contained 10,240 successfully loaded structures and no duplicate canonical SMILES in that run.
