from pathlib import Path
import re, subprocess, shutil, sys
import pandas as pd
import numpy as np
from rdkit import Chem
from rdkit.Chem import AllChem

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'benchmark_results'
DOCK = OUT / 'docking'
OUT.mkdir(parents=True, exist_ok=True)
DOCK.mkdir(parents=True, exist_ok=True)

REF = ROOT / 'GPR68_reference_ligands.xlsx'
POCKETS = ROOT / 'GPR68_P2Rank_pockets.csv'
RECEPTOR = ROOT / '8Z68_GPR68_only.pdb'
GNINA = '/content/gnina'

# SUPERVISOR DESIGN: same ligand set, Pocket 1 vs Pocket 2, identical settings except center.
CORE = ['Ogerin', 'MS48107', 'Lorazepam', 'ZINC32547799']
# The supplied reference sheet does not explicitly label any OGM compounds as "Ogerin analogues".
# These are the weaker quantitative reference compounds available in that sheet and are kept
# explicitly as weak comparators rather than silently relabelled as Ogerin analogues.
WEAK_COMPARATORS = ['OGM26', 'OGM12', 'OGM16', 'OGM18']
BENCHMARK_NAMES = CORE + WEAK_COMPARATORS
POCKET_IDS = ['Pocket1', 'Pocket2']

# IDENTICAL GNINA SETTINGS FOR BOTH POCKETS. Only center_x/y/z changes.
SIZE_X = SIZE_Y = SIZE_Z = 22.0
EXHAUSTIVENESS = 8
NUM_MODES = 5
SEED = 68


def safe(x):
    return re.sub(r'[^A-Za-z0-9_.-]+', '_', str(x))


def prep_ligand(name, smiles, out_sdf, seed=6800):
    mol = Chem.MolFromSmiles(str(smiles))
    if mol is None:
        return False, 'SMILES parse failed'
    mol = Chem.AddHs(mol)
    params = AllChem.ETKDGv3()
    params.randomSeed = int(seed)
    if AllChem.EmbedMolecule(mol, params) != 0:
        return False, '3D embedding failed'
    try:
        if AllChem.MMFFHasAllMoleculeParams(mol):
            AllChem.MMFFOptimizeMolecule(mol, maxIters=500)
        else:
            AllChem.UFFOptimizeMolecule(mol, maxIters=500)
    except Exception as exc:
        return False, f'geometry optimisation failed: {exc}'
    mol.SetProp('_Name', str(name))
    writer = Chem.SDWriter(str(out_sdf))
    writer.write(mol)
    writer.close()
    return True, ''


def run_logged(cmd, logfile):
    with open(logfile, 'w') as fh:
        p = subprocess.run(cmd, stdout=fh, stderr=subprocess.STDOUT, text=True)
    return p.returncode


def read_poses(sdf_path):
    rows = []
    if not Path(sdf_path).exists() or Path(sdf_path).stat().st_size == 0:
        return rows
    for pose_i, mol in enumerate(Chem.SDMolSupplier(str(sdf_path), removeHs=False), 1):
        if mol is None:
            continue
        def val(key):
            try:
                return float(mol.GetProp(key)) if mol.HasProp(key) else np.nan
            except Exception:
                return np.nan
        rows.append({
            'pose_rank': pose_i,
            'affinity': val('minimizedAffinity'),
            'CNNscore': val('CNNscore'),
            'CNNaffinity': val('CNNaffinity')
        })
    return rows


print('=== GPR68 SUPERVISOR BENCHMARK ===')
print('Design: same benchmark ligands in Pocket1 and Pocket2; only pocket center changes.')

# 1) Input checks
for f in [REF, POCKETS, RECEPTOR]:
    if not f.exists():
        raise FileNotFoundError(f'Missing required input: {f.name}')
if not Path(GNINA).exists():
    raise FileNotFoundError('GNINA not found at /content/gnina. Run the install cell first.')

# 2) Benchmark panel from supplied reference table
ref = pd.read_excel(REF)
required_cols = {'compound_name', 'smiles', 'activity_type', 'activity_value', 'activity_unit', 'modulation_type'}
missing_cols = required_cols - set(ref.columns)
if missing_cols:
    raise RuntimeError(f'Reference sheet is missing columns: {sorted(missing_cols)}')
