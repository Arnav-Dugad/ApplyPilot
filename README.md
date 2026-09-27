# ApplyPilot

ApplyPilot finds internships for you across the internet, tells you in plain words whether you can apply (degree, graduation year, experience, citizenship, visa), and fills in application forms from your profile. It runs on your own computer and follows one hard rule: **it never guesses anything about you**. You always press submit yourself.

No account, cloud service, subscription, or API key is required.

## Download (Windows 10/11, 64-bit)

**[⬇ Download the latest ApplyPilot](https://github.com/Arnav-Dugad/ApplyPilot/releases/latest)** and run **`ApplyPilot-Setup-<version>.exe`**.

- Installs for your user only — no administrator prompt — with Start menu and optional desktop shortcuts.
- **Updates itself.** ApplyPilot checks for new versions, downloads them in the background with a live progress bar, verifies the download against GitHub's published checksum, and restarts on the new version. Nothing to re-download, ever.
- Prefer not to install? Use **`ApplyPilot-<version>-portable-win64.zip`**: unzip it and run `ApplyPilot\ApplyPilot.exe` (portable copies tell you when an update is out instead of installing it).

The installer isn't code-signed yet, so Windows SmartScreen may say "Windows protected your PC" — choose **More info → Run anyway**. The window uses Microsoft Edge WebView2, which ships with Windows 11 and current Windows 10.

**Your data never leaves your computer.** It lives in `%LOCALAPPDATA%\ApplyPilot` (database, CVs, backups). Uninstalling keeps it; **Settings → Backup & reset** backs it up, restores it, or erases everything and starts fresh.

### First five minutes

1. Finish the short setup (name, studies, skills, citizenship, where you'd like to work). A quick tour then shows you around; replay it any time from the **?** button.
2. **My profile:** add your degree, year of study, CGPA, LinkedIn and GitHub. Paste a GitHub link under **Projects** and it fills in by itself, or import all your repositories at once.
3. **My CVs:** upload your CV (PDF) and approve it. Its details arrive as suggestions in your Inbox.
4. **Autopilot:** turn it on. It searches worldwide internship lists and the companies you follow every few hours (closing the window keeps it running in the tray).
5. **Today** tells you what's worth doing next.

## What's new in 0.5

- **Searches the whole internet.** Besides the companies you follow, Autopilot reads the Simplify internship list (thousands of live internships), The Muse, Arbeitnow, Himalayas, Jobicy, Remotive and the Hacker News hiring thread, keeps only what fits your places and roles, and fetches the full posting from the company's own job board. Sites that forbid automated reading (LinkedIn, Indeed, Internshala) are never touched.
- **Reads what a job really asks for:** seniority, years of experience (and whether coursework counts), degree level and field, graduation window, year of study, current-student rules, GPA, citizenship or security clearance, visa sponsorship, and term dates — each shown with the sentence it came from.
- **Works out visas for you.** Add your citizenship and ApplyPilot knows where you can work without a visa (including EU, GCC, UK–Ireland, Australia–NZ and India–Nepal free movement). Your own answer for a country always wins. Jobs are sorted into *You qualify*, *Good fit*, *Needs a visa*, *Needs your answer* and *Not a fit*.
- **A much bigger profile:** citizenship and visas, links, degree, year and semester, CGPA, experience (or “none yet”), certifications, roles, and when you're free — all used in matching and form filling.
- **Projects from GitHub** in one paste: description, languages, skills and README highlights.
- **Plain words everywhere**, a guided tour, and a help page explaining every label.
- A "Connecting to GitHub…" state before update downloads start, a checkmark-and-confetti after an update, a live pipeline that pulses as jobs arrive, company cards that flip to show hiring seasons, and an Inbox ripple that shows which applications an answer unlocks.

## What it does

**Autopilot: your application engine.** It searches worldwide internship lists, plus any companies you follow (one click from a built-in catalogue, or paste any Greenhouse, Lever, Ashby, SmartRecruiters, Workday, Workable, Recruitee, or Teamtailor careers link). On a schedule, Autopilot:

1. finds internships in the places and roles you chose;
2. scores every job 0–100 against your verified profile, with a breakdown of every point (skills with partial credit for related skills, location, internship fit, freshness, deadline);
3. queues the best eligible matches above your score bar;
4. pre-checks each application form. For Greenhouse jobs it reads the **real application questions** before you open a browser;
5. sends everything it can't answer to your **Inbox**, grouped, so one answer unlocks every application that asks it.

**Fill in Edge.** One click opens the real application in your own Edge window, fills every field it has a verified answer for (including attaching your approved CV), outlines what still needs you in amber, and stops. **You press submit.**

**More intelligence, never guessing:**
- **CV reading:** upload a PDF and ApplyPilot suggests your name, contact links, university, degree, graduation date, and skills, each with the line it came from. Nothing is verified until you accept it.
- **Smart answers:** approved answers are reused on reworded questions. Answers about one employer never leak to another. Dropdowns only ever receive one of their own options, and a verified `2027-05` picks "May 2027" and nothing else. Passwords are never stored or filled.
- **Local AI (optional):** with Ollama installed, ApplyPilot writes job summaries, cover letters, and answer drafts on your computer. Drafts use only verified facts, flag skills you haven't verified, and can't be approved while `[placeholders]` remain.
- **Per-country truth:** whether you can work somewhere is worked out from your citizenship or answered per country, and never copied across borders (`UK` = `GB` = `United Kingdom`). A question that names a country ("Are you authorized to work in India?") is answered for that country, not the job's. Countries are inferred from locations like "London, UK" or "Pittsburgh, PA".

**Also in 0.4:**
- **Today:** the five highest-value actions right now, a profile-strength ring, and a health strip (failing boards, passed deadlines, expired answers).
- **Insights:** an animated pipeline flow from discovered to offer, a world map of where your matches are, and a "Why not me?" coach showing which skill or fact would unlock the most jobs.
- **Companies:** a page per company with roles, your history, hiring-season chart, private notes, and people you know (import LinkedIn's Connections.csv to find referrals and draft a referral request).
- **Calendar** of openings, deadlines, applications, and interviews, plus each followed company's hiring seasons. **Deadline radar** notifies you 72 hours before a queued job closes.
- **Offers:** compare stipends across currencies and pay periods (hourly, weekly, monthly, yearly, total) with live exchange rates and official Gulf currency pegs.
- **Tailored CVs:** reorder your CV's skills for each job, review a colour-coded diff, and approve to generate a clean PDF. Invented skills or numbers are flagged and block approval.
- **Interview prep packs:** technical, role, company, and behavioural questions to tick off, your matching projects, and questions to ask them.
- **Learns your taste** from 👍/👎 and adjusts rankings, spots **duplicate postings** across boards, checks **spoken-language requirements**, and understands **plain-English search** ("backend roles with Python in Europe").
- **Email sync (IMAP):** interview invites, rejections, and offers move your Tracker cards automatically, with one-click undo. The app password is encrypted with Windows data protection.
- **Follow-up drafts** two weeks after you apply, a focused one-question-at-a-time Inbox, Windows notifications, a tray icon, start with Windows, and Workday, Workable, Recruitee, and Teamtailor boards.

Automated *submission* is deliberately not implemented: ApplyPilot fills and validates, you submit.

## Safe defaults

| Setting | Default |
|---|---|
| Never guess | On |
| Practice mode | On |
| Real submissions | Off |
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
npm run test:all     # vitest + 98 backend tests
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
