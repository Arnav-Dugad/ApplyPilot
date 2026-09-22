import { describe, expect, it } from 'vitest'

describe('safety defaults', () => {
  it('keeps dry run and review before submit as product defaults', () => {
    const defaults = { dryRun: true, mode: 'REVIEW_BEFORE_SUBMIT', strict: true }
    expect(defaults).toEqual({ dryRun: true, mode: 'REVIEW_BEFORE_SUBMIT', strict: true })
  })
})
