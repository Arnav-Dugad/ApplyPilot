import { useState } from 'react'
import { Briefcase, ExternalLink, Languages, Pencil, Plus, Trash2, X } from 'lucide-react'
import { api } from '../api'
import type { Fact } from '../types'
import { Badge, Empty, useAction } from '../ui'

const COMMON_LANGUAGES = ['English', 'Hindi', 'Arabic', 'French', 'German', 'Spanish', 'Mandarin', 'Japanese', 'Tamil', 'Urdu', 'Portuguese', 'Italian']

export function LanguagesPanel({ facts, refresh }: { facts: Fact[]; refresh: () => Promise<void> }) {
  const { run } = useAction(refresh)
  const fact = facts.find(f => f.category === 'languages' && f.fact_key === 'spoken')
  const spoken = Array.isArray(fact?.value) && fact?.status === 'VERIFIED' ? (fact.value as string[]) : []
  const [adding, setAdding] = useState('')
  const save = (next: string[], message: string) => run('langs', () => api.saveFact({ category: 'languages', fact_key: 'spoken', value: next, status: next.length ? 'VERIFIED' : 'UNKNOWN', source: 'USER' }), message)
  const add = (name: string) => { const clean = name.trim(); if (!clean || spoken.some(s => s.toLowerCase() === clean.toLowerCase())) return; save([...spoken, clean], `${clean} added — jobs re-checked`); setAdding('') }
  return <section className="panel"><div className="panel-head"><div><h2><Languages size={15} /> Languages you speak</h2><p>Jobs that require a language you haven't listed are flagged before you apply. English is assumed.</p></div><Badge tone={spoken.length ? 'good' : 'warn'}>{spoken.length ? `${spoken.length} verified` : 'Not set'}</Badge></div>
    <div className="lang-chips">{spoken.map(l => <span key={l} className="chip done">{l}<button onClick={() => save(spoken.filter(s => s !== l), `${l} removed`)} aria-label={`Remove ${l}`}><X size={11} /></button></span>)}
      {COMMON_LANGUAGES.filter(l => !spoken.some(s => s.toLowerCase() === l.toLowerCase())).slice(0, 8).map(l => <button key={l} className="chip" onClick={() => add(l)}><Plus size={11} />{l}</button>)}
      <span className="chip-input"><input value={adding} onChange={e => setAdding(e.target.value)} onKeyDown={e => e.key === 'Enter' && add(adding)} placeholder="Other…" /></span></div>
  </section>
}

type Project = { name: string; description: string; skills: string; link: string }
const blank: Project = { name: '', description: '', skills: '', link: '' }
const slug = (name: string) => name.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '').slice(0, 40) || 'project'

export function ProjectsPanel({ facts, refresh }: { facts: Fact[]; refresh: () => Promise<void> }) {
  const { run, busy } = useAction(refresh)
  const projects = facts.filter(f => f.category === 'projects' && f.status === 'VERIFIED')
  const [form, setForm] = useState<(Project & { key?: string }) | null>(null)
  const save = async () => {
    if (!form || !form.name.trim()) return
    if (form.link && !/^https?:\/\//.test(form.link)) return
    const value = { name: form.name.trim(), description: form.description.trim(), skills: form.skills.split(',').map(s => s.trim()).filter(Boolean), link: form.link.trim() || undefined }
    const ok = await run('project', () => api.saveFact({ category: 'projects', fact_key: form.key ?? slug(form.name), value, status: 'VERIFIED', source: 'USER' }), 'Project saved — interview prep will use it')
    if (ok) setForm(null)
  }
  return <section className="panel"><div className="panel-head"><div><h2><Briefcase size={15} /> Projects</h2><p>Interview prep matches your projects to each job's skills so you know what to talk about.</p></div>
    <button className="button subtle" onClick={() => setForm({ ...blank })}><Plus size={14} /> Add project</button></div>
    {form && <div className="project-form"><div className="form-grid">
      <label>Name *<input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} autoFocus placeholder="Ledger API" /></label>
      <label>Link<input value={form.link} onChange={e => setForm({ ...form, link: e.target.value })} placeholder="https://github.com/…" /></label>
      <label className="span-2">What you built<textarea value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} placeholder="A double-entry ledger service in Python and PostgreSQL, handling 1,200 requests/sec." /></label>
      <label className="span-2">Skills used (comma separated)<input value={form.skills} onChange={e => setForm({ ...form, skills: e.target.value })} placeholder="Python, PostgreSQL, Docker" /></label></div>
      {form.link && !/^https?:\/\//.test(form.link) && <p className="warn-text small">Links must start with https://</p>}
      <div className="form-actions"><button className="button ghost" onClick={() => setForm(null)}>Cancel</button><button className="button primary" disabled={!form.name.trim() || busy === 'project'} onClick={save}>Save project</button></div></div>}
    {projects.length ? <div className="project-list">{projects.map(p => { const v = (p.value ?? {}) as { name?: string; description?: string; skills?: string[]; link?: string }
      return <article key={p.id} className="project-card"><div><b>{v.name}</b>{v.link && <a href={v.link} target="_blank" rel="noreferrer"><ExternalLink size={12} /></a>}<p>{v.description}</p><div className="skill-line">{(v.skills ?? []).map(s => <Badge key={s}>{s}</Badge>)}</div></div>
        <div className="fact-actions"><button className="icon-button" aria-label="Edit project" onClick={() => setForm({ key: p.fact_key, name: v.name ?? '', description: v.description ?? '', skills: (v.skills ?? []).join(', '), link: v.link ?? '' })}><Pencil /></button>
          <button className="icon-button" aria-label="Delete project" onClick={() => p.id && confirm(`Delete ${v.name}?`) && run('del', () => api.deleteFact(p.id!), 'Project deleted')}><Trash2 /></button></div></article> })}</div>
      : !form && <Empty icon={Briefcase} title="No projects yet" text="Add two or three projects you're proud of. They power interview prep and your profile strength." action={() => setForm({ ...blank })} actionLabel="Add a project" />}
  </section>
}
