#!/usr/bin/env python3
"""Competition entry point for the currently verified GPR68 workflow outputs.

This script does NOT fabricate unfinished benchmark/candidate results. It validates
that the supplied core artifacts are present, reproduces the descriptor summary,
and writes a UTF-8 status/results CSV documenting the current submission stage.
"""
from pathlib import Path
import csv, subprocess, sys

ROOT=Path(__file__).resolve().parent
required=[
 ROOT/'data/GPR68_reference_ligands.csv',
 ROOT/'data/GPR68_P2Rank_pockets.csv',
 ROOT/'receptor/8Z68_GPR68_only.pdb',
 ROOT/'results/preliminary_results/MCE_5K_RDKit_properties.csv',
 ROOT/'logs/GNINA_example_RMSD.txt',
 ROOT/'logs/GNINA_example_log.txt',
]
missing=[str(p.relative_to(ROOT)) for p in required if not p.exists()]
if missing:
    raise SystemExit('Missing required files: '+', '.join(missing))
subprocess.run([sys.executable,str(ROOT/'src/prepare_library.py')],check=True)
out=ROOT/'results/results.csv'
fields=['candidate_id','competition_track','compound_name','smiles','predicted_indicator','model_run_version','structure_file','status','remarks']
with out.open('w',newline='',encoding='utf-8') as f:
    w=csv.DictWriter(f,fieldnames=fields); w.writeheader()
print('Core artifacts verified.')
print('No prospective candidates are claimed at the current stage; results.csv therefore contains headers only.')
print(f'Wrote {out}')
