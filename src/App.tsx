import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Activity, BarChart3, Bell, BookOpenCheck, Command, FileText, Gauge, Inbox as InboxIcon, LayoutDashboard, ListChecks, Moon, Octagon, Play, Search, Settings, ShieldCheck, Sun, UserRound, Zap } from 'lucide-react'
import { api } from './api'
import { JobDrawer } from './JobDrawer'
import type { Bootstrap } from './types'
import { ACTIVE_STATUSES, ActivityList, Logo, NotifyProvider, PageHeading, relativeTime, useNotify, type Page } from './ui'
import { Analytics } from './pages/Analytics'
import { AnswerVault } from './pages/AnswerVault'
import { Autopilot } from './pages/Autopilot'
import { CVLibrary } from './pages/CVLibrary'
import { Discover } from './pages/Discover'
import { Home } from './pages/Home'
import { Inbox } from './pages/Inbox'
import { Profile } from './pages/Profile'
import { Queue } from './pages/Queue'
import { SettingsPage } from './pages/Settings'
import { Tracker } from './pages/Tracker'
import { Wizard } from './pages/Wizard'

const navigation: [Page, typeof LayoutDashboard][] = [
  ['Home', LayoutDashboard], ['Autopilot', Zap], ['Inbox', InboxIcon], ['Discover', Search], ['Queue', ListChecks], ['Tracker', Gauge],
  ['CV Library', FileText], ['Profile', UserRound], ['Answer Vault', BookOpenCheck], ['Analytics', BarChart3], ['Activity', Activity], ['Settings', Settings],
]
const initial: Bootstrap = {
  settings: {}, facts: [], jobs: [], applications: [], activity: [], cvs: [], answers: [], watchlist: [], catalog: [], notifications: [],
  inbox: { questions: [], suggestions: [], drafts: [] },
  autopilot: { config: { enabled: false, interval_hours: 6, min_score: 60, auto_queue: true, auto_prepare: true, location_filter: true, internships_only: true, ai_summaries: true, ai_cover_letters: false }, running: null, next_run_at: null, runs: [] },
}
const THEME_KEY = 'applypilot.theme'

function readTheme() {
  try { return localStorage.getItem(THEME_KEY) !== 'light' } catch { return true }
}

function ActivityPage({ data }: { data: Bootstrap }) {
  const [query, setQuery] = useState('')
  const items = data.activity.filter(a => !query || `${a.action} ${JSON.stringify(a.details ?? {})}`.toLowerCase().includes(query.toLowerCase().replaceAll(' ', '_')))
  return <><PageHeading eyebrow="Activity" title="Audit trail" text="Every important action, source, pause, and failure — the latest 200 events." /><section className="panel"><div className="toolbar"><input className="search-input" value={query} onChange={e => setQuery(e.target.value)} placeholder="Filter events…" /></div><ActivityList items={items} detailed /></section></>
}

function Notifications({ data, refresh, go }: { data: Bootstrap; refresh: () => Promise<void>; go: (p: Page) => void }) {
  const [open, setOpen] = useState(false)
  const unread = data.notifications.filter(n => !n.read).length
  const toggle = async () => { setOpen(!open); if (!open && unread) { await api.readNotifications(); await refresh() } }
  return <div className="bell-wrap">
    <button className={`icon-button bell ${unread ? 'has-unread' : ''}`} onClick={toggle} aria-label={`Notifications${unread ? `, ${unread} unread` : ''}`}><Bell />{unread > 0 && <em>{unread}</em>}</button>
    {open && <><div className="click-away" onClick={() => setOpen(false)} /><div className="bell-panel">
      <header>Notifications</header>
      {data.notifications.length ? data.notifications.slice(0, 12).map(n => <button key={n.id} className={n.read ? '' : 'unread'} onClick={() => { if (n.page) go(n.page as Page); setOpen(false) }}><b>{n.title}</b>{n.body && <span>{n.body}</span>}<time>{relativeTime(n.created_at)}</time></button>) : <p>Autopilot will tell you what it finds.</p>}
    </div></>}
  </div>
}

