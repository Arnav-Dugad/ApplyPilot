import { useEffect, useMemo, useRef, useState } from 'react'
import { ArrowLeft, Building2, ExternalLink, Linkedin, Search, Trash2, Users } from 'lucide-react'
import { api, readFileText } from '../api'
import type { CompanyDetail, CompanySummary } from '../types'
import { ScoreRing, Skeleton } from '../motion'
import { Badge, Empty, PageHeading, STATUS_LABELS, formatDate, statusTone, useAction, useNotify, type PageProps } from '../ui'

const MONTHS = ['J', 'F', 'M', 'A', 'M', 'J', 'J', 'A', 'S', 'O', 'N', 'D']
type Filter = 'ALL' | 'FOLLOWED' | 'APPLIED' | 'PEOPLE'

export function Companies({ data, refresh, openJob }: PageProps) {
  const [list, setList] = useState<CompanySummary[] | null>(null)
  const [selected, setSelected] = useState<string | null>(null)
  const [query, setQuery] = useState('')
  const [filter, setFilter] = useState<Filter>('ALL')
  const notify = useNotify()
  const file = useRef<HTMLInputElement>(null)
  const load = () => api.companies().then(setList).catch(() => setList([]))
  useEffect(() => { load() }, [data.jobs.length, data.watchlist.length, data.connections])

  const importCsv = async (f?: File) => {
    if (!f) return
    try {
      const result = await api.importConnections(await readFileText(f))
      notify(`Imported ${result.connections} connections — you know people at ${result.matched_companies} compan${result.matched_companies === 1 ? 'y' : 'ies'} you're tracking`)
      await refresh(); await load()
    } catch (e) { notify(e instanceof Error ? e.message : 'Import failed', 'bad') }
    if (file.current) file.current.value = ''
  }

  const shown = useMemo(() => (list ?? []).filter(c => (!query || c.name.toLowerCase().includes(query.toLowerCase()))
    && (filter === 'ALL' || (filter === 'FOLLOWED' && c.followed) || (filter === 'APPLIED' && c.applications > 0) || (filter === 'PEOPLE' && c.connections > 0))), [list, query, filter])

  if (selected) return <CompanyPage companyKey={selected} back={() => { setSelected(null); load() }} refresh={refresh} openJob={openJob} />
  return <>
    <PageHeading eyebrow="Companies" title="Everyone you’re tracking" text="Roles, your history, people you know, and your notes — one page per company.">
      <button className="button ghost" onClick={() => file.current?.click()}><Linkedin size={15} /> {data.connections ? `Update connections (${data.connections})` : 'Import LinkedIn connections'}</button>
      <input ref={file} type="file" accept=".csv,text/csv" hidden onChange={e => importCsv(e.target.files?.[0])} />
    </PageHeading>
    {!data.connections && <div className="attention banner info"><Users /><div><b>Find referrals automatically</b><p>On LinkedIn: Settings → Data privacy → Get a copy of your data → Connections. Import the CSV here — it never leaves this computer.</p></div></div>}
    <div className="toolbar"><div className="chips">{([['ALL', 'All'], ['FOLLOWED', 'Following'], ['APPLIED', 'Applied'], ['PEOPLE', 'People you know']] as [Filter, string][]).map(([k, l]) => <button key={k} className={filter === k ? 'active' : ''} onClick={() => setFilter(k)}>{l}</button>)}</div>
      <div className="search-wrap"><Search size={15} /><input className="search-input" value={query} onChange={e => setQuery(e.target.value)} placeholder="Find a company…" /></div></div>
    {list === null ? <Skeleton lines={6} /> : shown.length ? <div className="company-grid stagger">{shown.map(c => <button key={c.key} className="company-card" onClick={() => setSelected(c.key)}>
      <div className="company-mark big">{c.name.slice(0, 1).toUpperCase()}</div>
      <div className="company-card-body"><b>{c.name}</b><span>{c.jobs} role{c.jobs === 1 ? '' : 's'}{c.platform ? ` · ${c.platform.toLowerCase()}` : ''}</span>
        <div className="tags">{c.followed && <Badge tone="good">Following</Badge>}{c.applications > 0 && <Badge tone="accent">{c.applications} applied</Badge>}{c.connections > 0 && <Badge tone="warn"><Users size={10} /> {c.connections}</Badge>}{c.has_notes && <Badge>Notes</Badge>}</div></div>
      <ScoreRing score={c.best_score || null} size={40} />
    </button>)}</div> : <section className="panel"><Empty icon={Building2} title="No companies yet" text="Companies appear as Autopilot finds jobs or you follow them." /></section>}
  </>
}

