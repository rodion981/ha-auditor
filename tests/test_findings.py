"""Tests for persistent actionable finding lifecycle."""

from __future__ import annotations

import importlib.util
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

MODULE_PATH = (
    Path(__file__).parents[1]
    / "custom_components"
    / "custom_components_auditor"
    / "findings.py"
)
SPEC = importlib.util.spec_from_file_location("auditor_findings", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
findings = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(findings)

NOW = datetime(2026, 9, 15, 12, 0, tzinfo=UTC)


def _update(severity: str = "important", version: str = "2.0.0") -> dict:
    return {
        "repository": "owner/component",
        "component": "Component update",
        "installed_version": "1.0.0",
        "latest_version": version,
        "severity": severity,
        "reason": "Read before updating.",
        "summary": "Important release.",
        "url": "https://github.com/owner/component/releases/tag/2.0.0",
    }


def _health(status: str = "abandoned") -> dict:
    return {
        "repository": "owner/component",
        "component": "Component update",
        "status": status,
        "pushed_at": "2024-01-01T00:00:00Z",
        "days_since_push": 988,
        "url": "https://github.com/owner/component",
    }


def _run(existing: dict, candidates: list[dict], now: datetime = NOW) -> dict:
    return findings.update_findings(
        existing,
        candidates,
        {"owner/component"},
        {"owner/component"},
        now,
    )


def test_only_actionable_updates_become_candidates() -> None:
    candidates = findings.build_finding_candidates(
        [_update("minor"), _update("important")], []
    )

    assert len(candidates) == 1
    assert candidates[0]["finding_type"] == "important_update"
    assert candidates[0]["fingerprint"] == "update:2.0.0:important"


def test_important_update_activates_immediately_and_does_not_duplicate() -> None:
    candidates = findings.build_finding_candidates([_update()], [])

    first = _run({}, candidates)
    second = _run(first["findings"], candidates, NOW + timedelta(days=1))

    assert first["active_finding_count"] == 1
    assert len(first["finding_changes"]["activated"]) == 1
    assert second["active_finding_count"] == 1
    assert second["active_findings"][0]["confirmations"] == 2
    assert second["finding_changes"]["activated"] == []
    assert second["finding_counts"]["new"] == 1


def test_abandoned_repository_requires_two_successful_observations() -> None:
    candidates = findings.build_finding_candidates([], [_health()])

    first = _run({}, candidates)
    second = _run(first["findings"], candidates, NOW + timedelta(days=1))

    assert first["active_finding_count"] == 0
    assert first["findings_pending_confirmation"] == 1
    assert first["pending_findings"][0]["finding_type"] == "repository_abandoned"
    assert second["active_finding_count"] == 1
    assert second["active_findings"][0]["finding_type"] == "repository_abandoned"


def test_unchecked_repository_does_not_advance_or_clear_finding() -> None:
    candidates = findings.build_finding_candidates([], [_health()])
    first = _run({}, candidates)

    result = findings.update_findings(
        first["findings"],
        [],
        set(),
        {"owner/component"},
        NOW + timedelta(days=1),
    )

    assert result["findings_pending_confirmation"] == 1
    assert next(iter(result["findings"].values()))["confirmations"] == 1


def test_active_finding_resolves_after_two_clean_checks() -> None:
    candidates = findings.build_finding_candidates([_update()], [])
    active = _run({}, candidates)

    first_clear = _run(active["findings"], [], NOW + timedelta(days=1))
    second_clear = _run(first_clear["findings"], [], NOW + timedelta(days=2))

    assert first_clear["active_finding_count"] == 1
    assert first_clear["active_findings"][0]["clear_confirmations"] == 1
    assert second_clear["active_finding_count"] == 0
    assert len(second_clear["recently_resolved_findings"]) == 1
    assert len(second_clear["finding_changes"]["resolved"]) == 1


def test_new_update_version_starts_a_new_finding_lifecycle() -> None:
    first_candidates = findings.build_finding_candidates([_update()], [])
    first = _run({}, first_candidates)
    next_candidates = findings.build_finding_candidates([_update(version="3.0.0")], [])

    result = _run(first["findings"], next_candidates, NOW + timedelta(days=1))

    assert result["active_findings"][0]["latest_version"] == "3.0.0"
    assert result["active_findings"][0]["confirmations"] == 1
    assert (
        result["active_findings"][0]["first_seen"]
        != first["active_findings"][0]["first_seen"]
    )
    assert result["recently_resolved_findings"][0]["latest_version"] == "2.0.0"
    assert result["recently_resolved_findings"][0]["resolution_reason"] == (
        "superseded"
    )


def test_acknowledged_finding_stays_active_but_no_longer_new() -> None:
    candidate = findings.build_finding_candidates([_update()], [])
    active = _run({}, candidate)
    finding_id = active["active_findings"][0]["id"]

    result = findings.set_finding_review_state(
        active["findings"],
        finding_id,
        findings.REVIEW_ACKNOWLEDGED,
        NOW,
    )

    assert result["active_finding_count"] == 1
    assert result["finding_counts"]["new"] == 0
    assert result["finding_counts"]["acknowledged"] == 1
    assert result["active_findings"][0]["acknowledged_at"] == NOW.isoformat()


def test_snoozed_finding_reopens_after_its_deadline() -> None:
    candidate = findings.build_finding_candidates([_update()], [])
    active = _run({}, candidate)
    finding_id = active["active_findings"][0]["id"]
    snoozed = findings.set_finding_review_state(
        active["findings"],
        finding_id,
        findings.REVIEW_SNOOZED,
        NOW,
        snooze_days=7,
    )

    before_deadline = findings.summarize_findings(
        snoozed["findings"], NOW + timedelta(days=6)
    )
    after_deadline = findings.summarize_findings(
        snoozed["findings"], NOW + timedelta(days=8)
    )

    assert before_deadline["finding_counts"]["snoozed"] == 1
    assert before_deadline["finding_counts"]["new"] == 0
    assert after_deadline["finding_counts"]["snoozed"] == 0
    assert after_deadline["finding_counts"]["new"] == 1


def test_legacy_naive_snooze_deadline_is_normalized() -> None:
    candidate = findings.build_finding_candidates([_update()], [])
    active = _run({}, candidate)
    finding_id = active["active_findings"][0]["id"]
    active["findings"][finding_id]["review_status"] = findings.REVIEW_SNOOZED
    active["findings"][finding_id]["snoozed_until"] = "2026-09-22T12:00:00"

    result = findings.normalize_finding_workflow(active["findings"], NOW)

    assert result[finding_id]["review_status"] == findings.REVIEW_SNOOZED
    assert result[finding_id]["snoozed_until"] == "2026-09-22T12:00:00+00:00"


def test_ignored_finding_persists_until_its_fingerprint_changes() -> None:
    first_candidate = findings.build_finding_candidates([_update()], [])
    active = _run({}, first_candidate)
    finding_id = active["active_findings"][0]["id"]
    ignored = findings.set_finding_review_state(
        active["findings"],
        finding_id,
        findings.REVIEW_IGNORED,
        NOW,
    )

    same_version = _run(ignored["findings"], first_candidate, NOW + timedelta(days=1))
    next_candidate = findings.build_finding_candidates([_update(version="3.0.0")], [])
    next_version = _run(
        same_version["findings"], next_candidate, NOW + timedelta(days=2)
    )

    assert same_version["finding_counts"]["ignored"] == 1
    assert same_version["finding_counts"]["new"] == 0
    assert next_version["finding_counts"]["ignored"] == 0
    assert next_version["finding_counts"]["new"] == 1


def test_restore_returns_a_reviewed_finding_to_new() -> None:
    candidate = findings.build_finding_candidates([_update()], [])
    active = _run({}, candidate)
    finding_id = active["active_findings"][0]["id"]
    acknowledged = findings.set_finding_review_state(
        active["findings"],
        finding_id,
        findings.REVIEW_ACKNOWLEDGED,
        NOW,
    )

    restored = findings.set_finding_review_state(
        acknowledged["findings"],
        finding_id,
        findings.REVIEW_NEW,
        NOW + timedelta(minutes=1),
    )

    assert restored["finding_counts"]["new"] == 1
    assert restored["finding_counts"]["acknowledged"] == 0
    assert "acknowledged_at" not in restored["active_findings"][0]


def test_review_action_rejects_unknown_or_non_active_findings() -> None:
    candidate = findings.build_finding_candidates([], [_health()])
    pending = _run({}, candidate)

    with pytest.raises(findings.FindingNotFound):
        findings.set_finding_review_state(
            pending["findings"], "missing:update", findings.REVIEW_IGNORED, NOW
        )
    with pytest.raises(findings.FindingNotActionable):
        findings.set_finding_review_state(
            pending["findings"],
            pending["pending_findings"][0]["id"],
            findings.REVIEW_IGNORED,
            NOW,
        )


def test_excluded_or_removed_repository_forgets_its_findings() -> None:
    candidates = findings.build_finding_candidates([_update()], [])
    first = _run({}, candidates)

    result = findings.update_findings(
        first["findings"], candidates, set(), set(), NOW + timedelta(days=1)
    )

    assert result["findings"] == {}
    assert result["active_finding_count"] == 0


def test_resolved_findings_are_pruned_after_thirty_days() -> None:
    candidates = findings.build_finding_candidates([_update()], [])
    active = _run({}, candidates)
    first_clear = _run(active["findings"], [], NOW + timedelta(days=1))
    resolved = _run(first_clear["findings"], [], NOW + timedelta(days=2))

    result = findings.update_findings(
        resolved["findings"],
        [],
        set(),
        {"owner/component"},
        NOW + timedelta(days=33),
    )

    assert result["recently_resolved_findings"] == []
    assert result["findings"] == {}
