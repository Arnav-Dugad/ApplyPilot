import { useEffect, useMemo, useState } from 'react'
import { ExternalLink, Layers, Link2, PenLine, RefreshCw, Search, Sparkles, ThumbsDown, ThumbsUp, Trash2, X } from 'lucide-react'
import { api } from '../api'
import type { EligibilityResult, Job, SearchResult } from '../types'
import { Badge, Empty, JobRow, PageHeading, eligibilityLabel, eligibilityRank, eligibilityTone, useAction, type PageProps } from '../ui'

type Filter = 'ALL' | 'TOP' | EligibilityResult | 'UNANALYZED'
const FILTERS: [Filter, string][] = [['ALL', 'All'], ['TOP', 'Top matches'], ['ELIGIBLE', 'Eligible'], ['LIKELY_ELIGIBLE', 'Likely'], ['NEEDS_INFORMATION', 'Needs info'], ['INELIGIBLE', 'Ineligible'], ['UNANALYZED', 'Not analyzed']]
const blankJob = { company: '', role: '', location: '', country: '', posting_url: '', description: '' }
const EXAMPLES = ['backend roles with Python in Europe', 'remote ML internships', 'data analyst jobs in India or UAE', 'React frontend in the UK']
const looksLikeUrl = (text: string) => /^https?:\/\//i.test(text.trim()) || /^[\w-]+(\.[\w-]+)+\/\S*/.test(text.trim())

