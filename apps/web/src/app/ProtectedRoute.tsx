import type { ReactNode } from 'react'
import { Navigate } from 'react-router-dom'
import { useAuth, type Role } from '../lib/auth'
import { ForbiddenPage } from './ForbiddenPage'

export function ProtectedRoute({ role, children }: { role: Role; children: ReactNode }) {
  const accessToken = useAuth((s) => s.accessToken)
  const user = useAuth((s) => s.user)
  const hydrated = useAuth((s) => s.hydrated)

  if (!hydrated) return null
  if (!accessToken || !user) return <Navigate to="/login" replace />
  // Wrong-role route access = 403 (M1 GATE): rendered in place, URL unchanged, no redirect.
  if (user.role !== role) return <ForbiddenPage />
  return <>{children}</>
}
