import { useMemo, useState } from 'react'
import { Check, ChevronDown, Pencil, Plus, Trash2, X } from 'lucide-react'
import { api } from '../api'
import type { Fact, FactStatus } from '../types'
import { Badge, PageHeading, formatValue, useAction, type PageProps } from '../ui'
import { LanguagesPanel, ProjectsPanel } from '../components/ProfileExtras'
import { BasicsPanel, CertificationsPanel, EducationPanel, ExperiencePanel, LinksPanel, PreferencesPanel, ProfileNav, WorkRightsPanel, factValue } from '../components/AboutYou'
import { ScoreRing } from '../motion'

// Fields that appear on most application forms, and where each one lives in your profile.
const AUTOFILL: [string, string, string, string][] = [
  ['personal', 'full_name', 'Full name', 'basics'], ['contact', 'email', 'Email', 'basics'], ['contact', 'phone', 'Phone', 'basics'], ['contact', 'location', 'City', 'basics'],
  ['contact', 'linkedin', 'LinkedIn', 'links'], ['contact', 'github', 'GitHub', 'links'], ['education', 'university', 'University', 'education'], ['education', 'degree_name', 'Degree', 'education'],
  ['education', 'degree', 'Field of study', 'education'], ['education', 'graduation_date', 'Graduation date', 'education'], ['citizenship', 'countries', 'Citizenship', 'work-rights'],
  ['skills', 'verified_skills', 'Skills', 'advanced'], ['preferences', 'availability', 'Start dates', 'preferences'],
]
const LIST_KEYS = new Set(['verified_skills', 'locations'])
const COUNTRY_SCOPED = new Set(['work_authorization', 'sponsorship'])
// Shown in their own sections above; the advanced list shows everything else.
const OWN_PANELS = new Set(['work_authorization', 'sponsorship', 'languages', 'projects', 'citizenship', 'experience', 'certifications'])
const REGIONS = new Set(['europe', 'remote', 'anywhere', 'gcc', 'middle east', 'asia', 'emea', 'apac', 'worldwide'])
const CATEGORIES = ['personal', 'contact', 'education', 'skills', 'preferences', 'other']
const SECTIONS: [string, string][] = [['basics', 'Basics'], ['education', 'Education'], ['work-rights', 'Where you can work'], ['links', 'Links'], ['experience', 'Experience'], ['projects', 'Projects'], ['preferences', 'What you want'], ['languages', 'Languages'], ['certifications', 'Certificates'], ['advanced', 'Everything else']]

type Tri = true | false | null
const toInput = (value: unknown) => Array.isArray(value) ? value.join(', ') : value === null || value === undefined ? '' : typeof value === 'object' ? JSON.stringify(value) : String(value)
const fromInput = (key: string, text: string): unknown => LIST_KEYS.has(key) ? text.split(',').map(x => x.trim()).filter(Boolean) : text.trim()

