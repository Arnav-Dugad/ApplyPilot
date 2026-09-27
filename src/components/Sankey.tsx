import { useMemo, useState } from 'react'
import type { Application, Job } from '../types'

type Node = { id: string; label: string; column: number; value: number; tone: string; y: number; h: number }
type Link = { source: string; target: string; value: number; sy: number; ty: number; tone: string }

const TONES: Record<string, string> = {
  discovered: 'var(--accent2)', eligible: 'var(--accent)', likely: '#4fd1a5', needs: 'var(--amber)', ineligible: 'var(--rose)', unanalyzed: 'var(--muted)',
  queued: '#8ab8ff', notqueued: 'var(--muted)', active: '#8ab8ff', applied: 'var(--violet)', interviewing: '#f0a3ff', awaiting: 'var(--muted)', rejected: 'var(--rose)', withdrawn: 'var(--muted)', offer: '#ffd66b',
}
const LABELS: Record<string, string> = {
  discovered: 'Discovered', eligible: 'Eligible', likely: 'Likely eligible', needs: 'Needs info', ineligible: 'Ineligible', unanalyzed: 'Not analyzed', queued: 'Queued', notqueued: 'Not queued',
  active: 'In progress', applied: 'Applied', interviewing: 'Interviewing', awaiting: 'Awaiting reply', rejected: 'Rejected', withdrawn: 'Withdrawn', offer: 'Offer',
}
const ORDER = ['discovered', 'eligible', 'likely', 'needs', 'ineligible', 'unanalyzed', 'queued', 'notqueued', 'applied', 'active', 'interviewing', 'awaiting', 'rejected', 'withdrawn', 'offer']

/** Every job's path through the pipeline; consecutive steps become weighted links. */
export function pipelinePaths(jobs: Job[], apps: Application[]): string[][] {
  const byJob = new Map(apps.map(a => [a.job_id, a]))
  return jobs.filter(j => !j.duplicate_of).map(job => {
    const elig = job.eligibility_result === 'ELIGIBLE' ? 'eligible' : job.eligibility_result === 'LIKELY_ELIGIBLE' ? 'likely' : job.eligibility_result === 'NEEDS_INFORMATION' ? 'needs' : job.eligibility_result === 'INELIGIBLE' ? 'ineligible' : 'unanalyzed'
    const app = byJob.get(job.id)
    if (!app) return ['discovered', elig, 'notqueued']
    const s = app.status
    if (['QUEUED', 'NEEDS_INFO', 'WAITING_FOR_USER', 'READY_FOR_REVIEW'].includes(s)) return ['discovered', elig, 'queued', 'active']
    if (s === 'OFFER') return ['discovered', elig, 'queued', 'applied', 'interviewing', 'offer']
    const outcome = s === 'INTERVIEWING' ? 'interviewing' : s === 'REJECTED' ? 'rejected' : s === 'WITHDRAWN' ? 'withdrawn' : 'awaiting'
    return ['discovered', elig, 'queued', 'applied', outcome]
  })
}

export function Sankey({ jobs, apps, height = 330 }: { jobs: Job[]; apps: Application[]; height?: number }) {
  const [hover, setHover] = useState<string | null>(null)
  const width = 960
  const layout = useMemo(() => {
    const paths = pipelinePaths(jobs, apps)
    const counts = new Map<string, number>()
    const column = new Map<string, number>()
    const links = new Map<string, number>()
    for (const path of paths) path.forEach((node, i) => {
      counts.set(node, (counts.get(node) ?? 0) + 1)
      column.set(node, Math.max(column.get(node) ?? 0, i))
      if (i > 0) links.set(`${path[i - 1]}>${node}`, (links.get(`${path[i - 1]}>${node}`) ?? 0) + 1)
    })
    const total = paths.length || 1
    const columns = Math.max(...Array.from(column.values()), 1)
    const gap = 14, top = 18, usable = height - top * 2
    const nodes: Node[] = []
    for (let c = 0; c <= columns; c++) {
      const inColumn = ORDER.filter(id => column.get(id) === c && counts.get(id))
      const gaps = gap * Math.max(0, inColumn.length - 1)
      let y = top
      for (const id of inColumn) {
        const h = Math.max(3, ((counts.get(id) ?? 0) / total) * (usable - gaps))
        nodes.push({ id, label: LABELS[id], column: c, value: counts.get(id) ?? 0, tone: TONES[id], y, h })
        y += h + gap
      }
    }
    const byId = new Map(nodes.map(n => [n.id, n]))
    const outOffset = new Map<string, number>(), inOffset = new Map<string, number>()
    const linkList: Link[] = Array.from(links.entries())
      .sort((a, b) => ORDER.indexOf(a[0].split('>')[1]) - ORDER.indexOf(b[0].split('>')[1]))
      .map(([key, value]) => {
        const [source, target] = key.split('>')
        const s = byId.get(source)!, t = byId.get(target)!
        const band = (value / (s.value || 1)) * s.h
        const tBand = (value / (t.value || 1)) * t.h
        const sy = s.y + (outOffset.get(source) ?? 0) + band / 2
        const ty = t.y + (inOffset.get(target) ?? 0) + tBand / 2
        outOffset.set(source, (outOffset.get(source) ?? 0) + band)
        inOffset.set(target, (inOffset.get(target) ?? 0) + tBand)
        return { source, target, value, sy, ty, tone: t.tone }
      })
    return { nodes, links: linkList, columns, total: paths.length }
  }, [jobs, apps, height])

  if (!layout.total) return <p className="muted small">The pipeline appears once ApplyPilot has found some jobs.</p>
  const colX = (c: number) => 24 + (c / Math.max(1, layout.columns)) * (width - 200)
  const nodeW = 12
  const byId = new Map(layout.nodes.map(n => [n.id, n]))
  return <svg className="sankey" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Pipeline from discovered jobs to offers">
    <defs>{layout.links.map((l, i) => <linearGradient key={i} id={`sk-${i}`} x1="0" x2="1"><stop offset="0" stopColor={byId.get(l.source)!.tone} stopOpacity=".55" /><stop offset="1" stopColor={l.tone} stopOpacity=".55" /></linearGradient>)}</defs>
    {layout.links.map((l, i) => {
      const s = byId.get(l.source)!, t = byId.get(l.target)!
      const x0 = colX(s.column) + nodeW, x1 = colX(t.column)
      const mid = (x0 + x1) / 2
      const width = Math.max(1.5, (l.value / (s.value || 1)) * s.h)
      const dim = hover && hover !== l.source && hover !== l.target
      return <path key={i} className={`sk-link ${dim ? 'dim' : ''}`} d={`M${x0},${l.sy} C${mid},${l.sy} ${mid},${l.ty} ${x1},${l.ty}`} stroke={`url(#sk-${i})`} strokeWidth={width} style={{ animationDelay: `${120 + s.column * 140}ms` }}>
        <title>{`${LABELS[l.source]} → ${LABELS[l.target]}: ${l.value}`}</title></path>
    })}
    {layout.nodes.map(n => <g key={n.id} className="sk-node" onMouseEnter={() => setHover(n.id)} onMouseLeave={() => setHover(null)} style={{ animationDelay: `${n.column * 140}ms` }}>
      <rect x={colX(n.column)} y={n.y} width={nodeW} height={n.h} rx={4} fill={n.tone} />
      <text x={colX(n.column) + nodeW + 7} y={n.y + n.h / 2} dominantBaseline="middle"><tspan className="sk-label">{n.label}</tspan><tspan className="sk-value" dx="6">{n.value}</tspan></text>
    </g>)}
  </svg>
}
