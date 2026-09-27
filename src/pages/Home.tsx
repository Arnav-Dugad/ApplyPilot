import { useState } from 'react'
import { AlarmClock, ArrowRight, BriefcaseBusiness, Check, ChevronRight, CircleAlert, GraduationCap, Inbox, Info, Mail, Send, Sparkles, Target, TriangleAlert, Zap } from 'lucide-react'
import type { TodayAction } from '../types'
import { AnimatedNumber, AutopilotOrb, ScoreRing } from '../motion'
import { ActivityList, Empty, JobRow, PageHeading, eligibilityRank, relativeTime, type Page, type PageProps } from '../ui'

function greeting(hour: number) {
  return hour < 5 ? 'Working late' : hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening'
}
const ACTION_ICON: Record<TodayAction['kind'], typeof Send> = { DEADLINE: AlarmClock, SUBMIT: Send, INBOX: Inbox, PREP: GraduationCap, FOLLOW_UP: Mail, SUGGESTIONS: Sparkles, DISCOVER: Target }
const DONE_KEY = `applypilot.today.${new Date().toISOString().slice(0, 10)}`

export function Home({ data, go, openJob }: PageProps) {
  const now = new Date()
  const name = data.facts.find(f => f.category === 'personal' && f.fact_key === 'full_name' && f.status === 'VERIFIED')?.value
  const firstName = typeof name === 'string' ? name.trim().split(/\s+/)[0] : ''
  const [done, setDone] = useState<string[]>(() => { try { return JSON.parse(localStorage.getItem(DONE_KEY) || '[]') } catch { return [] } })
  const today = data.today ?? []
  const completed = today.filter(a => done.includes(a.title)).length
  const ap = data.autopilot
  const last = ap.runs[0]
  const running = Boolean(ap.running)
  const strength = data.strength
  const ready = data.applications.filter(a => a.status === 'READY_FOR_REVIEW').length
  const applied = data.applications.filter(a => ['APPLIED', 'SUBMITTED', 'INTERVIEWING', 'OFFER', 'REJECTED'].includes(a.status)).length
  const topMatches = [...data.jobs].filter(j => j.eligibility_result !== 'INELIGIBLE' && !j.duplicate_of && j.vote !== -1).sort((a, b) => eligibilityRank(a) - eligibilityRank(b)).slice(0, 5)
  const open = (action: TodayAction) => {
    const next = Array.from(new Set([...done, action.title]))
    setDone(next)
    try { localStorage.setItem(DONE_KEY, JSON.stringify(next)) } catch { /* optional */ }
    if (action.job_id && (action.kind === 'DEADLINE' || action.kind === 'PREP')) openJob(action.job_id)
    else go(action.page as Page)
  }

  return <>
    <PageHeading eyebrow={now.toLocaleDateString([], { weekday: 'long', month: 'long', day: 'numeric' })} title={`${greeting(now.getHours())}${firstName ? `, ${firstName}` : ''}`}
      text={today.length ? `${today.length - completed ? `${today.length - completed} thing${today.length - completed === 1 ? '' : 's'} worth doing today` : 'You’ve done today’s most valuable things'}.` : 'Here’s where your internship search stands.'} />

    <div className="today-layout">
      <section className="panel today"><div className="panel-head"><div><h2>Today</h2><p>The highest-value actions right now, ranked.</p></div><ScoreRing score={today.length ? Math.round((completed / today.length) * 100) : 100} size={46} stroke={4} /></div>
        {today.length ? <ol className="today-list">{today.map((action, i) => { const Icon = ACTION_ICON[action.kind]; const isDone = done.includes(action.title)
          return <li key={action.title} className={`${action.kind.toLowerCase()} ${isDone ? 'done' : ''}`} style={{ animationDelay: `${i * 60}ms` }}>
            <button onClick={() => open(action)}><span className="today-icon">{isDone ? <Check /> : <Icon />}</span><div><b>{action.title}</b>{action.detail && <span>{action.detail}</span>}</div><ArrowRight className="go" /></button>
          </li> })}</ol>
          : <div className="all-clear"><Check /><b>All caught up</b><span>Autopilot will surface the next thing to do.</span></div>}
      </section>
      <div className="stack">
        {strength && <button className="strength-card" onClick={() => go('Profile')}>
          <ScoreRing score={strength.percent} size={82} stroke={7} />
          <div><b>Profile strength</b><span>{strength.percent >= 100 ? 'Complete — every common field can autofill.' : 'Verified facts unlock more autofill and better matches.'}</span>
            {strength.next.length > 0 && <ul>{strength.next.map(i => <li key={i.label}>+{i.points}% · {i.label}</li>)}</ul>}</div>
        </button>}
        <button className={`autopilot-strip ${running ? 'running' : ap.config.enabled ? 'on' : 'off'}`} onClick={() => go('Autopilot')}>
          <AutopilotOrb state={running ? 'running' : ap.config.enabled ? 'idle' : 'off'} size={46} />
          <div><b>{running ? 'Autopilot is working' : ap.config.enabled ? 'Autopilot is on' : 'Autopilot is off'}</b>
            <span>{running ? last?.events.at(-1)?.message : last ? `Last run ${relativeTime(last.finished_at || last.started_at)}: ${last.summary.new ?? 0} new, ${last.summary.queued ?? 0} queued` : `Following ${data.watchlist.length} compan${data.watchlist.length === 1 ? 'y' : 'ies'}`}</span></div>
          <span className="strip-cta">{ap.config.enabled ? 'Open' : <><Zap size={14} /> Set up</>}<ArrowRight size={15} /></span>
        </button>
      </div>
    </div>

    {(data.health ?? []).length > 0 && <div className="health-strip">{(data.health ?? []).map(issue => <button key={issue.title} className={`health-chip ${issue.level}`} onClick={() => go(issue.page as Page)} title={issue.detail}>
      {issue.level === 'bad' ? <CircleAlert size={14} /> : issue.level === 'warn' ? <TriangleAlert size={14} /> : <Info size={14} />}{issue.title}</button>)}</div>}

    <section className="stats">
      <button className="stat" onClick={() => go('Discover')}><span>Internships found</span><strong><AnimatedNumber value={data.jobs.filter(j => !j.duplicate_of).length} /></strong><small>{data.jobs.filter(j => (j.score?.score ?? 0) >= 80 && !j.duplicate_of).length} strong matches</small></button>
      <button className="stat stat-accent" onClick={() => go('Queue')}><span>Ready to submit</span><strong><AnimatedNumber value={ready} /></strong><small>Filled from verified facts</small></button>
      <button className="stat" onClick={() => go('Inbox')}><span>Inbox</span><strong><AnimatedNumber value={data.inbox.questions.length + data.inbox.suggestions.length + data.inbox.drafts.length} /></strong><small>{data.inbox.questions.length} questions · {data.inbox.drafts.length} drafts</small></button>
      <button className="stat" onClick={() => go('Tracker')}><span>Applied</span><strong><AnimatedNumber value={applied} /></strong><small>{data.applications.filter(a => a.status === 'INTERVIEWING').length} interviewing · {data.applications.filter(a => a.status === 'OFFER').length} offers</small></button>
    </section>

    <div className="dashboard-grid">
      <section className="panel wide"><div className="panel-head"><div><h2>Top matches</h2><p>Eligible first, then match score. Click one for the full breakdown.</p></div><button className="text-button" onClick={() => go('Discover')}>View all <ChevronRight size={15} /></button></div>
        {topMatches.length ? <div className="job-list stagger">{topMatches.map(j => <JobRow key={j.id} job={j} onClick={() => openJob(j.id)} />)}</div> : <Empty icon={BriefcaseBusiness} title="No internships yet" text="Follow a few companies and let Autopilot find them, or paste a job link." action={() => go('Autopilot')} actionLabel="Set up Autopilot" />}
      </section>
      <section className="panel"><div className="panel-head"><div><h2>Recent activity</h2><p>A human-readable audit trail.</p></div><button className="text-button" onClick={() => go('Activity')}>Full log <ChevronRight size={15} /></button></div><ActivityList items={data.activity.slice(0, 7)} /></section>
    </div>
  </>
}
