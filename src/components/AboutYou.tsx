import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { Award, BadgeCheck, BriefcaseBusiness, ExternalLink, Github, Globe2, GraduationCap, Linkedin, Link2, MapPin, Pencil, Plane, Plus, Target, Trash2, UserRound, X } from 'lucide-react'
import { api } from '../api'
import type { Bootstrap, Certification, ExperienceEntry, Fact, VisaRow } from '../types'
import { Badge, useNotify } from '../ui'

// ---------- shared helpers ----------

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
export const monthLabel = (value?: string | null) => { const m = /^(\d{4})-(\d{2})/.exec(value ?? ''); return m ? `${MONTHS[Number(m[2]) - 1]} ${m[1]}` : value ?? '' }
const isEmpty = (v: unknown) => v === null || v === undefined || v === '' || (Array.isArray(v) && v.length === 0)

export function factValue<T = unknown>(facts: Fact[], category: string, key: string): T | undefined {
  const f = facts.find(x => x.category === category && x.fact_key === key && !x.country_code)
  return f?.status === 'VERIFIED' ? f.value as T : undefined
}

/** Saves one profile fact the moment you change it, with a quiet confirmation. Empty values clear the fact. */
export function useFactSaver(refresh: () => Promise<void>) {
  const notify = useNotify()
  const [saving, setSaving] = useState<string | null>(null)
  const save = async (category: string, key: string, value: unknown, message = 'Saved') => {
    setSaving(`${category}.${key}`)
    try {
      await api.saveFact({ category, fact_key: key, value: isEmpty(value) ? null : value, status: isEmpty(value) ? 'UNKNOWN' : 'VERIFIED', source: 'USER' })
      await refresh()
      notify(message)
      return true
    } catch (e) { notify(e instanceof Error ? e.message : 'Could not save', 'bad'); return false } finally { setSaving(null) }
  }
  return { save, saving }
}

function Panel({ id, icon: Icon, title, text, badge, children, action }: { id: string; icon: typeof Globe2; title: string; text: string; badge?: ReactNode; children: ReactNode; action?: ReactNode }) {
  return <section className="panel about-panel" id={id}><div className="panel-head"><div><h2><Icon size={15} /> {title}</h2><p>{text}</p></div><div className="panel-head-side">{badge}{action}</div></div>{children}</section>
}

/** A text field that saves when you leave it or press Enter. */
function Field({ label, value, placeholder, onSave, type = 'text', hint, className = '' }: { label: string; value?: string | number | null; placeholder?: string; onSave: (v: string) => void; type?: string; hint?: string; className?: string }) {
  const [text, setText] = useState(value == null ? '' : String(value))
  useEffect(() => { setText(value == null ? '' : String(value)) }, [value])
  const commit = () => { if (text.trim() !== (value == null ? '' : String(value))) onSave(text.trim()) }
  return <label className={`field ${className}`}><span>{label}</span><input type={type} value={text} placeholder={placeholder} onChange={e => setText(e.target.value)} onBlur={commit} onKeyDown={e => e.key === 'Enter' && (e.target as HTMLInputElement).blur()} />{hint && <small>{hint}</small>}</label>
}

function Choice<T extends string | number>({ label, value, options, onChange, hint }: { label: string; value?: T | null; options: [T, string][]; onChange: (v: T | null) => void; hint?: string }) {
  return <label className="field"><span>{label}</span><select value={value == null ? '' : String(value)} onChange={e => { const raw = e.target.value; const hit = options.find(([v]) => String(v) === raw); onChange(hit ? hit[0] : null) }}>
    <option value="">Not set</option>{options.map(([v, l]) => <option key={String(v)} value={String(v)}>{l}</option>)}</select>{hint && <small>{hint}</small>}</label>
}

