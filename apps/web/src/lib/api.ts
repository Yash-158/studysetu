// API client: generated types from OpenAPI land in packages/shared; thin fetch wrapper here.
// Attaches the current access token and retries once (after a token refresh) on a 401.
import { apiUrl } from './config'
import { useAuth } from './auth'

export async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const token = useAuth.getState().accessToken
  const headers = new Headers(init.headers)
  if (token) headers.set('Authorization', `Bearer ${token}`)

  let res = await fetch(apiUrl(path), { ...init, headers })
  if (res.status === 401 && useAuth.getState().refreshToken) {
    const fresh = await useAuth.getState().refresh()
    if (fresh) {
      headers.set('Authorization', `Bearer ${fresh}`)
      res = await fetch(apiUrl(path), { ...init, headers })
    }
  }
  return res
}
