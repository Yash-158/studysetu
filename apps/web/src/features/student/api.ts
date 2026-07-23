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

// M5: session planner + player (FEATURE_EXPLANATION F8/F9, S16 recipe cards).
export type PracticeItemRef = { item_id: string; topic_id: string; stem: string; options: SafeOption[] }
export type LessonSection = { heading: string; body: string }
export type SessionCard =
  | { type: 'bridge'; text: string }
  | { type: 'revision'; topic_id: string; topic_title: string; explanation: string; practice_items: PracticeItemRef[] }
  | { type: 'explanation'; topic_id: string; sections: LessonSection[] }
  | { type: 'worked_example'; steps: string[] }
  | { type: 'practice'; item_id: string; topic_id: string; stem: string; options: SafeOption[] }
  | { type: 'contrast'; misconception_title: string; text: string }
  | { type: 'summary'; bullets: string[] }
  | { type: 'cheatsheet'; text: string }
export type SessionOut = { session_id: string; topic_id: string; status: string; cards: SessionCard[]; resume_index: number }
export type PracticeResult = { is_correct: boolean; correct_option_id: string | null; explanation: string }

export const startSession = (topicId: string) =>
  apiFetch(`/api/learning/topics/${topicId}/session/start`, { method: 'POST' }).then((r) => unwrap<SessionOut>(r))

export const getSession = (sessionId: string) =>
  apiFetch(`/api/learning/sessions/${sessionId}`).then((r) => unwrap<SessionOut>(r))

export const answerPractice = (sessionId: string, itemId: string, optionId: string) =>
  apiFetch(`/api/learning/sessions/${sessionId}/practice/answer`, { method: 'POST', ...json({ item_id: itemId, option_id: optionId }) }).then((r) => unwrap<PracticeResult>(r))

export const completeSession = (sessionId: string) =>
  apiFetch(`/api/learning/sessions/${sessionId}/complete`, { method: 'POST' }).then((r) => unwrap<{ session_id: string; status: string }>(r))

// M6-remediation Phase 5: topic-scoped doubt chat (F11 minimal slice, modules/doubts.py).
export type DoubtAnswer = { doubt_id: string; answer: string }

export const askDoubt = (sessionId: string, question: string) =>
  apiFetch(`/api/doubts/sessions/${sessionId}/ask`, { method: 'POST', ...json({ question }) }).then((r) => unwrap<DoubtAnswer>(r))
