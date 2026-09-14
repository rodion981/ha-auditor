# HA Auditor for Home Assistant

[![English](https://img.shields.io/badge/lang-English-blue)](README.md)
[![Українська](https://img.shields.io/badge/lang-Українська-yellow)](README.uk.md)
[![Validate](https://github.com/rodion981/ha-auditor/actions/workflows/validate.yml/badge.svg)](https://github.com/rodion981/ha-auditor/actions/workflows/validate.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

HA Auditor is a Home Assistant custom integration that checks GitHub Releases
for installed HACS integrations and highlights release notes that may deserve
attention before an update. It is configured from the Home Assistant UI; YAML
is not required.

It is designed to answer three practical questions:

1. Which HACS integrations have an update available?
2. Which newly discovered releases may include breaking changes, important
   fixes or new features?
3. Did the audit finish completely, or was it limited by GitHub or the network?

## What it does

- Discovers enabled `update.*` entities provided by HACS.
- Creates a silent baseline on the first run, avoiding a flood of old releases.
- Uses GitHub Releases and ETags to reduce unnecessary API traffic.
- Separates currently available HACS updates from newly discovered releases.
- Classifies release notes as critical, important, feature or minor using
  deterministic keywords and exposes the matched reason.
- Persists release checkpoints and a weekly digest queue in Home Assistant
  storage.
- Reports partial audits instead of presenting incomplete results as success.
- Optionally sends immediate critical or important notifications and a weekly
  digest.

It does not install updates, modify Home Assistant configuration or expose the
GitHub token in sensor attributes.

## Important limitation

Release classification is a keyword-based hint. It is not a security audit and
does not prove that an update is incompatible. Always read the linked release
notes before installing a release marked critical or important.

Repositories that publish only tags or commits, without GitHub Releases,
cannot currently produce release-note alerts.

## Installation

### HACS custom repository

1. Open HACS in Home Assistant.
2. Add `https://github.com/rodion981/ha-auditor` as a custom repository with
   category **Integration**.
3. Install **HA Auditor**.
4. Restart Home Assistant.
5. Open **Settings → Devices & services → Add integration**.
6. Search for **HA Auditor** and complete the setup form.

### Manual installation

Copy the directory:

```text
custom_components/custom_components_auditor
```

to the same path inside the Home Assistant configuration directory, then
restart Home Assistant.

## Configuration

All settings are available in the integration setup form. To change them later,
open **Settings → Devices & services → HA Auditor → Configure**.

- **GitHub token** is optional. A read-only token increases the API limit and
  lets `full` mode check every discovered repository in one run.
- **Notification action** is optional. Use an action such as
  `notify.mobile_app_your_phone`, or leave it empty to disable push
  notifications.
- **Daily audit hour** uses local Home Assistant time. The job starts at minute
  15 of the selected hour.
- **Weekly digest day** is selected by name in the UI.
- **Repositories per unauthenticated run** controls the batch size when no
  token is configured.

The saved token is not displayed in sensor attributes. In the options form,
leave the token field empty to keep it, enter a new value to replace it, or use
the removal switch to delete it.

### Upgrading from the YAML version

Existing `custom_components_auditor:` YAML is imported automatically into a UI
config entry once. After **HA Auditor** appears under Devices & services,
remove that YAML block and its unused secret, then restart Home Assistant.
The legacy example remains in
[`examples/configuration.yaml`](examples/configuration.yaml) only for migration.

## Running an audit

The integration registers this Home Assistant action:

```yaml
action: custom_components_auditor.run_audit
data:
  mode: full
  notify: false
```

Available modes:

- `daily`: check the next configured batch;
- `full`: check all repositories when authenticated, otherwise one batch;
- `digest`: check repositories and send the accumulated weekly digest.

The scheduled audit runs at minute 15 of the selected hour. On the selected
weekly digest day, it runs in digest mode.

## Understanding the result

The integration publishes `sensor.custom_components_auditor`.

- `status`: `idle`, `running`, `partial` or `error`;
- `last_attempt`: when the most recent audit was started;
- `last_successful_audit`: the latest fully successful audit;
- `total_components`: all discovered HACS integrations;
- `targeted_this_run`: repositories selected for this run;
- `checked_this_run`: repositories successfully checked;
- `updates_available` and `available_updates`: updates currently offered by
  HACS;
- `critical`, `important`, `new_features` and `minor`: newly detected releases
  grouped by classification;
- `last_run_changes`: new releases found during the latest run;
- `pending_digest_changes`: releases waiting for the weekly digest;
- `error_details`: failures grouped by type;
- `github_rate_remaining`: remaining GitHub API quota when available.

`partial` means that at least one targeted repository was not checked. Treat
the result as incomplete and use `error_details` to find the reason.

A native dashboard example is available in
[`examples/dashboard.yaml`](examples/dashboard.yaml).

## Development

```bash
python -m pip install -r requirements_test.txt
python -m compileall -q custom_components
ruff check custom_components tests
pytest
```

The unit suite covers release classification, negated breaking-change phrases,
summary sanitization, change deduplication, repository metadata and a small
publication secret scan. Home Assistant runtime and clean-instance HACS tests
remain separate release gates.

## Security

Use only the permissions your GitHub token needs. Do not include tokens, Home
Assistant configuration, `.storage` data or notification payloads in public
issues. See [`SECURITY.md`](SECURITY.md).

## License

[MIT](LICENSE)
