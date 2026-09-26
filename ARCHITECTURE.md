# Architecture

## Trust boundary

ApplyPilot has three deliberately separated paths:

1. **Untrusted inputs**: job pages, form labels, imported CV text, and Ollama output.
2. **Truth Layer**: explicitly approved facts and scoped Answer Vault entries in SQLite.
3. **Action layer**: browser adapters may fill only values returned by deterministic Truth Layer resolution.

The AI layer may summarize, classify, or draft. It cannot write verified profile facts and cannot supply factual form answers. The action layer receives a `FILL` or `PAUSE` decision with an exact source; it does not receive permission to improvise.

## Components

- React/Vite renderer: first-run wizard, dashboard, discovery, queue, tracker, CV library, profile, answer vault, analytics, activity.
- Local Python service: loopback-only HTTP, SQLite migrations, parsers, rules, validation, audit log. It also serves the built UI, so the desktop app is a single process. Requests must carry a loopback `Host`, a same-origin (or dev-server) `Origin`, and a JSON content type, which blocks DNS rebinding and cross-site form posts from other pages open in your browser.
- Adapter layer: Greenhouse, Lever, Workday, Ashby, SmartRecruiters, then Generic fallback.
- Desktop shell (`backend/desktop.py`): starts the service on a random loopback port and opens a native window through pywebview (Edge WebView2). It falls back to an Edge app window, then the default browser. PyInstaller bundles it and Inno Setup installs it per user; data lives in `%LOCALAPPDATA%\ApplyPilot`.
- Optional Ollama provider: schema-validated suggestions only; deterministic fallback always exists.

## Data flow

`Web page → sanitized snapshot → extracted job (UNVERIFIED) → deterministic eligibility → queue → adapter field detection → Truth Layer resolution → dry-run fill plan → validator → user review`

Submission is a separate capability gate. A valid form alone is insufficient: actual submission must also be enabled, the automation mode must permit it, and the user must approve when required.

## Extension points

New ATS systems implement the `ATSAdapter` contract. AI providers implement a future provider interface that returns validated schemas. Discovery sources feed only normalized job records. Email and calendar modules consume events without modifying profile truth.

