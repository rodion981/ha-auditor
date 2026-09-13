"""Pure release-note helpers used by the HACS release auditor."""

from __future__ import annotations

import re
from typing import Any

MARKDOWN_LINK_RE = re.compile(r"\[([^]]+)]\([^)]+\)")
MARKDOWN_RE = re.compile(r"[`*_>#|~]+")
HTML_RE = re.compile(r"<[^>]+>")
SPACE_RE = re.compile(r"\s+")

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
    "new option",
    "configuration option",
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
    "added support",
    "new sensor",
    "new entity",
    "new card",
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


def classification_reason(severity: str, matched_term: str) -> str:
    """Explain a deterministic classification without overstating certainty."""
    if severity == "critical":
        return f"Можлива несумісність: у release notes є «{matched_term}»."
    if severity == "important":
        return f"Варто прочитати перед оновленням: знайдено «{matched_term}»."
    if severity == "feature":
        return f"Нова можливість: знайдено «{matched_term}»."
    return "Звичайний реліз без ключових сигналів ризику."


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
