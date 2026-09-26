export type FactStatus = 'VERIFIED' | 'UNVERIFIED' | 'UNKNOWN' | 'EXPIRED'
export type Fact = { id?: string; category: string; fact_key: string; country_code?: string | null; value?: unknown; status: FactStatus; source: string; last_confirmed?: string | null; notes?: string; revision?: number }
export type EligibilityResult = 'ELIGIBLE' | 'LIKELY_ELIGIBLE' | 'NEEDS_INFORMATION' | 'INELIGIBLE'
export type Check = { name: string; result: 'PASS' | 'FAIL' | 'UNKNOWN' | 'PARTIAL' | string; explanation: string }
export type Match = { strong: string[]; partial: string[]; missing: string[]; required_coverage?: number | null }
export type Analysis = { result: EligibilityResult; checks: Check[]; match: Match }
export type Job = {
  id: string; company?: string | null; role?: string | null; location?: string | null; country?: string | null; remote_status?: string | null
  description: string; required_skills: string[]; preferred_skills: string[]; posting_url?: string | null; application_url?: string | null
  application_platform?: string | null; extraction_status: string; date_found: string; source?: string
  work_authorization?: string | null; sponsorship_information?: string | null
  eligibility_result?: EligibilityResult | null; eligibility_checks?: Check[]; eligibility_match?: Match
}
export type FieldResult = { selector: string; label: string; required: boolean; classification: string; decision: { action: 'FILL' | 'PAUSE'; value?: unknown; source?: string | null; reason: string } }
export type Application = {
  id: string; job_id: string; company?: string | null; role?: string | null; location?: string | null; country?: string | null; posting_url?: string | null
  status: string; dry_run: boolean; mode: string; cv_id?: string | null; cv_name?: string | null
  field_state?: FieldResult[]; created_at: string; updated_at: string; submitted_at?: string | null
}
export type CV = {
  id: string; name: string; variant: string; version: number; sha256: string; approved: boolean; created_at: string
  extracted_profile?: { notice?: string; email_candidates?: string[]; skill_candidates?: string[]; text_length?: number; extraction_error?: string }
}
export type Answer = { id: string; canonical_question: string; answer_type: string; answer?: unknown; country_code?: string | null; company?: string | null; role_pattern?: string | null; status: FactStatus; updated_at: string }
export type Activity = { id: number; timestamp: string; action: string; level: string; entity_type?: string | null; details?: Record<string, unknown> }
export type Validation = { valid: boolean; blocked: boolean; failures: string[]; warnings: string[] }
export type Bootstrap = { version?: string; settings: Record<string, unknown>; facts: Fact[]; jobs: Job[]; applications: Application[]; activity: Activity[]; cvs: CV[]; answers: Answer[] }
