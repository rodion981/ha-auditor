"""Repair flows for HA Auditor."""

from __future__ import annotations

import asyncio
from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant.components.repairs import (
    ConfirmRepairFlow,
    RepairsFlow,
    RepairsFlowResult,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import CONF_GITHUB_TOKEN, TOKEN_REPAIR_ISSUE_ID


class GitHubTokenRepairFlow(RepairsFlow):
    """Replace and validate an invalid or expired GitHub token."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> RepairsFlowResult:
        """Validate a replacement token and update the config entry."""
        errors: dict[str, str] = {}
        if user_input is not None:
            token = str(user_input[CONF_GITHUB_TOKEN]).strip()
            try:
                await _async_validate_token(self.hass, token)
            except InvalidTokenError:
                errors["base"] = "invalid_auth"
            except CannotConnectError:
                errors["base"] = "cannot_connect"
            else:
                entry_id = str((self.data or {}).get("entry_id") or "")
                entry = self.hass.config_entries.async_get_entry(entry_id)
                if entry is None:
                    return self.async_abort(reason="entry_missing")
                options = dict(entry.options)
                options[CONF_GITHUB_TOKEN] = token
                self.hass.config_entries.async_update_entry(entry, options=options)
                return self.async_create_entry(data={})

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_GITHUB_TOKEN): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.PASSWORD)
                    )
                }
            ),
            errors=errors,
        )


async def _async_validate_token(hass: HomeAssistant, token: str) -> None:
    """Validate a GitHub token without storing or logging it."""
    session = async_get_clientsession(hass)
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2026-03-10",
        "User-Agent": "HA-Auditor/1.3.0-beta.2",
    }
    try:
        async with asyncio.timeout(20):
            async with session.get(
                "https://api.github.com/rate_limit", headers=headers
            ) as response:
                if response.status in {401, 403}:
                    raise InvalidTokenError
                if response.status >= 500:
                    raise CannotConnectError
                response.raise_for_status()
    except (InvalidTokenError, CannotConnectError):
        raise
    except (TimeoutError, aiohttp.ClientError) as err:
        raise CannotConnectError from err


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create a repair flow for a known HA Auditor issue."""
    if issue_id == TOKEN_REPAIR_ISSUE_ID:
        return GitHubTokenRepairFlow()
    return ConfirmRepairFlow()


class InvalidTokenError(Exception):
    """The replacement token was rejected by GitHub."""


class CannotConnectError(Exception):
    """GitHub could not be reached while validating a token."""
