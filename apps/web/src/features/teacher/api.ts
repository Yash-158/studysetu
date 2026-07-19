// Thin typed wrappers over apiFetch for the teacher curriculum-builder surface (M3).
import { apiFetch } from '../../lib/api'

export type Subject = { id: string; name: string; code: string | null; term: string | null; status: 'draft' | 'published' | 'archived' }
export type Topic = { id: string; title: string; description: string }
export type Block = {
  id: string
  position: number
  block_type: 'topic' | 'assessment'
  topic?: Topic
  assessment?: { id: string; title: string; status: string }
}
export type Chapter = { id: string; title: string; position: number; status: 'draft' | 'published' | 'archived'; blocks: Block[] }
export type Edge = { src_topic_id: string; dst_topic_id: string; origin: string }
export type Material = {
  id: string
  owner_type: 'subject' | 'chapter' | 'topic'
  owner_id: string
  kind: 'pdf' | 'note' | 'link' | 'image'
  title: string
  url: string | null
  readability: 'readable' | 'stored_only'
  created_at: string
}
export type SubjectDetail = Subject & { chapters: Chapter[]; topics: Topic[]; edges: Edge[]; materials: Material[] }
export type Pool = { id: string; name: string }
export type PoolDelta = { pool_id: string; pool_name: string; new_member_count: number; new_members: { id: string; display_name: string }[] }
export type Enrollment = { id: string; display_name: string; roll_number: string | null; source_pool_id: string | null }

export type Misconception = { code: string; title: string }
export type ItemOption = { id: string; position: number; body: string; is_correct: boolean; misconception: Misconception | null }
export type BankItem = {
  id: string
  topic_id: string
  status: 'draft' | 'approved' | 'flagged' | 'retired'
  stem: string
  difficulty: -1 | 0 | 1
  explanation: string
  options: ItemOption[]
}

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

export const listSubjects = () => apiFetch('/api/curriculum/subjects').then((r) => unwrap<Subject[]>(r))

export const createSubject = (body: { name: string; code?: string; term?: string }) =>
  apiFetch('/api/curriculum/subjects', { method: 'POST', ...json(body) }).then((r) => unwrap<Subject>(r))

export const getSubject = (subjectId: string) => apiFetch(`/api/curriculum/subjects/${subjectId}`).then((r) => unwrap<SubjectDetail>(r))

export const createChapter = (subjectId: string, title: string) =>
  apiFetch(`/api/curriculum/subjects/${subjectId}/chapters`, { method: 'POST', ...json({ title }) }).then((r) => unwrap<Chapter>(r))

export const reorderChapters = (subjectId: string, ids: string[]) =>
  apiFetch(`/api/curriculum/subjects/${subjectId}/chapters/reorder`, { method: 'PUT', ...json({ ids }) }).then((r) => unwrap<{ reordered: number }>(r))

export const publishChapter = (chapterId: string) =>
  apiFetch(`/api/curriculum/chapters/${chapterId}/publish`, { method: 'POST' }).then((r) => unwrap<Chapter & { subject_status: string }>(r))

export const createTopic = (subjectId: string, body: { title: string; description?: string }) =>
  apiFetch(`/api/curriculum/subjects/${subjectId}/topics`, { method: 'POST', ...json(body) }).then((r) => unwrap<Topic>(r))

export const addBlock = (chapterId: string, body: { block_type: 'topic' | 'assessment'; topic_id?: string; assessment_title?: string }) =>
  apiFetch(`/api/curriculum/chapters/${chapterId}/blocks`, { method: 'POST', ...json(body) }).then((r) => unwrap<{ id: string; position: number; block_type: string }>(r))

export const reorderBlocks = (chapterId: string, ids: string[]) =>
  apiFetch(`/api/curriculum/chapters/${chapterId}/blocks/reorder`, { method: 'PUT', ...json({ ids }) }).then((r) => unwrap<{ reordered: number }>(r))

export const deleteBlock = (chapterId: string, blockId: string) =>
  apiFetch(`/api/curriculum/chapters/${chapterId}/blocks/${blockId}`, { method: 'DELETE' }).then((r) => unwrap<{ removed: boolean }>(r))

export const listEdges = (subjectId: string) => apiFetch(`/api/curriculum/subjects/${subjectId}/edges`).then((r) => unwrap<Edge[]>(r))

export const createEdge = (topicId: string, dstTopicId: string) =>
  apiFetch(`/api/curriculum/topics/${topicId}/edges`, { method: 'POST', ...json({ dst_topic_id: dstTopicId }) }).then((r) => unwrap<Edge>(r))

export const deleteEdge = (topicId: string, dstTopicId: string) =>
  apiFetch(`/api/curriculum/topics/${topicId}/edges/${dstTopicId}`, { method: 'DELETE' }).then((r) => unwrap<{ removed: boolean }>(r))

export const createMaterial = (form: FormData) => apiFetch('/api/curriculum/materials', { method: 'POST', body: form }).then((r) => unwrap<Material>(r))

export const listPools = () => apiFetch('/api/curriculum/pools').then((r) => unwrap<Pool[]>(r))

export const attachPool = (subjectId: string, poolId: string) =>
  apiFetch(`/api/curriculum/subjects/${subjectId}/pools/${poolId}/attach`, { method: 'POST' }).then((r) => unwrap<{ attached: number }>(r))

export const poolDeltas = (subjectId: string) => apiFetch(`/api/curriculum/subjects/${subjectId}/pool-deltas`).then((r) => unwrap<PoolDelta[]>(r))

export const syncPool = (subjectId: string, poolId: string) =>
  apiFetch(`/api/curriculum/subjects/${subjectId}/pools/${poolId}/sync`, { method: 'POST' }).then((r) => unwrap<{ added: number }>(r))

export const listEnrollments = (subjectId: string) => apiFetch(`/api/curriculum/subjects/${subjectId}/enrollments`).then((r) => unwrap<Enrollment[]>(r))

export const removeEnrollment = (subjectId: string, userId: string) =>
  apiFetch(`/api/curriculum/subjects/${subjectId}/enrollments/${userId}`, { method: 'DELETE' }).then((r) => unwrap<{ archived: boolean }>(r))

export const generateBank = (topicId: string) =>
  apiFetch(`/api/assessment/topics/${topicId}/bank/generate`, { method: 'POST' }).then((r) => unwrap<{ generated: boolean; cache_hit: boolean; items: BankItem[] }>(r))

export const getBank = (topicId: string) => apiFetch(`/api/assessment/topics/${topicId}/bank`).then((r) => unwrap<BankItem[]>(r))

export const approveItem = (itemId: string) =>
  apiFetch(`/api/assessment/items/${itemId}/approve`, { method: 'POST' }).then((r) => unwrap<{ id: string; status: string }>(r))

export const approveAllBank = (topicId: string) =>
  apiFetch(`/api/assessment/topics/${topicId}/bank/approve-all`, { method: 'POST' }).then((r) => unwrap<{ approved: number }>(r))