function Chips({ items, onRemove, onAdd, placeholder, suggestions = [], list }: { items: string[]; onRemove: (v: string) => void; onAdd: (v: string) => void; placeholder: string; suggestions?: string[]; list?: string }) {
  const [text, setText] = useState('')
  const add = (v: string) => { const clean = v.trim(); if (clean && !items.some(i => i.toLowerCase() === clean.toLowerCase())) onAdd(clean); setText('') }
  return <div className="lang-chips">{items.map(i => <span key={i} className="chip done">{i}<button onClick={() => onRemove(i)} aria-label={`Remove ${i}`}><X size={11} /></button></span>)}
    {suggestions.filter(s => !items.some(i => i.toLowerCase() === s.toLowerCase())).slice(0, 8).map(s => <button key={s} className="chip" onClick={() => add(s)}><Plus size={11} />{s}</button>)}
    <span className="chip-input"><input value={text} list={list} onChange={e => { const v = e.target.value; setText(v); if (list && COUNTRIES.some(c => c === v)) add(v) }} onKeyDown={e => e.key === 'Enter' && add(text)} placeholder={placeholder} /></span></div>
}

const COUNTRIES = ['India', 'United States', 'United Kingdom', 'Germany', 'France', 'Netherlands', 'Ireland', 'Canada', 'Australia', 'Singapore', 'United Arab Emirates', 'Saudi Arabia', 'Qatar', 'Bahrain', 'Kuwait', 'Oman', 'Switzerland', 'Sweden', 'Norway', 'Denmark', 'Finland', 'Spain', 'Italy', 'Portugal', 'Poland', 'Belgium', 'Austria', 'Japan', 'South Korea', 'China', 'Hong Kong', 'Nepal', 'Sri Lanka', 'Bangladesh', 'Pakistan', 'New Zealand', 'Israel', 'Brazil', 'Mexico']
export function CountryList() { return <datalist id="country-list">{COUNTRIES.map(c => <option key={c} value={c} />)}</datalist> }

// ---------- panels ----------

export function BasicsPanel({ facts, refresh }: { facts: Fact[]; refresh: () => Promise<void> }) {
  const { save } = useFactSaver(refresh)
  const v = (c: string, k: string) => factValue<string>(facts, c, k)
  return <Panel id="basics" icon={UserRound} title="Basics" text="Used to fill the first page of every application form.">
    <div className="field-grid">
      <Field label="Full legal name" value={v('personal', 'full_name')} placeholder="As on your passport" onSave={x => save('personal', 'full_name', x)} />
      <Field label="Email" type="email" value={v('contact', 'email')} placeholder="you@example.com" onSave={x => save('contact', 'email', x)} />
      <Field label="Phone" value={v('contact', 'phone')} placeholder="+91 98765 43210" hint="Include your country code" onSave={x => save('contact', 'phone', x)} />
      <Field label="City you live in" value={v('contact', 'location')} placeholder="Manipal, India" onSave={x => save('contact', 'location', x)} />
      <Field label="Address" value={v('contact', 'address')} placeholder="Street, city" className="span-2" onSave={x => save('contact', 'address', x)} />
      <Field label="PIN / postal code" value={v('contact', 'postal_code')} placeholder="576104" onSave={x => save('contact', 'postal_code', x)} />
    </div>
  </Panel>
}

export const DEGREES: [string, string, 'BACHELOR' | 'MASTER' | 'PHD', number][] = [
  ['B.Tech', 'B.Tech (Bachelor of Technology)', 'BACHELOR', 4], ['B.E.', 'B.E. (Bachelor of Engineering)', 'BACHELOR', 4], ['B.Sc', 'B.Sc (Bachelor of Science)', 'BACHELOR', 3],
  ['BCA', 'BCA (Bachelor of Computer Applications)', 'BACHELOR', 3], ['B.S.', 'B.S. (US-style Bachelor of Science)', 'BACHELOR', 4], ['B.A.', 'B.A. (Bachelor of Arts)', 'BACHELOR', 3],
  ['M.Tech', 'M.Tech', 'MASTER', 2], ['M.S.', 'M.S. (Master of Science)', 'MASTER', 2], ['M.Sc', 'M.Sc', 'MASTER', 2], ['MCA', 'MCA', 'MASTER', 2], ['MBA', 'MBA', 'MASTER', 2], ['PhD', 'PhD', 'PHD', 5],
]

