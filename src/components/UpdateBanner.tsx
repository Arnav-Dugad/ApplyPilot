import { useEffect, useState } from 'react'
import { Download, RefreshCw, ShieldCheck, Sparkles, X } from 'lucide-react'
import { api } from '../api'
import type { UpdateState } from '../types'
import { useNotify } from '../ui'

export const formatBytes = (bytes = 0) => bytes >= 1024 * 1024 ? `${(bytes / 1024 / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`
export const formatEta = (seconds?: number | null) => seconds == null ? '' : seconds < 60 ? `${Math.max(1, Math.round(seconds))}s left` : `${Math.round(seconds / 60)} min left`

function useSecondsUntil(iso?: string | null) {
  const [now, setNow] = useState(Date.now())
  useEffect(() => {
    if (!iso) return
    const id = setInterval(() => setNow(Date.now()), 250)
    return () => clearInterval(id)
  }, [iso])
  return iso ? Math.max(0, Math.ceil((new Date(iso).getTime() - now) / 1000)) : null
}

/** Live update progress: available → downloading (bytes, speed, ETA) → verifying → countdown → installing. */
export function UpdateBanner({ update, refresh, openNotes }: { update?: UpdateState; refresh: () => Promise<void>; openNotes: () => void }) {
  const notify = useNotify()
  const [hidden, setHidden] = useState<string | null>(null)
  const countdown = useSecondsUntil(update?.status === 'ready' && !update.postponed ? update.install_at : null)
  if (!update || !['available', 'downloading', 'verifying', 'ready', 'installing'].includes(update.status)) return null
  if (hidden === `${update.status}-${update.latest}` && update.status !== 'downloading' && update.status !== 'installing') return null
  const pct = update.total ? Math.min(100, Math.floor(((update.downloaded ?? 0) / update.total) * 100)) : 0
  const act = async (fn: () => Promise<unknown>, success?: string) => {
    try { await fn(); await refresh(); if (success) notify(success) } catch (e) { notify(e instanceof Error ? e.message : 'Update failed', 'bad') }
  }
  const installable = update.mode === 'installer'

  return <div className={`update-banner ${update.status}`} role="status" aria-live="polite">
    <div className="update-icon">{update.status === 'verifying' ? <ShieldCheck /> : update.status === 'installing' ? <RefreshCw className="spin" /> : update.status === 'ready' ? <Sparkles /> : <Download />}</div>
    <div className="update-body">
      {update.status === 'available' && <><b>ApplyPilot {update.latest} is available</b><span>{installable ? 'Download it now — it installs in the background.' : update.mode === 'portable' ? 'You’re using the portable version: download the new zip from GitHub.' : 'Running from source: pull the latest code to update.'}</span></>}
      {update.status === 'downloading' && <><b>Updating to ApplyPilot {update.latest} · {pct}%</b><span>{formatBytes(update.downloaded)} of {formatBytes(update.total)}{update.speed ? ` · ${formatBytes(update.speed)}/s` : ''}{update.eta != null ? ` · ${formatEta(update.eta)}` : ''}</span></>}
      {update.status === 'verifying' && <><b>Verifying ApplyPilot {update.latest}</b><span>Checking the download matches the release GitHub published…</span></>}
      {update.status === 'ready' && <><b>ApplyPilot {update.latest} is ready</b><span>{update.postponed ? 'It will install when you quit ApplyPilot.' : countdown != null ? `Installing and restarting in ${countdown}s — your data stays exactly as it is.` : 'Verified and ready to install.'}</span></>}
      {update.status === 'installing' && <><b>Installing ApplyPilot {update.latest}</b><span>ApplyPilot will close and reopen in a few seconds.</span></>}
      {(update.status === 'downloading' || update.status === 'verifying' || update.status === 'installing') && <div className="update-progress"><i style={{ width: `${update.status === 'downloading' ? pct : 100}%` }} className={update.status !== 'downloading' ? 'indeterminate' : ''} /></div>}
    </div>
    <div className="update-actions">
      {update.notes && <button className="button ghost" onClick={openNotes}>What’s new</button>}
      {update.status === 'available' && (installable ? <button className="button primary" onClick={() => act(api.downloadUpdate)}><Download size={15} /> Update</button>
        : <a className="button primary" href={update.release_url || update.releases_page} target="_blank" rel="noreferrer"><Download size={15} /> Download</a>)}
      {update.status === 'ready' && installable && <button className="button primary" onClick={() => act(api.installUpdate)}><RefreshCw size={15} /> Restart now</button>}
      {update.status === 'ready' && !update.postponed && <button className="button ghost" onClick={() => act(api.postponeUpdate, 'The update will install when you quit ApplyPilot')}>Later</button>}
      {(update.status === 'available' || update.status === 'ready') && <button className="icon-button" aria-label="Hide" onClick={() => setHidden(`${update.status}-${update.latest}`)}><X /></button>}
    </div>
  </div>
}

/** Release notes rendered from GitHub's markdown: headings, bullets, bold, and links. */
export function ReleaseNotes({ notes }: { notes: string }) {
  const inline = (text: string) => text.split(/(\*\*[^*]+\*\*|\[[^\]]+\]\([^)]+\))/g).map((part, i) => {
    const bold = part.match(/^\*\*(.+)\*\*$/)
    if (bold) return <b key={i}>{bold[1]}</b>
    const link = part.match(/^\[([^\]]+)\]\((https:\/\/[^)]+)\)$/)
    if (link) return <a key={i} href={link[2]} target="_blank" rel="noreferrer">{link[1]}</a>
    return part.replace(/`/g, '')
  })
  return <div className="release-notes">{notes.split('\n').map((line, i) => {
    const t = line.trim()
    if (!t || t.startsWith('|')) return null
    if (t.startsWith('### ')) return <h4 key={i}>{inline(t.slice(4))}</h4>
    if (t.startsWith('## ')) return <h3 key={i}>{inline(t.slice(3))}</h3>
    if (/^[-*] /.test(t)) return <li key={i}>{inline(t.slice(2))}</li>
    return <p key={i}>{inline(t)}</p>
  })}</div>
}
