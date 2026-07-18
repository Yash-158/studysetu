import { useEffect, useState } from 'react'
import { Card } from '../../components/Card'
import { type Subject } from '../teacher/api'
import { listMySubjects } from './api'

export function SubjectsPage({ onSelect }: { onSelect: (subjectId: string) => void }) {
  const [subjects, setSubjects] = useState<Subject[]>([])

  useEffect(() => {
    listMySubjects().then(setSubjects)
  }, [])

  return (
    <Card>
      <h2>Your subjects</h2>
      {subjects.length === 0 && <p>Nothing published to you yet - check back once your teacher publishes a chapter.</p>}
      <ul style={{ listStyle: 'none', padding: 0 }}>
        {subjects.map((s) => (
          <li key={s.id}>
            <button className="ss-link" onClick={() => onSelect(s.id)}>
              {s.name} {s.code ? `(${s.code})` : ''}
            </button>
          </li>
        ))}
      </ul>
    </Card>
  )
}
