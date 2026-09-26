# Testing

Run `python3 -m unittest discover -s backend/tests -v` for the zero-dependency safety suite. It covers safe defaults, local API request guarding (cross-site, DNS rebinding, form posts), static UI serving and path traversal, redirect-based SSRF, country normalization, sponsorship eligibility, CV approval and queue attachment, tracker status, deletes, unknown sponsorship, wording classification, legal declarations, expired facts, prompt injection, country isolation, false-skill rejection, deterministic matching, CAPTCHA/MFA pause behavior, and submission validation.

Frontend tests run with `npm test`. Playwright adapter integration tests will run against local static fixtures; they must never use live application sites in CI.

Critical future coverage: network interruption checkpoint restoration, dynamic form re-read, confirmation receipt capture, document allowlist enforcement, and every ATS fixture.


The Windows build (`npm run package:win`) runs the backend suite before bundling, so a failing test blocks a release.
