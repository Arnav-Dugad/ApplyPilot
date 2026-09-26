import { useState } from 'react'
import { Check, FileText, Inbox as InboxIcon, KeyRound, Lightbulb, PenLine, Sparkles, Trash2, Wand2, X } from 'lucide-react'
import { api } from '../api'
import type { Draft, InboxQuestion, Suggestion } from '../types'
import { Badge, Empty, PageHeading, formatValue, useAction, useNotify, type PageProps } from '../ui'

type Tab = 'questions' | 'suggestions' | 'drafts'

export function Inbox({ data, refresh, go, openJob }: PageProps) {
  const box = data.inbox
  const [tab, setTab] = useState<Tab>(box.questions.length ? 'questions' : box.suggestions.length ? 'suggestions' : box.drafts.length ? 'drafts' : 'questions')
  const aiOn = (data.settings.ollama as { provider?: string } | undefined)?.provider === 'OLLAMA'
  const total = box.questions.length + box.suggestions.length + box.drafts.length
  const tabs: [Tab, string, number][] = [['questions', 'Questions', box.questions.length], ['suggestions', 'Profile suggestions', box.suggestions.length], ['drafts', 'Drafts to review', box.drafts.length]]
  return <>
    <PageHeading eyebrow="Inbox" title={total ? 'A few answers unlock everything' : 'Inbox zero'} text="Answer once — ApplyPilot reuses it on every matching question, in every queued application." />
    <div className="tabs">{tabs.map(([key, label, count]) => <button key={key} className={tab === key ? 'active' : ''} onClick={() => setTab(key)}>{label}{count > 0 && <em>{count}</em>}</button>)}</div>
    {tab === 'questions' && (box.questions.length ? <div className="inbox-list">{box.questions.map(q => <QuestionCard key={q.key} q={q} refresh={refresh} go={go} openJob={openJob} aiOn={aiOn} />)}</div>
      : <section className="panel"><Empty icon={InboxIcon} title="No open questions" text="When Autopilot or a form check finds a question ApplyPilot can't answer from verified facts, it lands here." /></section>)}
    {tab === 'suggestions' && (box.suggestions.length ? <div className="inbox-list">{box.suggestions.map(s => <SuggestionCard key={s.id} s={s} refresh={refresh} />)}</div>
      : <section className="panel"><Empty icon={Lightbulb} title="No suggestions" text="Upload a CV and ApplyPilot will read it and suggest profile facts for you to confirm." action={() => go('CV Library')} actionLabel="Open CV Library" /></section>)}
    {tab === 'drafts' && (box.drafts.length ? <div className="inbox-list">{box.drafts.map(d => <DraftCard key={d.id} draft={d} refresh={refresh} />)}</div>
      : <section className="panel"><Empty icon={PenLine} title="No drafts waiting" text={aiOn ? 'Cover letters and answers drafted by local AI wait here for your edits and approval.' : 'Turn on local AI in Settings to draft cover letters and answers.'} /></section>)}
  </>
}