export function EducationPanel({ data, refresh }: { data: Bootstrap; refresh: () => Promise<void> }) {
  const { facts } = data
  const { save } = useFactSaver(refresh)
  const me = data.student
  const degreeName = factValue<string>(facts, 'education', 'degree_name')
  const known = DEGREES.find(d => d[0] === degreeName)
  const cgpa = factValue<{ value: number; scale: number }>(facts, 'education', 'cgpa')
  const [gpaText, setGpaText] = useState(cgpa ? String(cgpa.value) : '')
  const [scale, setScale] = useState(cgpa?.scale ?? 10)
  useEffect(() => { setGpaText(cgpa ? String(cgpa.value) : ''); setScale(cgpa?.scale ?? 10) }, [cgpa?.value, cgpa?.scale])
  const saveGpa = (text: string, s: number) => {
    const n = Number(text)
    if (!text.trim()) return save('education', 'cgpa', null, 'CGPA cleared')
    if (!Number.isFinite(n) || n <= 0 || n > s) return
    save('education', 'cgpa', { value: n, scale: s }, 'CGPA saved — GPA requirements re-checked')
  }
  const chooseDegree = async (name: string | null) => {
    await save('education', 'degree_name', name, 'Degree saved')
    const d = DEGREES.find(x => x[0] === name)
    if (d) {
      await save('education', 'level', d[2], 'Degree level set')
      if (!factValue(facts, 'education', 'program_years')) await save('education', 'program_years', d[3], `Course length set to ${d[3]} years`)
    }
  }
  const semester = factValue<number>(facts, 'education', 'semester')
  const year = factValue<number>(facts, 'education', 'year_of_study')
  const derivedYear = me?.derived.includes('year_of_study') ? me.year_of_study : null
  const enrolled = factValue<boolean>(facts, 'education', 'enrolled')

  return <Panel id="education" icon={GraduationCap} title="Education" text="ApplyPilot compares this with each job's degree, graduation-year and GPA rules."
    badge={me?.level ? <Badge tone="good">{me.level === 'BACHELOR' ? "Bachelor's" : me.level === 'MASTER' ? "Master's" : 'PhD'}{me.year_of_study ? ` · year ${me.year_of_study}` : ''}</Badge> : undefined}>
    <div className="field-grid">
      <Field label="University or college" value={factValue<string>(facts, 'education', 'university')} placeholder="Manipal Institute of Technology" className="span-2" onSave={x => save('education', 'university', x)} />
      <Choice label="Degree" value={known ? known[0] : degreeName ? '__other' : null} options={[...DEGREES.map(d => [d[0], d[1]] as [string, string]), ...(degreeName && !known ? [['__other', degreeName] as [string, string]] : [])]} onChange={x => x !== '__other' && chooseDegree(x)} />
      <Field label="Field of study (major)" value={factValue<string>(facts, 'education', 'degree')} placeholder="Computer Science and Engineering" onSave={x => save('education', 'degree', x, 'Field of study saved')} />
      <Choice label="Year you're in" value={year ?? null} options={[1, 2, 3, 4, 5].map(n => [n, `${n}${['st', 'nd', 'rd'][n - 1] ?? 'th'} year`] as [number, string])} onChange={x => save('education', 'year_of_study', x, 'Year of study saved')}
        hint={!year && derivedYear ? `Looks like year ${derivedYear} from your graduation date` : undefined} />
      <Choice label="Semester" value={semester ?? null} options={Array.from({ length: 10 }, (_, i) => [i + 1, `Semester ${i + 1}`] as [number, string])}
        onChange={async x => { await save('education', 'semester', x, 'Semester saved'); if (x && !year) await save('education', 'year_of_study', Math.ceil(x / 2), `Year of study set to ${Math.ceil(x / 2)}`) }} />
      <Choice label="Course length" value={factValue<number>(facts, 'education', 'program_years') ?? null} options={[3, 4, 5].map(n => [n, `${n} years`] as [number, string])} onChange={x => save('education', 'program_years', x, 'Course length saved')} />
      <Field label="Graduation month" type="month" value={factValue<string>(facts, 'education', 'graduation_date')} onSave={x => save('education', 'graduation_date', x, 'Graduation date saved — graduation-year rules re-checked')} />
      <div className="field"><span>CGPA</span><div className="inline-inputs"><input inputMode="decimal" value={gpaText} placeholder="8.7" onChange={e => setGpaText(e.target.value)} onBlur={() => saveGpa(gpaText, scale)} onKeyDown={e => e.key === 'Enter' && (e.target as HTMLInputElement).blur()} />
        <select value={scale} onChange={e => { const s = Number(e.target.value); setScale(s); if (gpaText.trim()) saveGpa(gpaText, s) }}>{[10, 4, 5, 100].map(s => <option key={s} value={s}>out of {s}</option>)}</select></div>
        {gpaText && Number(gpaText) > scale && <small className="warn-text">Higher than the scale</small>}</div>
      <div className="field"><span>Are you studying right now?</span><div className="segmented">{([[true, 'Yes'], [false, 'No, I graduated']] as [boolean, string][]).map(([v, l]) => <button key={l} className={enrolled === v ? `active ${v ? 'yes' : 'no'}` : ''} onClick={() => save('education', 'enrolled', v)}>{l}</button>)}</div>
        {enrolled === undefined && me?.enrolled && <small>Worked out from your graduation date</small>}</div>
    </div>
  </Panel>
}

