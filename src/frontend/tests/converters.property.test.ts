/**
 * P-FE01: DTO <-> view-model round-trip (the frontend counterpart of the backend's
 * P-API01). If a backend DTO field is dropped or renamed in the mapping, these fail.
 */

import fc from 'fast-check'
import { describe, expect, it } from 'vitest'

import {
  DEFAULT_OPTIMIZATION_FORM,
  fromAssignmentResponse,
  fromEventResponse,
  toOptimizationRequest,
} from '../src/api/converters'
import type { AssignmentResponse, EventResponse } from '../src/api/types'

const safeText = fc.string({ minLength: 1, maxLength: 20 })

describe('event view-model round-trip', () => {
  it('fromEventResponse preserves every field the DTO carries', () => {
    fc.assert(
      fc.property(safeText, safeText, safeText, safeText, safeText, (id, type, name, date, status) => {
        const dto: EventResponse = { id, type, name, scheduled_date: date, status }
        const view = fromEventResponse(dto)
        expect(view.id).toBe(dto.id)
        expect(view.type).toBe(dto.type)
        expect(view.name).toBe(dto.name)
        expect(view.scheduledDate).toBe(dto.scheduled_date)
        expect(view.status).toBe(dto.status)
      }),
    )
  })
})

describe('assignment view-model round-trip', () => {
  it('fromAssignmentResponse preserves ids and the pinned flag', () => {
    fc.assert(
      fc.property(safeText, safeText, fc.boolean(), (staff, facility, pinned) => {
        const dto: AssignmentResponse = { staff_id: staff, facility_id: facility, is_pinned: pinned }
        const view = fromAssignmentResponse(dto)
        expect(view.staffId).toBe(dto.staff_id)
        expect(view.facilityId).toBe(dto.facility_id)
        expect(view.isPinned).toBe(dto.is_pinned)
      }),
    )
  })
})

describe('optimization form -> request', () => {
  it('carries the weights and limits unchanged', () => {
    fc.assert(
      fc.property(
        fc.double({ min: 0, max: 5, noNaN: true }),
        fc.double({ min: 0, max: 5, noNaN: true }),
        fc.double({ min: 0, max: 5, noNaN: true }),
        fc.integer({ min: 1, max: 600 }),
        fc.integer({ min: 1, max: 50 }),
        (t, c, i, limit, cap) => {
          const form = {
            ...DEFAULT_OPTIMIZATION_FORM('E1'),
            travelTimeWeight: t,
            travelCostWeight: c,
            inequityWeight: i,
            timeLimitSeconds: limit,
            departmentCapLimit: cap,
          }
          const req = toOptimizationRequest(form)
          expect(req.travel_time_weight).toBe(t)
          expect(req.travel_cost_weight).toBe(c)
          expect(req.inequity_weight).toBe(i)
          expect(req.time_limit_seconds).toBe(limit)
          expect(req.department_cap_limit).toBe(cap)
          expect(req.event_id).toBe('E1')
        },
      ),
    )
  })
})
