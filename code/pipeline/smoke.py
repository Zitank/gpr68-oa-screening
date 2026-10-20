"""Walking-skeleton check: two logged runs of the example model, then a determinism assert.

## [EXPLORATORY]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from core.config import ExperimentConfig, config_hash
from core.ledger import read_ledger, run_logged

LEDGER = Path("governance/run_ledger.jsonl")


def fit_linear(xs: list[int], ys: list[int]) -> tuple[float, float]:
    """Ordinary least squares. The kit module ``clusters.example`` is not in this repo."""
    n = len(xs)
    if n < 2 or n != len(ys):
        raise RuntimeError("smoke fit needs at least two paired points")
    x_bar = sum(xs) / n
    y_bar = sum(ys) / n
    variance = sum((x - x_bar) ** 2 for x in xs)
    if variance == 0:
        raise RuntimeError("smoke fit needs variation in x")
    slope = sum((x - x_bar) * (y - y_bar) for x, y in zip(xs, ys, strict=True)) / variance
    return slope, y_bar - slope * x_bar


def smoke_config(seed: int = 0) -> ExperimentConfig:
    return ExperimentConfig(
        name="example-linear",
        seed=seed,
        mode="exploratory",
        condition_code="A",
        params={"n": 4},
    )


def run_once(cfg: ExperimentConfig) -> dict[str, Any]:
    n = int(cfg.params["n"])
    xs = list(range(n))
    ys = [2 * x + 1 for x in xs]
    slope, intercept = fit_linear(xs, ys)
    return {"slope": slope, "intercept": intercept, "seed": cfg.seed}


def main() -> int:
    cfg = smoke_config()
    before = len(read_ledger(LEDGER)) if LEDGER.exists() else 0
    r1 = run_logged(cfg, lambda: run_once(cfg), LEDGER)
    r2 = run_logged(cfg, lambda: run_once(cfg), LEDGER)
    lines = read_ledger(LEDGER)
    assert len(lines) == before + 2, "ledger must grow by exactly two lines"
    last = lines[-1]
    assert last["config_hash"] == config_hash(cfg) == lines[-2]["config_hash"]
    print("── ledger line (run 2) ──")
    print(json.dumps({k: v for k, v in last.items() if k != "config"}, indent=1, sort_keys=True))
    print(f"── result: slope={r2['slope']} intercept={r2['intercept']}")
    identical = r1 == r2
    print(f"── determinism: run1 == run2 → {identical}")
    if not identical:
        diff = {k: (r1[k], r2[k]) for k in r1 if r1[k] != r2[k]}
        print("   differing fields:", diff)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
