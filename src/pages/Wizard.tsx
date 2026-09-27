import { useState } from 'react'
import { AlertTriangle, Briefcase, Check, ChevronRight, FileText, Globe2, GraduationCap, Link2, ShieldCheck, Sparkles, UserRound, Wrench } from 'lucide-react'
import { api, readFileBase64 } from '../api'
import type { Fact } from '../types'
import { Logo } from '../ui'
import { CountryList, DEGREES } from '../components/AboutYou'

const list = (text: string) => text.split(',').map(x => x.trim()).filter(Boolean)
const LOCATION_CHIPS = ['India', 'Europe', 'United States', 'UK', 'Germany', 'Canada', 'Singapore', 'UAE', 'Australia', 'Remote']
const LANGUAGE_CHIPS = ['English', 'Hindi', 'Arabic', 'French', 'German', 'Spanish', 'Mandarin', 'Tamil']
const CITIZEN_CHIPS = ['India', 'United States', 'United Kingdom', 'Canada', 'Germany', 'Pakistan', 'Bangladesh', 'Nepal', 'Sri Lanka', 'UAE']
const SKILL_CHIPS = ['Python', 'Java', 'C++', 'C', 'JavaScript', 'React', 'SQL', 'Git', 'Data Structures', 'Machine Learning', 'HTML', 'CSS']

const STEPS: [string, typeof Sparkles, string][] = [
  ['Welcome', Sparkles, 'ApplyPilot finds internships for you across the internet, tells you in plain words if you can apply, and fills in the forms. You always press submit yourself.'],
  ['Your CV', FileText, 'Optional. ApplyPilot reads it and suggests details for your profile — nothing is saved until you confirm it.'],
  ['About you', UserRound, 'Used on the first page of every application.'],
  ['Your studies', GraduationCap, 'Jobs often ask for a degree, a graduation year, or a year of study. ApplyPilot checks these for you.'],
  ['Your skills', Wrench, 'Only skills you really have. Jobs are scored on how many of their must-have skills you know.'],
  ['Where you can work', Globe2, 'Tell ApplyPilot your citizenship and it works out which countries need a visa — for every job, automatically.'],
  ['Your links', Link2, 'Optional. Filled into the LinkedIn and GitHub boxes on forms. Your GitHub projects can be imported later in one click.'],
  ['Experience', Briefcase, 'Many postings ask for years of experience. ApplyPilot flags those so you can focus on the ones made for students.'],
  ['You’re all set', ShieldCheck, 'Here is how ApplyPilot keeps you safe.'],
]

