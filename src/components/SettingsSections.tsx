import { useEffect, useState } from 'react'
import { AlertOctagon, ArchiveRestore, CheckCircle2, Download, FolderOpen, HardDriveDownload, Mail, MonitorSmartphone, RefreshCw, RotateCcw, ShieldCheck, Undo2 } from 'lucide-react'
import { api } from '../api'
import type { Backup, Bootstrap, EmailEvent } from '../types'
import { Badge, formatDateTime, relativeTime, useAction, useNotify } from '../ui'
import { Modal } from './Modal'
import { ReleaseNotes, formatBytes, formatEta } from './UpdateBanner'

export function UpdatesSection({ data, refresh }: { data: Bootstrap; refresh: () => Promise<void> }) {
  const { run, busy } = useAction(refresh)
  const [notes, setNotes] = useState(false)
  const u = data.update
  const auto = Boolean((data.settings.updates as { auto_install?: boolean } | undefined)?.auto_install ?? true)
  if (!u) return null
  const pct = u.total ? Math.floor(((u.downloaded ?? 0) / u.total) * 100) : 0
  const label = { idle: 'Not checked yet', checking: 'Checking…', up_to_date: 'You’re up to date', available: `Version ${u.latest} is available`, downloading: `Downloading ${u.latest} · ${pct}%`, verifying: 'Verifying download…', ready: `Version ${u.latest} is ready to install`, installing: 'Installing…', error: u.error ?? 'Update check failed' }[u.status]
  return <section className="panel settings-list"><div className="panel-head"><div><h2><HardDriveDownload size={15} /> Updates</h2><p>ApplyPilot updates itself from its official GitHub releases, verifying every download before installing.</p></div><Badge tone={u.status === 'up_to_date' ? 'good' : u.status === 'error' ? 'bad' : 'accent'}>v{u.current}</Badge></div>
    <div className="update-status">
      <div className={`update-orb ${u.status}`}>{u.status === 'up_to_date' ? <CheckCircle2 /> : u.status === 'error' ? <AlertOctagon /> : <RefreshCw className={['checking', 'downloading', 'verifying', 'installing'].includes(u.status) ? 'spin' : ''} />}</div>
      <div><b>{label}</b><span>{u.checked_at ? `Last checked ${relativeTime(u.checked_at)}` : 'ApplyPilot checks shortly after launch and every 6 hours.'}{u.mode !== 'installer' ? ` · ${u.mode === 'portable' ? 'Portable copy: download new versions from GitHub' : 'Running from source'}` : ''}</span>
        {u.status === 'downloading' && <><div className="update-progress"><i style={{ width: `${pct}%` }} /></div><small>{formatBytes(u.downloaded)} of {formatBytes(u.total)}{u.speed ? ` · ${formatBytes(u.speed)}/s` : ''} {formatEta(u.eta)}</small></>}</div>
      <div className="update-buttons">
        {u.notes && <button className="button ghost" onClick={() => setNotes(true)}>What’s new</button>}
        {u.status === 'available' && u.mode === 'installer' && <button className="button primary" onClick={() => run('dl', api.downloadUpdate)}><Download size={15} /> Download update</button>}
        {u.status === 'ready' && u.mode === 'installer' && <button className="button primary" onClick={() => run('install', api.installUpdate)}><RefreshCw size={15} /> Restart & update</button>}
        {!['downloading', 'verifying', 'installing'].includes(u.status) && <button className="button ghost" disabled={busy === 'check' || u.status === 'checking'} onClick={() => run('check', api.checkUpdate, r => r.status === 'up_to_date' ? 'ApplyPilot is up to date' : r.status === 'available' ? `Version ${r.latest} is available` : r.error ?? 'Checked')}><RefreshCw size={15} className={busy === 'check' ? 'spin' : ''} /> Check now</button>}
      </div>
    </div>
    <div className="setting-row"><div className="setting-icon"><ShieldCheck /></div><div><b>Install updates automatically</b><span>Downloads in the background and installs after a 30-second countdown you can postpone. Never interrupts Autopilot or a live fill.</span></div><span />
      <button className={`toggle ${auto ? 'on' : ''}`} onClick={() => run('auto', () => api.settings({ updates: { auto_install: !auto } }), auto ? 'Automatic updates off' : 'Automatic updates on')} aria-label="Toggle automatic updates"><i /></button></div>
    {notes && u.notes && <Modal title={`What’s new in ${u.latest}`} onClose={() => setNotes(false)}><ReleaseNotes notes={u.notes} /></Modal>}
  </section>
}