function CompanyPage({ companyKey, back, refresh, openJob }: { companyKey: string; back: () => void; refresh: () => Promise<void>; openJob: (id: string) => void }) {
  const [company, setCompany] = useState<CompanyDetail | null>(null)
  const [notes, setNotes] = useState('')
  const [saved, setSaved] = useState<'idle' | 'saving' | 'saved'>('idle')
  const { run } = useAction(refresh)
  const timer = useRef<number | undefined>(undefined)
  useEffect(() => { api.company(companyKey).then(c => { setCompany(c); setNotes(c.notes) }) }, [companyKey])
  const onNotes = (value: string) => {
    setNotes(value); setSaved('saving')
    window.clearTimeout(timer.current)
    timer.current = window.setTimeout(() => api.companyNotes(companyKey, company?.name ?? companyKey, value).then(() => setSaved('saved')), 600)
  }
  if (!company) return <><button className="text-button back" onClick={back}><ArrowLeft size={15} /> Companies</button><Skeleton lines={8} /></>
  const peak = Math.max(1, ...company.seasons)
  return <>
    <button className="text-button back" onClick={back}><ArrowLeft size={15} /> Companies</button>
    <header className="company-hero">
      <div className="company-mark huge">{company.name.slice(0, 1).toUpperCase()}</div>
      <div><p className="eyebrow">{company.platform ? `${company.platform.toLowerCase()} board` : 'Company'}</p><h1>{company.name}</h1>
        <span>{company.jobs} open role{company.jobs === 1 ? '' : 's'} · {company.applications} application{company.applications === 1 ? '' : 's'} · {company.people.length} {company.people.length === 1 ? 'person' : 'people'} you know</span></div>
      <div className="hero-actions">{company.followed && company.watch_id ? <button className="button ghost" onClick={async () => { await run('unfollow', () => api.unfollow(company.watch_id!), `Unfollowed ${company.name}`); back() }}><Trash2 size={15} /> Unfollow</button> : null}</div>
    </header>
    <div className="company-layout">
      <div className="stack">
        <section className="panel"><div className="panel-head"><div><h2>Roles</h2><p>Every posting ApplyPilot has seen here</p></div></div>
          {company.roles.length ? <div className="role-list">{company.roles.map(r => { const score = (() => { try { return JSON.parse(r.score_json || '{}').score as number } catch { return undefined } })()
            return <button key={r.id} className={`role-row ${r.duplicate_of ? 'dup' : ''}`} onClick={() => openJob(r.id)}><ScoreRing score={score ?? null} size={34} /><div><b>{r.role}</b><span>{r.location || 'Location not stated'} · found {formatDate(r.date_found)}{r.duplicate_of ? ' · duplicate' : ''}</span></div>{r.deadline && <Badge tone="warn">Closes {formatDate(r.deadline)}</Badge>}</button> })}</div>
            : <p className="muted small">No roles yet.</p>}
        </section>
        {company.application_history.length > 0 && <section className="panel"><div className="panel-head"><div><h2>Your history</h2><p>Applications to {company.name}</p></div></div>
          <div className="history">{company.application_history.map(a => <div key={a.id} className="history-row"><Badge tone={statusTone(a.status)}>{STATUS_LABELS[a.status] ?? a.status}</Badge><b>{a.role}</b><span>{a.submitted_at ? `Applied ${formatDate(a.submitted_at)}` : `Updated ${formatDate(a.updated_at)}`}</span></div>)}</div></section>}
      </div>
      <div className="stack">
        <section className="panel"><div className="panel-head"><div><h2>Hiring season</h2><p>When postings appeared, by month</p></div></div>
          <div className="season-bars">{company.seasons.map((n, i) => <div key={i} title={`${n} posting${n === 1 ? '' : 's'}`}><i style={{ height: `${(n / peak) * 100}%` }} className={n ? '' : 'empty'} /><span>{MONTHS[i]}</span></div>)}</div>
          <small className="muted">Based on the postings ApplyPilot has seen so far.</small></section>
        <section className="panel"><div className="panel-head"><div><h2>People you know</h2><p>From your LinkedIn connections</p></div></div>
          {company.people.length ? <div className="people">{company.people.map(p => <div key={p.id} className="person"><div className="avatar">{(p.first_name[0] ?? '') + (p.last_name[0] ?? '')}</div><div><b>{p.first_name} {p.last_name}</b><span>{p.position}</span></div>{p.url && <a href={p.url} target="_blank" rel="noreferrer" className="icon-button" aria-label="LinkedIn profile"><ExternalLink /></a>}</div>)}</div>
            : <p className="muted small">No connections here yet. Import your LinkedIn connections from the Companies page.</p>}</section>
        <section className="panel"><div className="panel-head"><div><h2>Notes</h2><p>{saved === 'saving' ? 'Saving…' : saved === 'saved' ? 'Saved' : 'Private to you — used in interview prep'}</p></div></div>
          <textarea className="notes" value={notes} onChange={e => onNotes(e.target.value)} placeholder="What you learned, people you spoke to, why you're excited…" /></section>
      </div>
    </div>
  </>
}

