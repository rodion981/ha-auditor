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
changes that may deserve attention, keeps actionable findings until they are
confirmed resolved and clearly reports whether every repository was checked
successfully.

It helps you answer three questions before updating:

1. Which HACS integrations currently have updates available?
2. Which releases mention breaking changes, important fixes or new features?
3. Is the audit complete, or is part of the result missing because of a GitHub
   or network error?

HA Auditor is read-only. It never installs updates or changes other
integrations.

## Highlights

- Finds enabled HACS integration update entities automatically.
- Shows installed and available versions with the matching release summary.
- Classifies both currently available updates and newly discovered releases as
  critical, important, feature or minor.
- Shows the keyword that caused each classification.
- Keeps persistent findings with first/last seen time, confirmations,
  recommendation and resolution history.
- Separates component findings from GitHub or audit failures.
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
| Excluded repositories | Repositories that should not be audited, one `owner/repository` per line. |
| Daily audit hour | Local Home Assistant hour when the scheduled audit starts. The audit runs at minute 15. |
| Weekly digest day | Day on which the scheduled audit also sends the accumulated digest. |
| GitHub request budget per unauthenticated run | API request budget used without a token. Metadata, Releases and fallback Tags can require up to three requests per repository. |

The saved token is never exposed in sensor attributes. In the options form,
leave the token field empty to keep the current token, enter another token to
replace it or enable the removal switch to delete it.

## Running an audit

Scheduled audits run automatically. To run one manually, open the HA Auditor
device from **Settings > Devices & services** and press
`button.ha_auditor_run_audit`, or add that button to your dashboard. The
`custom_components_auditor.run_audit` action remains available when you need to
choose a mode or notification behaviour:

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

## Managing findings

Every active finding exposes a stable `finding_id`. Use it with the native HA
Auditor actions from **Developer tools > Actions** or in an automation:

```yaml
action: custom_components_auditor.acknowledge_finding
data:
  finding_id: "ad-ha/kidschores-ha:health"
```

- `acknowledge_finding` keeps the finding visible but marks it as reviewed.
- `snooze_finding` removes it from the attention indicator for 7 or 30 days;
  add `days: 7` or `days: 30` to the action data.
- `ignore_finding` hides that exact finding from the attention indicator until
  its available version or repository condition changes.
- `restore_finding` returns an acknowledged, snoozed or ignored finding to
  `new`.

The finding remains technically active until the auditor confirms that its
underlying condition is gone. A new update version gets a new fingerprint and
automatically returns to `new`, even when the previous version was reviewed.

## Understanding the result

The integration creates five native Home Assistant entities:

| Entity | Purpose |
| --- | --- |
| `sensor.custom_components_auditor` | Number of releases first seen during the latest audit, with full audit details in its attributes. |
| `sensor.ha_auditor_active_findings` | Number of persistent actionable findings, with their lifecycle, recommendation and URL in attributes. |
| `binary_sensor.ha_auditor_attention_required` | Turns on only while at least one active finding is new and unreviewed. |
| `binary_sensor.ha_auditor_audit_problem` | Turns on when the latest audit is partial or failed. |
| `button.ha_auditor_run_audit` | Runs the most complete audit allowed by the configured GitHub credentials without sending a push notification. |

| Attribute | Meaning |
| --- | --- |
| `status` | Current state: `idle`, `running`, `partial` or `error`. |
| `last_attempt` | Time when the latest audit started. |
| `last_successful_audit` | Time of the latest fully successful audit. |
| `total_components` | Number of discovered HACS integrations. |
| `targeted_this_run` | Repositories selected for the latest run. |
| `checked_this_run` | Repositories checked successfully. |
| `deferred_components` | Repositories deferred to later runs because the current unauthenticated batch is smaller than the discovered inventory. |
| `cycle_complete` | `true` when the latest run checked the complete discovered inventory successfully. |
| `updates_available` | Number of updates currently offered by HACS. |
| `available_updates` | Installed/latest versions, attention level, reason, summary, release URL and `found` / `not_found` / `not_checked` release-note status for current updates. |
| `available_update_counts` | Current available updates grouped as `critical`, `important`, `feature`, `minor` or `unknown`. |
| `repository_health_counts` | Number of archived repositories and repositories with no push for at least 730 days. |
| `repository_health_details` | Repository status, last push date, inactive days and GitHub URL. |
| `excluded_repositories` | Repositories skipped through the integration options. |
| `attention_required` | Whether the current result needs user attention. |
| `audit_problem` | Whether the latest audit is partial or failed. |
| `active_finding_count` | Number of active actionable findings. |
| `active_findings` | Stable finding ID, repository, component, type, severity, review status, lifecycle timestamps, recommendation and URL for each active finding. |
| `finding_counts` | Active findings grouped by severity, source and `new`, `acknowledged`, `snoozed` or `ignored` review status. |
| `findings_pending_confirmation` | Potential inactive-repository findings waiting for another successful observation. |
| `pending_findings` | Details of inactive-repository candidates waiting for confirmation. |
| `recently_resolved_findings` | Findings confirmed absent by two clean checks and retained for 30 days. |
| `finding_changes` | Findings activated or resolved during the latest run. |
| `critical`, `important`, `new_features`, `minor` | Newly detected releases grouped by classification. |
| `last_run_changes` | Releases discovered during the latest run. |
| `pending_digest_changes` | Releases waiting for the weekly digest. |
| `error_details` | Failed checks grouped by error type. |
| `github_token_configured` | Whether a GitHub token is currently configured. |
| `github_authenticated` | Whether the configured token was accepted during the latest run. |
| `github_rate_remaining` | Remaining GitHub API quota when available. |

