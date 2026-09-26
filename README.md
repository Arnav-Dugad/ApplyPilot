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

**Autopilot: your application engine.** Follow companies (one click from a built-in catalogue, or paste any Greenhouse, Lever, Ashby, or SmartRecruiters careers link). On a schedule, Autopilot:

1. scans their official public job boards for internships in your preferred locations;
2. scores every job 0–100 against your verified profile, with a breakdown of every point (skills with partial credit for related skills, location, internship fit, freshness, deadline);
3. queues the best eligible matches above your score bar;
4. pre-checks each application form. For Greenhouse jobs it reads the **real application questions** before you open a browser;
5. sends everything it can't answer to your **Inbox**, grouped, so one answer unlocks every application that asks it.

**Fill in Edge.** One click opens the real application in your own Edge window, fills every field it has a verified answer for (including attaching your approved CV), outlines what still needs you in amber, and stops. **You press submit.**

**More intelligence, never guessing:**
- **CV reading:** upload a PDF and ApplyPilot suggests your name, contact links, university, degree, graduation date, and skills, each with the line it came from. Nothing is verified until you accept it.
- **Smart answers:** approved answers are reused on reworded questions. Answers about one employer never leak to another. Dropdowns only ever receive one of their own options, and a verified `2027-05` picks "May 2027" and nothing else. Passwords are never stored or filled.
- **Local AI (optional):** with Ollama installed, ApplyPilot writes job summaries, cover letters, and answer drafts on your computer. Drafts use only verified facts, flag skills you haven't verified, and can't be approved while `[placeholders]` remain.
- **Per-country truth:** work authorization and sponsorship are answered per country and never cross borders (`UK` = `GB` = `United Kingdom`). Countries are inferred from locations like "London, UK".

Also included: a job detail drawer, Tracker board (with confetti for offers), CV Library, Answer Vault, Analytics, Activity audit log, notifications, a `Ctrl+K` palette that searches jobs, and dark/light themes.

Automated *submission* is deliberately not implemented: ApplyPilot fills and validates, you submit.

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
npm run test:all     # vitest + 67 backend tests
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
- `backend/`: local HTTP service (`server.py`), services and Autopilot (`service.py`), job-board discovery, scoring, skills taxonomy, CV reader, local AI client, live Edge filler (`browser_runner.py`), safety engine, and `desktop.py` (native window launcher).
- `backend/tests/`: safety, eligibility, country, and API tests.
- `packaging/`: PyInstaller spec, Inno Setup installer script, icon, and `build.ps1`.
- `docs/fixtures/`: mock ATS forms for adapter testing.
