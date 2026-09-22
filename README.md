# ApplyPilot

ApplyPilot is a local-first internship application workspace built around one hard rule: **never guess personal information**. It stores verified facts in SQLite, separates eligibility from match quality, imports public job pages, runs safe dry-run form decisions, pauses on uncertainty, validates applications, and records a human-readable audit trail.

## Current milestone

The first usable vertical slice is implemented:

- first-run safety/profile wizard;
- versioned Truth Layer with `VERIFIED`, `UNVERIFIED`, `UNKNOWN`, and `EXPIRED` states;
- country-specific work-authorization model;
- deterministic public job URL parsing with JSON-LD support and SSRF protection;
- deterministic eligibility and skill matching;
- duplicate-protected queue;
- ATS adapter architecture and dry-run field classification;
- pre-submission blocking validation;
- SQLite persistence and activity history;
- premium Windows-style responsive UI, theme toggle, and `Ctrl+K` palette;
- 15 backend safety tests.

Actual submission remains deliberately disabled. See [DEVELOPMENT_PROGRESS.md](DEVELOPMENT_PROGRESS.md) for the exact boundary.

## Run locally

Requirements: Python 3.11+, Node 20+.

```powershell
npm install
npm run dev:api
```

In a second terminal:

```powershell
npm run dev
```

Open `http://localhost:1420`. Data is created in `data/applypilot.db` and is ignored by Git.

Run safety tests:

```powershell
npm run test:backend
npm run test:all
```

Browser automation support is optional during installation:

```powershell
py -m pip install -r requirements.txt
py -m playwright install chromium
```

ApplyPilot never bypasses CAPTCHA, MFA, authentication, access controls, or site restrictions.

## Safe defaults

| Setting | Default |
|---|---|
| Strict Accuracy Mode | On |
| Dry Run | On |
| Actual submissions | Off |
| Automation mode | Review Before Submit |
| Local AI | Off |

## Project layout

- `src/` — React/TypeScript application.
- `backend/` — local SQLite service, parsers, safety engine, eligibility, automation contracts.
- `backend/tests/` — critical safety tests.
- `src-tauri/` — Tauri Windows shell target (introduced after core workflow stabilization).
- `docs/fixtures/` — mock ATS forms for adapter testing.

No cloud AI, hosted service, paid database, subscription, or API key is required.

