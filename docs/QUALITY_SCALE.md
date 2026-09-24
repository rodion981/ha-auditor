# Home Assistant Integration Quality Scale self-assessment

This is an engineering self-assessment for a HACS custom integration. It is
not an official Home Assistant Core quality tier claim.

Measured on 2026-09-24 with Home Assistant 2026.9.2 and Python 3.14:

- 119 tests passed in the complete Linux suite.
- Integration coverage is 78%.
- CI rejects a regression below 78%.
- The official Silver coverage rule requires more than 95%, so HA Auditor does
  not claim Silver compliance yet.

## Task-relevant rules

| Rule | Status | Evidence or remaining gap |
| --- | --- | --- |
| `runtime-data` | Meets | The manager is owned by typed `ConfigEntry.runtime_data`; platforms, actions and diagnostics use that owner. |
| `action-setup` | Meets | Integration actions are registered from `async_setup`. |
| `action-exceptions` | Meets | Missing or stale finding actions raise translated `ServiceValidationError`; negative runtime tests cover this behavior. |
| `config-entry-unloading` | Meets | Runtime listeners and timers are cleaned up after platform unload; runtime setup/unload is tested. |
| `entity-event-setup` | Meets | Entities subscribe in `async_added_to_hass` and register the returned unsubscribe callback. |
| `entity-unique-id` and `has-entity-name` | Meets | Every native entity has a config-entry-derived unique ID and translated entity name. |
| `entity-translations` | Meets | English and Ukrainian names include sensor, binary sensor, button, select and to-do platforms. |
| `exception-translations` | Meets | English and Ukrainian messages exist for missing configuration, missing findings and inactive findings. |
| `diagnostics` | Meets | Diagnostics expose aggregate runtime data and are tested not to contain tokens, notification targets or repository names. |
| `repair-issues` | Meets for token failures | Invalid or expired GitHub tokens create a fixable Repair; replacement, removal and invalid-token paths have runtime tests. |
| `docs-examples` | Meets | English and Ukrainian dashboards and critical-finding automations are validated as YAML. |
| `docs-known-limitations` | Meets | The README explicitly documents bounded GitHub lookup and unknown compatibility when evidence is absent. |
| `test-coverage` | Does not meet | 78%; the official rule is above 95%. Most remaining misses are network/error, notification, scheduling and recovery branches in `__init__.py`. |
| `config-flow-test-coverage` | Partial | Initial setup, duplicate prevention, options and token removal are tested; legacy import and every token-preservation branch still need coverage. |
| `log-when-unavailable` | Does not meet | Failures are logged, but a single transition log for unavailable and recovered states is not implemented. |
| `strict-typing` | Not verified | Ruff passes, but a strict type checker is not yet a CI gate. |

## Next coverage targets

1. GitHub HTTP status, ETag, timeout and rate-limit branches.
2. Partial audit behavior for authentication, network and unknown repository
   failures.
3. Scheduling, snooze expiry and notification delivery/recovery paths.
4. Remaining config-flow and Repair HTTP validation branches.
5. Raise the CI threshold only after the measured suite passes the new value.
