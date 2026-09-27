import { useRef } from 'react'
import { FileText, Upload } from 'lucide-react'
import { api, readFileBase64 } from '../api'
import { Badge, Empty, PageHeading, formatDate, useAction, type PageProps } from '../ui'

export function CVLibrary({ data, refresh, go }: PageProps) {
  const { run, busy } = useAction(refresh)
  const input = useRef<HTMLInputElement>(null)
  const upload = async (file?: File) => {
    if (!file) return
    const result = await run('upload', async () => api.importCV(file.name, await readFileBase64(file)), r => r.suggestions ? `${file.name} read — ${r.suggestions} profile suggestions waiting in your Inbox` : `${file.name} imported — review and approve it`)
    if (result?.suggestions) go('Inbox')
    if (input.current) input.current.value = ''
  }
  return <>
    <PageHeading eyebrow="My CVs" title="Your CVs" text="Upload a PDF and ApplyPilot suggests details for your profile. Only a CV you approve is attached to applications.">
      <button className="button primary" disabled={busy === 'upload'} onClick={() => input.current?.click()}><Upload size={16} /> {busy === 'upload' ? 'Importing…' : 'Upload PDF'}</button>
      <input ref={input} type="file" accept="application/pdf" hidden onChange={e => upload(e.target.files?.[0])} />
    </PageHeading>
    <section className="panel">{data.cvs.length ? <div className="cv-list">{data.cvs.map(cv => <article key={cv.id} className="cv-card">
      <div className="cv-icon"><FileText /></div>
      <div className="cv-body">
        <div className="cv-title"><b>{cv.name}</b><Badge tone={cv.approved ? 'good' : 'warn'}>{cv.approved ? 'Approved' : 'Needs review'}</Badge></div>
        <span>{cv.variant} · v{cv.version} · added {formatDate(cv.created_at)} · sha256 {cv.sha256.slice(0, 10)}…</span>
        {cv.extracted_profile?.extraction_error && <small className="warn-text">{cv.extracted_profile.extraction_error}</small>}
        {!!cv.extracted_profile?.skill_candidates?.length && <div className="skill-line"><small>Skills it mentions (not added until you confirm):</small>{cv.extracted_profile.skill_candidates.map(s => <Badge key={s}>{s}</Badge>)}</div>}
        {!!cv.extracted_profile?.email_candidates?.length && <small>Emails found: {cv.extracted_profile.email_candidates.join(', ')}</small>}
      </div>
      <button className={`button ${cv.approved ? 'ghost' : 'primary'}`} disabled={busy === cv.id} onClick={() => run(cv.id, () => api.approveCV(cv.id, !cv.approved), cv.approved ? 'Approval removed' : 'CV approved — your applications will use it')}>{cv.approved ? 'Revoke approval' : 'Approve'}</button>
    </article>)}</div> : <Empty icon={FileText} title="No CVs yet" text="Upload a PDF. Anything ApplyPilot reads from it stays a suggestion until you confirm it." action={() => input.current?.click()} actionLabel="Upload PDF" />}</section>
  </>
}
