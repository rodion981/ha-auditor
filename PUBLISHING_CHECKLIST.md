# Publishing checklist

Release preparation for `rodion981/ha-auditor`.

## Owner decisions

- [x] Repository name: `ha-auditor`.
- [x] License: MIT.
- [x] Code owner: `@rodion981`.
- [x] Full English and Ukrainian README files with language switching.

## Repository metadata

- [x] Add the final `documentation` and `issue_tracker` URLs to `manifest.json`.
- [x] Add the repository description.
- [x] Add topics such as `home-assistant`, `hacs`, `custom-component`,
      `github-releases` and `monitoring`.
- [ ] Enable GitHub private vulnerability reporting.

## Validation and release

- [x] Run the `1.5.1` local validation suite: compile, Ruff and 100 tests,
      including Home Assistant 2026.9 runtime tests on Python 3.14.
- [x] Confirm the hassfest job passes for `1.5.0` on the public branch.
- [x] Confirm the hassfest and runtime-test jobs pass for `1.5.1` on the public
      branch.
- [x] Validate UI setup and options reload in Home Assistant.
- [x] Install the repository through HACS with no existing HA Auditor entry,
      then complete native setup on the test Home Assistant instance
      (`v1.7.0-beta.1`, 2026-10-13).
- [x] Validate finding activation and a repeated audit on a live Home Assistant
      instance.
- [x] Validate acknowledge, restore, snooze and ignore actions on a live Home
      Assistant instance, including restart persistence and attention state.
- [ ] Validate two clean resolution checks on a live Home Assistant instance.
- [x] Confirm that no secrets, `.storage`, database or private dashboard files
      are tracked.
- [x] Review the exact local `1.5.1` diff.
- [x] Owner explicitly approves pushing and publishing `1.5.0`.
- [x] Publish a stable release whose tag matches `1.5.0`.
- [x] Owner explicitly approves pushing and publishing `1.5.1`.
- [x] Publish a stable release whose tag matches `1.5.1`.

The live Home Assistant test and GitHub release remain separate gates. A
green local suite is not evidence that the integration has passed hassfest or a
live Home Assistant installation test.

## v1.6.0 release gate

- [x] Add target-aware Releases and Tags lookup with bounded pagination.
- [x] Pass the local compile, Ruff and 103-test runtime suite.
- [x] Pass hassfest and the complete remote test workflow.
- [x] Validate a repeated full audit on a live Home Assistant instance: 110 of
      110 components checked, 14 available updates, zero unknown matches, no
      errors and no duplicate release events.
- [ ] Validate an update whose matching Release or Tag is outside the first ten
      GitHub results on a live Home Assistant instance.
- [x] Owner explicitly approves publishing `v1.6.0-beta.1`.
- [x] Publish the prerelease tag and GitHub Release.
- [x] Owner explicitly approves publishing stable `v1.6.0`.
- [x] Publish the stable tag and GitHub Release.

## v1.7.0 release gate

- [x] Build an exact installed-to-target path from bounded GitHub Release data.
- [x] Keep unknown or incomplete boundaries explicit instead of estimating
      version distance or compatibility.
- [x] Aggregate breaking-change, security, deprecation and feature signals
      across the confirmed path.
- [x] Extract a minimum Home Assistant version only from explicit release-note
      wording.
- [x] Add bilingual dashboard cards and critical-finding automations.
- [x] Add native no-copy acknowledge/restore through one to-do list and a
      native finding-type filter.
- [x] Move runtime ownership from `hass.data` to typed
      `ConfigEntry.runtime_data` without changing the Store format.
- [x] Add translated negative action tests and runtime coverage for the full
      multi-release audit path, config flow and GitHub-token Repair.
- [x] Pass the dependency-free unit suite, Ruff and formatting checks.
- [x] Pass 119 tests in local Linux/WSL with Home Assistant 2026.9.2 and reach
      78.38% measured integration coverage.
- [x] Pass the Home Assistant runtime suite in Linux CI for both `main` and
      `v1.7.0-beta.1`.
- [ ] Validate complete, partial and tag-only paths on a live Home Assistant
      audit with real pending HACS updates.
- [ ] Confirm that the additional bounded pages stay within the expected GitHub
      request budget during a full live audit.
- [x] Owner explicitly approves pushing and publishing `v1.7.0-beta.1`.
- [x] Publish the `v1.7.0-beta.1` prerelease tag and GitHub Release.

### v1.7.0-beta.1 live result, 2026-10-13

Clean HACS installation, Ukrainian setup, all seven entities, acknowledge and
restore through To-do, review persistence across reload, native filtering,
translated negative action errors and repeated 5/5 ordinary audits passed.
Complete and partial upgrade paths were exercised with controlled state
overrides; no real pending HACS updates were present.

Stable remains blocked by generic-word classification false positives,
resolution of an existing update finding with an incomplete upgrade path,
and inability to clear exclusions with an empty optional UI field.
See [the live validation report](docs/validation/v1.7.0-beta.1-live.md).

## v1.7.0-beta.2 regression gate

- [x] Fix generic severity/token-security descriptions triggering risk findings.
- [x] Preserve update findings for incomplete paths, including lower-severity
      target notes, independently of repository-health resolution.
- [x] Use suggested values instead of old-value defaults for clearable optional
      notification/exclusion fields.
- [x] Pass the local 133-test Home Assistant 2026.9.2 suite with 79.34% coverage,
      Ruff and formatting checks.
- [x] Owner approves fixing, publishing the next beta and live revalidation.
- [ ] Verify green `main` and exact `v1.7.0-beta.2` tag CI.
- [ ] Publish the beta.2 GitHub prerelease through Git/CLI.
- [ ] Install beta.2 on the owner's test HA and recheck all three regressions.
- [ ] Restore test fixtures/settings and confirm repeated full ordinary audits.