The detailed finding lifecycle attributes are exposed by
`sensor.ha_auditor_active_findings`; the original result sensor keeps compact
finding counts for existing dashboards and automations.

`partial` means at least one selected repository was not checked because of an
error or interrupted request sequence. A successful unauthenticated batch stays
`idle`; use `deferred_components` and `cycle_complete` to see whether that run
covered the complete inventory.

A ready-to-use native card is available in
[`examples/dashboard.yaml`](examples/dashboard.yaml).

## How it works

On the first successful run, HA Auditor immediately assesses every currently
available HACS update for which it can match a GitHub Release. It also saves the
latest known release for each repository without creating old alerts. Later
runs compare GitHub Releases with that baseline, store new findings and update
the entities. Checkpoints and pending digest entries are preserved in Home
Assistant storage.

Available HACS updates and newly published GitHub releases are intentionally
reported separately. An integration can have an available update without that
release being new to the auditor.

If a repository has no GitHub Releases, HA Auditor falls back to its latest
GitHub Tags. A matched tag is reported as the source, without inventing release
notes or a risk classification. Repository metadata is also checked for the
GitHub `archived` flag and for a last push at least 730 days ago.

Critical and important update findings, and archived-repository findings,
activate immediately. A repository must be observed as inactive in two
successful checks before its finding activates. Any active finding needs two
clean checks before it is marked resolved. A repository deferred by the API
budget or missed because of a GitHub error does not advance or clear a finding.
Resolved findings remain available for 30 days; excluded or removed
repositories are removed from finding storage.

Acknowledging, snoozing or ignoring a finding changes only its review status.
The finding stays in `active_findings`, but only `new` findings turn on the
attention binary sensor. Snoozes reopen automatically at their deadline.

If GitHub rejects a configured token, HA Auditor creates a fixable Home
Assistant Repair. The repair flow can validate and save a replacement token or
remove the rejected token and continue with unauthenticated batches.

## Limitations

- Classification is a deterministic keyword-based hint, not a security audit
  and not proof that an update is incompatible.
- Always read the linked release notes before installing an update marked
  critical or important.
- Tag-only repositories can be tracked, but a tag does not provide release notes
  or enough evidence for a risk classification.
- If the HACS version cannot be matched to one of the ten latest GitHub Releases
  or 100 latest Tags, the update is shown as `unknown` instead of guessing.
- GitHub's unauthenticated API limit is lower, so larger installations should
  use a read-only token or process repositories in batches.

## Privacy and security

HA Auditor runs inside Home Assistant and contacts the GitHub API for public
repository metadata, Releases and Tags. It does not install updates, modify other
integrations or expose the saved token in its sensor. Notifications are sent
only through the Home Assistant action explicitly configured by the user.

Detailed entity attributes remain available for dashboards, templates and
automations, but HA Auditor excludes them from Recorder history to avoid
repeatedly storing large audit payloads. **Download diagnostics** exposes only
configuration flags, progress and aggregate counts; it excludes the GitHub
token, notification target and repository names.

Do not include tokens, Home Assistant configuration, `.storage` data or
notification payloads in public issues. See [`SECURITY.md`](SECURITY.md).

## Development

```bash
python -m pip install -r requirements_test.txt
python -m compileall -q custom_components
ruff check custom_components tests
python -m pytest
```

The Home Assistant runtime tests require Linux or WSL, Python 3.14 and a
separate environment because Home Assistant itself is not supported as a
native Windows runtime:

```bash
python -m pip install -r requirements_runtime_test.txt
python -m pytest tests/test_runtime.py
```

The automated suite covers release classification, negated breaking-change
phrases, summary sanitization, deduplication, configuration handling,
translations, repository metadata, finding lifecycle and a basic secret scan.
The runtime gate additionally loads the integration through Home Assistant,
registers its entities and actions, verifies finding persistence across a
config-entry reload and checks that diagnostics do not expose private values.

Want to add another interface language? See
[`CONTRIBUTING.md`](CONTRIBUTING.md#adding-a-translation). Each locale is a
separate JSON file in the integration's `translations` directory, so no Python
changes are needed.

## License

[MIT](LICENSE)
