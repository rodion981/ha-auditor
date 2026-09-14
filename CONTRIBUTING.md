# Contributing to HA Auditor

Thank you for helping improve HA Auditor. Keep changes focused, do not include
Home Assistant configuration or tokens, and run the checks below before opening
a pull request.

## Adding a translation

HA Auditor uses Home Assistant's standard custom integration translation layout:

`custom_components/custom_components_auditor/translations/<language_code>.json`

To add a language:

1. Copy `translations/en.json` to a new BCP 47 language file, for example
   `de.json`, `pl.json`, or `pt-BR.json`.
2. Translate values only. Do not rename, add, or remove JSON keys.
3. Preserve placeholders exactly, including `{matched_term}`, `{repository}`,
   `{status}`, `{reset}`, `{error}`, `{checked}`, `{targeted}`, `{total}`, and
   `{count}`.
4. Keep the JSON valid UTF-8 and run the verification commands below.

The English file is the complete source locale and Home Assistant uses it as the
fallback when a translated value is unavailable. User-visible release
assessments, GitHub errors, entity names, setup screens, options, actions, and
notification text all come from these locale files.

## Verification

```bash
python -m pip install -r requirements_test.txt
python -m compileall -q custom_components
python -m ruff check .
pytest
```

The GitHub Actions workflow also runs Home Assistant hassfest for pull requests.
