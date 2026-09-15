"""Tests for deterministic release-note processing."""

from __future__ import annotations

import importlib.util
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

MODULE_PATH = (
    Path(__file__).parents[1]
    / "custom_components"
    / "custom_components_auditor"
    / "release.py"
)
SPEC = importlib.util.spec_from_file_location("auditor_release", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release)

MESSAGES = json.loads(
    (
        Path(__file__).parents[1]
        / "custom_components"
        / "custom_components_auditor"
        / "translations"
        / "en.json"
    ).read_text(encoding="utf-8")
)["common"]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("BREAKING CHANGE: migrate the configuration", "critical"),
        ("Security fix for API authentication", "important"),
        ("New feature: added support for a sensor", "feature"),
        ("New option for map centering", "feature"),
        (
            "Add support for a new device; fix concentration unit deprecation warnings",
            "feature",
        ),
        ("Fix concentration unit deprecation warnings", "minor"),
        ("Resolve API deprecation warning", "minor"),
        ("Deprecated option will be removed in the next release", "important"),
        ("Maintenance release with dependency updates", "minor"),
    ],
)
def test_classification(text: str, expected: str) -> None:
    assert release.classify_release(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "No breaking changes in this release",
        "This is not a breaking change",
        "A non-breaking change",
        "Released without breaking changes",
    ],
)
def test_breaking_change_negations_are_not_critical(text: str) -> None:
    assert release.classify_release(text) != "critical"


def test_classification_exposes_matched_term_and_reason() -> None:
    severity, matched = release.classify_release_details("Migration required")

    assert severity == "critical"
    assert matched == "migration required"
    assert matched in release.classification_reason(severity, matched, MESSAGES)


def test_classification_reason_uses_translated_template() -> None:
    messages = {
        "assessment_important": "Translated assessment: {matched_term}",
    }

    assert release.classification_reason("important", "security", messages) == (
        "Translated assessment: security"
    )


def test_summary_removes_markdown_html_and_changelog_link() -> None:
    body = """
    ## [Useful release title](https://example.test/release)
    <b>Second useful line</b>
    Full changelog: https://example.test/changelog
    """

    summary = release.summarize_release(body)

    assert "Useful release title" in summary
    assert "Second useful line" in summary
    assert "https://" not in summary
    assert "<b>" not in summary


def test_summary_is_bounded() -> None:
    assert len(release.summarize_release("x" * 400)) <= 281


@pytest.mark.parametrize(
    ("tag", "version"),
    [
        ("v1.2.3", "1.2.3"),
        ("1.2.3", "v1.2.3"),
        ("refs/tags/v2.0.0", "2.0.0"),
        ("release-2026.9.0", "2026.9.0"),
    ],
)
def test_release_version_matching_handles_common_prefixes(
    tag: str, version: str
) -> None:
    candidate = {"tag_name": tag}

    assert release.find_release_for_version([candidate], version) is candidate


def test_release_version_matching_handles_short_commit_sha() -> None:
    candidate = {
        "tag_name": "v1.3.0-beta.3",
        "target_commitish": "8b7ff1ad5c5f95c31d88cd22291c3f484f7ae70e",
    }

    assert release.find_release_for_version([candidate], "8b7ff1a") is candidate


def test_release_version_does_not_match_unrelated_commit_sha() -> None:
    candidate = {
        "tag_name": "v1.3.0-beta.3",
        "target_commitish": "8b7ff1ad5c5f95c31d88cd22291c3f484f7ae70e",
    }

    assert release.find_release_for_version([candidate], "abcdef0") is None


def test_available_update_is_assessed_on_the_first_audit() -> None:
    repository = {
        "repository": "owner/component",
        "title": "Useful component",
        "entity_id": "update.useful_component",
        "installed_version": "1.0.0",
        "latest_version": "1.1.0",
        "release_url": "https://github.com/owner/component/releases/latest",
    }
    releases = [
        {
            "tag_name": "v1.1.0",
            "name": "Version 1.1.0",
            "body": "Security fix for authentication handling",
            "html_url": "https://github.com/owner/component/releases/tag/v1.1.0",
            "published_at": "2026-09-14T10:00:00Z",
        }
    ]

    assessment = release.assess_available_update(repository, releases, MESSAGES)

    assert assessment["release_status"] == "found"
    assert assessment["release_status_label"] == MESSAGES["release_status_found"]
    assert assessment["severity"] == "important"
    assert assessment["matched_term"] == "security"
    assert assessment["latest_version"] == "1.1.0"
    assert assessment["classification_version"] == release.CLASSIFICATION_VERSION
    assert assessment["summary"] == "Security fix for authentication handling"
    assert assessment["reason"] == "Read before updating, found: security."


