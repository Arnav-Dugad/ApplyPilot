import { useEffect, useMemo, useState } from 'react'
import { Activity, BarChart3, BookOpenCheck, Command, FileText, Gauge, LayoutDashboard, ListChecks, Moon, Octagon, Search, Settings, ShieldCheck, Sun, UserRound } from 'lucide-react'
import { api } from './api'
import type { Bootstrap } from './types'
import { ACTIVE_STATUSES, ActivityList, Logo, NotifyProvider, PageHeading, type Page } from './ui'
import { Analytics } from './pages/Analytics'
import { AnswerVault } from './pages/AnswerVault'
import { CVLibrary } from './pages/CVLibrary'
import { Discover } from './pages/Discover'
import { Home } from './pages/Home'
import { Profile } from './pages/Profile'
import { Queue } from './pages/Queue'
import { SettingsPage } from './pages/Settings'
import { Tracker } from './pages/Tracker'
import { Wizard } from './pages/Wizard'

const navigation: [Page, typeof LayoutDashboard][] = [
  ['Home', LayoutDashboard], ['Discover', Search], ['Queue', ListChecks], ['Tracker', Gauge], ['CV Library', FileText],
  ['Profile', UserRound], ['Answer Vault', BookOpenCheck], ['Analytics', BarChart3], ['Activity', Activity], ['Settings', Settings],
]
const initial: Bootstrap = { settings: {}, facts: [], jobs: [], applications: [], activity: [], cvs: [], answers: [] }
const THEME_KEY = 'applypilot.theme'

function readTheme() {
  try { return localStorage.getItem(THEME_KEY) !== 'light' } catch { return true }
}

function ActivityPage({ data }: { data: Bootstrap }) {
  const [query, setQuery] = useState('')
  const items = data.activity.filter(a => !query || `${a.action} ${JSON.stringify(a.details ?? {})}`.toLowerCase().includes(query.toLowerCase().replaceAll(' ', '_')))
  return <><PageHeading eyebrow="Activity" title="Audit trail" text="Every important action, source, pause, and failure — the latest 200 events." /><section className="panel"><div className="toolbar"><input className="search-input" value={query} onChange={e => setQuery(e.target.value)} placeholder="Filter events…" /></div><ActivityList items={items} detailed /></section></>
}

function AppShell({ data, refresh }: { data: Bootstrap; refresh: () => Promise<void> }) {
  const [page, setPage] = useState<Page>('Home')
  const [dark, setDarkState] = useState(readTheme)
  const [palette, setPalette] = useState(false)
  const [query, setQuery] = useState('')
  const [selected, setSelected] = useState(0)
  const setDark = (value: boolean) => { setDarkState(value); try { localStorage.setItem(THEME_KEY, value ? 'dark' : 'light') } catch { /* preference is optional */ } }

  const commands = useMemo(() => [
    ...navigation.map(([name, Icon]) => ({ label: name, hint: 'Open', icon: Icon, run: () => setPage(name) })),
    { label: dark ? 'Switch to light mode' : 'Switch to dark mode', hint: 'Theme', icon: dark ? Sun : Moon, run: () => setDark(!dark) },
  ].filter(c => c.label.toLowerCase().includes(query.trim().toLowerCase())), [query, dark])

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

  const choose = (index: number) => { commands[index]?.run(); setPalette(false) }
  const active = data.applications.filter(a => ACTIVE_STATUSES.includes(a.status)).length
  const paused = data.applications.filter(a => a.status === 'WAITING_FOR_USER' || a.status === 'NEEDS_INFO').length
  const props = { data, refresh, go: setPage }

  return <div className={dark ? 'app dark' : 'app light'}>
    <aside><Logo /><nav>{navigation.map(([name, Icon]) => <button key={name} className={page === name ? 'active' : ''} onClick={() => setPage(name)}><Icon size={18} />{name}{name === 'Queue' && active > 0 && <em>{active}</em>}</button>)}</nav>
      <div className="sidebar-foot"><div className="privacy"><ShieldCheck /><div><b>Local & private</b><span>Data stays on this device</span></div></div><button onClick={() => setDark(!dark)}>{dark ? <Sun /> : <Moon />}{dark ? 'Light mode' : 'Dark mode'}</button></div></aside>
    <main><div className="topbar"><button className="command-button" onClick={() => setPalette(true)}><Search />Search or jump to…<kbd>Ctrl K</kbd></button><div className="status"><span className={`status-dot ${paused ? 'warn' : ''}`} /> {paused ? `${paused} paused — waiting for you` : data.settings.dry_run ? 'Dry Run · automation idle' : 'Automation idle'}</div></div>
      <div className="content">
        {page === 'Home' ? <Home {...props} /> : page === 'Discover' ? <Discover {...props} /> : page === 'Queue' ? <Queue {...props} /> : page === 'Tracker' ? <Tracker {...props} />
          : page === 'CV Library' ? <CVLibrary {...props} /> : page === 'Profile' ? <Profile {...props} /> : page === 'Answer Vault' ? <AnswerVault {...props} />
          : page === 'Analytics' ? <Analytics {...props} /> : page === 'Activity' ? <ActivityPage data={data} /> : <SettingsPage {...props} dark={dark} setDark={setDark} />}
      </div></main>
    {palette && <div className="modal-backdrop" onMouseDown={() => setPalette(false)}><div className="palette" onMouseDown={e => e.stopPropagation()}>
      <div><Command /><input autoFocus value={query} placeholder="Type a page or command…" onChange={e => { setQuery(e.target.value); setSelected(0) }}
        onKeyDown={e => { if (e.key === 'ArrowDown') { e.preventDefault(); setSelected(s => Math.min(s + 1, commands.length - 1)) } if (e.key === 'ArrowUp') { e.preventDefault(); setSelected(s => Math.max(s - 1, 0)) } if (e.key === 'Enter') choose(selected) }} /></div>
      {commands.length ? commands.map((c, i) => <button key={c.label} className={i === selected ? 'selected' : ''} onMouseEnter={() => setSelected(i)} onClick={() => choose(i)}><c.icon />{c.label}<span>{c.hint}</span></button>) : <p className="palette-empty">No matches</p>}
    </div></div>}
  </div>
}

export function App() {
  const [data, setData] = useState<Bootstrap>(initial)
  const [loaded, setLoaded] = useState(false)
  const [offline, setOffline] = useState('')
  const refresh = async () => { try { setData(await api.bootstrap()); setOffline('') } catch (e) { setOffline(e instanceof Error ? e.message : 'Local service unavailable') } finally { setLoaded(true) } }
  useEffect(() => { refresh() }, [])
  if (!loaded) return <div className="loading"><Logo /><span>Opening your local workspace…</span></div>
  if (offline) return <div className="loading error-state"><Octagon /><h1>Local service isn’t running</h1><p>{offline}</p><code>npm run dev:api</code><button className="button primary" onClick={refresh}>Try again</button></div>
  return <NotifyProvider>{data.settings.first_run_complete ? <AppShell data={data} refresh={refresh} /> : <Wizard onComplete={refresh} />}</NotifyProvider>
}
