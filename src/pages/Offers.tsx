import { useState } from 'react'
import { Crown, HandCoins, Pencil, Plus, Trash2 } from 'lucide-react'
import { api } from '../api'
import { Modal } from '../components/Modal'
import type { OfferRow } from '../types'
import { Badge, Empty, PageHeading, formatDate, relativeTime, useAction, type PageProps } from '../ui'

const PERIODS: [OfferRow['period'], string][] = [['MONTH', 'per month'], ['HOUR', 'per hour'], ['WEEK', 'per week'], ['YEAR', 'per year'], ['TOTAL', 'for the whole internship']]
const PERKS: [string, string][] = [['housing', 'Housing (monthly value)'], ['relocation', 'Relocation (monthly equivalent)'], ['travel', 'Travel (monthly)'], ['meals', 'Meals (monthly)']]
type Draft = { id?: string; company: string; role: string; location: string; amount: string; currency: string; period: OfferRow['period']; hours_per_week: string; duration_months: string; decision_deadline: string; notes: string; perks: Record<string, string> }
const blank = (currency: string): Draft => ({ company: '', role: '', location: '', amount: '', currency, period: 'MONTH', hours_per_week: '40', duration_months: '3', decision_deadline: '', notes: '', perks: {} })
const money = (value: number | null | undefined, currency: string) => value == null ? '—' : new Intl.NumberFormat([], { style: 'currency', currency, maximumFractionDigits: 0 }).format(value)

