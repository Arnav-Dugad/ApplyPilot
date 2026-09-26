import { useState } from 'react'
import { AlertTriangle, Check, ExternalLink, FileText, ListChecks, Pause, Play, Send, ShieldCheck, Trash2 } from 'lucide-react'
import { api } from '../api'
import type { Application, Validation } from '../types'
import { ACTIVE_STATUSES, Badge, Empty, PageHeading, STATUS_LABELS, formatValue, statusTone, useAction, type PageProps } from '../ui'

// A representative application form used for the dry run until live ATS adapters are enabled.
const SAMPLE_FORM = [
  { selector: '#name', label: 'Full legal name', required: true },
  { selector: '#email', label: 'Email address', required: true },
  { selector: '#phone', label: 'Phone number', required: false },
  { selector: '#university', label: 'University', required: true },
  { selector: '#graduation', label: 'Expected graduation date', required: true },
  { selector: '#auth', label: 'Are you legally authorized to work in this country?', required: true },
  { selector: '#sponsor', label: 'Will you now or in the future require sponsorship?', required: true },
  { selector: '#why', label: 'Why do you want to work here?', required: false },
  { selector: '#legal', label: 'I agree to the legal declarations', required: true },
]

export function Queue({ data, refresh, go }: PageProps) {
  const { run, busy } = useAction(refresh)
  const [validation, setValidation] = useState<Record<string, Validation>>({})
  const active = data.applications.filter(a => ACTIVE_STATUSES.includes(a.status))
  const hasApprovedCV = data.cvs.some(c => c.approved)

  return <>
    <PageHeading eyebrow="Application queue" title="Safe automation workspace" text="Dry Run fills a sample form from verified facts only and never presses submit.">
      <Badge tone="good"><ShieldCheck size={13} /> {data.settings.dry_run ? 'DRY RUN' : 'LIVE CHECKS'}</Badge>
    </PageHeading>
    {!hasApprovedCV && active.length > 0 && <div className="attention banner"><FileText /><div><b>No approved CV yet</b><p>Validation blocks every application until a CV is approved. <button className="link" onClick={() => go('CV Library')}>Open CV Library</button></p></div></div>}
    <section className="panel">{active.length ? <div className="queue-list">{active.map(app => <QueueCard key={app.id} app={app} busy={busy} validation={validation[app.id]}
      onRun={() => run(`run-${app.id}`, () => api.dryRun(app.id, SAMPLE_FORM), r => `${r.filled_count} filled · ${r.unknown_count} paused`)}
      onValidate={async () => { const v = await run(`validate-${app.id}`, () => api.validate(app.id)); if (v) setValidation({ ...validation, [app.id]: v }) }}
      onApplied={() => run(`status-${app.id}`, () => api.setStatus(app.id, 'APPLIED'), 'Moved to Tracker as applied')}
      onRemove={() => confirm('Remove this application from the queue?') && run(`remove-${app.id}`, () => api.deleteApplication(app.id), 'Removed from queue')}
      onFix={() => go('Profile')} />)}</div>
      : <Empty icon={ListChecks} title="Your queue is empty" text="Analyze a job in Discover, then add it here for a controlled dry run." action={() => go('Discover')} actionLabel="Find jobs" />}</section>
  </>
}

function QueueCard({ app, busy, validation, onRun, onValidate, onApplied, onRemove, onFix }: { app: Application; busy: string | null; validation?: Validation; onRun: () => void; onValidate: () => void; onApplied: () => void; onRemove: () => void; onFix: () => void }) {
  const fields = app.field_state ?? []
  const paused = fields.filter(f => f.decision.action === 'PAUSE')
  return <div className="queue-card">
    <div>
      <Badge tone={statusTone(app.status)}>{STATUS_LABELS[app.status] ?? app.status}</Badge>
      <h3>{app.role || 'Role'} · {app.company || 'Company'}</h3>
      <p>{app.location || 'Location unknown'} · {app.mode.replaceAll('_', ' ').toLowerCase()} · {app.cv_name ? <>CV: {app.cv_name}</> : <span className="warn-text">No approved CV attached</span>}</p>
    </div>
    <div className="queue-actions">
      {app.posting_url && <a className="button ghost icon-only" href={app.posting_url} target="_blank" rel="noreferrer" title="Open posting"><ExternalLink size={15} /></a>}
      <button className="button ghost icon-only" title="Remove from queue" onClick={onRemove}><Trash2 size={15} /></button>
      <button className="button ghost" disabled={busy === `run-${app.id}`} onClick={onRun}><Play size={16} /> {fields.length ? 'Re-run' : 'Run'} safe fill</button>
      <button className="button ghost" disabled={busy === `validate-${app.id}`} onClick={onValidate}><ShieldCheck size={16} /> Validate</button>
      <button className="button primary" disabled={busy === `status-${app.id}`} onClick={onApplied} title="You submitted this application yourself"><Send size={15} /> Mark as applied</button>
    </div>
    {fields.length > 0 && <div className="field-plan">
      <div className="field-plan-head"><b>Dry-run plan</b><span>{fields.length - paused.length} filled from verified facts · {paused.length} paused</span>{paused.length > 0 && <button className="link" onClick={onFix}>Add missing facts</button>}</div>
      {fields.map(f => <div key={f.selector} className={`field-line ${f.decision.action.toLowerCase()}`}>
        {f.decision.action === 'FILL' ? <Check size={14} /> : <Pause size={14} />}
        <span>{f.label}{f.required && <i>*</i>}</span>
        <small>{f.decision.action === 'FILL' ? <><b>{formatValue(f.decision.value)}</b> — {f.decision.source}</> : f.decision.reason}</small>
      </div>)}
    </div>}
    {validation && <div className={`run-result ${validation.blocked ? '' : 'ok'}`}>
      {validation.blocked ? <AlertTriangle size={16} /> : <Check size={16} />}
      <div><b>{validation.blocked ? `Blocked by ${validation.failures.length} check${validation.failures.length > 1 ? 's' : ''}` : 'All checks passed'}</b>
        <ul>{validation.failures.map(f => <li key={f}>{f}</li>)}{validation.warnings.map(w => <li key={w} className="muted">{w}</li>)}</ul></div>
    </div>}
  </div>
}
