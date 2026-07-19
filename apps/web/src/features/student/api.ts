// Thin typed wrappers over apiFetch for the student's read-only published-structure view (M3).
import { apiFetch } from '../../lib/api'
import type { Chapter, Edge, Material, Subject } from '../teacher/api'

export type StudentSubjectDetail = Subject & { chapters: Chapter[]; edges: Edge[]; materials: Material[] }

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

const json = (body: unknown) => ({ headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })

export const listMySubjects = () => apiFetch('/api/curriculum/student/subjects').then((r) => unwrap<Subject[]>(r))

export const getMySubject = (subjectId: string) => apiFetch(`/api/curriculum/student/subjects/${subjectId}`).then((r) => unwrap<StudentSubjectDetail>(r))

export type SafeOption = { id: string; position: number; body: string }
export type DiagnosticItem = { id: string; stem: string; options: SafeOption[] }
export type DiagnosticStart = { diagnostic_id: string; topic_id: string; items: DiagnosticItem[] }
export type AnswerAck = { ack: string; completed: boolean }
export type ReviewOption = { id: string; body: string; is_correct: boolean }
export type ReviewItem = {
  item_id: string
  stem: string
  options: ReviewOption[]
  chosen_option_id: string | null
  correct_option_id: string | null
  is_correct: boolean | null
  explanation: string
}
export type MasteryRow = { topic_id: string; topic_title: string; p_known: number | null }
export type DiagnosticReview = { diagnostic_id: string; topic_id: string; score: number | null; total: number; review: ReviewItem[]; mastery: MasteryRow[] }

export const startDiagnostic = (topicId: string) =>
  apiFetch(`/api/learning/topics/${topicId}/diagnostic/start`, { method: 'POST' }).then((r) => unwrap<DiagnosticStart>(r))

export const answerDiagnostic = (diagnosticId: string, itemId: string, optionId: string) =>
  apiFetch(`/api/learning/diagnostic/${diagnosticId}/answer`, { method: 'POST', ...json({ item_id: itemId, option_id: optionId }) }).then((r) => unwrap<AnswerAck>(r))

export const getDiagnosticReview = (diagnosticId: string) =>
  apiFetch(`/api/learning/diagnostic/${diagnosticId}`).then((r) => unwrap<DiagnosticReview>(r))
