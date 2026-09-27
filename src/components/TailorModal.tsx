import { useEffect, useState } from 'react'
import { AlertTriangle, Check, FileText, Wand2 } from 'lucide-react'
import { api } from '../api'
import type { TailorResult } from '../types'
import { Skeleton } from '../motion'
import { useNotify } from '../ui'
import { Modal } from './Modal'
import { WordDiff } from './WordDiff'

/** Review a tailored CV: colour-coded changes, invention flags, optional edits, then approve → PDF. */
export function TailorModal({ jobId, draftId, useAI, onClose, onDone }: { jobId?: string; draftId?: string; useAI?: boolean; onClose: () => void; onDone: () => Promise<void> }) {
  const notify = useNotify()
  const [result, setResult] = useState<TailorResult | null>(null)
  const [text, setText] = useState('')
  const [mode, setMode] = useState<'diff' | 'edit'>('diff')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  useEffect(() => {
    const load = draftId ? api.tailoredDiff(draftId) : api.tailor(jobId!, Boolean(useAI))
    load.then(r => { setResult(r); setText(r.content) }).catch(e => setError(e instanceof Error ? e.message : 'Tailoring failed'))
  }, [jobId, draftId, useAI])
  const approve = async () => {
    if (!result) return
    setBusy(true)
    try {
      const saved = await api.saveDraft(result.id, text, true)
      notify(saved.cv ? `Created ${saved.cv.name} — attached to this application` : 'Tailored CV approved')
      await onDone(); onClose()
    } catch (e) { notify(e instanceof Error ? e.message : 'Could not approve', 'bad') } finally { setBusy(false) }
  }
  const flags = result?.flags
  const flagged = Boolean(flags && (flags.skills.length || flags.numbers.length))
  return <Modal wide title="Tailored CV" subtitle={result ? `${result.model === 'ApplyPilot' ? 'Skills reordered for this role — wording untouched' : `Rewritten by ${result.model} from your own CV`}` : 'Preparing…'} onClose={onClose}
    footer={result && <><span className="muted small">Approving creates a clean one-page PDF in your CV Library and attaches it to this application.</span><span className="spacer" />
      <button className="button ghost" onClick={() => setMode(mode === 'diff' ? 'edit' : 'diff')}>{mode === 'diff' ? 'Edit text' : 'Show changes'}</button>
      <button className="button ghost" disabled={busy} onClick={async () => { await api.saveDraft(result.id, text, false); notify('Saved as a draft in your Inbox'); onClose() }}>Save for later</button>
      <button className="button primary" disabled={busy} onClick={approve}>{busy ? <><Wand2 size={15} className="spin" /> Creating PDF…</> : <><Check size={15} /> Approve & create PDF</>}</button></>}>
    {error ? <div className="error-banner"><AlertTriangle /><span>{error}</span></div> : !result ? <><Skeleton lines={3} /><Skeleton lines={8} /></> : <>
      {flagged && <div className="attention banner"><AlertTriangle /><div><b>Check these before approving</b><p>They aren't in your original CV or your profile: {[...flags!.skills, ...flags!.numbers].join(', ')}. ApplyPilot won't approve a CV that claims them.</p></div></div>}
      {mode === 'diff' ? <WordDiff before={result.original} after={text} /> : <textarea className="cv-editor" value={text} onChange={e => setText(e.target.value)} />}
      <p className="muted small tailor-note"><FileText size={13} /> Green lines are the tailored version; struck-through lines are what they replace. Nothing about you is ever invented.</p>
    </>}
  </Modal>
}
