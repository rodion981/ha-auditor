# Changelog

## 1.3.0-beta.1

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
