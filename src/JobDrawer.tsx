import { useEffect, useState } from 'react'
import { ExternalLink, FileQuestion, ListPlus, PenLine, Sparkles, Wand2, X } from 'lucide-react'
import { api } from './api'
import type { Bootstrap, JobDetail } from './types'
import { ScoreRing, Skeleton } from './motion'
import { Badge, eligibilityLabel, eligibilityTone, formatDate, relativeTime, useAction, type Page } from './ui'

export function JobDrawer({ jobId, data, refresh, close, go }: { jobId: string; data: Bootstrap; refresh: () => Promise<void>; close: () => void; go: (p: Page) => void }) {
  const [job, setJob] = useState<JobDetail | null>(null)
  const [error, setError] = useState('')
  const { run, busy } = useAction(async () => { await refresh(); setJob(await api.job(jobId)) })
  const aiOn = (data.settings.ollama as { provider?: string } | undefined)?.provider === 'OLLAMA'
  useEffect(() => { setJob(null); api.job(jobId).then(setJob).catch(e => setError(e.message)) }, [jobId])
  useEffect(() => { const key = (e: KeyboardEvent) => e.key === 'Escape' && close(); addEventListener('keydown', key); return () => removeEventListener('keydown', key) }, [close])
  const score = job?.score
  const letter = job?.drafts.find(d => d.kind === 'COVER_LETTER')

  return <div className="drawer-backdrop" onMouseDown={close}>
    <aside className="drawer" onMouseDown={e => e.stopPropagation()} role="dialog" aria-label="Job details">
      <button className="icon-button drawer-close" onClick={close} aria-label="Close"><X /></button>
      {error ? <p className="warn-text">{error}</p> : !job ? <div className="drawer-body"><Skeleton lines={2} /><Skeleton lines={6} /></div> : <div className="drawer-body">
        <header className="drawer-head">
          <ScoreRing score={score?.score} size={78} stroke={6} />
          <div><p className="eyebrow">{job.company}</p><h2>{job.role}</h2>
            <span>{job.location || 'Location not stated'}{job.employment_type ? ` · ${job.employment_type}` : ''}{job.date_posted ? ` · posted ${relativeTime(job.date_posted)}` : ''}</span>
            <div className="tags">{job.eligibility_result && <Badge tone={eligibilityTone(job.eligibility_result)}>{eligibilityLabel(job.eligibility_result)}</Badge>}{score && <Badge tone="accent">Grade {score.grade}</Badge>}<Badge>{job.application_platform || 'GENERIC'}</Badge>{job.compensation && <Badge tone="good">{job.compensation}</Badge>}</div></div>
        </header>
        <div className="drawer-actions">
          {job.application ? <button className="button subtle" onClick={() => { go('Queue'); close() }}>In queue · {job.application.status.replaceAll('_', ' ').toLowerCase()}</button>
            : <button className="button primary" disabled={busy === 'queue' || job.eligibility_result === 'INELIGIBLE'} onClick={() => run('queue', () => api.queueJob(job.id), 'Queued and form checked')}><ListPlus size={16} /> Add to queue</button>}
          {job.posting_url && <a className="button ghost" href={job.posting_url} target="_blank" rel="noreferrer"><ExternalLink size={15} /> Posting</a>}
          {aiOn && !letter && <button className="button ghost" disabled={busy === 'letter'} onClick={() => run('letter', () => api.coverLetter(job.id), 'Cover letter drafted — review it in your Inbox')}><Wand2 size={15} className={busy === 'letter' ? 'spin' : ''} /> {busy === 'letter' ? 'Writing…' : 'Draft cover letter'}</button>}
        </div>

        <section className="drawer-section"><h3><Sparkles size={15} /> At a glance</h3>
          {job.ai_summary ? <div className="ai-summary"><p>{job.ai_summary.summary}</p><ul>{job.ai_summary.highlights.map(h => <li key={h}>{h}</li>)}</ul>{job.ai_summary.watch_outs.length > 0 && <><b>Watch out</b><ul className="watch">{job.ai_summary.watch_outs.map(h => <li key={h}>{h}</li>)}</ul></>}<small>Summarized locally by {job.ai_summary.model}</small></div>
            : <><p className="drawer-desc">{job.description.slice(0, 420)}{job.description.length > 420 ? '…' : ''}</p>{aiOn && <button className="button ghost" disabled={busy === 'sum'} onClick={() => run('sum', () => api.summarize(job.id))}><Sparkles size={14} className={busy === 'sum' ? 'spin' : ''} /> {busy === 'sum' ? 'Reading…' : 'Summarize with local AI'}</button>}</>}
        </section>

        {score && <section className="drawer-section"><h3>Why it scored {score.score}</h3>
          <div className="factors">{score.factors.map(f => <div key={f.name} className="factor"><span>{f.name}</span><div className="factor-bar"><i style={{ width: `${(f.points / f.max) * 100}%` }} /></div><b>{Math.round(f.points)}/{f.max}</b><small>{f.detail}</small></div>)}</div>
          {score.adjustment && <p className="warn-text small">{score.adjustment}</p>}
        </section>}

        {job.eligibility_checks && <section className="drawer-section"><h3>Eligibility checks</h3>
          {job.eligibility_checks.map(c => <div key={c.name} className="check-line"><Badge tone={c.result === 'PASS' ? 'good' : c.result === 'FAIL' ? 'bad' : 'warn'}>{c.result}</Badge><b>{c.name}</b><span>{c.explanation}</span></div>)}
          {job.eligibility_result === 'NEEDS_INFORMATION' && <button className="link" onClick={() => { go('Profile'); close() }}>Add the missing facts in your profile →</button>}
          {job.eligibility_match && <div className="skill-line">{job.eligibility_match.strong.map(s => <Badge key={s} tone="good">{s}</Badge>)}{job.eligibility_match.related?.map(s => <Badge key={s} tone="accent">{s} ~</Badge>)}{job.eligibility_match.missing.filter(s => !job.eligibility_match?.related?.includes(s)).map(s => <Badge key={s} tone="bad">{s}</Badge>)}</div>}
          <small className="muted">Green: verified skills · Blue ~: you know a related skill · Red: missing</small>
        </section>}

        {job.board_questions && job.board_questions.length > 0 && <section className="drawer-section"><h3><FileQuestion size={15} /> The real application form · {job.board_questions.length} questions</h3>
          <ol className="question-preview">{job.board_questions.map((q, i) => <li key={i}><span>{q.label}</span>{q.required && <em>required</em>}{q.field_type === 'file' && <Badge>upload</Badge>}{q.options.length > 0 && <small>{q.options.slice(0, 4).join(' · ')}{q.options.length > 4 ? ' …' : ''}</small>}</li>)}</ol>
        </section>}

        {letter && <section className="drawer-section"><h3><PenLine size={15} /> Cover letter {letter.status === 'APPROVED' ? <Badge tone="good">approved</Badge> : <Badge tone="warn">draft</Badge>}</h3><p className="letter">{letter.content}</p>{letter.status !== 'APPROVED' && <button className="link" onClick={() => { go('Inbox'); close() }}>Review and approve in Inbox →</button>}</section>}

        <footer className="drawer-foot">Found {formatDate(job.date_found)} via {job.source}{job.deadline ? ` · closes ${formatDate(job.deadline)}` : ''}</footer>
      </div>}
    </aside>
  </div>
}
