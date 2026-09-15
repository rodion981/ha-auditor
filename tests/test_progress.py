"""Tests for audit coverage and failure semantics."""

from __future__ import annotations

import importlib.util
from pathlib import Path

MODULE_PATH = (
    Path(__file__).parents[1]
    / "custom_components"
    / "custom_components_auditor"
    / "progress.py"
)
SPEC = importlib.util.spec_from_file_location("auditor_progress", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
progress = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(progress)


def test_successful_unauthenticated_batch_is_not_partial() -> None:
    result = progress.audit_progress(22, 15, 15, 15, 0)

    assert result == {
        "deferred_components": 7,
        "not_attempted_this_run": 0,
        "partial_audit": False,
        "cycle_complete": False,
    }


def test_successful_full_inventory_run_completes_cycle() -> None:
    result = progress.audit_progress(108, 108, 108, 108, 0)

    assert result["deferred_components"] == 0
    assert result["partial_audit"] is False
    assert result["cycle_complete"] is True


def test_interrupted_batch_is_partial_and_incomplete() -> None:
    result = progress.audit_progress(22, 15, 3, 2, 1)

    assert result["deferred_components"] == 7
    assert result["not_attempted_this_run"] == 12
    assert result["partial_audit"] is True
    assert result["cycle_complete"] is False
