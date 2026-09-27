import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Activity, BarChart3, Bell, BookOpenCheck, Building2, CalendarDays, CircleHelp, Command, FileText, Gauge, HandCoins, Inbox as InboxIcon, LayoutDashboard, ListChecks, Moon, Octagon, Play, RefreshCw, Search, Settings, ShieldCheck, Sparkles, Sun, UserRound, Zap } from 'lucide-react'
import { api } from './api'
import { JobDrawer } from './JobDrawer'
import { Modal } from './components/Modal'
import { ReleaseNotes, UpdateBanner } from './components/UpdateBanner'
import { UpdateSuccess } from './components/Celebrate'
import { HelpModal, Tour } from './components/Tour'
import type { Bootstrap } from './types'
import { ACTIVE_STATUSES, ActivityList, Logo, NotifyProvider, PAGE_NAMES, PageHeading, relativeTime, useNotify, type Page } from './ui'
import { AnswerVault } from './pages/AnswerVault'
import { Autopilot } from './pages/Autopilot'
import { Calendar } from './pages/Calendar'
import { Companies } from './pages/Companies'
import { CVLibrary } from './pages/CVLibrary'
import { Discover } from './pages/Discover'
import { Home } from './pages/Home'
import { Inbox } from './pages/Inbox'
import { Insights } from './pages/Insights'
import { Offers } from './pages/Offers'
import { Profile } from './pages/Profile'
import { Queue } from './pages/Queue'
import { SettingsPage } from './pages/Settings'
import { Tracker } from './pages/Tracker'
import { Wizard } from './pages/Wizard'

const SECTIONS: [string, [Page, typeof LayoutDashboard][]][] = [
  ['Work', [['Home', LayoutDashboard], ['Autopilot', Zap], ['Inbox', InboxIcon], ['Discover', Search], ['Queue', ListChecks], ['Tracker', Gauge]]],
  ['Explore', [['Insights', BarChart3], ['Companies', Building2], ['Calendar', CalendarDays], ['Offers', HandCoins]]],
  ['You', [['Profile', UserRound], ['CV Library', FileText], ['Answer Vault', BookOpenCheck], ['Activity', Activity], ['Settings', Settings]]],
]
const navigation = SECTIONS.flatMap(([, items]) => items)
const initial: Bootstrap = {
  settings: {}, facts: [], jobs: [], applications: [], activity: [], cvs: [], answers: [], watchlist: [], catalog: [], notifications: [],
  inbox: { questions: [], suggestions: [], drafts: [] }, today: [], health: [],
  autopilot: { config: { enabled: false, interval_hours: 6, min_score: 60, auto_queue: true, auto_prepare: true, location_filter: true, internships_only: true, ai_summaries: true, ai_cover_letters: false }, running: null, next_run_at: null, runs: [] },
}
const THEME_KEY = 'applypilot.theme'

function readTheme() {
  try { return localStorage.getItem(THEME_KEY) !== 'light' } catch { return true }
}

