import { AlertTriangle, BriefcaseBusiness, Check, ChevronRight, Circle, Plus, ShieldCheck } from 'lucide-react'
import { ActivityList, Badge, Empty, JobRow, PageHeading, Stat, eligibilityRank, type PageProps } from '../ui'

function greeting(hour: number) {
  return hour < 5 ? 'Working late' : hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening'
}

export function Home({ data, go }: PageProps) {
  const now = new Date()
  const name = data.facts.find(f => f.category === 'personal' && f.fact_key === 'full_name' && f.status === 'VERIFIED')?.value
  const firstName = typeof name === 'string' ? name.trim().split(/\s+/)[0] : ''
  const waiting = data.applications.filter(a => a.status === 'WAITING_FOR_USER' || a.status === 'NEEDS_INFO')
  const needsInfoJobs = data.jobs.filter(j => j.eligibility_result === 'NEEDS_INFORMATION').length
  const applied = data.applications.filter(a => ['APPLIED', 'SUBMITTED', 'INTERVIEWING', 'OFFER', 'REJECTED'].includes(a.status)).length
  const recommended = [...data.jobs].filter(j => j.eligibility_result !== 'INELIGIBLE').sort((a, b) => eligibilityRank(a) - eligibilityRank(b)).slice(0, 5)

  const setup = [
    { done: data.facts.some(f => f.category === 'skills' && f.status === 'VERIFIED'), label: 'Verify your skills', page: 'Profile' as const },
    { done: data.facts.some(f => f.category === 'work_authorization' && f.status === 'VERIFIED'), label: 'Set work authorization per country', page: 'Profile' as const },
    { done: data.cvs.some(c => c.approved), label: 'Approve a CV', page: 'CV Library' as const },
    { done: data.jobs.length > 0, label: 'Add your first internship', page: 'Discover' as const },
    { done: data.applications.length > 0, label: 'Queue an application', page: 'Discover' as const },
  ]
  const setupLeft = setup.filter(s => !s.done).length

  return <>
    <PageHeading eyebrow={now.toLocaleDateString([], { weekday: 'long', month: 'long', day: 'numeric' })} title={`${greeting(now.getHours())}${firstName ? `, ${firstName}` : ''}`} text="Here’s what needs your attention today.">
      <button className="button primary" onClick={() => go('Discover')}><Plus size={17} /> Add job</button>
    </PageHeading>
    <section className="stats">
      <Stat label="Internships found" value={data.jobs.length} hint={`${data.jobs.filter(j => j.eligibility_result).length} analyzed`} />
      <Stat label="In the queue" value={data.applications.filter(a => ['QUEUED', 'READY_FOR_REVIEW', 'WAITING_FOR_USER', 'NEEDS_INFO'].includes(a.status)).length} accent hint="Awaiting a safe run or review" />
      <Stat label="Need your answer" value={waiting.length + needsInfoJobs} hint="Paused until you verify facts" />
      <Stat label="Applied" value={applied} hint={`${data.applications.filter(a => a.status === 'INTERVIEWING').length} interviewing`} />
    </section>
    <div className="dashboard-grid">
      <section className="panel wide"><div className="panel-head"><div><h2>Recommended internships</h2><p>Ranked by eligibility first, then required-skill coverage.</p></div><button className="text-button" onClick={() => go('Discover')}>View all <ChevronRight size={15} /></button></div>
        {recommended.length ? <div className="job-list">{recommended.map(j => <JobRow key={j.id} job={j} onClick={() => go('Discover')} />)}</div> : <Empty icon={BriefcaseBusiness} title="No internships yet" text="Paste a public job URL or add one manually. Missing fields stay missing." action={() => go('Discover')} />}
      </section>
      <div className="stack">
        {setupLeft > 0 && <section className="panel"><div className="panel-head"><div><h2>Finish setting up</h2><p>{setup.length - setupLeft} of {setup.length} done</p></div></div>
          <div className="checklist">{setup.map(s => <button key={s.label} className={s.done ? 'done' : ''} disabled={s.done} onClick={() => go(s.page)}>{s.done ? <Check /> : <Circle />}{s.label}{!s.done && <ChevronRight size={14} />}</button>)}</div>
        </section>}
        <section className="panel"><div className="panel-head"><div><h2>Needs attention</h2><p>Automation is waiting for you.</p></div><Badge tone={waiting.length + needsInfoJobs ? 'warn' : 'good'}>{waiting.length + needsInfoJobs}</Badge></div>
          {waiting.length + needsInfoJobs ? <div className="stack-sm">
            {waiting.length > 0 && <button className="attention as-button" onClick={() => go('Queue')}><AlertTriangle /><div><b>{waiting.length} application{waiting.length > 1 ? 's' : ''} paused</b><p>A verified answer is required before continuing.</p></div></button>}
            {needsInfoJobs > 0 && <button className="attention as-button" onClick={() => go('Profile')}><AlertTriangle /><div><b>{needsInfoJobs} job{needsInfoJobs > 1 ? 's' : ''} need more facts</b><p>Usually work authorization or sponsorship for that country.</p></div></button>}
          </div> : <div className="all-clear"><ShieldCheck /><b>Everything is under control</b><span>No unresolved application questions.</span></div>}
        </section>
      </div>
      <section className="panel wide"><div className="panel-head"><div><h2>Recent activity</h2><p>A human-readable audit trail.</p></div><button className="text-button" onClick={() => go('Activity')}>Full log <ChevronRight size={15} /></button></div><ActivityList items={data.activity.slice(0, 6)} /></section>
    </div>
  </>
}
