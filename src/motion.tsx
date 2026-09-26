import { useEffect, useRef, useState } from 'react'

export const prefersReducedMotion = () => typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches

/** Eases from the previous value to the new one. */
export function useCountUp(target: number, duration = 700) {
  const [value, setValue] = useState(target)
  const from = useRef(target)
  useEffect(() => {
    if (prefersReducedMotion() || from.current === target) { from.current = target; setValue(target); return }
    const start = performance.now(), origin = from.current
    let frame = 0
    const tick = (t: number) => {
      const p = Math.min(1, (t - start) / duration)
      const eased = 1 - Math.pow(1 - p, 3)
      setValue(origin + (target - origin) * eased)
      if (p < 1) frame = requestAnimationFrame(tick)
      else from.current = target
    }
    frame = requestAnimationFrame(tick)
    return () => { cancelAnimationFrame(frame); from.current = target }
  }, [target, duration])
  return value
}

export function AnimatedNumber({ value, suffix = '' }: { value: number; suffix?: string }) {
  const shown = useCountUp(value)
  return <>{Math.round(shown)}{suffix}</>
}

export const scoreTone = (score: number) => score >= 80 ? 'excellent' : score >= 65 ? 'good' : score >= 50 ? 'fair' : 'low'

/** Circular gauge that sweeps to the score on mount. */
export function ScoreRing({ score, size = 44, stroke = 4, label = true }: { score: number | null | undefined; size?: number; stroke?: number; label?: boolean }) {
  const [drawn, setDrawn] = useState(prefersReducedMotion() ? score ?? 0 : 0)
  useEffect(() => { const id = requestAnimationFrame(() => setDrawn(score ?? 0)); return () => cancelAnimationFrame(id) }, [score])
  const radius = (size - stroke) / 2
  const circumference = 2 * Math.PI * radius
  if (score === null || score === undefined) return <div className="score-ring empty" style={{ width: size, height: size }} title="Not scored yet"><span>—</span></div>
  return <div className={`score-ring ${scoreTone(score)}`} style={{ width: size, height: size }} title={`Match score ${score}/100`}>
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden="true">
      <circle cx={size / 2} cy={size / 2} r={radius} className="track" strokeWidth={stroke} />
      <circle cx={size / 2} cy={size / 2} r={radius} className="arc" strokeWidth={stroke} strokeDasharray={circumference} strokeDashoffset={circumference * (1 - drawn / 100)} transform={`rotate(-90 ${size / 2} ${size / 2})`} />
    </svg>
    {label && <span style={{ fontSize: Math.max(10, size * 0.3) }}><AnimatedNumber value={score} /></span>}
  </div>
}

export function Skeleton({ lines = 3 }: { lines?: number }) {
  return <div className="skeleton">{Array.from({ length: lines }, (_, i) => <i key={i} style={{ width: `${90 - i * 17}%` }} />)}</div>
}

/** Glowing orb: calm when idle, orbiting rings while Autopilot works. */
export function AutopilotOrb({ state, size = 120 }: { state: 'off' | 'idle' | 'running'; size?: number }) {
  return <div className={`orb ${state}`} style={{ width: size, height: size }} aria-hidden="true">
    <div className="orb-core" /><div className="orb-ring r1" /><div className="orb-ring r2" /><div className="orb-ring r3" />
  </div>
}

/** One-shot confetti burst for real wins (an offer). Pure canvas, no dependencies. */
export function burstConfetti() {
  if (prefersReducedMotion()) return
  const canvas = document.createElement('canvas')
  canvas.className = 'confetti'
  canvas.width = innerWidth * devicePixelRatio
  canvas.height = innerHeight * devicePixelRatio
  document.body.appendChild(canvas)
  const ctx = canvas.getContext('2d')
  if (!ctx) { canvas.remove(); return }
  ctx.scale(devicePixelRatio, devicePixelRatio)
  const colors = ['#65e6bd', '#7aa8ff', '#f5c77e', '#ff8fb1', '#c9a7ff', '#ffffff']
  const pieces = Array.from({ length: 160 }, () => ({
    x: innerWidth / 2, y: innerHeight * 0.35, vx: (Math.random() - 0.5) * 16, vy: -Math.random() * 14 - 4,
    size: 5 + Math.random() * 6, rot: Math.random() * Math.PI, vr: (Math.random() - 0.5) * 0.3, color: colors[Math.floor(Math.random() * colors.length)],
  }))
  const start = performance.now()
  const frame = (t: number) => {
    ctx.clearRect(0, 0, innerWidth, innerHeight)
    for (const p of pieces) {
      p.vy += 0.35; p.vx *= 0.99; p.x += p.vx; p.y += p.vy; p.rot += p.vr
      ctx.save(); ctx.translate(p.x, p.y); ctx.rotate(p.rot); ctx.fillStyle = p.color
      ctx.globalAlpha = Math.max(0, 1 - (t - start) / 2600); ctx.fillRect(-p.size / 2, -p.size / 4, p.size, p.size / 2); ctx.restore()
    }
    if (t - start < 2600) requestAnimationFrame(frame)
    else canvas.remove()
  }
  requestAnimationFrame(frame)
}
