"""Select platform for filtering HA Auditor findings."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AuditorConfigEntry, ComponentsAuditor
from .entity import AuditorEntity

FINDING_FILTERS = ("all", "updates", "archived", "abandoned")


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AuditorConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the native finding filter."""
    async_add_entities([AuditorFindingFilterSelect(entry.runtime_data, entry.entry_id)])


class AuditorFindingFilterSelect(AuditorEntity, SelectEntity):
    """Filter the shared finding review list by finding type."""

    _attr_translation_key = "finding_filter"
    _attr_icon = "mdi:filter-variant"
    _attr_options = list(FINDING_FILTERS)

    def __init__(self, manager: ComponentsAuditor, entry_id: str) -> None:
        super().__init__(manager, entry_id, "finding_filter")
        self.entity_id = "select.ha_auditor_finding_filter"

    @property
    def current_option(self) -> str:
        """Return the active finding filter."""
        return self.manager.finding_filter

    async def async_select_option(self, option: str) -> None:
        """Apply the selected filter to the native finding list."""
        self.manager.finding_filter = option
        self.manager._publish()
