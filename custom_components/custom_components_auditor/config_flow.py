"""Config and options flows for HA Auditor."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry, ConfigFlowResult
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .config import normalize_settings
from .const import (
    CONF_CLEAR_GITHUB_TOKEN,
    CONF_DAILY_HOUR,
    CONF_EXCLUDED_REPOSITORIES,
    CONF_GITHUB_TOKEN,
    CONF_MAX_REQUESTS,
    CONF_NOTIFY_SERVICE,
    CONF_WEEKLY_WEEKDAY,
    DOMAIN,
    WEEKDAY_OPTIONS,
)


def _settings_schema(current: dict[str, Any], *, allow_token_clear: bool) -> vol.Schema:
    """Build a localized form schema with current non-secret values."""
    schema: dict[vol.Marker, Any] = {
        vol.Optional(CONF_GITHUB_TOKEN, default=""): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
        vol.Optional(
            CONF_NOTIFY_SERVICE,
            default=current[CONF_NOTIFY_SERVICE],
        ): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
        vol.Optional(
            CONF_EXCLUDED_REPOSITORIES,
            default="\n".join(current[CONF_EXCLUDED_REPOSITORIES]),
        ): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT, multiline=True)),
        vol.Required(
            CONF_DAILY_HOUR,
            default=current[CONF_DAILY_HOUR],
        ): NumberSelector(
            NumberSelectorConfig(
                min=0,
                max=23,
                step=1,
                mode=NumberSelectorMode.BOX,
            )
        ),
        vol.Required(
            CONF_WEEKLY_WEEKDAY,
            default=str(current[CONF_WEEKLY_WEEKDAY]),
        ): SelectSelector(
            SelectSelectorConfig(
                options=list(WEEKDAY_OPTIONS),
                translation_key="weekday",
                mode=SelectSelectorMode.DROPDOWN,
            )
        ),
        vol.Required(
            CONF_MAX_REQUESTS,
            default=current[CONF_MAX_REQUESTS],
        ): NumberSelector(
            NumberSelectorConfig(
                min=1,
                max=500,
                step=1,
                mode=NumberSelectorMode.BOX,
            )
        ),
    }
    if allow_token_clear:
        schema[vol.Optional(CONF_CLEAR_GITHUB_TOKEN, default=False)] = BooleanSelector()
    return vol.Schema(schema)


class AuditorConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle setup of HA Auditor."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> AuditorOptionsFlow:
        """Return the options flow."""
        return AuditorOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Set up HA Auditor from the integrations page."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is not None:
            settings = normalize_settings(user_input)
            await self.async_set_unique_id(DOMAIN)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title="HA Auditor", data=settings)

        return self.async_show_form(
            step_id="user",
            data_schema=_settings_schema(normalize_settings(), allow_token_clear=False),
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Import a legacy YAML configuration once."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        settings = normalize_settings(import_data)
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(title="HA Auditor", data=settings)


class AuditorOptionsFlow(config_entries.OptionsFlow):
    """Allow HA Auditor settings to be changed without YAML."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage HA Auditor options."""
        current = normalize_settings(self.config_entry.data, self.config_entry.options)
        if user_input is not None:
            clear_token = bool(user_input.pop(CONF_CLEAR_GITHUB_TOKEN, False))
            new_token = str(user_input.pop(CONF_GITHUB_TOKEN, "") or "").strip()
            options = normalize_settings(user_input)

            if clear_token:
                options[CONF_GITHUB_TOKEN] = ""
            elif new_token:
                options[CONF_GITHUB_TOKEN] = new_token
            elif CONF_GITHUB_TOKEN in self.config_entry.options:
                options[CONF_GITHUB_TOKEN] = self.config_entry.options[
                    CONF_GITHUB_TOKEN
                ]
            else:
                options.pop(CONF_GITHUB_TOKEN, None)

            return self.async_create_entry(data=options)

        return self.async_show_form(
            step_id="init",
            data_schema=_settings_schema(current, allow_token_clear=True),
        )
