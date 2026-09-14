"""Tests for config-entry setting normalization."""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import pytest

INTEGRATION = (
    Path(__file__).parents[1]
    / "custom_components"
    / "custom_components_auditor"
)
PACKAGE_NAME = "auditor_config_test"
package = types.ModuleType(PACKAGE_NAME)
package.__path__ = [str(INTEGRATION)]
sys.modules[PACKAGE_NAME] = package


def _load_module(name: str, path: Path) -> types.ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


const = _load_module(f"{PACKAGE_NAME}.const", INTEGRATION / "const.py")
config = _load_module(f"{PACKAGE_NAME}.config", INTEGRATION / "config.py")

normalize_settings = config.normalize_settings
CONF_DAILY_HOUR = const.CONF_DAILY_HOUR
CONF_GITHUB_TOKEN = const.CONF_GITHUB_TOKEN
CONF_MAX_REQUESTS = const.CONF_MAX_REQUESTS
CONF_NOTIFY_SERVICE = const.CONF_NOTIFY_SERVICE
CONF_WEEKLY_WEEKDAY = const.CONF_WEEKLY_WEEKDAY


def test_normalize_settings_supplies_ui_defaults() -> None:
    settings = normalize_settings()

    assert settings == {
        CONF_GITHUB_TOKEN: "",
        CONF_NOTIFY_SERVICE: "",
        CONF_DAILY_HOUR: 9,
        CONF_WEEKLY_WEEKDAY: 6,
        CONF_MAX_REQUESTS: 45,
    }


def test_options_override_entry_data_and_values_are_normalized() -> None:
    settings = normalize_settings(
        {
            CONF_GITHUB_TOKEN: " old ",
            CONF_DAILY_HOUR: 9,
            CONF_WEEKLY_WEEKDAY: 6,
        },
        {
            CONF_GITHUB_TOKEN: " new ",
            CONF_NOTIFY_SERVICE: " notify.mobile_app_phone ",
            CONF_DAILY_HOUR: 7.0,
            CONF_WEEKLY_WEEKDAY: "1",
            CONF_MAX_REQUESTS: 80.0,
        },
    )

    assert settings[CONF_GITHUB_TOKEN] == "new"
    assert settings[CONF_NOTIFY_SERVICE] == "notify.mobile_app_phone"
    assert settings[CONF_DAILY_HOUR] == 7
    assert settings[CONF_WEEKLY_WEEKDAY] == 1
    assert settings[CONF_MAX_REQUESTS] == 80


@pytest.mark.parametrize(
    ("key", "value"),
    [
        (CONF_DAILY_HOUR, -1),
        (CONF_DAILY_HOUR, 24),
        (CONF_WEEKLY_WEEKDAY, -1),
        (CONF_WEEKLY_WEEKDAY, 7),
        (CONF_MAX_REQUESTS, 0),
        (CONF_MAX_REQUESTS, 501),
    ],
)
def test_normalize_settings_rejects_out_of_range_values(
    key: str, value: int
) -> None:
    with pytest.raises(ValueError):
        normalize_settings({key: value})
