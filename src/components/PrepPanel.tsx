import { useEffect, useState } from 'react'
import { BookOpen, Briefcase, Check, Copy, ExternalLink, HelpCircle, MessageCircleQuestion, Users } from 'lucide-react'
import { api } from '../api'
import type { PrepPack } from '../types'
import { Skeleton } from '../motion'
import { Badge, useNotify } from '../ui'

/** Interview prep: likely questions (tick them off as you practise), your matching projects, notes, and people. */
export function PrepPanel({ jobId }: { jobId: string }) {
  const notify = useNotify()
  const [pack, setPack] = useState<PrepPack | null>(null)
  const [done, setDone] = useState<Record<string, boolean>>(() => { try { return JSON.parse(localStorage.getItem(`prep:${jobId}`) || '{}') } catch { return {} } })
  useEffect(() => { api.prep(jobId).then(setPack).catch(() => setPack(null)) }, [jobId])
  const toggle = (q: string) => { const next = { ...done, [q]: !done[q] }; setDone(next); try { localStorage.setItem(`prep:${jobId}`, JSON.stringify(next)) } catch { /* optional */ } }
  if (!pack) return <Skeleton lines={8} />
  const all = [...pack.technical.map(t => t.question), ...pack.role_specific, ...pack.company_questions, ...pack.behavioural]
  const practised = all.filter(q => done[q]).length
  const copy = async () => {
    const text = [`Interview prep — ${pack.role} at ${pack.company}`, '', 'Technical', ...pack.technical.map(t => `- [${t.skill}] ${t.question}`), '', 'Role', ...pack.role_specific.map(q => `- ${q}`), '', 'Company', ...pack.company_questions.map(q => `- ${q}`), '', 'Behavioural', ...pack.behavioural.map(q => `- ${q}`), '', 'Questions to ask', ...pack.questions_to_ask.map(q => `- ${q}`)].join('\n')
    await navigator.clipboard.writeText(text); notify('Prep pack copied')
  }
  const Q = ({ q, tag }: { q: string; tag?: string }) => <li className={done[q] ? 'done' : ''}><button onClick={() => toggle(q)} aria-label="Mark practised">{done[q] ? <Check size={13} /> : null}</button><span>{tag && <Badge>{tag}</Badge>} {q}</span></li>
  return <div className="prep">
    <div className="prep-progress"><div><b>{practised} of {all.length} practised</b><span>Tick questions off as you rehearse them out loud.</span></div><div className="meter"><i style={{ width: `${(practised / all.length) * 100}%` }} /></div><button className="button ghost" onClick={copy}><Copy size={14} /> Copy</button></div>
    {pack.projects.length > 0 ? <section><h4><Briefcase size={14} /> Your projects to talk about</h4>{pack.projects.map(p => <div key={p.name} className="prep-project"><b>{p.name}</b>{p.link && <a href={p.link} target="_blank" rel="noreferrer"><ExternalLink size={12} /></a>}<span>{p.description}</span><div className="skill-line">{p.overlap.map(s => <Badge key={s} tone="good">{s}</Badge>)}</div></div>)}
      {pack.unmatched_skills.length > 0 && <small className="muted">No project yet showing: {pack.unmatched_skills.join(', ')}</small>}</section>
      : <section><h4><Briefcase size={14} /> Your projects</h4><p className="muted small">Add projects in Profile → Projects and ApplyPilot will pick the ones that match each job.</p></section>}
    {pack.technical.length > 0 && <section><h4><BookOpen size={14} /> Technical</h4><ul className="q-list">{pack.technical.map(t => <Q key={t.question} q={t.question} tag={t.skill} />)}</ul></section>}
    {pack.role_specific.length > 0 && <section><h4><HelpCircle size={14} /> This kind of role</h4><ul className="q-list">{pack.role_specific.map(q => <Q key={q} q={q} />)}</ul></section>}
    <section><h4><Briefcase size={14} /> About {pack.company}</h4><ul className="q-list">{pack.company_questions.map(q => <Q key={q} q={q} />)}</ul>
      {pack.company_notes.length > 0 && <div className="prep-notes">{pack.company_notes.map(n => <p key={n}>{n}</p>)}</div>}
      {pack.your_notes && <div className="prep-notes mine"><b>Your notes</b><p>{pack.your_notes}</p></div>}</section>
    <section><h4><MessageCircleQuestion size={14} /> Behavioural</h4><ul className="q-list">{pack.behavioural.map(q => <Q key={q} q={q} />)}</ul></section>
    <section><h4><HelpCircle size={14} /> Questions to ask them</h4><ul className="plain">{pack.questions_to_ask.map(q => <li key={q}>{q}</li>)}</ul></section>
    {pack.people.length > 0 && <section><h4><Users size={14} /> People who could share tips</h4><div className="people">{pack.people.map(p => <div key={p.id} className="person"><div className="avatar">{(p.first_name[0] ?? '') + (p.last_name[0] ?? '')}</div><div><b>{p.first_name} {p.last_name}</b><span>{p.position}</span></div>{p.url && <a className="icon-button" href={p.url} target="_blank" rel="noreferrer" aria-label="LinkedIn"><ExternalLink /></a>}</div>)}</div></section>}
  </div>
}
