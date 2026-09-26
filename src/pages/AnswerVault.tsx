import { useState } from 'react'
import { BookOpenCheck, Check, Plus, Trash2, X } from 'lucide-react'
import { api } from '../api'
import { Badge, Empty, PageHeading, formatDate, formatValue, useAction, type PageProps } from '../ui'

const TYPES: [string, string][] = [['EXACT', 'Exact answer'], ['COUNTRY_SPECIFIC', 'Country-specific'], ['COMPANY_SPECIFIC', 'Company-specific'], ['ROLE_SPECIFIC', 'Role-specific'], ['MANUAL_ONLY', 'Always ask me']]
const blank = { canonical_question: '', answer: '', answer_type: 'EXACT', country_code: '', company: '', approved: false }

export function AnswerVault({ data, refresh }: PageProps) {
  const { run, busy } = useAction(refresh)
  const [form, setForm] = useState<typeof blank | null>(null)
  const save = async () => {
    if (!form) return
    const saved = await run('save', () => api.saveAnswer(form), r => r.status === 'VERIFIED' ? 'Answer saved and approved' : 'Answer saved — approve it before automation can use it')
    if (saved) setForm(null)
  }
  return <>
    <PageHeading eyebrow="Answer Vault" title="Reusable answers" text="Answers to recurring questions, with explicit scope. Automation uses only approved answers whose question matches exactly.">
      <button className="button primary" onClick={() => setForm({ ...blank })}><Plus size={16} /> New answer</button>
    </PageHeading>
    {form && <section className="panel form-panel"><div className="panel-head"><div><h2>New answer</h2><p>Write the question exactly as forms ask it.</p></div><button className="icon-button" onClick={() => setForm(null)} aria-label="Close"><X /></button></div>
      <div className="form-grid">
        <label className="span-2">Question *<input value={form.canonical_question} onChange={e => setForm({ ...form, canonical_question: e.target.value })} placeholder="Are you at least 18 years old?" autoFocus /></label>
        <label className="span-2">Answer<textarea value={form.answer} onChange={e => setForm({ ...form, answer: e.target.value })} placeholder="Yes" /></label>
        <label>Scope<select value={form.answer_type} onChange={e => setForm({ ...form, answer_type: e.target.value })}>{TYPES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>
        {form.answer_type === 'COUNTRY_SPECIFIC' && <label>Country<input value={form.country_code} onChange={e => setForm({ ...form, country_code: e.target.value })} placeholder="United Kingdom" /></label>}
        {form.answer_type === 'COMPANY_SPECIFIC' && <label>Company<input value={form.company} onChange={e => setForm({ ...form, company: e.target.value })} /></label>}
        <label className="checkbox span-2"><input type="checkbox" checked={form.approved} onChange={e => setForm({ ...form, approved: e.target.checked })} /> I confirm this answer is accurate and may be used automatically</label>
      </div>
      <div className="form-actions"><button className="button ghost" onClick={() => setForm(null)}>Cancel</button><button className="button primary" disabled={!form.canonical_question.trim() || busy === 'save'} onClick={save}>Save answer</button></div>
    </section>}
    <section className="panel">{data.answers.length ? <div className="answer-list">{data.answers.map(a => <article key={a.id} className="answer-card">
      <div><b>{a.canonical_question}</b><p>{formatValue(a.answer)}</p><small>{TYPES.find(([v]) => v === a.answer_type)?.[1] ?? a.answer_type}{a.country_code ? ` · ${a.country_code}` : ''}{a.company ? ` · ${a.company}` : ''} · updated {formatDate(a.updated_at)}</small></div>
      <div className="fact-actions"><Badge tone={a.status === 'VERIFIED' ? 'good' : a.status === 'EXPIRED' ? 'bad' : 'warn'}>{a.status}</Badge>
        {a.status !== 'VERIFIED' && <button className="button subtle" onClick={() => run(`approve-${a.id}`, () => api.approveAnswer(a.id), 'Answer approved')}><Check size={14} /> Approve</button>}
        <button className="icon-button" aria-label="Delete answer" onClick={() => confirm('Delete this answer?') && run(`del-${a.id}`, () => api.deleteAnswer(a.id), 'Answer deleted')}><Trash2 /></button></div>
    </article>)}</div> : <Empty icon={BookOpenCheck} title="No saved answers" text="Save answers to questions you see again and again. Sensitive questions can stay “Always ask me”." action={() => setForm({ ...blank })} actionLabel="Add an answer" />}</section>
  </>
}
