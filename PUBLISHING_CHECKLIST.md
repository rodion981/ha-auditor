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

Beta.1 live testing blocked stable on generic-word classification false positives,
resolution of an existing update finding with an incomplete upgrade path,
and inability to clear exclusions with an empty optional UI field.
See [the beta.1 live validation report](docs/validation/v1.7.0-beta.1-live.md).
These three regressions were subsequently fixed and revalidated in beta.2;
the real pending-update and large-inventory gates above remain open.

## v1.7.0-beta.2 regression gate

- [x] Fix generic severity/token-security descriptions triggering risk findings.
- [x] Preserve update findings for incomplete paths, including lower-severity
      target notes, independently of repository-health resolution.
- [x] Use suggested values instead of old-value defaults for clearable optional
      notification/exclusion fields.
- [x] Pass the local 133-test Home Assistant 2026.9.2 suite with 79.34% coverage,
      Ruff and formatting checks.
- [x] Owner approves fixing, publishing the next beta and live revalidation.
- [x] Verify green `main` and exact `v1.7.0-beta.2` tag CI.
- [x] Publish the beta.2 GitHub prerelease through Git/CLI.
- [x] Install beta.2 on the owner's test HA and recheck all three regressions.
- [x] Restore test fixtures/settings and confirm repeated full ordinary audits.

See [the beta.2 live validation report](docs/validation/v1.7.0-beta.2-live.md)
for controlled fixtures, DNS failures, recovery and the remaining evidence limits.

## v1.7.0-beta.3 release gate

- [x] Prefer concrete risk excerpts with intermediate-release provenance.
- [x] Expose the excerpt in native to-do items and bilingual example cards.
- [x] Mark prereleases from GitHub metadata and split confirmed path counts.
- [x] Preserve finding IDs, review states and incomplete-path safeguards.
- [x] Pass 153 Linux/Home Assistant tests with 79.79% measured coverage.
- [x] Pass local Windows tests, Ruff, formatting and strict template rendering.
- [x] Owner approves publication, installation and live validation of beta.3.
- [x] Verify green main and exact beta.3 tag CI.
- [x] Publish beta.3 through Git/CLI.
- [x] Install the exact beta.3 through HACS and verify all seven native entities.
- [x] Validate explicit prerelease metadata and both live example templates.
- [ ] Extract concrete HACS change-list items instead of their introductory sentence.
- [x] Restore controlled fixtures and confirm two ordinary 8/8 audits without errors.

The [beta.3 live report](docs/validation/v1.7.0-beta.3-live.md) separates
confirmed passes from the failed concrete-excerpt acceptance check.

## v1.7.0-beta.4 regression gate

- [x] Prefer dedicated risk sections and extract items after list introductions.
- [x] Avoid crossing sections or filling absent risk evidence with other notes.
- [x] Verify actual public HACS 2.0.0 notes locally, preserving their source.
- [x] Pass 166 Linux/HA tests with 79.99% coverage and 147 Windows tests.
- [x] Owner approves publishing beta.4 and checking it on test HAOS.
- [x] Verify green main and exact beta.4 tag CI and publish through Git/CLI.
- [x] Install beta.4 through HACS, restart Core and verify seven entities.
- [x] Repeat the HACS path scenario and verify the concrete native to-do excerpt.
- [x] Restore fixtures/settings and confirm ordinary audits without errors.

See [the beta.4 live report](docs/validation/v1.7.0-beta.4-live.md) for the
passing risk-excerpt regression, two clean ordinary audits and evidence limits.

## v1.7.0-beta.5 regression gate

- [x] Expose every assessed update in the sensor and bilingual example cards.
- [x] Preserve Recorder exclusions and bounded individual path details.
- [x] Reject feature-scoped/conditional global HA minimums; preserve explicit ones.
- [x] Refresh cached assessments with rules 9, preserving finding IDs/review states.
- [x] Pass 192 Linux/HA tests at 80.39% coverage and 169 Windows tests.
- [x] Pass Ruff, formatting and 12/120-update sensor/card regressions.
- [x] Owner explicitly approves publication of the next beta through Git/CLI.
- [x] Verify green main and exact beta.5 tag CI.
- [x] Publish beta.5 through Git/CLI and verify the tagged HACS package.
- [ ] Install beta.5 and verify all twelve update details and corrected HA requirement.

The original beta.4 audit is recorded in
[the accumulated-update report](docs/validation/v1.7.0-beta.4-backlog-audit-2026-10-19.md).
Local regression proof does not close the installed live-validation gate.
