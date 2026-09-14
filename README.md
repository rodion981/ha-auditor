<p align="center">
  <img src="custom_components/custom_components_auditor/brand/icon.png" alt="HA Auditor" width="180">
</p>

<h1 align="center">HA Auditor</h1>

<p align="center">Understand HACS updates before you install them.</p>

<p align="center">
  <a href="README.md"><img src="https://img.shields.io/badge/lang-English-blue" alt="English"></a>
  <a href="README.uk.md"><img src="https://img.shields.io/badge/lang-Українська-yellow" alt="Українська"></a>
  <a href="https://github.com/rodion981/ha-auditor/actions/workflows/validate.yml"><img src="https://github.com/rodion981/ha-auditor/actions/workflows/validate.yml/badge.svg" alt="Validate"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-green.svg" alt="MIT License"></a>
</p>

HA Auditor is a Home Assistant custom integration for monitoring updates to
integrations installed through HACS. It reads GitHub Release notes, highlights
changes that may deserve attention and clearly reports whether every repository
was checked successfully.

It helps you answer three questions before updating:

1. Which HACS integrations currently have updates available?
2. Which releases mention breaking changes, important fixes or new features?
3. Is the audit complete, or is part of the result missing because of a GitHub
   or network error?

HA Auditor is read-only. It never installs updates or changes other
integrations.

## Highlights

- Finds enabled HACS integration update entities automatically.
- Shows installed and available versions in one place.
- Reads GitHub Releases and classifies newly discovered release notes as
  critical, important, feature or minor.
- Shows the keyword that caused each classification.
- Uses a silent first-run baseline, so old releases are not reported as new.
- Distinguishes `idle`, `running`, `partial` and `error` states.
- Stores release checkpoints and the weekly digest queue across restarts.
- Supports optional immediate notifications and a weekly digest.
- Uses GitHub ETags to avoid unnecessary API traffic.
- Provides English and Ukrainian setup screens and action descriptions.

## Installation

### HACS custom repository

1. Open **HACS** in Home Assistant.
2. Open the menu and select **Custom repositories**.
3. Add `https://github.com/rodion981/ha-auditor` with category
   **Integration**.
4. Open **HA Auditor** and select **Download**.
5. Restart Home Assistant.
6. Open **Settings > Devices & services > Add integration**.
7. Search for **HA Auditor** and complete the setup form.

### Manual installation

Copy `custom_components/custom_components_auditor` into the
`custom_components` directory of your Home Assistant configuration, restart
Home Assistant and add **HA Auditor** from **Devices & services**.

## Configuration

All settings are managed from **Settings > Devices & services > HA Auditor >
Configure**.

| Setting | Purpose |
| --- | --- |
| GitHub token | Optional read-only token that raises the API limit and lets a full audit check every discovered repository in one run. |
| Notification action | Optional Home Assistant notification action, for example `notify.mobile_app_your_phone`. Leave it empty to disable push notifications. |
| Daily audit hour | Local Home Assistant hour when the scheduled audit starts. The audit runs at minute 15. |
| Weekly digest day | Day on which the scheduled audit also sends the accumulated digest. |
| Repositories per unauthenticated run | Batch size used when no GitHub token is configured. |

The saved token is never exposed in sensor attributes. In the options form,
leave the token field empty to keep the current token, enter another token to
replace it or enable the removal switch to delete it.

## Running an audit

Scheduled audits run automatically. To run one manually, open **Developer
tools > Actions**, select `custom_components_auditor.run_audit` and choose a
mode:

| Mode | Behaviour |
| --- | --- |
| `daily` | Checks the next configured batch of repositories. |
| `full` | Checks every repository when a token is configured; otherwise checks one batch. |
| `digest` | Checks repositories and sends the accumulated weekly digest. |

Example action call:

```yaml
action: custom_components_auditor.run_audit
data:
  mode: full
  notify: false
```

Set `notify: false` when you want to refresh the sensor without sending
immediate notifications.

## Understanding the result

The integration creates `sensor.custom_components_auditor`.

| Attribute | Meaning |
| --- | --- |
| `status` | Current state: `idle`, `running`, `partial` or `error`. |
| `last_attempt` | Time when the latest audit started. |
| `last_successful_audit` | Time of the latest fully successful audit. |
| `total_components` | Number of discovered HACS integrations. |
| `targeted_this_run` | Repositories selected for the latest run. |
| `checked_this_run` | Repositories checked successfully. |
| `updates_available` | Number of updates currently offered by HACS. |
| `available_updates` | Installed and latest versions of those updates. |
| `critical`, `important`, `new_features`, `minor` | Newly detected releases grouped by classification. |
| `last_run_changes` | Releases discovered during the latest run. |
| `pending_digest_changes` | Releases waiting for the weekly digest. |
| `error_details` | Failed checks grouped by error type. |
| `github_rate_remaining` | Remaining GitHub API quota when available. |

`partial` means at least one selected repository was not checked. The result is
incomplete, so review `error_details` before relying on it.

A ready-to-use native card is available in
[`examples/dashboard.yaml`](examples/dashboard.yaml).

## How it works

On the first successful run, HA Auditor saves the latest known release for each
repository without creating old alerts. Later runs compare GitHub Releases with
that baseline, store new findings and update the sensor. Checkpoints and pending
digest entries are preserved in Home Assistant storage.

Available HACS updates and newly published GitHub releases are intentionally
reported separately. An integration can have an available update without that
release being new to the auditor.

## Limitations

- Classification is a deterministic keyword-based hint, not a security audit
  and not proof that an update is incompatible.
- Always read the linked release notes before installing an update marked
  critical or important.
- Repositories that publish only tags or commits without GitHub Releases cannot
  produce release-note alerts.
- GitHub's unauthenticated API limit is lower, so larger installations should
  use a read-only token or process repositories in batches.

## Privacy and security

HA Auditor runs inside Home Assistant and contacts the GitHub API for public
repository and release information. It does not install updates, modify other
integrations or expose the saved token in its sensor. Notifications are sent
only through the Home Assistant action explicitly configured by the user.

Do not include tokens, Home Assistant configuration, `.storage` data or
notification payloads in public issues. See [`SECURITY.md`](SECURITY.md).

## Development

```bash
python -m pip install -r requirements_test.txt
python -m compileall -q custom_components
ruff check custom_components tests
pytest
```

The automated suite covers release classification, negated breaking-change
phrases, summary sanitization, deduplication, configuration handling,
translations, repository metadata and a basic secret scan.

## License

[MIT](LICENSE)
