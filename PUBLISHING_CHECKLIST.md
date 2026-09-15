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

- [x] Run the current local validation suite: compile, Ruff and 97 pytest tests.
- [x] Confirm the hassfest job passes for `1.5.0-beta.1` on the public branch.
- [x] Validate UI setup and options reload in Home Assistant.
- [ ] Install the repository as a HACS custom repository in a clean test Home
      Assistant instance.
- [x] Validate finding activation and a repeated audit on a live Home Assistant
      instance.
- [ ] Validate two clean resolution checks on a live Home Assistant instance.
- [x] Confirm that no secrets, `.storage`, database or private dashboard files
      are tracked.
- [x] Review the exact `1.5.0-beta.1` staged diff.
- [x] Owner explicitly approves pushing and publishing `1.5.0-beta.1`.
- [x] Publish a prerelease whose tag matches `1.5.0-beta.1`.

The live Home Assistant test and GitHub release remain separate gates. A
green local suite is not evidence that the integration has passed hassfest or a
live Home Assistant installation test.
