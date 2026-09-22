# Contributing

Preserve the safety boundary. A feature must never turn model confidence, string similarity, location, citizenship, or resume inference into verified personal data.

Before a pull request:

1. Run `npm run test:backend`.
2. Run `npm run check` when Node dependencies are available.
3. Add a regression test for every changed safety decision.
4. Update `DEVELOPMENT_PROGRESS.md` honestly.
5. Never commit databases, resumes, screenshots containing personal data, browser profiles, tokens, or `.env`.

