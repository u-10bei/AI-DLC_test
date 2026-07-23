/**
 * LC-FE-05 DTO <-> view-model conversions (pure functions).
 *
 * These are the frontend analog of the backend's hand-written converters, and the
 * round-trip is property-tested with fast-check (the P-API01 counterpart). Keeping
 * the mapping explicit means a backend DTO change surfaces as a type/test failure
 * here rather than silently mis-rendering.
 */

import type {
  AssignmentResponse,
  EventRequest,
  EventResponse,
  OptimizationRequest,
  ReoptimizationMode,
} from './types'

// --- Event ------------------------------------------------------------------

export interface EventForm {
  id: string
  type: string
  name: string
  scheduledDate: string
}

export interface EventView {
  id: string
  type: string
  name: string
  scheduledDate: string
  status: string
}

export function toEventRequest(form: EventForm): EventRequest {
  return {
    id: form.id,
    type: form.type,
    name: form.name,
    scheduled_date: form.scheduledDate,
  }
}

export function fromEventResponse(dto: EventResponse): EventView {
  return {
    id: dto.id,
    type: dto.type,
    name: dto.name,
    scheduledDate: dto.scheduled_date,
    status: dto.status,
  }
}

// --- Optimization parameters ------------------------------------------------

export interface OptimizationForm {
  eventId: string
  mode: ReoptimizationMode
  travelTimeWeight: number
  travelCostWeight: number
  inequityWeight: number
  timeLimitSeconds: number
  departmentCapLimit: number
}

export function toOptimizationRequest(form: OptimizationForm): OptimizationRequest {
  return {
    event_id: form.eventId,
    mode: form.mode,
    travel_time_weight: form.travelTimeWeight,
    travel_cost_weight: form.travelCostWeight,
    inequity_weight: form.inequityWeight,
    time_limit_seconds: form.timeLimitSeconds,
    department_cap_limit: form.departmentCapLimit,
  }
}

export const DEFAULT_OPTIMIZATION_FORM = (eventId: string): OptimizationForm => ({
  eventId,
  mode: 'FULL',
  travelTimeWeight: 1.0,
  travelCostWeight: 1.0,
  inequityWeight: 0.5,
  timeLimitSeconds: 300,
  departmentCapLimit: 100,
})

// --- Assignment -------------------------------------------------------------

export interface AssignmentView {
  staffId: string
  facilityId: string
  isPinned: boolean
}

export function fromAssignmentResponse(dto: AssignmentResponse): AssignmentView {
  return {
    staffId: dto.staff_id,
    facilityId: dto.facility_id,
    isPinned: dto.is_pinned,
  }
}