export function DesktopSection({ data, refresh }: { data: Bootstrap; refresh: () => Promise<void> }) {
  const { run } = useAction(refresh)
  const desktop = (data.settings.desktop as { close_to_tray?: boolean; start_with_windows?: boolean } | undefined) ?? {}
  const installed = data.update?.mode === 'installer'
  const set = (patch: Record<string, boolean>, message: string) => run('desktop', () => api.settings({ desktop: { ...desktop, ...patch } }), message)
  return <section className="panel settings-list"><div className="panel-head"><div><h2><MonitorSmartphone size={15} /> Desktop</h2><p>Keep Autopilot working in the background and get Windows notifications.</p></div></div>
    <div className="setting-row"><div className="setting-icon"><MonitorSmartphone /></div><div><b>Keep running in the tray when closed</b><span>Closing the window hides ApplyPilot to the system tray so Autopilot, deadline alerts, and email sync keep working. Quit from the tray icon.</span></div><span />
      <button className={`toggle ${desktop.close_to_tray !== false ? 'on' : ''}`} onClick={() => set({ close_to_tray: desktop.close_to_tray === false }, desktop.close_to_tray !== false ? 'Closing now quits ApplyPilot' : 'ApplyPilot will keep running in the tray')} aria-label="Toggle tray mode"><i /></button></div>
    <div className="setting-row"><div className="setting-icon"><RefreshCw /></div><div><b>Start with Windows</b><span>{installed ? 'Opens quietly in the tray when you sign in, so Autopilot never misses a run.' : 'Available in the installed app.'}</span></div><span />
      <button className={`toggle ${desktop.start_with_windows ? 'on' : ''}`} disabled={!installed} onClick={() => set({ start_with_windows: !desktop.start_with_windows }, desktop.start_with_windows ? 'Won’t start with Windows' : 'ApplyPilot will start with Windows')} aria-label="Toggle start with Windows"><i /></button></div>
  </section>
}

const PROVIDERS: [string, string, string][] = [['GMAIL', 'Gmail', 'Use a Google App Password: Google Account → Security → 2-Step Verification → App passwords.'], ['OUTLOOK', 'Microsoft 365 (work/school)', 'Personal Outlook.com accounts only allow Microsoft’s own sign-in, which isn’t supported yet.'], ['YAHOO', 'Yahoo Mail', 'Use a Yahoo app password (Account security → Generate app password).'], ['ICLOUD', 'iCloud Mail', 'Use an app-specific password from appleid.apple.com.'], ['ZOHO', 'Zoho Mail', 'Enable IMAP and create an app password.'], ['CUSTOM', 'Other (IMAP)', 'Any mail server with IMAP over SSL.']]

