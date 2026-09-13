# Security policy

## Reporting a vulnerability

After the repository is published, report vulnerabilities through GitHub's
private vulnerability reporting feature. Do not post access tokens, Home
Assistant configuration files, `.storage` contents or notification payloads in
public issues.

Until a private reporting channel is configured, do not publish a live secret
as part of a report. Revoke any token that may have been exposed.

## Token handling

The optional GitHub token is read from Home Assistant configuration and is not
written to the integration store or sensor attributes. Users should reference
it through `secrets.yaml` and grant read-only access only.
