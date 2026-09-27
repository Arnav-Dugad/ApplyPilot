import { useMemo, useState } from 'react'
import { geoCentroid, geoNaturalEarth1, geoPath } from 'd3-geo'
import { feature } from 'topojson-client'
import type { Feature, FeatureCollection, Geometry } from 'geojson'
import type { GeometryCollection, Topology } from 'topojson-specification'
import atlas from 'world-atlas/countries-110m.json'
import type { Job } from '../types'

// ISO alpha-2 → Natural Earth numeric id (generated from the atlas); tiny states are drawn as points.
const NUMERIC: Record<string, string> = { AE: '784', AU: '036', CA: '124', CH: '756', DE: '276', DK: '208', ES: '724', FI: '246', FR: '250', GB: '826', IE: '372', IN: '356', IT: '380', JP: '392', KW: '414', NL: '528', NO: '578', NZ: '554', OM: '512', PL: '616', PT: '620', QA: '634', SA: '682', SE: '752', US: '840', AT: '040', BE: '056', BG: '100', BR: '076', CN: '156', CY: '196', CZ: '203', EE: '233', EG: '818', GR: '300', HR: '191', HU: '348', ID: '360', IL: '376', IS: '352', JO: '400', KR: '410', LB: '422', LT: '440', LU: '442', LV: '428', MX: '484', MY: '458', PH: '608', PK: '586', RO: '642', SI: '705', SK: '703', TR: '792', TW: '158', VN: '704', ZA: '710', TH: '764', NG: '566' }
const POINTS: Record<string, [number, number]> = { SG: [103.82, 1.35], BH: [50.55, 26.07], HK: [114.17, 22.32], MT: [14.38, 35.94] }
const NAMES: Record<string, string> = { SG: 'Singapore', BH: 'Bahrain', HK: 'Hong Kong', MT: 'Malta' }

type Stat = { code: string; name: string; jobs: number; strong: number; roles: string[] }

export function WorldMap({ jobs, onSelect }: { jobs: Job[]; onSelect?: (code: string, name: string) => void }) {
  const [hover, setHover] = useState<Stat | null>(null)
  const [tip, setTip] = useState<[number, number]>([0, 0])
  const width = 960, height = 480
  const { shapes, projection } = useMemo(() => {
    const topology = atlas as unknown as Topology<{ countries: GeometryCollection<{ name: string }> }>
    const collection = feature(topology, topology.objects.countries) as unknown as FeatureCollection<Geometry, { name: string }>
    const shapes = collection.features.filter(f => f.properties.name !== 'Antarctica')
    const projection = geoNaturalEarth1().fitExtent([[8, 8], [width - 8, height - 8]], { type: 'FeatureCollection', features: shapes } as FeatureCollection)
    return { shapes, projection }
  }, [])
  const path = useMemo(() => geoPath(projection), [projection])

  const stats = useMemo(() => {
    const byCode = new Map<string, Stat>()
    for (const job of jobs) {
      if (job.duplicate_of || !job.country_code) continue
      const stat = byCode.get(job.country_code) ?? { code: job.country_code, name: '', jobs: 0, strong: 0, roles: [] }
      stat.jobs += 1
      if ((job.score?.score ?? 0) >= 80) stat.strong += 1
      if (stat.roles.length < 3 && job.role) stat.roles.push(`${job.role} · ${job.company}`)
      byCode.set(job.country_code, stat)
    }
    return byCode
  }, [jobs])
  const max = Math.max(1, ...Array.from(stats.values()).map(s => s.jobs))
  const byNumeric = new Map(Object.entries(NUMERIC).map(([a2, n]) => [n, a2]))
  const shade = (count: number) => count ? 0.18 + 0.72 * Math.sqrt(count / max) : 0

  const enter = (stat: Stat, name: string, e: React.MouseEvent) => { setHover({ ...stat, name }); setTip([e.nativeEvent.offsetX, e.nativeEvent.offsetY]) }
  const bubbles = Array.from(stats.values()).map(stat => {
    const numeric = NUMERIC[stat.code]
    const shape = numeric ? shapes.find(s => (s as Feature & { id?: string }).id === numeric) : undefined
    const point = shape ? projection(geoCentroid(shape)) : POINTS[stat.code] ? projection(POINTS[stat.code]) : null
    return point ? { stat, name: shape?.properties.name ?? NAMES[stat.code] ?? stat.code, x: point[0], y: point[1] } : null
  }).filter(Boolean) as { stat: Stat; name: string; x: number; y: number }[]

  return <div className="world-map" onMouseLeave={() => setHover(null)}>
    <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Where your matching internships are">
      <path className="graticule" d={path({ type: 'Sphere' }) ?? ''} />
      {shapes.map((shape, i) => {
        const code = byNumeric.get(String((shape as Feature & { id?: string }).id))
        const stat = code ? stats.get(code) : undefined
        return <path key={i} d={path(shape) ?? ''} className={`country ${stat ? 'has-jobs' : ''}`} style={stat ? { fillOpacity: shade(stat.jobs) } : undefined}
          onMouseMove={stat ? e => enter(stat, shape.properties.name, e) : undefined} onClick={stat && onSelect ? () => onSelect(stat.code, shape.properties.name) : undefined} />
      })}
      {bubbles.map(({ stat, name, x, y }) => <g key={stat.code} className="map-bubble" onMouseMove={e => enter(stat, name, e)} onClick={() => onSelect?.(stat.code, name)}>
        {stat.strong > 0 && <circle cx={x} cy={y} r={5 + 16 * Math.sqrt(stat.jobs / max)} className="pulse" />}
        <circle cx={x} cy={y} r={3 + 12 * Math.sqrt(stat.jobs / max)} className="dot" />
        {stat.jobs >= max * 0.25 && <text x={x} y={y - 8 - 12 * Math.sqrt(stat.jobs / max)} textAnchor="middle">{stat.jobs}</text>}
      </g>)}
    </svg>
    {hover && <div className="map-tip" style={{ left: `${(tip[0] / width) * 100}%`, top: `${(tip[1] / height) * 100}%` }}>
      <b>{hover.name}</b><span>{hover.jobs} job{hover.jobs === 1 ? '' : 's'}{hover.strong ? ` · ${hover.strong} strong match${hover.strong === 1 ? '' : 'es'}` : ''}</span>
      {hover.roles.map(r => <small key={r}>{r}</small>)}{onSelect && <em>Click to see them</em>}
    </div>}
  </div>
}
