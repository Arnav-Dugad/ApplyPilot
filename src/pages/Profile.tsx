import { useMemo, useState } from 'react'
import { Check, Globe2, Pencil, Plus, ShieldCheck, Trash2, X } from 'lucide-react'
import { api } from '../api'
import type { Fact, FactStatus } from '../types'
import { Badge, PageHeading, formatValue, useAction, type PageProps } from '../ui'

// Facts the form filler knows how to use, in the order they usually appear on applications.
const AUTOFILL: [string, string, string][] = [
  ['personal', 'full_name', 'Full legal name'], ['contact', 'email', 'Email'], ['contact', 'phone', 'Phone'], ['contact', 'address', 'Address'],
  ['education', 'university', 'University'], ['education', 'degree', 'Degree'], ['education', 'graduation_date', 'Graduation date'],
  ['skills', 'verified_skills', 'Skills'], ['preferences', 'relocation', 'Open to relocation'], ['preferences', 'salary', 'Salary expectation'],
]
const LIST_KEYS = new Set(['verified_skills', 'locations'])
const COUNTRY_SCOPED = new Set(['work_authorization', 'sponsorship'])
const REGIONS = new Set(['europe', 'remote', 'anywhere', 'gcc', 'middle east', 'asia', 'emea', 'apac', 'worldwide'])
const CATEGORIES = ['personal', 'contact', 'education', 'skills', 'preferences', 'other']

type Tri = true | false | null
const toInput = (value: unknown) => Array.isArray(value) ? value.join(', ') : value === null || value === undefined ? '' : String(value)
const fromInput = (key: string, text: string): unknown => LIST_KEYS.has(key) ? text.split(',').map(x => x.trim()).filter(Boolean) : text.trim()

