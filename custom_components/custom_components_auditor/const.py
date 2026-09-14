"""Constants for Custom Components Auditor."""

DOMAIN = "custom_components_auditor"
SERVICE_RUN_AUDIT = "run_audit"
SENSOR_ENTITY_ID = "sensor.custom_components_auditor"

CONF_GITHUB_TOKEN = "github_token"
CONF_NOTIFY_SERVICE = "notify_service"
CONF_DAILY_HOUR = "daily_hour"
CONF_WEEKLY_WEEKDAY = "weekly_weekday"
CONF_MAX_REQUESTS = "max_requests_per_run"
CONF_CLEAR_GITHUB_TOKEN = "clear_github_token"

DEFAULT_NOTIFY_SERVICE = ""
DEFAULT_DAILY_HOUR = 9
DEFAULT_WEEKLY_WEEKDAY = 6
DEFAULT_MAX_REQUESTS = 45

WEEKDAY_OPTIONS = ("0", "1", "2", "3", "4", "5", "6")

STORE_VERSION = 1
STORE_KEY = DOMAIN

SEVERITY_ORDER = {
    "minor": 0,
    "feature": 1,
    "important": 2,
    "critical": 3,
}
