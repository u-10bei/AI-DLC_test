/**
 * Client-side, UX-only validation (business-rules.md FE-*). The backend stays the
 * source of truth (Q5=A): these give immediate feedback but a passing form can still
 * be rejected by the backend, and its message is what we ultimately show.
 *
 * Pure functions so the properties (fast-check) are cheap to state: e.g. all-zero
 * weights is ALWAYS invalid (BR-02), a negative weight is ALWAYS invalid.
 */

import type { OptimizationForm } from './converters'

export interface FieldError {
  field: string
  message: string
}

// FE-01/02, FE-10/11, FE-40: required, non-empty.
export function validateLogin(userId: string, password: string): FieldError[] {
  const errors: FieldError[] = []
  if (userId.trim() === '') errors.push({ field: 'user_id', message: 'ユーザーIDを入力してください' })
  if (password === '') errors.push({ field: 'password', message: 'パスワードを入力してください' })
  return errors
}

export function validateEventForm(id: string, name: string, type: string, date: string): FieldError[] {
  const errors: FieldError[] = []
  if (id.trim() === '') errors.push({ field: 'id', message: 'イベントIDを入力してください' })
  if (name.trim() === '') errors.push({ field: 'name', message: '名称を入力してください' })
  if (type.trim() === '') errors.push({ field: 'type', message: '種別を選択してください' })
  if (date.trim() === '') errors.push({ field: 'scheduled_date', message: '実施日を入力してください' })
  return errors
}

// FE-30..34: weights >= 0 with at least one > 0 (BR-02), limits >= 1.
export function validateOptimizationForm(form: OptimizationForm): FieldError[] {
  const errors: FieldError[] = []
  const weights = [
    ['travel_time_weight', form.travelTimeWeight],
    ['travel_cost_weight', form.travelCostWeight],
    ['inequity_weight', form.inequityWeight],
  ] as const

  for (const [field, value] of weights) {
    if (Number.isNaN(value) || value < 0) {
      errors.push({ field, message: '重みは0以上で入力してください' })
    }
  }
  const allZero = weights.every(([, v]) => v === 0)
  if (allZero) {
    errors.push({ field: 'weights', message: '少なくとも1つの重みは0より大きくしてください' })
  }
  if (!Number.isInteger(form.timeLimitSeconds) || form.timeLimitSeconds < 1) {
    errors.push({ field: 'time_limit_seconds', message: '制限時間は1以上の整数で入力してください' })
  }
  if (!Number.isInteger(form.departmentCapLimit) || form.departmentCapLimit < 1) {
    errors.push({ field: 'department_cap_limit', message: '部署上限は1以上の整数で入力してください' })
  }
  return errors
}

// FE-40: manual edit fields required.
export function validateAssignmentPatch(staffId: string, facilityId: string): FieldError[] {
  const errors: FieldError[] = []
  if (staffId.trim() === '') errors.push({ field: 'staff_id', message: '職員IDを選択してください' })
  if (facilityId.trim() === '') errors.push({ field: 'facility_id', message: '施設IDを選択してください' })
  return errors
}
