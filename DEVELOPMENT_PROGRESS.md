# ApplyPilot development progress

Last updated: 2026-09-27

## Completed in 0.3 (Autopilot)

- Autopilot: scheduled discovery from Greenhouse, Lever, Ashby, and SmartRecruiters public feeds; curated company catalogue; location and internship filters; auto-queue above a score bar; form pre-checks; notifications; live run timeline.
- Transparent 0-100 match score; 150-skill taxonomy with aliases, ambiguity rules, and related-skill partial credit; employer names never count as skills.
- Real Greenhouse application questions fetched and resolved before any browser opens.
- Inbox: grouped questions answered once for all applications; CV-derived profile suggestions with evidence; AI drafts to review.
- Resolver: first/last name from unambiguous legal names, fuzzy Answer Vault reuse with an employer guard, option-aware selects, date-aware options, credential fields never filled, résumé upload.
- Live fill in the user's Edge window via Playwright over CDP; fields outlined green/amber; never submits.
- Optional local AI (Ollama): model detection and one-click download, job summaries, cover letters, answer drafts with unverified-skill flags and placeholder gating.
- UI: Autopilot command centre, Inbox, job drawer, animated score rings and counters, orb, confetti, notifications, page transitions, job search in the palette.
- Tests: 67 backend tests including a full Autopilot pipeline against a fake board and the Ollama protocol against a fake server.

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
8. Per-ATS adapters for custom widgets (Workday, Ashby React selects) in live fill.
9. Auto-submit, only as an explicit per-application opt-in after a final review screen.

## Non-negotiable boundary

Actual submission is not implemented or enabled in this milestone. The current application runs analysis and a deterministic dry-run field plan. Do not represent it as production-ready for unattended submission until the adapter integration and Windows packaging checkpoints pass.
