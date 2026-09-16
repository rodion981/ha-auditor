# Security policy

## Reporting a vulnerability

Report vulnerabilities through GitHub private vulnerability reporting when the
private reporting form is available. If it is not available, open a public
issue without sensitive details and ask the maintainer for a private contact
channel. Do not post access tokens, Home Assistant configuration files,
`.storage` contents, backups, diagnostics or notification payloads in public
issues.

Until a private reporting channel is configured, do not publish a live secret
as part of a report. Revoke any token that may have been exposed.

## Token handling

The optional GitHub token is entered through the HA Auditor configuration UI
and stored by Home Assistant in the config entry under `.storage`. The token is
not copied to the HA Auditor store, entity attributes, logs or diagnostics.

Protect Home Assistant backups and the `.storage` directory because config
entries are not encrypted at rest. Use a fine-grained GitHub token with only
the read access required for public repository metadata. Revoke and replace the
token immediately if it may have been exposed.
