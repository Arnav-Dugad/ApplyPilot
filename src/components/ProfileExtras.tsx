import { useEffect, useRef, useState } from 'react'
import { Briefcase, Check, ExternalLink, Github, Languages, Pencil, Plus, Sparkles, Star, Trash2, X } from 'lucide-react'
import { api } from '../api'
import type { Fact, GitHubProject, GitHubRepo } from '../types'
import { Modal } from './Modal'
import { Badge, Empty, useAction, useNotify } from '../ui'

const COMMON_LANGUAGES = ['English', 'Hindi', 'Arabic', 'French', 'German', 'Spanish', 'Mandarin', 'Japanese', 'Tamil', 'Urdu', 'Portuguese', 'Italian']

export function LanguagesPanel({ facts, refresh }: { facts: Fact[]; refresh: () => Promise<void> }) {
  const { run } = useAction(refresh)
  const fact = facts.find(f => f.category === 'languages' && f.fact_key === 'spoken')
  const spoken = Array.isArray(fact?.value) && fact?.status === 'VERIFIED' ? (fact.value as string[]) : []
  const [adding, setAdding] = useState('')
  const save = (next: string[], message: string) => run('langs', () => api.saveFact({ category: 'languages', fact_key: 'spoken', value: next, status: next.length ? 'VERIFIED' : 'UNKNOWN', source: 'USER' }), message)
  const add = (name: string) => { const clean = name.trim(); if (!clean || spoken.some(s => s.toLowerCase() === clean.toLowerCase())) return; save([...spoken, clean], `${clean} added — jobs re-checked`); setAdding('') }
  return <section className="panel" id="languages"><div className="panel-head"><div><h2><Languages size={15} /> Languages you speak</h2><p>Jobs that need a language you haven't listed are flagged before you apply. English is assumed.</p></div><Badge tone={spoken.length ? 'good' : 'warn'}>{spoken.length ? `${spoken.length} added` : 'Not set'}</Badge></div>
    <div className="lang-chips">{spoken.map(l => <span key={l} className="chip done">{l}<button onClick={() => save(spoken.filter(s => s !== l), `${l} removed`)} aria-label={`Remove ${l}`}><X size={11} /></button></span>)}
      {COMMON_LANGUAGES.filter(l => !spoken.some(s => s.toLowerCase() === l.toLowerCase())).slice(0, 8).map(l => <button key={l} className="chip" onClick={() => add(l)}><Plus size={11} />{l}</button>)}
      <span className="chip-input"><input value={adding} onChange={e => setAdding(e.target.value)} onKeyDown={e => e.key === 'Enter' && add(adding)} placeholder="Other…" /></span></div>
  </section>
}

type ProjectForm = { name: string; description: string; skills: string; link: string; key?: string; extra?: Partial<GitHubProject> }
const blank: ProjectForm = { name: '', description: '', skills: '', link: '' }
const slug = (name: string) => name.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '').slice(0, 40) || 'project'
const REPO_LINK = /^(https?:\/\/)?(www\.)?github\.com\/[A-Za-z0-9-]+\/[A-Za-z0-9._-]+\/?$/
type StoredProject = { name?: string; description?: string; skills?: string[]; link?: string; highlights?: string[]; stars?: number; languages?: string[]; source?: string; repo?: string; updated?: string }

