// Shared chrome for the three role-routed shells (student/teacher/admin). Each shell's own
// content grows starting M2+; M1 ships the skeleton (RULES.md folder discipline: shared UI in
// components/, feature-specific screens in features/<role>/).
import type { ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button } from './Button'
import { useAuth } from '../lib/auth'
import { getConfig } from '../lib/config'

export function RoleShell({
  roleLabel,
  children,
  wide = false,
}: {
  roleLabel: string
  children?: ReactNode
  wide?: boolean
}) {
  const navigate = useNavigate()
  const user = useAuth((s) => s.user)
  const logout = useAuth((s) => s.logout)
  const product = getConfig().product as { name?: string } | undefined

  return (
    <div>
      <header className="ss-shell-header">
        <strong>{product?.name ?? 'StudySetu'}</strong>
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
      <div className={wide ? 'ss-container-wide' : 'ss-container'}>
        {children ?? <p>Your {roleLabel} shell will grow here starting M2.</p>}
      </div>
    </div>
  )
}
