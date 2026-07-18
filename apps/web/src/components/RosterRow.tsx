// DESIGN.md component inventory: RosterRow (build once, reuse everywhere).
import type { ReactNode } from 'react'
import type { RosterUser } from '../features/admin/api'

export function RosterRow({ user, action }: { user: RosterUser; action?: ReactNode }) {
  return (
    <tr>
      <td>{user.display_name}</td>
      <td>{user.role}</td>
      <td>{user.roll_number ?? '—'}</td>
      <td>{user.email ?? '—'}</td>
      <td>
        <span className={`ss-status-pill ss-status-${user.status}`}>{user.status}</span>
      </td>
      <td>{action}</td>
    </tr>
  )
}
