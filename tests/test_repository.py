"""Repository-level publication safety tests."""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from string import Formatter

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
    assert manifest["version"] == "1.4.0"
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
    assert "migration" not in english.lower()
    assert "міграц" not in ukrainian.lower()
    assert "examples/configuration.yaml" not in english
    assert "examples/configuration.yaml" not in ukrainian


def test_config_flow_has_bilingual_translations() -> None:
    strings = json.loads((INTEGRATION / "strings.json").read_text(encoding="utf-8"))
    english = json.loads(
        (INTEGRATION / "translations" / "en.json").read_text(encoding="utf-8")
    )
    ukrainian = json.loads(
        (INTEGRATION / "translations" / "uk.json").read_text(encoding="utf-8")
    )
    constants = ast.parse((INTEGRATION / "const.py").read_text(encoding="utf-8"))
    message_keys = next(
        ast.literal_eval(node.value)
        for node in constants.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "MESSAGE_KEYS"
            for target in node.targets
        )
    )

    for translation in (strings, english, ukrainian):
        assert set(translation) == {
            "title",
            "config",
            "options",
            "services",
            "exceptions",
            "issues",
            "entity",
            "common",
            "selector",
        }
        assert "user" in translation["config"]["step"]
        assert "init" in translation["options"]["step"]
        assert "excluded_repositories" in translation["config"]["step"]["user"]["data"]
        assert "excluded_repositories" in translation["options"]["step"]["init"]["data"]
        assert set(translation["services"]["run_audit"]["fields"]) == {
            "mode",
            "notify",
        }
        assert set(translation["exceptions"]) == {"not_configured"}
        assert set(translation["issues"]) == {"github_token_invalid"}
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
        assert set(translation["entity"]) == {
            "sensor",
            "binary_sensor",
            "button",
        }
        assert set(translation["common"]) == set(strings["common"])

    assert set(strings["common"]) == set(message_keys)

    for key, english_message in english["common"].items():
        english_fields = {
            field_name
            for _literal, field_name, _format_spec, _conversion in Formatter().parse(
                english_message
            )
            if field_name
        }
        ukrainian_fields = {
            field_name
            for _literal, field_name, _format_spec, _conversion in Formatter().parse(
                ukrainian["common"][key]
            )
            if field_name
        }
        assert ukrainian_fields == english_fields

    assert strings == english


def test_translation_contribution_guide_is_present() -> None:
    guide = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")

    assert "translations/<language_code>.json" in guide
    assert "{matched_term}" in guide


def test_translation_placeholders_are_not_wrapped_in_quotes() -> None:
    """Mirror hassfest's placeholder quoting rule for local validation."""
    quoted_placeholder = re.compile(r"['‘’«»]\{[^}]+\}['‘’«»]")

    for path in (
        INTEGRATION / "strings.json",
        INTEGRATION / "translations" / "en.json",
        INTEGRATION / "translations" / "uk.json",
    ):
        assert quoted_placeholder.search(path.read_text(encoding="utf-8")) is None


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
        services["run_audit"]["fields"]["mode"]["selector"]["select"]["translation_key"]
        == "audit_mode"
    )


def test_service_icon_is_present() -> None:
    icons = json.loads((INTEGRATION / "icons.json").read_text(encoding="utf-8"))

    assert icons["services"]["run_audit"]["service"] == "mdi:refresh"


def test_native_entity_platforms_are_packaged() -> None:
    for platform in ("sensor", "binary_sensor", "button"):
        assert (INTEGRATION / f"{platform}.py").is_file()

    integration_source = (INTEGRATION / "__init__.py").read_text(encoding="utf-8")
    assert "async_forward_entry_setups(entry, PLATFORMS)" in integration_source
    assert "hass.states.async_set" not in integration_source
    assert "update_findings" in integration_source
    assert "AuditorActiveFindingsSensor" in (INTEGRATION / "sensor.py").read_text(
        encoding="utf-8"
    )
    assert "AuditorAuditProblemBinarySensor" in (
        INTEGRATION / "binary_sensor.py"
    ).read_text(encoding="utf-8")


def test_fixable_github_token_repair_is_packaged() -> None:
    repairs = (INTEGRATION / "repairs.py").read_text(encoding="utf-8")
    integration = (INTEGRATION / "__init__.py").read_text(encoding="utf-8")

    assert "GitHubTokenRepairFlow" in repairs
    assert "async_create_fix_flow" in repairs
    assert "is_fixable=True" in integration
    assert "is_persistent=True" in integration
    assert "async_remove_entry" in integration
    assert "CONF_CLEAR_GITHUB_TOKEN" in repairs
    assert "BooleanSelector" in repairs
    assert "repair_token_choice_submitted" in repairs
    assert '"github_token_configured"' in integration


def test_integration_brand_icon_is_packaged_locally() -> None:
    icon = INTEGRATION / "brand" / "icon.png"
    data = icon.read_bytes()

    assert not (ROOT / "brand" / "icon.png").exists()
    assert data.startswith(b"\x89PNG\r\n\x1a\n")
    assert int.from_bytes(data[16:20], "big") == int.from_bytes(data[20:24], "big")


@pytest.mark.parametrize(
    "relative_path",
    [
        ".github/workflows/validate.yml",
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
