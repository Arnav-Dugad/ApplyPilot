import { useState } from 'react'
import { AlertTriangle, Check, ChevronRight, CircleHelp, FileText, ShieldCheck } from 'lucide-react'
import { api, readFileBase64 } from '../api'
import type { Fact } from '../types'
import { Badge, Logo } from '../ui'

const list = (text: string) => text.split(',').map(x => x.trim()).filter(Boolean)

export function Wizard({ onComplete }: { onComplete: () => Promise<void> }) {
  const [step, setStep] = useState(0)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [cv, setCV] = useState<{ name: string; base64: string } | null>(null)
  const [form, setForm] = useState({ name: '', email: '', university: 'Manipal Institute of Technology', degree: 'Computer Science', graduation: '', skills: '', locations: 'India, UAE, Saudi Arabia, Qatar, Bahrain, Kuwait, Oman, Europe, UK, Singapore' })
  const steps = ['Welcome', 'Import CV', 'Review profile', 'Verify education', 'Verify skills', 'Locations', 'Work authorization', 'Sponsorship', 'Preferences', 'Answer Vault', 'Local AI', 'Safety check']
  const set = (key: keyof typeof form) => (e: { target: { value: string } }) => setForm({ ...form, [key]: e.target.value })
  const fact = (category: string, fact_key: string, value: unknown, present: boolean): Fact =>
    ({ category, fact_key, value: present ? value : null, status: present ? 'VERIFIED' : 'UNKNOWN', source: 'FIRST_RUN_WIZARD' })

  const save = async () => {
    setBusy(true)
    setError('')
    try {
      if (cv) await api.importCV(cv.name, cv.base64).catch(e => { if (!String(e.message).includes('already in your library')) throw e })
      const entries = [
        fact('personal', 'full_name', form.name.trim(), Boolean(form.name.trim())),
        fact('contact', 'email', form.email.trim(), Boolean(form.email.trim())),
        fact('education', 'university', form.university.trim(), Boolean(form.university.trim())),
        fact('education', 'degree', form.degree.trim(), Boolean(form.degree.trim())),
        fact('education', 'graduation_date', form.graduation, Boolean(form.graduation)),
        fact('skills', 'verified_skills', list(form.skills), list(form.skills).length > 0),
        fact('preferences', 'locations', list(form.locations), list(form.locations).length > 0),
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

  return <div className="wizard-shell">
    <div className="wizard-brand"><Logo /><p>Private by default. Precise by design.</p></div>
    <div className="wizard-card">
      <div className="wizard-progress"><span>Step {step + 1} of {steps.length}</span><div><i style={{ width: `${((step + 1) / steps.length) * 100}%` }} /></div></div>
      <div className="wizard-icon"><ShieldCheck size={28} /></div>
      <h1>{step === 0 ? 'Welcome to ApplyPilot' : steps[step]}</h1>
      <p className="lede">{step === 0 ? 'Your local internship copilot — built to move fast without ever making up facts about you.' : 'Review each value carefully. Nothing becomes verified until you approve it.'}</p>
      {step === 0 && <div className="promise"><ShieldCheck /><div><b>Zero-guess guarantee</b><span>Unknown personal answers always stop automation.</span></div></div>}
      {step === 1 && <label className="dropzone"><FileText /><b>{cv ? cv.name : 'Choose your CV (PDF)'}</b><span>Extraction is staged as unverified for your review. You can skip this and add CVs later.</span><input type="file" accept="application/pdf" onChange={e => pickCV(e.target.files?.[0])} /></label>}
      {step === 2 && <div className="fields"><label>Full legal name<input value={form.name} onChange={set('name')} placeholder="Not stored until you finish" autoFocus /></label><label>Email<input value={form.email} onChange={set('email')} type="email" /></label></div>}
      {step === 3 && <div className="fields"><label>University<input value={form.university} onChange={set('university')} /></label><label>Degree<input value={form.degree} onChange={set('degree')} /></label><label>Graduation date<input value={form.graduation} onChange={set('graduation')} type="month" /></label></div>}
      {step === 4 && <label className="field-full">Verified skills, comma separated<textarea value={form.skills} onChange={set('skills')} placeholder="Java, Python, Git, Data Structures" /></label>}
      {step === 5 && <label className="field-full">Enabled locations<textarea value={form.locations} onChange={set('locations')} /></label>}
      {(step === 6 || step === 7) && <div className="attention"><AlertTriangle /><div><b>Country-specific and currently unknown</b><p>ApplyPilot asks separately for every country and never copies citizenship, residence, authorization, or sponsorship answers between countries. Set them per country in Profile → Work authorization.</p></div></div>}
      {step === 8 && <div className="choice-grid"><button className="choice active">Internships only<Check /></button><button className="choice">Remote or on-site</button><button className="choice">Review before submit<Check /></button></div>}
      {step === 9 && <div className="attention"><CircleHelp /><div><b>Sensitive answers start as Manual Only</b><p>You can approve exact recurring answers later, with country and company scope.</p></div></div>}
      {step === 10 && <div className="choice-grid"><button className="choice active">Off <Badge tone="good">Default</Badge></button><button className="choice">Ollama</button><button className="choice" disabled>Future provider</button></div>}
      {step === 11 && <div className="safety-list">{['Strict Accuracy Mode is on', 'Dry Run is on', 'Actual submissions are off', 'Unknown answers pause', 'CAPTCHA and MFA pause'].map(x => <div key={x}><Check /> {x}</div>)}</div>}
      {error && <div className="error-banner wizard-error"><AlertTriangle /><span>{error}</span></div>}
      <div className="wizard-actions"><button className="button ghost" disabled={step === 0 || busy} onClick={() => setStep(step - 1)}>Back</button>{step < steps.length - 1 ? <button className="button primary" onClick={() => setStep(step + 1)}>Continue <ChevronRight size={17} /></button> : <button className="button primary" disabled={busy} onClick={save}>{busy ? 'Saving…' : 'Finish safety setup'} <Check size={17} /></button>}</div>
    </div>
  </div>
}
