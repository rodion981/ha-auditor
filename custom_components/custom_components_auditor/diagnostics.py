"""Diagnostics support for HA Auditor."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .config import normalize_settings
from .const import (
    CONF_DAILY_HOUR,
    CONF_EXCLUDED_REPOSITORIES,
    CONF_GITHUB_TOKEN,
    CONF_MAX_REQUESTS,
    CONF_NOTIFY_SERVICE,
    CONF_WEEKLY_WEEKDAY,
    DOMAIN,
)

_RUNTIME_KEYS = (
    "status",
    "last_attempt",
    "last_successful_audit",
    "last_weekly_digest",
    "audit_mode",
    "total_components",
    "targeted_this_run",
    "attempted_this_run",
    "checked_this_run",
    "deferred_components",
    "partial_audit",
    "cycle_complete",
    "updates_available",
    "active_finding_count",
    "findings_pending_confirmation",
    "github_authenticated",
    "github_rate_remaining",
)


def _safe_mapping(value: Any) -> dict[str, Any]:
    """Return a shallow JSON-safe copy of a diagnostic mapping."""
    return dict(value) if isinstance(value, Mapping) else {}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return privacy-preserving diagnostics for a config entry."""
    settings = normalize_settings(entry.data, entry.options)
    managers = hass.data.get(DOMAIN, {})
    manager = managers.get(entry.entry_id) if isinstance(managers, Mapping) else None
    runtime = manager.data if manager is not None else {}

    return {
        "configuration": {
            "github_token_configured": bool(settings[CONF_GITHUB_TOKEN]),
            "notification_configured": bool(settings[CONF_NOTIFY_SERVICE]),
            "excluded_repository_count": len(settings[CONF_EXCLUDED_REPOSITORIES]),
            "daily_hour": settings[CONF_DAILY_HOUR],
            "weekly_weekday": settings[CONF_WEEKLY_WEEKDAY],
            "max_requests_per_run": settings[CONF_MAX_REQUESTS],
        },
        "runtime": {
            **{key: runtime.get(key) for key in _RUNTIME_KEYS},
            "release_counts": _safe_mapping(runtime.get("counts")),
            "available_update_counts": _safe_mapping(
                runtime.get("available_update_counts")
            ),
            "repository_health_counts": _safe_mapping(
                runtime.get("repository_health_counts")
            ),
            "finding_counts": _safe_mapping(runtime.get("finding_counts")),
            "error_counts": _safe_mapping(runtime.get("error_counts")),
        },
    }
