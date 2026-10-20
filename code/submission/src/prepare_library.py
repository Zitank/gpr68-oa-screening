#!/usr/bin/env python3
"""Reproduce summary statistics from the supplied RDKit descriptor table."""
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
INFILE = ROOT / 'results' / 'preliminary_results' / 'MCE_5K_RDKit_properties.csv'
OUTFILE = ROOT / 'results' / 'library_summary.csv'

def main():
    df = pd.read_csv(INFILE)
    # Flexible column matching because the original notebook controls exact labels.
    lower = {c.lower(): c for c in df.columns}
    def pick(*names):
        for n in names:
            if n.lower() in lower: return lower[n.lower()]
        return None
    mw=pick('MW','MolWt','molecular_weight')
    logp=pick('LogP','MolLogP')
    tpsa=pick('TPSA')
    rows=[['metric','value'],['structures_loaded',len(df)]]
    for label,col in [('mean_MW',mw),('mean_LogP',logp),('mean_TPSA',tpsa)]:
        if col: rows.append([label,float(pd.to_numeric(df[col],errors='coerce').mean())])
    pd.DataFrame(rows[1:],columns=rows[0]).to_csv(OUTFILE,index=False)
    print(f'Wrote {OUTFILE}')
if __name__=='__main__': main()
