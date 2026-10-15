"""To-do platform for reviewing HA Auditor findings."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.todo import (
    TodoItem,
    TodoItemStatus,
    TodoListEntity,
    TodoListEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import AuditorConfigEntry, ComponentsAuditor
from .const import DOMAIN
from .entity import AuditorEntity
from .findings import (
    REVIEW_ACKNOWLEDGED,
    REVIEW_NEW,
    FindingNotActionable,
    FindingNotFound,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AuditorConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the native finding review list."""
    manager = entry.runtime_data
    async_add_entities([AuditorFindingsTodo(manager, entry.entry_id)])


class AuditorFindingsTodo(AuditorEntity, TodoListEntity):
    """Expose active findings as one native Home Assistant to-do list."""

    _attr_translation_key = "findings"
    _attr_icon = "mdi:clipboard-check-outline"
    _attr_supported_features = TodoListEntityFeature.UPDATE_TODO_ITEM

    def __init__(self, manager: ComponentsAuditor, entry_id: str) -> None:
        super().__init__(manager, entry_id, "findings")
        self.entity_id = "todo.ha_auditor_findings"

    @property
    def todo_items(self) -> list[TodoItem]:
        """Return the current bounded list without performing I/O."""
        findings = self.manager.finding_attributes()["active_findings"]
        finding_filter = self.manager.finding_filter
        if finding_filter == "updates":
            findings = [item for item in findings if item.get("kind") == "update"]
        elif finding_filter == "archived":
            findings = [
                item
                for item in findings
                if item.get("finding_type") == "repository_archived"
            ]
        elif finding_filter == "abandoned":
            findings = [
                item
                for item in findings
                if item.get("finding_type") == "repository_abandoned"
            ]
        return [self._to_todo_item(finding) for finding in findings]

    async def async_update_todo_item(self, item: TodoItem) -> None:
        """A checkbox acknowledges a finding; clearing it restores the finding."""
        if not item.uid:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="finding_not_found",
            )
        review_status = (
            REVIEW_ACKNOWLEDGED
            if item.status == TodoItemStatus.COMPLETED
            else REVIEW_NEW
        )
        try:
            await self.manager.async_set_finding_review_state(item.uid, review_status)
        except FindingNotFound as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="finding_not_found",
            ) from err
        except FindingNotActionable as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="finding_not_active",
            ) from err

    @staticmethod
    def _to_todo_item(finding: dict[str, Any]) -> TodoItem:
        """Convert one localized finding into a native to-do item."""
        component = str(
            finding.get("component") or finding.get("repository") or "HA Auditor"
        )
        finding_type = str(
            finding.get("finding_type_label")
            or finding.get("finding_type")
            or "Finding"
        )
        summary = str(finding.get("summary") or "")
        summary_version = str(finding.get("summary_version") or "")
        evidence = f"{summary_version}: {summary}" if summary_version else summary
        description_parts = [
            str(value)
            for value in (
                evidence,
                finding.get("recommendation"),
                finding.get("repository"),
                finding.get("url"),
                finding.get("summary_url")
                if finding.get("summary_url") != finding.get("url")
                else None,
            )
            if value
        ]
        review_status = str(finding.get("review_status") or REVIEW_NEW)
        completed: datetime | None = None
        if review_status != REVIEW_NEW:
            completed = dt_util.parse_datetime(
                str(finding.get("review_updated_at") or "")
            )
        return TodoItem(
            uid=str(finding.get("finding_id") or ""),
            summary=f"{component}: {finding_type}",
            status=(
                TodoItemStatus.NEEDS_ACTION
                if review_status == REVIEW_NEW
                else TodoItemStatus.COMPLETED
            ),
            description="\n".join(description_parts) or None,
            completed=completed,
        )
