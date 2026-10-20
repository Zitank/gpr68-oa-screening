"""Data-provenance figure: activity rows per ChEMBL document.

## [EXPLORATORY]
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from core.errors import ContractViolation


def write_provenance_figure(rows: list[dict[str, str]], path: Path) -> None:
    """Bar chart of ChEMBL activity rows per document, labeled with molecule counts."""
    chembl = [row for row in rows if row["source"] == "ChEMBL"]
    activities: dict[str, int] = defaultdict(int)
    molecules: dict[str, set[str]] = defaultdict(set)
    labels: dict[str, str] = {}
    for row in chembl:
        doc = row["document_chembl_id"]
        activities[doc] += 1
        molecules[doc].add(row["inchikey"])
        labels[doc] = row["reference"]
    order = sorted(activities, key=lambda doc: (-activities[doc], doc))
    if not order:
        raise ContractViolation("no ChEMBL rows for the provenance figure")
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, axis = plt.subplots(figsize=(9.5, 5.2))
    positions = list(range(len(order)))
    counts = [activities[doc] for doc in order]
    # The two documents that contribute the most molecules are highlighted.
    by_molecules = sorted(order, key=lambda doc: (-len(molecules[doc]), doc))
    dominant = set(by_molecules[:2])
    colors = ["#1f4e79" if doc in dominant else "#c5cdd6" for doc in order]
    axis.barh(positions, counts, color=colors)
    axis.set_yticks(positions, [labels[doc] for doc in order])
    axis.invert_yaxis()
    axis.set_xlabel("Activity rows (endpoints are not pooled)")
    axis.set_title("GPR68 ChEMBL bioactivity by source document")
    for pos, doc in zip(positions, order, strict=True):
        axis.text(
            counts[pos] + max(counts) * 0.01,
            pos,
            f"{len(molecules[doc])} molecules",
            va="center",
            fontsize=8,
        )
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)