export function EmailSection({ data, refresh }: { data: Bootstrap; refresh: () => Promise<void> }) {
  const { run, busy } = useAction(refresh)
  const mail = (data.settings.email_sync ?? {}) as { enabled?: boolean; provider?: string; host?: string; address?: string; has_password?: boolean; last_sync?: string; last_error?: string }
  const [form, setForm] = useState({ provider: mail.provider ?? 'GMAIL', host: mail.host ?? '', address: mail.address ?? '', password: '' })
  const [events, setEvents] = useState<EmailEvent[]>([])
  useEffect(() => { api.emailEvents().then(setEvents).catch(() => undefined) }, [mail.last_sync])
  const help = PROVIDERS.find(p => p[0] === form.provider)?.[2]
  const save = (enabled: boolean) => run('save', () => api.emailSettings({ ...form, enabled }), enabled ? 'Email sync is on' : 'Email settings saved').then(r => { if (r) setForm({ ...form, password: '' }) })
  return <section className="panel settings-list"><div className="panel-head"><div><h2><Mail size={15} /> Email sync</h2><p>Reads recent application emails and moves Tracker cards when an interview invite, rejection, or offer arrives. Only subjects of matched emails are kept.</p></div>
    <Badge tone={mail.enabled ? (mail.last_error ? 'bad' : 'good') : 'neutral'}>{mail.enabled ? (mail.last_error ? 'Error' : 'On') : 'Off'}</Badge></div>
    <div className="form-grid">
      <label>Provider<select value={form.provider} onChange={e => setForm({ ...form, provider: e.target.value, host: '' })}>{PROVIDERS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>
      <label>Email address<input type="email" value={form.address} onChange={e => setForm({ ...form, address: e.target.value })} placeholder="you@gmail.com" /></label>
      {form.provider === 'CUSTOM' && <label>IMAP server<input value={form.host} onChange={e => setForm({ ...form, host: e.target.value })} placeholder="imap.example.com" /></label>}
      <label>App password{mail.has_password && <span className="muted small"> · saved (encrypted by Windows)</span>}<input type="password" value={form.password} onChange={e => setForm({ ...form, password: e.target.value })} placeholder={mail.has_password ? '•••••••• (leave blank to keep)' : 'xxxx xxxx xxxx xxxx'} autoComplete="new-password" /></label>
    </div>
    {help && <p className="muted small">{help}</p>}
    {mail.last_error && <p className="warn-text small">{mail.last_error}</p>}
    <div className="form-actions">
      {mail.last_sync && <span className="muted small">Last sync {relativeTime(mail.last_sync)}</span>}<span className="spacer" />
      {mail.enabled && <button className="button ghost" disabled={busy === 'sync'} onClick={() => run('sync', api.emailSync, r => `Checked ${r.messages} emails · ${r.moved} card${r.moved === 1 ? '' : 's'} moved`)}><RefreshCw size={14} className={busy === 'sync' ? 'spin' : ''} /> Sync now</button>}
      {mail.enabled ? <button className="button ghost" onClick={() => save(false)}>Turn off</button> : null}
      <button className="button primary" disabled={busy === 'save' || !form.address || (!form.password && !mail.has_password)} onClick={() => save(true)}>{mail.enabled ? 'Save' : 'Turn on sync'}</button>
    </div>
    {events.filter(e => e.action !== 'NONE').length > 0 && <div className="email-events"><b>Recent moves</b>{events.filter(e => e.action !== 'NONE').slice(0, 6).map(e => <div key={e.id} className="email-event"><Badge tone={e.kind === 'REJECTED' ? 'bad' : e.kind === 'OFFER' ? 'good' : 'accent'}>{e.kind.toLowerCase()}</Badge><span>{e.company ?? '—'} · {e.subject}</span>
      {e.action === 'MOVE' ? <button className="button subtle" onClick={() => run(`undo-${e.id}`, () => api.undoEmail(e.id), 'Moved back')}><Undo2 size={12} /> Undo</button> : <em>{e.action.toLowerCase()}</em>}</div>)}</div>}
  </section>
}

export function BackupResetSection({ refresh }: { refresh: () => Promise<void> }) {
  const notify = useNotify()
  const { run, busy } = useAction(refresh)
  const [backups, setBackups] = useState<Backup[] | null>(null)
  const [resetOpen, setResetOpen] = useState(false)
  const [restoreName, setRestoreName] = useState<string | null>(null)
  const load = () => api.backups().then(setBackups).catch(() => setBackups([]))
  useEffect(() => { load() }, [])
  return <section className="panel settings-list danger-zone"><div className="panel-head"><div><h2><ArchiveRestore size={15} /> Backup & reset</h2><p>Backups include every fact, job, application, answer, and uploaded CV. They stay on this computer.</p></div></div>
    <div className="backup-actions"><button className="button primary" disabled={busy === 'backup'} onClick={async () => { const b = await run('backup', api.createBackup, r => `Backup saved (${formatBytes(r.size)})`); if (b) load() }}><ArchiveRestore size={15} /> Back up now</button>
      <button className="button ghost" onClick={() => api.openBackups()}><FolderOpen size={15} /> Open backups folder</button></div>
    {backups && backups.length > 0 && <div className="backup-list">{backups.slice(0, 6).map(b => <div key={b.name} className="backup-row"><div><b>{formatDateTime(b.created_at)}</b><span>{b.name.includes('before-reset') ? 'Automatic, before a reset' : b.name.includes('before-restore') ? 'Automatic, before a restore' : 'Manual backup'} · {formatBytes(b.size)}</span></div>
      <button className="button subtle" onClick={() => setRestoreName(b.name)}><RotateCcw size={13} /> Restore</button></div>)}</div>}
    <div className="setting-row reset-row"><div className="setting-icon danger"><AlertOctagon /></div><div><b>Reset ApplyPilot</b><span>Erase every job, fact, answer, CV, and setting and start again from the setup wizard. A backup is saved first unless you opt out.</span></div><span />
      <button className="button danger" onClick={() => setResetOpen(true)}>Reset…</button></div>
    {resetOpen && <ResetModal close={() => setResetOpen(false)} done={async result => { setResetOpen(false); try { localStorage.clear() } catch { /* optional */ } notify(result.backup ? `ApplyPilot was reset. A backup was saved first.` : 'ApplyPilot was reset.'); await refresh() }} />}
    {restoreName && <Modal title="Restore this backup?" subtitle={restoreName} onClose={() => setRestoreName(null)}
      footer={<><button className="button ghost" onClick={() => setRestoreName(null)}>Cancel</button><button className="button primary" disabled={busy === 'restore'} onClick={async () => { const r = await run('restore', () => api.restoreBackup(restoreName), 'Backup restored'); if (r) { setRestoreName(null); load() } }}>Restore</button></>}>
      <p>Your current workspace is replaced by this backup. ApplyPilot saves a safety backup of the current state first, so you can undo this.</p></Modal>}
  </section>
}

function ResetModal({ close, done }: { close: () => void; done: (result: { backup: Backup | null; browser_data_kept: boolean }) => Promise<void> }) {
  const notify = useNotify()
  const [typed, setTyped] = useState('')
  const [backup, setBackup] = useState(true)
  const [busy, setBusy] = useState(false)
  const reset = async () => {
    setBusy(true)
    try { await done(await api.reset(backup)) } catch (e) { notify(e instanceof Error ? e.message : 'Reset failed', 'bad'); setBusy(false) }
  }
  return <Modal title="Reset ApplyPilot" subtitle="This can’t be undone without a backup." onClose={close}
    footer={<><button className="button ghost" onClick={close}>Cancel</button><button className="button danger" disabled={typed !== 'RESET' || busy} onClick={reset}>{busy ? 'Resetting…' : 'Erase everything'}</button></>}>
    <div className="reset-list"><b>This erases:</b><ul><li>Your verified profile, languages, and projects</li><li>Every job, application, and Tracker card</li><li>Answer Vault answers, drafts, and offers</li><li>Uploaded and tailored CVs</li><li>Followed companies, connections, and all settings</li></ul></div>
    <label className="checkbox-line"><input type="checkbox" checked={backup} onChange={e => setBackup(e.target.checked)} /> Save a backup first (recommended)</label>
    <label className="confirm-type"><span>Type <b>RESET</b> to confirm</span><input value={typed} onChange={e => setTyped(e.target.value)} autoFocus placeholder="RESET" /></label>
  </Modal>
}
