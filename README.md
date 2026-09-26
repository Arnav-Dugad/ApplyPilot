# ApplyPilot

ApplyPilot is a local-first internship application workspace built around one hard rule: **never guess personal information**. It stores verified facts in SQLite on your own machine, separates eligibility from match quality, imports public job pages, runs safe dry-run form decisions, pauses on uncertainty, validates applications, and records a human-readable audit trail.

No account, cloud service, subscription, or API key is required.

## Download (Windows 10/11, 64-bit)

Get the latest build from [**Releases**](https://github.com/Arnav-Dugad/ApplyPilot/releases/latest):

- **`ApplyPilot-Setup-<version>.exe`**: recommended. Installs for your user only (no administrator prompt) and adds Start menu and optional desktop shortcuts.
- **`ApplyPilot-<version>-portable-win64.zip`**: unzip anywhere and run `ApplyPilot\ApplyPilot.exe`.

The builds are not code-signed yet, so Windows SmartScreen may show "Windows protected your PC". Choose **More info → Run anyway**. The app window uses Microsoft Edge WebView2, which ships with Windows 11 and current Windows 10.

Your data lives in `%LOCALAPPDATA%\ApplyPilot` (database, imported CVs). Uninstalling the app keeps it; delete that folder to remove it.

## What it does

- **First-run safety wizard** that captures only the facts you confirm.
- **Truth Layer profile** with `VERIFIED`, `UNVERIFIED`, `UNKNOWN`, and `EXPIRED` states. Every fact can be edited inline, and the autofill-readiness meter shows which common form fields are covered.
- **Work authorization and sponsorship per country**. Answers are never copied across borders, and country names and codes are matched (`UK` = `GB` = `United Kingdom`).
- **Discover**: import public job URLs (JSON-LD aware, SSRF-protected including redirects), or add jobs manually when a site blocks import. Eligibility results are saved, filterable and ranked.
- **Deterministic eligibility**: degree, work authorization, sponsorship wording, and required-skill coverage, each with a PASS/FAIL/UNKNOWN explanation.
- **Queue**: dry-run a form and see, field by field, what would be filled (with its source fact) and what pauses (with the reason). Pre-submission validation lists every blocking check.
- **CV Library** with immutable originals, duplicate detection, and explicit approval. Only approved CVs are attached to applications.
- **Tracker** board (in progress → applied → interviewing → offer → closed), **Answer Vault** for scoped reusable answers, **Analytics**, and a filterable **Activity** audit log.
- Dark and light themes, `Ctrl+K` command palette.

Automated submission is deliberately not implemented. See [DEVELOPMENT_PROGRESS.md](DEVELOPMENT_PROGRESS.md) for the exact boundary.

## Safe defaults

| Setting | Default |
|---|---|
| Strict Accuracy Mode | On |
| Dry Run | On |
| Actual submissions | Off |
| Automation mode | Review Before Submit |
| Local AI | Off |

ApplyPilot never bypasses CAPTCHA, MFA, authentication, access controls, or site restrictions.

## Develop

Requirements: Python 3.11+ and Node 20+.

```powershell
npm install
npm run dev:api      # local service on http://127.0.0.1:4817
npm run dev          # UI with hot reload on http://localhost:1420 (second terminal)
```

In development, data goes to `data/applypilot.db`, which Git ignores. To run the desktop window against a production UI build:

```powershell
py -m pip install pywebview pypdf
npm run desktop
```

Tests:

```powershell
npm run test:all     # vitest + 41 backend safety/API tests
npm run check        # typecheck + build + all tests
```

Browser automation support is optional:

```powershell
py -m pip install -r requirements.txt
py -m playwright install chromium
```

## Build the Windows app

```powershell
winget install JRSoftware.InnoSetup   # once
npm run package:win
```

This builds the UI, runs the backend tests, bundles the app with PyInstaller, and writes the portable zip and installer to `release/`.

Pushing a `v*` tag builds the same artifacts on GitHub Actions and publishes them as a release:

```powershell
git tag v0.2.0; git push origin v0.2.0
```

Bump the version in both `package.json` and `backend/__init__.py` first. The build fails if they disagree.

## Project layout

- `src/`: React/TypeScript UI (`pages/` for screens, `ui.tsx` for shared components).
- `backend/`: local HTTP service, SQLite, parsers, safety engine, eligibility, automation contracts, and `desktop.py` (native window launcher).
- `backend/tests/`: safety, eligibility, country, and API tests.
- `packaging/`: PyInstaller spec, Inno Setup installer script, icon, and `build.ps1`.
- `docs/fixtures/`: mock ATS forms for adapter testing.
