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

export const listMySubjects = () => apiFetch('/api/curriculum/student/subjects').then((r) => unwrap<Subject[]>(r))

export const getMySubject = (subjectId: string) => apiFetch(`/api/curriculum/student/subjects/${subjectId}`).then((r) => unwrap<StudentSubjectDetail>(r))