export function Discover({ data, refresh, go, openJob, askQuery }: PageProps & { askQuery?: string }) {
  const matches = (j: Job, key: Filter) => key === 'ALL' || (key === 'TOP' ? (j.score?.score ?? 0) >= 80 : key === 'UNANALYZED' ? !j.eligibility_result : j.eligibility_result === key)
  const { run, busy } = useAction(refresh)
  const [input, setInput] = useState('')
  const [manual, setManual] = useState<typeof blankJob | null>(null)
  const [filter, setFilter] = useState<Filter>('ALL')
  const [showDuplicates, setShowDuplicates] = useState(false)
  const [search, setSearch] = useState<(SearchResult & { query: string }) | null>(null)
  const queued = useMemo(() => new Set(data.applications.map(a => a.job_id)), [data.applications])
  const duplicates = data.jobs.filter(j => j.duplicate_of).length

  const ask = async (query: string) => {
    const result = await run('ask', () => api.search(query))
    if (result) { setSearch({ ...result, query }); setInput(query) }
  }
  useEffect(() => { if (askQuery) ask(askQuery) }, [askQuery]) // eslint-disable-line react-hooks/exhaustive-deps

  const jobs = useMemo(() => {
    if (search) {
      const byId = new Map(data.jobs.map(j => [j.id, j]))
      return search.ids.map(id => byId.get(id)).filter(Boolean) as Job[]
    }
    return data.jobs.filter(j => matches(j, filter) && (showDuplicates || !j.duplicate_of))
      .sort((a, b) => ((a.vote ?? 0) < 0 ? 1 : 0) - ((b.vote ?? 0) < 0 ? 1 : 0) || eligibilityRank(a) - eligibilityRank(b))
  }, [data.jobs, filter, search, showDuplicates])

  const submit = async () => {
    const text = input.trim()
    if (!text) return
    if (!looksLikeUrl(text)) return ask(text)
    const job = await run('import', () => api.importJob(text), j => `Imported ${j.role || 'job'}${j.company ? ` at ${j.company}` : ''}`)
    if (job) { setInput(''); await run(`analyze-${job.id}`, () => api.analyzeJob(job.id)); openJob(job.id) }
    else setManual({ ...blankJob, posting_url: text })
  }
  const saveManual = async () => {
    if (!manual) return
    const job = await run('manual', () => api.manualJob(manual), 'Job added')
    if (job) { setManual(null); setInput(''); openJob(job.id) }
  }
  const isUrl = looksLikeUrl(input)

  return <>
    <PageHeading eyebrow="Discovery" title="Find a role worth applying to" text="Paste a job link to import it, or just ask in plain English.">
      <button className="button ghost" onClick={() => setManual(manual ? null : { ...blankJob })}><PenLine size={16} /> Add manually</button>
      {data.jobs.length > 0 && <button className="button ghost" disabled={busy === 'analyze-all'} onClick={() => run('analyze-all', () => api.analyzeAll(), r => `Re-scored ${r.analyzed} jobs against your verified profile`)}><RefreshCw size={16} className={busy === 'analyze-all' ? 'spin' : ''} /> Re-analyze all</button>}
    </PageHeading>
    <section className={`import-bar smart ${isUrl ? 'url' : 'ask'}`}>{isUrl ? <Link2 /> : <Sparkles />}
      <input value={input} onChange={e => setInput(e.target.value)} placeholder="Paste a job link, or ask: “backend roles with Python in Europe”" onKeyDown={e => e.key === 'Enter' && submit()} />
      {search && <button className="icon-button" onClick={() => { setSearch(null); setInput('') }} aria-label="Clear search"><X /></button>}
      <button className="button primary" disabled={!input.trim() || busy === 'import' || busy === 'ask'} onClick={submit}>{isUrl ? (busy === 'import' ? 'Importing…' : 'Import & analyze') : (busy === 'ask' ? 'Searching…' : 'Search')}</button></section>
    {!search && !input && data.jobs.length > 0 && <div className="example-row">Try: {EXAMPLES.map(q => <button key={q} onClick={() => ask(q)}>{q}</button>)}</div>}

    {manual && <section className="panel form-panel"><div className="panel-head"><div><h2>Add a job manually</h2><p>Only what you enter is stored. Skills and requirements are detected from the description.</p></div><button className="icon-button" onClick={() => setManual(null)} aria-label="Close"><X /></button></div>
      <div className="form-grid">
        <label>Company *<input value={manual.company} onChange={e => setManual({ ...manual, company: e.target.value })} autoFocus /></label>
        <label>Role *<input value={manual.role} onChange={e => setManual({ ...manual, role: e.target.value })} /></label>
        <label>Location<input value={manual.location} onChange={e => setManual({ ...manual, location: e.target.value })} placeholder="Dubai" /></label>
        <label>Country<input value={manual.country} onChange={e => setManual({ ...manual, country: e.target.value })} placeholder="United Arab Emirates" /></label>
        <label className="span-2">Posting URL<input value={manual.posting_url} onChange={e => setManual({ ...manual, posting_url: e.target.value })} placeholder="https://" /></label>
        <label className="span-2">Description<textarea value={manual.description} onChange={e => setManual({ ...manual, description: e.target.value })} placeholder="Paste the job description, including requirements, languages, and any sponsorship wording." /></label>
      </div>
      <div className="form-actions"><button className="button ghost" onClick={() => setManual(null)}>Cancel</button><button className="button primary" disabled={!manual.company.trim() || !manual.role.trim() || busy === 'manual'} onClick={saveManual}>Save & analyze</button></div>
    </section>}

    <section className="panel">
      {search ? <div className="panel-head"><div><h2>{search.ids.length} result{search.ids.length === 1 ? '' : 's'} for “{search.query}”</h2>
        <div className="parsed">{search.parsed.roles.map(r => <span key={r} className="chip on">Role: {r}</span>)}{search.parsed.skills.map(s => <span key={s} className="chip on">Skill: {s}</span>)}{search.parsed.places.map(p => <span key={p} className="chip on">Place: {p}</span>)}{search.parsed.remote && <span className="chip on">Remote</span>}{search.parsed.keywords.map(k => <span key={k} className="chip">“{k}”</span>)}{search.semantic && <span className="chip ai">✦ semantic ranking</span>}</div></div>
        <button className="button ghost" onClick={() => { setSearch(null); setInput('') }}>Clear</button></div>
        : <><div className="panel-head"><div><h2>Internships</h2><p>Extracted facts stay unverified until you review them. 👍/👎 teaches the ranking.</p></div><Badge>{data.jobs.length - duplicates} unique</Badge></div>
          {data.jobs.length > 0 && <div className="toolbar"><div className="chips">{FILTERS.map(([key, label]) => <button key={key} className={filter === key ? 'active' : ''} onClick={() => setFilter(key)}>{label}<em>{data.jobs.filter(j => matches(j, key) && !j.duplicate_of).length}</em></button>)}</div>
            {duplicates > 0 && <button className={`chip-toggle ${showDuplicates ? 'on' : ''}`} onClick={() => setShowDuplicates(!showDuplicates)}><Layers size={13} /> {showDuplicates ? 'Hide' : 'Show'} {duplicates} duplicate{duplicates === 1 ? '' : 's'}</button>}</div>}</>}
      {jobs.length ? <div className="job-cards stagger">{jobs.map(job => <JobCard key={job.id} job={job} queued={queued.has(job.id)} busy={busy}
        onAnalyze={() => run(`analyze-${job.id}`, () => api.analyzeJob(job.id), r => `${job.company || 'Job'}: ${eligibilityLabel(r.result)}`)}
        onQueue={() => run(`queue-${job.id}`, () => api.queueJob(job.id), 'Added to queue')}
        onDelete={() => confirm(`Delete ${job.role || 'this job'}${job.company ? ` at ${job.company}` : ''}?`) && run(`delete-${job.id}`, () => api.deleteJob(job.id), 'Job removed')}
        onVote={v => run(`vote-${job.id}`, () => api.voteJob(job.id, job.vote === v ? 0 : v), v > 0 ? 'Noted — similar roles will rank higher' : 'Noted — hidden from Autopilot')}
        onOpenQueue={() => go('Queue')} onOpen={() => openJob(job.id)} />)}</div>
        : search ? <Empty icon={Search} title="Nothing matches that yet" text="Try fewer words, a region like “Europe”, or follow more companies in Autopilot." />
        : data.jobs.length ? <Empty icon={Search} title="No jobs match this filter" text="Try another filter." />
        : <Empty icon={Search} title="No internships yet" text="Paste a job link above, or follow companies in Autopilot to find them automatically." action={() => go('Autopilot')} actionLabel="Open Autopilot" />}
    </section>
  </>
}

