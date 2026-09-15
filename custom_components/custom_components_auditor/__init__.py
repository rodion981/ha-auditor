"""Release auditor for HACS repositories."""

from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import Callable, Mapping
from datetime import datetime, timedelta
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED, Platform
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_call_later, async_track_time_change
from homeassistant.helpers.storage import Store
from homeassistant.helpers.translation import async_get_translations
from homeassistant.util import dt as dt_util

from .config import normalize_settings
from .const import (
    ABANDONED_REPOSITORY_DAYS,
    CONF_DAILY_HOUR,
    CONF_EXCLUDED_REPOSITORIES,
    CONF_GITHUB_TOKEN,
    CONF_MAX_REQUESTS,
    CONF_NOTIFY_SERVICE,
    CONF_WEEKLY_WEEKDAY,
    DEFAULT_DAILY_HOUR,
    DEFAULT_MAX_REQUESTS,
    DEFAULT_NOTIFY_SERVICE,
    DEFAULT_WEEKLY_WEEKDAY,
    DOMAIN,
    MESSAGE_KEYS,
    SERVICE_RUN_AUDIT,
    SEVERITY_ORDER,
    STORE_KEY,
    STORE_VERSION,
    TOKEN_REPAIR_ISSUE_ID,
)
from .findings import (
    build_finding_candidates,
    summarize_findings,
    update_findings,
)
from .progress import audit_progress
from .release import (
    _merge_changes,
    add_tag_commit_shas,
    assess_available_update,
    assess_repository_health,
    assessment_needs_refresh,
    classification_reason,
    classify_release_details,
    find_release_for_version,
    localize,
    parse_rate_limit_reset,
    release_version_is_commit_sha,
    summarize_release,
    tags_as_release_candidates,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = (Platform.SENSOR, Platform.BINARY_SENSOR, Platform.BUTTON)

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Optional(DOMAIN): vol.Schema(
            {
                vol.Optional(CONF_GITHUB_TOKEN): cv.string,
                vol.Optional(
                    CONF_NOTIFY_SERVICE, default=DEFAULT_NOTIFY_SERVICE
                ): cv.string,
                vol.Optional(CONF_DAILY_HOUR, default=DEFAULT_DAILY_HOUR): vol.All(
                    vol.Coerce(int), vol.Range(min=0, max=23)
                ),
                vol.Optional(
                    CONF_WEEKLY_WEEKDAY, default=DEFAULT_WEEKLY_WEEKDAY
                ): vol.All(vol.Coerce(int), vol.Range(min=0, max=6)),
                vol.Optional(CONF_MAX_REQUESTS, default=DEFAULT_MAX_REQUESTS): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=500)
                ),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

SERVICE_SCHEMA = vol.Schema(
    {
        vol.Optional("mode", default="full"): vol.In(["daily", "full", "digest"]),
        vol.Optional("notify", default=True): cv.boolean,
    }
)

GITHUB_REPOSITORY_RE = re.compile(
    r"^https?://github\.com/([^/]+)/([^/#?]+)", re.IGNORECASE
)


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up actions and import a legacy YAML configuration."""
    managers: dict[str, ComponentsAuditor] = hass.data.setdefault(DOMAIN, {})

    async def handle_run(call: ServiceCall) -> None:
        manager = next(iter(managers.values()), None)
        if manager is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="not_configured",
            )
        await manager.async_run(call.data["mode"], call.data["notify"])

    hass.services.async_register(
        DOMAIN, SERVICE_RUN_AUDIT, handle_run, schema=SERVICE_SCHEMA
    )

    if yaml_config := config.get(DOMAIN):
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_IMPORT},
                data=dict(yaml_config),
            ),
            eager_start=True,
        )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up HA Auditor from a UI config entry."""
    settings = normalize_settings(entry.data, entry.options)
    translations = await async_get_translations(
        hass,
        str(hass.config.language or "en"),
        "common",
        {DOMAIN},
    )
    prefix = f"component.{DOMAIN}.common."
    messages = {key: translations.get(f"{prefix}{key}", key) for key in MESSAGE_KEYS}
    manager = ComponentsAuditor(hass, entry.entry_id, settings, messages)
    await manager.async_initialize()

    managers: dict[str, ComponentsAuditor] = hass.data.setdefault(DOMAIN, {})
    managers[entry.entry_id] = manager
    try:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except Exception:
        managers.pop(entry.entry_id, None)
        manager.async_shutdown()
        raise
    manager.async_start_schedules()
    manager.add_unsubscriber(entry.add_update_listener(_async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload HA Auditor and cancel all background callbacks."""
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    managers: dict[str, ComponentsAuditor] = hass.data.get(DOMAIN, {})
    manager = managers.pop(entry.entry_id, None)
    if manager is not None:
        manager.async_shutdown()
    return True


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove repair issues when the HA Auditor entry is deleted."""
    ir.async_delete_issue(hass, DOMAIN, TOKEN_REPAIR_ISSUE_ID)


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload HA Auditor after its UI options change."""
    await hass.config_entries.async_reload(entry.entry_id)


class ComponentsAuditor:
    """Discover HACS update entities and audit GitHub releases."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        config: Mapping[str, Any],
        messages: Mapping[str, str],
    ) -> None:
        self.hass = hass
        self.entry_id = entry_id
        self.messages = messages
        self.token = config.get(CONF_GITHUB_TOKEN, "").strip()
        self.notify_service = config[CONF_NOTIFY_SERVICE]
        self.daily_hour = config[CONF_DAILY_HOUR]
        self.weekly_weekday = config[CONF_WEEKLY_WEEKDAY]
        self.max_requests = config[CONF_MAX_REQUESTS]
        self.excluded_repositories = set(config[CONF_EXCLUDED_REPOSITORIES])
        self.store: Store[dict[str, Any]] = Store(hass, STORE_VERSION, STORE_KEY)
        self.lock = asyncio.Lock()
        self.data: dict[str, Any] = {}
        self._unsubscribers: list[Any] = []
        self._listeners: set[Callable[[], None]] = set()

    async def async_initialize(self) -> None:
        """Restore the previous checkpoint and publish the sensor."""
        stored = await self.store.async_load()
        self.data = stored if isinstance(stored, dict) else {}
        self.data.setdefault("components", {})
        self.data.setdefault("latest_changes", [])
        self.data.setdefault("pending_changes", [])
        self.data.setdefault("cursor", 0)
        self.data.setdefault("status", "idle")
        if not isinstance(self.data.get("findings"), Mapping):
            self.data["findings"] = {}
        self.data.update(summarize_findings(self.data["findings"]))
        self.data.setdefault("finding_changes", {"activated": [], "resolved": []})
        self._publish()

    def add_unsubscriber(self, unsubscribe: Any) -> None:
        """Track a callback that must be removed when the entry unloads."""
        self._unsubscribers.append(unsubscribe)

    @callback
    def async_add_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        """Subscribe a native entity to manager data changes."""
        self._listeners.add(listener)

        @callback
        def remove_listener() -> None:
            self._listeners.discard(listener)

        return remove_listener

    def async_start_schedules(self) -> None:
        """Start the delayed baseline and recurring audit schedules."""

        @callback
        def schedule_startup(_: Any = None) -> None:
            if not self.data.get("last_checked"):
                self.add_unsubscriber(
                    async_call_later(
                        self.hass,
                        120,
                        lambda _now: self.hass.async_create_task(
                            self.async_run("daily", False), eager_start=True
                        ),
                    )
                )

        if self.hass.is_running:
            schedule_startup()
        else:
            self.add_unsubscriber(
                self.hass.bus.async_listen_once(
                    EVENT_HOMEASSISTANT_STARTED, schedule_startup
                )
            )

        async def scheduled_audit(now: datetime) -> None:
            local_now = dt_util.as_local(now)
            weekly = local_now.weekday() == self.weekly_weekday
            await self.async_run("digest" if weekly else "daily", True)

        self.add_unsubscriber(
            async_track_time_change(
                self.hass,
                scheduled_audit,
                hour=self.daily_hour,
                minute=15,
                second=0,
            )
        )

    @callback
    def async_shutdown(self) -> None:
        """Cancel listeners and timers registered for this config entry."""
        while self._unsubscribers:
            self._unsubscribers.pop()()
        self._listeners.clear()

    async def async_run(self, mode: str, notify: bool) -> None:
        """Run one audit without overlapping another run."""
        if self.lock.locked():
            _LOGGER.warning("Custom Components Auditor is already running")
            return

        async with self.lock:
            attempt_at = dt_util.utcnow().isoformat()
            self.data["status"] = "running"
            self.data["last_error"] = ""
            self.data["last_attempt"] = attempt_at
            self._publish()
            try:
                result = await self._audit(mode)
                self.data.update(result)
                self.data["status"] = "partial" if result["partial_audit"] else "idle"
                # Keep last_checked for backwards compatibility with the v1 card.
                self.data["last_checked"] = attempt_at
                if not result["partial_audit"]:
                    self.data["last_successful_audit"] = attempt_at
                if mode == "digest":
                    self.data["last_weekly_digest"] = dt_util.utcnow().isoformat()
                await self.store.async_save(self.data)
                self._publish()

                should_notify = notify and (
                    mode == "digest"
                    or result["counts"]["critical"] > 0
                    or result["counts"]["important"] > 0
                    or bool(result["finding_changes"]["activated"])
                )
                if should_notify:
                    delivered = await self._notify(mode)
                    if mode == "digest" and delivered and not result["partial_audit"]:
                        self.data["pending_changes"] = []
                        await self.store.async_save(self.data)
                        self._publish()
            except Exception as err:  # noqa: BLE001 - keep scheduled job alive
                _LOGGER.exception("Custom Components Auditor failed")
                self.data["status"] = "error"
                self.data["last_error"] = str(err)[:255]
                self.data["last_checked"] = attempt_at
                await self.store.async_save(self.data)
                self._publish()

    async def _audit(self, mode: str) -> dict[str, Any]:
        repositories, skipped, excluded = self._discover_repositories()
        component_state = self.data.setdefault("components", {})
        active_keys = {item["repository"].lower() for item in repositories}
        component_state = {
            key: value for key, value in component_state.items() if key in active_keys
        }
        total = len(repositories)
        request_limit = (
            max(self.max_requests, total)
            if self.token
            else max(min(self.max_requests, 60) // 3, 1)
        )

        if mode in ("full", "digest") and self.token:
            selected = repositories
            next_cursor = 0
        else:
            cursor = int(self.data.get("cursor", 0)) % max(total, 1)
            ordered = repositories[cursor:] + repositories[:cursor]
            selected = ordered[:request_limit]
            next_cursor = (cursor + len(selected)) % max(total, 1)

        changes: list[dict[str, Any]] = []
        error_details: list[dict[str, str]] = []
        rate_remaining: int | None = None
        attempted = 0
        checked_successfully = 0
        checked_repositories: set[str] = set()

        for repository in selected:
            attempted += 1
            key = repository["repository"].lower()
            previous = component_state.get(key, {})
            try:
                metadata, metadata_remaining = await self._fetch_repository_metadata(
                    repository["repository"]
                )
                if metadata_remaining is not None:
                    rate_remaining = metadata_remaining
                previous_assessment = previous.get("available_update")
                etag = previous.get("etag")
                if previous.get("release_source") != "release":
                    etag = None
                if repository["update_available"] and (
                    assessment_needs_refresh(
                        previous_assessment, repository["latest_version"]
                    )
                ):
                    etag = None
                releases, etag, release_remaining = await self._fetch_releases(
                    repository["repository"],
                    etag,
                    repository["latest_version"]
                    if repository["update_available"]
                    else "",
                )
                if release_remaining is not None:
                    rate_remaining = release_remaining
            except RateLimitReached as err:
                error_details.append(
                    self._make_error_detail(repository, err.category, str(err))
                )
                break
            except GitHubRequestError as err:
                _LOGGER.warning("Audit failed for %s: %s", key, err)
                error_details.append(
                    self._make_error_detail(repository, err.category, str(err))
                )
                if err.category == "authentication":
                    break
                continue
            except Exception as err:  # noqa: BLE001 - isolate one repository
                _LOGGER.warning("Audit failed for %s: %s", key, err)
                error_details.append(
                    self._make_error_detail(repository, "unknown", str(err))
                )
                continue

            checked_successfully += 1
            current = {
                **previous,
                **repository,
                "checked_at": dt_util.utcnow().isoformat(),
                "repository_health": assess_repository_health(
                    metadata,
                    dt_util.utcnow(),
                    ABANDONED_REPOSITORY_DAYS,
                ),
            }
            if etag:
                current["etag"] = etag

            if releases is not None:
                published = [item for item in releases if not item.get("draft")]
                current["release_source"] = (
                    str(published[0].get("source") or "release")
                    if published
                    else "none"
                )
                last_id = previous.get("last_release_id")
                last_tag = previous.get("last_release_tag")
                initialized = bool(previous.get("initialized"))
                unseen: list[dict[str, Any]] = []
                for release in published:
                    if release.get("id") == last_id or (
                        last_tag and release.get("tag_name") == last_tag
                    ):
                        break
                    unseen.append(release)

                if published:
                    newest = published[0]
                    newest_tag = newest.get("tag_name", "")
                    if (
                        previous.get("last_release_tag")
                        and previous.get("last_release_tag") != newest_tag
                    ):
                        current["previous_release_tag"] = previous["last_release_tag"]
                    current["last_release_id"] = newest.get("id")
                    current["last_release_tag"] = newest_tag
                    current["last_release_at"] = (
                        newest.get("published_at") or newest.get("created_at") or ""
                    )
                    current["last_release_url"] = newest.get("html_url", "")

                if initialized:
                    for release in reversed(unseen):
                        changes.append(self._make_change(repository, release))

                current["initialized"] = True

                if repository["update_available"]:
                    current["available_update"] = assess_available_update(
                        repository, published, self.messages
                    )
                else:
                    current.pop("available_update", None)
            elif not repository["update_available"]:
                current.pop("available_update", None)

            component_state[key] = current
            checked_repositories.add(key)
            await asyncio.sleep(0.15)

        changes.sort(
            key=lambda item: (
                SEVERITY_ORDER.get(item["severity"], -1),
                item.get("published_at", ""),
            ),
            reverse=True,
        )
        counts = {key: 0 for key in (*SEVERITY_ORDER, "unknown")}
        for change in changes:
            counts[change["severity"]] += 1

        latest_changes = _merge_changes(
            changes, self.data.get("latest_changes", []), 12
        )
        pending_changes = _merge_changes(
            changes, self.data.get("pending_changes", []), 100
        )
        stale_components = self._get_stale_components(component_state)
        repository_health_details = self._get_repository_health_details(component_state)
        repository_health_counts = {
            "archived": sum(
                1 for item in repository_health_details if item["status"] == "archived"
            ),
            "abandoned": sum(
                1 for item in repository_health_details if item["status"] == "abandoned"
            ),
        }
        updates_available = sum(1 for item in repositories if item["update_available"])
        available_updates = self._get_available_updates(repositories, component_state)
        available_update_counts = {key: 0 for key in (*SEVERITY_ORDER, "unknown")}
        for update in available_updates:
            severity = update.get("severity", "unknown")
            available_update_counts[severity] = (
                available_update_counts.get(severity, 0) + 1
            )
        error_counts: dict[str, int] = {}
        for error in error_details:
            category = error["category"]
            error_counts[category] = error_counts.get(category, 0) + 1
        authentication_failed = error_counts.get("authentication", 0) > 0
        self._sync_token_repair(authentication_failed)
        progress = audit_progress(
            total,
            len(selected),
            attempted,
            checked_successfully,
            len(error_details),
        )
        finding_result = update_findings(
            self.data.get("findings", {}),
            build_finding_candidates(available_updates, repository_health_details),
            checked_repositories,
            active_keys,
            dt_util.utcnow(),
        )

        return {
            "components": component_state,
            "audit_mode": mode,
            "total_components": total,
            "targeted_this_run": len(selected),
            "attempted_this_run": attempted,
            "checked_this_run": checked_successfully,
            **progress,
            "new_release_count": len(changes),
            "counts": counts,
            "last_run_changes": changes[:12],
            "latest_changes": latest_changes,
            "pending_changes": pending_changes,
            "updates_available": updates_available,
            "available_updates": available_updates,
            "available_update_counts": available_update_counts,
            "up_to_date_components": max(total - updates_available, 0),
            "stale_components": len(stale_components),
            "stale_component_details": stale_components,
            "repository_health_counts": repository_health_counts,
            "repository_health_details": repository_health_details,
            "skipped_components": skipped,
            "excluded_components": len(excluded),
            "excluded_repositories": excluded,
            "errors": [item["message"] for item in error_details[:10]],
            "error_details": error_details[:10],
            "error_counts": error_counts,
            "cursor": next_cursor,
            "github_token_configured": bool(self.token),
            "github_authenticated": bool(self.token) and not authentication_failed,
            "github_rate_remaining": rate_remaining,
            **finding_result,
        }

    @callback
    def _sync_token_repair(self, authentication_failed: bool) -> None:
        """Create or clear the repair issue for an invalid GitHub token."""
        if self.token and authentication_failed:
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                TOKEN_REPAIR_ISSUE_ID,
                data={"entry_id": self.entry_id},
                is_fixable=True,
                is_persistent=True,
                severity=ir.IssueSeverity.ERROR,
                translation_key=TOKEN_REPAIR_ISSUE_ID,
            )
            return
        ir.async_delete_issue(self.hass, DOMAIN, TOKEN_REPAIR_ISSUE_ID)

    def _get_available_updates(
        self,
        repositories: list[dict[str, Any]],
        component_state: Mapping[str, Mapping[str, Any]],
    ) -> list[dict[str, Any]]:
        """Return current HACS updates enriched with matching release details."""
        updates: list[dict[str, Any]] = []
        for repository in repositories:
            if not repository["update_available"]:
                continue
            stored = component_state.get(repository["repository"].lower(), {})
            assessment = stored.get("available_update")
            if (
                isinstance(assessment, Mapping)
                and assessment.get("latest_version") == repository["latest_version"]
            ):
                updates.append(self._with_localized_reason(assessment))
                continue
            updates.append(
                {
                    "repository": repository["repository"],
                    "component": repository["title"],
                    "entity_id": repository["entity_id"],
                    "installed_version": repository["installed_version"],
                    "latest_version": repository["latest_version"],
                    "release_status": "not_checked",
                    "release_status_label": localize(
                        self.messages, "release_status_not_checked"
                    ),
                    "severity": "unknown",
                    "reason": localize(self.messages, "not_checked"),
                    "matched_term": "",
                    "summary": "",
                    "url": repository["release_url"],
                    "published_at": "",
                }
            )
        updates.sort(
            key=lambda item: (
                SEVERITY_ORDER.get(str(item.get("severity")), -1),
                str(item.get("component", "")).casefold(),
            ),
            reverse=True,
        )
        return updates

    def _with_localized_reason(self, item: Mapping[str, Any]) -> dict[str, Any]:
        """Render a stored assessment in the currently selected HA language."""
        localized = dict(item)
        release_status = str(item.get("release_status") or "")
        if release_status == "matched":
            release_status = "found"
            localized["release_status"] = release_status
        status_message_key = {
            "found": "release_status_found",
            "not_found": "release_status_not_found",
            "not_checked": "release_status_not_checked",
        }.get(release_status)
        if item.get("release_source") == "tag":
            status_message_key = "release_status_tag_found"
        if status_message_key:
            localized["release_status_label"] = localize(
                self.messages, status_message_key
            )
        if release_status == "not_found":
            localized["reason"] = localize(self.messages, "release_not_found")
        elif release_status == "not_checked":
            localized["reason"] = localize(self.messages, "not_checked")
        elif item.get("release_source") == "tag":
            localized["reason"] = localize(self.messages, "tag_fallback_reason")
        elif item.get("severity") in SEVERITY_ORDER:
            localized["reason"] = classification_reason(
                str(item["severity"]),
                str(item.get("matched_term") or ""),
                self.messages,
            )
        return localized

    @staticmethod
    def _make_error_detail(
        repository: Mapping[str, Any], category: str, message: str
    ) -> dict[str, str]:
        """Build a compact error record suitable for a sensor attribute."""
        return {
            "component": str(repository["title"]),
            "repository": str(repository["repository"]),
            "category": category,
            "message": str(message)[:180],
        }

    def _discover_repositories(
        self,
    ) -> tuple[list[dict[str, Any]], int, list[str]]:
        registry = er.async_get(self.hass)
        found: dict[str, dict[str, Any]] = {}
        skipped = 0
        excluded: list[str] = []

        for entry in registry.entities.values():
            if (
                entry.domain != "update"
                or entry.platform != "hacs"
                or entry.disabled_by is not None
            ):
                continue
            state = self.hass.states.get(entry.entity_id)
            if state is None:
                skipped += 1
                continue
            attributes = state.attributes
            release_url = str(attributes.get("release_url") or "")
            match = GITHUB_REPOSITORY_RE.match(release_url)
            if not match:
                skipped += 1
                continue
            repository_name = match.group(2)
            if repository_name.casefold().endswith(".git"):
                repository_name = repository_name[:-4]
            repository = f"{match.group(1)}/{repository_name}"
            key = repository.lower()
            if key in self.excluded_repositories:
                excluded.append(repository)
                continue
            found[key] = {
                "repository": repository,
                "entity_id": entry.entity_id,
                "title": str(
                    attributes.get("title")
                    or attributes.get("friendly_name")
                    or repository
                ),
                "installed_version": str(attributes.get("installed_version") or ""),
                "latest_version": str(attributes.get("latest_version") or ""),
                "release_url": release_url,
                "update_available": state.state == "on",
            }

        return (
            sorted(found.values(), key=lambda item: item["title"].casefold()),
            skipped,
            sorted(excluded, key=str.casefold),
        )

    async def _fetch_repository_metadata(
        self, repository: str
    ) -> tuple[dict[str, Any], int | None]:
        """Fetch repository status and activity metadata."""
        payload, _etag, remaining = await self._github_get(repository, "")
        if not isinstance(payload, dict):
            raise GitHubRequestError(
                "github",
                localize(self.messages, "error_network", error="invalid metadata"),
            )
        return payload, remaining

    async def _fetch_releases(
        self, repository: str, etag: str | None, latest_version: str
    ) -> tuple[list[dict[str, Any]] | None, str | None, int | None]:
        payload, response_etag, remaining = await self._github_get(
            repository, "releases?per_page=10", etag
        )
        if payload is None:
            return None, response_etag, remaining
        if not isinstance(payload, list):
            raise GitHubRequestError(
                "github",
                localize(self.messages, "error_network", error="invalid releases"),
            )
        if payload:
            releases = [dict(item, source="release") for item in payload]
            if release_version_is_commit_sha(latest_version) and not (
                find_release_for_version(releases, latest_version)
            ):
                tags, _tag_etag, tag_remaining = await self._github_get(
                    repository, "tags?per_page=100"
                )
                if not isinstance(tags, list):
                    raise GitHubRequestError(
                        "github",
                        localize(self.messages, "error_network", error="invalid tags"),
                    )
                releases = add_tag_commit_shas(releases, tags)
                if tag_remaining is not None:
                    remaining = tag_remaining
            return (
                releases,
                response_etag,
                remaining,
            )

        tags, _tag_etag, tag_remaining = await self._github_get(
            repository, "tags?per_page=100"
        )
        if not isinstance(tags, list):
            raise GitHubRequestError(
                "github",
                localize(self.messages, "error_network", error="invalid tags"),
            )
        return (
            tags_as_release_candidates(repository, tags),
            response_etag,
            tag_remaining if tag_remaining is not None else remaining,
        )

    async def _github_get(
        self, repository: str, path: str, etag: str | None = None
    ) -> tuple[Any, str | None, int | None]:
        """Fetch one GitHub API resource with shared error handling."""
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2026-03-10",
            "User-Agent": "HA-Auditor/1.4.0-beta.1",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        if etag:
            headers["If-None-Match"] = etag

        suffix = f"/{path}" if path else ""
        url = f"https://api.github.com/repos/{repository}{suffix}"
        session = async_get_clientsession(self.hass)
        try:
            async with asyncio.timeout(25):
                async with session.get(url, headers=headers) as response:
                    remaining_raw = response.headers.get("X-RateLimit-Remaining")
                    remaining = (
                        int(remaining_raw)
                        if remaining_raw and remaining_raw.isdigit()
                        else None
                    )
                    if response.status == 304:
                        return None, etag, remaining
                    if response.status == 401:
                        raise GitHubRequestError(
                            "authentication",
                            localize(self.messages, "error_authentication_401"),
                        )
                    if response.status == 429 or (
                        response.status == 403 and remaining == 0
                    ):
                        reset_raw = response.headers.get("X-RateLimit-Reset", "unknown")
                        reset_at = parse_rate_limit_reset(reset_raw)
                        reset = (
                            dt_util.as_local(reset_at).strftime("%Y-%m-%d %H:%M %Z")
                            if reset_at is not None
                            else reset_raw
                        )
                        raise RateLimitReached(
                            localize(self.messages, "error_rate_limit", reset=reset)
                        )
                    if response.status == 403:
                        raise GitHubRequestError(
                            "authentication",
                            localize(self.messages, "error_authentication_403"),
                        )
                    if response.status == 404:
                        raise GitHubRequestError(
                            "repository_not_found",
                            localize(
                                self.messages,
                                "error_repository_not_found",
                                repository=repository,
                            ),
                        )
                    if response.status >= 500:
                        raise GitHubRequestError(
                            "github",
                            localize(
                                self.messages,
                                "error_github_status",
                                status=response.status,
                            ),
                        )
                    response.raise_for_status()
                    payload = await response.json()
                    return payload, response.headers.get("ETag"), remaining
        except (GitHubRequestError, RateLimitReached):
            raise
        except TimeoutError as err:
            raise GitHubRequestError(
                "network",
                localize(self.messages, "error_timeout", repository=repository),
            ) from err
        except Exception as err:
            raise GitHubRequestError(
                "network",
                localize(self.messages, "error_network", error=str(err)[:120]),
            ) from err

    def _make_change(
        self, repository: Mapping[str, Any], release: Mapping[str, Any]
    ) -> dict[str, Any]:
        body = str(release.get("body") or "")
        title = str(
            release.get("name")
            or release.get("tag_name")
            or localize(self.messages, "new_release")
        )
        release_source = str(release.get("source") or "release")
        if release_source == "tag":
            severity, matched_term = "unknown", ""
            reason = localize(self.messages, "tag_fallback_reason")
        else:
            severity, matched_term = classify_release_details(f"{title}\n{body}")
            reason = classification_reason(severity, matched_term, self.messages)
        return {
            "repository": repository["repository"],
            "component": repository["title"],
            "installed_version": repository["installed_version"],
            "version": str(release.get("tag_name") or title),
            "release_source": release_source,
            "severity": severity,
            "reason": reason,
            "matched_term": matched_term,
            "summary": summarize_release(body),
            "url": str(release.get("html_url") or repository["release_url"]),
            "published_at": str(
                release.get("published_at") or release.get("created_at") or ""
            ),
        }

    def _get_stale_components(
        self, components: Mapping[str, Mapping[str, Any]]
    ) -> list[dict[str, Any]]:
        """Return components whose latest GitHub release is over one year old."""
        threshold = dt_util.utcnow() - timedelta(days=365)
        stale: list[dict[str, Any]] = []
        for component in components.values():
            published = component.get("last_release_at")
            if not published:
                continue
            parsed = dt_util.parse_datetime(published)
            if parsed is not None and parsed < threshold:
                stale.append(
                    {
                        "component": str(
                            component.get("title")
                            or localize(self.messages, "unknown_component")
                        ),
                        "version": str(component.get("last_release_tag") or ""),
                        "published_at": str(published),
                        "days_without_release": (dt_util.utcnow() - parsed).days,
                        "url": str(
                            component.get("last_release_url")
                            or component.get("release_url")
                            or ""
                        ),
                    }
                )
        stale.sort(key=lambda item: item["days_without_release"], reverse=True)
        return stale

    def _get_repository_health_details(
        self,
        components: Mapping[str, Mapping[str, Any]],
    ) -> list[dict[str, Any]]:
        """Return archived and long-abandoned repositories."""
        details: list[dict[str, Any]] = []
        for component in components.values():
            health = component.get("repository_health")
            if not isinstance(health, Mapping) or health.get("status") not in {
                "archived",
                "abandoned",
            }:
                continue
            details.append(
                {
                    "component": str(
                        component.get("title") or component.get("repository") or ""
                    ),
                    "repository": str(component.get("repository") or ""),
                    **dict(health),
                    "status_label": localize(
                        self.messages,
                        f"repository_status_{health['status']}",
                    ),
                }
            )
        details.sort(
            key=lambda item: (
                item["status"] != "archived",
                -(item.get("days_since_push") or 0),
            )
        )
        return details

    def _with_localized_repository_health(
        self, item: Mapping[str, Any]
    ) -> dict[str, Any]:
        """Render a stored repository-health label in the current HA language."""
        localized = dict(item)
        status = str(item.get("status") or "")
        if status in {"archived", "abandoned"}:
            localized["status_label"] = localize(
                self.messages, f"repository_status_{status}"
            )
        return localized

    async def _notify(self, mode: str) -> bool:
        if not self.notify_service:
            _LOGGER.debug("Notification service is not configured; skipping digest")
            return False

        stored_changes = (
            self.data.get("pending_changes", [])
            if mode == "digest"
            else self.data.get("last_run_changes", [])
        )
        changes = [self._with_localized_reason(item) for item in stored_changes]
        finding_changes = self.data.get("finding_changes", {})
        activated_findings = [
            self._with_localized_finding(item)
            for item in finding_changes.get("activated", [])[:5]
        ]
        activated_update_repositories = {
            str(item.get("repository") or "").casefold()
            for item in activated_findings
            if item.get("kind") == "update"
        }
        review_changes = [
            item
            for item in changes
            if str(item.get("repository") or "").casefold()
            not in activated_update_repositories
        ]
        counts = {key: 0 for key in SEVERITY_ORDER}
        for change in changes:
            severity = change.get("severity", "minor")
            counts[severity] = counts.get(severity, 0) + 1
        lines = [
            localize(self.messages, "notification_heading"),
            "",
            localize(
                self.messages,
                "notification_checked",
                checked=self.data.get("checked_this_run", 0),
                targeted=self.data.get("targeted_this_run", 0),
                total=self.data.get("total_components", 0),
            ),
            localize(
                self.messages, "notification_critical", count=counts.get("critical", 0)
            ),
            localize(
                self.messages,
                "notification_important",
                count=counts.get("important", 0),
            ),
            localize(
                self.messages, "notification_feature", count=counts.get("feature", 0)
            ),
            localize(self.messages, "notification_minor", count=counts.get("minor", 0)),
            localize(
                self.messages,
                "notification_updates_available",
                count=self.data.get("updates_available", 0),
            ),
            localize(
                self.messages,
                "notification_stale",
                count=self.data.get("stale_components", 0),
            ),
            localize(
                self.messages,
                "notification_archived",
                count=self.data.get("repository_health_counts", {}).get("archived", 0),
            ),
            localize(
                self.messages,
                "notification_abandoned",
                count=self.data.get("repository_health_counts", {}).get("abandoned", 0),
            ),
        ]
        if self.data.get("partial_audit"):
            lines.extend(
                [
                    "",
                    localize(self.messages, "notification_partial"),
                ]
            )
            for error in self.data.get("error_details", [])[:3]:
                lines.append(f"• {error['component']}: {error['message']}")
        if activated_findings:
            lines.extend(["", localize(self.messages, "notification_new_findings")])
            for finding in activated_findings:
                marker = "🔴" if finding.get("severity") == "critical" else "🟠"
                lines.append(
                    f"{marker} {finding['component']}: "
                    f"{finding.get('finding_type_label', finding['finding_type'])}"
                )
                if finding.get("recommendation"):
                    lines.append(f"• {finding['recommendation']}")
        if review_changes:
            lines.extend(["", localize(self.messages, "notification_review")])
            for change in review_changes[:5]:
                marker = {
                    "critical": "🔴",
                    "important": "🟠",
                    "feature": "🔵",
                    "minor": "⚪",
                    "unknown": "❔",
                }.get(change["severity"], "❔")
                lines.append(f"{marker} {change['component']} → {change['version']}")
                if change.get("reason"):
                    lines.append(f"• {change['reason']}")
                if change["summary"]:
                    lines.append(f"• {change['summary']}")
        elif mode == "digest" and not changes:
            lines.extend(["", localize(self.messages, "notification_no_new_releases")])

        domain, separator, service = self.notify_service.partition(".")
        if not separator or not self.hass.services.has_service(domain, service):
            _LOGGER.error("Notification service %s is unavailable", self.notify_service)
            return False
        await self.hass.services.async_call(
            domain,
            service,
            {
                "title": localize(self.messages, "notification_title"),
                "message": "\n".join(lines)[:3900],
                "data": {"tag": "custom_components_audit"},
            },
            blocking=True,
        )
        return True

    @property
    def attention_required(self) -> bool:
        """Return whether persistent actionable findings need attention."""
        return int(self.data.get("active_finding_count", 0)) > 0

    @property
    def audit_problem(self) -> bool:
        """Return whether the latest audit itself failed or was incomplete."""
        return self.data.get("status") in {"partial", "error"}

    def finding_attributes(self) -> dict[str, Any]:
        """Return bounded localized attributes for finding entities."""
        changes = self.data.get("finding_changes", {})
        return {
            "active_findings": [
                self._with_localized_finding(item)
                for item in self.data.get("active_findings", [])[:20]
            ],
            "finding_counts": self.data.get("finding_counts", {}),
            "findings_pending_confirmation": self.data.get(
                "findings_pending_confirmation", 0
            ),
            "pending_findings": [
                self._with_localized_finding(item)
                for item in self.data.get("pending_findings", [])[:10]
            ],
            "recently_resolved_findings": [
                self._with_localized_finding(item)
                for item in self.data.get("recently_resolved_findings", [])[:10]
            ],
            "finding_changes": {
                "activated": [
                    self._with_localized_finding(item)
                    for item in changes.get("activated", [])[:5]
                ],
                "resolved": [
                    self._with_localized_finding(item)
                    for item in changes.get("resolved", [])[:5]
                ],
            },
        }

    def _with_localized_finding(self, item: Mapping[str, Any]) -> dict[str, Any]:
        """Render a stored finding type and recommendation in HA language."""
        localized = dict(item)
        finding_type = str(item.get("finding_type") or "")
        recommendation_key = str(item.get("recommendation_key") or "")
        if finding_type:
            localized["finding_type_label"] = localize(
                self.messages, f"finding_type_{finding_type}"
            )
        if recommendation_key:
            localized["recommendation"] = localize(self.messages, recommendation_key)
        for internal_key in ("id", "fingerprint", "recommendation_key"):
            localized.pop(internal_key, None)
        return localized

    def state_attributes(self) -> dict[str, Any]:
        """Return bounded attributes for the public audit sensor."""
        counts = self.data.get("counts", {})
        return {
            "status": self.data.get("status", "idle"),
            "last_checked": self.data.get("last_checked"),
            "last_attempt": self.data.get("last_attempt"),
            "last_successful_audit": self.data.get("last_successful_audit"),
            "last_weekly_digest": self.data.get("last_weekly_digest"),
            "audit_mode": self.data.get("audit_mode"),
            "total_components": self.data.get("total_components", 0),
            "targeted_this_run": self.data.get("targeted_this_run", 0),
            "attempted_this_run": self.data.get("attempted_this_run", 0),
            "checked_this_run": self.data.get("checked_this_run", 0),
            "not_attempted_this_run": self.data.get("not_attempted_this_run", 0),
            "deferred_components": self.data.get("deferred_components", 0),
            "partial_audit": self.data.get("partial_audit", False),
            "cycle_complete": self.data.get("cycle_complete", False),
            "new_release_count": self.data.get("new_release_count", 0),
            "critical": counts.get("critical", 0),
            "important": counts.get("important", 0),
            "new_features": counts.get("feature", 0),
            "minor": counts.get("minor", 0),
            "updates_available": self.data.get("updates_available", 0),
            "available_updates": [
                self._with_localized_reason(item)
                for item in self.data.get("available_updates", [])[:10]
            ],
            "available_update_counts": self.data.get("available_update_counts", {}),
            "attention_required": self.attention_required,
            "audit_problem": self.audit_problem,
            "active_finding_count": self.data.get("active_finding_count", 0),
            "finding_counts": self.data.get("finding_counts", {}),
            "findings_pending_confirmation": self.data.get(
                "findings_pending_confirmation", 0
            ),
            "up_to_date_components": self.data.get("up_to_date_components", 0),
            "stale_components": self.data.get("stale_components", 0),
            "stale_component_details": self.data.get("stale_component_details", [])[:8],
            "repository_health_counts": self.data.get("repository_health_counts", {}),
            "repository_health_details": [
                self._with_localized_repository_health(item)
                for item in self.data.get("repository_health_details", [])[:10]
            ],
            "skipped_components": self.data.get("skipped_components", 0),
            "excluded_components": self.data.get("excluded_components", 0),
            "excluded_repositories": self.data.get("excluded_repositories", [])[:20],
            "last_run_changes": [
                self._with_localized_reason(item)
                for item in self.data.get("last_run_changes", [])[:8]
            ],
            "latest_changes": [
                self._with_localized_reason(item)
                for item in self.data.get("latest_changes", [])[:8]
            ],
            "pending_digest_changes": len(self.data.get("pending_changes", [])),
            "errors": self.data.get("errors", []),
            "error_details": self.data.get("error_details", [])[:5],
            "error_counts": self.data.get("error_counts", {}),
            "github_authenticated": self.data.get(
                "github_authenticated", bool(self.token)
            ),
            "github_token_configured": self.data.get(
                "github_token_configured", bool(self.token)
            ),
            "github_rate_remaining": self.data.get("github_rate_remaining"),
            "last_error": self.data.get("last_error", ""),
        }

    @callback
    def _publish(self) -> None:
        """Notify native Home Assistant entities about updated manager data."""
        for listener in tuple(self._listeners):
            listener()


class RateLimitReached(Exception):
    """Raised when GitHub asks the auditor to stop making requests."""

    category = "rate_limit"


class GitHubRequestError(Exception):
    """Raised for a classified GitHub request failure."""

    def __init__(self, category: str, message: str) -> None:
        super().__init__(message)
        self.category = category
