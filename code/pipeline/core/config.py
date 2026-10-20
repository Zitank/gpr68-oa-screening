"""Frozen experiment configuration and its canonical hash."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, SerializerFunctionWrapHandler, model_serializer

from core.hashing import sha256_json


class ExperimentConfig(BaseModel):
    """One logged run. ``params`` holds experiment-specific numbers and labels."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    seed: int
    mode: Literal["exploratory", "confirmatory"] = "exploratory"
    condition_code: str
    params: dict[str, float | int | str] = Field(default_factory=dict)
    study_id: str | None = None

    @model_serializer(mode="wrap")
    def _omit_null_study_id(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        # ``model_dump()`` includes ``study_id: None`` by default, which would change
        # hashes of configs that never set the field. Drop only that null key.
        data = handler(self)
        if not isinstance(data, dict):
            raise TypeError(f"ExperimentConfig serialised to {type(data).__name__}, expected dict")
        if data.get("study_id") is None:
            return {k: v for k, v in data.items() if k != "study_id"}
        return data


def config_hash(cfg: ExperimentConfig) -> str:
    """sha256 hex of canonical JSON of the config.

    A null ``study_id`` is left out of the hashed dict so configs that do not set it
    keep a stable hash.
    """
    dumped = cfg.model_dump()
    payload = {k: v for k, v in dumped.items() if not (k == "study_id" and v is None)}
    return sha256_json(payload)
