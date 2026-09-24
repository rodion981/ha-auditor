"""Pure release-note helpers used by the HACS release auditor."""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

MARKDOWN_LINK_RE = re.compile(r"\[([^]]+)]\([^)]+\)")
MARKDOWN_RE = re.compile(r"[`*_>#|~]+")
HTML_RE = re.compile(r"<[^>]+>")
SPACE_RE = re.compile(r"\s+")
UPDATE_SUFFIX_RE = re.compile(r"\s+update\s*$", re.IGNORECASE)
CLASSIFICATION_VERSION = 5
COMMIT_SHA_RE = re.compile(r"^[0-9a-f]{7,40}$")
MINIMUM_HOME_ASSISTANT_PATTERNS = (
    re.compile(
        r"\b(?:minimum|required|requires?)\s+(?:supported\s+)?"
        r"(?:home assistant|ha)(?:\s+version)?\s*"
        r"(?:is|of|:|>=|\u2265)?\s*(\d{4}\.\d+(?:\.\d+)?)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:home assistant|ha)\s+(\d{4}\.\d+(?:\.\d+)?)\s*"
        r"(?:or newer|or later|\+|minimum|required)\b",
        re.IGNORECASE,
    ),
)
UPGRADE_PATH_DISPLAY_LIMIT = 30
UPGRADE_SIGNAL_KEYS = (
    "breaking_changes",
    "security_fixes",
    "deprecations",
    "new_features",
)
_SEVERITY_ORDER = {
    "unknown": -1,
    "minor": 0,
    "feature": 1,
    "important": 2,
    "critical": 3,
}
RESOLVED_DEPRECATION_WARNING_RE = re.compile(
    r"\b(?:fix(?:ed|es|ing)?|resolv(?:e|ed|es|ing)|silenc(?:e|ed|es|ing))\b"
    r"[^\n.;]{0,100}\bdeprecat(?:ed|ion)?\s+warnings?\b"
)

CRITICAL_TERMS = (
    "breaking change",
    "breaking:",
    "backward incompatible",
    "backwards incompatible",
    "removed support",
    "removed feature",
    "migration required",
    "configuration schema",
    "api change",
    "changed api",
    "removed functionality",
    "несуміс",
    "критич",
    "видалено підтримку",
)
IMPORTANT_TERMS = (
    "security",
    "data loss",
    "important",
    "new service",
    "behavior change",
    "behaviour change",
    "minimum home assistant",
    "deprecat",
    "важлив",
    "безпек",
    "нова служба",
)
FEATURE_TERMS = (
    "new feature",
    "add support",
    "adds support",
    "added support",
    "new sensor",
    "new entity",
    "new card",
    "new option",
    "configuration option",
    "introducing",
    "feature:",
    "feat:",
    "додано",
    "нова можливість",
    "підтримку",
)


def normalize_component_title(title: str) -> str:
    """Remove the generic HACS update-entity suffix from a component title."""
    normalized = title.strip()
    return UPDATE_SUFFIX_RE.sub("", normalized) or normalized


def classify_release(text: str) -> str:
    """Classify release notes using deterministic rules."""
    severity, _matched_term = classify_release_details(text)
    return severity


def classify_release_details(text: str) -> tuple[str, str]:
    """Classify release notes and return the term that caused the decision."""
    lowered = _normalized_classification_text(text)
    for severity, terms in (
        ("critical", CRITICAL_TERMS),
        ("important", IMPORTANT_TERMS),
        ("feature", FEATURE_TERMS),
    ):
        for term in terms:
            if term in lowered:
                return severity, term
    return "minor", ""


def _normalized_classification_text(text: str) -> str:
    """Normalize release notes before deterministic keyword inspection."""
    lowered = text.casefold()
    lowered = RESOLVED_DEPRECATION_WARNING_RE.sub("", lowered)
    for harmless_phrase in (
        "no breaking changes",
        "without breaking changes",
        "not a breaking change",
        "non-breaking change",
    ):
        lowered = lowered.replace(harmless_phrase, "")
    return lowered


def release_signals(text: str) -> list[str]:
    """Return evidence-backed signal categories present in release notes."""
    lowered = _normalized_classification_text(text)
    signals: list[str] = []
    if any(term in lowered for term in CRITICAL_TERMS):
        signals.append("breaking_changes")
    if any(
        term in lowered
        for term in (
            "security",
            "vulnerability",
            "cve-",
            "\u0431\u0435\u0437\u043f\u0435\u043a",
            "\u0432\u0440\u0430\u0437\u043b\u0438\u0432",
        )
    ):
        signals.append("security_fixes")
    if any(
        term in lowered
        for term in (
            "deprecat",
            "obsolete option",
            "\u0437\u0430\u0441\u0442\u0430\u0440",
        )
    ):
        signals.append("deprecations")
    if any(term in lowered for term in FEATURE_TERMS):
        signals.append("new_features")
    return signals


