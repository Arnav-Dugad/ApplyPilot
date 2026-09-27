import { useEffect, useState } from 'react'
import { AlertTriangle, Brain, Building2, CheckCircle2, Clock, FileSearch, Globe2, ListChecks, Play, Plus, Radar, Sparkles, Trash2, Zap } from 'lucide-react'
import { Sankey } from '../components/Sankey'
import { api } from '../api'
import type { AutopilotConfig, AutopilotRun, RunEvent, SourceInfo } from '../types'
import { AnimatedNumber, AutopilotOrb } from '../motion'
import { Badge, Empty, PageHeading, formatDateTime, relativeTime, useAction, useNotify, type PageProps } from '../ui'

const STEP_ICON: Record<string, typeof Radar> = { scan: Radar, worldwide: Globe2, analyze: Brain, ai: Sparkles, queue: ListChecks, prepare: FileSearch, done: CheckCircle2, error: AlertTriangle }
const INTERVALS = [1, 3, 6, 12, 24]

export function Autopilot({ data, refresh, go }: PageProps) {
  const { run, busy } = useAction(refresh)
  const notify = useNotify()
  const [url, setUrl] = useState('')
  const state = data.autopilot
  const cfg = state.config
  const running = Boolean(state.running)
  const current = state.runs[0]
  const followed = new Set(data.watchlist.map(w => `${w.platform}:${w.slug.toLowerCase()}`))
  const catalog = data.catalog.filter(c => !followed.has(`${c.platform}:${c.slug.toLowerCase()}`))
  const aiReady = Boolean((data.settings.ollama as { provider?: string } | undefined)?.provider === 'OLLAMA')

  const save = (patch: Partial<AutopilotConfig>, message?: string) => run('config', () => api.settings({ autopilot: { ...cfg, ...patch } }), message)
  const follow = async (target: string, label?: string) => {
    const result = await run(`follow-${target}`, () => api.follow(target))
    if (result) { notify(`Following ${result.company} — ${result.internships} internship${result.internships === 1 ? '' : 's'} open now`); if (!label) setUrl('') }
  }
  const start = () => run('run', () => api.runAutopilot(), 'Autopilot is searching for internships…')
  const [sources, setSources] = useState<SourceInfo[] | null>(null)
  useEffect(() => { api.sources().then(r => setSources(r.sources)).catch(() => setSources([])) }, [running, data.jobs.length])
  const toggleSource = async (key: string, on: boolean) => {
    setSources(list => list && list.map(x => x.key === key ? { ...x, enabled: on } : x))
    await run(`src-${key}`, () => api.settings({ sources: { [key]: on } }), on ? 'Source turned on' : 'Source turned off')
  }
  const worldwide = cfg.worldwide !== false

  return <>
    <PageHeading eyebrow="Autopilot" title="Your internship search, on autopilot" text="Every few hours it searches job lists across the whole internet, checks each job against your profile, and gets the best ones ready. You answer a few questions and press submit." />

    <section className={`autopilot-hero ${running ? 'running' : cfg.enabled ? 'on' : 'off'}`}>
      <AutopilotOrb state={running ? 'running' : cfg.enabled ? 'idle' : 'off'} size={132} />
      <div className="hero-copy">
        <Badge tone={running ? 'accent' : cfg.enabled ? 'good' : 'neutral'}>{running ? 'Working now' : cfg.enabled ? 'On' : 'Off'}</Badge>
        <h2>{running ? 'Autopilot is working…' : cfg.enabled ? `Autopilot runs every ${cfg.interval_hours}h` : 'Autopilot is off'}</h2>
        <p>{running ? (current?.events.at(-1)?.message ?? 'Starting up') : cfg.enabled ? `Next run ${state.next_run_at ? relativeTime(state.next_run_at) : 'soon'} · while ApplyPilot is open (it keeps running in the tray)` : 'Turn it on and ApplyPilot keeps finding internships for you, even while you study.'}</p>
        <div className="hero-actions">
          <button className={`button ${cfg.enabled ? 'ghost' : 'primary'} large`} disabled={busy === 'config'} onClick={() => save({ enabled: !cfg.enabled }, cfg.enabled ? 'Autopilot paused' : 'Autopilot is on')}><Zap size={17} /> {cfg.enabled ? 'Pause Autopilot' : 'Turn on Autopilot'}</button>
          <button className="button ghost large" disabled={running || busy === 'run'} onClick={start}><Play size={16} /> Run now</button>
        </div>
      </div>
      {current && <div className="hero-stats">
        {([['new', 'New jobs'], ['queued', 'Getting ready'], ['ready', 'Ready'], ['needs_you', 'Need you']] as const).map(([key, label]) => <div key={key}><strong><AnimatedNumber value={current.summary[key] ?? 0} /></strong><span>{label}</span></div>)}
        <small>{current.status === 'RUNNING' ? 'This run' : `Last run ${relativeTime(current.finished_at || current.started_at)}`}</small>
      </div>}
    </section>

    <div className="autopilot-grid">
      <section className="panel"><div className="panel-head"><div><h2>Live timeline</h2><p>{current ? `${current.trigger === 'SCHEDULE' ? 'Scheduled' : 'Manual'} run · ${formatDateTime(current.started_at)}` : 'Every step Autopilot takes shows up here'}</p></div>{running && <span className="live-dot">Live</span>}</div>
        {current ? <Timeline events={current.events} running={current.status === 'RUNNING'} /> : <Empty icon={Radar} title="No runs yet" text="Press Run now — it searches worldwide job lists straight away." />}
        {(data.inbox.questions.length > 0 && !running) && <button className="attention as-button inbox-cta" onClick={() => go('Inbox')}><Sparkles /><div><b>{data.inbox.questions.length} question{data.inbox.questions.length > 1 ? 's' : ''} waiting</b><p>Answer once in your Inbox — every application that asked it updates instantly.</p></div></button>}
      </section>

      <section className="panel rules"><div className="panel-head"><div><h2>Rules</h2><p>What Autopilot is allowed to do on its own</p></div></div>
        <label className="rule"><span><Clock size={15} /> Run every</span><select value={cfg.interval_hours} onChange={e => save({ interval_hours: Number(e.target.value) })}>{INTERVALS.map(h => <option key={h} value={h}>{h} hour{h > 1 ? 's' : ''}</option>)}</select></label>
        <label className="rule slider"><span>Get jobs ready when they score at least <b>{cfg.min_score}</b></span><input type="range" min={30} max={95} step={5} value={cfg.min_score} onChange={e => save({ min_score: Number(e.target.value) })} /></label>
        <Rule label="Search the whole internet" hint="Worldwide internship lists, not just companies you follow" on={worldwide} set={v => save({ worldwide: v }, v ? 'Worldwide search on' : 'Only followed companies')} />
        <Rule label="Internships only" hint="Skip full-time jobs" on={cfg.internships_only} set={v => save({ internships_only: v })} />
        <Rule label="Only places I'd work" hint="From your profile; unknown places are kept" on={cfg.location_filter} set={v => save({ location_filter: v })} />
        <Rule label="Get the best jobs ready" hint="Ones you qualify for, above your score" on={cfg.auto_queue} set={v => save({ auto_queue: v })} />
        <Rule label="Pre-fill application forms" hint="Answer every question it can from your profile" on={cfg.auto_prepare} set={v => save({ auto_prepare: v })} />
        <Rule label="AI job summaries" hint={aiReady ? 'Local AI, on this computer' : 'Set up local AI in Settings'} on={cfg.ai_summaries && aiReady} disabled={!aiReady} set={v => save({ ai_summaries: v })} />
        <Rule label="AI cover-letter drafts" hint="Drafts wait for your approval" on={cfg.ai_cover_letters && aiReady} disabled={!aiReady} set={v => save({ ai_cover_letters: v })} />
      </section>
    </div>

    {data.jobs.length > 0 && <section className="panel"><div className="panel-head"><div><h2>Your pipeline</h2><p>{running ? 'Watch new jobs flow in as Autopilot finds them.' : 'Every job, from found to offer. Hover a stage to trace it.'}</p></div>{running && <span className="live-dot">Live</span>}</div>
      <Sankey jobs={data.jobs} apps={data.applications} height={260} live={running} /></section>}

    <section className="panel" id="sources"><div className="panel-head"><div><h2><Globe2 size={15} /> Where Autopilot looks</h2><p>Free public job lists that allow automatic reading. Sites that forbid it — LinkedIn, Indeed, Internshala — are never touched.</p></div>
      <Badge tone={worldwide ? 'good' : 'neutral'}>{worldwide ? `${sources?.filter(x => x.enabled).length ?? 0} lists on` : 'Worldwide search off'}</Badge></div>
      {sources === null ? <p className="muted small">Loading…</p> : <div className={`source-grid ${worldwide ? '' : 'off'}`}>{sources.map(src => <div key={src.key} className={`source-card ${src.enabled ? 'on' : ''}`}>
        <div><b>{src.name}</b><span>{src.about}</span>
          <small className={src.status?.error ? 'warn-text' : ''}>{src.status?.error ? `Couldn't reach it last time` : src.status ? `Last search: ${src.status.found} openings, ${src.status.new} new for you · ${relativeTime(src.status.at)}` : 'Not searched yet'}{src.jobs ? ` · ${src.jobs} saved` : ''}</small></div>
        <button className={`toggle ${src.enabled ? 'on' : ''}`} disabled={!worldwide || busy === `src-${src.key}`} onClick={() => toggleSource(src.key, !src.enabled)} aria-label={`Toggle ${src.name}`}><i /></button>
      </div>)}</div>}
    </section>

    <section className="panel"><div className="panel-head"><div><h2>Companies you follow</h2><p>Autopilot also checks these companies' own career pages directly, and reads their real application forms.</p></div><Badge>{data.watchlist.length} following</Badge></div>
      <div className="follow-bar"><Building2 size={17} /><input value={url} onChange={e => setUrl(e.target.value)} onKeyDown={e => e.key === 'Enter' && url.trim() && follow(url.trim())} placeholder="Paste any careers link, e.g. jobs.lever.co/company or boards.greenhouse.io/company" /><button className="button primary" disabled={!url.trim() || busy === `follow-${url.trim()}`} onClick={() => follow(url.trim())}>{busy === `follow-${url.trim()}` ? 'Checking…' : 'Follow'}</button></div>
      {data.watchlist.length > 0 && <div className="watch-grid">{data.watchlist.map(w => <article key={w.id} className="watch-card">
        <div className="company-mark">{w.company.slice(0, 1)}</div>
        <div><b>{w.company}</b><span>{w.platform.toLowerCase()} · {w.internships_seen} internship{w.internships_seen === 1 ? '' : 's'} of {w.jobs_seen}</span><small className={w.last_status?.startsWith('Error') ? 'warn-text' : ''}>{w.last_scanned_at ? `Scanned ${relativeTime(w.last_scanned_at)}` : 'Not scanned yet'}{w.last_status?.startsWith('Error') ? ` · ${w.last_status}` : ''}</small></div>
        <button className="icon-button" aria-label={`Unfollow ${w.company}`} onClick={() => run(`unfollow-${w.id}`, () => api.unfollow(w.id), `Unfollowed ${w.company}`)}><Trash2 /></button>
      </article>)}</div>}
      {catalog.length > 0 && <><p className="catalog-title">Popular companies with internships · one click to follow</p>
        <div className="catalog">{catalog.map(c => { const key = `${c.platform.toLowerCase()}:${c.slug}`; return <button key={key} className="catalog-chip" disabled={busy === `follow-${key}`} onClick={() => follow(key, c.company)}>{busy === `follow-${key}` ? <span className="mini-spinner" /> : <Plus size={13} />}{c.company}</button> })}</div></>}
    </section>

    {state.runs.length > 1 && <section className="panel"><div className="panel-head"><div><h2>Run history</h2><p>Recent Autopilot runs</p></div></div>
      <div className="run-history">{state.runs.map(r => <RunRow key={r.id} run={r} />)}</div></section>}
  </>
}

