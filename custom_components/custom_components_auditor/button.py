"""Button platform for HA Auditor."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import ComponentsAuditor
from .const import DOMAIN
from .entity import AuditorEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the manual audit button."""
    manager: ComponentsAuditor = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([RunAuditButton(manager, entry.entry_id)])


class RunAuditButton(AuditorEntity, ButtonEntity):
    """Run a full audit without sending push notifications."""

    _attr_translation_key = "run_audit"
    _attr_icon = "mdi:refresh"

    def __init__(self, manager: ComponentsAuditor, entry_id: str) -> None:
        super().__init__(manager, entry_id, "run_audit")
        self.entity_id = "button.ha_auditor_run_audit"

    async def async_press(self) -> None:
        """Run the most complete audit allowed by the current credentials."""
        await self.manager.async_run("full", False)
