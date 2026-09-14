"""Repository-level publication safety tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).parents[1]
INTEGRATION = ROOT / "custom_components" / "custom_components_auditor"


class HomeAssistantYamlLoader(yaml.SafeLoader):
    """Minimal loader that accepts Home Assistant scalar tags in examples."""


HomeAssistantYamlLoader.add_constructor(
    "!secret", lambda loader, node: loader.construct_scalar(node)
)


def test_manifest_is_valid_for_custom_integration() -> None:
    manifest = json.loads((INTEGRATION / "manifest.json").read_text(encoding="utf-8"))

    assert manifest["domain"] == "custom_components_auditor"
    assert manifest["name"] == "HA Auditor"
    assert manifest["version"] == "1.1.0"
    assert manifest["integration_type"] == "service"
    assert manifest["iot_class"] == "cloud_polling"
    assert manifest["config_flow"] is True
    assert manifest["codeowners"] == ["@rodion981"]
    assert manifest["documentation"] == "https://github.com/rodion981/ha-auditor"
    assert manifest["issue_tracker"] == (
        "https://github.com/rodion981/ha-auditor/issues"
    )


def test_hacs_manifest_has_name() -> None:
    hacs = json.loads((ROOT / "hacs.json").read_text(encoding="utf-8"))

    assert hacs["name"] == "HA Auditor"


def test_bilingual_readme_links_are_present() -> None:
    english = (ROOT / "README.md").read_text(encoding="utf-8")
    ukrainian = (ROOT / "README.uk.md").read_text(encoding="utf-8")

    assert "README.uk.md" in english
    assert "README.md" in ukrainian
    assert "## Installation" in english
    assert "## Встановлення" in ukrainian
    assert "Devices & services" in english
    assert "Пристрої та служби" in ukrainian
    assert "YAML-configured" not in english
    assert "YAML-інтеграція" not in ukrainian


def test_config_flow_has_bilingual_translations() -> None:
    strings = json.loads((INTEGRATION / "strings.json").read_text(encoding="utf-8"))
    english = json.loads(
        (INTEGRATION / "translations" / "en.json").read_text(encoding="utf-8")
    )
    ukrainian = json.loads(
        (INTEGRATION / "translations" / "uk.json").read_text(encoding="utf-8")
    )

    for translation in (strings, english, ukrainian):
        assert set(translation) == {
            "title",
            "config",
            "options",
            "services",
            "selector",
        }
        assert "user" in translation["config"]["step"]
        assert "init" in translation["options"]["step"]
        assert set(translation["services"]["run_audit"]["fields"]) == {
            "mode",
            "notify",
        }
        assert set(translation["selector"]["audit_mode"]["options"]) == {
            "daily",
            "full",
            "digest",
        }
        assert set(translation["selector"]["weekday"]["options"]) == {
            "0",
            "1",
            "2",
            "3",
            "4",
            "5",
            "6",
        }

    assert strings == english


def test_mit_license_is_present() -> None:
    license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")

    assert "MIT License" in license_text
    assert "Copyright (c) 2026 rodion981" in license_text


def test_services_yaml_is_valid() -> None:
    services = yaml.safe_load(
        (INTEGRATION / "services.yaml").read_text(encoding="utf-8")
    )

    assert "run_audit" in services
    assert set(services["run_audit"]["fields"]) == {"mode", "notify"}
    assert (
        services["run_audit"]["fields"]["mode"]["selector"]["select"][
            "translation_key"
        ]
        == "audit_mode"
    )


def test_service_icon_is_present() -> None:
    icons = json.loads((INTEGRATION / "icons.json").read_text(encoding="utf-8"))

    assert icons["services"]["run_audit"]["service"] == "mdi:refresh"


@pytest.mark.parametrize(
    "relative_path",
    [
        ".github/workflows/validate.yml",
        "examples/configuration.yaml",
        "examples/dashboard.yaml",
    ],
)
def test_repository_yaml_is_valid(relative_path: str) -> None:
    content = (ROOT / relative_path).read_text(encoding="utf-8")

    assert yaml.load(content, Loader=HomeAssistantYamlLoader) is not None


def test_public_tree_does_not_contain_known_private_values_or_tokens() -> None:
    forbidden = (
        "github" + "_pat_",
        "gh" + "p_",
    )

    ignored_parts = {".git", ".pytest_cache", ".ruff_cache", "__pycache__"}
    text_suffixes = {".json", ".md", ".py", ".toml", ".txt", ".yaml", ".yml"}

    for path in ROOT.rglob("*"):
        if (
            path.is_file()
            and not ignored_parts.intersection(path.parts)
            and path.suffix in text_suffixes
        ):
            text = path.read_text(encoding="utf-8", errors="ignore")
            for marker in forbidden:
                assert marker not in text, f"Private marker {marker!r} in {path}"
