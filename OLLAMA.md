# Optional Ollama integration

Ollama is off by default. The planned settings surface supports `Off`, `Ollama`, and a reserved future provider, with a configurable default endpoint of `http://localhost:11434`.

Allowed tasks include job summarization, requirement extraction, terminology matching, CV bullet selection, and draft generation. Outputs must validate against a JSON schema and remain unverified. Invalid JSON, timeout, missing service, out-of-memory errors, or conflicting output fall back to deterministic behavior.

Ollama may not answer factual candidate questions or update the Truth Layer. Model downloads always require user action after size and hardware guidance are shown.