const LINK_RULES: [string, string, typeof Linkedin, string, RegExp][] = [
  ['linkedin', 'LinkedIn', Linkedin, 'https://www.linkedin.com/in/you', /^https:\/\/([a-z]{2,3}\.)?linkedin\.com\/in\/[^/\s]+\/?$/i],
  ['github', 'GitHub', Github, 'https://github.com/you', /^https:\/\/github\.com\/[A-Za-z0-9-]+\/?$/],
  ['website', 'Portfolio or website', Globe2, 'https://you.dev', /^https:\/\/[^\s.]+\.[^\s]+$/],
]
const normalizeLink = (text: string) => { const t = text.trim(); return !t ? '' : /^https?:\/\//i.test(t) ? t.replace(/^http:/i, 'https:') : `https://${t}` }

export function LinksPanel({ facts, refresh, onGitHub }: { facts: Fact[]; refresh: () => Promise<void>; onGitHub?: (user: string) => void }) {
  const { save } = useFactSaver(refresh)
  const [bad, setBad] = useState<string | null>(null)
  return <Panel id="links" icon={Link2} title="Links" text="Filled into the LinkedIn, GitHub and portfolio boxes on every form.">
    <div className="link-rows">{LINK_RULES.map(([key, label, Icon, placeholder, rule]) => { const value = factValue<string>(facts, 'contact', key)
      return <div key={key} className="link-row"><span className="link-icon"><Icon size={16} /></span>
        <Field label={label} value={value} placeholder={placeholder} onSave={x => { const link = normalizeLink(x); if (link && !rule.test(link)) { setBad(key); return } setBad(null); save('contact', key, link, `${label} saved`) }} hint={bad === key ? `That doesn't look like a ${label} link` : undefined} />
        {value && <a className="icon-button" href={value} target="_blank" rel="noreferrer" aria-label={`Open ${label}`}><ExternalLink /></a>}
        {key === 'github' && value && onGitHub && <button className="button subtle" onClick={() => onGitHub(value)}><Github size={14} /> Import projects</button>}
      </div> })}</div>
  </Panel>
}

export function WorkRightsPanel({ data, refresh, answerCountry }: { data: Bootstrap; refresh: () => Promise<void>; answerCountry: ReactNode }) {
  const { facts } = data
  const { save } = useFactSaver(refresh)
  const citizenship = factValue<string[]>(facts, 'citizenship', 'countries') ?? []
  const residency = factValue<string[]>(facts, 'citizenship', 'permanent_residency') ?? []
  const permits = factValue<{ country: string; kind?: string }[]>(facts, 'citizenship', 'work_permits') ?? []
  const [permit, setPermit] = useState<{ country: string; kind: string } | null>(null)
  const [showAnswers, setShowAnswers] = useState(false)
  const rows = data.visa ?? []
  const canWork = rows.filter(r => r.authorized === true || r.needs_visa === false).length
  return <Panel id="work-rights" icon={Plane} title="Where you can work" text="Tell ApplyPilot your citizenship and it works out every country for you — no more answering country by country."
    badge={rows.length ? <Badge tone="good">{canWork} of {rows.length} without a visa</Badge> : undefined}>
    <CountryList />
    <div className="field-grid">
      <div className="field span-2"><span>Citizenship</span><Chips items={citizenship} list="country-list" placeholder="Add a country…" suggestions={citizenship.length ? [] : ['India']}
        onAdd={c => save('citizenship', 'countries', [...citizenship, c], `Citizenship saved — ${c} worked out for every job`)} onRemove={c => save('citizenship', 'countries', citizenship.filter(x => x !== c), 'Citizenship updated')} /></div>
      <div className="field"><span>Permanent residency (green card, PR)</span><Chips items={residency} list="country-list" placeholder="None — add if you have one"
        onAdd={c => save('citizenship', 'permanent_residency', [...residency, c])} onRemove={c => save('citizenship', 'permanent_residency', residency.filter(x => x !== c))} /></div>
      <div className="field"><span>Visas or work permits you hold now</span>
        <div className="lang-chips">{permits.map(p => <span key={p.country + p.kind} className="chip done">{p.kind ? `${p.kind} · ` : ''}{p.country}<button onClick={() => save('citizenship', 'work_permits', permits.filter(x => x !== p))} aria-label="Remove"><X size={11} /></button></span>)}
          {permit ? <span className="permit-form"><input list="country-list" value={permit.country} onChange={e => setPermit({ ...permit, country: e.target.value })} placeholder="Country" autoFocus /><input value={permit.kind} onChange={e => setPermit({ ...permit, kind: e.target.value })} placeholder="e.g. F-1 student visa" />
            <button className="button subtle" disabled={!permit.country.trim()} onClick={async () => { if (await save('citizenship', 'work_permits', [...permits, { country: permit.country.trim(), kind: permit.kind.trim() || undefined }])) setPermit(null) }}>Add</button><button className="icon-button" onClick={() => setPermit(null)} aria-label="Cancel"><X /></button></span>
            : <button className="chip" onClick={() => setPermit({ country: '', kind: '' })}><Plus size={11} />Add a visa</button>}</div></div>
    </div>
    {rows.length > 0 && <div className="visa-grid">{rows.map((r, i) => <VisaTile key={r.country} row={r} index={i} />)}</div>}
    <button className="text-button" onClick={() => setShowAnswers(!showAnswers)}>{showAnswers ? 'Hide' : 'Answer a country yourself'} — your own answer always wins</button>
    {showAnswers && answerCountry}
  </Panel>
}

function VisaTile({ row, index }: { row: VisaRow; index: number }) {
  const state = row.authorized === true || row.needs_visa === false ? 'ok' : row.needs_visa === true || row.authorized === false ? 'visa' : 'unknown'
  return <div className={`visa-tile ${state}`} style={{ animationDelay: `${Math.min(index, 16) * 25}ms` }} title={row.reason}>
    <div className="visa-top"><b>{(row.name ?? row.country).replace(/^the /, '')}</b>{row.jobs ? <small>{row.jobs} job{row.jobs === 1 ? '' : 's'}</small> : null}</div>
    <span className="visa-state">{state === 'ok' ? <><BadgeCheck size={13} /> Can work</> : state === 'visa' ? <><Plane size={13} /> Needs a visa</> : 'Not sure yet'}</span>
    <small className="visa-source">{row.source === 'YOUR_ANSWER' ? 'Your answer' : row.source === 'CITIZENSHIP' ? 'From your citizenship' : 'Add citizenship'}</small>
  </div>
}

const KINDS: [ExperienceEntry['kind'], string][] = [['INTERNSHIP', 'Internship'], ['JOB', 'Full-time job'], ['PART_TIME', 'Part-time job'], ['RESEARCH', 'Research'], ['VOLUNTEER', 'Volunteering']]
const blankExp: ExperienceEntry = { title: '', company: '', kind: 'INTERNSHIP', start: '', end: '', description: '' }

export function ExperiencePanel({ data, refresh }: { data: Bootstrap; refresh: () => Promise<void> }) {
  const { facts } = data
  const { save } = useFactSaver(refresh)
  const entries = factValue<ExperienceEntry[]>(facts, 'experience', 'entries') ?? []
  const none = factValue<boolean>(facts, 'experience', 'none') === true
  const [form, setForm] = useState<(ExperienceEntry & { index?: number }) | null>(null)
  const saveEntry = async () => {
    if (!form || !form.title.trim() || !form.company.trim() || !form.start) return
    const clean: ExperienceEntry = { title: form.title.trim(), company: form.company.trim(), kind: form.kind, start: form.start, end: form.end || null, description: form.description?.trim() || undefined }
    const next = form.index != null ? entries.map((e, i) => i === form.index ? clean : e) : [...entries, clean]
    if (await save('experience', 'entries', next, 'Experience saved — experience rules re-checked')) {
      if (none) await save('experience', 'none', null, 'Updated')
      setForm(null)
    }
  }
  const years = data.student?.experience.work_years ?? 0
  return <Panel id="experience" icon={BriefcaseBusiness} title="Experience" text="Jobs that ask for years of experience are checked against this. Internships don't count as years of work."
    badge={none ? <Badge tone="accent">No experience yet</Badge> : entries.length ? <Badge tone="good">{entries.length} entr{entries.length === 1 ? 'y' : 'ies'}{years ? ` · ${years} yrs work` : ''}</Badge> : <Badge tone="warn">Not set</Badge>}
    action={<button className="button subtle" onClick={() => setForm({ ...blankExp })}><Plus size={14} /> Add</button>}>
    {!entries.length && <label className={`no-exp ${none ? 'on' : ''}`}><input type="checkbox" checked={none} onChange={e => save('experience', 'none', e.target.checked ? true : null, e.target.checked ? 'Got it — ApplyPilot will favour roles that need no experience' : 'Updated')} />
      <span><b>I don't have work experience yet</b><small>Totally normal for students. ApplyPilot flags jobs that ask for years of experience so you don't waste time.</small></span></label>}
    {form && <div className="project-form"><div className="form-grid">
      <label>Role *<input value={form.title} onChange={e => setForm({ ...form, title: e.target.value })} placeholder="Software Engineering Intern" autoFocus /></label>
      <label>Company *<input value={form.company} onChange={e => setForm({ ...form, company: e.target.value })} placeholder="Acme" /></label>
      <label>Type<select value={form.kind} onChange={e => setForm({ ...form, kind: e.target.value as ExperienceEntry['kind'] })}>{KINDS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></label>
      <div className="inline-inputs dates"><label>Started *<input type="month" value={form.start} onChange={e => setForm({ ...form, start: e.target.value })} /></label><label>Ended<input type="month" value={form.end ?? ''} onChange={e => setForm({ ...form, end: e.target.value })} /></label></div>
      <label className="span-2">What you did<textarea value={form.description ?? ''} onChange={e => setForm({ ...form, description: e.target.value })} placeholder="Built … which led to … (numbers help)" /></label></div>
      <small className="muted">Leave “Ended” empty if you still work there.</small>
      <div className="form-actions"><button className="button ghost" onClick={() => setForm(null)}>Cancel</button><button className="button primary" disabled={!form.title.trim() || !form.company.trim() || !form.start} onClick={saveEntry}>Save</button></div></div>}
    {entries.length > 0 && <div className="exp-list">{entries.map((e, i) => <article key={i} className="exp-item"><span className="exp-dot" /><div><b>{e.title} · {e.company}</b><span>{KINDS.find(k => k[0] === e.kind)?.[1]} · {monthLabel(e.start)} – {e.end ? monthLabel(e.end) : 'now'}</span>{e.description && <p>{e.description}</p>}</div>
      <div className="fact-actions"><button className="icon-button" aria-label="Edit" onClick={() => setForm({ ...e, end: e.end ?? '', index: i })}><Pencil /></button><button className="icon-button" aria-label="Delete" onClick={() => confirm(`Delete ${e.title}?`) && save('experience', 'entries', entries.filter((_, j) => j !== i), 'Removed')}><Trash2 /></button></div></article>)}</div>}
  </Panel>
}

const ROLE_PRESETS = ['Software engineering', 'Data science', 'AI / Machine learning', 'Product', 'Design', 'Quant', 'Hardware', 'Business']
const REGION_PRESETS = ['India', 'Europe', 'GCC', 'Remote', 'United States', 'United Kingdom', 'Singapore']

function suggestedWindows(year?: number | null, programYears?: number | null, graduation?: string | null): { label: string; start: string; end: string }[] {
  const now = new Date()
  const nextSummer = now.getMonth() >= 6 ? now.getFullYear() + 1 : now.getFullYear()
  const out = [{ label: `Summer break ${nextSummer}`, start: `${nextSummer}-05`, end: `${nextSummer}-07` }]
  const grad = /^(\d{4})-(\d{2})/.exec(graduation ?? '')
  if (grad && year && programYears && programYears - year <= 1) out.push({ label: `Final semester ${grad[1]}`, start: `${grad[1]}-01`, end: `${grad[1]}-06` })
  else if (grad) out.push({ label: `Final semester ${grad[1]}`, start: `${grad[1]}-01`, end: `${grad[1]}-06` })
  return out
}

export function PreferencesPanel({ data, refresh }: { data: Bootstrap; refresh: () => Promise<void> }) {
  const { facts } = data
  const { save } = useFactSaver(refresh)
  const roles = factValue<string[]>(facts, 'preferences', 'roles') ?? []
  const locations = factValue<string[]>(facts, 'preferences', 'locations') ?? []
  const windows = factValue<{ label?: string; start: string; end: string }[]>(facts, 'preferences', 'availability') ?? []
  const [win, setWin] = useState<{ start: string; end: string } | null>(null)
  const me = data.student
  const suggestions = useMemo(() => suggestedWindows(me?.year_of_study, me?.program_years, me?.graduation).filter(s => !windows.some(w => w.start === s.start && w.end === s.end)), [me, windows])
  const addWindow = (w: { label?: string; start: string; end: string }) => save('preferences', 'availability', [...windows, w].sort((a, b) => a.start.localeCompare(b.start)), 'Dates saved — jobs outside them are flagged')
  return <Panel id="preferences" icon={Target} title="What you're looking for" text="Autopilot only saves jobs that fit these, from every source it searches.">
    <div className="field-grid one">
      <div className="field"><span>Kinds of roles</span><Chips items={roles} suggestions={ROLE_PRESETS} placeholder="Other role…" onAdd={r => save('preferences', 'roles', [...roles, r], 'Roles saved')} onRemove={r => save('preferences', 'roles', roles.filter(x => x !== r), 'Roles saved')} />
        {!roles.length && <small>No roles picked means every kind of internship is kept.</small>}</div>
      <div className="field"><span><MapPin size={12} /> Places you'd work</span><Chips items={locations} suggestions={REGION_PRESETS} list="country-list" placeholder="Country, city or region…" onAdd={l => save('preferences', 'locations', [...locations, l], 'Locations saved — jobs re-ranked')} onRemove={l => save('preferences', 'locations', locations.filter(x => x !== l), 'Locations saved')} /><CountryList /></div>
      <div className="field"><span>When you're free for an internship</span>
        <div className="lang-chips">{windows.map((w, i) => <span key={i} className="chip done">{w.label ? `${w.label}: ` : ''}{monthLabel(w.start)} – {monthLabel(w.end)}<button aria-label="Remove" onClick={() => save('preferences', 'availability', windows.filter((_, j) => j !== i), 'Dates saved')}><X size={11} /></button></span>)}
          {suggestions.map(s => <button key={s.label} className="chip suggest" onClick={() => addWindow(s)}><Plus size={11} />{s.label} ({monthLabel(s.start)} – {monthLabel(s.end)})</button>)}
          {win ? <span className="permit-form"><input type="month" value={win.start} onChange={e => setWin({ ...win, start: e.target.value })} /><input type="month" value={win.end} onChange={e => setWin({ ...win, end: e.target.value })} />
            <button className="button subtle" disabled={!win.start || !win.end || win.end < win.start} onClick={async () => { await addWindow(win); setWin(null) }}>Add</button><button className="icon-button" onClick={() => setWin(null)} aria-label="Cancel"><X /></button></span>
            : <button className="chip" onClick={() => setWin({ start: '', end: '' })}><Plus size={11} />Other dates</button>}</div>
        <small>Used to warn you when an internship runs during your semester, and to answer “earliest start date”.</small></div>
    </div>
  </Panel>
}

export function CertificationsPanel({ facts, refresh }: { facts: Fact[]; refresh: () => Promise<void> }) {
  const { save } = useFactSaver(refresh)
  const list = factValue<Certification[]>(facts, 'certifications', 'list') ?? []
  const [form, setForm] = useState<Certification | null>(null)
  return <Panel id="certifications" icon={Award} title="Certifications & awards" text="Courses, certificates, hackathon wins and scholarships." action={<button className="button subtle" onClick={() => setForm({ name: '', issuer: '', year: '', link: '' })}><Plus size={14} /> Add</button>}>
    {form && <div className="project-form"><div className="form-grid">
      <label>Name *<input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} placeholder="AWS Cloud Practitioner" autoFocus /></label>
      <label>From<input value={form.issuer} onChange={e => setForm({ ...form, issuer: e.target.value })} placeholder="Amazon Web Services" /></label>
      <label>Year<input value={form.year} onChange={e => setForm({ ...form, year: e.target.value.replace(/[^0-9]/g, '').slice(0, 4) })} placeholder="2026" /></label>
      <label>Link<input value={form.link} onChange={e => setForm({ ...form, link: e.target.value })} placeholder="https://…" /></label></div>
      <div className="form-actions"><button className="button ghost" onClick={() => setForm(null)}>Cancel</button><button className="button primary" disabled={!form.name.trim() || Boolean(form.link && !/^https:\/\//.test(form.link))}
        onClick={async () => { if (await save('certifications', 'list', [...list, { name: form.name.trim(), issuer: form.issuer?.trim() || undefined, year: form.year || undefined, link: form.link?.trim() || undefined }], 'Added')) setForm(null) }}>Save</button></div></div>}
    {list.length ? <div className="cert-list">{list.map((c, i) => <div key={i} className="cert"><Award size={15} /><div><b>{c.name}</b><span>{[c.issuer, c.year].filter(Boolean).join(' · ')}</span></div>{c.link && <a className="icon-button" href={c.link} target="_blank" rel="noreferrer" aria-label="Open"><ExternalLink /></a>}
      <button className="icon-button" aria-label="Delete" onClick={() => save('certifications', 'list', list.filter((_, j) => j !== i), 'Removed')}><Trash2 /></button></div>)}</div>
      : !form && <p className="muted small">Nothing yet. Even an online course counts.</p>}
  </Panel>
}

export function ProfileNav({ items }: { items: [string, string][] }) {
  return <div className="profile-nav" role="navigation" aria-label="Profile sections">{items.map(([id, label]) => <button key={id} onClick={() => document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })}>{label}</button>)}</div>
}

