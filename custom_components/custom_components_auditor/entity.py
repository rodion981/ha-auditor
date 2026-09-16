"""Shared native entities for HA Auditor."""

from __future__ import annotations

from homeassistant.const import MATCH_ALL
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from . import ComponentsAuditor
from .const import DOMAIN


class AuditorEntity(Entity):
    """Base entity backed by the shared audit manager."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _unrecorded_attributes = frozenset({MATCH_ALL})

    def __init__(
        self,
        manager: ComponentsAuditor,
        entry_id: str,
        unique_suffix: str,
    ) -> None:
        self.manager = manager
        self._attr_unique_id = f"{entry_id}_{unique_suffix}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name="HA Auditor",
            manufacturer="rodion981",
            model="HACS Release Auditor",
        )

    async def async_added_to_hass(self) -> None:
        """Subscribe after Home Assistant has registered the entity."""
        await super().async_added_to_hass()
        self.async_on_remove(self.manager.async_add_listener(self._handle_update))

    @callback
    def _handle_update(self) -> None:
        """Publish manager data already available in memory."""
        self.async_write_ha_state()
