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
CLASSIFICATION_VERSION = 4
COMMIT_SHA_RE = re.compile(r"^[0-9a-f]{7,40}$")
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


def classify_release(text: str) -> str:
    """Classify release notes using deterministic rules."""
    severity, _matched_term = classify_release_details(text)
    return severity


def classify_release_details(text: str) -> tuple[str, str]:
    """Classify release notes and return the term that caused the decision."""
    lowered = text.casefold()
    lowered = RESOLVED_DEPRECATION_WARNING_RE.sub("", lowered)
    for harmless_phrase in (
        "no breaking changes",
        "without breaking changes",
        "not a breaking change",
        "non-breaking change",
    ):
        lowered = lowered.replace(harmless_phrase, "")
    for severity, terms in (
        ("critical", CRITICAL_TERMS),
        ("important", IMPORTANT_TERMS),
        ("feature", FEATURE_TERMS),
    ):
        for term in terms:
            if term in lowered:
                return severity, term
    return "minor", ""


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


def assessment_needs_refresh(assessment: Any, latest_version: Any) -> bool:
    """Return whether a cached available-update assessment must be rebuilt."""
    return not isinstance(assessment, Mapping) or (
        assessment.get("latest_version") != str(latest_version or "")
        or assessment.get("classification_version") != CLASSIFICATION_VERSION
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
    release = find_release_for_version(releases, latest_version)
    if release is None:
        return {
            **base,
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
        reason = classification_reason(severity, matched_term, messages)
        summary = summarize_release(body)
        status_label = localize(messages, "release_status_found")
    return {
        **base,
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