export function ProjectsPanel({ facts, refresh, githubUser, openImport }: { facts: Fact[]; refresh: () => Promise<void>; githubUser?: string; openImport: boolean; }) {
  const { run, busy } = useAction(refresh)
  const notify = useNotify()
  const projects = facts.filter(f => f.category === 'projects' && f.status === 'VERIFIED')
  const [form, setForm] = useState<ProjectForm | null>(null)
  const [fetching, setFetching] = useState(false)
  const [importer, setImporter] = useState(false)
  const lastFetched = useRef('')
  useEffect(() => { if (openImport) setImporter(true) }, [openImport])

  const fillFromGitHub = async (link: string) => {
    if (!REPO_LINK.test(link.trim()) || lastFetched.current === link.trim()) return
    lastFetched.current = link.trim()
    setFetching(true)
    try {
      const p = await api.githubProject(link.trim())
      setForm(f => f && { ...f, name: f.name || p.name, description: f.description || p.description, skills: f.skills || p.skills.join(', '), link: p.link, extra: p })
      notify(`Filled in from GitHub — ${p.skills.length} skills and ${p.highlights.length} highlights found`)
    } catch (e) { notify(e instanceof Error ? e.message : 'Could not read GitHub', 'bad'); lastFetched.current = '' } finally { setFetching(false) }
  }
  const save = async () => {
    if (!form || !form.name.trim()) return
    if (form.link && !/^https?:\/\//.test(form.link)) return
    const value = { ...(form.extra ?? {}), name: form.name.trim(), description: form.description.trim(), skills: form.skills.split(',').map(s => s.trim()).filter(Boolean), link: form.link.trim() || undefined }
    const ok = await run('project', () => api.saveFact({ category: 'projects', fact_key: form.key ?? slug(form.name), value, status: 'VERIFIED', source: form.extra ? 'GITHUB' : 'USER' }), 'Project saved — interview prep will use it')
    if (ok) { setForm(null); lastFetched.current = '' }
  }
  return <section className="panel" id="projects"><div className="panel-head"><div><h2><Briefcase size={15} /> Projects</h2><p>Paste a GitHub link and everything fills in by itself. Interview prep and tailored CVs pick the right ones for each job.</p></div>
    <div className="panel-head-side"><button className="button ghost" onClick={() => setImporter(true)}><Github size={14} /> Import from GitHub</button><button className="button subtle" onClick={() => setForm({ ...blank })}><Plus size={14} /> Add project</button></div></div>
    {form && <div className={`project-form ${fetching ? 'fetching' : ''}`}>
      <label className="gh-link">GitHub or project link<div className="inline-inputs"><input value={form.link} onChange={e => setForm({ ...form, link: e.target.value })} onBlur={() => fillFromGitHub(form.link)} onPaste={e => { const text = e.clipboardData.getData('text'); setTimeout(() => fillFromGitHub(text), 0) }} autoFocus placeholder="https://github.com/you/project — paste it and wait a second" />
        {REPO_LINK.test(form.link.trim()) && <button className="button subtle" disabled={fetching} onClick={() => { lastFetched.current = ''; fillFromGitHub(form.link) }}><Github size={14} /> {fetching ? 'Reading…' : 'Fill from GitHub'}</button>}</div></label>
      {fetching && <div className="gh-connecting"><span className="gh-orbit"><Github size={16} /></span><div><b>Connecting to GitHub…</b><span>Reading the description, languages, topics and README</span></div></div>}
      <div className="form-grid">
        <label>Name *<input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} placeholder="Ledger API" /></label>
        <label>Skills used (comma separated)<input value={form.skills} onChange={e => setForm({ ...form, skills: e.target.value })} placeholder="Python, PostgreSQL, Docker" /></label>
        <label className="span-2">What you built<textarea value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} placeholder="A double-entry ledger service in Python and PostgreSQL, handling 1,200 requests/sec." /></label></div>
      {form.extra?.highlights && form.extra.highlights.length > 0 && <div className="gh-highlights"><b><Sparkles size={13} /> Highlights from the README</b><ul>{form.extra.highlights.map(h => <li key={h}>{h}</li>)}</ul></div>}
      {form.link && !/^https?:\/\//.test(form.link) && !REPO_LINK.test(form.link) && <p className="warn-text small">Links must start with https://</p>}
      <div className="form-actions"><button className="button ghost" onClick={() => { setForm(null); lastFetched.current = '' }}>Cancel</button><button className="button primary" disabled={!form.name.trim() || busy === 'project' || fetching} onClick={save}>Save project</button></div></div>}
    {projects.length ? <div className="project-list">{projects.map(p => { const v = (p.value ?? {}) as StoredProject
      return <article key={p.id} className="project-card"><div><div className="project-title"><b>{v.name}</b>{v.source === 'GITHUB' && <Badge><Github size={10} /> GitHub</Badge>}{v.stars ? <span className="stars"><Star size={11} />{v.stars}</span> : null}{v.link && <a href={v.link} target="_blank" rel="noreferrer" aria-label="Open link"><ExternalLink size={12} /></a>}</div>
        <p>{v.description}</p>{v.highlights && v.highlights.length > 0 && <ul className="project-highlights">{v.highlights.slice(0, 2).map(h => <li key={h}>{h}</li>)}</ul>}
        <div className="skill-line">{(v.skills ?? []).map(s => <Badge key={s}>{s}</Badge>)}</div></div>
        <div className="fact-actions"><button className="icon-button" aria-label="Edit project" onClick={() => setForm({ key: p.fact_key, name: v.name ?? '', description: v.description ?? '', skills: (v.skills ?? []).join(', '), link: v.link ?? '', extra: v.source === 'GITHUB' ? (v as Partial<GitHubProject>) : undefined })}><Pencil /></button>
          <button className="icon-button" aria-label="Delete project" onClick={() => p.id && confirm(`Delete ${v.name}?`) && run('del', () => api.deleteFact(p.id!), 'Project deleted')}><Trash2 /></button></div></article> })}</div>
      : !form && <Empty icon={Briefcase} title="No projects yet" text="Import your GitHub repositories in one click, or add a project by hand." action={() => setImporter(true)} actionLabel="Import from GitHub" />}
    {importer && <GitHubImporter user={githubUser} existing={projects.map(p => ((p.value ?? {}) as StoredProject).repo ?? ((p.value ?? {}) as StoredProject).link ?? '')} facts={facts} refresh={refresh} onClose={() => setImporter(false)} />}
  </section>
}

