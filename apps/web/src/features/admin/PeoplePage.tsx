import { useEffect, useState } from 'react'
import { Button } from '../../components/Button'
import { Card } from '../../components/Card'
import { RosterRow } from '../../components/RosterRow'
import { type CreatedInvite, type RosterUser, importUsersCsv, inviteUser, listUsers, reissueCode } from './api'

function IssuedCodes({ items, onDismiss }: { items: CreatedInvite[]; onDismiss: () => void }) {
  return (
    <Card>
      <div className="ss-stack">
        <h2>Activation codes to distribute</h2>
        <p>Print this list and hand codes to students/teachers who don't have email set.</p>
        <table className="ss-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Roll / email</th>
              <th>Activation code</th>
            </tr>
          </thead>
          <tbody>
            {items.map(({ user, activation_code }) => (
              <tr key={user.id}>
                <td>{user.display_name}</td>
                <td>{user.roll_number ?? user.email}</td>
                <td style={{ fontFamily: 'monospace', fontSize: 16 }}>{activation_code}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="ss-no-print" style={{ display: 'flex', gap: 'var(--space-sm)' }}>
          <Button onClick={() => window.print()}>Print</Button>
          <Button variant="ghost" onClick={onDismiss}>Dismiss</Button>
        </div>
      </div>
    </Card>
  )
}

export function PeoplePage() {
  const [roster, setRoster] = useState<RosterUser[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [issued, setIssued] = useState<CreatedInvite[] | null>(null)

  const [role, setRole] = useState<'student' | 'teacher'>('student')
  const [displayName, setDisplayName] = useState('')
  const [rollNumber, setRollNumber] = useState('')
  const [email, setEmail] = useState('')
  const [busy, setBusy] = useState(false)

  const [csvText, setCsvText] = useState('')
  const [csvBusy, setCsvBusy] = useState(false)

  async function refresh() {
    setLoading(true)
    try {
      setRoster(await listUsers())
    } catch (err) {
      setError((err as { message?: string }).message ?? 'Failed to load roster')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    refresh()
  }, [])

  async function onAddUser(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setBusy(true)
    try {
      const result = await inviteUser({
        role,
        display_name: displayName,
        roll_number: rollNumber || undefined,
        email: email || undefined,
      })
      setIssued([result])
      setDisplayName('')
      setRollNumber('')
      setEmail('')
      await refresh()
    } catch (err) {
      setError((err as { message?: string }).message ?? 'Failed to add user')
    } finally {
      setBusy(false)
    }
  }

  async function onCsvFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (file) setCsvText(await file.text())
  }

  async function onImportCsv(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setCsvBusy(true)
    try {
      const result = await importUsersCsv(csvText)
      setIssued(result.created)
      setCsvText('')
      await refresh()
    } catch (err) {
      setError((err as { message?: string }).message ?? 'CSV import failed')
    } finally {
      setCsvBusy(false)
    }
  }

  async function onReissue(userId: string) {
    setError(null)
    try {
      const result = await reissueCode(userId)
      const user = roster.find((u) => u.id === userId)
      if (user) setIssued([{ user, activation_code: result.activation_code }])
      await refresh()
    } catch (err) {
      setError((err as { message?: string }).message ?? 'Reissue failed')
    }
  }

  return (
    <div className="ss-stack">
      {error && <p className="ss-error">{error}</p>}
      {issued && <IssuedCodes items={issued} onDismiss={() => setIssued(null)} />}

      <Card>
        <form className="ss-stack" onSubmit={onAddUser}>
          <h2>Add a teacher or student</h2>
          <div className="ss-field">
            <label htmlFor="add_role">Role</label>
            <select id="add_role" value={role} onChange={(e) => setRole(e.target.value as 'student' | 'teacher')}>
              <option value="student">Student</option>
              <option value="teacher">Teacher</option>
            </select>
          </div>
          <div className="ss-field">
            <label htmlFor="add_name">Name</label>
            <input id="add_name" value={displayName} onChange={(e) => setDisplayName(e.target.value)} required />
          </div>
          <div className="ss-field">
            <label htmlFor="add_roll">Roll number</label>
            <input id="add_roll" value={rollNumber} onChange={(e) => setRollNumber(e.target.value)} />
          </div>
          <div className="ss-field">
            <label htmlFor="add_email">Email</label>
            <input id="add_email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
          </div>
          <Button type="submit" disabled={busy}>{busy ? 'Adding…' : 'Add and issue activation code'}</Button>
        </form>
      </Card>

      <Card>
        <form className="ss-stack" onSubmit={onImportCsv}>
          <h2>Import a CSV roster</h2>
          <p>Columns: display_name, role (teacher/student), roll_number, email.</p>
          <div className="ss-field">
            <label htmlFor="csv_file">CSV file</label>
            <input id="csv_file" type="file" accept=".csv,text/csv" onChange={onCsvFile} />
          </div>
          <Button type="submit" disabled={csvBusy || !csvText}>{csvBusy ? 'Importing…' : 'Import and issue codes'}</Button>
        </form>
      </Card>

      <Card>
        <h2>Roster</h2>
        {loading ? (
          <p>Loading…</p>
        ) : (
          <table className="ss-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Role</th>
                <th>Roll</th>
                <th>Email</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {roster.map((u) => (
                <RosterRow
                  key={u.id}
                  user={u}
                  action={
                    <Button variant="ghost" onClick={() => onReissue(u.id)}>Reissue activation code</Button>
                  }
                />
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  )
}