function Rule({ label, hint, on, set, disabled }: { label: string; hint: string; on: boolean; set: (v: boolean) => void; disabled?: boolean }) {
  return <div className={`rule ${disabled ? 'disabled' : ''}`}><span>{label}<small>{hint}</small></span><button className={`toggle ${on ? 'on' : ''}`} disabled={disabled} onClick={() => set(!on)} aria-label={`Toggle ${label}`}><i /></button></div>
}

function Timeline({ events, running }: { events: RunEvent[]; running: boolean }) {
  return <ol className="timeline">{events.map((e, i) => { const Icon = STEP_ICON[e.step] ?? Radar; return <li key={`${e.at}-${i}`} className={`${e.level.toLowerCase()} ${e.step}`} style={{ animationDelay: `${Math.min(i, 8) * 40}ms` }}><span className="tl-icon"><Icon size={14} /></span><div><b>{e.message}</b><time>{new Date(e.at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</time></div></li> })}
    {running && <li className="pending"><span className="tl-icon"><span className="mini-spinner" /></span><div><b>Working…</b></div></li>}</ol>
}

function RunRow({ run }: { run: AutopilotRun }) {
  const s = run.summary
  return <div className="run-row"><Badge tone={run.status === 'FAILED' ? 'bad' : run.status === 'RUNNING' ? 'accent' : 'good'}>{run.status.toLowerCase()}</Badge><span>{formatDateTime(run.started_at)}</span><span>{run.trigger === 'SCHEDULE' ? 'Scheduled' : 'Manual'}</span><span>{s.new ?? 0} new{s.worldwide ? ` (${s.worldwide} worldwide)` : ''} · {s.queued ?? 0} getting ready · {s.ready ?? 0} ready · {s.needs_you ?? 0} need you</span></div>
}