function JobCard({ job, queued, busy, onAnalyze, onQueue, onDelete, onVote, onOpenQueue, onOpen }: { job: Job; queued: boolean; busy: string | null; onAnalyze: () => void; onQueue: () => void; onDelete: () => void; onVote: (v: -1 | 1) => void; onOpenQueue: () => void; onOpen: () => void }) {
  const match = job.eligibility_match
  const skills = [...job.required_skills, ...job.preferred_skills]
  return <article className={`job-card ${job.vote === -1 ? 'disliked' : ''} ${job.duplicate_of ? 'duplicate' : ''}`}>
    <JobRow job={job} onClick={onOpen} />
    {job.ai_summary && <p className="ai-line">✦ {job.ai_summary.summary}</p>}
    <p>{job.description.slice(0, 260) || 'No description was extracted. Add details manually; ApplyPilot will not fabricate them.'}</p>
    <div className="skill-line">{skills.slice(0, 9).map(s => <Badge key={s} tone={match?.strong.includes(s) ? 'good' : match?.missing.includes(s) ? 'bad' : 'neutral'}>{s}</Badge>)}</div>
    {job.eligibility_result && <div className="analysis-box">
      <div><Badge tone={eligibilityTone(job.eligibility_result)}>{eligibilityLabel(job.eligibility_result)}</Badge>{match?.required_coverage != null && <span>{match.required_coverage}% of required skills</span>}{match && match.missing.length > 0 && <span>Missing: {match.missing.join(', ')}</span>}</div>
      {job.eligibility_checks?.map(c => <small key={c.name}><b className={`check-${c.result.toLowerCase()}`}>{c.name}: {c.result}</b> — {c.explanation}</small>)}
    </div>}
    <footer>
      {job.posting_url && <a className="button ghost icon-only" href={job.posting_url} target="_blank" rel="noreferrer" title="Open posting"><ExternalLink size={15} /></a>}
      <button className="button ghost icon-only" title="Delete job" disabled={busy === `delete-${job.id}`} onClick={onDelete}><Trash2 size={15} /></button>
      <div className="vote small"><button className={job.vote === 1 ? 'on up' : ''} onClick={() => onVote(1)} title="More like this" aria-label="More like this"><ThumbsUp size={14} /></button><button className={job.vote === -1 ? 'on down' : ''} onClick={() => onVote(-1)} title="Not for me" aria-label="Not for me"><ThumbsDown size={14} /></button></div>
      <span className="spacer" />
      <button className="button ghost" disabled={busy === `analyze-${job.id}`} onClick={onAnalyze}>{busy === `analyze-${job.id}` ? 'Analyzing…' : job.eligibility_result ? 'Re-analyze' : 'Analyze'}</button>
      {queued ? <button className="button subtle" onClick={onOpenQueue}>In queue</button> : <button className="button primary" disabled={busy === `queue-${job.id}` || job.eligibility_result === 'INELIGIBLE'} title={job.eligibility_result === 'INELIGIBLE' ? 'Blocked: a definite eligibility check failed' : undefined} onClick={onQueue}>Add to queue</button>}
    </footer>
  </article>
}