def test_cached_assessment_refreshes_after_classification_rules_change() -> None:
    current = {
        "latest_version": "2.0.0",
        "classification_version": release.CLASSIFICATION_VERSION,
    }

    assert release.assessment_needs_refresh(None, "2.0.0") is True
    assert release.assessment_needs_refresh(current, "2.0.0") is False
    assert release.assessment_needs_refresh(current, "2.1.0") is True
    assert (
        release.assessment_needs_refresh(
            {**current, "classification_version": release.CLASSIFICATION_VERSION - 1},
            "2.0.0",
        )
        is True
    )


def test_available_update_reports_missing_matching_release() -> None:
    repository = {
        "repository": "owner/component",
        "title": "Useful component",
        "entity_id": "update.useful_component",
        "installed_version": "1.0.0",
        "latest_version": "2.0.0",
        "release_url": "https://github.com/owner/component/releases/latest",
    }

    assessment = release.assess_available_update(
        repository, [{"tag_name": "v1.0.0"}], MESSAGES
    )

    assert assessment["release_status"] == "not_found"
    assert assessment["release_status_label"] == (MESSAGES["release_status_not_found"])
    assert assessment["severity"] == "unknown"
    assert assessment["reason"] == MESSAGES["release_not_found"]
    assert assessment["summary"] == ""


def test_tags_are_used_as_release_candidates() -> None:
    candidates = release.tags_as_release_candidates(
        "owner/component",
        [{"name": "v2.0.0+build", "commit": {"sha": "abc123"}}],
    )

    assert candidates[0]["id"] == "tag:v2.0.0+build:abc123"
    assert candidates[0]["source"] == "tag"
    assert candidates[0]["target_commitish"] == "abc123"
    assert candidates[0]["html_url"].endswith("/tree/v2.0.0%2Bbuild")


def test_tag_fallback_matches_hacs_commit_sha() -> None:
    candidates = release.tags_as_release_candidates(
        "owner/component",
        [{"name": "v2.0.0", "commit": {"sha": "abcdef0123456789"}}],
    )

    assert release.find_release_for_version(candidates, "abcdef0") is candidates[0]


def test_available_update_reports_tag_fallback_without_fake_release_notes() -> None:
    repository = {
        "repository": "owner/component",
        "title": "Useful component",
        "installed_version": "1.0.0",
        "latest_version": "2.0.0",
    }
    tags = release.tags_as_release_candidates(
        "owner/component", [{"name": "v2.0.0", "commit": {"sha": "abc123"}}]
    )

    assessment = release.assess_available_update(repository, tags, MESSAGES)

    assert assessment["release_status"] == "found"
    assert assessment["release_source"] == "tag"
    assert assessment["severity"] == "unknown"
    assert assessment["summary"] == ""
    assert assessment["reason"] == MESSAGES["tag_fallback_reason"]


def test_repository_health_prioritizes_archived_status() -> None:
    health = release.assess_repository_health(
        {"archived": True, "pushed_at": "2026-09-01T00:00:00Z"},
        datetime(2026, 9, 14, tzinfo=UTC),
        730,
    )

    assert health["status"] == "archived"
    assert health["archived"] is True


def test_repository_health_detects_two_year_inactivity() -> None:
    health = release.assess_repository_health(
        {"archived": False, "pushed_at": "2024-01-01T00:00:00Z"},
        datetime(2026, 9, 14, tzinfo=UTC),
        730,
    )

    assert health["status"] == "abandoned"
    assert health["days_since_push"] > 730


def test_repository_health_keeps_recent_repository_active() -> None:
    health = release.assess_repository_health(
        {"archived": False, "pushed_at": "2026-09-01T00:00:00Z"},
        datetime(2026, 9, 14, tzinfo=UTC),
        730,
    )

    assert health["status"] == "active"
    assert health["days_since_push"] == 13


def test_broken_translation_template_fails_to_a_machine_key() -> None:
    assert release.localize({"message": "{missing}"}, "message") == "message"


def test_merge_changes_preserves_order_and_deduplicates_url() -> None:
    result = release.merge_changes(
        [{"url": "new", "version": "2"}],
        [
            {"url": "new", "version": "2"},
            {"url": "old", "version": "1"},
        ],
        10,
    )

    assert [item["url"] for item in result] == ["new", "old"]


def test_merge_changes_uses_repository_and_version_fallback() -> None:
    result = release.merge_changes(
        [{"repository": "owner/repo", "version": "2"}],
        [
            {"repository": "owner/repo", "version": "2"},
            {"repository": "owner/repo", "version": "1"},
        ],
        10,
    )

    assert [item["version"] for item in result] == ["2", "1"]


def test_merge_changes_honours_limit() -> None:
    items = [{"url": str(index)} for index in range(10)]

    assert len(release.merge_changes(items, [], 3)) == 3
