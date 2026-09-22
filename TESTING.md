# Testing

Run `python3 -m unittest discover -s backend/tests -v` for the zero-dependency safety suite. It covers safe defaults, unknown sponsorship, wording classification, legal declarations, expired facts, prompt injection, country isolation, false-skill rejection, deterministic matching, CAPTCHA/MFA pause behavior, and submission validation.

Frontend tests run with `npm test`. Playwright adapter integration tests will run against local static fixtures; they must never use live application sites in CI.

Critical future coverage: network interruption checkpoint restoration, dynamic form re-read, confirmation receipt capture, document allowlist enforcement, and every ATS fixture.