function ActivityPage({ data }: { data: Bootstrap }) {
  const [query, setQuery] = useState('')
  const items = data.activity.filter(a => !query || `${a.action} ${JSON.stringify(a.details ?? {})}`.toLowerCase().includes(query.toLowerCase().replaceAll(' ', '_')))
  return <><PageHeading eyebrow="History" title="Everything ApplyPilot did" text="Every action, where each answer came from, and anything that went wrong — the latest 200 events." /><section className="panel"><div className="toolbar"><input className="search-input" value={query} onChange={e => setQuery(e.target.value)} placeholder="Search the history…" /></div><ActivityList items={items} detailed /></section></>
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
  const [askQuery, setAskQuery] = useState<{ q: string; n: number } | null>(null)
  const [notesOpen, setNotesOpen] = useState(false)
  const [touring, setTouring] = useState(false)
  const [help, setHelp] = useState(false)
  // After an automatic update, show that version's release notes once.
  // Known from the first load (release notes can arrive a moment later), so the tour never starts on top of it.
  const justUpdated = Boolean(data.settings.whats_new_pending && data.settings.whats_new_pending === data.version)
  const notesReady = Boolean(data.update?.notes && data.update.latest === data.version)
  const dismissWhatsNew = useCallback(() => { api.settings({ whats_new_pending: null }).then(refresh).catch(() => undefined) }, [refresh])
  // The tour runs once for everyone (new installs and people updating from older versions), after any update celebration.
  const tourShown = useRef(false)
  useEffect(() => { if (!data.settings.tour_done && !justUpdated && !tourShown.current) { tourShown.current = true; setTouring(true) } }, [data.settings.tour_done, justUpdated])
  const finishTour = useCallback(() => { setTouring(false); api.settings({ tour_done: true }).then(refresh).catch(() => undefined) }, [refresh])
  const setDark = (value: boolean) => { setDarkState(value); try { localStorage.setItem(THEME_KEY, value ? 'dark' : 'light') } catch { /* preference is optional */ } }
  const go = useCallback((p: Page) => { setPage(p); document.querySelector('main')?.scrollTo({ top: 0 }) }, [])

  const commands = useMemo(() => [
    { label: 'Run Autopilot now', hint: 'Action', icon: Play, run: async () => { try { await api.runAutopilot(); notify('Autopilot is scanning your companies…'); setPage('Autopilot'); await refresh() } catch (e) { notify(e instanceof Error ? e.message : 'Could not start', 'bad') } } },
    ...navigation.map(([name, Icon]) => ({ label: PAGE_NAMES[name], hint: 'Open', icon: Icon, run: () => go(name) })),
    { label: 'Take the tour', hint: 'Help', icon: CircleHelp, run: () => setTouring(true) },
    { label: 'What does everything mean?', hint: 'Help', icon: CircleHelp, run: () => setHelp(true) },
    ...(query.trim().split(/\s+/).length >= 2 ? [{ label: `Search: “${query.trim()}”`, hint: 'Ask', icon: Sparkles, run: () => ask(query.trim()) }] : []),
    { label: 'Check for updates', hint: 'Action', icon: RefreshCw, run: async () => { const r = await api.checkUpdate(); notify(r.status === 'available' ? `ApplyPilot ${r.latest} is available` : r.status === 'up_to_date' ? 'ApplyPilot is up to date' : r.error ?? 'Checked'); await refresh() } },
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

  const ask = useCallback((q: string) => { setAskQuery({ q, n: Date.now() }); setPage('Discover'); setJobId(null) }, [])

  // Stream progress while something is working; otherwise check in quietly for scheduled runs.
  const busy = Boolean(data.autopilot.running) || data.applications.some(a => a.browser_run?.status === 'RUNNING') || ['downloading', 'verifying', 'ready', 'installing'].includes(data.update?.status ?? '')
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
  const props = { data, refresh, go, openJob: setJobId, ask }
  const running = Boolean(data.autopilot.running)

  return <div className={dark ? 'app dark' : 'app light'}>
    <aside><Logo /><nav>{SECTIONS.map(([section, items]) => <div key={section} className="nav-section"><span className="nav-label">{section}</span>{items.map(([name, Icon]) => <button key={name} data-tour={`nav-${name}`} className={page === name ? 'active' : ''} onClick={() => go(name)}><Icon size={17} /><span className="nav-text">{PAGE_NAMES[name]}</span>
      {name === 'Queue' && active > 0 && <em>{active}</em>}
      {name === 'Inbox' && inboxCount > 0 && <em className="attention-badge">{inboxCount}</em>}
      {name === 'Home' && (data.today?.length ?? 0) > 0 && <em>{data.today!.length}</em>}
      {name === 'Settings' && data.update?.status === 'available' && <span className="nav-dot update" title="Update available" />}
      {name === 'Autopilot' && (running ? <span className="nav-pulse" title="Running" /> : data.autopilot.config.enabled && <span className="nav-dot" title="On" />)}
    </button>)}</div>)}</nav>
      <div className="sidebar-foot"><div className="privacy"><ShieldCheck /><div><b>Local & private</b><span>Data stays on this device</span></div></div><button onClick={() => setDark(!dark)}>{dark ? <Sun /> : <Moon />}{dark ? 'Light mode' : 'Dark mode'}</button></div></aside>
    <main><div className="topbar"><button className="command-button" data-tour="command" onClick={() => setPalette(true)}><Search />Search jobs, pages, actions…<kbd>Ctrl K</kbd></button>
      <div className="topbar-right"><button className="status" onClick={() => go('Autopilot')}><span className={`status-dot ${running ? 'running' : data.inbox.questions.length ? 'warn' : ''}`} /> {running ? (data.autopilot.runs[0]?.events.at(-1)?.message ?? 'Autopilot running') : data.autopilot.config.enabled ? `Autopilot on · next ${data.autopilot.next_run_at ? relativeTime(data.autopilot.next_run_at) : 'soon'}` : 'Autopilot off'}</button><button className="icon-button help-button" data-tour="help" onClick={() => setHelp(true)} aria-label="Help: what everything means"><CircleHelp /></button><Notifications data={data} refresh={refresh} go={go} /></div></div>
      {justUpdated ? <UpdateSuccess version={data.version ?? ''} previous={data.settings.updated_from as string | undefined} onNotes={notesReady ? () => setNotesOpen(true) : undefined} onDismiss={dismissWhatsNew} />
        : <UpdateBanner update={data.update} refresh={refresh} openNotes={() => setNotesOpen(true)} />}
      <div className="content page-enter" key={page}>
        {page === 'Home' ? <Home {...props} /> : page === 'Autopilot' ? <Autopilot {...props} /> : page === 'Inbox' ? <Inbox {...props} /> : page === 'Discover' ? <Discover key={askQuery?.n ?? 0} {...props} askQuery={askQuery?.q} /> : page === 'Queue' ? <Queue {...props} /> : page === 'Tracker' ? <Tracker {...props} />
          : page === 'Insights' ? <Insights {...props} /> : page === 'Companies' ? <Companies {...props} /> : page === 'Calendar' ? <Calendar {...props} /> : page === 'Offers' ? <Offers {...props} />
          : page === 'CV Library' ? <CVLibrary {...props} /> : page === 'Profile' ? <Profile {...props} /> : page === 'Answer Vault' ? <AnswerVault {...props} />
          : page === 'Activity' ? <ActivityPage data={data} /> : <SettingsPage {...props} dark={dark} setDark={setDark} />}
      </div></main>
    {jobId && <JobDrawer jobId={jobId} data={data} refresh={refresh} close={() => setJobId(null)} go={go} openJob={setJobId} />}
    {notesOpen && data.update?.notes && <Modal title={`What’s new in ApplyPilot ${data.update.latest}`} onClose={() => setNotesOpen(false)}><ReleaseNotes notes={data.update.notes} /></Modal>}
    {touring && <Tour onDone={finishTour} />}
    {help && <HelpModal onClose={() => setHelp(false)} onTour={() => setTouring(true)} />}
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
