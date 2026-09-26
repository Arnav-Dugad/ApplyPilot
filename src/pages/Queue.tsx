import { useState } from 'react'
import { AlertTriangle, Check, ExternalLink, FileText, ListChecks, MinusCircle, MonitorPlay, Pause, RefreshCw, Send, ShieldCheck, Trash2 } from 'lucide-react'
import { api } from '../api'
import type { Application, Validation } from '../types'
import { ACTIVE_STATUSES, Badge, Empty, PageHeading, STATUS_LABELS, formatValue, statusTone, useAction, type PageProps } from '../ui'

const SOURCE_LABEL: Record<string, string> = { BOARD_FORM: 'Real application form (from the job board)', LIVE_PAGE: 'Read from the live page in Edge', STANDARD_FORM: 'Standard form estimate', CUSTOM: 'Custom form' }

export function Queue({ data, refresh, go, openJob }: PageProps) {
  const { run, busy } = useAction(refresh)
  const [validation, setValidation] = useState<Record<string, Validation>>({})
  const active = data.applications.filter(a => ACTIVE_STATUSES.includes(a.status)).sort((a, b) => (a.status === 'READY_FOR_REVIEW' ? -1 : 0) - (b.status === 'READY_FOR_REVIEW' ? -1 : 0))
  const hasApprovedCV = data.cvs.some(c => c.approved)
  const ready = active.filter(a => a.status === 'READY_FOR_REVIEW').length
  const required = data.inbox.questions.filter(q => q.required)
  const blocked = new Set(required.flatMap(q => q.applications.map(a => a.id))).size

  return <>
    <PageHeading eyebrow="Application queue" title={ready ? `${ready} ready for you to submit` : 'Safe automation workspace'} text="ApplyPilot fills forms from verified facts only, highlights what it can't answer, and never presses submit.">
      <button className="button ghost" disabled={busy === 'all'} onClick={() => run('all', async () => { for (const a of active) await api.prepare(a.id) }, 'All forms re-checked')}><RefreshCw size={15} className={busy === 'all' ? 'spin' : ''} /> Re-check all</button>
      <Badge tone="good"><ShieldCheck size={13} /> Never auto-submits</Badge>
    </PageHeading>
    {!hasApprovedCV && active.length > 0 && <div className="attention banner"><FileText /><div><b>No approved CV yet</b><p>Résumé fields stay paused until a CV is approved. <button className="link" onClick={() => go('CV Library')}>Open CV Library</button></p></div></div>}
    {blocked > 0 && <button className="attention as-button banner" onClick={() => go('Inbox')}><AlertTriangle /><div><b>{required.length} required question{required.length > 1 ? 's' : ''} hold back {blocked} application{blocked > 1 ? 's' : ''}</b><p>Answer them once in your Inbox and every application below updates.</p></div></button>}
    <section className="panel">{active.length ? <div className="queue-list">{active.map((app, i) => <QueueCard key={app.id} app={app} index={i} busy={busy} validation={validation[app.id]}
      onPrepare={() => run(`prep-${app.id}`, () => api.prepare(app.id), r => `${r.filled_count} filled · ${r.blocking_count} need you`)}
      onLive={() => run(`live-${app.id}`, () => api.liveFill(app.id), 'Opening the application in Edge…')}
      onValidate={async () => { const v = await run(`validate-${app.id}`, () => api.validate(app.id)); if (v) setValidation({ ...validation, [app.id]: v }) }}
      onApplied={() => run(`status-${app.id}`, () => api.setStatus(app.id, 'APPLIED'), 'Moved to Tracker as applied')}
      onRemove={() => confirm('Remove this application from the queue?') && run(`remove-${app.id}`, () => api.deleteApplication(app.id), 'Removed from queue')}
      onInbox={() => go('Inbox')} onOpen={() => openJob(app.job_id)} />)}</div>
      : <Empty icon={ListChecks} title="Your queue is empty" text="Turn on Autopilot to fill it automatically, or add jobs from Discover." action={() => go('Autopilot')} actionLabel="Open Autopilot" />}</section>
  </>
}

