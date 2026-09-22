import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { Activity, AlertTriangle, BarChart3, BookOpenCheck, Bot, BriefcaseBusiness, Check, ChevronRight, CircleHelp, Command, FileText, Gauge, LayoutDashboard, Library, ListChecks, Moon, Octagon, Play, Plus, Search, Settings, ShieldCheck, Sparkles, Sun, UserRound, X } from 'lucide-react'
import { api } from './api'
import type { Bootstrap, Fact, Job } from './types'

type Page = 'Home' | 'Discover' | 'Queue' | 'Tracker' | 'CV Library' | 'Profile' | 'Answer Vault' | 'Analytics' | 'Activity' | 'Settings'
const navigation: [Page, typeof LayoutDashboard][] = [
  ['Home', LayoutDashboard], ['Discover', Search], ['Queue', ListChecks], ['Tracker', Gauge], ['CV Library', FileText],
  ['Profile', UserRound], ['Answer Vault', BookOpenCheck], ['Analytics', BarChart3], ['Activity', Activity], ['Settings', Settings],
]
const initial: Bootstrap = { settings: {}, facts: [], jobs: [], applications: [], activity: [], cvs: [], answers: [] }

function Badge({ children, tone = 'neutral' }: { children: ReactNode; tone?: 'good' | 'warn' | 'bad' | 'accent' | 'neutral' }) {
  return <span className={`badge ${tone}`}>{children}</span>
}

function Stat({ label, value, accent }: { label: string; value: number | string; accent?: boolean }) {
  return <div className={`stat ${accent ? 'stat-accent' : ''}`}><span>{label}</span><strong>{value}</strong><small>Live local data</small></div>
}

