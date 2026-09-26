import { useMemo, useState } from 'react'
import { ExternalLink, PenLine, RefreshCw, Search, Trash2, X } from 'lucide-react'
import { api } from '../api'
import type { EligibilityResult, Job } from '../types'
import { Badge, Empty, JobRow, PageHeading, eligibilityLabel, eligibilityRank, eligibilityTone, useAction, type PageProps } from '../ui'

type Filter = 'ALL' | EligibilityResult | 'UNANALYZED'
const FILTERS: [Filter, string][] = [['ALL', 'All'], ['ELIGIBLE', 'Eligible'], ['LIKELY_ELIGIBLE', 'Likely'], ['NEEDS_INFORMATION', 'Needs info'], ['INELIGIBLE', 'Ineligible'], ['UNANALYZED', 'Not analyzed']]
const blankJob = { company: '', role: '', location: '', country: '', posting_url: '', description: '' }

export function Discover({ data, refresh, go }: PageProps) {
  const { run, busy } = useAction(refresh)
  const [url, setUrl] = useState('')
  const [manual, setManual] = useState<typeof blankJob | null>(null)
  const [filter, setFilter] = useState<Filter>('ALL')
  const [query, setQuery] = useState('')
  const queued = useMemo(() => new Set(data.applications.map(a => a.job_id)), [data.applications])

  const jobs = useMemo(() => data.jobs
    .filter(j => filter === 'ALL' || (filter === 'UNANALYZED' ? !j.eligibility_result : j.eligibility_result === filter))
    .filter(j => !query || `${j.company} ${j.role} ${j.location} ${j.required_skills.join(' ')}`.toLowerCase().includes(query.toLowerCase()))
    .sort((a, b) => eligibilityRank(a) - eligibilityRank(b)), [data.jobs, filter, query])

  const importJob = async () => {
    const job = await run('import', () => api.importJob(url.trim()), j => `Imported ${j.role || 'job'}${j.company ? ` at ${j.company}` : ''}`)
    if (job) { setUrl(''); await run(`analyze-${job.id}`, () => api.analyzeJob(job.id)) }
    else setManual({ ...blankJob, posting_url: url.trim() })
  }
  const saveManual = async () => {
    if (!manual) return
    const job = await run('manual', () => api.manualJob(manual), 'Job added')
    if (job) { setManual(null); setUrl(''); await run(`analyze-${job.id}`, () => api.analyzeJob(job.id)) }
  }
  const analyzeAll = () => run('analyze-all', async () => { for (const job of data.jobs) await api.analyzeJob(job.id) }, `Analyzed ${data.jobs.length} jobs against your verified profile`)

  return <>
    <PageHeading eyebrow="Discovery" title="Find a role worth applying to" text="Public pages only. Blocked or protected pages fall back to manual entry.">
      <button className="button ghost" onClick={() => setManual(manual ? null : { ...blankJob })}><PenLine size={16} /> Add manually</button>
      {data.jobs.length > 0 && <button className="button ghost" disabled={busy === 'analyze-all'} onClick={analyzeAll}><RefreshCw size={16} className={busy === 'analyze-all' ? 'spin' : ''} /> Re-analyze all</button>}
    </PageHeading>
    <section className="import-bar"><Search /><input value={url} onChange={e => setUrl(e.target.value)} placeholder="Paste an internship URL (Greenhouse, Lever, Workday, Ashby, company careers page…)" onKeyDown={e => e.key === 'Enter' && url.trim() && importJob()} /><button className="button primary" disabled={!url.trim() || busy === 'import'} onClick={importJob}>{busy === 'import' ? 'Importing…' : 'Import & analyze'}</button></section>

    {manual && <section className="panel form-panel"><div className="panel-head"><div><h2>Add a job manually</h2><p>Only what you enter is stored. Skills are detected from the description you paste.</p></div><button className="icon-button" onClick={() => setManual(null)} aria-label="Close"><X /></button></div>
      <div className="form-grid">
        <label>Company *<input value={manual.company} onChange={e => setManual({ ...manual, company: e.target.value })} autoFocus /></label>
        <label>Role *<input value={manual.role} onChange={e => setManual({ ...manual, role: e.target.value })} /></label>
        <label>Location<input value={manual.location} onChange={e => setManual({ ...manual, location: e.target.value })} placeholder="Dubai" /></label>
        <label>Country<input value={manual.country} onChange={e => setManual({ ...manual, country: e.target.value })} placeholder="United Arab Emirates" /></label>
        <label className="span-2">Posting URL<input value={manual.posting_url} onChange={e => setManual({ ...manual, posting_url: e.target.value })} placeholder="https://" /></label>
        <label className="span-2">Description<textarea value={manual.description} onChange={e => setManual({ ...manual, description: e.target.value })} placeholder="Paste the job description, including requirements and any sponsorship wording." /></label>
      </div>
      <div className="form-actions"><button className="button ghost" onClick={() => setManual(null)}>Cancel</button><button className="button primary" disabled={!manual.company.trim() || !manual.role.trim() || busy === 'manual'} onClick={saveManual}>Save & analyze</button></div>
    </section>}

    <section className="panel"><div className="panel-head"><div><h2>Imported internships</h2><p>Extracted facts remain unverified until reviewed.</p></div><Badge>{data.jobs.length} total</Badge></div>
      {data.jobs.length > 0 && <div className="toolbar"><div className="chips">{FILTERS.map(([key, label]) => <button key={key} className={filter === key ? 'active' : ''} onClick={() => setFilter(key)}>{label}<em>{key === 'ALL' ? data.jobs.length : data.jobs.filter(j => key === 'UNANALYZED' ? !j.eligibility_result : j.eligibility_result === key).length}</em></button>)}</div><input className="search-input" value={query} onChange={e => setQuery(e.target.value)} placeholder="Filter by company, role, skill…" /></div>}
      {jobs.length ? <div className="job-cards">{jobs.map(job => <JobCard key={job.id} job={job} queued={queued.has(job.id)} busy={busy} onAnalyze={() => run(`analyze-${job.id}`, () => api.analyzeJob(job.id), r => `${job.company || 'Job'}: ${eligibilityLabel(r.result)}`)} onQueue={() => run(`queue-${job.id}`, () => api.queueJob(job.id), 'Added to queue')} onDelete={() => confirm(`Delete ${job.role || 'this job'}${job.company ? ` at ${job.company}` : ''}?`) && run(`delete-${job.id}`, () => api.deleteJob(job.id), 'Job removed')} onOpenQueue={() => go('Queue')} />)}</div>
        : data.jobs.length ? <Empty icon={Search} title="No jobs match this filter" text="Try another filter or clear the search." />
        : <Empty icon={Search} title="Paste your first internship" text="ApplyPilot will extract only what the page actually says." />}
    </section>
  </>
}

