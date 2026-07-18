import { useState } from 'react'
import { RoleShell } from '../../components/RoleShell'
import { SubjectViewPage } from './SubjectViewPage'
import { SubjectsPage } from './SubjectsPage'

export function StudentShell() {
  const [subjectId, setSubjectId] = useState<string | null>(null)

  return (
    <RoleShell roleLabel="Student">
      {subjectId ? (
        <SubjectViewPage subjectId={subjectId} onBack={() => setSubjectId(null)} />
      ) : (
        <SubjectsPage onSelect={setSubjectId} />
      )}
    </RoleShell>
  )
}
