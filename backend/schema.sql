PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS schema_migrations (
  version INTEGER PRIMARY KEY,
  applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY,
  value_json TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS profile_facts (
  id TEXT PRIMARY KEY,
  category TEXT NOT NULL,
  fact_key TEXT NOT NULL,
  country_code TEXT,
  value_json TEXT,
  status TEXT NOT NULL CHECK(status IN ('VERIFIED','UNVERIFIED','UNKNOWN','EXPIRED')),
  source TEXT NOT NULL,
  date_added TEXT NOT NULL,
  last_confirmed TEXT,
  expires_at TEXT,
  notes TEXT NOT NULL DEFAULT '',
  revision INTEGER NOT NULL DEFAULT 1,
  UNIQUE(category, fact_key, country_code)
);

CREATE TABLE IF NOT EXISTS answer_vault (
  id TEXT PRIMARY KEY,
  canonical_question TEXT NOT NULL,
  normalized_pattern TEXT NOT NULL,
  answer_type TEXT NOT NULL CHECK(answer_type IN ('EXACT','COUNTRY_SPECIFIC','COMPANY_SPECIFIC','ROLE_SPECIFIC','GENERATED_WITH_APPROVAL','MANUAL_ONLY')),
  answer_json TEXT,
  country_code TEXT,
  company TEXT,
  role_pattern TEXT,
  status TEXT NOT NULL CHECK(status IN ('VERIFIED','UNVERIFIED','UNKNOWN','EXPIRED')),
  source_fact_ids_json TEXT NOT NULL DEFAULT '[]',
  approved_at TEXT,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cvs (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  variant TEXT NOT NULL,
  original_id TEXT,
  version INTEGER NOT NULL DEFAULT 1,
  path TEXT NOT NULL,
  sha256 TEXT NOT NULL,
  is_original INTEGER NOT NULL DEFAULT 1,
  approved INTEGER NOT NULL DEFAULT 0,
  extracted_profile_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL,
  FOREIGN KEY(original_id) REFERENCES cvs(id)
);

CREATE TABLE IF NOT EXISTS jobs (
  id TEXT PRIMARY KEY,
  company TEXT,
  role TEXT,
  location TEXT,
  country TEXT,
  remote_status TEXT,
  posting_url TEXT,
  application_url TEXT,
  source TEXT NOT NULL,
  date_found TEXT NOT NULL,
  date_posted TEXT,
  deadline TEXT,
  description TEXT NOT NULL DEFAULT '',
  required_skills_json TEXT NOT NULL DEFAULT '[]',
  preferred_skills_json TEXT NOT NULL DEFAULT '[]',
  degree_requirements TEXT,
  graduation_requirements TEXT,
  experience_requirements TEXT,
  work_authorization TEXT,
  sponsorship_information TEXT,
  duration TEXT,
  start_date TEXT,
  compensation TEXT,
  application_platform TEXT,
  requisition_id TEXT,
  raw_snapshot TEXT NOT NULL DEFAULT '',
  extraction_status TEXT NOT NULL DEFAULT 'UNVERIFIED',
  UNIQUE(posting_url)
);

CREATE TABLE IF NOT EXISTS eligibility_results (
  id TEXT PRIMARY KEY,
  job_id TEXT NOT NULL UNIQUE,
  result TEXT NOT NULL CHECK(result IN ('ELIGIBLE','LIKELY_ELIGIBLE','NEEDS_INFORMATION','INELIGIBLE')),
  checks_json TEXT NOT NULL,
  match_json TEXT NOT NULL,
  recommended_cv_id TEXT,
  evaluated_at TEXT NOT NULL,
  FOREIGN KEY(job_id) REFERENCES jobs(id) ON DELETE CASCADE,
  FOREIGN KEY(recommended_cv_id) REFERENCES cvs(id)
);

CREATE TABLE IF NOT EXISTS applications (
  id TEXT PRIMARY KEY,
  job_id TEXT NOT NULL,
  status TEXT NOT NULL,
  mode TEXT NOT NULL CHECK(mode IN ('ASSIST','REVIEW_BEFORE_SUBMIT','AUTO_SUBMIT_VERIFIED')),
  dry_run INTEGER NOT NULL DEFAULT 1,
  cv_id TEXT,
  cover_letter_id TEXT,
  field_state_json TEXT NOT NULL DEFAULT '[]',
  automation_checkpoint_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  submitted_at TEXT,
  FOREIGN KEY(job_id) REFERENCES jobs(id),
  FOREIGN KEY(cv_id) REFERENCES cvs(id)
);

CREATE TABLE IF NOT EXISTS receipts (
  id TEXT PRIMARY KEY,
  application_id TEXT NOT NULL UNIQUE,
  timestamp TEXT NOT NULL,
  company TEXT NOT NULL,
  role TEXT NOT NULL,
  job_external_id TEXT,
  application_url TEXT,
  answers_json TEXT NOT NULL,
  cv_version TEXT,
  cover_letter_version TEXT,
  confirmation_text TEXT,
  confirmation_number TEXT,
  screenshot_path TEXT,
  FOREIGN KEY(application_id) REFERENCES applications(id)
);

CREATE TABLE IF NOT EXISTS activity_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  timestamp TEXT NOT NULL,
  level TEXT NOT NULL,
  action TEXT NOT NULL,
  entity_type TEXT,
  entity_id TEXT,
  details_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS fact_dependencies (
  fact_id TEXT NOT NULL,
  dependent_type TEXT NOT NULL,
  dependent_id TEXT NOT NULL,
  fact_revision INTEGER NOT NULL,
  PRIMARY KEY(fact_id, dependent_type, dependent_id),
  FOREIGN KEY(fact_id) REFERENCES profile_facts(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_jobs_company_role ON jobs(company, role);
CREATE INDEX IF NOT EXISTS idx_applications_status ON applications(status);
CREATE INDEX IF NOT EXISTS idx_activity_time ON activity_log(timestamp DESC);


-- v0.3: Autopilot, discovery, suggestions, drafts, notifications
CREATE TABLE IF NOT EXISTS watchlist (
  id TEXT PRIMARY KEY,
  platform TEXT NOT NULL,
  slug TEXT NOT NULL,
  company TEXT NOT NULL,
  created_at TEXT NOT NULL,
  last_scanned_at TEXT,
  last_status TEXT,
  jobs_seen INTEGER NOT NULL DEFAULT 0,
  internships_seen INTEGER NOT NULL DEFAULT 0,
  UNIQUE(platform, slug)
);

CREATE TABLE IF NOT EXISTS autopilot_runs (
  id TEXT PRIMARY KEY,
  trigger TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('RUNNING','COMPLETED','FAILED')),
  started_at TEXT NOT NULL,
  finished_at TEXT,
  summary_json TEXT NOT NULL DEFAULT '{}',
  events_json TEXT NOT NULL DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS suggestions (
  id TEXT PRIMARY KEY,
  source TEXT NOT NULL,
  category TEXT NOT NULL,
  fact_key TEXT NOT NULL,
  value_json TEXT,
  confidence REAL NOT NULL DEFAULT 0.5,
  evidence TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'PENDING' CHECK(status IN ('PENDING','ACCEPTED','DISMISSED')),
  created_at TEXT NOT NULL,
  UNIQUE(category, fact_key, value_json)
);

CREATE TABLE IF NOT EXISTS drafts (
  id TEXT PRIMARY KEY,
  kind TEXT NOT NULL,
  job_id TEXT,
  application_id TEXT,
  question TEXT,
  content TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'DRAFT' CHECK(status IN ('DRAFT','APPROVED')),
  model TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(job_id) REFERENCES jobs(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS notifications (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  created_at TEXT NOT NULL,
  kind TEXT NOT NULL,
  title TEXT NOT NULL,
  body TEXT NOT NULL DEFAULT '',
  page TEXT,
  read INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_notifications_read ON notifications(read, id DESC);
CREATE INDEX IF NOT EXISTS idx_drafts_job ON drafts(job_id, kind);

-- v0.4: learning, referrals, companies, offers, email sync
CREATE TABLE IF NOT EXISTS job_feedback (
  job_id TEXT PRIMARY KEY,
  vote INTEGER NOT NULL CHECK(vote IN (-1, 1)),
  source TEXT NOT NULL DEFAULT 'USER',
  created_at TEXT NOT NULL,
  FOREIGN KEY(job_id) REFERENCES jobs(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS connections (
  id TEXT PRIMARY KEY,
  first_name TEXT NOT NULL DEFAULT '',
  last_name TEXT NOT NULL DEFAULT '',
  url TEXT,
  email TEXT,
  company TEXT NOT NULL DEFAULT '',
  company_key TEXT NOT NULL DEFAULT '',
  position TEXT NOT NULL DEFAULT '',
  connected_on TEXT,
  imported_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS company_notes (
  company_key TEXT PRIMARY KEY,
  company TEXT NOT NULL,
  notes TEXT NOT NULL DEFAULT '',
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS offers (
  id TEXT PRIMARY KEY,
  application_id TEXT,
  company TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT '',
  location TEXT NOT NULL DEFAULT '',
  amount REAL NOT NULL,
  currency TEXT NOT NULL,
  period TEXT NOT NULL CHECK(period IN ('HOUR','WEEK','MONTH','YEAR','TOTAL')),
  hours_per_week REAL NOT NULL DEFAULT 40,
  duration_months REAL NOT NULL DEFAULT 3,
  perks_json TEXT NOT NULL DEFAULT '{}',
  decision_deadline TEXT,
  notes TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS email_events (
  id TEXT PRIMARY KEY,
  message_id TEXT NOT NULL UNIQUE,
  received_at TEXT,
  sender TEXT NOT NULL DEFAULT '',
  subject TEXT NOT NULL DEFAULT '',
  kind TEXT NOT NULL,
  application_id TEXT,
  action TEXT NOT NULL DEFAULT 'NONE',
  previous_status TEXT,
  created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_connections_company ON connections(company_key);
