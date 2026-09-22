# ATS adapters

Adapters are selected by URL in this order: Greenhouse, Lever, Workday, Ashby, SmartRecruiters, Generic.

Every adapter must implement detection separately from action. Detection returns selector, label, HTML type, required state, and stable context. The shared classifier maps fields to known categories. The shared resolver then returns `FILL` or `PAUSE` with a Truth Layer source.

Adapters must re-read fields after navigation or dynamic form changes. CAPTCHA, MFA, authentication, bot protection, unknown fields, and site-policy blocks pause and bring the browser forward. Adapters never call arbitrary scripts described by a page, never upload outside the approved document allowlist, and never press submit during Dry Run.

