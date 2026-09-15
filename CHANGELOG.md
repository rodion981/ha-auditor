# Changelog

## 1.4.0

- Add persistent actionable findings and separate component attention from audit
  failures after successful beta validation in Home Assistant.
- Remove the generic trailing `Update` suffix from HACS component names while
  preserving names where those characters are part of the actual title.

## 1.4.0-beta.1

- Add persistent actionable findings for critical and important updates,
  archived repositories and long-inactive repositories.
- Keep first seen, last seen, confirmations, recommendation and resolution
  history for each finding across Home Assistant restarts.
- Add `sensor.ha_auditor_active_findings` with bounded finding details.
- Make `binary_sensor.ha_auditor_attention_required` represent active findings
  only.
- Add `binary_sensor.ha_auditor_audit_problem` for partial and failed audits.
- Require two successful observations before reporting an inactive repository
  and two clean checks before resolving a finding.
- Preserve findings when a repository was deferred or skipped by a failed
  GitHub request, and remove findings for excluded or removed repositories.
- Send an immediate configured notification when a finding first activates,
  without duplicating the same update in the release-review section.

## 1.3.0

- Add repository exclusions to the UI options flow.
- Fall back to GitHub Tags when a repository has no Releases.
- Detect archived repositories and repositories with no push for 730 days.
- Add a fixable Home Assistant Repair that can validate a replacement GitHub
  token or remove a rejected token.
- Match HACS commit-SHA versions to the corresponding GitHub Release and tag.
- Show readable Home Assistant-local GitHub rate-limit reset times.
- Separate successful batches, complete inventory coverage and partial runs.
- Report configured-token state separately from successful authentication.

## 1.3.0-beta.7

- Treat Home Assistant's initial Repair `issue_id` payload as flow metadata,
  so the invalid-token form opens with its fields instead of appearing empty.
- Report a configured token separately from successful GitHub authentication.

## 1.3.0-beta.6

- Show the GitHub rate-limit reset as a localized date and time instead of a
  raw Unix timestamp.
- Let the invalid-token Repair either validate a replacement token or remove the
  rejected token and continue without authentication.

## 1.3.0-beta.5

- Resolve HACS commit-SHA versions through the commit referenced by a matching
  GitHub tag when a Release reports a branch such as `main` as its target.
- Refresh cached update assessments for the expanded SHA matching.

## 1.3.0-beta.4

- Match HACS commit-SHA versions to GitHub Releases and tag commits.
- Separate successful unauthenticated batches from complete inventory coverage
  with `deferred_components` and `cycle_complete` attributes.
- Refresh cached update assessments for the improved release matching.

## 1.3.0-beta.3

- Recalculate cached available-update assessments when classification rules change.
- Calibrate release classification from live audit evidence: resolved deprecation
  warnings no longer raise attention, and new options are categorized as features.
- Add repository exclusions to the UI options flow.
- Fall back to GitHub Tags when a repository has no Releases.
- Detect archived repositories and repositories with no push for 730 days.
- Add a fixable Home Assistant Repair for invalid or expired GitHub tokens.
- Budget unauthenticated audits for repository metadata, Releases and Tags.

## 1.2.0

- Assess the HACS version currently available even during the first audit.
- Match common GitHub tag prefixes such as `v1.2.3` and `release-1.2.3`.
- Publish a reason, summary and release link for every available update.
- Show whether matching release notes were found, not found or not checked yet.
- Add native New releases, Attention required and Run audit now entities.
- Keep first-run notifications silent while still showing actionable results.
- Move all audit, error and notification text into contributor-friendly locale
  files under `translations`.

## 1.1.0

- Add UI setup through Settings > Devices & services.
- Bundle the integration icon where Home Assistant can serve it locally.
- Add a localized options flow for token, notifications and schedule settings.
- Cleanly cancel audit timers and listeners when the entry is reloaded or removed.
- Distinguish a successful audit from a partial audit.
- Publish attempted, targeted and successfully checked repository counts.
- Publish available HACS updates with installed and latest versions.
- Classify GitHub failures as authentication, rate limit, network,
  repository-not-found or server errors.
- Preserve the last successful audit separately from the last attempt.
- Explain the deterministic release classification term.
- Keep pending digest entries after an incomplete digest run.
- Make push notifications optional and remove device-specific defaults.
- Extract release processing into a dependency-free, testable module.

## 1.0.0

- Initial local release.
- Discover enabled HACS update entities.
- Create a silent first-run baseline.
- Track GitHub releases with ETag support and persistent deduplication.
- Send immediate critical/important notices and a weekly digest.
