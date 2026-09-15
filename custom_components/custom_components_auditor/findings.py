"""Persistent actionable findings for HA Auditor."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import UTC, datetime, timedelta
from typing import Any

_SEVERITY_ORDER = {"important": 1, "critical": 2}
_RESOLUTION_CONFIRMATIONS = 2
_RESOLVED_RETENTION_DAYS = 30
REVIEW_NEW = "new"
REVIEW_ACKNOWLEDGED = "acknowledged"
REVIEW_SNOOZED = "snoozed"
REVIEW_IGNORED = "ignored"
REVIEW_STATES = {
    REVIEW_NEW,
    REVIEW_ACKNOWLEDGED,
    REVIEW_SNOOZED,
    REVIEW_IGNORED,
}
SNOOZE_DAYS = {7, 30}


class FindingNotFound(KeyError):
    """Raised when a finding action targets an unknown stable ID."""


class FindingNotActionable(ValueError):
    """Raised when a finding action targets a non-active finding."""


def build_finding_candidates(
    available_updates: Iterable[Mapping[str, Any]],
    repository_health: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Build actionable candidates from current release and repository data."""
    candidates: list[dict[str, Any]] = []
    for update in available_updates:
        severity = str(update.get("severity") or "")
        if severity not in {"critical", "important"}:
            continue
        repository = str(update.get("repository") or "")
        latest_version = str(update.get("latest_version") or "")
        if not repository:
            continue
        candidates.append(
            {
                "id": f"{repository.casefold()}:update",
                "repository": repository,
                "component": str(update.get("component") or repository),
                "kind": "update",
                "finding_type": f"{severity}_update",
                "severity": severity,
                "fingerprint": f"update:{latest_version}:{severity}",
                "recommendation_key": "finding_recommendation_update",
                "installed_version": str(update.get("installed_version") or ""),
                "latest_version": latest_version,
                "reason": str(update.get("reason") or ""),
                "summary": str(update.get("summary") or ""),
                "url": str(update.get("url") or ""),
            }
        )

    for health in repository_health:
        status = str(health.get("status") or "")
        if status not in {"archived", "abandoned"}:
            continue
        repository = str(health.get("repository") or "")
        if not repository:
            continue
        candidates.append(
            {
                "id": f"{repository.casefold()}:health",
                "repository": repository,
                "component": str(health.get("component") or repository),
                "kind": "repository_health",
                "finding_type": f"repository_{status}",
                "severity": "important",
                "fingerprint": f"health:{status}",
                "recommendation_key": f"finding_recommendation_{status}",
                "pushed_at": str(health.get("pushed_at") or ""),
                "days_since_push": health.get("days_since_push"),
                "url": str(health.get("url") or ""),
            }
        )
    return candidates


