"""Binary sensor platform for HA Auditor."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
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
    """Set up the attention indicator."""
    manager: ComponentsAuditor = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([AuditorAttentionBinarySensor(manager, entry.entry_id)])


class AuditorAttentionBinarySensor(AuditorEntity, BinarySensorEntity):
    """Indicate actionable update risks or an incomplete audit."""

    _attr_translation_key = "attention_required"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_icon = "mdi:alert-circle-outline"

    def __init__(self, manager: ComponentsAuditor, entry_id: str) -> None:
        super().__init__(manager, entry_id, "attention_required")
        self.entity_id = "binary_sensor.ha_auditor_attention_required"

    @property
    def is_on(self) -> bool:
        """Return whether the latest result needs user attention."""
        return self.manager.attention_required

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose compact counts that explain the indicator."""
        counts = self.manager.data.get("available_update_counts", {})
        health = self.manager.data.get("repository_health_counts", {})
        return {
            "status": self.manager.data.get("status", "idle"),
            "critical_updates": counts.get("critical", 0),
            "important_updates": counts.get("important", 0),
            "unclassified_updates": counts.get("unknown", 0),
            "archived_repositories": health.get("archived", 0),
            "abandoned_repositories": health.get("abandoned", 0),
            "partial_audit": self.manager.data.get("partial_audit", False),
            "deferred_components": self.manager.data.get("deferred_components", 0),
            "cycle_complete": self.manager.data.get("cycle_complete", False),
        }
