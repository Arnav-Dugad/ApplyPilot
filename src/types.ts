export type FactStatus = 'VERIFIED' | 'UNVERIFIED' | 'UNKNOWN' | 'EXPIRED'
export type Fact = { id?: string; category: string; fact_key: string; country_code?: string | null; value?: unknown; status: FactStatus; source: string; last_confirmed?: string; notes?: string }
export type Job = { id: string; company?: string; role?: string; location?: string; country?: string; description: string; required_skills: string[]; preferred_skills: string[]; posting_url?: string; application_platform?: string; extraction_status: string; date_found: string }
export type Application = { id: string; job_id: string; company?: string; role?: string; location?: string; status: string; dry_run: boolean; mode: string; field_state?: FieldResult[] }
export type FieldResult = { selector: string; label: string; required: boolean; classification: string; decision: { action: 'FILL' | 'PAUSE'; value?: unknown; source?: string; reason: string } }
export type Activity = { id: number; timestamp: string; action: string; level: string; details?: Record<string, unknown> }
export type Bootstrap = { settings: Record<string, unknown>; facts: Fact[]; jobs: Job[]; applications: Application[]; activity: Activity[]; cvs: unknown[]; answers: unknown[] }

