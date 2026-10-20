"""Typed errors. Blueprint principle 1: fail loudly; never catch-and-continue a contract violation."""

from __future__ import annotations


class PipelineError(Exception):
    """Base class for all pipeline errors."""


class ContractViolation(PipelineError):
    """A component boundary received or produced something outside its contract (shape, dtype, units, split)."""  # noqa: E501


class LedgerError(PipelineError):
    """The run ledger was edited, truncated, or written outside run_logged()."""


class ScopeViolation(PipelineError):
    """A role touched a path outside its allowed set."""


class NeedsSource(PipelineError):
    """A number, constant or formula has no verified citation and no registered assumption."""
