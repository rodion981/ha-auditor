"""Tests for deterministic release-note processing."""

from __future__ import annotations

import importlib.util
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


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("BREAKING CHANGE: migrate the configuration", "critical"),
        ("Security fix for API authentication", "important"),
        ("New feature: added support for a sensor", "feature"),
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
    assert matched in release.classification_reason(severity, matched)


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
