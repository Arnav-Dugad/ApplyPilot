import { ExternalLink, Gauge, GraduationCap, HandCoins, Mail, Undo2 } from 'lucide-react'
import { api } from '../api'
import { burstConfetti } from '../motion'
import type { Application } from '../types'
import { ACTIVE_STATUSES, Empty, PageHeading, STATUS_LABELS, formatDate, useAction, type PageProps } from '../ui'

const COLUMNS: [string, string[]][] = [
  ['In progress', ACTIVE_STATUSES],
  ['Applied', ['APPLIED', 'SUBMITTED']],
  ['Interviewing', ['INTERVIEWING']],
  ['Offer', ['OFFER']],
  ['Closed', ['REJECTED', 'WITHDRAWN']],
]
const MOVES = ['QUEUED', 'APPLIED', 'INTERVIEWING', 'OFFER', 'REJECTED', 'WITHDRAWN']

export function Tracker({ data, refresh, go, openJob }: PageProps) {
  const { run } = useAction(refresh)
  const move = async (app: Application, status: string) => {
    const done = await run(`move-${app.id}`, () => api.setStatus(app.id, status), status === 'OFFER' ? `An offer from ${app.company || 'them'} — congratulations!` : `${app.company || 'Application'} → ${STATUS_LABELS[status]}`)
    if (done && status === 'OFFER') burstConfetti()
  }
  return <>
    <PageHeading eyebrow="My applications" title="Every application, from sent to offer" text="Move a card when you hear back. If you connect your email in Settings, ApplyPilot can move them for you." />
    {data.applications.length ? <div className="board">{COLUMNS.map(([title, statuses]) => {
      const apps = data.applications.filter(a => statuses.includes(a.status))
      return <section key={title} className="board-column"><header><b>{title}</b><em>{apps.length}</em></header>
        {apps.map(app => <article key={app.id} className={`board-card ${app.status === 'OFFER' ? 'offer' : ''}`}>
          <button className="link-title" onClick={() => openJob(app.job_id)}><b>{app.role || 'Role'}</b></button>
          <span>{app.company || 'Company'}{app.location ? ` · ${app.location}` : ''}</span>
          <small>{app.submitted_at ? `Applied ${formatDate(app.submitted_at)}` : `Updated ${formatDate(app.updated_at)}`}</small>
          {app.status_note && <div className="email-note"><Mail size={12} /><span>{app.status_note}</span>{app.email_event_id && <button onClick={() => run(`undo-${app.id}`, () => api.undoEmail(app.email_event_id!), 'Moved back')} title="Undo this automatic move"><Undo2 size={12} /> Undo</button>}</div>}
          {app.status === 'INTERVIEWING' && <button className="card-cta" onClick={() => openJob(app.job_id)}><GraduationCap size={13} /> Interview prep</button>}
          {app.status === 'OFFER' && !(data.offers?.rows ?? []).some(o => o.company.toLowerCase() === (app.company ?? '').toLowerCase()) && <button className="card-cta gold" onClick={() => go('Offers')}><HandCoins size={13} /> Add offer details</button>}
          <footer>
            <select value={MOVES.includes(app.status) ? app.status : ''} onChange={e => move(app, e.target.value)} aria-label="Move application">
              {!MOVES.includes(app.status) && <option value="">{STATUS_LABELS[app.status] ?? app.status}</option>}
              {MOVES.map(s => <option key={s} value={s}>{STATUS_LABELS[s]}</option>)}
            </select>
            {app.posting_url && <a href={app.posting_url} target="_blank" rel="noreferrer" title="Open posting"><ExternalLink size={14} /></a>}
          </footer>
        </article>)}
        {!apps.length && <p className="board-empty">Nothing here yet</p>}
      </section>
    })}</div> : <section className="panel"><Empty icon={Gauge} title="Nothing to track yet" text="Once you apply to a job, press “I applied” and it shows up here." action={() => go('Discover')} actionLabel="Find jobs" /></section>}
  </>
}
