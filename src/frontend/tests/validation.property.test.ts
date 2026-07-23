/**
 * P-FE02: form-validation properties (business-rules.md FE-30..34). These mirror the
 * backend invariants the UI previews, most importantly BR-02 (weights not all zero).
 */

import fc from 'fast-check'
import { describe, expect, it } from 'vitest'

import { DEFAULT_OPTIMIZATION_FORM } from '../src/api/converters'
import { validateOptimizationForm } from '../src/api/validation'

const weight = fc.double({ min: 0, max: 5, noNaN: true })

describe('optimization form validation', () => {
  it('all-zero weights is ALWAYS invalid (BR-02)', () => {
    const form = { ...DEFAULT_OPTIMIZATION_FORM('E1'), travelTimeWeight: 0, travelCostWeight: 0, inequityWeight: 0 }
    const errors = validateOptimizationForm(form)
    expect(errors.some((e) => e.field === 'weights')).toBe(true)
  })

  it('a negative weight is ALWAYS invalid', () => {
    fc.assert(
      fc.property(fc.double({ min: -5, max: -0.001, noNaN: true }), (neg) => {
        const form = { ...DEFAULT_OPTIMIZATION_FORM('E1'), travelTimeWeight: neg }
        const errors = validateOptimizationForm(form)
        expect(errors.some((e) => e.field === 'travel_time_weight')).toBe(true)
      }),
    )
  })

  it('at least one positive weight and integer limits >= 1 -> no weight/limit errors', () => {
    fc.assert(
      fc.property(weight, weight, weight, fc.integer({ min: 1, max: 600 }), fc.integer({ min: 1, max: 50 }), (t, c, i, limit, cap) => {
        fc.pre(t + c + i > 0) // at least one positive
        const form = {
          ...DEFAULT_OPTIMIZATION_FORM('E1'),
          travelTimeWeight: t,
          travelCostWeight: c,
          inequityWeight: i,
          timeLimitSeconds: limit,
          departmentCapLimit: cap,
        }
        expect(validateOptimizationForm(form)).toHaveLength(0)
      }),
    )
  })

  it('a non-integer or < 1 time limit is invalid', () => {
    const form = { ...DEFAULT_OPTIMIZATION_FORM('E1'), timeLimitSeconds: 0 }
    expect(validateOptimizationForm(form).some((e) => e.field === 'time_limit_seconds')).toBe(true)
  })
})