function QueueCard({ app, index, busy, validation, onPrepare, onLive, onValidate, onApplied, onRemove, onInbox, onOpen }: { app: Application; index: number; busy: string | null; validation?: Validation; onPrepare: () => void; onLive: () => void; onValidate: () => void; onApplied: () => void; onRemove: () => void; onInbox: () => void; onOpen: () => void }) {
  const fields = app.field_state ?? []
  const filled = fields.filter(f => f.decision.action === 'FILL').length
  const blocking = fields.filter(f => f.decision.action === 'PAUSE' && f.required).length
  const progress = fields.length ? Math.round((filled / fields.length) * 100) : 0
  const live = app.browser_run
  const liveRunning = live?.status === 'RUNNING'
  const [open, setOpen] = useState(index === 0)
  return <div className={`queue-card ${app.status === 'READY_FOR_REVIEW' ? 'is-ready' : ''}`} style={{ animationDelay: `${Math.min(index, 8) * 45}ms` }}>
    <div>
      <Badge tone={statusTone(app.status)}>{STATUS_LABELS[app.status] ?? app.status}</Badge>
      <h3><button className="link-title" onClick={onOpen}>{app.role || 'Role'} · {app.company || 'Company'}</button></h3>
      <p>{app.location || 'Location unknown'} · {app.cv_name ? <>CV: {app.cv_name}</> : <span className="warn-text">No approved CV attached</span>}</p>
      {fields.length > 0 && <div className="fill-meter" title={`${filled} of ${fields.length} fields filled`}><i style={{ width: `${progress}%` }} /><span>{filled}/{fields.length} filled{blocking ? ` · ${blocking} need you` : ' · nothing blocking'}</span></div>}
    </div>
    <div className="queue-actions">
      {app.posting_url && <a className="button ghost icon-only" href={app.posting_url} target="_blank" rel="noreferrer" title="Open posting"><ExternalLink size={15} /></a>}
      <button className="button ghost icon-only" title="Remove from queue" onClick={onRemove}><Trash2 size={15} /></button>
      <button className="button ghost" disabled={busy === `prep-${app.id}`} onClick={onPrepare}><RefreshCw size={15} className={busy === `prep-${app.id}` ? 'spin' : ''} /> Check form</button>
      <button className="button ghost" disabled={busy === `validate-${app.id}`} onClick={onValidate}><ShieldCheck size={16} /> Validate</button>
      <button className={`button ${app.status === 'READY_FOR_REVIEW' ? 'primary glow' : 'ghost'}`} disabled={liveRunning || busy === `live-${app.id}`} onClick={onLive} title="Opens the real application in Edge and fills verified answers. You press submit."><MonitorPlay size={16} /> {liveRunning ? 'Filling…' : 'Fill in Edge'}</button>
      <button className="button ghost" disabled={busy === `status-${app.id}`} onClick={onApplied} title="You submitted this application yourself"><Send size={15} /> I applied</button>
    </div>
    {live?.events && live.events.length > 0 && <div className={`live-run ${live.status?.toLowerCase()}`}>{live.events.slice(-4).map((e, i) => <span key={i} className={e.step}>{liveRunning && i === Math.min(3, live.events!.length - 1) ? <span className="mini-spinner" /> : e.step === 'error' ? <AlertTriangle size={13} /> : <Check size={13} />}{e.message}</span>)}</div>}
    {fields.length > 0 && <div className="field-plan">
      <button className="field-plan-head" onClick={() => setOpen(!open)}><b>Form plan</b><span>{SOURCE_LABEL[app.prep_source ?? ''] ?? 'Form check'}</span>{blocking > 0 && <span className="link" onClick={e => { e.stopPropagation(); onInbox() }}>Answer in Inbox →</span>}<em>{open ? 'Hide' : 'Show'}</em></button>
      {open && fields.map((f, i) => <div key={`${f.selector}-${i}`} className={`field-line ${f.decision.action.toLowerCase()}`}>
        {f.decision.action === 'FILL' ? <Check size={14} /> : f.decision.action === 'SKIP' ? <MinusCircle size={14} /> : <Pause size={14} />}
        <span>{f.label}{f.required && <i>*</i>}</span>
        <small>{f.decision.action === 'FILL' ? <><b>{f.decision.upload ? `📎 ${formatValue(f.decision.value)}` : formatValue(f.decision.value)}</b> — {f.decision.source}</> : f.decision.reason}</small>
      </div>)}
    </div>}
    {validation && <div className={`run-result ${validation.blocked ? '' : 'ok'}`}>
      {validation.blocked ? <AlertTriangle size={16} /> : <Check size={16} />}
      <div><b>{validation.blocked ? `Blocked by ${validation.failures.length} check${validation.failures.length > 1 ? 's' : ''}` : 'All checks passed'}</b>
        <ul>{validation.failures.map(f => <li key={f}>{f}</li>)}{validation.warnings.map(w => <li key={w} className="muted">{w}</li>)}</ul></div>
    </div>}
  </div>
}
