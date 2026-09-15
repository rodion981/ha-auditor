"""Constants for Custom Components Auditor."""

DOMAIN = "custom_components_auditor"
SERVICE_RUN_AUDIT = "run_audit"
SERVICE_ACKNOWLEDGE_FINDING = "acknowledge_finding"
SERVICE_SNOOZE_FINDING = "snooze_finding"
SERVICE_IGNORE_FINDING = "ignore_finding"
SERVICE_RESTORE_FINDING = "restore_finding"
SENSOR_ENTITY_ID = "sensor.custom_components_auditor"

CONF_GITHUB_TOKEN = "github_token"
CONF_NOTIFY_SERVICE = "notify_service"
CONF_DAILY_HOUR = "daily_hour"
CONF_WEEKLY_WEEKDAY = "weekly_weekday"
CONF_MAX_REQUESTS = "max_requests_per_run"
CONF_CLEAR_GITHUB_TOKEN = "clear_github_token"
CONF_EXCLUDED_REPOSITORIES = "excluded_repositories"

DEFAULT_NOTIFY_SERVICE = ""
DEFAULT_DAILY_HOUR = 9
DEFAULT_WEEKLY_WEEKDAY = 6
DEFAULT_MAX_REQUESTS = 45
DEFAULT_EXCLUDED_REPOSITORIES: tuple[str, ...] = ()

ABANDONED_REPOSITORY_DAYS = 730
TOKEN_REPAIR_ISSUE_ID = "github_token_invalid"

WEEKDAY_OPTIONS = ("0", "1", "2", "3", "4", "5", "6")

STORE_VERSION = 1
STORE_KEY = DOMAIN

SEVERITY_ORDER = {
    "minor": 0,
    "feature": 1,
    "important": 2,
    "critical": 3,
}

MESSAGE_KEYS = (
    "assessment_critical",
    "assessment_important",
    "assessment_feature",
    "assessment_minor",
    "release_not_found",
    "not_checked",
    "release_status_found",
    "release_status_not_found",
    "release_status_not_checked",
    "release_status_tag_found",
    "tag_fallback_reason",
    "repository_status_archived",
    "repository_status_abandoned",
    "finding_type_critical_update",
    "finding_type_important_update",
    "finding_type_repository_archived",
    "finding_type_repository_abandoned",
    "finding_recommendation_update",
    "finding_recommendation_archived",
    "finding_recommendation_abandoned",
    "finding_review_new",
    "finding_review_acknowledged",
    "finding_review_snoozed",
    "finding_review_ignored",
    "error_authentication_401",
    "error_rate_limit",
    "error_authentication_403",
    "error_repository_not_found",
    "error_github_status",
    "error_timeout",
    "error_network",
    "new_release",
    "unknown_component",
    "notification_title",
    "notification_heading",
    "notification_checked",
    "notification_critical",
    "notification_important",
    "notification_feature",
    "notification_minor",
    "notification_updates_available",
    "notification_stale",
    "notification_archived",
    "notification_abandoned",
    "notification_partial",
    "notification_new_findings",
    "notification_review",
    "notification_no_new_releases",
)
