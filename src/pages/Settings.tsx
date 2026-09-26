import { useEffect, useState } from 'react'
import { Bot, Database, Info, Moon, ShieldCheck, Sun } from 'lucide-react'
import { api } from '../api'
import { Badge, PageHeading, useAction, type PageProps } from '../ui'

export function SettingsPage({ data, refresh, dark, setDark }: PageProps & { dark: boolean; setDark: (dark: boolean) => void }) {
  const { run } = useAction(refresh)
  const [database, setDatabase] = useState('')
  useEffect(() => { api.health().then(h => setDatabase(h.database)).catch(() => undefined) }, [])
  const toggle = (key: string, value: boolean, label: string) => run(key, () => api.settings({ [key]: value }), `${label} ${value ? 'on' : 'off'}`)
  return <>
    <PageHeading eyebrow="Control center" title="Safety & preferences" text="Conservative defaults stay in place until you explicitly change them." />
    <section className="panel settings-list">
      <SettingRow title="Strict Accuracy Mode" text="Unknown personal answers always pause." active={Boolean(data.settings.strict_accuracy_mode)} onChange={v => toggle('strict_accuracy_mode', v, 'Strict Accuracy Mode')} note="Recommended" />
      <SettingRow title="Dry Run" text="Fill and validate, but never submit." active={Boolean(data.settings.dry_run)} onChange={v => toggle('dry_run', v, 'Dry Run')} />
      <SettingRow title="Actual submissions" text="Automated submission isn’t built in this version; this switch only changes what validation reports." active={Boolean(data.settings.actual_submission_enabled)} onChange={v => toggle('actual_submission_enabled', v, 'Actual submissions')} />
      <div className="setting-row"><div className="setting-icon"><Bot /></div><div><b>Local AI</b><span>Off · endpoint http://localhost:11434</span></div><Badge tone="good">Optional</Badge></div>
      <div className="setting-row"><div className="setting-icon">{dark ? <Moon /> : <Sun />}</div><div><b>Appearance</b><span>{dark ? 'Dark' : 'Light'} theme</span></div><span /><button className={`toggle ${dark ? 'on' : ''}`} onClick={() => setDark(!dark)} aria-label="Toggle dark theme"><i /></button></div>
    </section>
    <section className="panel settings-list about"><div className="setting-row"><div className="setting-icon"><Database /></div><div><b>Your data</b><span className="mono">{database || 'Loading…'}</span></div></div>
      <div className="setting-row"><div className="setting-icon"><Info /></div><div><b>ApplyPilot {data.version ?? ''}</b><span>Local-first. No account, cloud service, or API key. <a href="https://github.com/Arnav-Dugad/ApplyPilot/releases" target="_blank" rel="noreferrer">Check for updates</a></span></div></div>
    </section>
  </>
}

function SettingRow({ title, text, active, onChange, note }: { title: string; text: string; active: boolean; onChange: (v: boolean) => void; note?: string }) {
  return <div className="setting-row"><div className="setting-icon"><ShieldCheck /></div><div><b>{title}</b><span>{text}</span></div>{note ? <Badge>{note}</Badge> : <span />}<button className={`toggle ${active ? 'on' : ''}`} onClick={() => onChange(!active)} aria-label={`Toggle ${title}`}><i /></button></div>
}
