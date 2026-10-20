# Model Card — GPR68 computational screening submission

## Status
This submission represents the preliminary computational workflow and technical-validation stage. No self-trained or fine-tuned machine-learning model is claimed in the current package.

## Computational components
- RDKit: molecular parsing, canonical SMILES, descriptors and molecular preprocessing.
- P2Rank / PrankWeb: candidate binding-pocket prediction. Supplied pocket outputs are recorded results from the receptor-only GPR68 structure.
- GNINA v1.3.2: structure-based docking / CNN scoring. A reference redocking test is supplied as technical validation.

## Intended scope
Prioritisation of small molecules for later GPR68 functional and osteoarthritis-related experimental validation.

## Inputs
Small-molecule structures (SMILES/SDF), receptor-only GPR68 PDB, candidate pocket centres.

## Outputs
Molecular descriptors, candidate-pocket metadata, GNINA affinity/CNN scores and docking poses when a benchmark or screen is executed successfully.

## Current limitations
- The Pocket 1 versus Pocket 2 known-ligand benchmark was initiated but is not claimed as completed in this submission.
- No prospective hit/candidate list is claimed yet.
- Docking scores are computational predictions and do not prove binding, efficacy, selectivity or mechanism.
- Candidate pockets are computational predictions, not experimentally proven binding sites.
