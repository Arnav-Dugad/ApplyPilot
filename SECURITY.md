# Security

## Guarantees

- Local SQLite storage by default.
- Loopback-only local service.
- Parameterized SQL and an append-oriented activity trail.
- Private/local IP targets are blocked during URL import to prevent SSRF.
- Imported page instructions are treated as data; known injection phrases are removed and logged.
- Country-scoped legal/work answers never fall back to another country.
- Unknown, expired, unverified, legal, demographic, CAPTCHA, and MFA fields pause.
- Uploads will use an explicit document allowlist. Arbitrary paths are never accepted from a page.
- Actual submission is disabled independently of Dry Run.

## Secrets

OAuth tokens and credentials must use Windows Credential Manager through the Tauri secure-storage layer. They must not enter SQLite, logs, screenshots, source control, or `.env` committed to Git.

## Reporting

Do not include real candidate data, tokens, or private application URLs in public issues. Describe the behavior with synthetic fixtures.