function Wizard({ onComplete }: { onComplete: () => Promise<void> }) {
  const [step, setStep] = useState(0)
  const [busy, setBusy] = useState(false)
  const [cv, setCV] = useState<{ name: string; base64: string } | null>(null)
  const [form, setForm] = useState({ name: '', email: '', university: 'Manipal Institute of Technology', degree: 'Computer Science', graduation: '', skills: '', locations: 'India, UAE, Saudi Arabia, Qatar, Bahrain, Kuwait, Oman, Europe, UK, Singapore' })
  const steps = ['Welcome', 'Import CV', 'Review profile', 'Verify education', 'Verify skills', 'Locations', 'Work authorization', 'Sponsorship', 'Preferences', 'Answer Vault', 'Local AI', 'Safety check']
  const save = async () => {
    setBusy(true)
    if (cv) await api.importCV(cv.name, cv.base64)
    const entries: Fact[] = [
      { category: 'personal', fact_key: 'full_name', value: form.name || null, status: form.name ? 'VERIFIED' : 'UNKNOWN', source: 'FIRST_RUN_WIZARD' },
      { category: 'contact', fact_key: 'email', value: form.email || null, status: form.email ? 'VERIFIED' : 'UNKNOWN', source: 'FIRST_RUN_WIZARD' },
      { category: 'education', fact_key: 'university', value: form.university, status: 'VERIFIED', source: 'FIRST_RUN_WIZARD' },
      { category: 'education', fact_key: 'degree', value: form.degree, status: 'VERIFIED', source: 'FIRST_RUN_WIZARD' },
      { category: 'education', fact_key: 'graduation_date', value: form.graduation || null, status: form.graduation ? 'VERIFIED' : 'UNKNOWN', source: 'FIRST_RUN_WIZARD' },
      { category: 'skills', fact_key: 'verified_skills', value: form.skills.split(',').map(x => x.trim()).filter(Boolean), status: form.skills ? 'VERIFIED' : 'UNKNOWN', source: 'FIRST_RUN_WIZARD' },
      { category: 'preferences', fact_key: 'locations', value: form.locations.split(',').map(x => x.trim()), status: 'VERIFIED', source: 'FIRST_RUN_WIZARD' },
    ]
    await Promise.all(entries.map(api.saveFact))
    await api.settings({ first_run_complete: true })
    await onComplete()
    setBusy(false)
  }
  return <div className="wizard-shell">
    <div className="wizard-brand"><Logo /><p>Private by default. Precise by design.</p></div>
    <div className="wizard-card">
      <div className="wizard-progress"><span>Step {step + 1} of {steps.length}</span><div><i style={{ width: `${((step + 1) / steps.length) * 100}%` }} /></div></div>
      <div className="wizard-icon"><ShieldCheck size={28} /></div>
      <h1>{step === 0 ? 'Welcome to ApplyPilot' : steps[step]}</h1>
      <p className="lede">{step === 0 ? 'Your local internship copilot — built to move fast without ever making up facts about you.' : 'Review each value carefully. Nothing becomes verified until you approve it.'}</p>
      {step === 0 && <div className="promise"><ShieldCheck/><div><b>Zero-guess guarantee</b><span>Unknown personal answers always stop automation.</span></div></div>}
      {step === 1 && <label className="dropzone"><FileText/><b>{cv ? cv.name : 'Choose your CV (PDF)'}</b><span>Extraction is staged as unverified for your review.</span><input type="file" accept="application/pdf" onChange={e => { const file = e.target.files?.[0]; if (!file) return; const reader = new FileReader(); reader.onload = () => setCV({ name: file.name, base64: String(reader.result).split(',')[1] }); reader.readAsDataURL(file) }} /></label>}
      {step === 2 && <div className="fields"><label>Full legal name<input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} placeholder="Not stored until you continue" /></label><label>Email<input value={form.email} onChange={e => setForm({ ...form, email: e.target.value })} type="email" /></label></div>}
      {step === 3 && <div className="fields"><label>University<input value={form.university} onChange={e => setForm({ ...form, university: e.target.value })} /></label><label>Degree<input value={form.degree} onChange={e => setForm({ ...form, degree: e.target.value })} /></label><label>Graduation date<input value={form.graduation} onChange={e => setForm({ ...form, graduation: e.target.value })} type="month" /></label></div>}
      {step === 4 && <label className="field-full">Verified skills, comma separated<textarea value={form.skills} onChange={e => setForm({ ...form, skills: e.target.value })} placeholder="Java, Python, Git, Data Structures" /></label>}
      {step === 5 && <label className="field-full">Enabled locations<textarea value={form.locations} onChange={e => setForm({ ...form, locations: e.target.value })} /></label>}
      {(step === 6 || step === 7) && <div className="attention"><AlertTriangle/><div><b>Country-specific and currently unknown</b><p>ApplyPilot will ask separately for every country. It will never copy citizenship, residence, authorization, or sponsorship answers between countries.</p></div></div>}
      {step === 8 && <div className="choice-grid"><button className="choice active">Internships only<Check/></button><button className="choice">Remote or on-site</button><button className="choice">Review before submit<Check/></button></div>}
      {step === 9 && <div className="attention"><CircleHelp/><div><b>Sensitive answers start as Manual Only</b><p>You can approve exact recurring answers later, with country and company scope.</p></div></div>}
      {step === 10 && <div className="choice-grid"><button className="choice active">Off <Badge tone="good">Default</Badge></button><button className="choice">Ollama</button><button className="choice" disabled>Future provider</button></div>}
      {step === 11 && <div className="safety-list">{['Strict Accuracy Mode is on', 'Dry Run is on', 'Actual submissions are off', 'Unknown answers pause', 'CAPTCHA and MFA pause'].map(x => <div key={x}><Check/> {x}</div>)}</div>}
      <div className="wizard-actions"><button className="button ghost" disabled={step === 0} onClick={() => setStep(step - 1)}>Back</button>{step < steps.length - 1 ? <button className="button primary" onClick={() => setStep(step + 1)}>Continue <ChevronRight size={17}/></button> : <button className="button primary" disabled={busy} onClick={save}>{busy ? 'Saving…' : 'Finish safety setup'} <Check size={17}/></button>}</div>
    </div>
  </div>
}