def extract_minimum_home_assistant_version(text: str) -> str:
    """Extract an explicitly stated minimum Home Assistant version."""
    versions = {
        match.group(1)
        for pattern in MINIMUM_HOME_ASSISTANT_PATTERNS
        for match in pattern.finditer(text)
    }
    if not versions:
        return ""
    return max(
        versions, key=lambda value: tuple(int(part) for part in value.split("."))
    )


def localize(messages: Mapping[str, str], key: str, **placeholders: Any) -> str:
    """Format a translated message while failing safely on a broken locale."""
    template = str(messages.get(key, key))
    try:
        return template.format(**placeholders)
    except (KeyError, ValueError):
        return key


def classification_reason(
    severity: str, matched_term: str, messages: Mapping[str, str]
) -> str:
    """Explain a deterministic classification without overstating certainty."""
    return localize(
        messages,
        f"assessment_{severity}",
        matched_term=matched_term,
    )


def summarize_release(body: str) -> str:
    """Return a compact, safe excerpt without pretending to translate it."""
    text = MARKDOWN_LINK_RE.sub(r"\1", body)
    text = HTML_RE.sub(" ", text)
    candidates: list[str] = []
    for raw_line in text.splitlines():
        line = MARKDOWN_RE.sub("", raw_line).strip(" -\t")
        line = SPACE_RE.sub(" ", line)
        if len(line) >= 12 and not line.lower().startswith("full changelog"):
            candidates.append(line)
        if len(candidates) == 2:
            break
    summary = "; ".join(candidates)
    return summary[:280].rstrip(" ;,.") + ("…" if len(summary) > 280 else "")


def normalize_release_version(value: Any) -> str:
    """Normalize common GitHub tag prefixes without guessing version semantics."""
    normalized = str(value or "").strip().casefold()
    if normalized.startswith("refs/tags/"):
        normalized = normalized.removeprefix("refs/tags/")
    if normalized.startswith("release-"):
        normalized = normalized.removeprefix("release-")
    if normalized.startswith("v") and len(normalized) > 1 and normalized[1].isdigit():
        normalized = normalized[1:]
    return normalized


def find_release_for_version(
    releases: list[dict[str, Any]], version: Any
) -> dict[str, Any] | None:
    """Find the GitHub release that matches a HACS latest version."""
    target = normalize_release_version(version)
    if not target:
        return None
    for release in releases:
        if normalize_release_version(release.get("tag_name")) == target:
            return release
    if COMMIT_SHA_RE.fullmatch(target):
        for release in releases:
            for field in ("target_commitish", "commit_sha"):
                commit = str(release.get(field) or "").strip().casefold()
                if COMMIT_SHA_RE.fullmatch(commit) and (
                    commit.startswith(target) or target.startswith(commit)
                ):
                    return release
    return None


def release_version_is_commit_sha(version: Any) -> bool:
    """Return whether a HACS version looks like a short or full commit SHA."""
    return COMMIT_SHA_RE.fullmatch(normalize_release_version(version)) is not None


