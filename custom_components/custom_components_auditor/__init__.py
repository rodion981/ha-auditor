"""Release auditor for HACS repositories."""

from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import Mapping
from datetime import datetime, timedelta
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_call_later, async_track_time_change
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .config import normalize_settings
from .const import (
    CONF_DAILY_HOUR,
    CONF_GITHUB_TOKEN,
    CONF_MAX_REQUESTS,
    CONF_NOTIFY_SERVICE,
    CONF_WEEKLY_WEEKDAY,
    DEFAULT_DAILY_HOUR,
    DEFAULT_MAX_REQUESTS,
    DEFAULT_NOTIFY_SERVICE,
    DEFAULT_WEEKLY_WEEKDAY,
    DOMAIN,
    SENSOR_ENTITY_ID,
    SERVICE_RUN_AUDIT,
    SEVERITY_ORDER,
    STORE_KEY,
    STORE_VERSION,
)
from .release import (
    _merge_changes,
    classification_reason,
    classify_release_details,
    summarize_release,
)

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Optional(DOMAIN): vol.Schema(
            {
                vol.Optional(CONF_GITHUB_TOKEN): cv.string,
                vol.Optional(
                    CONF_NOTIFY_SERVICE, default=DEFAULT_NOTIFY_SERVICE
                ): cv.string,
                vol.Optional(
                    CONF_DAILY_HOUR, default=DEFAULT_DAILY_HOUR
                ): vol.All(vol.Coerce(int), vol.Range(min=0, max=23)),
                vol.Optional(
                    CONF_WEEKLY_WEEKDAY, default=DEFAULT_WEEKLY_WEEKDAY
                ): vol.All(vol.Coerce(int), vol.Range(min=0, max=6)),
                vol.Optional(
                    CONF_MAX_REQUESTS, default=DEFAULT_MAX_REQUESTS
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=500)),
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
                "HA Auditor is not configured. Add it from Settings > "
                "Devices & services."
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
    manager = ComponentsAuditor(hass, settings)
    await manager.async_initialize()
    manager.async_start_schedules()

    managers: dict[str, ComponentsAuditor] = hass.data.setdefault(DOMAIN, {})
    managers[entry.entry_id] = manager
    manager.add_unsubscriber(entry.add_update_listener(_async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload HA Auditor and cancel all background callbacks."""
    managers: dict[str, ComponentsAuditor] = hass.data.get(DOMAIN, {})
    manager = managers.pop(entry.entry_id, None)
    if manager is not None:
        manager.async_shutdown()
    if not managers:
        hass.states.async_remove(SENSOR_ENTITY_ID)
    return True


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload HA Auditor after its UI options change."""
    await hass.config_entries.async_reload(entry.entry_id)


class ComponentsAuditor:
    """Discover HACS update entities and audit GitHub releases."""

    def __init__(self, hass: HomeAssistant, config: Mapping[str, Any]) -> None:
        self.hass = hass
        self.token = config.get(CONF_GITHUB_TOKEN, "").strip()
        self.notify_service = config[CONF_NOTIFY_SERVICE]
        self.daily_hour = config[CONF_DAILY_HOUR]
        self.weekly_weekday = config[CONF_WEEKLY_WEEKDAY]
        self.max_requests = config[CONF_MAX_REQUESTS]
        self.store: Store[dict[str, Any]] = Store(hass, STORE_VERSION, STORE_KEY)
        self.lock = asyncio.Lock()
        self.data: dict[str, Any] = {}
        self._unsubscribers: list[Any] = []

    async def async_initialize(self) -> None:
        """Restore the previous checkpoint and publish the sensor."""
        stored = await self.store.async_load()
        self.data = stored if isinstance(stored, dict) else {}
        self.data.setdefault("components", {})
        self.data.setdefault("latest_changes", [])
        self.data.setdefault("pending_changes", [])
        self.data.setdefault("cursor", 0)
        self.data.setdefault("status", "idle")
        self._publish()

    def add_unsubscriber(self, unsubscribe: Any) -> None:
        """Track a callback that must be removed when the entry unloads."""
        self._unsubscribers.append(unsubscribe)

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
                self.data["status"] = (
                    "partial" if result["partial_audit"] else "idle"
                )
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
                )
                if should_notify:
                    delivered = await self._notify(mode)
                    if (
                        mode == "digest"
                        and delivered
                        and not result["partial_audit"]
                    ):
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
        repositories, skipped = self._discover_repositories()
        component_state = self.data.setdefault("components", {})
        active_keys = {item["repository"].lower() for item in repositories}
        component_state = {
            key: value for key, value in component_state.items() if key in active_keys
        }
        total = len(repositories)
        request_limit = (
            max(self.max_requests, total) if self.token else self.max_requests
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

        for repository in selected:
            attempted += 1
            key = repository["repository"].lower()
            previous = component_state.get(key, {})
            try:
                releases, etag, rate_remaining = await self._fetch_releases(
                    repository["repository"], previous.get("etag")
                )
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
            }
            if etag:
                current["etag"] = etag

            if releases is not None:
                published = [item for item in releases if not item.get("draft")]
                last_id = previous.get("last_release_id")
                initialized = bool(previous.get("initialized"))
                unseen: list[dict[str, Any]] = []
                for release in published:
                    if release.get("id") == last_id:
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

            component_state[key] = current
            await asyncio.sleep(0.15)

        changes.sort(
            key=lambda item: (
                SEVERITY_ORDER[item["severity"]], item.get("published_at", "")
            ),
            reverse=True,
        )
        counts = {key: 0 for key in SEVERITY_ORDER}
        for change in changes:
            counts[change["severity"]] += 1

        latest_changes = _merge_changes(
            changes, self.data.get("latest_changes", []), 12
        )
        pending_changes = _merge_changes(
            changes, self.data.get("pending_changes", []), 100
        )
        stale_components = self._get_stale_components(component_state)
        updates_available = sum(1 for item in repositories if item["update_available"])
        available_updates = [
            {
                "component": item["title"],
                "entity_id": item["entity_id"],
                "installed_version": item["installed_version"],
                "latest_version": item["latest_version"],
                "url": item["release_url"],
            }
            for item in repositories
            if item["update_available"]
        ]
        error_counts: dict[str, int] = {}
        for error in error_details:
            category = error["category"]
            error_counts[category] = error_counts.get(category, 0) + 1
        not_attempted = max(len(selected) - attempted, 0)
        partial_audit = bool(error_details or not_attempted)

        return {
            "components": component_state,
            "audit_mode": mode,
            "total_components": total,
            "targeted_this_run": len(selected),
            "attempted_this_run": attempted,
            "checked_this_run": checked_successfully,
            "not_attempted_this_run": not_attempted,
            "partial_audit": partial_audit,
            "new_release_count": len(changes),
            "counts": counts,
            "last_run_changes": changes[:12],
            "latest_changes": latest_changes,
            "pending_changes": pending_changes,
            "updates_available": updates_available,
            "available_updates": available_updates,
            "up_to_date_components": max(total - updates_available, 0),
            "stale_components": len(stale_components),
            "stale_component_details": stale_components,
            "skipped_components": skipped,
            "errors": [item["message"] for item in error_details[:10]],
            "error_details": error_details[:10],
            "error_counts": error_counts,
            "cursor": next_cursor,
            "github_authenticated": bool(self.token),
            "github_rate_remaining": rate_remaining,
        }

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

    def _discover_repositories(self) -> tuple[list[dict[str, Any]], int]:
        registry = er.async_get(self.hass)
        found: dict[str, dict[str, Any]] = {}
        skipped = 0

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
            repository = f"{match.group(1)}/{match.group(2).removesuffix('.git')}"
            key = repository.lower()
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
        )

    async def _fetch_releases(
        self, repository: str, etag: str | None
    ) -> tuple[list[dict[str, Any]] | None, str | None, int | None]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2026-03-10",
            "User-Agent": "Home-Assistant-Custom-Components-Auditor/1.0",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        if etag:
            headers["If-None-Match"] = etag

        url = f"https://api.github.com/repos/{repository}/releases?per_page=10"
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
                            "GitHub відхилив token (401). Перевір або заміни token.",
                        )
                    if response.status == 429 or (
                        response.status == 403 and remaining == 0
                    ):
                        reset = response.headers.get(
                            "X-RateLimit-Reset", "невідомо"
                        )
                        raise RateLimitReached(
                            f"GitHub rate limit вичерпано; reset: {reset}"
                        )
                    if response.status == 403:
                        raise GitHubRequestError(
                            "authentication",
                            "GitHub заборонив доступ (403). Перевір права token.",
                        )
                    if response.status == 404:
                        raise GitHubRequestError(
                            "repository_not_found",
                            f"Repository {repository} не знайдено або він недоступний.",
                        )
                    if response.status >= 500:
                        raise GitHubRequestError(
                            "github",
                            f"GitHub тимчасово недоступний (HTTP {response.status}).",
                        )
                    response.raise_for_status()
                    payload = await response.json()
                    return payload, response.headers.get("ETag"), remaining
        except (GitHubRequestError, RateLimitReached):
            raise
        except TimeoutError as err:
            raise GitHubRequestError(
                "network", f"Timeout під час перевірки {repository}."
            ) from err
        except Exception as err:
            raise GitHubRequestError(
                "network",
                f"Помилка мережі або відповіді GitHub: {str(err)[:120]}",
            ) from err

    def _make_change(
        self, repository: Mapping[str, Any], release: Mapping[str, Any]
    ) -> dict[str, Any]:
        body = str(release.get("body") or "")
        title = str(release.get("name") or release.get("tag_name") or "Новий реліз")
        severity, matched_term = classify_release_details(f"{title}\n{body}")
        return {
            "repository": repository["repository"],
            "component": repository["title"],
            "installed_version": repository["installed_version"],
            "version": str(release.get("tag_name") or title),
            "severity": severity,
            "reason": classification_reason(severity, matched_term),
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
                            component.get("title") or "Невідомий компонент"
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

    async def _notify(self, mode: str) -> bool:
        if not self.notify_service:
            _LOGGER.debug("Notification service is not configured; skipping digest")
            return False

        changes = (
            self.data.get("pending_changes", [])
            if mode == "digest"
            else self.data.get("last_run_changes", [])
        )
        counts = {key: 0 for key in SEVERITY_ORDER}
        for change in changes:
            severity = change.get("severity", "minor")
            counts[severity] = counts.get(severity, 0) + 1
        lines = [
            "🧩 Аудит кастомних компонентів",
            "",
            f"Перевірено: {self.data.get('checked_this_run', 0)} "
            f"із {self.data.get('targeted_this_run', 0)} запланованих "
            f"({self.data.get('total_components', 0)} загалом)",
            f"🔴 Критичні: {counts.get('critical', 0)}",
            f"🟠 Важливі: {counts.get('important', 0)}",
            f"🔵 Нові можливості: {counts.get('feature', 0)}",
            f"⚪ Незначні: {counts.get('minor', 0)}",
            f"⬆️ Доступно оновлень: {self.data.get('updates_available', 0)}",
            f"🕰️ Без релізів понад рік: {self.data.get('stale_components', 0)}",
        ]
        if self.data.get("partial_audit"):
            lines.extend(
                [
                    "",
                    "⚠️ Перевірку завершено частково. Результат не є повним.",
                ]
            )
            for error in self.data.get("error_details", [])[:3]:
                lines.append(f"• {error['component']}: {error['message']}")
        if changes:
            lines.extend(["", "Варто переглянути:"])
            for change in changes[:5]:
                marker = {
                    "critical": "🔴",
                    "important": "🟠",
                    "feature": "🔵",
                    "minor": "⚪",
                }[change["severity"]]
                lines.append(
                    f"{marker} {change['component']} → {change['version']}"
                )
                if change.get("reason"):
                    lines.append(f"• {change['reason']}")
                if change["summary"]:
                    lines.append(f"• {change['summary']}")
        elif mode == "digest":
            lines.extend(["", "Нових релізів від попередньої перевірки немає."])

        domain, separator, service = self.notify_service.partition(".")
        if not separator or not self.hass.services.has_service(domain, service):
            _LOGGER.error("Notification service %s is unavailable", self.notify_service)
            return False
        await self.hass.services.async_call(
            domain,
            service,
            {
                "title": "Custom Components Audit",
                "message": "\n".join(lines)[:3900],
                "data": {"tag": "custom_components_audit"},
            },
            blocking=True,
        )
        return True

    def _publish(self) -> None:
        counts = self.data.get("counts", {})
        attributes = {
            "friendly_name": "Аудит кастомних компонентів",
            "icon": "mdi:puzzle-check-outline",
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
            "partial_audit": self.data.get("partial_audit", False),
            "new_release_count": self.data.get("new_release_count", 0),
            "critical": counts.get("critical", 0),
            "important": counts.get("important", 0),
            "new_features": counts.get("feature", 0),
            "minor": counts.get("minor", 0),
            "updates_available": self.data.get("updates_available", 0),
            "available_updates": self.data.get("available_updates", [])[:10],
            "up_to_date_components": self.data.get("up_to_date_components", 0),
            "stale_components": self.data.get("stale_components", 0),
            "stale_component_details": self.data.get(
                "stale_component_details", []
            )[:8],
            "skipped_components": self.data.get("skipped_components", 0),
            "last_run_changes": self.data.get("last_run_changes", [])[:8],
            "latest_changes": self.data.get("latest_changes", [])[:8],
            "pending_digest_changes": len(self.data.get("pending_changes", [])),
            "errors": self.data.get("errors", []),
            "error_details": self.data.get("error_details", [])[:5],
            "error_counts": self.data.get("error_counts", {}),
            "github_authenticated": self.data.get(
                "github_authenticated", bool(self.token)
            ),
            "github_rate_remaining": self.data.get("github_rate_remaining"),
            "last_error": self.data.get("last_error", ""),
        }
        self.hass.states.async_set(
            SENSOR_ENTITY_ID,
            str(self.data.get("new_release_count", 0)),
            attributes,
        )


class RateLimitReached(Exception):
    """Raised when GitHub asks the auditor to stop making requests."""

    category = "rate_limit"


class GitHubRequestError(Exception):
    """Raised for a classified GitHub request failure."""

    def __init__(self, category: str, message: str) -> None:
        super().__init__(message)
        self.category = category
