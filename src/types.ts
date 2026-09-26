export type FactStatus = 'VERIFIED' | 'UNVERIFIED' | 'UNKNOWN' | 'EXPIRED'
export type Fact = { id?: string; category: string; fact_key: string; country_code?: string | null; value?: unknown; status: FactStatus; source: string; last_confirmed?: string | null; notes?: string; revision?: number }
export type EligibilityResult = 'ELIGIBLE' | 'LIKELY_ELIGIBLE' | 'NEEDS_INFORMATION' | 'INELIGIBLE'
export type Check = { name: string; result: 'PASS' | 'FAIL' | 'UNKNOWN' | 'PARTIAL' | string; explanation: string }
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
}
export type FieldDecision = { action: 'FILL' | 'PAUSE' | 'SKIP'; value?: unknown; source?: string | null; reason: string; upload?: boolean }
export type FieldResult = { selector: string; label: string; required: boolean; classification: string; options?: string[]; decision: FieldDecision }
export type BrowserRun = { status?: 'RUNNING' | 'DONE' | 'FAILED'; events?: { at: string; step: string; message: string }[]; filled?: number; paused?: number }
export type Application = {
  id: string; job_id: string; company?: string | null; role?: string | null; location?: string | null; country?: string | null; posting_url?: string | null; application_url?: string | null
  status: string; dry_run: boolean; mode: string; cv_id?: string | null; cv_name?: string | null; prep_source?: string | null
  field_state?: FieldResult[]; browser_run?: BrowserRun; created_at: string; updated_at: string; submitted_at?: string | null
}
export type CV = {
  id: string; name: string; variant: string; version: number; sha256: string; approved: boolean; created_at: string
  extracted_profile?: { notice?: string; email_candidates?: string[]; skill_candidates?: string[]; text_length?: number; extraction_error?: string }
}
export type Answer = { id: string; canonical_question: string; answer_type: string; answer?: unknown; country_code?: string | null; company?: string | null; role_pattern?: string | null; status: FactStatus; updated_at: string }
export type Activity = { id: number; timestamp: string; action: string; level: string; entity_type?: string | null; details?: Record<string, unknown> }
export type Validation = { valid: boolean; blocked: boolean; failures: string[]; warnings: string[] }
export type Watch = { id: string; platform: string; slug: string; company: string; created_at: string; last_scanned_at?: string | null; last_status?: string | null; jobs_seen: number; internships_seen: number }
export type CatalogEntry = { platform: string; slug: string; company: string }
export type RunEvent = { at: string; step: string; message: string; level: string; company?: string; job_id?: string }
export type RunSummary = { boards: number; found: number; new: number; filtered: number; analyzed: number; queued: number; prepared: number; ready: number; needs_you: number; summaries: number; letters: number }
export type AutopilotRun = { id: string; trigger: string; status: 'RUNNING' | 'COMPLETED' | 'FAILED'; started_at: string; finished_at?: string | null; summary: Partial<RunSummary>; events: RunEvent[] }
export type AutopilotConfig = { enabled: boolean; interval_hours: number; min_score: number; auto_queue: boolean; auto_prepare: boolean; location_filter: boolean; internships_only: boolean; ai_summaries: boolean; ai_cover_letters: boolean }
export type AutopilotState = { config: AutopilotConfig; running: string | null; next_run_at: string | null; runs: AutopilotRun[] }
export type InboxQuestion = { key: string; question: string; classification: string; kind: 'FACT' | 'COUNTRY_FACT' | 'ANSWER' | 'RESUME' | 'COVER_LETTER' | 'CREDENTIAL'; options: string[]; required: boolean; reason: string; country?: string | null; applications: { id: string; job_id: string; company?: string; role?: string }[] }
export type Suggestion = { id: string; source: string; category: string; fact_key: string; value: unknown; confidence: number; evidence: string; created_at: string }
export type Draft = { id: string; kind: 'COVER_LETTER' | 'ANSWER' | 'SUMMARY'; job_id?: string | null; question?: string | null; content: string; status: 'DRAFT' | 'APPROVED'; model?: string | null; company?: string | null; role?: string | null; updated_at: string; unverified_skills?: string[] }
export type Inbox = { questions: InboxQuestion[]; suggestions: Suggestion[]; drafts: Draft[] }
export type Notification = { id: number; created_at: string; kind: string; title: string; body: string; page?: string | null; read: number }
export type AIStatus = { available: boolean; enabled: boolean; endpoint: string; version?: string; models: string[]; model?: string | null; recommended: { name: string; size: string; note: string }[]; pull: { status: string; model?: string; completed?: number; total?: number; detail?: string } }
export type JobDetail = Job & { board_questions?: { label: string; required: boolean; field_type: string; options: string[] }[]; drafts: Draft[]; application?: { id: string; status: string } | null }
export type Bootstrap = {
  version?: string; settings: Record<string, unknown>; facts: Fact[]; jobs: Job[]; applications: Application[]; activity: Activity[]; cvs: CV[]; answers: Answer[]
  watchlist: Watch[]; catalog: CatalogEntry[]; inbox: Inbox; autopilot: AutopilotState; notifications: Notification[]
}