function Logo() { return <div className="logo"><span><Sparkles size={18}/></span><b>ApplyPilot</b></div> }

function Home({ data, changePage }: { data: Bootstrap; changePage: (p: Page) => void }) {
  const attention = data.applications.filter(a => a.status === 'WAITING_FOR_USER' || a.status === 'NEEDS_INFO').length
  return <>
    <header className="page-heading"><div><p>Tuesday, September 22</p><h1>Good afternoon, Arnav</h1><span>Here’s what needs your attention today.</span></div><button className="button primary" onClick={() => changePage('Discover')}><Plus size={17}/> Add job</button></header>
    <section className="stats"><Stat label="Internships found" value={data.jobs.length}/><Stat label="Ready to apply" value={data.applications.filter(a => a.status === 'READY_FOR_REVIEW').length} accent/><Stat label="Need your answer" value={attention}/><Stat label="Applied" value={data.applications.filter(a => a.status === 'SUBMITTED').length}/></section>
    <div className="dashboard-grid">
      <section className="panel wide"><div className="panel-head"><div><h2>Recommended internships</h2><p>Ranked by eligibility first, then skill match.</p></div><button className="text-button" onClick={() => changePage('Discover')}>View all <ChevronRight size={15}/></button></div>
        {data.jobs.length ? <div className="job-list">{data.jobs.slice(0, 4).map(j => <JobRow key={j.id} job={j}/>)}</div> : <Empty icon={BriefcaseBusiness} title="No internships yet" text="Paste a public job URL or add one manually. Missing fields stay missing." action={() => changePage('Discover')} />}
      </section>
      <section className="panel"><div className="panel-head"><div><h2>Needs attention</h2><p>Automation is waiting for you.</p></div><Badge tone={attention ? 'warn' : 'good'}>{attention}</Badge></div>
        {attention ? <div className="attention"><AlertTriangle/><div><b>{attention} application{attention > 1 ? 's' : ''} paused</b><p>A verified answer is required before continuing.</p></div></div> : <div className="all-clear"><ShieldCheck/><b>Everything is under control</b><span>No unresolved application questions.</span></div>}
      </section>
      <section className="panel wide"><div className="panel-head"><div><h2>Recent activity</h2><p>A human-readable audit trail.</p></div></div><ActivityList items={data.activity.slice(0, 6)} /></section>
    </div>
  </>
}

function JobRow({ job }: { job: Job }) { return <div className="job-row"><div className="company-mark">{(job.company || '?').slice(0, 1)}</div><div><b>{job.role || 'Role needs review'}</b><span>{job.company || 'Company unknown'} · {job.location || 'Location unknown'}</span></div><div className="tags"><Badge tone="accent">{job.application_platform || 'GENERIC'}</Badge><Badge>{job.extraction_status}</Badge></div><ChevronRight size={18}/></div> }

function Empty({ icon: Icon, title, text, action }: { icon: typeof BriefcaseBusiness; title: string; text: string; action?: () => void }) { return <div className="empty"><Icon/><b>{title}</b><span>{text}</span>{action && <button className="button subtle" onClick={action}>Get started</button>}</div> }

