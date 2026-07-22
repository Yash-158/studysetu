// Thin typed wrapper over apiFetch for the student's own event-sourced timeline (F13).
import { apiFetch } from '../../lib/api'

type ApiError = { code: string; message: string; hint: string }

async function parseError(res: Response): Promise<ApiError> {
  try {
    const body = await res.json()
    return body.detail ?? { code: 'error', message: 'Request failed', hint: '' }
  } catch {
    return { code: 'error', message: `Request failed (${res.status})`, hint: '' }
  }
}

async function unwrap<T>(res: Response): Promise<T> {
  if (!res.ok) throw await parseError(res)
  return res.json() as Promise<T>
}

export type TimelineEvent = {
  id: string
  event_type: string
  topic_id: string | null
  topic_title: string | null
  subject_id: string | null
  subject_title: string | null
  payload: Record<string, unknown>
  occurred_at: string
}

export const getMyTimeline = () => apiFetch('/api/timeline/me').then((r) => unwrap<{ events: TimelineEvent[] }>(r))
