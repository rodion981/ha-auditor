"""Configuration helpers for HA Auditor."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .const import (
    CONF_CLEAR_GITHUB_TOKEN,
    CONF_DAILY_HOUR,
    CONF_EXCLUDED_REPOSITORIES,
    CONF_GITHUB_TOKEN,
    CONF_MAX_REQUESTS,
    CONF_NOTIFY_SERVICE,
    CONF_WEEKLY_WEEKDAY,
    DEFAULT_DAILY_HOUR,
    DEFAULT_EXCLUDED_REPOSITORIES,
    DEFAULT_MAX_REQUESTS,
    DEFAULT_NOTIFY_SERVICE,
    DEFAULT_WEEKLY_WEEKDAY,
)


def requested_repair_token(user_input: Mapping[str, Any]) -> str | None:
    """Return the replacement token, an empty removal request, or no choice."""
    if bool(user_input.get(CONF_CLEAR_GITHUB_TOKEN, False)):
        return ""
    token = str(user_input.get(CONF_GITHUB_TOKEN) or "").strip()
    return token or None


def repair_token_choice_submitted(user_input: Mapping[str, Any] | None) -> bool:
    """Return whether the Repair payload contains an actual user choice."""
    return user_input is not None and (
        CONF_GITHUB_TOKEN in user_input or CONF_CLEAR_GITHUB_TOKEN in user_input
    )


def normalize_settings(*sources: Mapping[str, Any]) -> dict[str, Any]:
    """Merge and normalize YAML, config-entry and options values."""
    settings: dict[str, Any] = {
        CONF_GITHUB_TOKEN: "",
        CONF_NOTIFY_SERVICE: DEFAULT_NOTIFY_SERVICE,
        CONF_DAILY_HOUR: DEFAULT_DAILY_HOUR,
        CONF_WEEKLY_WEEKDAY: DEFAULT_WEEKLY_WEEKDAY,
        CONF_MAX_REQUESTS: DEFAULT_MAX_REQUESTS,
        CONF_EXCLUDED_REPOSITORIES: list(DEFAULT_EXCLUDED_REPOSITORIES),
    }
    for source in sources:
        settings.update(source)

    settings[CONF_GITHUB_TOKEN] = str(settings[CONF_GITHUB_TOKEN] or "").strip()
    settings[CONF_NOTIFY_SERVICE] = str(settings[CONF_NOTIFY_SERVICE] or "").strip()
    settings[CONF_DAILY_HOUR] = int(settings[CONF_DAILY_HOUR])
    settings[CONF_WEEKLY_WEEKDAY] = int(settings[CONF_WEEKLY_WEEKDAY])
    settings[CONF_MAX_REQUESTS] = int(settings[CONF_MAX_REQUESTS])
    excluded_value = settings[CONF_EXCLUDED_REPOSITORIES]
    if isinstance(excluded_value, str):
        excluded_items = excluded_value.replace(",", "\n").splitlines()
    elif isinstance(excluded_value, (list, tuple, set)):
        excluded_items = excluded_value
    else:
        excluded_items = []
    settings[CONF_EXCLUDED_REPOSITORIES] = sorted(
        {
            str(item).strip().casefold().removesuffix(".git")
            for item in excluded_items
            if str(item).strip()
        }
    )

    if not 0 <= settings[CONF_DAILY_HOUR] <= 23:
        raise ValueError("daily_hour must be between 0 and 23")
    if not 0 <= settings[CONF_WEEKLY_WEEKDAY] <= 6:
        raise ValueError("weekly_weekday must be between 0 and 6")
    if not 1 <= settings[CONF_MAX_REQUESTS] <= 500:
        raise ValueError("max_requests_per_run must be between 1 and 500")

    return settings
