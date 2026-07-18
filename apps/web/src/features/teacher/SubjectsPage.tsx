import { useEffect, useState } from 'react'
import { Button } from '../../components/Button'
import { Card } from '../../components/Card'
import { type Subject, createSubject, listSubjects } from './api'

export function SubjectsPage({ onSelect }: { onSelect: (subjectId: string) => void }) {
  const [subjects, setSubjects] = useState<Subject[]>([])
  const [name, setName] = useState('')
  const [code, setCode] = useState('')
  const [term, setTerm] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    listSubjects().then(setSubjects)
  }, [])

  async function onCreate(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setBusy(true)
    try {
      const subject = await createSubject({ name, code: code || undefined, term: term || undefined })
      setName('')
      setCode('')
      setTerm('')
      setSubjects(await listSubjects())
      onSelect(subject.id)
    } catch (err) {
      setError((err as { message?: string }).message ?? 'Failed to create subject')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="ss-stack">
      {error && <p className="ss-error">{error}</p>}

      <Card>
        <form className="ss-stack" onSubmit={onCreate}>
          <h2>Create a subject</h2>
          <div className="ss-field">
            <label htmlFor="subject_name">Name</label>
            <input id="subject_name" value={name} onChange={(e) => setName(e.target.value)} required />
          </div>
          <div className="ss-field">
            <label htmlFor="subject_code">Code (optional)</label>
            <input id="subject_code" value={code} onChange={(e) => setCode(e.target.value)} />
          </div>
          <div className="ss-field">
            <label htmlFor="subject_term">Term (optional)</label>
            <input id="subject_term" value={term} onChange={(e) => setTerm(e.target.value)} />
          </div>
          <Button type="submit" disabled={busy}>{busy ? 'Creating…' : 'Create subject'}</Button>
        </form>
      </Card>

      <Card>
        <h2>Your subjects</h2>
        {subjects.length === 0 && <p>No subjects yet - create one above.</p>}
        <ul style={{ listStyle: 'none', padding: 0 }}>
          {subjects.map((s) => (
            <li key={s.id}>
              <button className="ss-link" onClick={() => onSelect(s.id)}>
                {s.name} {s.code ? `(${s.code})` : ''}
              </button>{' '}
              <span className={`ss-status-pill ss-status-${s.status === 'draft' ? 'invited' : 'active'}`}>{s.status}</span>
            </li>
          ))}
        </ul>
      </Card>
    </div>
  )
}
