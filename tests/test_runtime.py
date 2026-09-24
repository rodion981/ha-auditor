"""Home Assistant runtime tests for HA Auditor."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

pytest.importorskip("homeassistant")

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import MATCH_ALL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import ServiceValidationError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.custom_components_auditor import repairs
from custom_components.custom_components_auditor.const import (
    CONF_CLEAR_GITHUB_TOKEN,
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
from custom_components.custom_components_auditor.release import find_release_for_version
from custom_components.custom_components_auditor.todo import (
    AuditorFindingsTodo,
    TodoItem,
    TodoItemStatus,
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
        "select.ha_auditor_finding_filter": "all",
        "todo.ha_auditor_findings": "0",
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


async def test_config_and_options_flows_use_ui_only(hass: HomeAssistant) -> None:
    """Cover initial setup, duplicate prevention and secret-safe options."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "github_token": "flow-secret",
            "notify_service": "",
            "excluded_repositories": "owner/one\nowner/two",
            "daily_hour": 8,
            "weekly_weekday": "5",
            "max_requests_per_run": 30,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    entry = result["result"]
    assert entry.data["github_token"] == "flow-secret"
    assert entry.data["excluded_repositories"] == ["owner/one", "owner/two"]

    duplicate = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert duplicate["type"] is FlowResultType.ABORT
    assert duplicate["reason"] == "single_instance_allowed"

    options = await hass.config_entries.options.async_init(entry.entry_id)
    assert options["type"] is FlowResultType.FORM
    options = await hass.config_entries.options.async_configure(
        options["flow_id"],
        {
            "github_token": "",
            CONF_CLEAR_GITHUB_TOKEN: True,
            "notify_service": "",
            "excluded_repositories": "owner/two",
            "daily_hour": 10,
            "weekly_weekday": "6",
            "max_requests_per_run": 45,
        },
    )
    assert options["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options["github_token"] == ""
    assert entry.options["daily_hour"] == 10


async def test_repair_flow_replaces_or_removes_rejected_token(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Exercise the fixable Repair without exposing the submitted token."""
    entry = _entry()
    entry.add_to_hass(hass)
    validated: list[str] = []

    async def fake_validate(_hass: HomeAssistant, token: str) -> None:
        validated.append(token)

    monkeypatch.setattr(repairs, "_async_validate_token", fake_validate)
    flow = repairs.GitHubTokenRepairFlow()
    flow.hass = hass
    flow.data = {"entry_id": entry.entry_id}

    result = await flow.async_step_init()
    assert result["type"] is FlowResultType.FORM
    result = await flow.async_step_init(
        {"github_token": "replacement-secret", CONF_CLEAR_GITHUB_TOKEN: False}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert validated == ["replacement-secret"]
    assert entry.options["github_token"] == "replacement-secret"

    remove_flow = repairs.GitHubTokenRepairFlow()
    remove_flow.hass = hass
    remove_flow.data = {"entry_id": entry.entry_id}
    result = await remove_flow.async_step_init(
        {"github_token": "", CONF_CLEAR_GITHUB_TOKEN: True}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options["github_token"] == ""


async def test_repair_flow_translates_invalid_token(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Return a localized form error when GitHub rejects a replacement."""
    entry = _entry()
    entry.add_to_hass(hass)

    async def reject_token(_hass: HomeAssistant, _token: str) -> None:
        raise repairs.InvalidTokenError

    monkeypatch.setattr(repairs, "_async_validate_token", reject_token)
    flow = repairs.GitHubTokenRepairFlow()
    flow.hass = hass
    flow.data = {"entry_id": entry.entry_id}

    result = await flow.async_step_init(
        {"github_token": "rejected-secret", CONF_CLEAR_GITHUB_TOKEN: False}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_finding_action_persists_across_entry_reload(
    hass: HomeAssistant,
) -> None:
    """Exercise a native action and HA Store persistence through a reload."""
    entry = await _setup_entry(hass)
    manager = entry.runtime_data
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


async def test_todo_checkbox_acknowledges_and_restores_finding(
    hass: HomeAssistant,
) -> None:
    """Use the native to-do action without copying a finding ID into a form."""
    entry = await _setup_entry(hass)
    manager = entry.runtime_data
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
    manager.data.update(
        update_findings({}, candidates, {"example/archived"}, {"example/archived"}, now)
    )
    manager._publish()
    await hass.async_block_till_done()

    todo_state = hass.states.get("todo.ha_auditor_findings")
    assert todo_state is not None
    assert todo_state.state == "1"

    await hass.services.async_call(
        "select",
        "select_option",
        {
            "entity_id": "select.ha_auditor_finding_filter",
            "option": "updates",
        },
        blocking=True,
    )
    assert hass.states.get("todo.ha_auditor_findings").state == "0"
    await hass.services.async_call(
        "select",
        "select_option",
        {
            "entity_id": "select.ha_auditor_finding_filter",
            "option": "archived",
        },
        blocking=True,
    )
    assert hass.states.get("todo.ha_auditor_findings").state == "1"

    await hass.services.async_call(
        "todo",
        "update_item",
        {
            "entity_id": "todo.ha_auditor_findings",
            "item": "example/archived:health",
            "status": "completed",
        },
        blocking=True,
    )
    assert hass.states.get("todo.ha_auditor_findings").state == "0"
    finding_state = hass.states.get("sensor.ha_auditor_active_findings")
    assert finding_state is not None
    assert finding_state.attributes["finding_counts"]["acknowledged"] == 1

    await hass.services.async_call(
        "todo",
        "update_item",
        {
            "entity_id": "todo.ha_auditor_findings",
            "item": "example/archived:health",
            "status": "needs_action",
        },
        blocking=True,
    )
    assert hass.states.get("todo.ha_auditor_findings").state == "1"
    finding_state = hass.states.get("sensor.ha_auditor_active_findings")
    assert finding_state is not None
    assert finding_state.attributes["finding_counts"]["new"] == 1


async def test_todo_rejects_stale_finding_with_translated_error(
    hass: HomeAssistant,
) -> None:
    """Return a translated action error if a finding vanished before the update."""
    entry = await _setup_entry(hass)
    manager = entry.runtime_data
    entity = AuditorFindingsTodo(manager, entry.entry_id)

    with pytest.raises(ServiceValidationError) as raised:
        await entity.async_update_todo_item(
            TodoItem(
                uid="missing:finding",
                summary="Missing",
                status=TodoItemStatus.COMPLETED,
            )
        )

    assert raised.value.translation_domain == DOMAIN
    assert raised.value.translation_key == "finding_not_found"


async def test_finding_action_rejects_missing_finding_with_translated_error(
    hass: HomeAssistant,
) -> None:
    """Keep native action failures actionable and localizable."""
    await _setup_entry(hass)

    with pytest.raises(ServiceValidationError) as raised:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ACKNOWLEDGE_FINDING,
            {"finding_id": "missing:finding"},
            blocking=True,
        )

    assert raised.value.translation_domain == DOMAIN
    assert raised.value.translation_key == "finding_not_found"


async def test_diagnostics_exclude_private_values(hass: HomeAssistant) -> None:
    """Diagnostics expose useful counts without credentials or private targets."""
    entry = await _setup_entry(hass)
    manager = entry.runtime_data
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


async def test_full_audit_builds_confirmed_upgrade_path(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Exercise the complete manager pipeline for one multi-release update."""
    entry = await _setup_entry(hass)
    manager = entry.runtime_data
    repository = {
        "repository": "example/component",
        "entity_id": "update.example_component",
        "title": "Example component",
        "installed_version": "1.0.0",
        "latest_version": "3.0.0",
        "release_url": "https://github.com/example/component/releases/tag/v3.0.0",
        "update_available": True,
    }
    manager.data["components"] = {
        "example/component": {
            **repository,
            "initialized": True,
            "last_release_id": 1,
            "last_release_tag": "v1.0.0",
            "release_source": "release",
        }
    }

    monkeypatch.setattr(
        manager,
        "_discover_repositories",
        lambda: ([repository], 0, []),
    )

    async def fake_metadata(
        _repository: str,
    ) -> tuple[dict[str, object], int]:
        return (
            {
                "archived": False,
                "pushed_at": "2026-09-20T00:00:00Z",
                "html_url": "https://github.com/example/component",
            },
            4999,
        )

    releases = [
        {
            "id": 3,
            "tag_name": "v3.0.0",
            "name": "Version 3",
            "body": "Requires Home Assistant 2026.9 or newer. Security fix.",
            "published_at": "2026-09-20T00:00:00Z",
            "html_url": "https://github.com/example/component/releases/tag/v3.0.0",
            "source": "release",
            "draft": False,
            "prerelease": False,
        },
        {
            "id": 2,
            "tag_name": "v2.0.0",
            "name": "Version 2",
            "body": "Breaking change: remove the legacy option.",
            "published_at": "2026-08-20T00:00:00Z",
            "html_url": "https://github.com/example/component/releases/tag/v2.0.0",
            "source": "release",
            "draft": False,
            "prerelease": False,
        },
        {
            "id": 1,
            "tag_name": "v1.0.0",
            "name": "Version 1",
            "body": "Installed baseline.",
            "published_at": "2026-07-20T00:00:00Z",
            "html_url": "https://github.com/example/component/releases/tag/v1.0.0",
            "source": "release",
            "draft": False,
            "prerelease": False,
        },
    ]

    async def fake_releases(
        _repository: str,
        _etag: str | None,
        _latest_version: str,
        _installed_version: str,
    ) -> tuple[list[dict[str, object]], str, int]:
        return releases, "etag-v3", 4998

    monkeypatch.setattr(manager, "_fetch_repository_metadata", fake_metadata)
    monkeypatch.setattr(manager, "_fetch_releases", fake_releases)

    result = await manager._audit("full")

    assert result["checked_this_run"] == 1
    assert result["partial_audit"] is False
    assert result["new_release_count"] == 2
    assert result["updates_available"] == 1
    update = result["available_updates"][0]
    assert update["upgrade_path_status"] == "complete"
    assert update["versions_behind"] == 2
    assert update["version_path"] == ["1.0.0", "v2.0.0", "v3.0.0"]
    assert update["upgrade_signal_counts"]["breaking_changes"] == 1
    assert update["upgrade_signal_counts"]["security_fixes"] == 1
    assert update["minimum_home_assistant_version"] == "2026.9"
    assert result["finding_counts"]["new"] == 1


async def test_authenticated_release_search_stops_on_matching_page(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Follow bounded Release pages only until the HACS target is found."""
    entry = await _setup_entry(hass)
    manager = entry.runtime_data
    calls: list[tuple[str, str | None]] = []

    async def fake_github_get(
        _repository: str, path: str, etag: str | None = None
    ) -> tuple[object, str | None, int | None, bool]:
        calls.append((path, etag))
        if path == "releases?per_page=100&page=1":
            return ([{"id": 1, "tag_name": "v2.0.0"}], "fresh-etag", 4998, True)
        if path == "releases?per_page=100&page=2":
            return ([{"id": 2, "tag_name": "v1.6.0"}], None, 4997, True)
        raise AssertionError(f"Unexpected GitHub request: {path}")

    monkeypatch.setattr(manager, "_github_get", fake_github_get)
    releases, etag, remaining = await manager._fetch_releases(
        "owner/repository", "old-etag", "1.6.0"
    )

    assert releases is not None
    assert find_release_for_version(releases, "1.6.0") is not None
    assert calls == [
        ("releases?per_page=100&page=1", "old-etag"),
        ("releases?per_page=100&page=2", None),
    ]
    assert etag == "fresh-etag"
    assert remaining == 4997


async def test_authenticated_release_search_continues_to_installed_boundary(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Fetch the next bounded page when target is found but installed is not."""
    entry = await _setup_entry(hass)
    manager = entry.runtime_data
    calls: list[str] = []

    async def fake_github_get(
        _repository: str, path: str, _etag: str | None = None
    ) -> tuple[object, str | None, int | None, bool]:
        calls.append(path)
        if path == "releases?per_page=100&page=1":
            return ([{"id": 2, "tag_name": "v2.0.0"}], "fresh-etag", 4998, True)
        if path == "releases?per_page=100&page=2":
            return ([{"id": 1, "tag_name": "v1.0.0"}], None, 4997, False)
        raise AssertionError(f"Unexpected GitHub request: {path}")

    monkeypatch.setattr(manager, "_github_get", fake_github_get)
    releases, etag, remaining = await manager._fetch_releases(
        "owner/repository", "old-etag", "2.0.0", "1.0.0"
    )

    assert releases is not None
    assert find_release_for_version(releases, "2.0.0") is not None
    assert find_release_for_version(releases, "1.0.0") is not None
    assert calls == [
        "releases?per_page=100&page=1",
        "releases?per_page=100&page=2",
    ]
    assert etag == "fresh-etag"
    assert remaining == 4997


async def test_unauthenticated_search_uses_one_release_and_tag_page(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Keep anonymous lookup bounded while finding a target available as a tag."""
    entry = await _setup_entry(hass)
    manager = entry.runtime_data
    manager.token = ""
    calls: list[str] = []

    async def fake_github_get(
        _repository: str, path: str, _etag: str | None = None
    ) -> tuple[object, str | None, int | None, bool]:
        calls.append(path)
        if path == "releases?per_page=100&page=1":
            return ([{"id": 1, "tag_name": "v2.0.0"}], "etag", 58, True)
        if path == "tags?per_page=100&page=1":
            return (
                [{"name": "v1.6.0", "commit": {"sha": "a" * 40}}],
                None,
                57,
                True,
            )
        raise AssertionError(f"Unexpected GitHub request: {path}")

    monkeypatch.setattr(manager, "_github_get", fake_github_get)
    releases, _etag, remaining = await manager._fetch_releases(
        "owner/repository", None, "1.6.0"
    )

    assert releases is not None
    matched = find_release_for_version(releases, "1.6.0")
    assert matched is not None
    assert matched["source"] == "tag"
    assert calls == [
        "releases?per_page=100&page=1",
        "tags?per_page=100&page=1",
    ]
    assert remaining == 57


async def test_authenticated_release_pagination_is_capped_before_tag_fallback(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Never follow an unbounded number of authenticated Release pages."""
    entry = await _setup_entry(hass)
    manager = entry.runtime_data
    calls: list[str] = []

    async def fake_github_get(
        _repository: str, path: str, _etag: str | None = None
    ) -> tuple[object, str | None, int | None, bool]:
        calls.append(path)
        if path.startswith("releases?"):
            page = int(path.rsplit("=", 1)[-1])
            return ([{"id": page, "tag_name": f"v2.0.{page}"}], None, 5000, True)
        if path == "tags?per_page=100&page=1":
            return (
                [{"name": "v1.6.0", "commit": {"sha": "b" * 40}}],
                None,
                4996,
                False,
            )
        raise AssertionError(f"Unexpected GitHub request: {path}")

    monkeypatch.setattr(manager, "_github_get", fake_github_get)
    releases, _etag, remaining = await manager._fetch_releases(
        "owner/repository", None, "1.6.0"
    )

    assert releases is not None
    assert find_release_for_version(releases, "1.6.0")["source"] == "tag"
    assert calls == [
        "releases?per_page=100&page=1",
        "releases?per_page=100&page=2",
        "releases?per_page=100&page=3",
        "tags?per_page=100&page=1",
    ]
    assert remaining == 4996
