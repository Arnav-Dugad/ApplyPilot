import { useCallback, useEffect, useLayoutEffect, useState, type CSSProperties } from 'react'
import { ArrowLeft, ArrowRight, BookOpen, PlayCircle, X } from 'lucide-react'
import type { EligibilityResult } from '../types'
import { Modal } from './Modal'
import { ELIGIBILITY_HELP, eligibilityLabel, eligibilityTone } from '../ui'

type Step = { target?: string; title: string; text: string }
const STEPS: Step[] = [
  { title: 'Welcome to ApplyPilot 👋', text: 'It finds internships for you all over the world, tells you in plain words whether you can apply, and fills in the application forms. You always press submit yourself.' },
  { target: 'nav-Home', title: 'Today', text: 'Your to-do list: the most useful things to do right now, in order.' },
  { target: 'nav-Autopilot', title: 'Autopilot', text: 'Turn it on and every few hours it searches job boards across the world, checks every job against your profile, and gets the best ones ready.' },
  { target: 'nav-Discover', title: 'Find jobs', text: 'Every internship it found, best first. Each one says “You qualify”, “Needs a visa” or “Not a fit”, with the exact sentence from the posting.' },
  { target: 'nav-Inbox', title: 'Inbox', text: 'Questions only you can answer, like “Are you willing to relocate?”. Answer once, and every application that asked it is updated.' },
  { target: 'nav-Queue', title: 'Ready to apply', text: 'Jobs whose forms are already filled in from your profile. Open one in Edge, check it, and press submit yourself.' },
  { target: 'nav-Tracker', title: 'My applications', text: 'Move each application along as you hear back: applied, interview, offer.' },
  { target: 'nav-Profile', title: 'My profile', text: 'Fill in your citizenship, CGPA, links and projects. The more you add, the better your matches and the more of each form gets filled.' },
  { target: 'command', title: 'Search anything', text: 'Press Ctrl + K to jump to any page, job or action. You can also type things like “remote ML internships”.' },
  { target: 'help', title: 'Help is always here', text: 'Click the question mark any time to see what every label means, or to replay this tour.' },
]

type Rect = { top: number; left: number; width: number; height: number }

/** A short spotlight tour of the main pages. Arrow keys move, Esc closes. */
export function Tour({ onDone }: { onDone: () => void }) {
  const [index, setIndex] = useState(0)
  const [rect, setRect] = useState<Rect | null>(null)
  const step = STEPS[index]
  const measure = useCallback(() => {
    const el = step.target ? document.querySelector(`[data-tour="${step.target}"]`) : null
    if (!el) { setRect(null); return }
    el.scrollIntoView({ block: 'nearest' })
    const r = el.getBoundingClientRect()
    setRect({ top: r.top - 6, left: r.left - 6, width: r.width + 12, height: r.height + 12 })
  }, [step.target])
  useLayoutEffect(() => { measure() }, [measure])
  useEffect(() => { addEventListener('resize', measure); return () => removeEventListener('resize', measure) }, [measure])
  const next = useCallback(() => index < STEPS.length - 1 ? setIndex(index + 1) : onDone(), [index, onDone])
  const back = useCallback(() => setIndex(i => Math.max(0, i - 1)), [])
  useEffect(() => {
    const key = (e: KeyboardEvent) => { if (e.key === 'ArrowRight' || e.key === 'Enter') { e.preventDefault(); next() } if (e.key === 'ArrowLeft') back(); if (e.key === 'Escape') onDone() }
    addEventListener('keydown', key); return () => removeEventListener('keydown', key)
  }, [next, back, onDone])

  // The card sits beside the highlighted item: to the right of the sidebar, below the top bar, centred otherwise.
  const card: CSSProperties = !rect ? { top: '50%', left: '50%', transform: 'translate(-50%, -50%)' }
    : rect.left < 260 ? { top: Math.min(Math.max(16, rect.top - 8), innerHeight - 250), left: rect.left + rect.width + 18 }
    : { top: rect.top + rect.height + 14, left: Math.min(Math.max(16, rect.left + rect.width / 2 - 170), innerWidth - 356) }
  return <div className="tour" role="dialog" aria-modal="true" aria-label="ApplyPilot tour">
    {rect ? <div className="tour-spot" style={rect} /> : <div className="tour-dim" />}
    <div className={`tour-card ${rect ? '' : 'center'}`} style={card} key={index}>
      <button className="icon-button tour-close" onClick={onDone} aria-label="Close tour"><X /></button>
      <small>{index + 1} of {STEPS.length}</small>
      <h3>{step.title}</h3>
      <p>{step.text}</p>
      <div className="tour-dots">{STEPS.map((_, i) => <i key={i} className={i === index ? 'on' : i < index ? 'done' : ''} />)}</div>
      <div className="tour-actions">{index > 0 ? <button className="button ghost" onClick={back}><ArrowLeft size={15} /> Back</button> : <button className="button ghost" onClick={onDone}>Skip</button>}
        <span className="spacer" /><button className="button primary" onClick={next} autoFocus>{index === STEPS.length - 1 ? 'Start using ApplyPilot' : <>Next <ArrowRight size={15} /></>}</button></div>
    </div>
  </div>
}

const RESULTS: EligibilityResult[] = ['ELIGIBLE', 'LIKELY_ELIGIBLE', 'VISA_NEEDED', 'NEEDS_INFORMATION', 'INELIGIBLE']
const WORDS: [string, string][] = [
  ['Score out of 100', 'How well a job matches you: skills, location, whether it is an internship, how new it is. Open a job to see every point explained.'],
  ['Autopilot', 'Searches job boards worldwide on a schedule, checks every job, and gets the best ones ready. It never submits anything.'],
  ['Ready to apply', 'Jobs whose forms ApplyPilot has already checked and filled from your profile. You open them in Edge and press submit.'],
  ['Inbox', 'Questions ApplyPilot could not answer from your profile. One answer fixes every application that asked it.'],
  ['Needs a visa', 'You fit the job, but you are not allowed to work in that country without a visa. ApplyPilot works this out from your citizenship.'],
  ['Visa sponsorship', 'When a company helps you get a work visa. Many postings say whether they do; ApplyPilot reads that for you.'],
  ['Saved answers', 'Answers you wrote once (like “Why this company?”) that ApplyPilot can reuse on similar questions.'],
  ['Practice mode', 'Fills and checks forms without letting anything be submitted. Good for trying things out.'],
  ['Worked out', 'Something ApplyPilot figured out from what you told it, like your year of study from your graduation date. It always tells you when it did this.'],
]

export function HelpModal({ onClose, onTour }: { onClose: () => void; onTour: () => void }) {
  return <Modal title="What everything means" subtitle="ApplyPilot in plain words." onClose={onClose}
    footer={<><span className="spacer" /><button className="button primary" onClick={() => { onClose(); onTour() }}><PlayCircle size={15} /> Replay the tour</button></>}>
    <div className="glossary">
      <h4><BookOpen size={14} /> Can I apply?</h4>
      {RESULTS.map(r => <div key={r} className="gloss-row"><span className={`badge ${eligibilityTone(r)}`}>{eligibilityLabel(r)}</span><p>{ELIGIBILITY_HELP[r]}</p></div>)}
      <h4><BookOpen size={14} /> Words you'll see</h4>
      {WORDS.map(([w, d]) => <div key={w} className="gloss-row"><b>{w}</b><p>{d}</p></div>)}
      <p className="muted small">Keyboard: Ctrl + K opens search from anywhere. Esc closes any window.</p>
    </div>
  </Modal>
}
