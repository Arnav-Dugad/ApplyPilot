import { useEffect, useMemo, useRef, useState } from 'react'
import { prefersReducedMotion } from '../motion'

const COLORS = ['#7c9cff', '#4fd1a5', '#ffd66b', '#f0a3ff', '#ff8a8a', '#8ab8ff', '#ffffff']

/** A one-shot confetti burst from a point on screen. Nothing renders when reduced motion is preferred. */
export function Confetti({ x, y, pieces = 90 }: { x: number; y: number; pieces?: number }) {
  const [alive, setAlive] = useState(!prefersReducedMotion())
  useEffect(() => { const id = setTimeout(() => setAlive(false), 2600); return () => clearTimeout(id) }, [])
  const bits = useMemo(() => Array.from({ length: pieces }, (_, i) => {
    const angle = (Math.PI * 2 * i) / pieces + (Math.random() - 0.5) * 0.6
    const power = 90 + Math.random() * 190
    return {
      dx: Math.cos(angle) * power, dy: Math.sin(angle) * power * 0.75 - 70, rot: Math.random() * 720 - 360,
      delay: Math.random() * 90, color: COLORS[i % COLORS.length], w: 5 + Math.random() * 5, h: 8 + Math.random() * 8, round: i % 5 === 0,
    }
  }), [pieces])
  if (!alive) return null
  return <div className="confetti" style={{ left: x, top: y }} aria-hidden>{bits.map((b, i) => <i key={i} style={{
    ['--dx' as string]: `${b.dx}px`, ['--dy' as string]: `${b.dy}px`, ['--rot' as string]: `${b.rot}deg`, animationDelay: `${b.delay}ms`,
    background: b.color, width: b.round ? b.w : b.w, height: b.round ? b.w : b.h, borderRadius: b.round ? '50%' : '2px',
  }} />)}</div>
}

/** Shown once after an automatic update: the progress bar morphs into a checkmark, then confetti. */
export function UpdateSuccess({ version, previous, onNotes, onDismiss }: { version: string; previous?: string | null; onNotes?: () => void; onDismiss: () => void }) {
  const mark = useRef<HTMLDivElement>(null)
  const [burst, setBurst] = useState<{ x: number; y: number } | null>(null)
  useEffect(() => {
    const id = setTimeout(() => { const r = mark.current?.getBoundingClientRect(); if (r) setBurst({ x: r.left + r.width / 2, y: r.top + r.height / 2 }) }, 1150)
    return () => clearTimeout(id)
  }, [])
  return <div className="update-banner success" role="status" aria-live="polite">
    <div className="morph-mark" ref={mark}><svg viewBox="0 0 36 36" aria-hidden><circle cx="18" cy="18" r="16" /><path d="M11 18.5l4.6 4.6L25.5 13" /></svg></div>
    <div className="update-body"><b>Updated to ApplyPilot {version}</b><span>{previous ? `You were on ${previous}. ` : ''}Everything you saved is exactly where you left it.</span></div>
    <div className="update-actions">{onNotes && <button className="button primary" onClick={onNotes}>See what’s new</button>}<button className={`button ${onNotes ? 'ghost' : 'primary'}`} onClick={onDismiss}>Got it</button></div>
    {burst && <Confetti x={burst.x} y={burst.y} />}
  </div>
}