def add_tag_commit_shas(
    releases: list[dict[str, Any]], tags: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Attach tag commit SHAs to matching GitHub Release records."""
    tag_commits: dict[str, str] = {}
    for tag in tags:
        name = normalize_release_version(tag.get("name"))
        commit = tag.get("commit") if isinstance(tag.get("commit"), Mapping) else {}
        sha = str(commit.get("sha") or "").strip()
        if name and sha:
            tag_commits[name] = sha

    enriched: list[dict[str, Any]] = []
    for release in releases:
        candidate = dict(release)
        sha = tag_commits.get(normalize_release_version(release.get("tag_name")))
        if sha:
            candidate["commit_sha"] = sha
        enriched.append(candidate)
    return enriched


def parse_rate_limit_reset(value: Any) -> datetime | None:
    """Parse GitHub's Unix reset timestamp without trusting malformed headers."""
    try:
        timestamp = int(str(value).strip())
        if timestamp <= 0:
            return None
        return datetime.fromtimestamp(timestamp, UTC)
    except (OSError, OverflowError, TypeError, ValueError):
        return None


def assessment_needs_refresh(
    assessment: Any, latest_version: Any, installed_version: Any | None = None
) -> bool:
    """Return whether a cached available-update assessment must be rebuilt."""
    return not isinstance(assessment, Mapping) or (
        assessment.get("latest_version") != str(latest_version or "")
        or assessment.get("classification_version") != CLASSIFICATION_VERSION
        or (
            installed_version is not None
            and assessment.get("installed_version") != str(installed_version or "")
        )
    )


def tags_as_release_candidates(
    repository: str, tags: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Convert GitHub tags into the release-shaped records used by the auditor."""
    candidates: list[dict[str, Any]] = []
    for tag in tags:
        name = str(tag.get("name") or "").strip()
        if not name:
            continue
        commit = tag.get("commit") if isinstance(tag.get("commit"), Mapping) else {}
        sha = str(commit.get("sha") or "")
        candidates.append(
            {
                "id": f"tag:{name}:{sha}",
                "tag_name": name,
                "name": name,
                "body": "",
                "draft": False,
                "prerelease": False,
                "source": "tag",
                "target_commitish": sha,
                "commit_sha": sha,
                "html_url": (
                    f"https://github.com/{repository}/tree/{quote(name, safe='')}"
                ),
                "published_at": "",
            }
        )
    return candidates


def assess_repository_health(
    metadata: Mapping[str, Any],
    now: datetime,
    abandoned_days: int,
) -> dict[str, Any]:
    """Classify repository maintenance health from GitHub metadata."""
    pushed_at = str(metadata.get("pushed_at") or "")
    days_since_push: int | None = None
    if pushed_at:
        try:
            parsed = datetime.fromisoformat(pushed_at.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            current = now if now.tzinfo is not None else now.replace(tzinfo=UTC)
            days_since_push = max((current - parsed).days, 0)
        except ValueError:
            days_since_push = None

    archived = bool(metadata.get("archived"))
    if archived:
        status = "archived"
    elif days_since_push is not None and days_since_push >= abandoned_days:
        status = "abandoned"
    elif days_since_push is not None:
        status = "active"
    else:
        status = "unknown"
    return {
        "status": status,
        "archived": archived,
        "pushed_at": pushed_at,
        "days_since_push": days_since_push,
        "url": str(metadata.get("html_url") or ""),
    }


def build_upgrade_path(
    releases: list[dict[str, Any]], installed_version: Any, latest_version: Any
) -> dict[str, Any]:
    """Build a bounded, evidence-backed release path between exact endpoints."""
    installed = str(installed_version or "")
    latest = str(latest_version or "")
    base: dict[str, Any] = {
        "upgrade_path_status": "unavailable",
        "upgrade_path_complete": False,
        "versions_behind": None,
        "intermediate_release_count": None,
        "version_path": [value for value in (installed, latest) if value],
        "upgrade_releases": [],
        "upgrade_path_truncated": False,
        "upgrade_signal_counts": {key: 0 for key in UPGRADE_SIGNAL_KEYS},
        "upgrade_severity": "unknown",
        "upgrade_matched_term": "",
        "minimum_home_assistant_version": "",
        "minimum_home_assistant_version_source": "",
        "compatibility_status": "unknown",
    }
    target_release = find_release_for_version(releases, latest)
    if target_release is None or target_release.get("source") == "tag":
        return base

    installed_release = find_release_for_version(releases, installed)
    if installed_release is None:
        return {**base, "upgrade_path_status": "partial"}

    target_index = releases.index(target_release)
    installed_index = releases.index(installed_release)
    if target_index >= installed_index:
        return base

    path = list(reversed(releases[target_index:installed_index]))
    details: list[dict[str, Any]] = []
    signal_counts = {key: 0 for key in UPGRADE_SIGNAL_KEYS}
    upgrade_severity = "minor"
    upgrade_matched_term = ""
    minimum_ha_version = ""
    minimum_ha_source = ""

    for release in path:
        version = str(release.get("tag_name") or "")
        title = str(release.get("name") or version)
        body = str(release.get("body") or "")
        text = f"{title}\n{body}"
        severity, matched_term = classify_release_details(text)
        signals = release_signals(text)
        for signal in signals:
            signal_counts[signal] += 1
        if _SEVERITY_ORDER[severity] > _SEVERITY_ORDER[upgrade_severity]:
            upgrade_severity = severity
            upgrade_matched_term = matched_term

        explicit_minimum = extract_minimum_home_assistant_version(text)
        if explicit_minimum and (
            not minimum_ha_version
            or tuple(int(part) for part in explicit_minimum.split("."))
            > tuple(int(part) for part in minimum_ha_version.split("."))
        ):
            minimum_ha_version = explicit_minimum
            minimum_ha_source = str(release.get("html_url") or "")

        details.append(
            {
                "version": version,
                "title": title,
                "severity": severity,
                "signals": signals,
                "summary": summarize_release(body),
                "url": str(release.get("html_url") or ""),
                "published_at": str(
                    release.get("published_at") or release.get("created_at") or ""
                ),
            }
        )

    display_details = details
    if len(details) > UPGRADE_PATH_DISPLAY_LIMIT:
        display_details = [
            *details[: UPGRADE_PATH_DISPLAY_LIMIT - 1],
            details[-1],
        ]
    compatibility_status = "requirement_found" if minimum_ha_version else "unknown"
    return {
        **base,
        "upgrade_path_status": "complete",
        "upgrade_path_complete": True,
        "versions_behind": len(path),
        "intermediate_release_count": max(len(path) - 1, 0),
        "version_path": [installed] + [item["version"] for item in display_details],
        "upgrade_releases": display_details,
        "upgrade_path_truncated": len(details) > len(display_details),
        "upgrade_signal_counts": signal_counts,
        "upgrade_severity": upgrade_severity,
        "upgrade_matched_term": upgrade_matched_term,
        "minimum_home_assistant_version": minimum_ha_version,
        "minimum_home_assistant_version_source": minimum_ha_source,
        "compatibility_status": compatibility_status,
    }


def assess_available_update(
    repository: dict[str, Any],
    releases: list[dict[str, Any]],
    messages: Mapping[str, str],
) -> dict[str, Any]:
    """Build an actionable assessment for the version currently offered by HACS."""
    latest_version = str(repository.get("latest_version") or "")
    base = {
        "repository": str(repository.get("repository") or ""),
        "component": str(repository.get("title") or repository.get("repository") or ""),
        "entity_id": str(repository.get("entity_id") or ""),
        "installed_version": str(repository.get("installed_version") or ""),
        "latest_version": latest_version,
        "classification_version": CLASSIFICATION_VERSION,
    }
    upgrade_path = build_upgrade_path(
        releases, base["installed_version"], base["latest_version"]
    )
    release = find_release_for_version(releases, latest_version)
    if release is None:
        return {
            **base,
            **upgrade_path,
            "release_status": "not_found",
            "release_status_label": localize(messages, "release_status_not_found"),
            "severity": "unknown",
            "reason": localize(messages, "release_not_found"),
            "matched_term": "",
            "summary": "",
            "url": str(repository.get("release_url") or ""),
            "published_at": "",
        }

    title = str(release.get("name") or release.get("tag_name") or latest_version)
    body = str(release.get("body") or "")
    release_source = str(release.get("source") or "release")
    if release_source == "tag":
        severity, matched_term = "unknown", ""
        reason = localize(messages, "tag_fallback_reason")
        summary = ""
        status_label = localize(messages, "release_status_tag_found")
    else:
        severity, matched_term = classify_release_details(f"{title}\n{body}")
        if upgrade_path["upgrade_path_complete"]:
            severity = str(upgrade_path["upgrade_severity"])
            matched_term = str(upgrade_path["upgrade_matched_term"])
        reason = classification_reason(severity, matched_term, messages)
        summary = summarize_release(body)
        status_label = localize(messages, "release_status_found")
    return {
        **base,
        **upgrade_path,
        "release_status": "found",
        "release_status_label": status_label,
        "release_source": release_source,
        "severity": severity,
        "reason": reason,
        "matched_term": matched_term,
        "summary": summary,
        "url": str(release.get("html_url") or repository.get("release_url") or ""),
        "published_at": str(
            release.get("published_at") or release.get("created_at") or ""
        ),
    }


def merge_changes(
    new: list[dict[str, Any]], existing: list[dict[str, Any]], limit: int
) -> list[dict[str, Any]]:
    """Merge release changes newest-first without duplicating a release URL."""
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in new + existing:
        identity = str(
            item.get("url") or f"{item.get('repository')}:{item.get('version')}"
        )
        if identity in seen:
            continue
        seen.add(identity)
        result.append(item)
        if len(result) >= limit:
            break
    return result


# Backwards-compatible private name used by the manager module.
_merge_changes = merge_changes
