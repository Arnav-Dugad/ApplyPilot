import { useEffect, useMemo, useState } from 'react'
import { CalendarDays, ChevronLeft, ChevronRight } from 'lucide-react'
import { api } from '../api'
import type { CalendarData, CalendarEvent } from '../types'
import { Skeleton } from '../motion'
import { Empty, PageHeading, formatDate, type PageProps } from '../ui'

const KIND_LABEL: Record<CalendarEvent['kind'], string> = { POSTED: 'Opened', DEADLINE: 'Deadline', APPLIED: 'Applied', INTERVIEW: 'Interview' }
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
const key = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`

export function Calendar({ data, openJob }: PageProps) {
  const [cal, setCal] = useState<CalendarData | null>(null)
  const [cursor, setCursor] = useState(() => { const d = new Date(); return new Date(d.getFullYear(), d.getMonth(), 1) })
  const [picked, setPicked] = useState<string | null>(null)
  useEffect(() => { api.calendar().then(setCal).catch(() => setCal({ events: [], seasons: [] })) }, [data.jobs.length, data.applications.length])

  const byDay = useMemo(() => {
    const map = new Map<string, CalendarEvent[]>()
    for (const e of cal?.events ?? []) map.set(e.date, [...(map.get(e.date) ?? []), e])
    return map
  }, [cal])
  const cells = useMemo(() => {
    const first = new Date(cursor)
    const offset = (first.getDay() + 6) % 7 // Monday first
    const start = new Date(first.getFullYear(), first.getMonth(), 1 - offset)
    return Array.from({ length: 42 }, (_, i) => new Date(start.getFullYear(), start.getMonth(), start.getDate() + i))
  }, [cursor])
  const today = key(new Date())
  const upcoming = (cal?.events ?? []).filter(e => e.kind === 'DEADLINE' && e.date >= today).slice(0, 8)
  const shownDay = picked ?? today
  const peak = Math.max(1, ...(cal?.seasons ?? []).flatMap(s => s.months))

  if (cal === null) return <><PageHeading eyebrow="Calendar" title="Your internship calendar" text="Openings, deadlines, applications, and interviews." /><Skeleton lines={10} /></>
  return <>
    <PageHeading eyebrow="Calendar" title="Your internship calendar" text="Openings, deadlines, applications, and interviews — plus when each company usually hires." />
    <div className="calendar-layout">
      <section className="panel calendar">
        <header className="cal-head"><button className="icon-button" onClick={() => setCursor(new Date(cursor.getFullYear(), cursor.getMonth() - 1, 1))} aria-label="Previous month"><ChevronLeft /></button>
          <h2>{cursor.toLocaleDateString([], { month: 'long', year: 'numeric' })}</h2>
          <button className="icon-button" onClick={() => setCursor(new Date(cursor.getFullYear(), cursor.getMonth() + 1, 1))} aria-label="Next month"><ChevronRight /></button>
          <button className="button subtle" onClick={() => { const d = new Date(); setCursor(new Date(d.getFullYear(), d.getMonth(), 1)); setPicked(null) }}>Today</button>
          <div className="cal-legend">{(Object.keys(KIND_LABEL) as CalendarEvent['kind'][]).map(k => <span key={k} className={k.toLowerCase()}>{KIND_LABEL[k]}</span>)}</div></header>
        <div className="cal-grid">{['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].map(d => <div key={d} className="cal-dow">{d}</div>)}
          {cells.map(day => { const k = key(day); const events = byDay.get(k) ?? []; const kinds = Array.from(new Set(events.map(e => e.kind)))
            return <button key={k} className={`cal-day ${day.getMonth() !== cursor.getMonth() ? 'other' : ''} ${k === today ? 'today' : ''} ${k === shownDay ? 'picked' : ''}`} onClick={() => setPicked(k)}>
              <span className="num">{day.getDate()}</span>
              {events.length > 0 && <span className="cal-dots">{kinds.map(kind => <i key={kind} className={kind.toLowerCase()} />)}{events.length > 3 && <em>{events.length}</em>}</span>}
            </button> })}</div>
      </section>
      <div className="stack">
        <section className="panel"><div className="panel-head"><div><h2>{shownDay === today ? 'Today' : formatDate(shownDay)}</h2><p>{(byDay.get(shownDay) ?? []).length} event{(byDay.get(shownDay) ?? []).length === 1 ? '' : 's'}</p></div></div>
          {(byDay.get(shownDay) ?? []).length ? <div className="day-events">{(byDay.get(shownDay) ?? []).map((e, i) => <button key={i} className={`day-event ${e.kind.toLowerCase()}`} onClick={() => e.job_id && openJob(e.job_id)}><i />{e.title}</button>)}</div> : <p className="muted small">Nothing on this day.</p>}</section>
        <section className="panel"><div className="panel-head"><div><h2>Coming deadlines</h2><p>Postings that list a closing date</p></div></div>
          {upcoming.length ? <div className="day-events">{upcoming.map((e, i) => <button key={i} className="day-event deadline" onClick={() => e.job_id && openJob(e.job_id)}><i />{e.title}<small>{formatDate(e.date)}</small></button>)}</div> : <p className="muted small">No upcoming deadlines listed.</p>}</section>
      </div>
    </div>
    <section className="panel"><div className="panel-head"><div><h2>Hiring seasons</h2><p>When each company you follow has posted roles, by month (based on what ApplyPilot has seen)</p></div></div>
      {cal.seasons.length ? <div className="season-table"><div className="season-row head"><span />{MONTHS.map(m => <b key={m}>{m}</b>)}</div>
        {cal.seasons.map(s => <div key={s.company} className="season-row"><span>{s.company}</span>{s.months.map((n, i) => <i key={i} title={`${n} in ${MONTHS[i]}`} style={{ opacity: n ? 0.18 + 0.82 * (n / peak) : 1 }} className={n ? 'on' : ''} />)}</div>)}</div>
        : <Empty icon={CalendarDays} title="Follow companies to see their seasons" text="Autopilot records when roles open so you can apply early next cycle." />}
    </section>
  </>
}
