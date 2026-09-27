export type FactStatus = 'VERIFIED' | 'UNVERIFIED' | 'UNKNOWN' | 'EXPIRED'
export type Fact = { id?: string; category: string; fact_key: string; country_code?: string | null; value?: unknown; status: FactStatus; source: string; last_confirmed?: string | null; notes?: string; revision?: number }
export type EligibilityResult = 'ELIGIBLE' | 'LIKELY_ELIGIBLE' | 'VISA_NEEDED' | 'NEEDS_INFORMATION' | 'INELIGIBLE'
export type Check = { name: string; result: 'PASS' | 'FAIL' | 'UNKNOWN' | 'PARTIAL' | 'WARN' | 'VISA' | string; explanation: string; evidence?: string }
export type JobTag = { label: string; tone: 'good' | 'warn' | 'bad' | 'neutral' }
export type Match = { strong: string[]; partial: string[]; missing: string[]; related?: string[]; required_coverage?: number | null; weighted_coverage?: number | null }
export type ScoreFactor = { name: string; points: number; max: number; detail: string }
export type Score = { score: number; grade: string; factors: ScoreFactor[]; adjustment?: string | null; location_ok?: boolean | null; is_internship?: boolean }
export type Analysis = { result: EligibilityResult; checks: Check[]; match: Match; score?: Score }
export type AISummary = { summary: string; highlights: string[]; watch_outs: string[]; model?: string }
export type Job = {
  id: string; company?: string | null; role?: string | null; location?: string | null; country?: string | null; remote_status?: string | null
  description: string; required_skills: string[]; preferred_skills: string[]; posting_url?: string | null; application_url?: string | null
  application_platform?: string | null; extraction_status: string; date_found: string; date_posted?: string | null; deadline?: string | null; source?: string
  compensation?: string | null; employment_type?: string | null; question_count?: number
  work_authorization?: string | null; sponsorship_information?: string | null
  eligibility_result?: EligibilityResult | null; eligibility_checks?: Check[]; eligibility_match?: Match; score?: Score | null; ai_summary?: AISummary | null
  duplicate_of?: string | null; vote?: number | null; country_code?: string | null; tags?: JobTag[]
}
export type FieldDecision = { action: 'FILL' | 'PAUSE' | 'SKIP'; value?: unknown; source?: string | null; reason: string; upload?: boolean }
export type FieldResult = { selector: string; label: string; required: boolean; classification: string; options?: string[]; decision: FieldDecision }
export type BrowserRun = { status?: 'RUNNING' | 'DONE' | 'FAILED'; events?: { at: string; step: string; message: string }[]; filled?: number; paused?: number }
export type Application = {
  id: string; job_id: string; company?: string | null; role?: string | null; location?: string | null; country?: string | null; posting_url?: string | null; application_url?: string | null
  status: string; dry_run: boolean; mode: string; cv_id?: string | null; cv_name?: string | null; prep_source?: string | null
  field_state?: FieldResult[]; browser_run?: BrowserRun; created_at: string; updated_at: string; submitted_at?: string | null
  deadline?: string | null; status_note?: string | null; email_event_id?: string | null
}
export type CV = {
  id: string; name: string; variant: string; version: number; sha256: string; approved: boolean; created_at: string
  extracted_profile?: { notice?: string; email_candidates?: string[]; skill_candidates?: string[]; text_length?: number; extraction_error?: string }
}
export type Answer = { id: string; canonical_question: string; answer_type: string; answer?: unknown; country_code?: string | null; company?: string | null; role_pattern?: string | null; status: FactStatus; updated_at: string }
export type Activity = { id: number; timestamp: string; action: string; level: string; entity_type?: string | null; details?: Record<string, unknown> }
export type Validation = { valid: boolean; blocked: boolean; failures: string[]; warnings: string[] }
export type Watch = { id: string; platform: string; slug: string; company: string; created_at: string; last_scanned_at?: string | null; last_status?: string | null; jobs_seen: number; internships_seen: number }
export type CatalogEntry = { platform: string; slug: string; company: string; region?: string }
export type RunEvent = { at: string; step: string; message: string; level: string; company?: string; job_id?: string; source?: string; new?: number }
export type RunSummary = { boards: number; found: number; new: number; worldwide?: number; filtered: number; analyzed: number; queued: number; prepared: number; ready: number; needs_you: number; summaries: number; letters: number }
export type AutopilotRun = { id: string; trigger: string; status: 'RUNNING' | 'COMPLETED' | 'FAILED'; started_at: string; finished_at?: string | null; summary: Partial<RunSummary>; events: RunEvent[] }
export type AutopilotConfig = { enabled: boolean; interval_hours: number; min_score: number; auto_queue: boolean; auto_prepare: boolean; location_filter: boolean; internships_only: boolean; ai_summaries: boolean; ai_cover_letters: boolean; worldwide?: boolean }
export type AutopilotState = { config: AutopilotConfig; running: string | null; next_run_at: string | null; runs: AutopilotRun[] }
export type InboxQuestion = { key: string; question: string; classification: string; kind: 'FACT' | 'COUNTRY_FACT' | 'ANSWER' | 'RESUME' | 'COVER_LETTER' | 'CREDENTIAL'; options: string[]; required: boolean; reason: string; country?: string | null; applications: { id: string; job_id: string; company?: string; role?: string }[] }
export type Suggestion = { id: string; source: string; category: string; fact_key: string; value: unknown; confidence: number; evidence: string; created_at: string }
export type Draft = { id: string; kind: 'COVER_LETTER' | 'ANSWER' | 'SUMMARY' | 'FOLLOW_UP' | 'CV_TAILORED'; application_id?: string | null; job_id?: string | null; question?: string | null; content: string; status: 'DRAFT' | 'APPROVED'; model?: string | null; company?: string | null; role?: string | null; updated_at: string; unverified_skills?: string[] }
export type Inbox = { questions: InboxQuestion[]; suggestions: Suggestion[]; drafts: Draft[] }
export type Notification = { id: number; created_at: string; kind: string; title: string; body: string; page?: string | null; read: number }
export type AIStatus = { available: boolean; enabled: boolean; endpoint: string; version?: string; models: string[]; model?: string | null; recommended: { name: string; size: string; note: string }[]; pull: { status: string; model?: string; completed?: number; total?: number; detail?: string } }
export type JobDetail = Job & { board_questions?: { label: string; required: boolean; field_type: string; options: string[] }[]; drafts: Draft[]; application?: { id: string; status: string } | null
  languages?: { required: string[]; preferred: string[] }; referrals?: Connection[]; duplicates?: { id: string; company: string; role: string; source: string; posting_url?: string }[]; company_notes?: string }
