"""Sensor platform for HA Auditor."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import ComponentsAuditor
from .const import DOMAIN, SENSOR_ENTITY_ID
from .entity import AuditorEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the audit result sensor."""
    manager: ComponentsAuditor = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([AuditorResultSensor(manager, entry.entry_id)])


class AuditorResultSensor(AuditorEntity, SensorEntity):
    """Expose the audit result while preserving the original entity ID."""

    _attr_translation_key = "new_releases"
    _attr_icon = "mdi:puzzle-check-outline"

    def __init__(self, manager: ComponentsAuditor, entry_id: str) -> None:
        super().__init__(manager, entry_id, "new_releases")
        self.entity_id = SENSOR_ENTITY_ID

    @property
    def native_value(self) -> int:
        """Return releases first seen during the most recent audit."""
        return int(self.manager.data.get("new_release_count", 0))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the bounded actionable audit details."""
        return self.manager.state_attributes()
