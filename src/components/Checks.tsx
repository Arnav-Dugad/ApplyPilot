import { AlertTriangle, Check as CheckIcon, CircleHelp, Plane, X } from 'lucide-react'
import type { Check, JobTag } from '../types'

const LOOK: Record<string, [string, string, typeof CheckIcon]> = {
  PASS: ['ok', 'Fine', CheckIcon], FAIL: ['bad', 'Rules you out', X], UNKNOWN: ['ask', 'Needs your answer', CircleHelp],
  WARN: ['warn', 'Worth checking', AlertTriangle], PARTIAL: ['warn', 'Partly', AlertTriangle], VISA: ['visa', 'Needs a visa', Plane],
}
const ORDER = ['FAIL', 'UNKNOWN', 'VISA', 'WARN', 'PARTIAL', 'PASS']

/** Every requirement the posting has, in plain words, with the sentence it came from. Problems first. */
export function CheckList({ checks, compact }: { checks: Check[]; compact?: boolean }) {
  const sorted = [...checks].sort((a, b) => ORDER.indexOf(a.result) - ORDER.indexOf(b.result))
  return <ul className={`check-list ${compact ? 'compact' : ''}`}>{sorted.map(c => { const [cls, label, Icon] = LOOK[c.result] ?? ['warn', c.result, AlertTriangle]
    return <li key={c.name} className={cls}><span className="check-icon" title={label}><Icon size={13} /></span><div><b>{c.name}</b><span>{c.explanation}</span>{!compact && c.evidence && <q>{c.evidence}</q>}</div></li> })}</ul>
}

export function Tags({ tags, limit = 6 }: { tags?: JobTag[]; limit?: number }) {
  if (!tags?.length) return null
  return <div className="req-tags">{tags.slice(0, limit).map(t => <span key={t.label} className={`req-tag ${t.tone}`}>{t.label}</span>)}</div>
}
