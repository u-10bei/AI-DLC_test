/**
 * V-02 Event create / view (US-05). `type` is chosen from a fixed list of Japanese
 * labels — the frontend never re-implements the enum, it sends the label and the
 * backend converts it (FE-12 / BR-DM03).
 */

import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'

import { ApiError } from '../api/client'
import { fromEventResponse, toEventRequest, type EventView as EventVM } from '../api/converters'
import type { EventResponse } from '../api/types'
import { validateEventForm, type FieldError } from '../api/validation'
import { useApi } from '../app/apiContext'
import { useAuth } from '../app/AuthContext'

// Japanese labels matching the backend EventType enum (US-05).
const EVENT_TYPES = ['災害時避難所応援', '選挙事務'] as const

export function EventView(): JSX.Element {
  const api = useApi()
  const auth = useAuth()
  const [id, setId] = useState('')
  const [name, setName] = useState('')
  const [type, setType] = useState<string>(EVENT_TYPES[0])
  const [date, setDate] = useState('')
  const [errors, setErrors] = useState<FieldError[]>([])
  const [created, setCreated] = useState<EventVM | null>(null)
  const [message, setMessage] = useState<string | null>(null)

  const mutation = useMutation({
    mutationFn: (): Promise<EventResponse> =>
      api.postJson<EventResponse>('/events', toEventRequest({ id, type, name, scheduledDate: date })),
    onSuccess: (dto) => {
      const view = fromEventResponse(dto)
      setCreated(view)
      auth.selectEvent(view.id)
      setMessage(null)
    },
    onError: (err) => setMessage(err instanceof ApiError ? err.message : 'イベントの作成に失敗しました'),
  })

  function submit(e: React.FormEvent): void {
    e.preventDefault()
    const found = validateEventForm(id, name, type, date)
    setErrors(found)
    if (found.length === 0) mutation.mutate()
  }

  return (
    <main className="event-view">
      <h1>イベント登録</h1>
      <form onSubmit={submit} data-testid="event-form" noValidate>
        <label htmlFor="event-id">イベントID</label>
        <input id="event-id" value={id} onChange={(e) => setId(e.target.value)} data-testid="event-id" />

        <label htmlFor="event-name">名称</label>
        <input id="event-name" value={name} onChange={(e) => setName(e.target.value)} data-testid="event-name" />

        <label htmlFor="event-type">種別</label>
        <select id="event-type" value={type} onChange={(e) => setType(e.target.value)} data-testid="event-type">
          {EVENT_TYPES.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>

        <label htmlFor="event-date">実施日</label>
        <input
          id="event-date"
          type="date"
          value={date}
          onChange={(e) => setDate(e.target.value)}
          data-testid="event-date"
        />

        <button type="submit" disabled={mutation.isPending} data-testid="event-submit">
          作成
        </button>
      </form>

      {errors.map((err) => (
        <p key={err.field} role="alert" data-testid={`event-field-error-${err.field}`}>
          {err.message}
        </p>
      ))}
      {message && (
        <p role="alert" data-testid="event-error">
          {message}
        </p>
      )}
      {created && (
        <section data-testid="event-summary">
          <h2>作成済みイベント</h2>
          <dl>
            <dt>ID</dt>
            <dd>{created.id}</dd>
            <dt>名称</dt>
            <dd>{created.name}</dd>
            <dt>種別</dt>
            <dd>{created.type}</dd>
            <dt>実施日</dt>
            <dd>{created.scheduledDate}</dd>
            <dt>状態</dt>
            <dd>{created.status}</dd>
          </dl>
        </section>
      )}
    </main>
  )
}
