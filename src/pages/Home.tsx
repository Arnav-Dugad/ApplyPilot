import { ArrowRight, BriefcaseBusiness, Check, ChevronRight, Circle, Inbox, Plus, ShieldCheck, Zap } from 'lucide-react'
import { AnimatedNumber, AutopilotOrb } from '../motion'
import { ActivityList, Badge, Empty, JobRow, PageHeading, eligibilityRank, relativeTime, type PageProps } from '../ui'

function greeting(hour: number) {
  return hour < 5 ? 'Working late' : hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening'
}

export function Home({ data, go, openJob }: PageProps) {
  const now = new Date()
  const name = data.facts.find(f => f.category === 'personal' && f.fact_key === 'full_name' && f.status === 'VERIFIED')?.value
  const firstName = typeof name === 'string' ? name.trim().split(/\s+/)[0] : ''
  const inbox = data.inbox.questions.length + data.inbox.suggestions.length + data.inbox.drafts.length
  const ready = data.applications.filter(a => a.status === 'READY_FOR_REVIEW').length
  const applied = data.applications.filter(a => ['APPLIED', 'SUBMITTED', 'INTERVIEWING', 'OFFER', 'REJECTED'].includes(a.status)).length
  const topMatches = [...data.jobs].filter(j => j.eligibility_result !== 'INELIGIBLE').sort((a, b) => eligibilityRank(a) - eligibilityRank(b)).slice(0, 6)
  const ap = data.autopilot
  const last = ap.runs[0]
  const running = Boolean(ap.running)

  const setup = [
    { done: data.facts.some(f => f.category === 'skills' && f.status === 'VERIFIED'), label: 'Verify your skills', page: 'Profile' as const },
    { done: data.facts.some(f => f.category === 'work_authorization' && f.status === 'VERIFIED'), label: 'Set work authorization per country', page: 'Profile' as const },
    { done: data.cvs.some(c => c.approved), label: 'Approve a CV', page: 'CV Library' as const },
    { done: data.watchlist.length > 0, label: 'Follow companies for Autopilot', page: 'Autopilot' as const },
    { done: ap.config.enabled, label: 'Turn on Autopilot', page: 'Autopilot' as const },
  ]
  const setupLeft = setup.filter(s => !s.done).length

  return <>
    <PageHeading eyebrow={now.toLocaleDateString([], { weekday: 'long', month: 'long', day: 'numeric' })} title={`${greeting(now.getHours())}${firstName ? `, ${firstName}` : ''}`} text={ready ? `${ready} application${ready > 1 ? 's are' : ' is'} filled and ready for your final check.` : inbox ? `${inbox} quick item${inbox > 1 ? 's' : ''} in your Inbox will move things forward.` : 'Here’s where your internship search stands.'}>
      <button className="button primary" onClick={() => go('Discover')}><Plus size={17} /> Add job</button>
    </PageHeading>

    <button className={`autopilot-strip ${running ? 'running' : ap.config.enabled ? 'on' : 'off'}`} onClick={() => go('Autopilot')}>
      <AutopilotOrb state={running ? 'running' : ap.config.enabled ? 'idle' : 'off'} size={46} />
      <div><b>{running ? 'Autopilot is working' : ap.config.enabled ? 'Autopilot is on' : 'Autopilot is off'}</b>
        <span>{running ? last?.events.at(-1)?.message : last ? `Last run ${relativeTime(last.finished_at || last.started_at)}: ${last.summary.new ?? 0} new, ${last.summary.queued ?? 0} queued` : `Following ${data.watchlist.length} compan${data.watchlist.length === 1 ? 'y' : 'ies'} · turn it on to discover jobs automatically`}</span></div>
      <span className="strip-cta">{ap.config.enabled ? 'Open' : <><Zap size={14} /> Set up</>}<ArrowRight size={15} /></span>
    </button>

    <section className="stats">
      <button className="stat" onClick={() => go('Discover')}><span>Internships found</span><strong><AnimatedNumber value={data.jobs.length} /></strong><small>{data.jobs.filter(j => (j.score?.score ?? 0) >= 80).length} strong matches</small></button>
      <button className="stat stat-accent" onClick={() => go('Queue')}><span>Ready to submit</span><strong><AnimatedNumber value={ready} /></strong><small>Filled from verified facts</small></button>
      <button className="stat" onClick={() => go('Inbox')}><span>Inbox</span><strong><AnimatedNumber value={inbox} /></strong><small>{data.inbox.questions.length} questions · {data.inbox.suggestions.length} suggestions</small></button>
      <button className="stat" onClick={() => go('Tracker')}><span>Applied</span><strong><AnimatedNumber value={applied} /></strong><small>{data.applications.filter(a => a.status === 'INTERVIEWING').length} interviewing · {data.applications.filter(a => a.status === 'OFFER').length} offers</small></button>
    </section>

    <div className="dashboard-grid">
      <section className="panel wide"><div className="panel-head"><div><h2>Top matches</h2><p>Ranked by eligibility, then match score. Click one for the full breakdown.</p></div><button className="text-button" onClick={() => go('Discover')}>View all <ChevronRight size={15} /></button></div>
        {topMatches.length ? <div className="job-list stagger">{topMatches.map(j => <JobRow key={j.id} job={j} onClick={() => openJob(j.id)} />)}</div> : <Empty icon={BriefcaseBusiness} title="No internships yet" text="Follow a few companies and let Autopilot find them, or paste a job link." action={() => go('Autopilot')} actionLabel="Set up Autopilot" />}
      </section>
      <div className="stack">
        {inbox > 0 ? <button className="inbox-hero" onClick={() => go('Inbox')}><Inbox /><div><b>{inbox} item{inbox > 1 ? 's' : ''} in your Inbox</b><span>{data.inbox.questions.length ? `Answering ${data.inbox.questions.length} question${data.inbox.questions.length > 1 ? 's' : ''} unlocks ${new Set(data.inbox.questions.flatMap(q => q.applications.map(a => a.id))).size} application${new Set(data.inbox.questions.flatMap(q => q.applications.map(a => a.id))).size === 1 ? '' : 's'}` : 'Suggestions and drafts to confirm'}</span></div><ArrowRight /></button>
          : <section className="panel"><div className="all-clear"><ShieldCheck /><b>Inbox zero</b><span>Nothing needs your answer right now.</span></div></section>}
        {setupLeft > 0 && <section className="panel"><div className="panel-head"><div><h2>Finish setting up</h2><p>{setup.length - setupLeft} of {setup.length} done</p></div><Badge tone="accent">{Math.round(((setup.length - setupLeft) / setup.length) * 100)}%</Badge></div>
          <div className="checklist">{setup.map(s => <button key={s.label} className={s.done ? 'done' : ''} disabled={s.done} onClick={() => go(s.page)}>{s.done ? <Check /> : <Circle />}{s.label}{!s.done && <ChevronRight size={14} />}</button>)}</div>
        </section>}
      </div>
      <section className="panel wide"><div className="panel-head"><div><h2>Recent activity</h2><p>A human-readable audit trail.</p></div><button className="text-button" onClick={() => go('Activity')}>Full log <ChevronRight size={15} /></button></div><ActivityList items={data.activity.slice(0, 6)} /></section>
    </div>
  </>
}
