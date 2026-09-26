import { createContext, useContext, useState, type ReactNode } from 'react'
import { Activity as ActivityIcon, BriefcaseBusiness, ChevronRight, Sparkles } from 'lucide-react'
import { ScoreRing } from './motion'
import type { Activity, Bootstrap, EligibilityResult, Job } from './types'

export type Page = 'Home' | 'Autopilot' | 'Inbox' | 'Discover' | 'Queue' | 'Tracker' | 'CV Library' | 'Profile' | 'Answer Vault' | 'Analytics' | 'Activity' | 'Settings'
export type PageProps = { data: Bootstrap; refresh: () => Promise<void>; go: (page: Page) => void; openJob: (id: string) => void }
export type Tone = 'good' | 'warn' | 'bad' | 'accent' | 'neutral'

export function Badge({ children, tone = 'neutral' }: { children: ReactNode; tone?: Tone }) {
  return <span className={`badge ${tone}`}>{children}</span>
}

export function Stat({ label, value, hint = 'Live local data', accent }: { label: string; value: number | string; hint?: string; accent?: boolean }) {
  return <div className={`stat ${accent ? 'stat-accent' : ''}`}><span>{label}</span><strong>{value}</strong><small>{hint}</small></div>
}

export function Logo() { return <div className="logo"><span><Sparkles size={18} /></span><b>ApplyPilot</b></div> }

export function PageHeading({ eyebrow, title, text, children }: { eyebrow: string; title: string; text: string; children?: ReactNode }) {
  return <header className="page-heading"><div><p>{eyebrow}</p><h1>{title}</h1><span>{text}</span></div>{children && <div className="heading-actions">{children}</div>}</header>
}

export function Empty({ icon: Icon, title, text, action, actionLabel = 'Get started' }: { icon: typeof BriefcaseBusiness; title: string; text: string; action?: () => void; actionLabel?: string }) {
  return <div className="empty"><Icon /><b>{title}</b><span>{text}</span>{action && <button className="button subtle" onClick={action}>{actionLabel}</button>}</div>
}

export function JobRow({ job, onClick }: { job: Job; onClick?: () => void }) {
  return <div className={`job-row ${onClick ? 'clickable' : ''}`} onClick={onClick}>
    <ScoreRing score={job.score?.score} size={38} />
    <div><b>{job.role || 'Role needs review'}</b><span>{job.company || 'Company unknown'} · {job.location || 'Location unknown'}</span></div>
    <div className="tags">{job.eligibility_result ? <Badge tone={eligibilityTone(job.eligibility_result)}>{eligibilityLabel(job.eligibility_result)}</Badge> : <Badge>Not analyzed</Badge>}<Badge tone="accent">{job.application_platform || 'GENERIC'}</Badge></div>
    <ChevronRight size={18} />
  </div>
}

export function ActivityList({ items, detailed }: { items: Activity[]; detailed?: boolean }) {
  if (!items.length) return <div className="activity-list"><Empty icon={ActivityIcon} title="No activity yet" text="Every important automated action will appear here." /></div>
  return <div className={`activity-list ${detailed ? 'detailed' : ''}`}>{items.map(item => <div key={item.id}>
    <span className={`activity-dot ${item.level.toLowerCase()}`} />
    <time title={new Date(item.timestamp).toLocaleString()}>{detailed ? formatDateTime(item.timestamp) : formatTime(item.timestamp)}</time>
    <b>{item.action.replaceAll('_', ' ').toLowerCase()}</b>
    {detailed && <small>{summarizeDetails(item.details)}</small>}
  </div>)}</div>
}

const ELIGIBILITY: Record<EligibilityResult, [string, Tone, number]> = {
  ELIGIBLE: ['Eligible', 'good', 0], LIKELY_ELIGIBLE: ['Likely eligible', 'good', 1], NEEDS_INFORMATION: ['Needs info', 'warn', 2], INELIGIBLE: ['Ineligible', 'bad', 4],
}
export const eligibilityLabel = (r?: EligibilityResult | null) => r ? ELIGIBILITY[r]?.[0] ?? r : 'Not analyzed'
export const eligibilityTone = (r?: EligibilityResult | null): Tone => r ? ELIGIBILITY[r]?.[1] ?? 'neutral' : 'neutral'
export const eligibilityRank = (job: Job) => (job.eligibility_result ? ELIGIBILITY[job.eligibility_result]?.[2] ?? 3 : 3) - (job.score?.score ?? job.eligibility_match?.required_coverage ?? 0) / 1000

