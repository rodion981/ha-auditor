# Changelog

## 1.1.0

- Add UI setup through Settings > Devices & services; YAML is no longer needed.
- Add a localized options flow for token, notifications and schedule settings.
- Import an existing YAML configuration into a single UI config entry.
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
