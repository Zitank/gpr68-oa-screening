# ligand_data

One row per molecule-assay-endpoint. Endpoints are not pooled.

Logged run `m1-ligand-harvest` (study M1, seed 20261004).

ChEMBL CHEMBL3713916 matched the plan headline: 340 activities, 94 molecules, 21 assays, 8 documents, 14 pChEMBL values on 10 molecules. Three extra endpoint types (Inhibition, Mean fold stimulation, RLU; one row each) are recorded as discrepancies. The two largest documents are CHEMBL4406806 (67 molecules, 273 activity rows) and CHEMBL5661984 (29 molecules, 60 activity rows).

PubChem GeneID 8111 has 22 AIDs. Nine have CIDCountAll > 0. AID 2060853 is 39 active and 13 inactive molecules; the 13 inactives are `results/ligand_data/AID2060853_inactives.csv`. Five further compound AIDs were kept and flagged because they were not in the plan's named list. ChEMBL-deposited PubChem rows that repeat an InChIKey and endpoint already in ChEMBL are mirrors (A11) and are not in `GPR68_reference_ligands.csv` (394 rows).

Assumptions: A10, A11, A12. Values are in the module docstrings.
