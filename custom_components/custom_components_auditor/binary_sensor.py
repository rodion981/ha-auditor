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
    """Set up actionable-attention and audit-health indicators."""
    manager: ComponentsAuditor = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            AuditorAttentionBinarySensor(manager, entry.entry_id),
            AuditorAuditProblemBinarySensor(manager, entry.entry_id),
        ]
    )


class AuditorAttentionBinarySensor(AuditorEntity, BinarySensorEntity):
    """Indicate new actionable findings that have not been reviewed."""

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
        counts = self.manager.data.get("finding_counts", {})
        return {
            "status": self.manager.data.get("status", "idle"),
            "active_findings": counts.get("total", 0),
            "new_findings": counts.get("new", 0),
            "acknowledged_findings": counts.get("acknowledged", 0),
            "snoozed_findings": counts.get("snoozed", 0),
            "ignored_findings": counts.get("ignored", 0),
            "critical_findings": counts.get("critical", 0),
            "important_findings": counts.get("important", 0),
            "update_findings": counts.get("updates", 0),
            "repository_health_findings": counts.get("repository_health", 0),
            "archived_repositories": counts.get("archived", 0),
            "abandoned_repositories": counts.get("abandoned", 0),
            "pending_confirmation": self.manager.data.get(
                "findings_pending_confirmation", 0
            ),
        }


class AuditorAuditProblemBinarySensor(AuditorEntity, BinarySensorEntity):
    """Indicate a failed or incomplete GitHub audit."""

    _attr_translation_key = "audit_problem"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_icon = "mdi:cloud-alert-outline"

    def __init__(self, manager: ComponentsAuditor, entry_id: str) -> None:
        super().__init__(manager, entry_id, "audit_problem")
        self.entity_id = "binary_sensor.ha_auditor_audit_problem"

    @property
    def is_on(self) -> bool:
        """Return whether the latest audit failed or was incomplete."""
        return self.manager.audit_problem

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose compact diagnostics that explain the audit problem."""
        return {
            "status": self.manager.data.get("status", "idle"),
            "partial_audit": self.manager.data.get("partial_audit", False),
            "targeted_this_run": self.manager.data.get("targeted_this_run", 0),
            "checked_this_run": self.manager.data.get("checked_this_run", 0),
            "deferred_components": self.manager.data.get("deferred_components", 0),
            "cycle_complete": self.manager.data.get("cycle_complete", False),
            "error_counts": self.manager.data.get("error_counts", {}),
            "errors": self.manager.data.get("errors", [])[:5],
            "github_token_configured": self.manager.data.get(
                "github_token_configured", bool(self.manager.token)
            ),
            "github_authenticated": self.manager.data.get(
                "github_authenticated", bool(self.manager.token)
            ),
            "github_rate_remaining": self.manager.data.get("github_rate_remaining"),
        }