function QuestionCard({ q, refresh, go, openJob, aiOn }: { q: InboxQuestion; refresh: () => Promise<void>; go: PageProps['go']; openJob: (id: string) => void; aiOn: boolean }) {
  const { run, busy } = useAction(refresh)
  const notify = useNotify()
  const [value, setValue] = useState('')
  const company = q.applications[0]?.company ?? undefined
  const namesCompany = Boolean(company && q.question.toLowerCase().includes(company.toLowerCase()))
  const [scope, setScope] = useState<'EXACT' | 'COMPANY_SPECIFIC'>(namesCompany ? 'COMPANY_SPECIFIC' : 'EXACT')
  const [leaving, setLeaving] = useState(false)
  const scopePicker = q.kind === 'ANSWER' && company ? <select className="scope" value={scope} onChange={e => setScope(e.target.value as typeof scope)}><option value="EXACT">Use for every company</option><option value="COMPANY_SPECIFIC">Only for {company}</option></select> : null
  const submit = async (answer: unknown) => {
    const result = await run('answer', () => api.answerQuestion({ question: q.question, classification: q.classification, value: answer, country: q.country, scope, company }))
    if (result) { setLeaving(true); notify(`Saved · ${result.applications_updated} application${result.applications_updated === 1 ? '' : 's'} updated`) }
  }
  const draft = async () => {
    const d = await run('draft', () => api.draftAnswer(q.question, q.applications[0]?.job_id))
    if (d) setValue(d.content)
  }
  const apps = q.applications.map(a => a.company).filter(Boolean)
  return <article className={`inbox-card ${leaving ? 'leaving' : ''}`}>
    <header><div><Badge tone={q.required ? 'warn' : 'neutral'}>{q.required ? 'Required' : 'Optional'}</Badge>{q.country && <Badge tone="accent">{q.country} only</Badge>}<small>{q.classification.replaceAll('_', ' ').toLowerCase()}</small></div>
      <span className="app-chips">{q.applications.slice(0, 3).map(a => <button key={a.id} onClick={() => openJob(a.job_id)}>{a.company}</button>)}{q.applications.length > 3 && <em>+{q.applications.length - 3}</em>}</span></header>
    <h3>{q.question}</h3>
    {q.reason && !/doesn't have a verified answer|MANUAL_ONLY/.test(q.reason) && <p className="pause-reason">Paused: {q.reason}</p>}
    <p className="muted small">{q.kind === 'COUNTRY_FACT' ? `Saved for ${q.country} only — never reused for other countries.` : q.kind === 'FACT' ? 'Saved to your verified profile.' : `Saved to your Answer Vault and reused on similar questions${apps.length > 1 ? ` — unlocks ${apps.length} applications` : ''}.`}</p>
    {q.kind === 'RESUME' ? <button className="button primary" onClick={() => go('CV Library')}><FileText size={15} /> Approve a CV</button>
      : q.kind === 'CREDENTIAL' ? <div className="attention"><KeyRound /><div><b>Enter this on the site yourself</b><p>Passwords and access codes are never stored or auto-filled.</p></div></div>
      : q.kind === 'COVER_LETTER' ? <button className="button primary" onClick={() => openJob(q.applications[0].job_id)}><PenLine size={15} /> Write or draft a cover letter</button>
      : q.kind === 'COUNTRY_FACT' || (q.options.length > 0 && q.options.length <= 6) ? <div className="answer-options">{(q.kind === 'COUNTRY_FACT' ? ['Yes', 'No'] : q.options).map(o => <button key={o} className="button ghost" disabled={busy === 'answer'} onClick={() => submit(o)}>{o}</button>)}{scopePicker && <span className="spacer" />}{scopePicker}</div>
      : <div className="answer-form">
        {q.options.length > 6 ? <select value={value} onChange={e => setValue(e.target.value)}><option value="">Choose…</option>{q.options.map(o => <option key={o}>{o}</option>)}</select>
          : q.kind === 'ANSWER' && !/^(yes|no)\b/i.test(q.question) ? <textarea value={value} onChange={e => setValue(e.target.value)} placeholder="Your answer, exactly as you want it submitted" />
          : <input value={value} onChange={e => setValue(e.target.value)} onKeyDown={e => e.key === 'Enter' && value.trim() && submit(value.trim())} placeholder="Your answer" />}
        <div className="answer-actions">
          {scopePicker}
          {q.kind === 'ANSWER' && aiOn && <button className="button ghost" disabled={busy === 'draft'} onClick={draft}><Wand2 size={15} className={busy === 'draft' ? 'spin' : ''} /> {busy === 'draft' ? 'Drafting…' : 'Draft with AI'}</button>}
          <span className="spacer" />
          <button className="button primary" disabled={!value.trim() || busy === 'answer'} onClick={() => submit(value.trim())}><Check size={15} /> Save answer</button>
        </div>
      </div>}
  </article>
}

function SuggestionCard({ s, refresh }: { s: Suggestion; refresh: () => Promise<void> }) {
  const { run, busy } = useAction(refresh)
  const [edit, setEdit] = useState<string | null>(null)
  const [leaving, setLeaving] = useState(false)
  const isList = Array.isArray(s.value)
  const accept = async () => {
    const value = edit === null ? undefined : isList ? edit.split(',').map(x => x.trim()).filter(Boolean) : edit
    if (await run('accept', () => api.acceptSuggestion(s.id, value), 'Added to your verified profile')) setLeaving(true)
  }
  return <article className={`inbox-card suggestion ${leaving ? 'leaving' : ''}`}>
    <header><div><Badge tone="accent"><Sparkles size={11} /> {s.category}</Badge><small>{s.source}</small></div><span className="confidence" title="How sure the reader is"><i style={{ width: `${s.confidence * 100}%` }} />{Math.round(s.confidence * 100)}%</span></header>
    <h3>{s.fact_key.replaceAll('_', ' ')}</h3>
    {edit === null ? <p className="suggested-value">{isList ? <span className="skill-line">{(s.value as string[]).map(v => <Badge key={v}>{v}</Badge>)}</span> : formatValue(s.value)}</p>
      : <input className="suggest-edit" value={edit} onChange={e => setEdit(e.target.value)} autoFocus />}
    {s.evidence && <blockquote>“{s.evidence}”</blockquote>}
    <div className="answer-actions">
      <button className="button ghost" onClick={() => run('dismiss', () => api.dismissSuggestion(s.id))}><X size={15} /> Dismiss</button>
      {edit === null && <button className="button ghost" onClick={() => setEdit(isList ? (s.value as string[]).join(', ') : formatValue(s.value))}><PenLine size={15} /> Edit</button>}
      <span className="spacer" />
      <button className="button primary" disabled={busy === 'accept'} onClick={accept}><Check size={15} /> It’s correct — verify</button>
    </div>
  </article>
}

function DraftCard({ draft, refresh }: { draft: Draft; refresh: () => Promise<void> }) {
  const { run, busy } = useAction(refresh)
  const [text, setText] = useState(draft.content)
  const placeholders = text.match(/\[[^\]]{3,}\]/g) ?? []
  return <article className="inbox-card draft">
    <header><div><Badge tone="accent"><Sparkles size={11} /> {draft.kind === 'COVER_LETTER' ? 'Cover letter' : 'Answer'}</Badge><small>{draft.company ? `${draft.role} · ${draft.company}` : 'General'}{draft.model ? ` · ${draft.model}` : ''}</small></div>
      <button className="icon-button" aria-label="Delete draft" onClick={() => run('delete', () => api.deleteDraft(draft.id), 'Draft deleted')}><Trash2 /></button></header>
    {draft.question && <h3>{draft.question}</h3>}
    <textarea className="draft-text" value={text} onChange={e => setText(e.target.value)} />
    {placeholders.length > 0 && <p className="warn-text small">Fill in {placeholders.length} placeholder{placeholders.length > 1 ? 's' : ''}: {placeholders.slice(0, 3).join(' · ')}</p>}
    <div className="answer-actions"><span className="muted small">AI drafts use only your verified facts. Approving makes it usable in forms.</span><span className="spacer" />
      <button className="button ghost" disabled={busy === 'save'} onClick={() => run('save', () => api.saveDraft(draft.id, text, false), 'Draft saved')}>Save</button>
      <button className="button primary" disabled={placeholders.length > 0 || busy === 'approve'} onClick={() => run('approve', () => api.saveDraft(draft.id, text, true), 'Approved — it will be used automatically')}><Check size={15} /> Approve</button></div>
  </article>
}
