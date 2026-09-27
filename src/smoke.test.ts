import { describe, expect, it } from 'vitest'
import type { Job } from './types'
import { eligibilityLabel, eligibilityRank, formatValue, statusTone } from './ui'

const job = (over: Partial<Job>): Job => ({ id: 'j', description: '', required_skills: [], preferred_skills: [], extraction_status: 'UNVERIFIED', date_found: '', ...over })

describe('ui helpers', () => {
  it('ranks eligible jobs first, then by required-skill coverage, ineligible last', () => {
    const jobs = [
      job({ id: 'ineligible', eligibility_result: 'INELIGIBLE' }),
      job({ id: 'unanalyzed' }),
      job({ id: 'eligible-low', eligibility_result: 'ELIGIBLE', eligibility_match: { strong: [], partial: [], missing: [], required_coverage: 40 } }),
      job({ id: 'needs-info', eligibility_result: 'NEEDS_INFORMATION' }),
      job({ id: 'visa', eligibility_result: 'VISA_NEEDED' }),
      job({ id: 'eligible-high', eligibility_result: 'ELIGIBLE', eligibility_match: { strong: [], partial: [], missing: [], required_coverage: 90 } }),
    ]
    expect(jobs.sort((a, b) => eligibilityRank(a) - eligibilityRank(b)).map(j => j.id)).toEqual(['eligible-high', 'eligible-low', 'visa', 'needs-info', 'unanalyzed', 'ineligible'])
  })

  it('never renders a missing value as if it were an answer', () => {
    expect(formatValue(null)).toBe('Not provided')
    expect(formatValue('')).toBe('Not provided')
    expect(formatValue(false)).toBe('No')
    expect(formatValue(['Python', 'Git'])).toBe('Python, Git')
  })

  it('labels statuses and eligibility for people, not enums', () => {
    expect(eligibilityLabel('NEEDS_INFORMATION')).toBe('Needs your answer')
    expect(eligibilityLabel('VISA_NEEDED')).toBe('Needs a visa')
    expect(eligibilityLabel('INELIGIBLE')).toBe('Not a fit')
    expect(eligibilityLabel(undefined)).toBe('Not checked')
    expect(statusTone('WAITING_FOR_USER')).toBe('warn')
    expect(statusTone('OFFER')).toBe('good')
  })
})
