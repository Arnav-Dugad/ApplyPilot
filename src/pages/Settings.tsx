import { useEffect, useState } from 'react'
import { Bot, Cpu, Database, Download, Info, Moon, ShieldCheck, Sun } from 'lucide-react'
import { api } from '../api'
import type { AIStatus } from '../types'
import { Badge, PageHeading, useAction, type PageProps } from '../ui'

export function SettingsPage({ data, refresh, dark, setDark }: PageProps & { dark: boolean; setDark: (dark: boolean) => void }) {
  const { run } = useAction(refresh)
  const [database, setDatabase] = useState('')
  useEffect(() => { api.health().then(h => setDatabase(h.database)).catch(() => undefined) }, [])
  const toggle = (key: string, value: boolean, label: string) => run(key, () => api.settings({ [key]: value }), `${label} ${value ? 'on' : 'off'}`)
  return <>
    <PageHeading eyebrow="Control center" title="Safety, AI & preferences" text="Conservative defaults stay in place until you explicitly change them." />
    <LocalAI refresh={refresh} provider={(data.settings.ollama as { provider?: string } | undefined)?.provider} />
    <section className="panel settings-list">
      <SettingRow title="Strict Accuracy Mode" text="Unknown personal answers always pause." active={Boolean(data.settings.strict_accuracy_mode)} onChange={v => toggle('strict_accuracy_mode', v, 'Strict Accuracy Mode')} note="Recommended" />
      <SettingRow title="Dry Run" text="Fill and validate, but never submit." active={Boolean(data.settings.dry_run)} onChange={v => toggle('dry_run', v, 'Dry Run')} />
      <SettingRow title="Actual submissions" text="ApplyPilot never presses submit in this version; this switch only changes what validation reports." active={Boolean(data.settings.actual_submission_enabled)} onChange={v => toggle('actual_submission_enabled', v, 'Actual submissions')} />
      <div className="setting-row"><div className="setting-icon">{dark ? <Moon /> : <Sun />}</div><div><b>Appearance</b><span>{dark ? 'Dark' : 'Light'} theme</span></div><span /><button className={`toggle ${dark ? 'on' : ''}`} onClick={() => setDark(!dark)} aria-label="Toggle dark theme"><i /></button></div>
    </section>
    <section className="panel settings-list about"><div className="setting-row"><div className="setting-icon"><Database /></div><div><b>Your data</b><span className="mono">{database || 'Loading…'}</span></div></div>
      <div className="setting-row"><div className="setting-icon"><Info /></div><div><b>ApplyPilot {data.version ?? ''}</b><span>Local-first. No account, cloud service, or API key. <a href="https://github.com/Arnav-Dugad/ApplyPilot/releases" target="_blank" rel="noreferrer">Check for updates</a></span></div></div>
    </section>
  </>
}

function LocalAI({ refresh, provider }: { refresh: () => Promise<void>; provider?: string }) {
  const { run } = useAction(refresh)
  const [status, setStatus] = useState<AIStatus | null>(null)
  const load = () => api.aiStatus().then(setStatus).catch(() => undefined)
  useEffect(() => { load() }, [])
  useEffect(() => {
    if (status?.pull.status !== 'pulling') return
    const id = setInterval(load, 1200)
    return () => clearInterval(id)
  }, [status?.pull.status])
  const enabled = provider === 'OLLAMA'
  const save = async (patch: Record<string, unknown>, message: string) => { await run('ai', () => api.settings({ ollama: { endpoint: status?.endpoint ?? 'http://localhost:11434', provider: provider ?? 'OFF', ...patch } }), message); load() }
  const pull = status?.pull
  const pct = pull?.total ? Math.round(((pull.completed ?? 0) / pull.total) * 100) : 0

  return <section className="panel ai-panel"><div className="panel-head"><div><h2><Cpu size={15} /> Local AI</h2><p>Runs entirely on this computer with Ollama. Writes summaries and drafts — never facts, never submissions.</p></div>
    <Badge tone={status?.available ? 'good' : 'neutral'}>{status === null ? 'Checking…' : status.available ? `Ollama ${status.version ?? ''} detected` : 'Not installed'}</Badge></div>
    {status && !status.available && <div className="ai-setup"><Bot /><div><b>Install Ollama to unlock AI features</b><p>Free and private. After installing, come back here and download a model with one click.</p></div><a className="button primary" href="https://ollama.com/download/windows" target="_blank" rel="noreferrer"><Download size={15} /> Get Ollama</a></div>}
    {status?.available && <>
      <div className="setting-row"><div className="setting-icon"><Bot /></div><div><b>Use local AI</b><span>{status.models.length ? `Model: ${status.model}` : 'Download a model below first'}</span></div>
        {status.models.length > 1 ? <select value={status.model ?? ''} onChange={e => save({ model: e.target.value }, `Using ${e.target.value}`)}>{status.models.map(m => <option key={m}>{m}</option>)}</select> : <span />}
        <button className={`toggle ${enabled ? 'on' : ''}`} disabled={!status.models.length} onClick={() => save({ provider: enabled ? 'OFF' : 'OLLAMA', model: status.model }, enabled ? 'Local AI off' : 'Local AI on')} aria-label="Toggle local AI"><i /></button></div>
      <div className="model-grid">{status.recommended.map(m => { const installed = status.models.some(x => x === m.name || x.startsWith(m.name)); const pulling = pull?.status === 'pulling' && pull.model === m.name
        return <div key={m.name} className={`model-card ${installed ? 'installed' : ''}`}><b>{m.name}</b><span>{m.note} · {m.size}</span>
          {pulling ? <div className="pull-progress"><i style={{ width: `${pct}%` }} /><small>{pull?.detail} {pct ? `${pct}%` : ''}</small></div>
            : installed ? <Badge tone="good">Installed</Badge>
            : <button className="button subtle" disabled={pull?.status === 'pulling'} onClick={async () => { await api.pullModel(m.name); load() }}><Download size={14} /> Download</button>}
        </div> })}</div>
      {pull?.status === 'error' && <p className="warn-text small">Download failed: {pull.detail}</p>}
    </>}
  </section>
}

function SettingRow({ title, text, active, onChange, note }: { title: string; text: string; active: boolean; onChange: (v: boolean) => void; note?: string }) {
  return <div className="setting-row"><div className="setting-icon"><ShieldCheck /></div><div><b>{title}</b><span>{text}</span></div>{note ? <Badge>{note}</Badge> : <span />}<button className={`toggle ${active ? 'on' : ''}`} onClick={() => onChange(!active)} aria-label={`Toggle ${title}`}><i /></button></div>
}