export const STATUS_LABELS: Record<string, string> = {
  QUEUED: 'Queued', NEEDS_INFO: 'Needs info', WAITING_FOR_USER: 'Waiting for you', READY_FOR_REVIEW: 'Ready for review',
  APPLIED: 'Applied', SUBMITTED: 'Applied', INTERVIEWING: 'Interviewing', OFFER: 'Offer', REJECTED: 'Rejected', WITHDRAWN: 'Withdrawn',
}
export const ACTIVE_STATUSES = ['QUEUED', 'NEEDS_INFO', 'WAITING_FOR_USER', 'READY_FOR_REVIEW']
export const statusTone = (status: string): Tone =>
  status === 'OFFER' || status === 'READY_FOR_REVIEW' ? 'good' : status === 'WAITING_FOR_USER' || status === 'NEEDS_INFO' ? 'warn' : status === 'REJECTED' ? 'bad' : status === 'WITHDRAWN' ? 'neutral' : 'accent'

export function formatValue(value: unknown): string {
  if (value === null || value === undefined || value === '') return 'Not provided'
  if (typeof value === 'boolean') return value ? 'Yes' : 'No'
  if (Array.isArray(value)) return value.join(', ')
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}
export const formatTime = (iso: string) => new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
export const formatDate = (iso?: string | null) => iso ? new Date(iso).toLocaleDateString([], { day: 'numeric', month: 'short', year: 'numeric' }) : '—'
export const formatDateTime = (iso: string) => new Date(iso).toLocaleString([], { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })

function summarizeDetails(details?: Record<string, unknown>) {
  if (!details) return ''
  return Object.entries(details).filter(([, v]) => v !== null && v !== undefined && typeof v !== 'object').map(([k, v]) => `${k.replaceAll('_', ' ')}: ${v}`).join(' · ')
}

type Toast = { id: number; message: string; tone: Tone }
const NotifyContext = createContext<(message: string, tone?: Tone) => void>(() => undefined)
export const useNotify = () => useContext(NotifyContext)

export function NotifyProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])
  const notify = (message: string, tone: Tone = 'good') => {
    const id = Date.now() + Math.random()
    setToasts(current => [...current.slice(-3), { id, message, tone }])
    setTimeout(() => setToasts(current => current.filter(t => t.id !== id)), tone === 'bad' ? 7000 : 3500)
  }
  return <NotifyContext.Provider value={notify}>{children}<div className="toasts" role="status">{toasts.map(t => <div key={t.id} className={`toast ${t.tone}`}>{t.message}</div>)}</div></NotifyContext.Provider>
}

/** Runs an API action, refreshes data, and reports the outcome as a toast. */
export function useAction(refresh: () => Promise<void>) {
  const notify = useNotify()
  const [busy, setBusy] = useState<string | null>(null)
  const run = async <T,>(key: string, action: () => Promise<T>, success?: string | ((value: T) => string)): Promise<T | undefined> => {
    setBusy(key)
    try {
      const value = await action()
      await refresh()
      if (success) notify(typeof success === 'function' ? success(value) : success)
      return value
    } catch (e) {
      notify(e instanceof Error ? e.message : 'Something went wrong', 'bad')
      return undefined
    } finally {
      setBusy(null)
    }
  }
  return { run, busy }
}

export function relativeTime(iso: string) {
  const diff = (new Date(iso).getTime() - Date.now()) / 1000
  const abs = Math.abs(diff)
  const [value, unit] = abs < 45 ? [0, 'second'] : abs < 3600 ? [Math.round(diff / 60), 'minute'] : abs < 86400 ? [Math.round(diff / 3600), 'hour'] : [Math.round(diff / 86400), 'day']
  if (unit === 'second') return diff >= 0 ? 'in a moment' : 'just now'
  return new Intl.RelativeTimeFormat([], { numeric: 'auto' }).format(value, unit as Intl.RelativeTimeFormatUnit)
}