def update_findings(
    existing: Mapping[str, Mapping[str, Any]],
    candidates: Iterable[Mapping[str, Any]],
    checked_repositories: Iterable[str],
    active_repositories: Iterable[str],
    now: datetime,
) -> dict[str, Any]:
    """Advance finding confirmation and resolution state after an audit run."""
    checked = {item.casefold() for item in checked_repositories}
    active_repositories_set = {item.casefold() for item in active_repositories}
    timestamp = now.isoformat()
    state = normalize_finding_workflow(
        {
            finding_id: dict(finding)
            for finding_id, finding in existing.items()
            if str(finding.get("repository") or "").casefold()
            in active_repositories_set
        },
        now,
    )
    candidate_map = {
        str(candidate["id"]): dict(candidate)
        for candidate in candidates
        if str(candidate.get("repository") or "").casefold() in checked
    }
    activated: list[dict[str, Any]] = []
    resolved: list[dict[str, Any]] = []

    for finding_id in list(state):
        finding = state[finding_id]
        repository = str(finding.get("repository") or "").casefold()
        if repository not in checked or finding_id in candidate_map:
            continue
        if finding.get("status") == "pending":
            del state[finding_id]
            continue
        if finding.get("status") != "active":
            continue
        finding["clear_confirmations"] = int(finding.get("clear_confirmations", 0)) + 1
        finding["last_checked"] = timestamp
        if finding["clear_confirmations"] >= _RESOLUTION_CONFIRMATIONS:
            finding["status"] = "resolved"
            finding["resolved_at"] = timestamp
            resolved.append(dict(finding))

    for finding_id, candidate in candidate_map.items():
        previous = state.get(finding_id)
        if (
            previous is None
            or previous.get("fingerprint") != candidate.get("fingerprint")
            or previous.get("status") == "resolved"
        ):
            if previous is not None and previous.get("status") in {
                "active",
                "resolved",
            }:
                archived = dict(previous)
                if archived.get("status") == "active":
                    archived["status"] = "resolved"
                    archived["resolved_at"] = timestamp
                    archived["resolution_reason"] = "superseded"
                    resolved.append(dict(archived))
                history_id = (
                    f"{finding_id}:resolved:{archived.get('resolved_at') or timestamp}"
                )
                state[history_id] = archived
            finding = {
                **candidate,
                "status": "pending",
                "review_status": REVIEW_NEW,
                "first_seen": timestamp,
                "last_seen": timestamp,
                "last_checked": timestamp,
                "confirmations": 1,
                "clear_confirmations": 0,
            }
        else:
            lifecycle = {
                key: previous[key]
                for key in (
                    "status",
                    "first_seen",
                    "activated_at",
                    "confirmations",
                    "clear_confirmations",
                    "review_status",
                    "review_updated_at",
                    "acknowledged_at",
                    "snoozed_at",
                    "snoozed_until",
                    "ignored_at",
                )
                if key in previous
            }
            finding = {
                **candidate,
                **lifecycle,
                "last_seen": timestamp,
                "last_checked": timestamp,
                "confirmations": int(previous.get("confirmations", 0)) + 1,
                "clear_confirmations": 0,
            }

        threshold = _confirmation_threshold(str(finding["finding_type"]))
        if finding["confirmations"] >= threshold and finding["status"] != "active":
            finding["status"] = "active"
            finding["activated_at"] = timestamp
            activated.append(dict(finding))
        state[finding_id] = finding

    _prune_resolved(state, now)
    summary = summarize_findings(state, now)
    return {
        "findings": state,
        **summary,
        "finding_changes": {
            "activated": activated,
            "resolved": resolved,
        },
    }


def normalize_finding_workflow(
    existing: Mapping[str, Mapping[str, Any]], now: datetime
) -> dict[str, dict[str, Any]]:
    """Normalize legacy workflow fields and reopen expired snoozes."""
    state = {finding_id: dict(finding) for finding_id, finding in existing.items()}
    for finding in state.values():
        review_status = str(finding.get("review_status") or REVIEW_NEW)
        if review_status not in REVIEW_STATES:
            review_status = REVIEW_NEW
        if review_status == REVIEW_SNOOZED:
            snoozed_until = _parse_timestamp(finding.get("snoozed_until"), now)
            if snoozed_until is None or snoozed_until <= now:
                review_status = REVIEW_NEW
                finding.pop("snoozed_at", None)
                finding.pop("snoozed_until", None)
                finding["review_updated_at"] = now.isoformat()
            else:
                finding["snoozed_until"] = snoozed_until.isoformat()
        finding["review_status"] = review_status
    return state


def set_finding_review_state(
    existing: Mapping[str, Mapping[str, Any]],
    finding_id: str,
    review_status: str,
    now: datetime,
    snooze_days: int | None = None,
) -> dict[str, Any]:
    """Apply one explicit user workflow action to an active finding."""
    if review_status not in REVIEW_STATES:
        raise ValueError(f"Unsupported finding review state: {review_status}")
    state = normalize_finding_workflow(existing, now)
    finding = state.get(finding_id)
    if finding is None:
        raise FindingNotFound(finding_id)
    if finding.get("status") != "active":
        raise FindingNotActionable(finding_id)

    for field in ("acknowledged_at", "snoozed_at", "snoozed_until", "ignored_at"):
        finding.pop(field, None)
    timestamp = now.isoformat()
    finding["review_status"] = review_status
    finding["review_updated_at"] = timestamp
    if review_status == REVIEW_ACKNOWLEDGED:
        finding["acknowledged_at"] = timestamp
    elif review_status == REVIEW_SNOOZED:
        if snooze_days not in SNOOZE_DAYS:
            raise ValueError("Snooze duration must be 7 or 30 days")
        finding["snoozed_at"] = timestamp
        finding["snoozed_until"] = (now + timedelta(days=snooze_days)).isoformat()
    elif review_status == REVIEW_IGNORED:
        finding["ignored_at"] = timestamp

    return {"findings": state, **summarize_findings(state, now)}