function AppShell({ data, refresh }: { data: Bootstrap; refresh: () => Promise<void> }) {
  const notify = useNotify()
  const [page, setPage] = useState<Page>('Home')
  const [dark, setDarkState] = useState(readTheme)
  const [palette, setPalette] = useState(false)
  const [query, setQuery] = useState('')
  const [selected, setSelected] = useState(0)
  const [jobId, setJobId] = useState<string | null>(null)
  const setDark = (value: boolean) => { setDarkState(value); try { localStorage.setItem(THEME_KEY, value ? 'dark' : 'light') } catch { /* preference is optional */ } }
  const go = useCallback((p: Page) => { setPage(p); document.querySelector('main')?.scrollTo({ top: 0 }) }, [])

  const commands = useMemo(() => [
    { label: 'Run Autopilot now', hint: 'Action', icon: Play, run: async () => { try { await api.runAutopilot(); notify('Autopilot is scanning your companies…'); setPage('Autopilot'); await refresh() } catch (e) { notify(e instanceof Error ? e.message : 'Could not start', 'bad') } } },
    ...navigation.map(([name, Icon]) => ({ label: name, hint: 'Open', icon: Icon, run: () => go(name) })),
    ...data.jobs.slice(0, 200).map(j => ({ label: `${j.role} · ${j.company}`, hint: `${j.score?.score ?? '—'}`, icon: Search, run: () => setJobId(j.id) })),
    { label: dark ? 'Switch to light mode' : 'Switch to dark mode', hint: 'Theme', icon: dark ? Sun : Moon, run: () => setDark(!dark) },
  ].filter(c => c.label.toLowerCase().includes(query.trim().toLowerCase())).slice(0, 12), [query, dark, data.jobs, go, notify, refresh])

  useEffect(() => {
    const key = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); setPalette(x => !x) }
      if (e.key === 'Escape') setPalette(false)
    }
    addEventListener('keydown', key)
    return () => removeEventListener('keydown', key)
  }, [])
  useEffect(() => { if (palette) { setQuery(''); setSelected(0) } }, [palette])
  useEffect(() => { document.documentElement.style.colorScheme = dark ? 'dark' : 'light' }, [dark])

  // Stream progress while something is working; otherwise check in quietly for scheduled runs.
  const busy = Boolean(data.autopilot.running) || data.applications.some(a => a.browser_run?.status === 'RUNNING')
  const wasBusy = useRef(busy)
  useEffect(() => {
    const id = setInterval(refresh, busy ? 1500 : 15000)
    if (wasBusy.current && !busy && data.autopilot.runs[0]?.status === 'COMPLETED') notify(data.autopilot.runs[0].events.at(-1)?.message ?? 'Autopilot finished')
    wasBusy.current = busy
    return () => clearInterval(id)
  }, [busy, refresh])

  const choose = (index: number) => { commands[index]?.run(); setPalette(false) }
  const active = data.applications.filter(a => ACTIVE_STATUSES.includes(a.status)).length
  const inboxCount = data.inbox.questions.length + data.inbox.suggestions.length + data.inbox.drafts.length
  const props = { data, refresh, go, openJob: setJobId }
  const running = Boolean(data.autopilot.running)

  return <div className={dark ? 'app dark' : 'app light'}>
    <aside><Logo /><nav>{navigation.map(([name, Icon]) => <button key={name} className={page === name ? 'active' : ''} onClick={() => go(name)}><Icon size={18} />{name}
      {name === 'Queue' && active > 0 && <em>{active}</em>}
      {name === 'Inbox' && inboxCount > 0 && <em className="attention-badge">{inboxCount}</em>}
      {name === 'Autopilot' && (running ? <span className="nav-pulse" title="Running" /> : data.autopilot.config.enabled && <span className="nav-dot" title="On" />)}
    </button>)}</nav>
      <div className="sidebar-foot"><div className="privacy"><ShieldCheck /><div><b>Local & private</b><span>Data stays on this device</span></div></div><button onClick={() => setDark(!dark)}>{dark ? <Sun /> : <Moon />}{dark ? 'Light mode' : 'Dark mode'}</button></div></aside>
    <main><div className="topbar"><button className="command-button" onClick={() => setPalette(true)}><Search />Search jobs, pages, actions…<kbd>Ctrl K</kbd></button>
      <div className="topbar-right"><button className="status" onClick={() => go('Autopilot')}><span className={`status-dot ${running ? 'running' : data.inbox.questions.length ? 'warn' : ''}`} /> {running ? (data.autopilot.runs[0]?.events.at(-1)?.message ?? 'Autopilot running') : data.autopilot.config.enabled ? `Autopilot on · next ${data.autopilot.next_run_at ? relativeTime(data.autopilot.next_run_at) : 'soon'}` : 'Autopilot off'}</button><Notifications data={data} refresh={refresh} go={go} /></div></div>
      <div className="content page-enter" key={page}>
        {page === 'Home' ? <Home {...props} /> : page === 'Autopilot' ? <Autopilot {...props} /> : page === 'Inbox' ? <Inbox {...props} /> : page === 'Discover' ? <Discover {...props} /> : page === 'Queue' ? <Queue {...props} /> : page === 'Tracker' ? <Tracker {...props} />
          : page === 'CV Library' ? <CVLibrary {...props} /> : page === 'Profile' ? <Profile {...props} /> : page === 'Answer Vault' ? <AnswerVault {...props} />
          : page === 'Analytics' ? <Analytics {...props} /> : page === 'Activity' ? <ActivityPage data={data} /> : <SettingsPage {...props} dark={dark} setDark={setDark} />}
      </div></main>
    {jobId && <JobDrawer jobId={jobId} data={data} refresh={refresh} close={() => setJobId(null)} go={go} />}
    {palette && <div className="modal-backdrop" onMouseDown={() => setPalette(false)}><div className="palette" onMouseDown={e => e.stopPropagation()}>
      <div><Command /><input autoFocus value={query} placeholder="Search jobs, pages, or actions…" onChange={e => { setQuery(e.target.value); setSelected(0) }}
        onKeyDown={e => { if (e.key === 'ArrowDown') { e.preventDefault(); setSelected(s => Math.min(s + 1, commands.length - 1)) } if (e.key === 'ArrowUp') { e.preventDefault(); setSelected(s => Math.max(s - 1, 0)) } if (e.key === 'Enter') choose(selected) }} /></div>
      {commands.length ? commands.map((c, i) => <button key={c.label + i} className={i === selected ? 'selected' : ''} onMouseEnter={() => setSelected(i)} onClick={() => choose(i)}><c.icon />{c.label}<span>{c.hint}</span></button>) : <p className="palette-empty">No matches</p>}
    </div></div>}
  </div>
}

export function App() {
  const [data, setData] = useState<Bootstrap>(initial)
  const [loaded, setLoaded] = useState(false)
  const [offline, setOffline] = useState('')
  const refresh = useCallback(async () => { try { setData(await api.bootstrap()); setOffline('') } catch (e) { setOffline(e instanceof Error ? e.message : 'Local service unavailable') } finally { setLoaded(true) } }, [])
  useEffect(() => { refresh() }, [refresh])
  if (!loaded) return <div className="loading"><Logo /><span>Opening your local workspace…</span></div>
  if (offline) return <div className="loading error-state"><Octagon /><h1>Local service isn’t running</h1><p>{offline}</p><code>npm run dev:api</code><button className="button primary" onClick={refresh}>Try again</button></div>
  return <NotifyProvider>{data.settings.first_run_complete ? <AppShell data={data} refresh={refresh} /> : <Wizard onComplete={refresh} />}</NotifyProvider>
}
