/**
 * TypeScript mirror of U-07's DTOs (`src/api_orchestration/dto.py`).
 *
 * The backend is the source of truth for this contract (BR-API02). These types are
 * hand-written to match it; a drift is caught by the round-trip property tests
 * (converters, fast-check) — the frontend analog of the backend's P-API01.
 */

export type EventStatusLabel = string // Japanese label from the backend enum

export interface LoginRequest {
  user_id: string
  password: string
}

export interface EventRequest {
  id: string
  type: string // Japanese label; unknown -> backend 400 (BR-DM03)
  name: string
  scheduled_date: string // YYYY-MM-DD
}

export interface EventResponse {
  id: string
  type: string
  name: string
  scheduled_date: string
  status: string
}

export interface ImportResultResponse {
  success_count: number
}

export interface SufficiencyResponse {
  available: number
  unavailable: number
  undeclared: number
  required: number
  shortage: number
}

export type ReoptimizationMode = 'FULL' | 'INCREMENTAL'

export interface OptimizationRequest {
  event_id: string
  mode: ReoptimizationMode
  travel_time_weight: number
  travel_cost_weight: number
  inequity_weight: number
  time_limit_seconds: number
  department_cap_limit: number
}

export interface JobAcceptedResponse {
  job_id: string
  state: string
}

export type JobState = 'QUEUED' | 'RUNNING' | 'SUCCEEDED' | 'INFEASIBLE' | 'FAILED'

export const TERMINAL_STATES: readonly JobState[] = ['SUCCEEDED', 'INFEASIBLE', 'FAILED']

export interface AssignmentResponse {
  staff_id: string
  facility_id: string
  is_pinned: boolean
}

export interface ConstraintViolationResponse {
  constraint_id: string
  detail: string
  facility_id: string | null
  staff_id: string | null
}

export interface JobStatusResponse {
  job_id: string
  state: string
  assignments: AssignmentResponse[] | null
  objective_value: number | null
  optimality_gap: number | null
  solver_status: string | null
  violations: ConstraintViolationResponse[] | null
  detail: string | null
}

export interface AssignmentPatchRequest {
  staff_id: string
  facility_id: string
}

export interface RowErrorResponse {
  line: number
  message: string
}

export interface ErrorResponse {
  message: string
  violated_rule: string | null
  errors: RowErrorResponse[] | null
  violations: ConstraintViolationResponse[] | null
}