export type Bootstrap = {
  version?: string; settings: Record<string, unknown>; facts: Fact[]; jobs: Job[]; applications: Application[]; activity: Activity[]; cvs: CV[]; answers: Answer[]
  watchlist: Watch[]; catalog: CatalogEntry[]; inbox: Inbox; autopilot: AutopilotState; notifications: Notification[]
  update?: UpdateState; strength?: Strength; today?: TodayAction[]; health?: HealthIssue[]; connections?: number; offers?: OffersOverview
  student?: StudentSummary; visa?: VisaRow[]
}

// ---- v0.4 ----
export type UpdateState = {
  status: 'idle' | 'checking' | 'up_to_date' | 'available' | 'downloading' | 'verifying' | 'ready' | 'installing' | 'error'
  current: string; latest?: string; notes?: string; published_at?: string; checked_at?: string; release_url?: string; releases_page: string
  mode: 'installer' | 'portable' | 'dev'; downloaded?: number; total?: number; speed?: number; eta?: number | null; error?: string | null
  install_at?: string | null; postponed?: boolean; asset?: { name: string; size: number } | null
}
export type StrengthItem = { label: string; points: number; done: boolean }
export type Strength = { percent: number; next: StrengthItem[]; items: StrengthItem[] }
export type TodayAction = { value: number; kind: 'DEADLINE' | 'SUBMIT' | 'INBOX' | 'PREP' | 'FOLLOW_UP' | 'SUGGESTIONS' | 'DISCOVER'; title: string; detail?: string; page: string; job_id?: string }
export type HealthIssue = { level: 'bad' | 'warn' | 'info'; title: string; detail: string; page: string }
export type OfferRow = { id: string; company: string; role: string; location: string; amount: number; currency: string; period: 'HOUR' | 'WEEK' | 'MONTH' | 'YEAR' | 'TOTAL'; hours_per_week: number; duration_months: number; perks?: Record<string, number>; decision_deadline?: string | null; notes: string; monthly: number; monthly_base: number | null; total_base: number | null; perks_base: number; hourly_base: number | null; best: boolean }
export type OffersOverview = { base: string; rows: OfferRow[]; currencies: string[]; rates_source: string | null; rates_updated?: string | null }
export type Connection = { id: string; first_name: string; last_name: string; url?: string; company: string; position: string }
export type CoachTip = { kind: 'SKILL' | 'FACT'; name: string; jobs: number; unlocks: number; examples: string[] }
export type CompanySummary = { key: string; name: string; jobs: number; best_score: number; applications: number; statuses: Record<string, number>; followed: boolean; platform?: string | null; watch_id?: string | null; connections: number; has_notes: boolean; last_seen: string; seasons?: number[] }
export type CompanyDetail = CompanySummary & { roles: (Job & { score_json?: string })[]; application_history: { id: string; job_id: string; status: string; submitted_at?: string | null; updated_at: string; role: string }[]; people: Connection[]; notes: string; seasons: number[] }
export type CalendarEvent = { date: string; kind: 'POSTED' | 'DEADLINE' | 'APPLIED' | 'INTERVIEW'; title: string; job_id?: string }
export type CalendarData = { events: CalendarEvent[]; seasons: { company: string; months: number[] }[] }
export type PrepPack = { role: string; company: string; technical: { skill: string; question: string }[]; role_specific: string[]; company_questions: string[]; behavioural: string[]; projects: { name: string; description: string; skills: string[]; overlap: string[]; link?: string }[]; unmatched_skills: string[]; company_notes: string[]; your_notes: string; questions_to_ask: string[]; people: Connection[] }
export type SearchResult = { parsed: { skills: string[]; countries: string[]; places: string[]; roles: string[]; remote: boolean; keywords: string[] }; ids: string[]; semantic?: boolean }
export type TailorResult = { id: string; original: string; content: string; model: string; flags: { skills: string[]; numbers: string[] }; company?: string; role?: string; status?: string }
export type EmailEvent = { id: string; message_id: string; received_at?: string; sender: string; subject: string; kind: string; application_id?: string | null; action: string; company?: string; role?: string; created_at: string }
export type Backup = { name: string; size: number; created_at: string }

