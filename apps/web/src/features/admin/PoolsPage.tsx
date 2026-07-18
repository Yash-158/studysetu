import { useEffect, useState } from 'react'
import { Button } from '../../components/Button'
import { Card } from '../../components/Card'
import { type Pool, type PoolDetail, type RosterUser, addPoolMembers, createPool, getPool, listPools, listUsers, removePoolMember } from './api'

export function PoolsPage() {
  const [pools, setPools] = useState<Pool[]>([])
  const [roster, setRoster] = useState<RosterUser[]>([])
  const [selectedPoolId, setSelectedPoolId] = useState<string | null>(null)
  const [detail, setDetail] = useState<PoolDetail | null>(null)
  const [error, setError] = useState<string | null>(null)

  const [poolName, setPoolName] = useState('')
  const [busy, setBusy] = useState(false)
  const [toAdd, setToAdd] = useState<Set<string>>(new Set())

  async function refreshPools() {
    setPools(await listPools())
  }

  useEffect(() => {
    refreshPools()
    listUsers().then(setRoster)
  }, [])

  useEffect(() => {
    if (!selectedPoolId) {
      setDetail(null)
      return
    }
    getPool(selectedPoolId).then(setDetail)
  }, [selectedPoolId])

  async function onCreatePool(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setBusy(true)
    try {
      const pool = await createPool(poolName)
      setPoolName('')
      await refreshPools()
      setSelectedPoolId(pool.id)
    } catch (err) {
      setError((err as { message?: string }).message ?? 'Failed to create pool')
    } finally {
      setBusy(false)
    }
  }

  async function onAddMembers() {
    if (!selectedPoolId || toAdd.size === 0) return
    setError(null)
    try {
      await addPoolMembers(selectedPoolId, [...toAdd])
      setToAdd(new Set())
      setDetail(await getPool(selectedPoolId))
      await refreshPools()
    } catch (err) {
      setError((err as { message?: string }).message ?? 'Failed to add members')
    }
  }

  async function onRemoveMember(userId: string) {
    if (!selectedPoolId) return
    await removePoolMember(selectedPoolId, userId)
    setDetail(await getPool(selectedPoolId))
    await refreshPools()
  }

  const memberIds = new Set(detail?.members.map((m) => m.id) ?? [])
  const available = roster.filter((u) => u.role === 'student' && !memberIds.has(u.id))

  return (
    <div className="ss-stack">
      {error && <p className="ss-error">{error}</p>}

      <Card>
        <form className="ss-stack" onSubmit={onCreatePool}>
          <h2>Create a pool</h2>
          <div className="ss-field">
            <label htmlFor="pool_name">Name</label>
            <input id="pool_name" value={poolName} onChange={(e) => setPoolName(e.target.value)} required />
          </div>
          <Button type="submit" disabled={busy}>{busy ? 'Creating…' : 'Create pool'}</Button>
        </form>
      </Card>

      <Card>
        <h2>Pools</h2>
        <ul style={{ listStyle: 'none', padding: 0 }}>
          {pools.map((p) => (
            <li key={p.id}>
              <button className="ss-link" onClick={() => setSelectedPoolId(p.id)}>
                {p.name} ({p.member_count} members)
              </button>
            </li>
          ))}
        </ul>
      </Card>

      {detail && (
        <Card>
          <h2>{detail.name}</h2>
          <table className="ss-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Roll</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {detail.members.map((m) => (
                <tr key={m.id}>
                  <td>{m.display_name}</td>
                  <td>{m.roll_number ?? '—'}</td>
                  <td>{m.status}</td>
                  <td>
                    <Button variant="ghost" onClick={() => onRemoveMember(m.id)}>Remove</Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {available.length > 0 && (
            <div className="ss-stack">
              <h3>Add students</h3>
              {available.map((u) => (
                <label key={u.id} style={{ display: 'block' }}>
                  <input
                    type="checkbox"
                    checked={toAdd.has(u.id)}
                    onChange={(e) => {
                      const next = new Set(toAdd)
                      if (e.target.checked) next.add(u.id)
                      else next.delete(u.id)
                      setToAdd(next)
                    }}
                  />{' '}
                  {u.display_name} ({u.roll_number ?? u.email})
                </label>
              ))}
              <Button onClick={onAddMembers} disabled={toAdd.size === 0}>Add selected</Button>
            </div>
          )}
        </Card>
      )}
    </div>
  )
}
