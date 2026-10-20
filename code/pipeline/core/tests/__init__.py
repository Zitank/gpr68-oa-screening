"""Shared fixtures for core platform tests."""

from __future__ import annotations

from typing import Any

from core.config import ExperimentConfig


def make_config(**overrides: Any) -> ExperimentConfig:
    payload: dict[str, Any] = {
        "name": "example",
        "seed": 0,
        "mode": "exploratory",
        "condition_code": "A",
        "params": {"x": 1.0},
    }
    payload.update(overrides)
    return ExperimentConfig.model_validate(payload)