export function Offers({ data, refresh }: PageProps) {
  const { run, busy } = useAction(refresh)
  const overview = data.offers ?? { base: 'USD', rows: [], currencies: ['USD'], rates_source: null }
  const [draft, setDraft] = useState<Draft | null>(null)
  const base = overview.base
  const max = Math.max(1, ...overview.rows.map(r => (r.monthly_base ?? 0) + (r.perks_base ?? 0)))
  const edit = (o: OfferRow) => setDraft({ id: o.id, company: o.company, role: o.role, location: o.location, amount: String(o.amount), currency: o.currency, period: o.period, hours_per_week: String(o.hours_per_week), duration_months: String(o.duration_months), decision_deadline: o.decision_deadline ?? '', notes: o.notes, perks: Object.fromEntries(Object.entries(o.perks ?? {}).map(([k, v]) => [k, String(v)])) })
  const save = async () => {
    if (!draft) return
    const ok = await run('save', () => api.saveOffer({ ...draft, amount: Number(draft.amount), hours_per_week: Number(draft.hours_per_week), duration_months: Number(draft.duration_months), perks: Object.fromEntries(Object.entries(draft.perks).filter(([, v]) => v.trim()).map(([k, v]) => [k, Number(v)])) }), 'Offer saved')
    if (ok) setDraft(null)
  }

  return <>
    <PageHeading eyebrow="Offers" title={overview.rows.length > 1 ? 'Compare your offers' : 'Your offers'} text="Every stipend normalised to a monthly amount in one currency, so offers in different countries and pay periods compare fairly.">
      <label className="currency-pick">Compare in<select value={base} onChange={e => run('base', () => api.settings({ base_currency: e.target.value }))}>{overview.currencies.map(c => <option key={c}>{c}</option>)}</select></label>
      <button className="button primary" onClick={() => setDraft(blank(base))}><Plus size={16} /> Add offer</button>
    </PageHeading>
    {overview.rows.length ? <>
      <div className="offer-grid stagger">{overview.rows.map(o => <article key={o.id} className={`offer-card ${o.best ? 'best' : ''}`}>
        {o.best && overview.rows.length > 1 && <span className="crown"><Crown size={14} /> Highest pay</span>}
        <header><div className="company-mark">{o.company.slice(0, 1)}</div><div><b>{o.company}</b><span>{o.role || 'Internship'}{o.location ? ` · ${o.location}` : ''}</span></div>
          <button className="icon-button" onClick={() => edit(o)} aria-label="Edit offer"><Pencil /></button><button className="icon-button" onClick={() => confirm(`Delete the ${o.company} offer?`) && run('del', () => api.deleteOffer(o.id), 'Offer deleted')} aria-label="Delete offer"><Trash2 /></button></header>
        <strong className="offer-amount">{money(o.monthly_base, base)}<small>/month</small></strong>
        <p className="muted small">{money(o.amount, o.currency)} {PERIODS.find(p => p[0] === o.period)?.[1]}{o.period !== 'MONTH' ? ` · ${money(o.monthly, o.currency)}/month` : ''}{o.currency !== base ? ` · converted from ${o.currency}` : ''}</p>
        <div className="offer-facts"><span><b>{money(o.total_base, base)}</b>total over {o.duration_months} mo</span><span><b>{money(o.hourly_base, base)}</b>per hour</span>{o.perks_base > 0 && <span><b>{money(o.perks_base, base)}</b>perks /mo</span>}</div>
        {o.decision_deadline && <Badge tone="warn">Decide {relativeTime(o.decision_deadline)} · {formatDate(o.decision_deadline)}</Badge>}
        {o.notes && <p className="offer-notes">{o.notes}</p>}
      </article>)}</div>
      {overview.rows.length > 1 && <section className="panel"><div className="panel-head"><div><h2>Monthly value</h2><p>Stipend plus perks, in {base}</p></div></div>
        <div className="offer-bars">{overview.rows.map(o => <div key={o.id} className="offer-bar"><span>{o.company}</span><div><i className="pay" style={{ width: `${((o.monthly_base ?? 0) / max) * 100}%` }} /><i className="perk" style={{ width: `${((o.perks_base ?? 0) / max) * 100}%` }} /></div><b>{money((o.monthly_base ?? 0) + (o.perks_base ?? 0), base)}</b></div>)}</div>
        <small className="muted">Rates: {overview.rates_source ?? '—'}{overview.rates_updated ? ` · ${overview.rates_updated}` : ''}. Gulf currencies use their official US-dollar pegs.</small></section>}
    </> : <section className="panel"><Empty icon={HandCoins} title="No offers yet" text="When an offer arrives, add it here to compare pay across countries, currencies, and pay periods." action={() => setDraft(blank(base))} actionLabel="Add an offer" /></section>}

    {draft && <Modal title={draft.id ? 'Edit offer' : 'Add an offer'} subtitle="Only you see this. Amounts stay on your computer." onClose={() => setDraft(null)}
      footer={<><button className="button ghost" onClick={() => setDraft(null)}>Cancel</button><button className="button primary" disabled={!draft.company.trim() || !(Number(draft.amount) > 0) || busy === 'save'} onClick={save}>Save offer</button></>}>
      <div className="form-grid">
        <label>Company *<input value={draft.company} onChange={e => setDraft({ ...draft, company: e.target.value })} autoFocus /></label>
        <label>Role<input value={draft.role} onChange={e => setDraft({ ...draft, role: e.target.value })} /></label>
        <label>Pay *<input inputMode="decimal" value={draft.amount} onChange={e => setDraft({ ...draft, amount: e.target.value.replace(/[^\d.]/g, '') })} placeholder="3000" /></label>
        <label>Currency<select value={draft.currency} onChange={e => setDraft({ ...draft, currency: e.target.value })}>{overview.currencies.map(c => <option key={c}>{c}</option>)}</select></label>
        <label>Paid<select value={draft.period} onChange={e => setDraft({ ...draft, period: e.target.value as OfferRow['period'] })}>{PERIODS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>
        <label>Duration (months)<input inputMode="decimal" value={draft.duration_months} onChange={e => setDraft({ ...draft, duration_months: e.target.value })} /></label>
        {(draft.period === 'HOUR' || draft.period === 'WEEK') && <label>Hours per week<input inputMode="decimal" value={draft.hours_per_week} onChange={e => setDraft({ ...draft, hours_per_week: e.target.value })} /></label>}
        <label>Location<input value={draft.location} onChange={e => setDraft({ ...draft, location: e.target.value })} /></label>
        <label>Decide by<input type="date" value={draft.decision_deadline} onChange={e => setDraft({ ...draft, decision_deadline: e.target.value })} /></label>
        {PERKS.map(([k, l]) => <label key={k}>{l}<input inputMode="decimal" value={draft.perks[k] ?? ''} onChange={e => setDraft({ ...draft, perks: { ...draft.perks, [k]: e.target.value.replace(/[^\d.]/g, '') } })} placeholder="0" /></label>)}
        <label className="span-2">Notes<textarea value={draft.notes} onChange={e => setDraft({ ...draft, notes: e.target.value })} placeholder="Team, mentor, return-offer chances…" /></label>
      </div>
    </Modal>}
  </>
}
