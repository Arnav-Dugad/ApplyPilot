# ApplyPilot development progress

Last updated: 2026-09-27

## Completed in 0.2 (first downloadable release)

- Windows desktop app: single-process launcher (`backend/desktop.py`) with a native WebView2 window, PyInstaller bundle, per-user Inno Setup installer, portable zip, and a tag-triggered GitHub Actions release workflow.
- Packaged data lives in `%LOCALAPPDATA%\ApplyPilot`; the service serves the built UI with a strict CSP.
- Security: the local API rejects cross-site requests (Host/Origin/content-type checks), and URL import re-checks every redirect hop against private networks.
- Country normalization (`IN` = `India`, `UK` = `GB`) for authorization, sponsorship, and Answer Vault scope; they still never cross borders.
- Sponsorship eligibility check (PASS/FAIL/UNKNOWN) from verified per-country need and posting wording.
- Manual job entry with deterministic skill and requirement extraction; saved eligibility shown on reload.
- CV approval, duplicate detection, and automatic attachment of the latest approved CV to queued applications.
- Tracker board with status changes, Answer Vault CRUD and approval, Analytics, and a filterable Activity log.
- Profile: inline fact editing, per-country authorization/sponsorship grid, autofill-readiness meter.
- Queue: field-by-field dry-run plan with sources and pause reasons; validation failures listed individually.
- Fixed: production build (tsconfig), invisible first-run wizard buttons, serif fallback fonts, light-theme contrast, hardcoded date/name on Home.
- Tests: 41 backend tests and frontend helper tests.

## Completed in milestone 0.1

- Repository initialized from an empty workspace.
- SQLite schema for settings, profile truth, Answer Vault, CV versions, normalized jobs, eligibility, applications, receipts, activity, and dependencies.
- Safe migrations and conservative defaults.
- Versioned Truth Layer; changed facts expire dependent answers/applications.
- Country-specific work authorization and sponsorship lookup.
- Deterministic field classifier, resolver, prompt-injection filtering, and pre-submission validator.
- Public URL importer with JSON-LD extraction, normalized fields, body-size limit, and SSRF prevention.
- Deterministic skill extraction, eligibility, and transparent match factors.
- Duplicate-protected application queue and checkpointed dry-run results.
- React first-run wizard, dashboard, discover/import, eligibility, queue, profile, settings, activity, theme, and command palette.
- Critical backend suite: 18 passing tests.

## Environment limitation observed

This build environment returns HTTP 403 for public npm and PyPI registries and does not include Rust. The frontend source could not be dependency-installed/bundled here, and Playwright/Tauri binaries could not be installed here. Backend tests and live HTTP API smoke tests remain executable with no downloads. CI and a normal Windows developer machine can install those free dependencies.

## Next implementation checkpoint

1. Add PDF upload/extraction endpoint and immutable CV version records.
2. Complete Playwright page lifecycle and per-ATS selector implementations against local fixtures.
3. Add Answer Vault CRUD and user-answer resume flow.
4. Add full review screen and document allowlist.
5. Capture successful confirmation receipts.
6. Add Ollama health/model discovery and strict schema validation.
7. Code-sign the Windows installer.
8. Wire the Playwright browser runner to the queue behind the existing pause rules.

## Non-negotiable boundary

Actual submission is not implemented or enabled in this milestone. The current application runs analysis and a deterministic dry-run field plan. Do not represent it as production-ready for unattended submission until the adapter integration and Windows packaging checkpoints pass.