function ActivityList({ items }: { items: Bootstrap['activity'] }) { return <div className="activity-list">{items.length ? items.map(item => <div key={item.id}><span className={`activity-dot ${item.level.toLowerCase()}`} /><time>{new Date(item.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</time><b>{item.action.replaceAll('_', ' ').toLowerCase()}</b></div>) : <Empty icon={Activity} title="No activity yet" text="Every important automated action will appear here." />}</div> }

function Discover({ data, refresh }: { data: Bootstrap; refresh: () => Promise<void> }) {
  const [url, setUrl] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [analysis, setAnalysis] = useState<Record<string, { result: string; checks: { name: string; result: string; explanation: string }[]; match: { strong: string[]; partial: string[]; missing: string[] } }>>({})
  const importJob = async () => { setBusy(true); setError(''); try { await api.importJob(url); setUrl(''); await refresh() } catch (e) { setError(e instanceof Error ? e.message : 'Import failed safely') } finally { setBusy(false) } }
  const analyze = async (id: string) => { try { setAnalysis({ ...analysis, [id]: await api.analyzeJob(id) }) } catch (e) { setError(e instanceof Error ? e.message : 'Analysis failed') } }
  const queue = async (id: string) => { try { await api.queueJob(id); await refresh() } catch (e) { setError(e instanceof Error ? e.message : 'Queue failed') } }
  return <><header className="page-heading"><div><p>Discovery</p><h1>Find a role worth applying to</h1><span>Public pages only. Blocked or protected pages fall back to manual entry.</span></div></header>
    <section className="import-bar"><Search/><input value={url} onChange={e => setUrl(e.target.value)} placeholder="Paste an internship URL…" onKeyDown={e => e.key === 'Enter' && url && importJob()} /><button className="button primary" disabled={!url || busy} onClick={importJob}>{busy ? 'Analyzing…' : 'Import & analyze'}</button></section>
    {error && <div className="error-banner"><AlertTriangle/> <span>{error}</span><button onClick={() => setError('')}><X/></button></div>}
    <section className="panel"><div className="panel-head"><div><h2>Imported internships</h2><p>Extracted facts remain unverified until reviewed.</p></div><Badge>{data.jobs.length} total</Badge></div>
      {data.jobs.length ? <div className="job-cards">{data.jobs.map(job => <article className="job-card" key={job.id}><JobRow job={job}/><p>{job.description.slice(0, 240) || 'No description was extracted. Add details manually; ApplyPilot will not fabricate them.'}</p><div className="skill-line">{job.required_skills?.slice(0, 7).map(s => <Badge key={s}>{s}</Badge>)}</div>{analysis[job.id] && <div className="analysis-box"><div><Badge tone={analysis[job.id].result === 'NEEDS_INFORMATION' ? 'warn' : 'good'}>{analysis[job.id].result}</Badge><span>Strong: {analysis[job.id].match.strong.join(', ') || 'none yet'}</span><span>Missing: {analysis[job.id].match.missing.join(', ') || 'none detected'}</span></div>{analysis[job.id].checks.map(c => <small key={c.name}><b>{c.name}: {c.result}</b> — {c.explanation}</small>)}</div>}<footer><button className="button ghost" onClick={() => analyze(job.id)}>Analyze eligibility</button><button className="button primary" onClick={() => queue(job.id)}>Add to queue</button></footer></article>)}</div> : <Empty icon={Search} title="Paste your first internship" text="ApplyPilot will extract only what the page actually says." />}
    </section></>
}

function Queue({ data, refresh }: { data: Bootstrap; refresh: () => Promise<void> }) {
  const [result, setResult] = useState<Record<string, string>>({})
  const sampleFields = [
    { selector: '#name', label: 'Full legal name', required: true }, { selector: '#email', label: 'Email address', required: true },
    { selector: '#sponsor', label: 'Will you now or in the future require sponsorship?', required: true }, { selector: '#custom', label: 'Agree to all legal declarations', required: true },
  ]
  const run = async (id: string) => { const value = await api.dryRun(id, sampleFields); setResult({ ...result, [id]: `${value.filled_count} filled · ${value.unknown_count} paused · ${value.status}` }); await refresh() }
  const validate = async (id: string) => { const value = await api.validate(id); setResult({ ...result, [id]: value.blocked ? `Blocked: ${value.failures.join(' • ')}` : 'Ready for review' }) }
  return <><header className="page-heading"><div><p>Application queue</p><h1>Safe automation workspace</h1><span>Dry Run is active. No submit button can be pressed.</span></div><Badge tone="good"><ShieldCheck size={13}/> DRY RUN</Badge></header>
    <section className="panel">{data.applications.length ? <div className="queue-list">{data.applications.map(app => <div className="queue-card" key={app.id}><div><Badge tone={app.status.includes('WAITING') ? 'warn' : 'accent'}>{app.status}</Badge><h3>{app.role || 'Role'} · {app.company || 'Company'}</h3><p>{app.location || 'Location unknown'} · {app.mode.replaceAll('_', ' ')}</p></div><div className="queue-actions"><button className="button ghost" onClick={() => run(app.id)}><Play size={16}/> Run safe fill</button><button className="button primary" onClick={() => validate(app.id)}><ShieldCheck size={16}/> Validate</button></div>{result[app.id] && <div className="run-result"><AlertTriangle size={16}/>{result[app.id]}</div>}</div>)}</div> : <Empty icon={ListChecks} title="Your queue is empty" text="Analyze a job, then add it here for a controlled dry run." />}</section></>
}

function Profile({ data, refresh }: { data: Bootstrap; refresh: () => Promise<void> }) {
  const groups = useMemo(() => data.facts.reduce<Record<string, Fact[]>>((all, fact) => {
    ;(all[fact.category] ||= []).push(fact)
    return all
  }, {}), [data.facts])
  return <><header className="page-heading"><div><p>Truth Layer</p><h1>Verified profile</h1><span>These are the only facts automation is allowed to use.</span></div><Badge tone="good"><ShieldCheck size={13}/> STRICT</Badge></header><div className="profile-grid">{Object.entries(groups).map(([category, facts]) => <section className="panel" key={category}><div className="panel-head"><h2>{category.replaceAll('_', ' ')}</h2><Badge>{facts?.length || 0}</Badge></div>{facts?.map(f => <div className="fact" key={f.id}><div><b>{f.fact_key.replaceAll('_', ' ')}</b><span>{Array.isArray(f.value) ? f.value.join(', ') : String(f.value ?? 'Not provided')}</span>{f.country_code && <small>{f.country_code} only</small>}</div><Badge tone={f.status === 'VERIFIED' ? 'good' : f.status === 'EXPIRED' ? 'bad' : 'warn'}>{f.status}</Badge></div>)}</section>)}<button className="add-fact" onClick={async () => { await api.saveFact({ category: 'contact', fact_key: `new_fact_${Date.now()}`, value: null, status: 'UNKNOWN', source: 'USER' }); await refresh() }}><Plus/>Add an unknown fact placeholder</button></div></>
}

function SettingsPage({ data, refresh }: { data: Bootstrap; refresh: () => Promise<void> }) {
  const toggle = async (key: string, value: boolean) => { await api.settings({ [key]: value }); await refresh() }
  return <><header className="page-heading"><div><p>Control center</p><h1>Safety & local AI</h1><span>Conservative defaults are locked in until you explicitly change them.</span></div></header><section className="panel settings-list"><SettingRow title="Strict Accuracy Mode" text="Unknown personal answers always pause." active={Boolean(data.settings.strict_accuracy_mode)} onChange={v => toggle('strict_accuracy_mode', v)} locked/><SettingRow title="Dry Run" text="Fill and validate, but never submit." active={Boolean(data.settings.dry_run)} onChange={v => toggle('dry_run', v)}/><SettingRow title="Actual submissions" text="Requires an explicit opt-in and still runs validation." active={Boolean(data.settings.actual_submission_enabled)} onChange={v => toggle('actual_submission_enabled', v)}/><div className="setting-row"><div className="setting-icon"><Bot/></div><div><b>Local AI</b><span>Off · endpoint http://localhost:11434</span></div><Badge tone="good">Optional</Badge></div></section></>
}

function SettingRow({ title, text, active, onChange, locked }: { title: string; text: string; active: boolean; onChange: (v: boolean) => void; locked?: boolean }) { return <div className="setting-row"><div className="setting-icon"><ShieldCheck/></div><div><b>{title}</b><span>{text}</span></div>{locked && <Badge>Recommended</Badge>}<button className={`toggle ${active ? 'on' : ''}`} onClick={() => onChange(!active)} aria-label={`Toggle ${title}`}><i /></button></div> }

function GenericPage({ page, data }: { page: Page; data: Bootstrap }) {
  const map: Record<string, [typeof BriefcaseBusiness, string]> = { Tracker: [Gauge, 'Track every application from saved to offer.'], 'CV Library': [Library, 'Originals stay immutable; tailored versions keep an audit trail.'], 'Answer Vault': [BookOpenCheck, 'Reusable answers with explicit scope and approval.'], Analytics: [BarChart3, 'Outcome metrics without false causal claims.'], Activity: [Activity, 'Every important action, source, pause, and failure.'] }
  const [Icon, text] = map[page] || ([BriefcaseBusiness, 'Coming next'] as [typeof BriefcaseBusiness, string])
  return <><header className="page-heading"><div><p>ApplyPilot</p><h1>{page}</h1><span>{text}</span></div></header><section className="panel">{page === 'Activity' ? <ActivityList items={data.activity}/> : <Empty icon={Icon} title={`${page} is ready for data`} text="The underlying schema is active; this workspace will populate as you use the end-to-end flow." />}</section></>
}

function AppShell({ data, refresh }: { data: Bootstrap; refresh: () => Promise<void> }) {
  const [page, setPage] = useState<Page>('Home')
  const [dark, setDark] = useState(true)
  const [palette, setPalette] = useState(false)
  useEffect(() => { const key = (e: KeyboardEvent) => { if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); setPalette(x => !x) } if (e.key === 'Escape') setPalette(false) }; addEventListener('keydown', key); return () => removeEventListener('keydown', key) }, [])
  return <div className={dark ? 'app dark' : 'app light'}>
    <aside><Logo/><nav>{navigation.map(([name, Icon]) => <button key={name} className={page === name ? 'active' : ''} onClick={() => setPage(name)}><Icon size={18}/>{name}{name === 'Queue' && data.applications.length > 0 && <em>{data.applications.length}</em>}</button>)}</nav><div className="sidebar-foot"><div className="privacy"><ShieldCheck/><div><b>Local & private</b><span>Data stays on this device</span></div></div><button onClick={() => setDark(!dark)}>{dark ? <Sun/> : <Moon/>}{dark ? 'Light mode' : 'Dark mode'}</button></div></aside>
    <main><div className="topbar"><button className="command-button" onClick={() => setPalette(true)}><Search/>Search or jump to…<kbd>Ctrl K</kbd></button><div className="status"><span className="status-dot"/> Automation idle</div></div><div className="content">{page === 'Home' ? <Home data={data} changePage={setPage}/> : page === 'Discover' ? <Discover data={data} refresh={refresh}/> : page === 'Queue' ? <Queue data={data} refresh={refresh}/> : page === 'Profile' ? <Profile data={data} refresh={refresh}/> : page === 'Settings' ? <SettingsPage data={data} refresh={refresh}/> : <GenericPage page={page} data={data}/>}</div></main>
    {palette && <div className="modal-backdrop" onMouseDown={() => setPalette(false)}><div className="palette" onMouseDown={e => e.stopPropagation()}><div><Command/><input autoFocus placeholder="Type a command…" /></div>{navigation.slice(0, 7).map(([name, Icon]) => <button key={name} onClick={() => { setPage(name); setPalette(false) }}><Icon/>{name}<span>Open</span></button>)}</div></div>}
  </div>
}

export function App() {
  const [data, setData] = useState<Bootstrap>(initial)
  const [loaded, setLoaded] = useState(false)
  const [offline, setOffline] = useState('')
  const refresh = async () => { try { setData(await api.bootstrap()); setOffline('') } catch (e) { setOffline(e instanceof Error ? e.message : 'Local service unavailable') } finally { setLoaded(true) } }
  useEffect(() => { refresh() }, [])
  if (!loaded) return <div className="loading"><Logo/><span>Opening your local workspace…</span></div>
  if (offline) return <div className="loading error-state"><Octagon/><h1>Local service isn’t running</h1><p>{offline}</p><code>npm run dev:api</code><button className="button primary" onClick={refresh}>Try again</button></div>
  return data.settings.first_run_complete ? <AppShell data={data} refresh={refresh}/> : <Wizard onComplete={refresh}/>
}
