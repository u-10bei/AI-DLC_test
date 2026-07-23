/**
 * LC-FE-01 ApiClient — the single window onto U-07's REST API.
 *
 * Two things live here so no view has to reinvent them:
 *   - 401 capture (PAT-FE-11 / FE-50): any 401 fires onUnauthorized(); views never
 *     handle session expiry individually.
 *   - typed errors (PAT-FE-13 / FE-53): a non-2xx becomes a typed ApiError carrying
 *     the backend's ErrorResponse verbatim. The backend never leaks internals
 *     (SECURITY-09), so surfacing its message as-is is safe.
 *
 * The session is an HttpOnly cookie (BR-API21); credentials:'include' sends it and
 * JS never touches it (PAT-FE-10).
 */

import type { ErrorResponse } from './types'

export class ApiError extends Error {
  readonly status: number
  readonly body: ErrorResponse | null

  constructor(status: number, body: ErrorResponse | null) {
    super(body?.message ?? `リクエストに失敗しました (${status})`)
    this.name = 'ApiError'
    this.status = status
    this.body = body
  }
}

export interface ApiClientOptions {
  /** Externalised backend base URL (NFR-M05/M03). Empty = same origin (production). */
  baseUrl?: string
  /** Called on any 401 so the app can redirect to login (PAT-FE-11). */
  onUnauthorized?: () => void
}

export class ApiClient {
  private readonly baseUrl: string
  private readonly onUnauthorized: (() => void) | undefined

  constructor(options: ApiClientOptions = {}) {
    this.baseUrl = options.baseUrl ?? ''
    this.onUnauthorized = options.onUnauthorized
  }

  async getJson<T>(path: string): Promise<T> {
    return this.request<T>('GET', path)
  }

  async postJson<T>(path: string, body: unknown): Promise<T> {
    return this.request<T>('POST', path, JSON.stringify(body), 'application/json')
  }

  async patchJson<T>(path: string, body: unknown): Promise<T> {
    return this.request<T>('PATCH', path, JSON.stringify(body), 'application/json')
  }

  /** login / logout return 204 with no body. */
  async postEmpty(path: string, body: unknown): Promise<void> {
    await this.request<unknown>('POST', path, JSON.stringify(body), 'application/json', true)
  }

  async deleteEmpty(path: string): Promise<void> {
    await this.request<unknown>('DELETE', path, undefined, undefined, true)
  }

  /** CSV import: the raw file bytes are the body (the backend parses, not us — FE-21). */
  async postCsv(path: string, file: File): Promise<{ success_count: number }> {
    return this.request<{ success_count: number }>('POST', path, file, 'text/csv')
  }

  /** CSV export: returns the text so the caller can offer it as a download. */
  async getText(path: string): Promise<string> {
    const response = await this.fetch('GET', path)
    await this.guard(response)
    return response.text()
  }

  private async request<T>(
    method: string,
    path: string,
    body?: BodyInit,
    contentType?: string,
    empty = false,
  ): Promise<T> {
    const response = await this.fetch(method, path, body, contentType)
    await this.guard(response)
    if (empty || response.status === 204) return undefined as T
    return (await response.json()) as T
  }

  private fetch(method: string, path: string, body?: BodyInit, contentType?: string): Promise<Response> {
    const headers: Record<string, string> = {}
    if (contentType) headers['Content-Type'] = contentType
    const init: RequestInit = {
      method,
      headers,
      credentials: 'include', // send the HttpOnly session cookie (PAT-FE-10)
    }
    if (body !== undefined) init.body = body
    return fetch(`${this.baseUrl}${path}`, init)
  }

  private async guard(response: Response): Promise<void> {
    if (response.ok) return
    if (response.status === 401) {
      this.onUnauthorized?.() // PAT-FE-11: one place decides expiry -> login
    }
    throw new ApiError(response.status, await this.readError(response))
  }

  private async readError(response: Response): Promise<ErrorResponse | null> {
    try {
      const data: unknown = await response.json()
      if (data && typeof data === 'object' && 'message' in data) {
        return data as ErrorResponse
      }
      // FastAPI validation errors (422) use {detail: ...}; normalise to a message.
      if (data && typeof data === 'object' && 'detail' in data) {
        const detail = (data as { detail: unknown }).detail
        return {
          message: typeof detail === 'string' ? detail : '入力内容が正しくありません',
          violated_rule: null,
          errors: null,
          violations: null,
        }
      }
      return null
    } catch {
      return null
    }
  }
}
