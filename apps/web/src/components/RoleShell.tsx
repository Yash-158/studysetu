// Shared chrome for the three role-routed shells (student/teacher/admin). Each shell's own
// content grows starting M2+; M1 ships the skeleton (RULES.md folder discipline: shared UI in
// components/, feature-specific screens in features/<role>/).
import type { ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button } from './Button'
import { Logo } from './Logo'
import { useAuth } from '../lib/auth'

export function RoleShell({
  roleLabel,
  children,
  wide = false,
  sidebar,
}: {
  roleLabel: string
  children?: ReactNode
  wide?: boolean
  /** M6-remediation Phase 2: an ERP-style persistent left nav (currently teacher-only - Subjects/
   * Analytics). Optional so student/admin shells are untouched - they still get the plain centered
   * container. */
  sidebar?: ReactNode
}) {
  const navigate = useNavigate()
  const user = useAuth((s) => s.user)
  const logout = useAuth((s) => s.logout)

  return (
    <div>
      <header className="ss-shell-header">
        <Logo />
        <span>
          {user?.display_name} · {roleLabel}{' '}
          <Button
            variant="ghost"
            onClick={() => {
              logout()
              navigate('/login', { replace: true })
            }}
          >
            Log out
          </Button>
        </span>
      </header>
      {sidebar ? (
        <div className="ss-workspace">
          <nav className="ss-sidebar" aria-label={`${roleLabel} navigation`}>{sidebar}</nav>
          <div className="ss-workspace-main">{children}</div>
        </div>
      ) : (
        <div className={wide ? 'ss-container-wide' : 'ss-container'}>
          {children ?? <p>Your {roleLabel} shell will grow here starting M2.</p>}
        </div>
      )}
    </div>
  )
}
