import { Suspense, lazy, useEffect, useState } from 'react'
import { BarChart3, Check, Lightbulb, Plus, Sparkles } from 'lucide-react'
import { api } from '../api'
import { Sankey } from '../components/Sankey'
import type { CoachTip } from '../types'
import { AnimatedNumber, Skeleton } from '../motion'
import { Empty, PageHeading, STATUS_LABELS, Stat, eligibilityLabel, useAction, type PageProps } from '../ui'

const WorldMap = lazy(() => import('../components/WorldMap').then(m => ({ default: m.WorldMap })))

function Bars({ rows, tone = 'accent' }: { rows: [string, number][]; tone?: string }) {
  const max = Math.max(1, ...rows.map(([, n]) => n))
  if (!rows.length) return <p className="muted small">No data yet.</p>
  return <div className="bars">{rows.map(([label, n]) => <div key={label} className="bar-row"><span>{label}</span><div><i className={tone} style={{ width: `${(n / max) * 100}%` }} /></div><b>{n}</b></div>)}</div>
}

const count = <T,>(items: T[], key: (item: T) => string | null | undefined) =>
  Object.entries(items.reduce<Record<string, number>>((all, item) => { const k = key(item); if (k) all[k] = (all[k] ?? 0) + 1; return all }, {})).sort((a, b) => b[1] - a[1])

export function Insights({ data, refresh, go, ask }: PageProps) {
  const { run } = useAction(refresh)
  const [coach, setCoach] = useState<CoachTip[] | null>(null)
  useEffect(() => { api.insights().then(r => setCoach(r.coach)).catch(() => setCoach([])) }, [data.jobs.length, data.facts.length])
  const jobs = data.jobs.filter(j => !j.duplicate_of)
  const applied = data.applications.filter(a => ['APPLIED', 'SUBMITTED', 'INTERVIEWING', 'OFFER', 'REJECTED'].includes(a.status))
  const responses = applied.filter(a => ['INTERVIEWING', 'OFFER', 'REJECTED'].includes(a.status)).length
  const verifiedSkills = (data.facts.find(f => f.category === 'skills' && f.fact_key === 'verified_skills' && f.status === 'VERIFIED')?.value as string[] | undefined) ?? []

  const addSkill = (skill: string) => {
    if (!confirm(`Add “${skill}” to your verified skills?\n\nOnly add skills you genuinely have — ApplyPilot will treat it as true on every application.`)) return
    run('skill', () => api.saveFact({ category: 'skills', fact_key: 'verified_skills', value: [...verifiedSkills, skill], status: 'VERIFIED', source: 'USER' }), `${skill} added — every job re-scored`)
  }

  if (!jobs.length) return <><PageHeading eyebrow="Insights" title="How your search is going" text="Descriptive, never causal: what ApplyPilot has seen and what you've done." /><section className="panel"><Empty icon={BarChart3} title="No data yet" text="Follow a few companies and let Autopilot run once." action={() => go('Autopilot')} actionLabel="Open Autopilot" /></section></>

  return <>
    <PageHeading eyebrow="Insights" title="How your search is going" text="Descriptive, never causal: what ApplyPilot has seen and what you've done." />
    <section className="stats">
      <Stat label="Unique jobs" value={jobs.length} hint={`${data.jobs.length - jobs.length} duplicates merged`} />
      <Stat label="Strong matches" value={jobs.filter(j => (j.score?.score ?? 0) >= 80).length} accent hint="Score 80 or higher" />
      <Stat label="Applied" value={applied.length} hint={`${data.applications.length} in your pipeline`} />
      <Stat label="Heard back" value={applied.length ? `${Math.round((responses / applied.length) * 100)}%` : '—'} hint={`${responses} of ${applied.length} applications`} />
    </section>

    <section className="panel"><div className="panel-head"><div><h2>Pipeline</h2><p>Every unique job, from discovery to offer. Hover a stage to trace it.</p></div></div><Sankey jobs={data.jobs} apps={data.applications} /></section>

    <section className="panel"><div className="panel-head"><div><h2>Where your matches are</h2><p>Brighter countries have more jobs; pulsing dots have strong matches. Click one to see its jobs.</p></div></div>
      <Suspense fallback={<Skeleton lines={6} />}><WorldMap jobs={data.jobs} onSelect={(_code, name) => ask(`internships in ${name}`)} /></Suspense></section>

    <section className="panel coach"><div className="panel-head"><div><h2><Lightbulb size={15} /> Why not me?</h2><p>The single additions that would unlock the most jobs you've already found.</p></div></div>
      {coach === null ? <Skeleton lines={4} /> : coach.length === 0 ? <p className="muted small">Nothing is holding you back across the analyzed jobs. 🎯</p>
        : <div className="coach-list">{coach.map((tip, i) => <article key={tip.name} className={`coach-tip ${tip.kind.toLowerCase()}`} style={{ animationDelay: `${i * 40}ms` }}>
          <div className="coach-rank">{i + 1}</div>
          <div><b>{tip.kind === 'SKILL' ? `Learn ${tip.name}` : `Verify: ${tip.name}`}</b>
            <span>{tip.kind === 'SKILL' ? <>Required by <b><AnimatedNumber value={tip.jobs} /></b> job{tip.jobs === 1 ? '' : 's'}{tip.unlocks ? <> · would make <b>{tip.unlocks}</b> fully eligible</> : ''}</> : <>Needed to decide <b>{tip.jobs}</b> job{tip.jobs === 1 ? '' : 's'}</>}</span>
            {tip.examples.length > 0 && <small>{tip.examples.join(' · ')}</small>}</div>
          {tip.kind === 'SKILL' ? (verifiedSkills.map(s => s.toLowerCase()).includes(tip.name) ? <span className="chip done"><Check size={12} />Verified</span>
            : <button className="button ghost" onClick={() => addSkill(tip.name)}><Plus size={14} /> I have it</button>)
            : <button className="button ghost" onClick={() => go('Profile')}><Sparkles size={14} /> Add in Profile</button>}
        </article>)}</div>}
    </section>

    <div className="analytics-grid">
      <section className="panel"><div className="panel-head"><div><h2>Eligibility</h2><p>Across analyzed jobs</p></div></div><Bars rows={count(jobs.filter(j => j.eligibility_result), j => eligibilityLabel(j.eligibility_result))} /></section>
      <section className="panel"><div className="panel-head"><div><h2>Pipeline by stage</h2><p>Applications</p></div></div><Bars rows={count(data.applications, a => STATUS_LABELS[a.status] ?? a.status)} /></section>
      <section className="panel"><div className="panel-head"><div><h2>Most-missed skills</h2><p>Required by jobs, not in your verified profile</p></div></div><Bars rows={count(jobs.flatMap(j => j.eligibility_match?.missing ?? []), s => s).slice(0, 8)} tone="warn" /></section>
      <section className="panel"><div className="panel-head"><div><h2>Where jobs come from</h2><p>Job board</p></div></div><Bars rows={count(jobs, j => j.application_platform || 'GENERIC')} /></section>
    </div>
  </>
}