function JobCard({ job, queued, busy, onAnalyze, onQueue, onDelete, onOpenQueue }: { job: Job; queued: boolean; busy: string | null; onAnalyze: () => void; onQueue: () => void; onDelete: () => void; onOpenQueue: () => void }) {
  const match = job.eligibility_match
  const skills = [...job.required_skills, ...job.preferred_skills]
  return <article className="job-card">
    <JobRow job={job} />
    <p>{job.description.slice(0, 260) || 'No description was extracted. Add details manually; ApplyPilot will not fabricate them.'}</p>
    <div className="skill-line">{skills.slice(0, 9).map(s => <Badge key={s} tone={match?.strong.includes(s) ? 'good' : match?.missing.includes(s) ? 'bad' : 'neutral'}>{s}</Badge>)}</div>
    {job.eligibility_result && <div className="analysis-box">
      <div><Badge tone={eligibilityTone(job.eligibility_result)}>{eligibilityLabel(job.eligibility_result)}</Badge>{match?.required_coverage != null && <span>{match.required_coverage}% of required skills</span>}{match && match.missing.length > 0 && <span>Missing: {match.missing.join(', ')}</span>}</div>
      {job.eligibility_checks?.map(c => <small key={c.name}><b className={`check-${c.result.toLowerCase()}`}>{c.name}: {c.result}</b> — {c.explanation}</small>)}
    </div>}
    <footer>
      {job.posting_url && <a className="button ghost icon-only" href={job.posting_url} target="_blank" rel="noreferrer" title="Open posting"><ExternalLink size={15} /></a>}
      <button className="button ghost icon-only" title="Delete job" disabled={busy === `delete-${job.id}`} onClick={onDelete}><Trash2 size={15} /></button>
      <span className="spacer" />
      <button className="button ghost" disabled={busy === `analyze-${job.id}`} onClick={onAnalyze}>{busy === `analyze-${job.id}` ? 'Analyzing…' : job.eligibility_result ? 'Re-analyze' : 'Analyze eligibility'}</button>
      {queued ? <button className="button subtle" onClick={onOpenQueue}>In queue</button> : <button className="button primary" disabled={busy === `queue-${job.id}` || job.eligibility_result === 'INELIGIBLE'} title={job.eligibility_result === 'INELIGIBLE' ? 'Blocked: a definite eligibility check failed' : undefined} onClick={onQueue}>Add to queue</button>}
    </footer>
  </article>
}
