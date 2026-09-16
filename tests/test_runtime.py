"""Home Assistant runtime tests for HA Auditor."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

pytest.importorskip("homeassistant")

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import MATCH_ALL
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.custom_components_auditor.const import (
    DOMAIN,
    SERVICE_ACKNOWLEDGE_FINDING,
    SERVICE_IGNORE_FINDING,
    SERVICE_RESTORE_FINDING,
    SERVICE_RUN_AUDIT,
    SERVICE_SNOOZE_FINDING,
)
from custom_components.custom_components_auditor.diagnostics import (
    async_get_config_entry_diagnostics,
)
from custom_components.custom_components_auditor.entity import AuditorEntity
from custom_components.custom_components_auditor.findings import (
    build_finding_candidates,
    update_findings,
)

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


def _entry() -> MockConfigEntry:
    """Create a complete UI config entry for runtime tests."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="HA Auditor",
        unique_id=DOMAIN,
        data={
            "github_token": "runtime-secret-token",
            "notify_service": "notify.mobile_app_private_phone",
            "excluded_repositories": ["private-owner/private-repository"],
            "daily_hour": 9,
            "weekly_weekday": 6,
            "max_requests_per_run": 45,
        },
    )


async def _setup_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Set up one HA Auditor entry through Home Assistant's config manager."""
    entry = _entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    return entry


async def test_runtime_setup_registers_entities_and_actions(
    hass: HomeAssistant,
) -> None:
    """Set up and unload the integration through public HA interfaces."""
    entry = await _setup_entry(hass)

    expected_states = {
        "sensor.custom_components_auditor": "0",
        "sensor.ha_auditor_active_findings": "0",
        "binary_sensor.ha_auditor_attention_required": "off",
        "binary_sensor.ha_auditor_audit_problem": "off",
        "button.ha_auditor_run_audit": "unknown",
    }
    for entity_id, expected_state in expected_states.items():
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == expected_state

    for action in (
        SERVICE_RUN_AUDIT,
        SERVICE_ACKNOWLEDGE_FINDING,
        SERVICE_SNOOZE_FINDING,
        SERVICE_IGNORE_FINDING,
        SERVICE_RESTORE_FINDING,
    ):
        assert hass.services.has_service(DOMAIN, action)

    assert AuditorEntity._unrecorded_attributes == frozenset({MATCH_ALL})
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_finding_action_persists_across_entry_reload(
    hass: HomeAssistant,
) -> None:
    """Exercise a native action and HA Store persistence through a reload."""
    entry = await _setup_entry(hass)
    manager = hass.data[DOMAIN][entry.entry_id]
    now = datetime(2026, 9, 16, 9, 0, tzinfo=UTC)
    candidates = build_finding_candidates(
        [],
        [
            {
                "repository": "example/archived",
                "component": "Archived example",
                "status": "archived",
                "url": "https://github.com/example/archived",
            }
        ],
    )
    finding_result = update_findings(
        {}, candidates, {"example/archived"}, {"example/archived"}, now
    )
    manager.data.update(finding_result)
    manager._publish()
    await hass.async_block_till_done()

    await hass.services.async_call(
        DOMAIN,
        SERVICE_ACKNOWLEDGE_FINDING,
        {"finding_id": "example/archived:health"},
        blocking=True,
    )
    state = hass.states.get("sensor.ha_auditor_active_findings")
    assert state is not None
    assert state.attributes["finding_counts"]["acknowledged"] == 1
    assert state.attributes["active_findings"][0]["review_status"] == "acknowledged"

    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    state = hass.states.get("sensor.ha_auditor_active_findings")
    assert state is not None
    assert state.attributes["finding_counts"]["acknowledged"] == 1
    assert state.attributes["active_findings"][0]["review_status"] == "acknowledged"


async def test_diagnostics_exclude_private_values(hass: HomeAssistant) -> None:
    """Diagnostics expose useful counts without credentials or private targets."""
    entry = await _setup_entry(hass)
    manager = hass.data[DOMAIN][entry.entry_id]
    manager.data.update(
        {
            "status": "partial",
            "total_components": 108,
            "checked_this_run": 107,
            "active_finding_count": 9,
            "finding_counts": {"total": 9, "new": 2, "acknowledged": 7},
            "error_counts": {"network": 1},
        }
    )

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    serialized = json.dumps(diagnostics)

    assert diagnostics["configuration"] == {
        "github_token_configured": True,
        "notification_configured": True,
        "excluded_repository_count": 1,
        "daily_hour": 9,
        "weekly_weekday": 6,
        "max_requests_per_run": 45,
    }
    assert diagnostics["runtime"]["status"] == "partial"
    assert diagnostics["runtime"]["finding_counts"]["new"] == 2
    assert diagnostics["runtime"]["error_counts"] == {"network": 1}
    assert "runtime-secret-token" not in serialized
    assert "notify.mobile_app_private_phone" not in serialized
    assert "private-owner/private-repository" not in serialized