export function Profile({ data, refresh }: PageProps) {
  const { run, busy } = useAction(refresh)
  const [editing, setEditing] = useState<string | null>(null)
  const [draft, setDraft] = useState({ value: '', status: 'VERIFIED' as FactStatus })
  const [adding, setAdding] = useState<{ category: string; fact_key: string; value: string } | null>(null)
  const [newCountry, setNewCountry] = useState('')
  const [extraCountries, setExtraCountries] = useState<string[]>([])
  const [advanced, setAdvanced] = useState(false)
  const [importGitHub, setImportGitHub] = useState(0)

  const general = data.facts.filter(f => !OWN_PANELS.has(f.category))
  const groups = useMemo(() => general.reduce<Record<string, Fact[]>>((all, fact) => { (all[fact.category] ||= []).push(fact); return all }, {}), [general])
  const has = (category: string, key: string) => data.facts.some(f => f.category === category && f.fact_key === key && f.status === 'VERIFIED')
  const ready = AUTOFILL.filter(([c, k]) => has(c, k)).length
  const githubLink = factValue<string>(data.facts, 'contact', 'github')
  const githubUser = githubLink?.replace(/^https:\/\/github\.com\//, '').replace(/\/$/, '')

  const countries = useMemo(() => {
    const prefs = data.facts.find(f => f.category === 'preferences' && f.fact_key === 'locations')?.value
    const fromPrefs = Array.isArray(prefs) ? prefs.map(String).filter(c => !REGIONS.has(c.toLowerCase())) : []
    const fromFacts = data.facts.filter(f => COUNTRY_SCOPED.has(f.category) && f.country_code).map(f => f.country_code as string)
    const seen = new Set<string>()
    return [...fromPrefs, ...fromFacts, ...extraCountries].filter(c => { const k = c.trim().toLowerCase(); if (!k || seen.has(k)) return false; seen.add(k); return true })
  }, [data.facts, extraCountries])

  const countryValue = (category: string, key: string, country: string): Tri => {
    const f = data.facts.find(x => x.category === category && x.fact_key === key && x.country_code?.toLowerCase() === country.toLowerCase())
    return f?.status === 'VERIFIED' && typeof f.value === 'boolean' ? f.value : null
  }
  const setCountry = (category: string, key: string, country: string, value: Tri) => run(`${category}-${country}`, () => api.saveFact({ category, fact_key: key, country_code: country, value, status: value === null ? 'UNKNOWN' : 'VERIFIED', source: 'USER' }), value === null ? `${country}: now worked out from your citizenship` : `${country}: saved`)

  const startEdit = (f: Fact) => { setEditing(f.id ?? null); setDraft({ value: toInput(f.value), status: f.status === 'EXPIRED' ? 'VERIFIED' : f.status }) }
  const saveEdit = async (f: Fact) => {
    let value = fromInput(f.fact_key, draft.value)
    if (typeof f.value === 'object' && f.value !== null && !Array.isArray(f.value)) { try { value = JSON.parse(draft.value) } catch { return } }
    const empty = Array.isArray(value) ? !value.length : !value
    await run(`edit-${f.id}`, () => api.saveFact({ category: f.category, fact_key: f.fact_key, country_code: f.country_code, value: empty ? null : value, status: empty ? 'UNKNOWN' : draft.status, source: 'USER' }), 'Saved')
    setEditing(null)
  }
  const saveNew = async () => {
    if (!adding) return
    const key = adding.fact_key.trim().toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '')
    const value = fromInput(key, adding.value)
    const saved = await run('add', () => api.saveFact({ category: adding.category, fact_key: key, value, status: 'VERIFIED', source: 'USER' }), 'Saved')
    if (saved) setAdding(null)
  }
  const jump = (id: string) => { if (id === 'advanced') setAdvanced(true); setTimeout(() => document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 30) }

  const countryAnswers = <div className="country-table">
    <div className="country-row head"><span>Country</span><span>Can you work there?</span><span>Need a visa?</span></div>
    {countries.map(country => <div className="country-row" key={country}>
      <b>{country}</b>
      <TriToggle value={countryValue('work_authorization', 'authorized', country)} onChange={v => setCountry('work_authorization', 'authorized', country, v)} />
      <TriToggle value={countryValue('sponsorship', 'requires_sponsorship', country)} onChange={v => setCountry('sponsorship', 'requires_sponsorship', country, v)} />
    </div>)}
    <div className="country-row add"><input value={newCountry} list="country-list" onChange={e => setNewCountry(e.target.value)} placeholder="Add a country…" onKeyDown={e => { if (e.key === 'Enter' && newCountry.trim()) { setExtraCountries([...extraCountries, newCountry.trim()]); setNewCountry('') } }} /><button className="button subtle" disabled={!newCountry.trim()} onClick={() => { setExtraCountries([...extraCountries, newCountry.trim()]); setNewCountry('') }}><Plus size={14} /> Add</button></div>
    <p className="muted small">“Not sure” lets ApplyPilot work it out from your citizenship.</p>
  </div>

  return <>
    <PageHeading eyebrow="My profile" title="About you" text="ApplyPilot only ever uses what you write here. The more you fill in, the smarter your matches and the more of each form it fills.">
      {data.strength && <div className="heading-strength" title={data.strength.next.map(i => `+${i.points}% ${i.label}`).join(' · ')}><ScoreRing score={data.strength.percent} size={46} stroke={4} /><span>Profile<br />strength</span></div>}
    </PageHeading>

    <section className="panel readiness"><div className="panel-head"><div><h2>Ready to autofill</h2><p>{ready} of {AUTOFILL.length} common form fields are ready. Tap a missing one to fill it in.</p></div><div className="meter"><i style={{ width: `${(ready / AUTOFILL.length) * 100}%` }} /></div></div>
      <div className="chips">{AUTOFILL.map(([c, k, label, section]) => has(c, k) ? <span key={k} className="chip done"><Check size={12} />{label}</span> : <button key={k} className="chip" onClick={() => jump(section)}><Plus size={12} />{label}</button>)}</div>
    </section>
    <ProfileNav items={SECTIONS} />

    <div className="profile-columns">
      <BasicsPanel facts={data.facts} refresh={refresh} />
      <LinksPanel facts={data.facts} refresh={refresh} onGitHub={() => { setImportGitHub(n => n + 1); jump('projects') }} />
    </div>
    <EducationPanel data={data} refresh={refresh} />
    <WorkRightsPanel data={data} refresh={refresh} answerCountry={countryAnswers} />
    <ExperiencePanel data={data} refresh={refresh} />
    <ProjectsPanel key={importGitHub} facts={data.facts} refresh={refresh} githubUser={githubUser} openImport={importGitHub > 0} />
    <PreferencesPanel data={data} refresh={refresh} />
    <div className="profile-duo"><LanguagesPanel facts={data.facts} refresh={refresh} /><CertificationsPanel facts={data.facts} refresh={refresh} /></div>

    <section className="panel" id="advanced"><button className="disclosure" onClick={() => setAdvanced(!advanced)} aria-expanded={advanced}><div><h2>Everything else ApplyPilot knows</h2><p>Your skills and every other saved detail, exactly as stored.</p></div><ChevronDown className={advanced ? 'open' : ''} /></button>
      {advanced && <>
        <div className="advanced-actions"><button className="button subtle" onClick={() => setAdding({ category: 'skills', fact_key: 'verified_skills', value: '' })}><Plus size={14} /> Add a detail</button></div>
        {adding && <div className="project-form"><div className="form-grid three">
          <label>Group<select value={adding.category} onChange={e => setAdding({ ...adding, category: e.target.value })}>{CATEGORIES.map(c => <option key={c}>{c}</option>)}</select></label>
          <label>Name<input value={adding.fact_key} onChange={e => setAdding({ ...adding, fact_key: e.target.value })} placeholder="verified_skills" /></label>
          <label>Value<input value={adding.value} onChange={e => setAdding({ ...adding, value: e.target.value })} autoFocus onKeyDown={e => e.key === 'Enter' && saveNew()} placeholder="Lists are comma separated" /></label>
        </div>
          <div className="form-actions"><button className="button ghost" onClick={() => setAdding(null)}>Cancel</button><button className="button primary" disabled={!adding.fact_key.trim() || !adding.value.trim() || busy === 'add'} onClick={saveNew}><Check size={16} /> Save</button></div></div>}
        <div className="profile-grid">{Object.entries(groups).map(([category, facts]) => <div className="fact-group" key={category}><div className="fact-group-head"><h3>{category.replaceAll('_', ' ')}</h3><Badge>{facts.length}</Badge></div>
          {facts.map(f => editing === f.id ? <div className="fact editing" key={f.id}>
            <b>{f.fact_key.replaceAll('_', ' ')}</b>
            <input value={draft.value} onChange={e => setDraft({ ...draft, value: e.target.value })} autoFocus onKeyDown={e => { if (e.key === 'Enter') saveEdit(f); if (e.key === 'Escape') setEditing(null) }} />
            <select value={draft.status} onChange={e => setDraft({ ...draft, status: e.target.value as FactStatus })}><option value="VERIFIED">Confirmed</option><option value="UNVERIFIED">Not sure</option><option value="UNKNOWN">Unknown</option></select>
            <div className="fact-actions"><button className="icon-button" onClick={() => setEditing(null)} aria-label="Cancel"><X /></button><button className="button primary subtle" disabled={busy === `edit-${f.id}`} onClick={() => saveEdit(f)}>Save</button></div>
          </div> : <div className="fact" key={f.id}>
            <div><b>{f.fact_key.replaceAll('_', ' ')}</b><span title={formatValue(f.value)}>{formatValue(f.value)}</span>{f.country_code && <small>{f.country_code} only</small>}</div>
            <div className="fact-actions"><Badge tone={f.status === 'VERIFIED' ? 'good' : f.status === 'EXPIRED' ? 'bad' : 'warn'}>{f.status === 'VERIFIED' ? 'Confirmed' : f.status === 'EXPIRED' ? 'Expired' : f.status === 'UNVERIFIED' ? 'Not sure' : 'Unknown'}</Badge>
              <button className="icon-button" onClick={() => startEdit(f)} aria-label={`Edit ${f.fact_key}`}><Pencil /></button>
              <button className="icon-button" onClick={() => f.id && confirm(`Delete ${f.fact_key.replaceAll('_', ' ')}?`) && run(`del-${f.id}`, () => api.deleteFact(f.id!), 'Deleted')} aria-label={`Delete ${f.fact_key}`}><Trash2 /></button></div>
          </div>)}
        </div>)}</div>
      </>}
    </section>
  </>
}

function TriToggle({ value, onChange }: { value: Tri; onChange: (v: Tri) => void }) {
  const options: [Tri, string, string][] = [[true, 'Yes', 'yes'], [false, 'No', 'no'], [null, 'Not sure', 'unknown']]
  return <div className="segmented">{options.map(([v, label, cls]) => <button key={label} className={value === v ? `active ${cls}` : ''} onClick={() => value !== v && onChange(v)}>{label}</button>)}</div>
}
