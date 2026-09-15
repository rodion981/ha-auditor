"""Pure audit-progress helpers for HA Auditor."""

from __future__ import annotations

from typing import Any


def audit_progress(
    total: int,
    targeted: int,
    attempted: int,
    checked: int,
    error_count: int,
) -> dict[str, Any]:
    """Describe run success separately from full-inventory coverage."""
    deferred = max(total - targeted, 0)
    not_attempted = max(targeted - attempted, 0)
    partial = bool(error_count or not_attempted)
    cycle_complete = deferred == 0 and checked >= total and not partial
    return {
        "deferred_components": deferred,
        "not_attempted_this_run": not_attempted,
        "partial_audit": partial,
        "cycle_complete": cycle_complete,
    }
