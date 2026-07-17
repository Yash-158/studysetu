// Auth store (zustand): tokens, role, refresh. Persisted to localStorage so a reload/browser
// restart keeps the session alive via the refresh token (M1 GATE: "refresh works across restart").
import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { apiUrl } from './config'

export type Role = 'admin' | 'teacher' | 'student'

export type User = {
  id: string
  role: Role
  display_name: string
  roll_number: string | null
  email: string | null
  institution_id: string
  locale: string
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

type AuthState = {
  accessToken: string | null
  refreshToken: string | null
  user: User | null
  hydrated: boolean
  login: (institutionSlug: string, identifier: string, password: string) => Promise<void>
  activate: (
    institutionSlug: string,
    identifier: string,
    activationCode: string,
    newPassword: string,
  ) => Promise<void>
  logout: () => void
  refresh: () => Promise<string | null>
  hydrate: () => Promise<void>
}

export const useAuth = create<AuthState>()(
  persist(
    (set, get) => ({
      accessToken: null,
      refreshToken: null,
      user: null,
      hydrated: false,

      async login(institutionSlug, identifier, password) {
        const res = await fetch(apiUrl('/api/auth/login'), {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ institution_slug: institutionSlug, identifier, password }),
        })
        if (!res.ok) throw await parseError(res)
        const data = await res.json()
        set({ accessToken: data.access_token, refreshToken: data.refresh_token, user: data.user })
      },

      async activate(institutionSlug, identifier, activationCode, newPassword) {
        const res = await fetch(apiUrl('/api/auth/activate'), {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            institution_slug: institutionSlug,
            identifier,
            activation_code: activationCode,
            new_password: newPassword,
          }),
        })
        if (!res.ok) throw await parseError(res)
      },

      logout() {
        set({ accessToken: null, refreshToken: null, user: null })
      },

      async refresh() {
        const rt = get().refreshToken
        if (!rt) return null
        const res = await fetch(apiUrl('/api/auth/refresh'), {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh_token: rt }),
        })
        if (!res.ok) {
          set({ accessToken: null, refreshToken: null, user: null })
          return null
        }
        const data = await res.json()
        set({ accessToken: data.access_token, refreshToken: data.refresh_token })
        return data.access_token as string
      },

      async hydrate() {
        if (get().hydrated) return
        let token = get().accessToken
        if (token) {
          const res = await fetch(apiUrl('/api/auth/me'), { headers: { Authorization: `Bearer ${token}` } })
          if (res.ok) {
            set({ user: await res.json(), hydrated: true })
            return
          }
          token = await get().refresh()
          if (token) {
            const retry = await fetch(apiUrl('/api/auth/me'), { headers: { Authorization: `Bearer ${token}` } })
            if (retry.ok) {
              set({ user: await retry.json(), hydrated: true })
              return
            }
          }
        }
        set({ hydrated: true })
      },
    }),
    {
      name: 'studysetu.auth',
      partialize: (s) => ({ accessToken: s.accessToken, refreshToken: s.refreshToken, user: s.user }),
    },
  ),
)