chem = ref[ref['smiles'].notna()].drop_duplicates(['compound_name', 'smiles']).copy()
bench = chem[chem['compound_name'].isin(BENCHMARK_NAMES)].copy()
missing = [x for x in BENCHMARK_NAMES if x not in set(bench['compound_name'])]
if missing:
    raise RuntimeError(f'Missing benchmark compounds from reference sheet: {missing}')
bench['benchmark_role'] = 'weak_reference_comparator'
bench.loc[bench['compound_name'].isin(['Ogerin', 'MS48107', 'Lorazepam']), 'benchmark_role'] = 'reference_GPR68_PAM'
bench.loc[bench['compound_name'].eq('ZINC32547799'), 'benchmark_role'] = 'negative_control'
bench['requested_by_supervisor'] = True
bench.to_csv(OUT / 'benchmark_panel.csv', index=False)
ref[ref['compound_name'].isin(BENCHMARK_NAMES)].to_csv(OUT / 'benchmark_source_assay_rows.csv', index=False)
print('\nBenchmark panel:')
print(bench[['compound_name','benchmark_role','modulation_type','activity_type','activity_value','activity_unit']].to_string(index=False))

# 3) Prepare 3D ligands once, then reuse EXACT same ligand files for both pockets
qc = []
for i, row in bench.reset_index(drop=True).iterrows():
    lig = DOCK / f'{safe(row.compound_name)}_input.sdf'
    ok, msg = prep_ligand(row.compound_name, row.smiles, lig, seed=6800+i)
    qc.append({'compound_name': row.compound_name, 'prepared': ok, 'message': msg, 'ligand_file': str(lig)})
qc = pd.DataFrame(qc)
qc.to_csv(OUT / 'ligand_preparation_QC.csv', index=False)
if not qc['prepared'].all():
    raise RuntimeError('One or more ligands failed preparation. See ligand_preparation_QC.csv')

# 4) Keep only Pocket1 and Pocket2; save exact settings for auditability
pockets = pd.read_csv(POCKETS)
pockets = pockets[pockets['pocket_id'].isin(POCKET_IDS)].copy()
if set(pockets['pocket_id']) != set(POCKET_IDS):
    raise RuntimeError('Pocket1 and/or Pocket2 missing from GPR68_P2Rank_pockets.csv')
pockets['size_x'] = SIZE_X; pockets['size_y'] = SIZE_Y; pockets['size_z'] = SIZE_Z
pockets['exhaustiveness'] = EXHAUSTIVENESS; pockets['num_modes'] = NUM_MODES; pockets['seed'] = SEED
pockets['receptor'] = RECEPTOR.name
pockets['settings_rule'] = 'All GNINA settings identical; only center_x/center_y/center_z differ.'
pockets.to_csv(OUT / 'pocket1_pocket2_identical_settings.csv', index=False)

# 5) Dock every ligand into both sites
all_poses = []
run_qc = []
for _, row in bench.iterrows():
    lig = DOCK / f'{safe(row.compound_name)}_input.sdf'
    for _, p in pockets.iterrows():
        tag = f'{safe(row.compound_name)}_{p.pocket_id}'
        out_sdf = DOCK / f'{tag}_docked.sdf'
        log = DOCK / f'{tag}.log'
        cmd = [
            GNINA, '-r', str(RECEPTOR), '-l', str(lig),
            '--center_x', str(p.center_x), '--center_y', str(p.center_y), '--center_z', str(p.center_z),
            '--size_x', str(SIZE_X), '--size_y', str(SIZE_Y), '--size_z', str(SIZE_Z),
            '--exhaustiveness', str(EXHAUSTIVENESS), '--num_modes', str(NUM_MODES), '--seed', str(SEED),
            '-o', str(out_sdf)
        ]
        rc = run_logged(cmd, log)
        poses = read_poses(out_sdf) if rc == 0 else []
        run_qc.append({'compound_name': row.compound_name, 'pocket_id': p.pocket_id,
                       'return_code': rc, 'n_poses': len(poses), 'pose_file': str(out_sdf), 'log_file': str(log)})
        for pose in poses:
            all_poses.append({'compound_name': row.compound_name, 'benchmark_role': row.benchmark_role,
                              'pocket_id': p.pocket_id, **pose})
        print(f'{tag}:', 'OK' if poses else 'FAILED')

