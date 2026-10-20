"""Print the pocket table from the points file and the saved histidine states.

This is a live computation over the P2Rank points, not a canned printout.
"""

from __future__ import annotations

import json
from pathlib import Path

from clusters.pocket.src.facts import PLAN_CENTRES
from clusters.pocket.src.pdbio import iter_atoms
from clusters.pocket.src.pipeline import DATA, POINTS_PDB, RESULTS, STRUCTURES
from clusters.pocket.src.points import read_pockets
from clusters.pocket.src.summary import pocket_records

REPO = Path(__file__).resolve().parents[3]


def main() -> None:
    pockets = read_pockets(POINTS_PDB.read_text())
    chain = iter_atoms((DATA / "chainR.pdb").read_text())
    records = pocket_records(pockets, chain)
    hist = json.loads((RESULTS / "histidines.json").read_text())
    print("PDB 8Z68 chain R. Centres for pockets 1 and 2 are the plan values.")
    print(f"{'id':>4} {'n':>5} {'score_sum':>10} {'centre'}")
    for record in records:
        centre = (record["center_x"], record["center_y"], record["center_z"])
        print(
            f"{record['pocket_id']:4d} {record['point_count']:5d} "
            f"{record['score_sum']:10.3f} {centre}  {record['role']}"
        )
    print(f"plan pocket 1 {PLAN_CENTRES[1]}")
    print(f"plan pocket 2 {PLAN_CENTRES[2]}")
    flips = ", ".join(f"HIS{row['resseq']} {row['ph_7_4']}->{row['ph_6_8']}" for row in hist["flipped"])
    bare = ", ".join(f"HIS{resseq}" for resseq in hist["unprotonated_at_both_ph"])
    print(f"pH 7.4 -> 6.8 flips: {flips}")
    print(f"unprotonated at both pH: {bare}")
    print(f"structure file: {STRUCTURES / '8Z68.pdb'}")


if __name__ == "__main__":
    main()