function GitHubImporter({ user, existing, facts, refresh, onClose }: { user?: string; existing: string[]; facts: Fact[]; refresh: () => Promise<void>; onClose: () => void }) {
  const notify = useNotify()
  const [name, setName] = useState(user ?? '')
  const [repos, setRepos] = useState<GitHubRepo[] | null>(null)
  const [picked, setPicked] = useState<string[]>([])
  const [state, setState] = useState<'idle' | 'loading' | 'importing'>('idle')
  const [result, setResult] = useState<{ saved: number; skills: string[] } | null>(null)
  const have = (r: GitHubRepo) => existing.some(e => e && (e === r.repo || e.replace(/\/$/, '').toLowerCase() === r.link.toLowerCase()))
  const load = async (who = name) => {
    if (!who.trim()) return
    setState('loading'); setRepos(null)
    try { const list = await api.githubRepos(who.trim()); setRepos(list); setPicked(list.filter(r => !have(r)).slice(0, 4).map(r => r.link)) } catch (e) { notify(e instanceof Error ? e.message : 'Could not reach GitHub', 'bad') } finally { setState('idle') }
  }
  useEffect(() => { if (user) load(user) }, []) // eslint-disable-line react-hooks/exhaustive-deps
  const importNow = async () => {
    setState('importing')
    try {
      const r = await api.githubImport(picked)
      await refresh()
      if (r.errors.length) notify(r.errors[0].error, 'bad')
      setResult({ saved: r.saved.length, skills: r.new_skills })
    } catch (e) { notify(e instanceof Error ? e.message : 'Import failed', 'bad') } finally { setState('idle') }
  }
  const verified = (facts.find(f => f.category === 'skills' && f.fact_key === 'verified_skills' && f.status === 'VERIFIED')?.value as string[] | undefined) ?? []
  const addSkills = async (skills: string[]) => {
    await api.saveFact({ category: 'skills', fact_key: 'verified_skills', value: [...verified, ...skills], status: 'VERIFIED', source: 'USER' })
    await refresh(); notify(`${skills.length} skill${skills.length === 1 ? '' : 's'} added — every job re-scored`); onClose()
  }
  return <Modal title={result ? `Imported ${result.saved} project${result.saved === 1 ? '' : 's'}` : 'Import projects from GitHub'} subtitle={result ? 'They power interview prep and tailored CVs.' : 'Only public repositories are read. Nothing is posted to GitHub.'} onClose={onClose}
    footer={result ? <><span className="spacer" />{result.skills.length > 0 && <button className="button ghost" onClick={onClose}>Not now</button>}<button className="button primary" onClick={() => result.skills.length ? addSkills(result.skills) : onClose()}>{result.skills.length ? <><Check size={15} /> Add {result.skills.length} skill{result.skills.length === 1 ? '' : 's'}</> : 'Done'}</button></>
      : <><span className="muted small">{picked.length} selected</span><span className="spacer" /><button className="button ghost" onClick={onClose}>Cancel</button><button className="button primary" disabled={!picked.length || state === 'importing'} onClick={importNow}>{state === 'importing' ? 'Importing…' : `Import ${picked.length || ''}`}</button></>}>
    {result ? <div className="gh-result"><div className="gh-done"><Check /></div>{result.skills.length ? <><p>Your projects use skills that aren't on your profile yet. Add them only if you really know them — ApplyPilot will treat them as true.</p><div className="skill-line">{result.skills.map(s => <Badge key={s} tone="accent">{s}</Badge>)}</div></> : <p>All the skills they use are already on your profile.</p>}</div>
      : <>
        <div className="inline-inputs gh-user"><input value={name} onChange={e => setName(e.target.value)} onKeyDown={e => e.key === 'Enter' && load()} placeholder="Your GitHub username or profile link" autoFocus={!user} /><button className="button subtle" disabled={!name.trim() || state === 'loading'} onClick={() => load()}>{state === 'loading' ? 'Loading…' : 'Show repositories'}</button></div>
        {state === 'loading' && <div className="gh-connecting"><span className="gh-orbit"><Github size={16} /></span><div><b>Connecting to GitHub…</b><span>Fetching your public repositories</span></div></div>}
        {repos && (repos.length ? <div className="repo-list">{repos.map(r => { const already = have(r); const on = picked.includes(r.link)
          return <label key={r.repo} className={`repo ${on ? 'on' : ''} ${already ? 'imported' : ''}`}><input type="checkbox" checked={on} disabled={already} onChange={() => setPicked(on ? picked.filter(x => x !== r.link) : [...picked, r.link])} />
            <div><b>{r.name}</b><span>{r.description || 'No description'}</span></div><div className="repo-meta">{r.language && <Badge>{r.language}</Badge>}{r.stars > 0 && <span className="stars"><Star size={11} />{r.stars}</span>}{already && <Badge tone="good">Added</Badge>}</div></label> })}</div>
          : <p className="muted small">No public repositories found for that account.</p>)}
      </>}
  </Modal>
}
