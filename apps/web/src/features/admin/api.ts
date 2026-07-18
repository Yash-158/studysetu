// Thin typed wrappers over apiFetch for the admin people/pools surface (M2).
import { apiFetch } from '../../lib/api'

export type RosterUser = {
  id: string
  role: 'admin' | 'teacher' | 'student'
  display_name: string
  roll_number: string | null
  email: string | null
  status: 'invited' | 'active' | 'disabled'
}

export type CreatedInvite = { user: RosterUser; activation_code: string }

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

export const listUsers = () => apiFetch('/api/institutions/users').then((r) => unwrap<RosterUser[]>(r))

export const inviteUser = (body: {
  role: 'teacher' | 'student'
  display_name: string
  roll_number?: string
  email?: string
}) =>
  apiFetch('/api/institutions/users', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }).then(
    (r) => unwrap<CreatedInvite>(r),
  )

export const importUsersCsv = (csvText: string) =>
  apiFetch('/api/institutions/users/csv', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ csv_text: csvText }),
  }).then((r) => unwrap<{ created: CreatedInvite[] }>(r))

export const reissueCode = (userId: string) =>
  apiFetch(`/api/institutions/users/${userId}/reissue-code`, { method: 'POST' }).then((r) => unwrap<{ activation_code: string }>(r))

export type Pool = { id: string; name: string; member_count: number }
export type PoolMember = { id: string; display_name: string; role: string; roll_number: string | null; email: string | null; status: string }
export type PoolDetail = { id: string; name: string; members: PoolMember[] }

export const listPools = () => apiFetch('/api/pools').then((r) => unwrap<Pool[]>(r))

export const createPool = (name: string) =>
  apiFetch('/api/pools', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name }) }).then(
    (r) => unwrap<Pool>(r),
  )

export const getPool = (poolId: string) => apiFetch(`/api/pools/${poolId}`).then((r) => unwrap<PoolDetail>(r))

export const addPoolMembers = (poolId: string, userIds: string[]) =>
  apiFetch(`/api/pools/${poolId}/members`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_ids: userIds }),
  }).then((r) => unwrap<{ added: number }>(r))

export const removePoolMember = (poolId: string, userId: string) =>
  apiFetch(`/api/pools/${poolId}/members/${userId}`, { method: 'DELETE' }).then((r) => unwrap<{ removed: boolean }>(r))