export function Wizard({ onComplete }: { onComplete: () => Promise<void> }) {
  const [step, setStep] = useState(0)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [cv, setCV] = useState<{ name: string; base64: string } | null>(null)
  const [form, setForm] = useState({ name: '', email: '', university: '', degree: '', major: '', year: '', graduation: '', skills: '', citizenship: '', locations: '', languages: '', linkedin: '', github: '', noExperience: true })
  const toggleChip = (key: 'locations' | 'languages' | 'citizenship' | 'skills', value: string) => {
    const items = list(form[key])
    const next = items.some(i => i.toLowerCase() === value.toLowerCase()) ? items.filter(i => i.toLowerCase() !== value.toLowerCase()) : [...items, value]
    setForm({ ...form, [key]: next.join(', ') })
  }
  const set = (key: keyof typeof form) => (e: { target: { value: string } }) => setForm({ ...form, [key]: e.target.value })
  const fact = (category: string, fact_key: string, value: unknown, present: boolean): Fact =>
    ({ category, fact_key, value: present ? value : null, status: present ? 'VERIFIED' : 'UNKNOWN', source: 'FIRST_RUN_WIZARD' })
  const link = (text: string) => { const t = text.trim(); return !t ? '' : /^https?:\/\//i.test(t) ? t.replace(/^http:/i, 'https:') : `https://${t}` }

  const save = async () => {
    setBusy(true)
    setError('')
    try {
      if (cv) await api.importCV(cv.name, cv.base64).catch(e => { if (!String(e.message).includes('already in your library')) throw e })
      const degree = DEGREES.find(d => d[0] === form.degree)
      const linkedin = link(form.linkedin), github = link(form.github)
      const entries = [
        fact('personal', 'full_name', form.name.trim(), Boolean(form.name.trim())),
        fact('contact', 'email', form.email.trim(), Boolean(form.email.trim())),
        fact('education', 'university', form.university.trim(), Boolean(form.university.trim())),
        fact('education', 'degree_name', form.degree, Boolean(form.degree)),
        fact('education', 'level', degree?.[2], Boolean(degree)),
        fact('education', 'program_years', degree?.[3], Boolean(degree)),
        fact('education', 'degree', form.major.trim(), Boolean(form.major.trim())),
        fact('education', 'year_of_study', Number(form.year), Boolean(form.year)),
        fact('education', 'graduation_date', form.graduation, Boolean(form.graduation)),
        fact('skills', 'verified_skills', list(form.skills), list(form.skills).length > 0),
        fact('citizenship', 'countries', list(form.citizenship), list(form.citizenship).length > 0),
        fact('preferences', 'locations', list(form.locations), list(form.locations).length > 0),
        fact('languages', 'spoken', list(form.languages), list(form.languages).length > 0),
        fact('contact', 'linkedin', linkedin, /linkedin\.com\/in\//i.test(linkedin)),
        fact('contact', 'github', github, /^https:\/\/github\.com\/[A-Za-z0-9-]+\/?$/.test(github)),
        fact('experience', 'none', true, form.noExperience),
      ]
      for (const entry of entries) await api.saveFact(entry)
      await api.settings({ first_run_complete: true })
      await onComplete()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Setup could not be saved')
      setBusy(false)
    }
  }

  const pickCV = async (file?: File) => {
    if (!file) return
    try { setCV({ name: file.name, base64: await readFileBase64(file) }) } catch (e) { setError(e instanceof Error ? e.message : 'Could not read file') }
  }
  const chips = (key: 'locations' | 'languages' | 'citizenship' | 'skills', options: string[]) => <div className="chip-row">{options.map(c => <button key={c} type="button" className={list(form[key]).some(i => i.toLowerCase() === c.toLowerCase()) ? 'on' : ''} onClick={() => toggleChip(key, c)}>{c}</button>)}</div>
  const [title, Icon, lede] = STEPS[step]

  return <div className="wizard-shell">
    <div className="wizard-brand"><Logo /><p>Private: everything stays on this computer.</p></div>
    <div className="wizard-card">
      <div className="wizard-progress"><span>Step {step + 1} of {STEPS.length}</span><div><i style={{ width: `${((step + 1) / STEPS.length) * 100}%` }} /></div></div>
      <div className="wizard-icon" key={step}><Icon size={28} /></div>
      <h1>{step === 0 ? 'Welcome to ApplyPilot' : title}</h1>
      <p className="lede">{lede}</p>
      <div className="wizard-step" key={`s${step}`}>
        {step === 0 && <div className="promise"><ShieldCheck /><div><b>It never guesses about you</b><span>If ApplyPilot doesn't know an answer, it stops and asks you. It never submits an application for you.</span></div></div>}
        {step === 1 && <label className="dropzone"><FileText /><b>{cv ? cv.name : 'Choose your CV (PDF)'}</b><span>You can skip this and add CVs later.</span><input type="file" accept="application/pdf" onChange={e => pickCV(e.target.files?.[0])} /></label>}
        {step === 2 && <div className="fields"><label>Full name (as on your passport)<input value={form.name} onChange={set('name')} autoFocus /></label><label>Email<input value={form.email} onChange={set('email')} type="email" /></label></div>}
        {step === 3 && <div className="fields">
          <label>University or college<input value={form.university} onChange={set('university')} placeholder="Manipal Institute of Technology" autoFocus /></label>
          <label>Degree<select value={form.degree} onChange={set('degree')}><option value="">Choose…</option>{DEGREES.map(d => <option key={d[0]} value={d[0]}>{d[1]}</option>)}</select></label>
          <label>Field of study<input value={form.major} onChange={set('major')} placeholder="Computer Science and Engineering" /></label>
          <label>Year you're in<select value={form.year} onChange={set('year')}><option value="">Choose…</option>{[1, 2, 3, 4, 5].map(n => <option key={n} value={n}>{n}{['st', 'nd', 'rd'][n - 1] ?? 'th'} year</option>)}</select></label>
          <label>Graduation month<input value={form.graduation} onChange={set('graduation')} type="month" /></label>
        </div>}
        {step === 4 && <div className="fields single"><label className="field-full">Skills, separated by commas<textarea value={form.skills} onChange={set('skills')} placeholder="Python, Java, SQL, Git" autoFocus /></label>{chips('skills', SKILL_CHIPS)}</div>}
        {step === 5 && <div className="fields single">
          <CountryList />
          <label className="field-full">Your citizenship<input value={form.citizenship} onChange={set('citizenship')} list="country-list" placeholder="India" /></label>{chips('citizenship', CITIZEN_CHIPS)}
          <label className="field-full">Where would you like to work? Countries, regions or “Remote”<input value={form.locations} onChange={set('locations')} placeholder="India, Europe, Singapore" /></label>{chips('locations', LOCATION_CHIPS)}
          <label className="field-full">Languages you speak<input value={form.languages} onChange={set('languages')} placeholder="English, Hindi" /></label>{chips('languages', LANGUAGE_CHIPS)}
        </div>}
        {step === 6 && <div className="fields"><label>LinkedIn<input value={form.linkedin} onChange={set('linkedin')} placeholder="linkedin.com/in/you" /></label><label>GitHub<input value={form.github} onChange={set('github')} placeholder="github.com/you" /></label></div>}
        {step === 7 && <div className="choice-grid two">
          <button type="button" className={`choice ${form.noExperience ? 'active' : ''}`} onClick={() => setForm({ ...form, noExperience: true })}><span><b>No work experience yet</b><small>Totally normal for students</small></span>{form.noExperience && <Check />}</button>
          <button type="button" className={`choice ${!form.noExperience ? 'active' : ''}`} onClick={() => setForm({ ...form, noExperience: false })}><span><b>I have some</b><small>Add it in My profile after setup</small></span>{!form.noExperience && <Check />}</button>
        </div>}
        {step === 8 && <div className="safety-list">{['You press submit — always', 'Unknown answers stop and ask you', 'Passwords and CAPTCHAs are left to you', 'Everything stays on this computer', 'Visa needs worked out from your citizenship', 'You can change anything later in My profile'].map(x => <div key={x}><Check /> {x}</div>)}</div>}
      </div>
      {error && <div className="error-banner wizard-error"><AlertTriangle /><span>{error}</span></div>}
      <div className="wizard-actions"><button className="button ghost" disabled={step === 0 || busy} onClick={() => setStep(step - 1)}>Back</button>{step < STEPS.length - 1 ? <button className="button primary" onClick={() => setStep(step + 1)}>{step === 0 ? 'Let’s start' : 'Continue'} <ChevronRight size={17} /></button> : <button className="button primary" disabled={busy} onClick={save}>{busy ? 'Saving…' : 'Start using ApplyPilot'} <Check size={17} /></button>}</div>
    </div>
  </div>
}
