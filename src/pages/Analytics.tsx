import { BarChart3 } from 'lucide-react'
import { Empty, PageHeading, STATUS_LABELS, Stat, eligibilityLabel, type PageProps } from '../ui'

function Bars({ rows, tone = 'accent' }: { rows: [string, number][]; tone?: string }) {
  const max = Math.max(1, ...rows.map(([, n]) => n))
  if (!rows.length) return <p className="muted small">No data yet.</p>
  return <div className="bars">{rows.map(([label, n]) => <div key={label} className="bar-row"><span>{label}</span><div><i className={tone} style={{ width: `${(n / max) * 100}%` }} /></div><b>{n}</b></div>)}</div>
}

const count = <T,>(items: T[], key: (item: T) => string | null | undefined) =>
  Object.entries(items.reduce<Record<string, number>>((all, item) => { const k = key(item); if (k) all[k] = (all[k] ?? 0) + 1; return all }, {})).sort((a, b) => b[1] - a[1])

export function Analytics({ data, go }: PageProps) {
  const applied = data.applications.filter(a => ['APPLIED', 'SUBMITTED', 'INTERVIEWING', 'OFFER', 'REJECTED'].includes(a.status))
  const responses = applied.filter(a => ['INTERVIEWING', 'OFFER', 'REJECTED'].includes(a.status)).length
  const analyzed = data.jobs.filter(j => j.eligibility_result)
  const missing = count(analyzed.flatMap(j => j.eligibility_match?.missing ?? []), s => s).slice(0, 8)
  if (!data.jobs.length) return <><PageHeading eyebrow="Analytics" title="How your search is going" text="Descriptive counts only — no false causal claims." /><section className="panel"><Empty icon={BarChart3} title="No data yet" text="Add a few internships and this page fills in." action={() => go('Discover')} actionLabel="Find jobs" /></section></>
  return <>
    <PageHeading eyebrow="Analytics" title="How your search is going" text="Descriptive counts only — no false causal claims." />
    <section className="stats">
      <Stat label="Jobs tracked" value={data.jobs.length} hint={`${analyzed.length} analyzed`} />
      <Stat label="Applied" value={applied.length} accent hint={`${data.applications.length} in pipeline overall`} />
      <Stat label="Heard back" value={applied.length ? `${Math.round((responses / applied.length) * 100)}%` : '—'} hint={`${responses} of ${applied.length} applications`} />
      <Stat label="Offers" value={data.applications.filter(a => a.status === 'OFFER').length} hint={`${data.applications.filter(a => a.status === 'INTERVIEWING').length} interviewing`} />
    </section>
    <div className="analytics-grid">
      <section className="panel"><div className="panel-head"><div><h2>Eligibility</h2><p>Across analyzed jobs</p></div></div><Bars rows={count(analyzed, j => eligibilityLabel(j.eligibility_result))} /></section>
      <section className="panel"><div className="panel-head"><div><h2>Pipeline</h2><p>Applications by stage</p></div></div><Bars rows={count(data.applications, a => STATUS_LABELS[a.status] ?? a.status)} /></section>
      <section className="panel"><div className="panel-head"><div><h2>Skills you’re most often missing</h2><p>Required by analyzed jobs, absent from your verified skills</p></div></div><Bars rows={missing} tone="warn" /></section>
      <section className="panel"><div className="panel-head"><div><h2>Where jobs come from</h2><p>Application platform</p></div></div><Bars rows={count(data.jobs, j => j.application_platform || 'GENERIC')} /></section>
    </div>
  </>
}
