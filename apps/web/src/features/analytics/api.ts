// Thin typed wrappers over apiFetch for the teacher's analytics command center (M6).
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

export type StuckSignal = {
  kind: 'session' | 'diagnostic'
  student_id: string
  student_name: string
  topic_id: string
  topic_title: string
  subject_id: string
  subject_title: string
  stalled_minutes: number
}

export type ClusterStudent = { id: string; display_name: string }
export type Cluster = {
  misconception_id: string
  misconception_code: string
  misconception_title: string
  topic_id: string
  topic_title: string
  subject_id: string
  subject_title: string
  student_count: number
  students: ClusterStudent[]
}

export type UngradedSignal = { topic_id: string; topic_title: string; subject_id: string; subject_title: string; draft_count: number }

export type Today = { stuck: StuckSignal[]; clusters: Cluster[]; ungraded: UngradedSignal[] }

export const getToday = () => apiFetch('/api/analytics/today').then((r) => unwrap<Today>(r))

export type ExplorerSubject = { id: string; name: string; code: string | null; status: string; student_count: number; avg_mastery: number | null }
export const listExplorerSubjects = () => apiFetch('/api/analytics/explorer/subjects').then((r) => unwrap<ExplorerSubject[]>(r))

export type ExplorerTopic = {
  id: string
  title: string
  avg_mastery: number | null
  completion_pct: number | null
  top_misconceptions: { misconception_id: string; misconception_title: string; student_count: number }[]
}
export type ExplorerChapter = { id: string; title: string; position: number; topics: ExplorerTopic[] }
export type ExplorerSubjectDetail = { id: string; name: string; student_count: number; chapters: ExplorerChapter[] }
export const getExplorerSubject = (subjectId: string) =>
  apiFetch(`/api/analytics/explorer/subjects/${subjectId}`).then((r) => unwrap<ExplorerSubjectDetail>(r))

export type HeatGrid = { students: { id: string; display_name: string }[]; topics: { id: string; title: string }[]; cells: { student_id: string; topic_id: string; p_known: number }[] }
export const getExplorerHeat = (subjectId: string) => apiFetch(`/api/analytics/explorer/subjects/${subjectId}/heat`).then((r) => unwrap<HeatGrid>(r))

export type TopicStudent = { student_id: string; display_name: string; p_known: number | null; attempts_count: number; last_activity_at: string | null }
export const getExplorerTopicStudents = (topicId: string) =>
  apiFetch(`/api/analytics/explorer/topics/${topicId}/students`).then((r) => unwrap<TopicStudent[]>(r))

export type StudentMastery = { topic_id: string; topic_title: string | null; p_known: number; attempts_count: number }
export type StudentTimelineEvent = { id: string; event_type: string; topic_id: string | null; topic_title: string | null; payload: Record<string, unknown>; occurred_at: string }
export type WrongAttempt = { attempt_id: string; item_stem: string; chosen_option_body: string; misconception_title: string | null; topic_id: string; topic_title: string | null; occurred_at: string }
export type StudentArtifact = { id: string; artifact_type: string; topic_id: string | null; topic_title: string | null; model: string | null; created_at: string; flagged: boolean; hidden: boolean }
export type StudentDetail = {
  student: { id: string; display_name: string; roll_number: string | null; enrollment_status: string }
  mastery: StudentMastery[]
  timeline: StudentTimelineEvent[]
  wrong_attempts: WrongAttempt[]
  artifacts: StudentArtifact[]
}
export const getStudentDetail = (studentId: string, subjectId: string, misconceptionId?: string) => {
  const params = new URLSearchParams({ subject_id: subjectId })
  if (misconceptionId) params.set('misconception_id', misconceptionId)
  return apiFetch(`/api/analytics/students/${studentId}?${params}`).then((r) => unwrap<StudentDetail>(r))
}

export const flagArtifact = (artifactId: string) =>
  apiFetch(`/api/analytics/artifacts/${artifactId}/flag`, { method: 'POST' }).then((r) => unwrap<{ id: string; flagged: boolean }>(r))