// ---- v0.5 ----
export type StudentSummary = {
  derived: string[]; citizenships: string[]; permanent_residency: string[]; work_permits: { country: string; kind?: string; expires?: string }[]; citizenship_known: boolean
  level: 'BACHELOR' | 'MASTER' | 'PHD' | null; degree_name?: string | null; major?: string | null; graduation?: string | null; program_years?: number | null
  year_of_study?: number | null; semester?: number | null; enrolled?: boolean | null; cgpa?: { value: number; scale: number } | null
  experience: { known: boolean; work_years: number; internship_count: number; internship_months: number; none: boolean }
  availability: { start: string; end: string; label?: string }[]; roles: string[]
}
export type VisaRow = { country: string; name?: string | null; authorized: boolean | null; needs_visa: boolean | null; source: 'YOUR_ANSWER' | 'CITIZENSHIP' | null; reason: string; jobs?: number }
export type SourceInfo = { key: string; name: string; about: string; enabled: boolean; jobs: number; status?: { at: string; error?: string | null; found: number; new: number } | null }
export type GitHubProject = { name: string; description: string; skills: string[]; link: string; homepage?: string | null; highlights: string[]; topics: string[]; languages: string[]; stars: number; started?: string | null; updated?: string | null; repo: string; source: 'GITHUB' }
export type GitHubRepo = { repo: string; name: string; description: string; language?: string | null; stars: number; updated: string; link: string; topics: string[] }
export type ExperienceEntry = { title: string; company: string; kind: 'INTERNSHIP' | 'JOB' | 'RESEARCH' | 'VOLUNTEER' | 'PART_TIME'; start: string; end?: string | null; description?: string }
export type Certification = { name: string; issuer?: string; year?: string; link?: string }