run_qc = pd.DataFrame(run_qc)
run_qc.to_csv(OUT / 'docking_run_QC.csv', index=False)
if (run_qc['return_code'] != 0).any() or (run_qc['n_poses'] == 0).any():
    raise RuntimeError('At least one docking run failed. See docking_run_QC.csv and the matching .log file. No interpretation was generated.')

poses = pd.DataFrame(all_poses)
poses.to_csv(OUT / 'all_docking_poses.csv', index=False)

# Best pose per ligand/site by CNNscore, tie-break by more negative affinity
best = (poses.sort_values(['compound_name','pocket_id','CNNscore','affinity'], ascending=[True,True,False,True])
             .groupby(['compound_name','pocket_id'], as_index=False).first())
best.to_csv(OUT / 'benchmark_best_pose_results.csv', index=False)

# 6) Paired Pocket1-vs-Pocket2 table. No automatic declaration of a biological "winner".
p1 = best[best.pocket_id.eq('Pocket1')].set_index('compound_name')
p2 = best[best.pocket_id.eq('Pocket2')].set_index('compound_name')
paired = pd.DataFrame(index=sorted(set(p1.index) & set(p2.index)))
roles = bench.drop_duplicates('compound_name').set_index('compound_name')['benchmark_role']
paired['benchmark_role'] = roles.reindex(paired.index)
for metric in ['affinity','CNNscore','CNNaffinity']:
    paired[f'Pocket1_{metric}'] = p1[metric].reindex(paired.index)
    paired[f'Pocket2_{metric}'] = p2[metric].reindex(paired.index)
paired['P1_minus_P2_CNNscore'] = paired['Pocket1_CNNscore'] - paired['Pocket2_CNNscore']
paired['P1_minus_P2_CNNaffinity'] = paired['Pocket1_CNNaffinity'] - paired['Pocket2_CNNaffinity']
paired['P1_minus_P2_affinity'] = paired['Pocket1_affinity'] - paired['Pocket2_affinity']
paired.reset_index(names='compound_name').to_csv(OUT / 'Pocket1_vs_Pocket2_paired_comparison.csv', index=False)

# 7) Descriptive group summary only; primary/alternative designation comes from supervisor, not from score ranking.
summary = (best.groupby(['pocket_id','benchmark_role'])
               .agg(n=('compound_name','nunique'), median_affinity=('affinity','median'),
                    median_CNNscore=('CNNscore','median'), median_CNNaffinity=('CNNaffinity','median'))
               .reset_index())
summary.to_csv(OUT / 'benchmark_descriptive_summary.csv', index=False)

text = f'''GPR68 known-ligand benchmark completed.\n\nSupervisor-specified design:\n- Pocket1 = primary candidate\n- Pocket2 = alternative candidate\n- Same benchmark ligand set docked to both sites\n- Identical GNINA settings except pocket center\n\nGNINA settings:\n- search box = {SIZE_X:.0f} x {SIZE_Y:.0f} x {SIZE_Z:.0f} A\n- exhaustiveness = {EXHAUSTIVENESS}\n- num_modes = {NUM_MODES}\n- seed = {SEED}\n\nCore ligands: {', '.join(CORE)}\nAdditional weak quantitative comparators from supplied reference sheet: {', '.join(WEAK_COMPARATORS)}\n\nIMPORTANT DATA NOTE:\nThe supplied reference spreadsheet does not explicitly establish OGM26/OGM12/OGM16/OGM18 as "Ogerin analogues". They are included as weaker quantitative GPR68 reference comparators because they have higher reported EC50 values in the supplied dataset. Replace these names if your supervisor provides a specifically validated weak-Ogerin-analogue series.\n\nInterpretation limit:\nDocking scores and P2Rank pockets are computational predictions. This benchmark does not prove a biological binding site or experimental binding.\n'''
(OUT / 'RUN_SUMMARY.txt').write_text(text)
print('\n' + text)

zipbase = '/content/GPR68_SUPERVISOR_BENCHMARK_RESULTS'
shutil.make_archive(zipbase, 'zip', OUT)
print('RESULT ZIP:', zipbase + '.zip')