def summarize_findings(
    state: Mapping[str, Mapping[str, Any]], now: datetime | None = None
) -> dict[str, Any]:
    """Return bounded public lists and counts from stored finding state."""
    current = now or datetime.now(UTC)
    normalized = normalize_finding_workflow(state, current)
    active = [
        dict(item) for item in normalized.values() if item.get("status") == "active"
    ]
    pending_items = [
        dict(item) for item in normalized.values() if item.get("status") == "pending"
    ]
    recently_resolved = [
        dict(item) for item in normalized.values() if item.get("status") == "resolved"
    ]
    active.sort(key=_finding_sort_key, reverse=True)
    pending_items.sort(key=_finding_sort_key, reverse=True)
    recently_resolved.sort(
        key=lambda item: str(item.get("resolved_at") or ""), reverse=True
    )
    counts = {
        "total": len(active),
        "critical": sum(1 for item in active if item.get("severity") == "critical"),
        "important": sum(1 for item in active if item.get("severity") == "important"),
        "updates": sum(1 for item in active if item.get("kind") == "update"),
        "repository_health": sum(
            1 for item in active if item.get("kind") == "repository_health"
        ),
        "archived": sum(
            1 for item in active if item.get("finding_type") == "repository_archived"
        ),
        "abandoned": sum(
            1 for item in active if item.get("finding_type") == "repository_abandoned"
        ),
        "new": sum(1 for item in active if item.get("review_status") == REVIEW_NEW),
        "acknowledged": sum(
            1 for item in active if item.get("review_status") == REVIEW_ACKNOWLEDGED
        ),
        "snoozed": sum(
            1 for item in active if item.get("review_status") == REVIEW_SNOOZED
        ),
        "ignored": sum(
            1 for item in active if item.get("review_status") == REVIEW_IGNORED
        ),
    }
    return {
        "active_finding_count": len(active),
        "active_findings": active[:20],
        "recently_resolved_findings": recently_resolved[:20],
        "finding_counts": counts,
        "findings_pending_confirmation": len(pending_items),
        "pending_findings": pending_items[:20],
    }


def _confirmation_threshold(finding_type: str) -> int:
    """Return consecutive successful observations needed for activation."""
    return 2 if finding_type == "repository_abandoned" else 1


def _finding_sort_key(item: Mapping[str, Any]) -> tuple[int, str, str]:
    """Prioritize severity, then recent activation, then component name."""
    return (
        _SEVERITY_ORDER.get(str(item.get("severity") or ""), 0),
        str(item.get("activated_at") or item.get("first_seen") or ""),
        str(item.get("component") or "").casefold(),
    )


def _prune_resolved(state: dict[str, dict[str, Any]], now: datetime) -> None:
    """Forget resolved findings after the bounded retention period."""
    cutoff = now - timedelta(days=_RESOLVED_RETENTION_DAYS)
    for finding_id in list(state):
        finding = state[finding_id]
        if finding.get("status") != "resolved":
            continue
        try:
            resolved_at = datetime.fromisoformat(str(finding["resolved_at"]))
        except (KeyError, TypeError, ValueError):
            continue
        if resolved_at.tzinfo is None and now.tzinfo is not None:
            resolved_at = resolved_at.replace(tzinfo=now.tzinfo)
        if resolved_at < cutoff:
            del state[finding_id]


def _parse_timestamp(value: Any, reference: datetime) -> datetime | None:
    """Parse an ISO timestamp and align a legacy naive value to the reference."""
    try:
        parsed = datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None and reference.tzinfo is not None:
        parsed = parsed.replace(tzinfo=reference.tzinfo)
    return parsed
