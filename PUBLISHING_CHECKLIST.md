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
- [ ] Add topics such as `home-assistant`, `hacs`, `custom-component`,
      `github-releases` and `monitoring`.
- [ ] Enable GitHub private vulnerability reporting.

## Validation and release

- [x] Run the final local validation suite: compile, Ruff and 23 pytest tests.
- [ ] Install the repository as a HACS custom repository in a clean test Home
      Assistant instance.
- [ ] Validate first-run baseline, a second audit and one simulated failure.
- [x] Confirm that no secrets, `.storage`, database or private dashboard files
      are tracked.
- [x] Review the exact staged diff before the first commit.
- [x] Owner approved the first commit.
- [x] Owner approved creating and pushing the public GitHub repository.
- [ ] Publish a GitHub release whose tag matches `1.1.0`.

The clean-instance HACS test and first GitHub release intentionally remain
separate gates. A public repository is not evidence that the integration has
passed a live Home Assistant installation test.
