"""Config hash stability, frozen models, and unknown-field rejection."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from core.config import ExperimentConfig, config_hash
from core.hashing import sha256_json
from core.tests import make_config


def test_config_hash_stable_and_changes_with_field() -> None:
    first = make_config()
    second = make_config()
    assert config_hash(first) == config_hash(second)
    assert config_hash(first) == sha256_json(first.model_dump())
    assert len(config_hash(first)) == 64
    assert config_hash(make_config(seed=1)) != config_hash(first)


def test_frozen_config_rejects_assignment() -> None:
    cfg = make_config()
    with pytest.raises(ValidationError):
        cfg.seed = 3  # type: ignore[misc]
    with pytest.raises(ValidationError):
        cfg.name = "other"  # type: ignore[misc]


def test_unknown_field_rejected() -> None:
    dumped = make_config().model_dump()
    dumped["extra"] = 1
    with pytest.raises(ValidationError):
        ExperimentConfig.model_validate(dumped)


def test_mode_must_be_known() -> None:
    dumped = make_config().model_dump()
    dumped["mode"] = "pilot"
    with pytest.raises(ValidationError):
        ExperimentConfig.model_validate(dumped)


def test_null_study_id_omitted_from_dump() -> None:
    assert "study_id" not in make_config().model_dump()
    assert make_config(study_id="S01").model_dump()["study_id"] == "S01"
