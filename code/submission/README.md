# GPR68 AI-Assisted Small-Molecule Screening for Osteoarthritis

## Competition track
Track 3 — Virtual Screening of Small-Molecule Drugs for Ion Channels, GPCRs, and Other Drug Targets.

## Project status
This package contains the **verified preliminary computational workflow and technical-validation outputs** available at submission time. It does **not** claim a completed prospective screen or a completed Pocket 1 vs Pocket 2 known-ligand benchmark.

The current verified work includes:
1. Curated GPR68 reference-ligand records.
2. RDKit processing of a commercial library: 10,240 structures loaded, 0 failed structures and 0 duplicate canonical SMILES in the processed run.
3. Receptor-only GPR68 structure derived from experimental PDB 8Z68.
4. P2Rank/PrankWeb candidate-pocket results.
5. GNINA technical redocking validation, with best RMSD 0.59408 A.
6. A reproducible script/notebook for the planned controlled Pocket 1 vs Pocket 2 benchmark.

## Directory structure
- `data/` — curated reference ligands, pocket table, data provenance.
- `receptor/` — receptor-only GPR68 PDB.
- `src/` — core scripts, including benchmark workflow.
- `models/` — Model Card. No self-trained model is claimed.
- `notebooks/` — executable RDKit and benchmark notebooks.
- `results/` — standardized results workbook/CSV and verified preliminary outputs.
- `logs/` — GNINA technical-validation logs and run metadata.
- `docs/` — competition code-submission requirements supplied by the team.

## Environment
Development used Python/Colab-style environments. Python dependencies are listed in `requirements.txt`.

External tool used:
- GNINA v1.3.2, CUDA build.

Pocket prediction was performed with P2Rank/PrankWeb; recorded outputs are supplied. The current package does not require rerunning P2Rank to verify the recorded pocket table.

### Hardware
CPU is sufficient for descriptor-summary reproduction. GNINA docking requires a compatible NVIDIA/CUDA environment for the supplied development route. A Tesla T4 was available during Colab development.

## One-command verified entry point
From the project root:

```bash
python -m pip install -r requirements.txt
python main.py
```

`main.py` checks required artifacts, reproduces a descriptor summary from the supplied processed table, and writes `results/results.csv`.

Because a prospective screen has not yet been completed, the generated `results.csv` intentionally contains the required candidate-list headers but no fabricated candidate rows. `results/results.xlsx` contains the same submission-status disclosure plus the verified preliminary metrics.

## Known-ligand benchmark
The supplied `src/benchmark_docking.py` and `notebooks/GPR68_Supervisor_Benchmark_Autopilot.ipynb` implement the planned benchmark design:
- Pocket 1 = primary candidate region.
- Pocket 2 = alternative candidate region.
- Same ligand set in both pockets.
- Identical GNINA settings except for pocket centre.
- Planned box size: 22 x 22 x 22 A.
- Exhaustiveness: 8.
- Number of modes: 5.
- Random seed: 68 where supported by the GNINA build.

Core benchmark references include Ogerin, MS48107, lorazepam and ZINC32547799, with additional weaker GPR68 reference comparators selected from the curated table. Benchmark completion is not claimed because the latest Colab attempt encountered a CUDA runtime-library issue before GNINA launched.

## Verified preliminary results
### RDKit library processing
- Structures loaded: 10,240
- Failed structures: 0
- Duplicate canonical SMILES: 0
- Mean molecular weight: 366.59 Da
- Mean LogP: 2.59
- Mean TPSA: 78.90 A^2

### Candidate pockets
Pocket 1: score 7.06, probability 0.366, centre (145.764, 127.948, 98.930).
Pocket 2: score 6.87, probability 0.353, centre (129.885, 132.584, 117.625).
These are computationally predicted candidate binding sites, not experimentally proven sites.

### GNINA technical validation
- Best redocking RMSD: 0.59408 A
- Top-pose affinity: -8.51 kcal/mol
- CNN pose score: 0.9790
- CNN affinity: 7.160
This is technical validation of the docking workflow, not biological validation of GPR68 binding.

## Data and licensing
See `data/DATA_SOURCES.md`. The raw commercial SDF is not redistributed because its redistribution rights were not established for this submission. Derived descriptor outputs are included. Public literature/PDB provenance is disclosed.

## Reproducibility / traceability
- Core inputs and verified outputs are included.
- Random-seed information is recorded.
- Third-party tools and versions are disclosed where known.
- No self-trained model is claimed at this stage.
- No unfinished benchmark values or prospective hits are fabricated.

## Limitations
The competition's standardized candidate-list requirement can only be fully populated after the known-ligand benchmark and prospective pilot/full screening are successfully completed. This package is deliberately truthful about that limitation.