export function Profile({ data, refresh }: PageProps) {
  const { run, busy } = useAction(refresh)
  const [editing, setEditing] = useState<string | null>(null)
  const [draft, setDraft] = useState({ value: '', status: 'VERIFIED' as FactStatus })
  const [adding, setAdding] = useState<{ category: string; fact_key: string; value: string } | null>(null)
  const [newCountry, setNewCountry] = useState('')
  const [extraCountries, setExtraCountries] = useState<string[]>([])

  const general = data.facts.filter(f => !COUNTRY_SCOPED.has(f.category))
  const groups = useMemo(() => general.reduce<Record<string, Fact[]>>((all, fact) => { (all[fact.category] ||= []).push(fact); return all }, {}), [general])
  const has = (category: string, key: string) => data.facts.some(f => f.category === category && f.fact_key === key && f.status === 'VERIFIED')
  const ready = AUTOFILL.filter(([c, k]) => has(c, k)).length

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
  const setCountry = (category: string, key: string, country: string, value: Tri) => run(`${category}-${country}`, () => api.saveFact({ category, fact_key: key, country_code: country, value, status: value === null ? 'UNKNOWN' : 'VERIFIED', source: 'USER' }), `${country}: saved`)

  const startEdit = (f: Fact) => { setEditing(f.id ?? null); setDraft({ value: toInput(f.value), status: f.status === 'EXPIRED' ? 'VERIFIED' : f.status }) }
  const saveEdit = async (f: Fact) => {
    const value = fromInput(f.fact_key, draft.value)
    const empty = Array.isArray(value) ? !value.length : !value
    await run(`edit-${f.id}`, () => api.saveFact({ category: f.category, fact_key: f.fact_key, country_code: f.country_code, value: empty ? null : value, status: empty ? 'UNKNOWN' : draft.status, source: 'USER' }), 'Saved')
    setEditing(null)
  }
  const saveNew = async () => {
    if (!adding) return
    const key = adding.fact_key.trim().toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '')
    const value = fromInput(key, adding.value)
    const saved = await run('add', () => api.saveFact({ category: adding.category, fact_key: key, value, status: 'VERIFIED', source: 'USER' }), 'Fact added and verified')
    if (saved) setAdding(null)
  }

  return <>
    <PageHeading eyebrow="Truth Layer" title="Verified profile" text="These are the only facts automation is allowed to use. Editing a fact expires anything that depended on it.">
      <Badge tone="good"><ShieldCheck size={13} /> STRICT</Badge>
      <button className="button primary" onClick={() => setAdding({ category: 'contact', fact_key: '', value: '' })}><Plus size={16} /> Add fact</button>
    </PageHeading>

    <section className="panel readiness"><div className="panel-head"><div><h2>Autofill readiness</h2><p>{ready} of {AUTOFILL.length} common application fields can be filled from verified facts.</p></div><div className="meter"><i style={{ width: `${(ready / AUTOFILL.length) * 100}%` }} /></div></div>
      <div className="chips">{AUTOFILL.map(([c, k, label]) => has(c, k) ? <span key={k} className="chip done"><Check size={12} />{label}</span> : <button key={k} className="chip" onClick={() => setAdding({ category: c, fact_key: k, value: '' })}><Plus size={12} />{label}</button>)}</div>
    </section>

    {adding && <section className="panel form-panel"><div className="panel-head"><div><h2>Add a verified fact</h2><p>Only add what is true and current. Lists are comma separated.</p></div><button className="icon-button" onClick={() => setAdding(null)} aria-label="Close"><X /></button></div>
      <div className="form-grid three">
        <label>Category<select value={adding.category} onChange={e => setAdding({ ...adding, category: e.target.value })}>{CATEGORIES.map(c => <option key={c}>{c}</option>)}</select></label>
        <label>Name<input value={adding.fact_key} onChange={e => setAdding({ ...adding, fact_key: e.target.value })} placeholder="phone" list="fact-keys" /></label>
        <label>Value<input value={adding.value} onChange={e => setAdding({ ...adding, value: e.target.value })} autoFocus onKeyDown={e => e.key === 'Enter' && saveNew()} /></label>
        <datalist id="fact-keys">{AUTOFILL.map(([, k]) => <option key={k} value={k} />)}</datalist>
      </div>
      <div className="form-actions"><button className="button ghost" onClick={() => setAdding(null)}>Cancel</button><button className="button primary" disabled={!adding.fact_key.trim() || !adding.value.trim() || busy === 'add'} onClick={saveNew}><Check size={16} /> Save as verified</button></div>
    </section>}

    <section className="panel"><div className="panel-head"><div><h2>Work authorization by country</h2><p>Answered separately for every country — never copied across borders. Unknown pauses automation.</p></div><Globe2 size={18} className="muted" /></div>
      <div className="country-table">
        <div className="country-row head"><span>Country</span><span>Authorized to work?</span><span>Need visa sponsorship?</span></div>
        {countries.map(country => <div className="country-row" key={country}>
          <b>{country}</b>
          <TriToggle value={countryValue('work_authorization', 'authorized', country)} onChange={v => setCountry('work_authorization', 'authorized', country, v)} />
          <TriToggle value={countryValue('sponsorship', 'requires_sponsorship', country)} onChange={v => setCountry('sponsorship', 'requires_sponsorship', country, v)} />
        </div>)}
        <div className="country-row add"><input value={newCountry} onChange={e => setNewCountry(e.target.value)} placeholder="Add a country…" onKeyDown={e => { if (e.key === 'Enter' && newCountry.trim()) { setExtraCountries([...extraCountries, newCountry.trim()]); setNewCountry('') } }} /><button className="button subtle" disabled={!newCountry.trim()} onClick={() => { setExtraCountries([...extraCountries, newCountry.trim()]); setNewCountry('') }}><Plus size={14} /> Add</button></div>
      </div>
    </section>

    <div className="profile-grid">{Object.entries(groups).map(([category, facts]) => <section className="panel" key={category}><div className="panel-head"><h2>{category.replaceAll('_', ' ')}</h2><Badge>{facts.length}</Badge></div>
      {facts.map(f => editing === f.id ? <div className="fact editing" key={f.id}>
        <b>{f.fact_key.replaceAll('_', ' ')}</b>
        <input value={draft.value} onChange={e => setDraft({ ...draft, value: e.target.value })} autoFocus onKeyDown={e => { if (e.key === 'Enter') saveEdit(f); if (e.key === 'Escape') setEditing(null) }} />
        <select value={draft.status} onChange={e => setDraft({ ...draft, status: e.target.value as FactStatus })}><option value="VERIFIED">Verified</option><option value="UNVERIFIED">Unverified</option><option value="UNKNOWN">Unknown</option></select>
        <div className="fact-actions"><button className="icon-button" onClick={() => setEditing(null)} aria-label="Cancel"><X /></button><button className="button primary subtle" disabled={busy === `edit-${f.id}`} onClick={() => saveEdit(f)}>Save</button></div>
      </div> : <div className="fact" key={f.id}>
        <div><b>{f.fact_key.replaceAll('_', ' ')}</b><span title={formatValue(f.value)}>{formatValue(f.value)}</span>{f.country_code && <small>{f.country_code} only</small>}</div>
        <div className="fact-actions"><Badge tone={f.status === 'VERIFIED' ? 'good' : f.status === 'EXPIRED' ? 'bad' : 'warn'}>{f.status}</Badge>
          <button className="icon-button" onClick={() => startEdit(f)} aria-label={`Edit ${f.fact_key}`}><Pencil /></button>
          <button className="icon-button" onClick={() => f.id && confirm(`Delete ${f.fact_key.replaceAll('_', ' ')}?`) && run(`del-${f.id}`, () => api.deleteFact(f.id!), 'Fact deleted')} aria-label={`Delete ${f.fact_key}`}><Trash2 /></button></div>
      </div>)}
    </section>)}</div>
  </>
}

function TriToggle({ value, onChange }: { value: Tri; onChange: (v: Tri) => void }) {
  const options: [Tri, string][] = [[true, 'Yes'], [false, 'No'], [null, 'Unknown']]
  return <div className="segmented">{options.map(([v, label]) => <button key={label} className={value === v ? `active ${label.toLowerCase()}` : ''} onClick={() => value !== v && onChange(v)}>{label}</button>)}</div>
}
