#!/usr/bin/env bash
# Live terminal walkthrough. The docking step calls smina and appends the ledger.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO"

if [[ -x "$REPO/.venv/bin/python" ]]; then
  PYTHON=("$REPO/.venv/bin/python")
else
  PYTHON=(uv run python)
fi

echo "GPR68  PDB 8Z68 chain R  pH 6.8 cryo-EM"
echo "Pocket 1 and pocket 2. Engine: smina (Vina 1.1.2). GNINA was not run."
echo
sleep 2

echo "=== pocket summary, recomputed from the P2Rank points ==="
"${PYTHON[@]}" -m clusters.pocket.src.show
echo
sleep 2

echo "=== one real docking run, logged: Ogerin into pocket 1 ==="
"${PYTHON[@]}" -m clusters.docking.src.rerun
echo
sleep 2

echo "=== eight-run score table (smina) ==="
SCORES="$REPO/results/docking/scores.csv" "${PYTHON[@]}" - << 'PY'
import csv
import os
from pathlib import Path
path = Path(os.environ["SCORES"])
rows = list(csv.DictReader(path.open()))
print("%-16s %6s %10s %8s engine" % ("ligand", "pocket", "kcal/mol", "seconds"))
for row in rows:
    print("%-16s %6s %10.3f %8.1f %s" % (
        row["ligand"], row["pocket_id"], float(row["best_score_kcal_mol"]), float(row["seconds"]), row["engine"]
    ))
PY
echo
sleep 2

echo "=== ledger tail ==="
LEDGER="$REPO/governance/run_ledger.jsonl" "${PYTHON[@]}" - << 'PY'
import json
import os
from pathlib import Path
path = Path(os.environ["LEDGER"])
lines = [line for line in path.read_text().splitlines() if line.strip()]
last = json.loads(lines[-1])
result = last.get("result") or {}
print("lines:", len(lines))
print("status:", last["status"], "engine:", result.get("engine"), "ligand:", result.get("ligand"), "pocket:", result.get("pocket_id"))
print("best_score_kcal_mol:", result.get("best_score_kcal_mol"), "config_hash:", last["config_hash"])
PY
echo
echo "Done. Scores are smina / Vina 1.1.2. GNINA replay: results/docking/gnina_runs.sh"
